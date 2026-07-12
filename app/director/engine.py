from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification


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
        "visual_type": "subject_detail",
        "motion_type": "micro_push",
        "location_hint": "high-impact setting with intentional negative space",
        "subject_focus": "the most immediately compelling subject detail",
        "caption_style": "hook",
    },
    "setup": {
        "shot_type": "wide",
        "visual_type": "environment",
        "motion_type": "pan_right",
        "location_hint": "clear establishing view of the production world",
        "subject_focus": "context, environment, and central subject",
        "caption_style": "standard",
    },
    "conflict": {
        "shot_type": "close_up",
        "visual_type": "symbolic_object",
        "motion_type": "drift",
        "location_hint": "a tighter treatment that communicates pressure or contrast",
        "subject_focus": "the central obstacle, contrast, product detail, or symbolic object",
        "caption_style": "emphasis",
    },
    "insight": {
        "shot_type": "medium",
        "visual_type": "subject_action",
        "motion_type": "parallax_left",
        "location_hint": "a meaningful variation that reveals the core idea",
        "subject_focus": "the explanatory action, transformation, or key evidence",
        "caption_style": "standard",
    },
    "resolution": {
        "shot_type": "wide",
        "visual_type": "environmental_hero",
        "motion_type": "dolly_out",
        "location_hint": "an open and resolved treatment of the production world",
        "subject_focus": "the resolved subject within a clear final context",
        "caption_style": "resolution",
    },
    "final_line": {
        "shot_type": "wide",
        "visual_type": "symbolic_object",
        "motion_type": "micro_push",
        "location_hint": "a simple final composition with room for the closing thought",
        "subject_focus": "one memorable final image",
        "caption_style": "resolution",
    },
}

ROLE_ALIASES = {
    "tension": "conflict",
    "expansion": "insight",
    "climax": "resolution",
    "development": "insight",
}

MODEL_DEFAULTS = {
    "shot_type": "medium",
    "visual_type": "character_action",
    "motion_type": "dolly_in",
    "subject_focus": "",
}


def _directed_value(scene, field: str, fallback: str) -> str:
    value = str(getattr(scene, field, "") or "").strip()
    if not value or value == MODEL_DEFAULTS.get(field):
        return fallback
    return value


def _character_free_direction(
    value: str,
    fallback: str,
    specification: ProductionSpecification | None,
) -> str:
    if specification is None or specification.requires_character:
        return value
    lowered = value.casefold()
    if "character" not in lowered and "protagonist" not in lowered:
        return value
    return fallback


def apply_director_engine(
    storyboard,
    studio_profile=None,
    production_specification: ProductionSpecification | None = None,
):
    studio_profile = studio_profile or {}
    preferred_motions = list(studio_profile.get("preferred_motions", []) or [])
    preferred_visuals = list(studio_profile.get("preferred_visual_types", []) or [])

    recent_visuals: list[str] = []
    recent_motions: list[str] = []
    decisions: list[DirectorDecision] = []

    for scene in storyboard.scenes:
        raw_role = str(getattr(scene, "story_role", "") or "").lower()
        role = ROLE_ALIASES.get(raw_role, raw_role)
        plan = ROLE_PLAN.get(role, ROLE_PLAN["insight"]).copy()

        visual_type = _directed_value(scene, "visual_type", plan["visual_type"])
        visual_type = _character_free_direction(
            visual_type,
            plan["visual_type"],
            production_specification,
        )
        if len(recent_visuals) >= 2 and recent_visuals[-1] == recent_visuals[-2] == visual_type:
            visual_type = "environment" if visual_type != "environment" else "symbolic_object"
        if (
            preferred_visuals
            and getattr(scene, "visual_type", MODEL_DEFAULTS["visual_type"])
            == MODEL_DEFAULTS["visual_type"]
        ):
            compatible = [
                item
                for item in preferred_visuals
                if production_specification is None
                or production_specification.requires_character
                or "character" not in item.casefold()
            ]
            if compatible:
                visual_type = compatible[0]

        motion_type = _directed_value(scene, "motion_type", plan["motion_type"])
        if recent_motions and recent_motions[-1] == motion_type:
            alternatives = preferred_motions or [
                "micro_push",
                "drift",
                "pan_left",
                "pan_right",
                "static",
                "dolly_out",
            ]
            motion_type = next(
                (item for item in alternatives if item != recent_motions[-1]),
                motion_type,
            )

        shot_type = _directed_value(scene, "shot_type", plan["shot_type"])
        subject_focus = _directed_value(
            scene,
            "subject_focus",
            plan["subject_focus"],
        )
        subject_focus = _character_free_direction(
            subject_focus,
            getattr(production_specification, "effective_subject", None)
            or plan["subject_focus"],
            production_specification,
        )
        intensity = int(getattr(scene, "emotional_intensity", 5) or 5)
        caption_style = (
            getattr(production_specification, "caption_style", None)
            or plan["caption_style"]
        )

        decision = DirectorDecision(
            scene_number=int(scene.number),
            shot_type=shot_type,
            visual_type=visual_type,
            motion_type=motion_type,
            location_hint=plan["location_hint"],
            subject_focus=subject_focus,
            emotional_intensity=intensity,
            caption_style=caption_style,
        )

        scene.shot_type = decision.shot_type
        scene.visual_type = decision.visual_type
        scene.motion_type = decision.motion_type
        scene.subject_focus = decision.subject_focus
        if getattr(production_specification, "pacing", None):
            scene.pacing = production_specification.pacing
        scene.caption_emphasis = (
            getattr(scene, "caption_emphasis", "")
            or getattr(scene, "on_screen_text", "")
        )

        creative_context = []
        if getattr(production_specification, "tone", None):
            creative_context.append(f"tone: {production_specification.tone}")
        if getattr(production_specification, "visual_style", None):
            creative_context.append(f"visual style: {production_specification.visual_style}")
        context_text = f" Creator direction: {', '.join(creative_context)}." if creative_context else ""
        scene.visual_direction = (
            f"{getattr(scene, 'visual_direction', '')} "
            f"Director plan: {decision.visual_type}, {decision.shot_type}, "
            f"{decision.motion_type}, focus on {decision.subject_focus}. "
            f"Location treatment: {decision.location_hint}.{context_text}"
        ).strip()

        recent_visuals.append(decision.visual_type)
        recent_motions.append(decision.motion_type)
        decisions.append(decision)

    return storyboard, decisions
