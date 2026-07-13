from __future__ import annotations

import os


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "")
    try:
        return max(minimum, min(maximum, int(raw)))
    except (TypeError, ValueError):
        return default


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "")
    try:
        return max(minimum, min(maximum, float(raw)))
    except (TypeError, ValueError):
        return default


def visual_asset_economy_enabled() -> bool:
    return _truthy(os.getenv("VISUAL_ASSET_ECONOMY", "true"))


def image_cache_enabled() -> bool:
    return _truthy(os.getenv("IMAGE_CACHE_ENABLED", "true"))


def max_consecutive_reuse() -> int:
    """Hard cap: no Anchor Shot may cover more than this many consecutive
    scenes, regardless of what the planner proposes (spec: "Never reuse the
    same Anchor Shot for more than 3 consecutive scenes")."""

    return _bounded_int("MAX_CONSECUTIVE_REUSE", default=3, minimum=1, maximum=20)


def min_grouping_confidence() -> float:
    """Below this confidence, a proposed group is rejected and its scenes
    each get their own image instead -- reuse only happens when the planner
    is confident it is the same visual moment."""

    return _bounded_float("MIN_GROUPING_CONFIDENCE", default=0.75, minimum=0.0, maximum=1.0)
