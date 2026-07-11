import base64
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageFont
import imageio_ffmpeg

from app.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
)
from app.services.openai_client import client
from app.services.audio import master_audio
from app.models import Storyboard, ShortScript
from app.rendering.graph import RenderGraph

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TRANSITION_SECONDS = 0.32


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


def generate_voiceover(script: ShortScript, output_path: Path):
    response = client.audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_TTS_VOICE,
        input=script.voiceover,
        instructions=(
            "Calm, thoughtful documentary narration. "
            "Moderate pace, precise diction, restrained emotion. "
            "Use subtle pauses after important ideas."
        ),
    )
    output_path.write_bytes(response.read())


def generate_scene_image(prompt: str, output_path: Path):
    result = client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=(
            prompt
            + "\nPortrait 9:16 composition, cinematic documentary style, "
              "dark neutral palette, subtle warm highlights, realistic lighting, "
              "consistent fictional character identity when a recurring protagonist appears, "
              "no text, no logo, no watermark."
        ),
        size="1024x1536",
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
        ratio = max(WIDTH / image.width, HEIGHT / image.height)
        resized = image.resize(
            (int(image.width * ratio), int(image.height * ratio)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - WIDTH) // 2
        top = (resized.height - HEIGHT) // 2
        final = resized.crop((left, top, left + WIDTH, top + HEIGHT))
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
):
    frames = max(1, round(duration * FPS))
    filter_graph = _motion_filter(
        scene,
        frames,
        is_first=is_first,
        is_last=is_last,
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
        "-fflags", "+genpts",
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


def _write_dynamic_captions(storyboard: Storyboard, output_path: Path):
    header = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dynamic,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,3,3,0,2,100,100,330,1
Style: DynamicTop,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,3,3,0,8,100,100,280,1
Style: Hook,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,0,0,3,4,0,2,90,90,300,1
Style: HookTop,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,0,0,3,4,0,8,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    for scene in storyboard.scenes:
        phrases = _split_into_phrases(scene.narration, target_words=3)
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
        )
        clips.append(clip_path)

    silent_video = output_path.parent / "silent-video.mp4"
    _concat_scene_clips(ffmpeg, clips, silent_video)

    captions_file = output_path.parent / "dynamic-captions.ass"
    _write_dynamic_captions(storyboard, captions_file)

    captioned_video = output_path.parent / "captioned-video.mp4"
    _burn_captions(ffmpeg, silent_video, captions_file, captioned_video)

    mastered_audio = output_path.parent / "mastered-audio.m4a"
    master_audio(
        narration_path=audio_path,
        output_path=mastered_audio,
        project_dir=output_path.parent,
    )

    _mux_audio(ffmpeg, captioned_video, mastered_audio, output_path)


def build_video(project_dir: Path, script: ShortScript, storyboard: Storyboard) -> Path:
    graph = RenderGraph(project_dir)
    graph.mark("storyboard", "ready", detail=f"{len(storyboard.scenes)} scenes")

    media_dir = project_dir / "media"
    media_dir.mkdir(exist_ok=True)

    audio_path = media_dir / "voiceover.mp3"
    generate_voiceover(script, audio_path)
    graph.mark("voiceover", "complete", output=str(audio_path))

    images = []
    for scene in storyboard.scenes:
        image_path = media_dir / f"scene-{scene.number:02d}.jpg"
        generate_scene_image(scene.image_prompt, image_path)
        images.append(image_path)

    graph.mark("images", "complete", detail=f"{len(images)} images")

    video_path = project_dir / "mind-frontier-short.mp4"
    graph.mark("render", "started")
    render_video(storyboard, images, audio_path, video_path)
    graph.mark("render", "complete", output=str(video_path))
    return video_path
