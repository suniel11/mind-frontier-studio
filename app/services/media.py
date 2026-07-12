import base64
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageFont
import imageio_ffmpeg

from app.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
)
from app.services.openai_client import get_openai_client
from app.services.audio import master_audio
from app.models import Storyboard, ShortScript
from app.director.captions import semantic_phrases
from app.cinema.motion import compose_motion_filter
from app.rendering.graph import RenderGraph

if TYPE_CHECKING:
    from app.production.preferences import UserCreativePreferences

logger = logging.getLogger(__name__)

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TRANSITION_SECONDS = 0.32

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


# Voice pools split by the gender field on a project's Character Bible, so
# the narrator's voice and the presenter's on-screen appearance always agree
# instead of each subsystem picking independently.
MALE_VOICES = ("onyx", "echo")
FEMALE_VOICES = ("nova", "shimmer")


def _normalize_gender(value: str | None) -> str | None:
    gender = str(value or "").strip().casefold()
    if gender in {"male", "man", "masculine", "m"}:
        return "male"
    if gender in {"female", "woman", "feminine", "f"}:
        return "female"
    return None


def gender_for_voice(voice: str) -> str | None:
    """Reverse lookup used by validation to confirm what gender a voice
    selection actually resolved to."""

    if voice in MALE_VOICES:
        return "male"
    if voice in FEMALE_VOICES:
        return "female"
    return None


def voice_for_character(
    character_bible,
    preferences: "UserCreativePreferences | None" = None,
    default_voice: str = OPENAI_TTS_VOICE,
) -> str:
    """Pick a narrator voice, honoring an explicit user request first.

    Priority: an explicit ``preferences.narrator.gender`` (the user's own
    words) always wins, even when no Character Bible exists (a video can
    have a female narrator with no on-screen presenter). Only when the user
    did not specify a gender does the Character Bible's gender apply, so a
    presenter's on-screen appearance and the narrator agree by default.
    """

    explicit_gender = _normalize_gender(getattr(getattr(preferences, "narrator", None), "gender", None))
    bible_gender = _normalize_gender(getattr(character_bible, "gender", None))
    gender = explicit_gender or bible_gender

    if gender == "male":
        voice = MALE_VOICES[0]
    elif gender == "female":
        voice = FEMALE_VOICES[0]
    else:
        voice = default_voice

    logger.info(
        "Narrator voice selected: %s (gender=%s, source=%s)",
        voice,
        gender or "unspecified",
        "explicit_preference" if explicit_gender else ("character_bible" if bible_gender else "default"),
    )
    return voice


def _narrator_instructions(preferences: "UserCreativePreferences | None") -> str:
    base = (
        "Calm, thoughtful documentary narration. "
        "Moderate pace, precise diction, restrained emotion. "
        "Use subtle pauses after important ideas."
    )
    narrator = getattr(preferences, "narrator", None)
    if narrator is None:
        return base

    overrides = []
    if narrator.tone:
        overrides.append(f"tone: {narrator.tone}")
    if narrator.emotion:
        overrides.append(f"emotion: {narrator.emotion}")
    if narrator.voice_style:
        overrides.append(f"voice style: {narrator.voice_style}")
    if narrator.accent:
        overrides.append(f"accent: {narrator.accent}")
    if not overrides:
        return base
    return base + " Creator-specified direction takes priority: " + ", ".join(overrides) + "."


def generate_voiceover(
    script: ShortScript,
    output_path: Path,
    voice: str = OPENAI_TTS_VOICE,
    preferences: "UserCreativePreferences | None" = None,
):
    speed = getattr(getattr(preferences, "narrator", None), "speaking_speed", None)
    kwargs = {"speed": speed} if speed is not None else {}
    response = get_openai_client().audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=voice,
        input=script.voiceover,
        instructions=_narrator_instructions(preferences),
        **kwargs,
    )
    output_path.write_bytes(response.read())


_ASPECT_RATIO_LABELS = {
    "9:16": "Portrait 9:16",
    "16:9": "Landscape 16:9",
    "1:1": "Square 1:1",
    "4:5": "Portrait 4:5",
}


def generate_scene_image(
    prompt: str,
    output_path: Path,
    width: int = WIDTH,
    height: int = HEIGHT,
    size: str = "1024x1536",
    aspect_ratio: str = "9:16",
):
    result = get_openai_client().images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=(
            prompt
            + f"\n{_ASPECT_RATIO_LABELS.get(aspect_ratio, 'Portrait 9:16')} composition, "
              "cinematic documentary style, "
              "dark neutral palette, subtle warm highlights, realistic lighting, "
              "consistent fictional character identity when a recurring protagonist appears, "
              "no text, no logo, no watermark."
        ),
        size=size,
        quality="low",
    )

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

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg scene rendering failed: " + completed.stderr[-1800:])


def _concat_scene_clips(
    ffmpeg: str,
    clips: list[Path],
    output_path: Path,
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
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg scene concatenation failed: " + completed.stderr[-1800:])


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours}:{minutes:02d}:{remaining:05.2f}"


def _clean_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9’'-]+[.,!?;:]?", text)


def _split_into_phrases(text: str, target_words: int = 4) -> list[str]:
    words = _clean_words(text)
    if not words:
        return []

    phrases = []
    current = []
    for word in words:
        current.append(word)
        punctuation_break = word.endswith((".", ",", "!", "?", ";", ":"))
        if len(current) >= target_words or punctuation_break:
            phrases.append(" ".join(current))
            current = []

    if current:
        phrases.append(" ".join(current))
    return phrases


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _highlight_phrase(phrase: str) -> str:
    words = phrase.split()
    candidates = [
        (index, re.sub(r"[^A-Za-z0-9’'-]", "", word))
        for index, word in enumerate(words)
    ]
    candidates = [(index, word) for index, word in candidates if len(word) >= 5]

    if not candidates:
        return _escape_ass_text(phrase.upper())

    highlight_index, _ = max(candidates, key=lambda item: len(item[1]))
    rendered = []

    for index, word in enumerate(words):
        escaped = _escape_ass_text(word.upper())
        if index == highlight_index:
            rendered.append(r"{\c&H62B8E8&\b1}" + escaped + r"{\c&HFFFFFF&\b1}")
        else:
            rendered.append(escaped)

    return " ".join(rendered)


def _write_dynamic_captions(storyboard: Storyboard, output_path: Path, width: int = WIDTH, height: int = HEIGHT):
    # Margins were tuned for the 1080x1920 default; scale them proportionally
    # to height so captions land in a sensible place at other aspect ratios
    # instead of being positioned for a video half again as tall.
    scale = height / HEIGHT
    margin_standard = round(330 * scale)
    margin_top = round(280 * scale)
    margin_hook = round(300 * scale)
    margin_hook_top = round(250 * scale)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dynamic,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,3,3,0,2,100,100,{margin_standard},1
Style: DynamicTop,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,3,3,0,8,100,100,{margin_top},1
Style: Hook,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,0,0,3,4,0,2,90,90,{margin_hook},1
Style: HookTop,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,0,0,3,4,0,8,90,90,{margin_hook_top},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    for scene in storyboard.scenes:
        phrases = semantic_phrases(scene.narration, max_words=5)
        if not phrases:
            phrases = [scene.on_screen_text]

        scene_start = float(scene.start_second)
        scene_end = float(scene.end_second)
        scene_duration = max(0.5, scene_end - scene_start)

        weights = [max(1, len(_clean_words(phrase))) for phrase in phrases]
        total_weight = sum(weights)
        cursor = scene_start

        for index, (phrase, weight) in enumerate(zip(phrases, weights)):
            duration = scene_duration * weight / total_weight
            start = cursor
            end = scene_end if index == len(phrases) - 1 else cursor + duration
            cursor = end

            is_hook = scene.number == 1 and index == 0
            safe_area = str(getattr(scene, "caption_safe_area", "lower_third"))
            use_top = safe_area == "upper_third"
            if is_hook:
                style = "HookTop" if use_top else "Hook"
            else:
                style = "DynamicTop" if use_top else "Dynamic"
            animation = (
                r"{\fad(70,90)\fscx82\fscy82\t(0,150,\fscx100\fscy100)\bord4\shad0}"
                if is_hook
                else r"{\fad(80,80)\fscx90\fscy90\t(0,130,\fscx100\fscy100)\bord3\shad0}"
            )
            text = animation + _highlight_phrase(phrase)

            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
                f"{style},,0,0,0,,{text}"
            )

    output_path.write_text(header + "\n".join(events), encoding="utf-8-sig")


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
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg caption rendering failed: " + completed.stderr[-2000:])


def _mux_audio(
    ffmpeg: str,
    captioned_video: Path,
    audio_path: Path,
    output_path: Path,
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
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg audio muxing failed: " + completed.stderr[-1800:])


def render_video(
    storyboard: Storyboard,
    images: list[Path],
    audio_path: Path,
    output_path: Path,
    width: int = WIDTH,
    height: int = HEIGHT,
    subtitles: bool = True,
    background_music: bool | None = None,
):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clips_dir = output_path.parent / "scene-clips"
    clips_dir.mkdir(exist_ok=True)

    clips = []
    total_scenes = len(storyboard.scenes)
    for index, (scene, image_path) in enumerate(zip(storyboard.scenes, images)):
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
        )
        clips.append(clip_path)

    silent_video = output_path.parent / "silent-video.mp4"
    _concat_scene_clips(ffmpeg, clips, silent_video)

    if subtitles:
        captions_file = output_path.parent / "dynamic-captions.ass"
        _write_dynamic_captions(storyboard, captions_file, width=width, height=height)
        captioned_video = output_path.parent / "captioned-video.mp4"
        _burn_captions(ffmpeg, silent_video, captions_file, captioned_video)
    else:
        captioned_video = silent_video

    mastered_audio = output_path.parent / "mastered-audio.m4a"
    master_audio(
        narration_path=audio_path,
        output_path=mastered_audio,
        project_dir=output_path.parent,
        music_enabled=background_music,
    )

    _mux_audio(ffmpeg, captioned_video, mastered_audio, output_path)


def build_video(
    project_dir: Path,
    script: ShortScript,
    storyboard: Storyboard,
    narration_audio_path: Path | None = None,
    preferences: "UserCreativePreferences | None" = None,
    aspect_ratio: str = "9:16",
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
        generate_voiceover(script, audio_path, preferences=preferences)
    graph.mark("voiceover", "complete", output=str(audio_path))

    resolved_aspect_ratio = getattr(getattr(preferences, "video", None), "aspect_ratio", None) or aspect_ratio
    width, height, image_size = resolution_for_aspect_ratio(resolved_aspect_ratio)

    images = []
    for scene in storyboard.scenes:
        image_path = media_dir / f"scene-{scene.number:02d}.jpg"
        generate_scene_image(
            scene.image_prompt,
            image_path,
            width=width,
            height=height,
            size=image_size,
            aspect_ratio=resolved_aspect_ratio,
        )
        images.append(image_path)

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
    )
    graph.mark("render", "complete", output=str(video_path))
    return video_path
