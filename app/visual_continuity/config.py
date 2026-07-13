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


def debug_enabled() -> bool:
    """VISUAL_CONTINUITY_DEBUG: when true, save the raw planner proposal,
    per-group reasoning, and repetition-guard decisions to
    visual-continuity-debug.json alongside the normal report. Disabled by
    default -- purely diagnostic, never read by the render pipeline."""

    return _truthy(os.getenv("VISUAL_CONTINUITY_DEBUG", "false"))


# ---------------------------------------------------------------------------
# Planner Cost Guard pricing -- approximate, configurable USD-per-1M-token /
# USD-per-image estimates. These are not verified against a live OpenAI
# billing dashboard; they exist so the cost guard has *some* deterministic
# number to compare against, and are deliberately overridable via env vars
# rather than hardcoded, since real pricing can change or differ by account
# tier. Correct them here if your account's real rates differ -- the guard
# logic itself does not change.
# ---------------------------------------------------------------------------

_DEFAULT_TEXT_PRICE_PER_1M_INPUT_USD = 0.25
_DEFAULT_TEXT_PRICE_PER_1M_OUTPUT_USD = 2.00
_DEFAULT_IMAGE_PRICE_USD = 0.02


def text_price_per_1m_input_usd() -> float:
    return _bounded_float(
        "VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_INPUT_USD",
        default=_DEFAULT_TEXT_PRICE_PER_1M_INPUT_USD, minimum=0.0, maximum=1000.0,
    )


def text_price_per_1m_output_usd() -> float:
    return _bounded_float(
        "VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_OUTPUT_USD",
        default=_DEFAULT_TEXT_PRICE_PER_1M_OUTPUT_USD, minimum=0.0, maximum=1000.0,
    )


def image_price_usd() -> float:
    return _bounded_float(
        "VISUAL_CONTINUITY_IMAGE_PRICE_USD",
        default=_DEFAULT_IMAGE_PRICE_USD, minimum=0.0, maximum=100.0,
    )


# Derived, real, historical average latency for one gpt-image-1 scene-image
# call (see PROFILING_REPORT.md: "Average image generation latency
# (derived): ~15.36s/call"). Shared by telemetry (render-time-saved
# estimate) and the cost guard (time-based disable check) so the two never
# disagree with each other.
_DEFAULT_ESTIMATED_SECONDS_PER_IMAGE = 15.36


def estimated_seconds_per_image() -> float:
    return _bounded_float(
        "VISUAL_CONTINUITY_ESTIMATED_SECONDS_PER_IMAGE",
        default=_DEFAULT_ESTIMATED_SECONDS_PER_IMAGE, minimum=0.0, maximum=3600.0,
    )
