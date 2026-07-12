from __future__ import annotations

"""Dynamic caption font sizing.

Font size depends on aspect ratio (a 9:16 frame reads bigger text
comfortably; a 16:9 frame has more horizontal room but a shorter safe
height), how long the caption is, and how many lines it wraps to. Short,
punchy captions get a large size; longer, denser captions shrink -- but
never below a readability floor -- and the choice is always checked against
the frame's safe width so a line can never physically overflow.
"""

from app.captions.safe_area import safe_area_for

# Base size tuned per aspect ratio at a 1080-wide reference canvas; scaled
# linearly for other canvas widths.
_BASE_FONT_SIZE: dict[str, int] = {
    "9:16": 78,
    "16:9": 58,
    "1:1": 66,
    "4:5": 72,
}
_REFERENCE_WIDTH = 1080

MIN_FONT_SIZE = 40

# Average glyph width as a fraction of font size for a bold sans-serif face
# -- a conservative estimate used only to keep lines inside the safe width,
# not for pixel-perfect typesetting.
_AVG_GLYPH_WIDTH_RATIO = 0.56


def _length_scale(max_line_words: int, line_count: int) -> float:
    if max_line_words <= 3 and line_count == 1:
        scale = 1.12
    elif max_line_words <= 4:
        scale = 1.0
    elif max_line_words <= 6:
        scale = 0.9
    else:
        scale = 0.8
    if line_count >= 2:
        scale *= 0.94
    return scale


def font_size_for_card(
    lines: list[str],
    width: int,
    height: int,
    aspect_ratio: str | None = None,
    base_override: int | None = None,
    emphasis_multiplier: float = 1.0,
) -> int:
    """Pick a font size for a caption card that fits every line inside the
    frame's safe width, scaled down for longer/denser captions. Aims to
    never drop below ``MIN_FONT_SIZE``, but fitting inside the safe width is
    the hard constraint -- an unbreakable chunk (e.g. one long protected
    name) that's wider than the floor allows still shrinks further rather
    than clip. In practice app.captions.line_breaking's character budget
    keeps ordinary lines well clear of ever reaching that floor.

    ``emphasis_multiplier`` (a hook/emphasis-moment boost) is applied
    *before* the safe-width clamp, not after -- a boost applied afterward
    could push an already width-limited size back over budget."""

    base = base_override or _BASE_FONT_SIZE.get(aspect_ratio or "9:16", _BASE_FONT_SIZE["9:16"])
    base = round(base * width / _REFERENCE_WIDTH)

    max_line_words = max((len(line.split()) for line in lines), default=0)
    size = round(base * _length_scale(max_line_words, len(lines)) * emphasis_multiplier)
    size = max(MIN_FONT_SIZE, size)

    safe_area = safe_area_for(aspect_ratio)
    max_width = safe_area.max_text_width(width)
    longest_line_chars = max((len(line) for line in lines), default=0)
    if longest_line_chars:
        width_limited_size = int(max_width / (longest_line_chars * _AVG_GLYPH_WIDTH_RATIO))
        size = min(size, max(1, width_limited_size))

    return max(1, size)
