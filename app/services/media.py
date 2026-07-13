import base64
import logging
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import openai
from PIL import Image, ImageFont
import imageio_ffmpeg

from app.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
)
from app.services.cancellation import RenderCancelled
from app.services.openai_client import get_openai_client
from app.services.audio import master_audio
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.services.subprocess_utils import run_cancellable
from app.models import Storyboard, ShortScript
from app.captions.engine import build_caption_document
from app.cinema.motion import compose_motion_filter
from app.narration import voice_selection as narration_voices
from app.narration.instructions import build_narration_instructions
from app.narration.pauses import plan_pauses
from app.narration.pronunciation import apply_pronunciation_hints
from app.rendering.graph import RenderGraph
from app.visual_continuity.cache import ImageAssetCache, cache_key
from app.visual_continuity.config import image_cache_enabled

if TYPE_CHECKING:
    from app.production.preferences import UserCreativePreferences

logger = logging.getLogger(__name__)

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TRANSITION_SECONDS = 0.32

# Per-scene image generation is one independent OpenAI network call per
# scene (its own prompt, its own output file, no shared state) -- profiling
# showed it was, by far, the single largest bottleneck in the whole
# pipeline (roughly a third of total production time for a typical 2-minute
# documentary) purely because 16+ of these calls were made one at a time.
# Bounded concurrency here overlaps request latency; the rate limiter below
# is what actually keeps requests within the account's real per-minute
# image rate limit regardless of concurrency -- see PROFILING_REPORT.md.
MAX_CONCURRENT_IMAGE_GENERATIONS = 4

MAX_IMAGE_GENERATION_RETRIES = 3
_RATE_LIMIT_RETRY_HINT = re.compile(r"try again in (\d+(?:\.\d+)?)s", re.IGNORECASE)


def _image_rate_limit_per_minute() -> int:
    try:
        value = int(os.getenv("OPENAI_IMAGE_RATE_LIMIT_PER_MINUTE", "5"))
    except (TypeError, ValueError):
        value = 5
    return max(1, value)


# Shared across every concurrent worker so parallel scene-image generation
# (MAX_CONCURRENT_IMAGE_GENERATIONS) can never dispatch more requests per
# minute than the account actually allows -- concurrency alone caused a
# real production failure (openai.RateLimitError, "Limit 5, Used 5" on
# gpt-image-1) because bursting 4 requests at once blew straight past a
# tight per-minute cap that sequential ~15s-apart calls happened to stay
# under by luck, not by design. Conservative default of 5/min; raise
# OPENAI_IMAGE_RATE_LIMIT_PER_MINUTE for accounts with a higher tier.
_image_rate_limiter = SlidingWindowRateLimiter(
    max_calls=_image_rate_limit_per_minute(), period_seconds=60.0
)

# Final render resolution and the closest OpenAI gpt-image-1 generation size
# per aspect ratio. generate_scene_image() always crops/resizes to an exact
# (width, height) target regardless of what the API returns, so choosing the
# closest supported generation size only affects upscaling quality, not
# correctness. "9:16" reproduces the historical WIDTH/HEIGHT constants
# exactly so existing behavior is unchanged unless a different ratio is
# explicitly requested.
_ASPECT_RATIO_RESOLUTIONS: dict[str, tuple[int, int, str]] = {
    "9:16": (1080, 1920, "1024x1536"),
    "16:9": (1920, 1080, "1536x1024"),
    "1:1": (1080, 1080, "1024x1024"),
    "4:5": (1080, 1350, "1024x1536"),
}


def resolution_for_aspect_ratio(aspect_ratio: str | None) -> tuple[int, int, str]:
    return _ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "9:16", _ASPECT_RATIO_RESOLUTIONS["9:16"])


def _font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


# Voice pools/selection now live in app.narration.voice_selection (Narration
# Engine v2); re-exported here so existing call sites/tests that import them
# from app.services.media keep working unchanged.
MALE_VOICES = narration_voices.MALE_VOICES
FEMALE_VOICES = narration_voices.FEMALE_VOICES
gender_for_voice = narration_voices.gender_for_voice


def voice_for_character(
    character_bible,
    preferences: "UserCreativePreferences | None" = None,
    default_voice: str = OPENAI_TTS_VOICE,
) -> str:
    """Pick a narrator voice, honoring an explicit user request first.

    Thin backward-compatible wrapper over
    app.narration.voice_selection.select_voice, which also logs the
    selection and records any accent-guarantee warning. Priority: an
    explicit ``preferences.narrator.gender`` (the user's own words) always
    wins, even when no Character Bible exists (a video can have a female
    narrator with no on-screen presenter). Only when the user did not
    specify a gender does the Character Bible's gender apply.
    """

    return narration_voices.select_voice(character_bible, preferences, default_voice).voice


def generate_voiceover(
    script: ShortScript,
    output_path: Path,
    voice: str = OPENAI_TTS_VOICE,
    preferences: "UserCreativePreferences | None" = None,
    cancellation_check: Callable[[], bool] | None = None,
):
    if cancellation_check and cancellation_check():
        raise RenderCancelled("Rendering cancelled before voiceover generation.")
    # Pause planning and pronunciation hints only ever touch this TTS-input
    # copy -- scene.narration (what captions read) is never modified.
    narration_text = apply_pronunciation_hints(plan_pauses(script.voiceover))
    speed = narration_voices.effective_speed(preferences)
    kwargs = {"speed": speed} if speed is not None else {}
    response = get_openai_client().audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=voice,
        input=narration_text,
        instructions=build_narration_instructions(preferences),
        **kwargs,
    )
    output_path.write_bytes(response.read())


_ASPECT_RATIO_LABELS = {
    "9:16": "Portrait 9:16",
    "16:9": "Landscape 16:9",
    "1:1": "Square 1:1",
    "4:5": "Portrait 4:5",
}


def _is_quota_error(exc: openai.RateLimitError) -> bool:
    return "quota" in str(exc).casefold()


def _retry_delay_seconds(exc: openai.RateLimitError, attempt: int) -> float:
    match = _RATE_LIMIT_RETRY_HINT.search(str(exc))
    if match:
        return float(match.group(1)) + 0.5
    return min(20.0, 2.0 * (2**attempt))


def _generate_image(
    prompt: str,
    size: str,
    aspect_ratio: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
):
    """Call images.generate(), rate-limited across every concurrent
    worker and retried with backoff on a transient 429 rate-limit error --
    but never retried on quota exhaustion (insufficient_quota), which
    cannot succeed by waiting and retrying."""

    full_prompt = (
        prompt
        + f"\n{_ASPECT_RATIO_LABELS.get(aspect_ratio, 'Portrait 9:16')} composition, "
          "cinematic documentary style, "
          "dark neutral palette, subtle warm highlights, realistic lighting, "
          "consistent fictional character identity when a recurring protagonist appears, "
          "no text, no logo, no watermark."
    )
    attempt = 0
    while True:
        _image_rate_limiter.acquire()
        try:
            return get_openai_client().images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=full_prompt,
                size=size,
                quality="low",
            )
        except openai.RateLimitError as exc:
            if _is_quota_error(exc) or attempt >= MAX_IMAGE_GENERATION_RETRIES:
                raise
            sleep(_retry_delay_seconds(exc, attempt))
            attempt += 1


def generate_scene_image(
    prompt: str,
    output_path: Path,
    width: int = WIDTH,
    height: int = HEIGHT,
    size: str = "1024x1536",
    aspect_ratio: str = "9:16",
    cancellation_check: Callable[[], bool] | None = None,
):
    if cancellation_check and cancellation_check():
        raise RenderCancelled("Rendering cancelled before scene image generation.")
    result = _generate_image(prompt, size, aspect_ratio)

    image_data = result.data[0]
    if getattr(image_data, "b64_json", None):
        raw = base64.b64decode(image_data.b64_json)
    else:
        raise RuntimeError("Image generation returned no base64 image data.")

    temp = output_path.with_suffix(".raw.png")
    temp.write_bytes(raw)

    with Image.open(temp).convert("RGB") as image:
        ratio = max(width / image.width, height / image.height)
        resized = image.resize(
            (int(image.width * ratio), int(image.height * ratio)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        final = resized.crop((left, top, left + width, top + height))
        final.save(output_path, quality=92)

    temp.unlink(missing_ok=True)


def _motion_filter(scene, frames: int, is_first: bool = False, is_last: bool = False) -> str:
    motion = getattr(scene, "motion_type", "dolly_in")
    hook = scene.number == 1
    fade_out_start = max(0.0, frames / FPS - TRANSITION_SECONDS)
    fade_in_filter = "" if is_first else f"fade=t=in:st=0:d={TRANSITION_SECONDS},"
    fade_out_filter = "" if is_last else (
        f"fade=t=out:st={fade_out_start:.3f}:d={TRANSITION_SECONDS},"
    )

    zoom_speed = 0.0012 if hook else 0.00065
    max_zoom = 1.13 if hook else 1.08

    if motion == "dolly_out":
        zoom = f"if(eq(on,1),{max_zoom},max(1.0,zoom-{zoom_speed}))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "pan_left":
        zoom = "1.06"
        x = "max(0,(iw-iw/zoom)*(1-on/{frames}))".replace("{frames}", str(max(1, frames)))
        y = "ih/2-(ih/zoom/2)"
    elif motion == "pan_right":
        zoom = "1.06"
        x = "min(iw-iw/zoom,(iw-iw/zoom)*(on/{frames}))".replace("{frames}", str(max(1, frames)))
        y = "ih/2-(ih/zoom/2)"
    elif motion == "tilt_up":
        zoom = "1.06"
        x = "iw/2-(iw/zoom/2)"
        y = "max(0,(ih-ih/zoom)*(1-on/{frames}))".replace("{frames}", str(max(1, frames)))
    elif motion == "tilt_down":
        zoom = "1.06"
        x = "iw/2-(iw/zoom/2)"
        y = "min(ih-ih/zoom,(ih-ih/zoom)*(on/{frames}))".replace("{frames}", str(max(1, frames)))
    elif motion == "drift":
        zoom = "1.045+0.004*sin(on/38)"
        x = "iw/2-(iw/zoom/2)+10*sin(on/24)"
        y = "ih/2-(ih/zoom/2)+7*cos(on/31)"
    elif motion == "parallax_left":
        zoom = "1.07"
        x = "iw/2-(iw/zoom/2)+14*sin(on/30)"
        y = "ih/2-(ih/zoom/2)+4*cos(on/43)"
    elif motion == "parallax_right":
        zoom = "1.07"
        x = "iw/2-(iw/zoom/2)-14*sin(on/30)"
        y = "ih/2-(ih/zoom/2)+4*cos(on/43)"
    elif motion == "micro_push":
        zoom = "min(zoom+0.00035,1.045)"
        x = "iw/2-(iw/zoom/2)+4*sin(on/40)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "static":
        zoom = "1.02"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        zoom = f"min(zoom+{zoom_speed},{max_zoom})"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    return (
        "scale=1200:2134,"
        "zoompan="
        f"z='{zoom}':"
        f"x='{x}':"
        f"y='{y}':"
        f"d={frames}:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"
        f"{fade_in_filter}"
        f"{fade_out_filter}"
        "eq=contrast=1.04:saturation=0.94,"
        "format=yuv420p"
    )


def _render_scene_clip(
    ffmpeg: str,
    image_path: Path,
    output_path: Path,
    scene,
    duration: float,
    is_first: bool = False,
    is_last: bool = False,
    width: int = WIDTH,
    height: int = HEIGHT,
    cancellation_check: Callable[[], bool] | None = None,
):
    frames = max(1, round(duration * FPS))
    filter_graph = compose_motion_filter(
        scene=scene,
        frames=frames,
        fps=FPS,
        width=width,
        height=height,
    )

    command = [
        ffmpeg,
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_graph + ",setpts=PTS-STARTPTS",
        "-t", f"{duration:.3f}",
        "-r", str(FPS),
        "-an",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    completed = run_cancellable(command, cancellation_check=cancellation_check)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg scene rendering failed: " + completed.stderr[-1800:])


def _concat_scene_clips(
    ffmpeg: str,
    clips: list[Path],
    output_path: Path,
    cancellation_check: Callable[[], bool] | None = None,
):
    concat_file = output_path.parent / "scene-clips.txt"
    lines = []
    for clip in clips:
        safe_path = str(clip.resolve()).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{safe_path}'")
    concat_file.write_text("\n".join(lines), encoding="utf-8")

    command = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-fflags", "+genpts+discardcorrupt",
        "-vsync", "cfr",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]
    completed = run_cancellable(command, cancellation_check=cancellation_check)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg scene concatenation failed: " + completed.stderr[-1800:])


def _write_dynamic_captions(
    storyboard: Storyboard,
    output_path: Path,
    width: int = WIDTH,
    height: int = HEIGHT,
    aspect_ratio: str = "9:16",
    preferences: "UserCreativePreferences | None" = None,
):
    """Caption Engine v2: safe-area-aware, naturally line-broken, themed,
    highlighted, positioned, and animated -- see app/captions/engine.py for
    the actual generation logic. This stays a thin call site so the render
    pipeline's call graph is unchanged."""

    captions = getattr(preferences, "captions", None)
    document = build_caption_document(
        storyboard,
        width,
        height,
        aspect_ratio=aspect_ratio,
        theme_name=getattr(captions, "theme", None),
        animation_style=getattr(captions, "animation", None),
        position_override=getattr(captions, "position", None),
    )
    output_path.write_text(document, encoding="utf-8-sig")


def _subtitle_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def _burn_captions(
    ffmpeg: str,
    silent_video: Path,
    captions_file: Path,
    output_path: Path,
    cancellation_check: Callable[[], bool] | None = None,
):
    caption_path = _subtitle_filter_path(captions_file)
    filter_value = f"subtitles='{caption_path}'"

    command = [
        ffmpeg,
        "-y",
        "-i", str(silent_video),
        "-vf", filter_value,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-an",
        str(output_path),
    ]
    completed = run_cancellable(command, cancellation_check=cancellation_check)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg caption rendering failed: " + completed.stderr[-2000:])


def _mux_audio(
    ffmpeg: str,
    captioned_video: Path,
    audio_path: Path,
    output_path: Path,
    cancellation_check: Callable[[], bool] | None = None,
):
    command = [
        ffmpeg,
        "-y",
        "-i", str(captioned_video),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    completed = run_cancellable(command, cancellation_check=cancellation_check)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg audio muxing failed: " + completed.stderr[-1800:])


def _cleanup_partial_render_artifacts(output_dir: Path, clips_dir: Path) -> None:
    """Best-effort removal of whatever this render had already written when
    it was cancelled, so a cancelled job never leaves partial/orphaned media
    files behind (a retry or a fresh job for the same project regenerates
    all of these from scratch anyway)."""

    shutil.rmtree(clips_dir, ignore_errors=True)
    for name in (
        "silent-video.mp4",
        "dynamic-captions.ass",
        "captioned-video.mp4",
        "mastered-audio.m4a",
        "generated-ambient-bed.wav",
    ):
        (output_dir / name).unlink(missing_ok=True)


def render_video(
    storyboard: Storyboard,
    images: list[Path],
    audio_path: Path,
    output_path: Path,
    width: int = WIDTH,
    height: int = HEIGHT,
    subtitles: bool = True,
    background_music: bool | None = None,
    aspect_ratio: str = "9:16",
    preferences: "UserCreativePreferences | None" = None,
    cancellation_check: Callable[[], bool] | None = None,
):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips_dir = output_path.parent / "scene-clips"
    clips_dir.mkdir(exist_ok=True)

    try:
        clips = []
        total_scenes = len(storyboard.scenes)
        for index, (scene, image_path) in enumerate(zip(storyboard.scenes, images)):
            if cancellation_check and cancellation_check():
                raise RenderCancelled("Rendering cancelled between scene clips.")
            duration = max(1.0, scene.end_second - scene.start_second)
            clip_path = clips_dir / f"scene-{scene.number:02d}.mp4"
            _render_scene_clip(
                ffmpeg=ffmpeg,
                image_path=image_path,
                output_path=clip_path,
                scene=scene,
                duration=duration,
                is_first=index == 0,
                is_last=index == total_scenes - 1,
                width=width,
                height=height,
                cancellation_check=cancellation_check,
            )
            clips.append(clip_path)

        silent_video = output_path.parent / "silent-video.mp4"
        _concat_scene_clips(ffmpeg, clips, silent_video, cancellation_check=cancellation_check)

        if subtitles:
            captions_file = output_path.parent / "dynamic-captions.ass"
            _write_dynamic_captions(
                storyboard,
                captions_file,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                preferences=preferences,
            )
            captioned_video = output_path.parent / "captioned-video.mp4"
            _burn_captions(
                ffmpeg, silent_video, captions_file, captioned_video,
                cancellation_check=cancellation_check,
            )
        else:
            captioned_video = silent_video

        mastered_audio = output_path.parent / "mastered-audio.m4a"
        master_audio(
            narration_path=audio_path,
            output_path=mastered_audio,
            project_dir=output_path.parent,
            music_enabled=background_music,
            cancellation_check=cancellation_check,
        )

        _mux_audio(
            ffmpeg, captioned_video, mastered_audio, output_path,
            cancellation_check=cancellation_check,
        )
    except RenderCancelled:
        _cleanup_partial_render_artifacts(output_path.parent, clips_dir)
        raise


def _generate_scene_images(
    storyboard: Storyboard,
    media_dir: Path,
    *,
    width: int,
    height: int,
    size: str,
    aspect_ratio: str,
    cancellation_check: Callable[[], bool] | None = None,
) -> list[Path]:
    """Generate one image per unique scene.image_prompt, concurrently, and
    copy the result to every other scene that shares that prompt.

    Visual Asset Economy v3 (app.visual_continuity) may have already
    resolved several scenes to the exact same image_prompt (a shared
    Anchor Shot) before this runs -- when it has, this only makes one real
    OpenAI request for the whole group and locally copies the bytes for
    the rest, which is where the actual API-call and render-time savings
    come from. When every scene has its own unique prompt (the feature
    disabled, or a plan that never merged anything), this behaves exactly
    like the old one-request-per-scene loop. Set IMAGE_CACHE_ENABLED=false
    to force a fresh request per scene even for identical prompts.

    Each real generation call is an independent OpenAI network request
    writing to its own file -- there is no shared state or ordering
    dependency between them -- so this is safe to parallelize; bounded to
    ``MAX_CONCURRENT_IMAGE_GENERATIONS`` workers to stay well within
    typical account rate limits. Results are always returned in scene
    order, regardless of completion order, so callers (render_video) don't
    need to change how they consume the result.

    If cancellation is requested mid-batch, in-flight calls in that batch
    are allowed to finish (there is no way to abort a network request
    already sent) before the exception propagates -- this bounds the
    uncancellable window to roughly one batch's latency instead of the
    full sequential total.
    """

    if cancellation_check and cancellation_check():
        raise RenderCancelled("Rendering cancelled before scene image generation.")

    image_paths = [media_dir / f"scene-{scene.number:02d}.jpg" for scene in storyboard.scenes]
    cache_enabled = image_cache_enabled()
    cache = ImageAssetCache()

    scene_keys: list[str] = []
    for index, scene in enumerate(storyboard.scenes):
        key = (
            cache_key(scene.image_prompt, aspect_ratio=aspect_ratio, quality="low")
            if cache_enabled
            else f"__uncached_scene_{index}"
        )
        scene_keys.append(key)
        cache.put(key, index)

    generation_indices = sorted({cache.get(key) for key in scene_keys})
    worker_count = max(1, min(MAX_CONCURRENT_IMAGE_GENERATIONS, len(generation_indices)))

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="scene-image") as executor:
        futures = {
            executor.submit(
                generate_scene_image,
                storyboard.scenes[index].image_prompt,
                image_paths[index],
                width=width,
                height=height,
                size=size,
                aspect_ratio=aspect_ratio,
                cancellation_check=cancellation_check,
            ): index
            for index in generation_indices
        }
        first_error: BaseException | None = None
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as exc:  # noqa: BLE001 -- re-raised below, never swallowed
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    for index, key in enumerate(scene_keys):
        source_index = cache.get(key)
        if source_index is not None and source_index != index:
            shutil.copyfile(image_paths[source_index], image_paths[index])

    return image_paths


def build_video(
    project_dir: Path,
    script: ShortScript,
    storyboard: Storyboard,
    narration_audio_path: Path | None = None,
    preferences: "UserCreativePreferences | None" = None,
    aspect_ratio: str = "9:16",
    cancellation_check: Callable[[], bool] | None = None,
) -> Path:
    graph = RenderGraph(project_dir)
    graph.mark("storyboard", "ready", detail=f"{len(storyboard.scenes)} scenes")

    media_dir = project_dir / "media"
    media_dir.mkdir(exist_ok=True)

    audio_path = media_dir / "voiceover.mp3"
    if narration_audio_path is not None:
        # Narration was already synthesized (and its measured duration used
        # to time the scenes) by the voice_generation stage -- reuse it
        # instead of generating a second, untimed narration here.
        shutil.copyfile(narration_audio_path, audio_path)
    else:
        generate_voiceover(
            script, audio_path, preferences=preferences, cancellation_check=cancellation_check
        )
    graph.mark("voiceover", "complete", output=str(audio_path))

    resolved_aspect_ratio = getattr(getattr(preferences, "video", None), "aspect_ratio", None) or aspect_ratio
    width, height, image_size = resolution_for_aspect_ratio(resolved_aspect_ratio)

    images = _generate_scene_images(
        storyboard,
        media_dir,
        width=width,
        height=height,
        size=image_size,
        aspect_ratio=resolved_aspect_ratio,
        cancellation_check=cancellation_check,
    )

    graph.mark("images", "complete", detail=f"{len(images)} images")

    rendering = getattr(preferences, "rendering", None)
    subtitles = True if rendering is None or rendering.subtitles is None else rendering.subtitles
    background_music = None if rendering is None else rendering.background_music

    video_path = project_dir / "mind-frontier-short.mp4"
    graph.mark("render", "started")
    render_video(
        storyboard,
        images,
        audio_path,
        video_path,
        width=width,
        height=height,
        subtitles=subtitles,
        background_music=background_music,
        aspect_ratio=resolved_aspect_ratio,
        preferences=preferences,
        cancellation_check=cancellation_check,
    )
    graph.mark("render", "complete", output=str(video_path))
    return video_path
