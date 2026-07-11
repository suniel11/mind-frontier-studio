from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720


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


def _fit_cover(image: Image.Image) -> Image.Image:
    ratio = max(THUMBNAIL_WIDTH / image.width, THUMBNAIL_HEIGHT / image.height)
    resized = image.resize(
        (round(image.width * ratio), round(image.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - THUMBNAIL_WIDTH) // 2)
    top = max(0, (resized.height - THUMBNAIL_HEIGHT) // 2)
    return resized.crop((left, top, left + THUMBNAIL_WIDTH, top + THUMBNAIL_HEIGHT))


def _short_title(title: str, max_words: int = 5) -> str:
    words = title.strip().split()
    return " ".join(words[:max_words]).upper() if words else "MIND FRONTIER"


def create_thumbnail(source_image: Path, title: str, output_path: Path) -> Path:
    with Image.open(source_image).convert("RGB") as image:
        canvas = _fit_cover(image)

    canvas = ImageEnhance.Contrast(canvas).enhance(1.12)
    canvas = ImageEnhance.Color(canvas).enhance(0.92)
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=0.4)).convert("RGBA")

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for x in range(THUMBNAIL_WIDTH):
        opacity = int(220 * max(0.0, 1.0 - x / 860))
        draw.line([(x, 0), (x, THUMBNAIL_HEIGHT)], fill=(0, 0, 0, opacity))

    accent = (232, 184, 98, 255)
    draw.rounded_rectangle((70, 80, 250, 98), radius=9, fill=accent)

    font = _font(92)
    small_font = _font(34)
    wrapped = textwrap.wrap(_short_title(title), width=13)[:3]

    y = 135
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=2)
        line_height = bbox[3] - bbox[1]
        draw.text(
            (70, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=3,
            stroke_fill=(10, 10, 10, 230),
        )
        y += line_height + 12

    draw.text(
        (72, THUMBNAIL_HEIGHT - 92),
        "MIND FRONTIER",
        font=small_font,
        fill=(240, 240, 240, 235),
    )

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, quality=94)
    return output_path


def choose_thumbnail_source(media_dir: Path) -> Path:
    candidates = sorted(media_dir.glob("scene-*.jpg"))
    if not candidates:
        raise FileNotFoundError("No scene images found for thumbnail generation.")

    preferred_indexes = [4, 5, 2, 0]
    for index in preferred_indexes:
        if index < len(candidates):
            return candidates[index]
    return candidates[0]
