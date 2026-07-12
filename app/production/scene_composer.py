from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.visual.taxonomy import resolve_category
from app.visual.topic import topic_phrase as _topic_phrase


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

    visual_type = str(getattr(scene, "visual_type", "environment"))
    focus = str(getattr(scene, "subject_focus", "") or "")
    category = resolve_category(visual_type)

    if category.subject_kind == "character":
        # Only a production that actually commissioned a character bible may
        # render a person; anything else falls back to the environment so an
        # unrecognized or mis-set visual_type can never conjure a presenter
        # out of nowhere.
        if character_bible is not None:
            subject = getattr(character_bible, "prompt_anchor", "") or focus or environment
        else:
            subject = focus or environment
    elif category.subject_kind == "environment":
        subject = focus or environment
    elif category.subject_kind == "object":
        subject = focus or (props[0] if props else "tactile symbolic object")
    elif category.subject_kind == "map":
        subject = focus or _topic_phrase(scene) or environment
    elif category.subject_kind == "abstract":
        subject = focus or f"a symbolic visual metaphor for: {_topic_phrase(scene)}"
    else:  # diagram / data visualization
        subject = focus or f"an explanatory diagram of: {_topic_phrase(scene)}"

    foreground = {
        "environment": "subtle foreground depth element",
        "architecture": "architectural foreground frame",
        "symbolic_object": "shallow-depth foreground texture",
        "document_or_archive": "paper edge and tactile material detail",
        "process_diagram": "clean diagrammatic framing with clear focal hierarchy",
        "data_visualization": "clean infographic framing",
        "comparative_scale": "clear side-by-side scale reference",
        "map_or_location": "cartographic or aerial framing depth",
        "abstract_concept": "soft symbolic foreground shape",
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
