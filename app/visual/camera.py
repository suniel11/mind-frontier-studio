from __future__ import annotations


def normalize_motion(motion: str) -> str:
    aliases = {
        "push_in": "dolly_in",
        "pull_back": "dolly_out",
        "static_hold": "static",
        "handheld_drift": "drift",
        "slow_crane": "tilt_up",
    }
    return aliases.get(motion, motion)
