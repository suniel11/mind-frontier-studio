from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from app.visual.taxonomy import VISUAL_CATEGORIES, resolve_category
from app.visual.topic import topic_phrase


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


# Domain-agnostic linguistic cues. None of these name a topic (no "atom",
# "GDP", "Rome", ...) -- they detect the *shape* of the sentence (does it
# explain a mechanism, cite a number, name a place, quote a person) which is
# what actually predicts whether a diagram, a map, an object, or a person is
# the right visual, regardless of subject domain.
_CONTENT_SIGNALS: dict[str, tuple[str, ...]] = {
    "process_diagram": (
        "how it works", "how they work", "works by", "structure of", "consists of",
        "composed of", "made up of", "made of", "mechanism", "process of", "processes",
        "system of", "steps", "cycle", "function", "functions", "forms when",
        "transforms", "converts", "reaction", "interacts", "interaction",
    ),
    "data_visualization": (
        "percent", "%", "statistic", "statistics", "data show", "study found",
        "research shows", "increase", "decrease", "growth rate", "on average",
        "survey", "measured", "rate of",
    ),
    "comparative_scale": (
        "compared to", "compared with", "times larger", "times smaller", "times bigger",
        "larger than", "smaller than", "bigger than", "the size of", "scale of",
        "magnitude", "relative to", "orders of magnitude",
    ),
    "map_or_location": (
        "country", "countries", "city", "cities", "region", "continent", "border",
        "located in", "miles from", "kilometers from", "journey to", "journey across",
        "route", "voyage", "expedition", "coastline", "territory", "traveled to",
        "crossed the",
    ),
    "document_or_archive": (
        "document", "letter", "manuscript", "archive", "photograph", "newspaper",
        "diary", "inscription", "ledger", "record shows", "handwritten",
    ),
    "symbolic_object": (
        "artifact", "relic", "instrument", "device", "tool used", "object that",
        "symbol of", "represents the",
    ),
    "abstract_concept": (
        "idea of", "concept of", "belief that", "consciousness", "meaning of",
        "philosophy", "theory of", "principle of", "notion that", "sense of self",
        "existence", "perception of",
    ),
    "character_moment": (
        "i believe", "in my experience", "he said", "she said", "they recalled",
        "testimony", "according to", "remembers", "confided", "felt that", "\"",
    ),
}

_NUMBER_PATTERN = re.compile(r"\d")
# A bare four-digit year ("in 1953...") is common history/biography narration
# and is not, by itself, a statistic -- strip it before the generic digit
# check so dates alone don't misfire as data_visualization.
_YEAR_PATTERN = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")

# Soft priors keyed by story beat. Both the current beat vocabulary
# (hook/setup/conflict/insight/resolution/final_line, see
# app/narrative/beats.py) and the legacy vocabulary used by older scenes and
# fixtures (hook/setup/tension/expansion/climax/resolution) are covered so a
# vocabulary drift between stages can never again silently fall through to a
# hardcoded character default.
_ROLE_PRIORS: dict[str, tuple[str, ...]] = {
    "hook": ("symbolic_object", "environment", "comparative_scale"),
    "setup": ("environment", "map_or_location", "architecture"),
    "conflict": ("comparative_scale", "symbolic_object", "data_visualization"),
    "tension": ("comparative_scale", "symbolic_object", "data_visualization"),
    "insight": ("process_diagram", "data_visualization", "abstract_concept"),
    "expansion": ("process_diagram", "data_visualization", "abstract_concept"),
    "resolution": ("environment", "abstract_concept", "architecture"),
    "climax": ("environment", "abstract_concept", "architecture"),
    "final_line": ("abstract_concept", "environment", "symbolic_object"),
    "development": ("process_diagram", "symbolic_object", "environment"),
}
_DEFAULT_ROLE_PRIOR = ("environment", "symbolic_object", "abstract_concept")

# Never let a scene silently fall back onto a human figure. If nothing else
# matches, cycle through these subject-agnostic, generic-safe categories.
_SAFE_FALLBACK_CYCLE = ("environment", "symbolic_object", "abstract_concept", "process_diagram")

# At most this share of a storyboard may use a character-centric visual, and
# only when the production actually requires a recurring character.
_MAX_CHARACTER_SHARE = 0.34


def _scene_text(scene) -> str:
    parts = [
        getattr(scene, "narration", "") or "",
        getattr(scene, "image_prompt", "") or "",
        getattr(scene, "narrative_goal", "") or "",
        getattr(scene, "on_screen_text", "") or "",
        getattr(scene, "visual_direction", "") or "",
        getattr(scene, "subject_focus", "") or "",
    ]
    return " ".join(parts).casefold()


def _content_scores(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for category, cues in _CONTENT_SIGNALS.items():
        hits = sum(1 for cue in cues if cue in text)
        if hits:
            scores[category] = hits
    if _NUMBER_PATTERN.search(_YEAR_PATTERN.sub("", text)):
        scores["data_visualization"] = scores.get("data_visualization", 0) + 1
    return scores


def _role_key(scene) -> str:
    return str(getattr(scene, "story_role", "") or "").casefold().strip()


def _requires_character(production_specification) -> bool:
    if production_specification is None:
        return True  # unknown production: preserve legacy behavior, don't forbid characters
    return bool(getattr(production_specification, "requires_character", False))


def _candidate_order(scene, allow_character: bool) -> list[str]:
    text = _scene_text(scene)
    content = _content_scores(text)
    role_prior = _ROLE_PRIORS.get(_role_key(scene), _DEFAULT_ROLE_PRIOR)

    ranked = sorted(content, key=lambda key: content[key], reverse=True)
    for category in role_prior:
        if category not in ranked:
            ranked.append(category)
    for category in _SAFE_FALLBACK_CYCLE:
        if category not in ranked:
            ranked.append(category)
    for category in ("character_moment", "presenter"):
        if category not in ranked:
            ranked.append(category)

    if not allow_character:
        ranked = [category for category in ranked if category not in ("character_moment", "presenter")]
    return ranked


def _select_category(decisions: list[ShotDecision], ordered_candidates: list[str], total_scenes: int) -> str:
    # No 3-in-a-row, and no single visual language dominating the whole
    # storyboard -- both checked before falling through to the next-ranked
    # candidate, so diversity holds across the full run, not just locally.
    usage_cap = max(2, -(-total_scenes // 3))
    recent = [item.visual_type for item in decisions[-2:]]
    counts: dict[str, int] = {}
    for item in decisions:
        counts[item.visual_type] = counts.get(item.visual_type, 0) + 1

    for candidate in ordered_candidates:
        if recent.count(candidate) >= 2:
            continue
        if counts.get(candidate, 0) >= usage_cap:
            continue
        return candidate
    for candidate in ordered_candidates:
        if recent.count(candidate) < 2:
            return candidate
    return ordered_candidates[0]


def plan_shots(storyboard, production_specification=None) -> list[ShotDecision]:
    scenes = list(storyboard.scenes)
    character_budget = (
        max(1, round(len(scenes) * _MAX_CHARACTER_SHARE))
        if _requires_character(production_specification)
        else 0
    )
    character_used = 0

    decisions: list[ShotDecision] = []
    for scene in scenes:
        allow_character = character_used < character_budget
        ordered = _candidate_order(scene, allow_character)
        visual_type = _select_category(decisions, ordered, len(scenes))

        if resolve_category(visual_type).requires_character:
            character_used += 1

        category = VISUAL_CATEGORIES[visual_type]
        content_default = {
            "character": "recurring character",
            "environment": "location and atmosphere",
            "object": "object detail with tactile realism",
            "diagram": topic_phrase(scene) or "the mechanism or relationship the narration describes",
            "map": topic_phrase(scene) or "geography and place",
            "abstract": topic_phrase(scene) or "a symbolic representation of the idea",
        }[category.subject_kind]
        subject_focus = str(getattr(scene, "subject_focus", "") or "") or content_default

        role = _role_key(scene) or "development"
        decisions.append(
            ShotDecision(
                scene_number=scene.number,
                visual_type=visual_type,
                framing=category.framing,
                subject_focus=subject_focus,
                composition=category.composition,
                caption_safe_area=category.caption_safe_area,
                camera_motion=category.camera_motion,
                reason=f"Selected {visual_type} for the {role} beat based on scene content and visual variety.",
            )
        )

    return decisions
