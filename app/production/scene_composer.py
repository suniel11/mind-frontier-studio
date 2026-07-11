from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class SceneComposition:
    scene_number: int
    subject: str
    environment: str
    foreground: str
    recurring_props: list[str]
    lighting: str
    mood: str
    continuity: str
    shot_strategy: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def compose_scene(scene, storyboard, character_bible=None) -> SceneComposition:
    memory = getattr(storyboard, "visual_memory", None)

    location_id = str(getattr(scene, "location_id", "primary")).lower()
    if memory is None:
        environment = "cinematic documentary environment"
        props: list[str] = []
        lighting = "natural cinematic lighting"
    else:
        environment = (
            getattr(memory, "primary_location", "")
            if location_id == "primary"
            else getattr(memory, "secondary_location", "")
        )
        props = list(getattr(memory, "recurring_props", []) or [])
        lighting = getattr(memory, "lighting_language", "") or "natural cinematic lighting"

    visual_type = str(getattr(scene, "visual_type", "character_action"))
    focus = str(getattr(scene, "subject_focus", "") or "")

    if visual_type in {"environment", "architecture"}:
        subject = focus or environment
    elif visual_type in {"symbolic_object", "document_detail", "hands"}:
        subject = focus or (props[0] if props else "tactile symbolic object")
    else:
        if character_bible is not None:
            subject = getattr(character_bible, "prompt_anchor", "") or "fictional recurring protagonist"
        else:
            subject = "fictional recurring protagonist"

    foreground = {
        "environment": "subtle foreground depth element",
        "architecture": "architectural foreground frame",
        "symbolic_object": "shallow-depth foreground texture",
        "document_detail": "paper edge and tactile material detail",
        "hands": "natural hand and object interaction",
    }.get(visual_type, "soft cinematic foreground separation")

    return SceneComposition(
        scene_number=int(getattr(scene, "number", 0)),
        subject=subject,
        environment=environment or "cinematic documentary setting",
        foreground=foreground,
        recurring_props=props,
        lighting=lighting,
        mood=str(getattr(scene, "visual_emotion", "") or getattr(scene, "story_role", "reflective")),
        continuity=str(getattr(scene, "continuity_anchor", "") or ""),
        shot_strategy=visual_type,
    )
