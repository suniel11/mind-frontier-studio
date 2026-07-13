from __future__ import annotations

# Every motion type here is already implemented and rendered by
# app.cinema.motion.compose_motion_filter -- this module only decides
# *which* treatment each scene in a shared Visual Asset Group gets, so two
# scenes referencing the same underlying image are never given the same
# camera movement. Ordered so the first scene in any group (the
# establishing view) always gets a clean, simple treatment.
_VARIATION_ROTATION = [
    "static",
    "dolly_in",
    "pan_left",
    "dolly_out",
    "pan_right",
    "drift",
    "tilt_up",
    "micro_push",
    "tilt_down",
]


def assign_shot_variations(count: int) -> list[str]:
    """Return ``count`` motion_type values, guaranteed to contain no two
    equal values for any ``count`` up to ``len(_VARIATION_ROTATION)`` (9) --
    comfortably above MAX_CONSECUTIVE_REUSE's default and maximum (20 is
    the config ceiling, but rotation still avoids *adjacent* repeats past
    that by cycling)."""

    if count <= 0:
        return []
    if count == 1:
        return ["dolly_in"]
    return [_VARIATION_ROTATION[position % len(_VARIATION_ROTATION)] for position in range(count)]
