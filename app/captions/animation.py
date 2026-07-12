from __future__ import annotations

"""Caption entrance animation: fade, slide, pop, or none. Default is a
subtle fade. Generates plain ASS override tags -- no rendering-time
decisions, everything is computed up front.
"""

ANIMATIONS = ("fade", "slide", "pop", "none")
DEFAULT_ANIMATION = "fade"


def animation_tags(
    style: str,
    *,
    is_emphasis: bool = False,
    width: int = 1080,
    height: int = 1920,
    margin_v: int = 0,
    alignment: int = 2,
) -> str:
    style = style if style in ANIMATIONS else DEFAULT_ANIMATION

    if style == "none":
        return ""

    if style == "fade":
        return f"\\fad({70 if is_emphasis else 80},{90 if is_emphasis else 80})"

    if style == "pop":
        start_scale = 78 if is_emphasis else 88
        return (
            f"\\fad(60,80)\\fscx{start_scale}\\fscy{start_scale}"
            f"\\t(0,140,\\fscx100\\fscy100\\fscy100)"
        )

    # slide: a subtle move into the resting position, anchored consistently
    # with the style's own alignment so \move doesn't fight the normal
    # auto-position.
    x = width // 2
    if alignment >= 7:
        y_rest = margin_v
        y_start = max(0, y_rest - round(height * 0.03))
    elif 4 <= alignment <= 6:
        y_rest = height // 2
        y_start = y_rest + round(height * 0.02)
    else:
        y_rest = height - margin_v
        y_start = min(height, y_rest + round(height * 0.03))

    # \an is omitted here -- the caller (app/captions/engine.py) already sets
    # the alignment override once per event; \move's anchor point matches it.
    return f"\\fad(70,80)\\move({x},{y_start},{x},{y_rest})"
