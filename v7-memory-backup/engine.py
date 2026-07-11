from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class DirectorDecision:
    scene_number: int
    shot_type: str
    visual_type: str
    motion_type: str
    location_hint: str
    subject_focus: str
    emotional_intensity: int
    caption_style: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


ROLE_PLAN = {
    "hook": {
        "shot_type": "extreme_close_up",
        "visual_type": "character_detail",
        "motion_type": "micro_push",
        "location_hint": "dark interior with strong negative space",
        "subject_focus": "eyes, hands, or a single meaningful detail",
        "caption_style": "hook",
    },
    "setup": {
        "shot_type": "wide",
        "visual_type": "environment",
        "motion_type": "pan_right",
        "location_hint": "establishing view of the recurring location",
        "subject_focus": "environment and atmosphere",
        "caption_style": "standard",
    },
    "tension": {
        "shot_type": "close_up",
        "visual_type": "symbolic_object",
        "motion_type": "drift",
        "location_hint": "same location, tighter and more confined",
        "subject_focus": "recurring object, clock, notebook, mirror, or unfinished work",
        "caption_style": "emphasis",
    },
    "expansion": {
        "shot_type": "over_shoulder",
        "visual_type": "character_action",
        "motion_type": "parallax_left",
        "location_hint": "secondary location or meaningful variation of the primary location",
        "subject_focus": "protagonist interacting with the environment",
        "caption_style": "standard",
    },
    "climax": {
        "shot_type": "close_up",
        "visual_type": "character_emotion",
        "motion_type": "static",
        "location_hint": "visually compressed emotional setting",
        "subject_focus": "face, posture, and restrained emotion",
        "caption_style": "emphasis",
    },
    "resolution": {
        "shot_type": "wide",
        "visual_type": "environmental_hero",
        "motion_type": "dolly_out",
        "location_hint": "open, resolved version of the environment",
        "subject_focus": "protagonist within a larger hopeful setting",
        "caption_style": "resolution",
    },
}


def apply_director_engine(storyboard):
    recent_visuals: list[str] = []
    recent_motions: list[str] = []
    decisions: list[DirectorDecision] = []

    for scene in storyboard.scenes:
        role = str(getattr(scene, "story_role", "") or "").lower()
        plan = ROLE_PLAN.get(role, ROLE_PLAN["expansion"]).copy()

        visual_type = plan["visual_type"]
        if len(recent_visuals) >= 2 and recent_visuals[-1] == recent_visuals[-2] == visual_type:
            visual_type = "environment" if visual_type != "environment" else "symbolic_object"

        motion_type = plan["motion_type"]
        if recent_motions and recent_motions[-1] == motion_type:
            alternatives = ["micro_push", "drift", "pan_left", "pan_right", "static", "dolly_out"]
            motion_type = next((item for item in alternatives if item != recent_motions[-1]), motion_type)

        intensity = int(getattr(scene, "emotional_intensity", 5) or 5)

        decision = DirectorDecision(
            scene_number=int(scene.number),
            shot_type=plan["shot_type"],
            visual_type=visual_type,
            motion_type=motion_type,
            location_hint=plan["location_hint"],
            subject_focus=plan["subject_focus"],
            emotional_intensity=intensity,
            caption_style=plan["caption_style"],
        )

        scene.shot_type = decision.shot_type
        scene.visual_type = decision.visual_type
        scene.motion_type = decision.motion_type
        scene.subject_focus = decision.subject_focus
        scene.caption_emphasis = (
            getattr(scene, "caption_emphasis", "") or getattr(scene, "on_screen_text", "")
        )
        scene.visual_direction = (
            f"{scene.visual_direction} "
            f"Director plan: {decision.visual_type}, {decision.shot_type}, "
            f"{decision.motion_type}, focus on {decision.subject_focus}. "
            f"Location treatment: {decision.location_hint}."
        ).strip()

        recent_visuals.append(decision.visual_type)
        recent_motions.append(decision.motion_type)
        decisions.append(decision)

    return storyboard, decisions
