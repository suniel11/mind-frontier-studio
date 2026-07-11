from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ShotDecision:
    scene_number: int
    visual_type: str
    framing: str
    subject_focus: str
    composition: str
    caption_safe_area: str
    camera_motion: str
    reason: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


ROLE_DEFAULTS = {
    "hook": ("character_detail", "extreme_close_up", "eyes or hands", "center-weighted tension", "lower_third", "dolly_in"),
    "setup": ("environment", "wide", "location and atmosphere", "rule of thirds", "lower_third", "pan_right"),
    "tension": ("symbolic_object", "close_up", "recurring prop", "diagonal tension", "upper_third", "drift"),
    "expansion": ("character_action", "medium", "protagonist in environment", "leading lines", "lower_third", "pan_left"),
    "climax": ("character_emotion", "close_up", "face and posture", "tight negative space", "lower_third", "static"),
    "resolution": ("environmental_hero", "wide", "protagonist and resolved setting", "balanced symmetry", "upper_third", "dolly_out"),
}


def _avoid_repetition(decisions: list[ShotDecision], visual_type: str) -> str:
    if len(decisions) >= 2 and decisions[-1].visual_type == decisions[-2].visual_type == visual_type:
        for candidate in ("environment", "symbolic_object", "hands", "architecture", "document_detail"):
            if all(item.visual_type != candidate for item in decisions[-2:]):
                return candidate
    return visual_type


def plan_shots(storyboard) -> list[ShotDecision]:
    decisions: list[ShotDecision] = []

    for scene in storyboard.scenes:
        role = str(getattr(scene, "story_role", "development")).lower()
        visual_type, framing, subject_focus, composition, safe_area, motion = ROLE_DEFAULTS.get(
            role,
            ("character_action", "medium", "protagonist", "rule of thirds", "lower_third", "dolly_in"),
        )
        visual_type = _avoid_repetition(decisions, visual_type)

        if visual_type == "environment":
            framing = "wide"
            subject_focus = "location, atmosphere, and production design"
        elif visual_type in {"symbolic_object", "hands", "document_detail"}:
            framing = "close_up"
            subject_focus = "object detail with tactile realism"
        elif visual_type == "architecture":
            framing = "wide"
            subject_focus = "structure, scale, and leading lines"

        decisions.append(
            ShotDecision(
                scene_number=scene.number,
                visual_type=visual_type,
                framing=framing,
                subject_focus=subject_focus,
                composition=composition,
                caption_safe_area=safe_area,
                camera_motion=motion,
                reason=f"Selected for {role} beat and visual variety.",
            )
        )

    return decisions
