import base64
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

from app.config import (
    OPENAI_IMAGE_MODEL,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
)
from app.services.openai_client import client
from app.services.audio import master_audio
from app.models import Storyboard, ShortScript

WIDTH = 1080
HEIGHT = 1920

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

def _wrap_caption(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        box = draw.textbbox((0, 0), test, font=font)
        if box[2] - box[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines[:3]

def generate_voiceover(script: ShortScript, output_path: Path):
    response = client.audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_TTS_VOICE,
        input=script.voiceover,
        instructions=(
            "Calm, thoughtful documentary narration. "
            "Moderate pace, precise diction, restrained emotion."
        ),
    )
    output_path.write_bytes(response.read())

def generate_scene_image(prompt: str, output_path: Path):
    result = client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=(
            prompt
            + "\\nPortrait 9:16 composition, cinematic documentary style, "
              "dark neutral palette, subtle warm highlights, realistic lighting, "
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
        resized = image.resize((int(image.width * ratio), int(image.height * ratio)))
        left = (resized.width - WIDTH) // 2
        top = (resized.height - HEIGHT) // 2
        final = resized.crop((left, top, left + WIDTH, top + HEIGHT))
        final.save(output_path, quality=92)

    temp.unlink(missing_ok=True)

def add_caption(image_path: Path, caption: str, output_path: Path):
    with Image.open(image_path).convert("RGB") as image:
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = _font(72)
        lines = _wrap_caption(draw, caption, font, 900)

        line_height = 90
        total_height = len(lines) * line_height
        y = int(HEIGHT * 0.72) - total_height // 2

        for line in lines:
            box = draw.textbbox((0, 0), line, font=font)
            text_width = box[2] - box[0]
            x = (WIDTH - text_width) // 2
            pad = 24
            draw.rounded_rectangle(
                (x - pad, y - 12, x + text_width + pad, y + 74),
                radius=20,
                fill=(0, 0, 0, 165),
            )
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_height

        composited = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        composited.save(output_path, quality=92)

def render_video(
    storyboard: Storyboard,
    captioned_images: list[Path],
    audio_path: Path,
    output_path: Path,
):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    concat_file = output_path.parent / "frames.txt"

    lines = []
    for scene, image_path in zip(storyboard.scenes, captioned_images):
        duration = max(1, scene.end_second - scene.start_second)
        safe_path = str(image_path.resolve()).replace("\\\\", "/").replace("'", "'\\\\''")
        lines.append(f"file '{safe_path}'")
        lines.append(f"duration {duration}")
    last_path = str(captioned_images[-1].resolve()).replace("\\\\", "/").replace("'", "'\\\\''")
    lines.append(f"file '{last_path}'")
    concat_file.write_text("\n".join(lines), encoding="utf-8")

    command = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-i", str(audio_path),
        "-vf", "scale=1080:1920,format=yuv420p",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("FFmpeg rendering failed: " + completed.stderr[-1200:])

def build_video(project_dir: Path, script: ShortScript, storyboard: Storyboard) -> Path:
    media_dir = project_dir / "media"
    media_dir.mkdir(exist_ok=True)

    audio_path = media_dir / "voiceover.mp3"
    generate_voiceover(script, audio_path)

    captioned = []
    for scene in storyboard.scenes:
        raw_path = media_dir / f"scene-{scene.number:02d}.jpg"
        caption_path = media_dir / f"scene-{scene.number:02d}-captioned.jpg"
        generate_scene_image(scene.image_prompt, raw_path)
        add_caption(raw_path, scene.on_screen_text, caption_path)
        captioned.append(caption_path)

    video_path = project_dir / "mind-frontier-short.mp4"
    mastered_audio = media_dir / "mastered-audio.m4a"
    master_audio(
        narration_path=audio_path,
        output_path=mastered_audio,
        project_dir=project_dir,
    )

    render_video(storyboard, captioned, mastered_audio, video_path)
    return video_path

