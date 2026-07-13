from __future__ import annotations

"""Caption placement.

The renderer already knows, per scene, which third of the frame the visual
composition wants left clear for text -- ``scene.caption_safe_area``,
computed upstream by the Visual Director/cinematography stages from the
actual shot composition (see app/visual/taxonomy.py). This module turns
that existing signal (plus whether this is a hook/emphasis moment) into one
of the four supported caption positions, so placement automatically follows
whichever area the visuals leave clear -- no separate visual analysis is
duplicated here.
"""

from dataclasses import dataclass

from app.captions.safe_area import SafeArea

# ASS alignment codes (numpad layout): 1-3 bottom row, 4-6 middle row,
# 7-9 top row; the middle column (2/5/8) is horizontally centered.
_ALIGNMENT_BY_POSITION = {
    "bottom": 2,
    "lower_third": 2,
    "middle": 5,
    "top": 8,
}


@dataclass(frozen=True)
class PlacementResult:
    position: str
    alignment: int
    margin_v: int


def choose_position(
    caption_safe_area: str,
    *,
    is_emphasis_moment: bool = False,
    explicit_position: str | None = None,
) -> str:
    """Pick bottom / lower_third / middle / top.

    ``explicit_position`` (a user preference) always wins. Otherwise an
    emphasis moment (the hook, or a high-intensity beat) gets the bigger,
    centered "middle" treatment; everything else follows the safe area the
    shot composition already reserved: an "upper_third" safe area means the
    lower frame is occupied by the visual, so captions move to the top, and
    vice versa.
    """

    if explicit_position:
        return explicit_position
    if is_emphasis_moment:
        return "middle"
    return "top" if caption_safe_area == "upper_third" else "lower_third"


def placement_for(
    position: str,
    safe_area: SafeArea,
    height: int,
    *,
    is_emphasis_moment: bool = False,
) -> PlacementResult:
    alignment = _ALIGNMENT_BY_POSITION.get(position, 2)

    if position == "middle":
        margin_v = round(height * 0.5) - round(height * 0.06)
    elif position == "top":
        margin_v = safe_area.top_margin(height)
    elif position == "bottom":
        margin_v = round(safe_area.bottom_margin(height) * 0.55)
    else:  # lower_third
        margin_v = safe_area.bottom_margin(height)

    return PlacementResult(position=position, alignment=alignment, margin_v=margin_v)
