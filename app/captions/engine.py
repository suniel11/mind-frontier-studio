from __future__ import annotations

"""Caption Engine v2 -- orchestrates safe-area, line-breaking, font scaling,
theming, highlighting, position, and animation into a single deterministic
ASS subtitle document. No model calls happen here; every decision is a pure
function of the storyboard's already-computed scene data (narration,
caption_safe_area, caption_emphasis, timing) plus the chosen theme/animation.

This is the v2 replacement for the caption-generation half of
app/services/media.py's old ``_write_dynamic_captions`` -- the burn-in
mechanism (ffmpeg's ``subtitles=`` filter over an .ass file) is unchanged;
only how that .ass file's content is produced is new.
"""

import re

from app.captions.animation import animation_tags
from app.captions.font_scaling import font_size_for_card
from app.captions.highlighting import find_highlight_span
from app.captions.line_breaking import segment_into_caption_cards
from app.captions.position import choose_position, placement_for
from app.captions.safe_area import aspect_ratio_for_resolution, safe_area_for
from app.captions.themes import get_theme

DEFAULT_MARGIN_L = 90
DEFAULT_MARGIN_R = 90


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours}:{minutes:02d}:{remaining:05.2f}"


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def _render_line(line: str, highlight_color: str, caption_emphasis: str) -> str:
    span = find_highlight_span(line, caption_emphasis)
    if span is None:
        return _escape_ass_text(line)
    start, end = span
    before = _escape_ass_text(line[:start])
    mid = _escape_ass_text(line[start:end])
    after = _escape_ass_text(line[end:])
    return f"{before}{{\\c{highlight_color}}}{mid}{{\\c}}{after}"


def _header(theme, width: int, height: int) -> str:
    default_margin_v = round(height * 0.14)
    bold_flag = -1 if theme.bold else 0
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,{theme.font},{round(height * 0.045)},{theme.base_color},"
        f"{theme.base_color},{theme.outline_color},{theme.back_color},{bold_flag},0,0,0,"
        f"100,100,{theme.letter_spacing},0,1,{theme.outline_width},{theme.shadow},2,"
        f"{DEFAULT_MARGIN_L},{DEFAULT_MARGIN_R},{default_margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def build_caption_document(
    storyboard,
    width: int,
    height: int,
    *,
    aspect_ratio: str | None = None,
    theme_name: str | None = None,
    animation_style: str | None = None,
    position_override: str | None = None,
) -> str:
    theme = get_theme(theme_name)
    resolved_aspect_ratio = aspect_ratio or aspect_ratio_for_resolution(width, height)
    safe_area = safe_area_for(resolved_aspect_ratio)
    animation = animation_style or theme.default_animation

    events: list[str] = []

    for scene in storyboard.scenes:
        narration = str(getattr(scene, "narration", "") or "")
        cards = segment_into_caption_cards(narration)
        if not cards:
            on_screen_text = str(getattr(scene, "on_screen_text", "") or "")
            cards = segment_into_caption_cards(on_screen_text)
        if not cards:
            continue

        scene_start = float(getattr(scene, "start_second", 0))
        scene_end = float(getattr(scene, "end_second", scene_start + 1))
        scene_duration = max(0.5, scene_end - scene_start)

        total_words = sum(card.word_count for card in cards) or len(cards)
        caption_safe_area = str(getattr(scene, "caption_safe_area", "lower_third"))
        caption_emphasis = str(getattr(scene, "caption_emphasis", "") or "")
        is_hook_scene = int(getattr(scene, "number", 0)) == 1

        cursor = scene_start
        for card_index, card in enumerate(cards):
            weight = card.word_count or 1
            duration = scene_duration * weight / total_words
            start = cursor
            end = scene_end if card_index == len(cards) - 1 else cursor + duration
            cursor = end

            is_emphasis_moment = is_hook_scene and card_index == 0

            position = choose_position(
                caption_safe_area,
                is_emphasis_moment=is_emphasis_moment,
                explicit_position=position_override,
            )
            placement = placement_for(position, safe_area, height, is_emphasis_moment=is_emphasis_moment)
            font_size = font_size_for_card(
                card.lines,
                width,
                height,
                resolved_aspect_ratio,
                emphasis_multiplier=1.08 if is_emphasis_moment else 1.0,
            )

            tags = animation_tags(
                animation,
                is_emphasis=is_emphasis_moment,
                width=width,
                height=height,
                margin_v=placement.margin_v,
                alignment=placement.alignment,
            )
            text_lines = [
                _render_line(line, theme.highlight_color, caption_emphasis)
                for line in card.lines
            ]
            body = r"\N".join(text_lines)
            override = f"{{\\an{placement.alignment}\\fs{font_size}{tags}}}"

            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,"
                f"{placement.margin_v},,{override}{body}"
            )

    return _header(theme, width, height) + "\n".join(events)
