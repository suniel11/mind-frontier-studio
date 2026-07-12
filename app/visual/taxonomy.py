from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualCategory:
    """One visual language a scene can be rendered in.

    ``subject_kind`` tells scene_composer.py how to build the subject line
    generically, without knowing anything about the category itself.
    """

    key: str
    requires_character: bool
    framing: str
    composition: str
    camera_motion: str
    caption_safe_area: str
    subject_kind: str
    prompt_guidance: str


VISUAL_CATEGORIES: dict[str, VisualCategory] = {
    "presenter": VisualCategory(
        key="presenter",
        requires_character=True,
        framing="medium",
        composition="center-weighted, direct address",
        camera_motion="static",
        caption_safe_area="lower_third",
        subject_kind="character",
        prompt_guidance=(
            "A single recurring presenter speaking directly to camera. "
            "Use only when the narration is a direct address or personal testimony."
        ),
    ),
    "character_moment": VisualCategory(
        key="character_moment",
        requires_character=True,
        framing="medium_close_up",
        composition="rule of thirds, emotional framing",
        camera_motion="dolly_in",
        caption_safe_area="lower_third",
        subject_kind="character",
        prompt_guidance=(
            "The recurring character experiencing or reacting to the story beat, "
            "shown acting within their environment rather than addressing the camera."
        ),
    ),
    "environment": VisualCategory(
        key="environment",
        requires_character=False,
        framing="wide",
        composition="rule of thirds, establishing depth",
        camera_motion="pan_right",
        caption_safe_area="lower_third",
        subject_kind="environment",
        prompt_guidance=(
            "A wide establishing view of the location, atmosphere, and production design. "
            "No human figure required unless the subject naturally belongs to the scene."
        ),
    ),
    "architecture": VisualCategory(
        key="architecture",
        requires_character=False,
        framing="wide",
        composition="leading lines emphasizing structure and scale",
        camera_motion="tilt_up",
        caption_safe_area="lower_third",
        subject_kind="environment",
        prompt_guidance="A structural or architectural view emphasizing scale, form, and leading lines.",
    ),
    "symbolic_object": VisualCategory(
        key="symbolic_object",
        requires_character=False,
        framing="close_up",
        composition="shallow depth of field, tactile detail",
        camera_motion="drift",
        caption_safe_area="upper_third",
        subject_kind="object",
        prompt_guidance=(
            "A close, tactile view of the single object, artifact, or prop that carries the "
            "scene's meaning. No presenter, no unrelated human figure."
        ),
    ),
    "document_or_archive": VisualCategory(
        key="document_or_archive",
        requires_character=False,
        framing="close_up",
        composition="flat-lay or archival framing",
        camera_motion="static",
        caption_safe_area="upper_third",
        subject_kind="object",
        prompt_guidance=(
            "An archival or documentary artifact: a record, photograph, letter, manuscript, "
            "or similar material evidence, rendered with period-appropriate realism."
        ),
    ),
    "process_diagram": VisualCategory(
        key="process_diagram",
        requires_character=False,
        framing="medium",
        composition="clean explanatory composition with clear focal hierarchy",
        camera_motion="drift",
        caption_safe_area="lower_third",
        subject_kind="diagram",
        prompt_guidance=(
            "A clear explanatory diagram, cutaway illustration, or scientific rendering that "
            "shows how the subject works or is structured. Prioritize legibility over realism. "
            "No presenter or narrator figure."
        ),
    ),
    "data_visualization": VisualCategory(
        key="data_visualization",
        requires_character=False,
        framing="medium",
        composition="clean chart or infographic composition",
        camera_motion="static",
        caption_safe_area="lower_third",
        subject_kind="diagram",
        prompt_guidance=(
            "A clean data visualization, chart, or infographic communicating the scene's "
            "statistic or trend. No presenter or narrator figure."
        ),
    ),
    "comparative_scale": VisualCategory(
        key="comparative_scale",
        requires_character=False,
        framing="wide",
        composition="side-by-side or nested scale comparison",
        camera_motion="pan_left",
        caption_safe_area="lower_third",
        subject_kind="diagram",
        prompt_guidance=(
            "A side-by-side or nested scale comparison that makes the relative size, "
            "magnitude, or quantity in the narration immediately legible."
        ),
    ),
    "map_or_location": VisualCategory(
        key="map_or_location",
        requires_character=False,
        framing="wide",
        composition="cartographic or aerial framing",
        camera_motion="dolly_out",
        caption_safe_area="lower_third",
        subject_kind="map",
        prompt_guidance=(
            "A map, aerial view, or geographic visualization that grounds the narration in a "
            "real place, route, or territory."
        ),
    ),
    "abstract_concept": VisualCategory(
        key="abstract_concept",
        requires_character=False,
        framing="medium",
        composition="symbolic, high negative space",
        camera_motion="drift",
        caption_safe_area="upper_third",
        subject_kind="abstract",
        prompt_guidance=(
            "A symbolic or abstract visual metaphor for the idea in the narration. "
            "No presenter figure; let composition, light, and form carry the meaning."
        ),
    ),
}


# Values written by older stages (director/engine.py, shot_planner test fixtures,
# hand-authored scenes) that predate this taxonomy. Mapping them here means an
# unrecognized value can never silently collapse into a human presenter.
LEGACY_ALIASES: dict[str, str] = {
    "character_action": "character_moment",
    "character_detail": "character_moment",
    "character_emotion": "character_moment",
    "environmental_hero": "environment",
    "subject_detail": "symbolic_object",
    "subject_action": "process_diagram",
    "hands": "symbolic_object",
    "document_detail": "document_or_archive",
}

DEFAULT_CATEGORY = "environment"


def resolve_category(visual_type: str) -> VisualCategory:
    key = LEGACY_ALIASES.get(visual_type, visual_type)
    return VISUAL_CATEGORIES.get(key, VISUAL_CATEGORIES[DEFAULT_CATEGORY])
