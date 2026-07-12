from __future__ import annotations

"""Safe-area margins so captions never render outside the visible/safe area
of the frame, across every supported aspect ratio.

Margins are expressed as a fraction of the frame dimension rather than a
fixed pixel count, so they scale correctly whether the canvas is a portrait
1080x1920 short or a landscape 1920x1080 render. The bottom margin is
largest for 9:16 to clear the on-screen-UI zone mobile short-form platforms
reserve for captions/buttons/share icons.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeArea:
    horizontal_pct: float
    top_pct: float
    bottom_pct: float

    def horizontal_margin(self, width: int) -> int:
        return round(width * self.horizontal_pct)

    def top_margin(self, height: int) -> int:
        return round(height * self.top_pct)

    def bottom_margin(self, height: int) -> int:
        return round(height * self.bottom_pct)

    def max_text_width(self, width: int) -> int:
        """The widest a caption line may be before it risks leaving the
        safe area horizontally."""

        return max(1, width - 2 * self.horizontal_margin(width))


_SAFE_AREAS: dict[str, SafeArea] = {
    "9:16": SafeArea(horizontal_pct=0.08, top_pct=0.10, bottom_pct=0.14),
    "16:9": SafeArea(horizontal_pct=0.06, top_pct=0.06, bottom_pct=0.08),
    "1:1": SafeArea(horizontal_pct=0.07, top_pct=0.08, bottom_pct=0.10),
    "4:5": SafeArea(horizontal_pct=0.08, top_pct=0.09, bottom_pct=0.12),
}

_DEFAULT_ASPECT_RATIO = "9:16"


def safe_area_for(aspect_ratio: str | None) -> SafeArea:
    return _SAFE_AREAS.get(aspect_ratio or _DEFAULT_ASPECT_RATIO, _SAFE_AREAS[_DEFAULT_ASPECT_RATIO])


def aspect_ratio_for_resolution(width: int, height: int) -> str:
    """Best-effort reverse mapping from a rendered resolution back to one of
    the supported aspect-ratio safe-area profiles."""

    ratio = width / height if height else 1.0
    candidates = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0, "4:5": 4 / 5}
    return min(candidates, key=lambda key: abs(candidates[key] - ratio))
