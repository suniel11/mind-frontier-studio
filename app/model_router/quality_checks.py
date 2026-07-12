from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from app.creative_director.models import ProductionBrief, QuestionResponse
from app.models import CharacterBible, ResearchBrief, SeoPackage, ShortScript, Storyboard
from app.narrative.duration_planning import scenes_for_duration

_PLACEHOLDER_MARKERS = (
    "lorem ipsum",
    "todo",
    "tbd",
    "[insert",
    "n/a",
    "xxx",
    "placeholder text",
)


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    # True when no deterministic rule could actually judge this output (a
    # stage with no dedicated check below). MODEL_REQUIRE_BASELINE_QUALITY
    # treats "inconclusive" as "prefer baseline" (Phase 6: "If reliable
    # quality comparison cannot be performed, prefer baseline_model").
    inconclusive: bool = False


def ok() -> ValidationResult:
    return ValidationResult(passed=True, reasons=[])


def fail(*reasons: str) -> ValidationResult:
    return ValidationResult(passed=False, reasons=[reason for reason in reasons if reason])


def inconclusive(reason: str) -> ValidationResult:
    return ValidationResult(passed=True, reasons=[reason], inconclusive=True)


def _contains_placeholder(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _has_duplicates(values: list[str]) -> bool:
    cleaned = [value.strip().casefold() for value in values if value.strip()]
    return bool(cleaned) and len(cleaned) != len(set(cleaned))


def _has_excessive_repetition(text: str, *, max_repeats: int = 3) -> bool:
    sentences = [segment.strip().casefold() for segment in re.split(r"[.!?]+", text) if segment.strip()]
    counts: dict[str, int] = {}
    for sentence in sentences:
        counts[sentence] = counts.get(sentence, 0) + 1
        if counts[sentence] >= max_repeats:
            return True
    return False


# ---------------------------------------------------------------------------
# Creative Director
# ---------------------------------------------------------------------------


def validate_creative_director_questions(response: QuestionResponse) -> ValidationResult:
    reasons: list[str] = []
    questions = response.questions
    if not questions:
        reasons.append("no questions returned")
    if len(questions) > 5:
        reasons.append("more than 5 questions returned")
    if _has_duplicates([question.question for question in questions]):
        reasons.append("duplicate question text")
    if _has_duplicates([question.id for question in questions]):
        reasons.append("duplicate question ids")
    for question in questions:
        if len(question.options) < 2:
            reasons.append(f"question {question.id!r} has fewer than 2 options")
    return fail(*reasons) if reasons else ok()


def validate_creative_director_brief(
    brief: ProductionBrief,
    *,
    expected_answers: dict | None = None,
) -> ValidationResult:
    reasons: list[str] = []
    if _contains_placeholder(brief.creative_brief):
        reasons.append("creative brief contains placeholder text")
    if len(brief.creative_brief.strip()) < 20:
        reasons.append("creative brief is too short")
    if not (20 <= brief.target_seconds <= 180):
        reasons.append("target_seconds outside supported bounds")
    if not brief.hook_type.strip():
        reasons.append("missing hook_type")
    if expected_answers:
        # Preserve explicit user answers -- mirrors the leak check the
        # Creative Director engine already runs on the deterministic path
        # (_contains_raw_answers), catching a model that dumps the raw
        # answers payload into prose instead of writing a brief.
        brief_text = brief.creative_brief.casefold()
        for value in expected_answers.values():
            if isinstance(value, str) and len(value) > 12 and value.casefold() in brief_text:
                reasons.append("creative brief appears to leak the raw answers payload")
                break
    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


def validate_research(brief: ResearchBrief) -> ValidationResult:
    reasons: list[str] = []
    if not brief.central_question.strip():
        reasons.append("missing central_question")
    if not brief.core_insight.strip():
        reasons.append("missing core_insight")
    if not brief.verified_points:
        reasons.append("no verified_points")
    if not brief.audience_relevance.strip():
        reasons.append("missing audience_relevance")
    if not brief.possible_angles:
        reasons.append("no possible_angles")
    if _has_duplicates(brief.verified_points):
        reasons.append("duplicated entries in verified_points")
    if _has_duplicates(brief.possible_angles):
        reasons.append("duplicated entries in possible_angles")
    if any(_contains_placeholder(point) for point in brief.verified_points):
        reasons.append("placeholder content in verified_points")
    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------


def validate_script(
    script: ShortScript,
    *,
    target_seconds: int,
    tolerance: float = 0.45,
) -> ValidationResult:
    reasons: list[str] = []
    if not script.title.strip():
        reasons.append("missing title")
    if not script.hook.strip():
        reasons.append("missing hook")
    if not script.ending.strip():
        reasons.append("missing ending")

    voiceover = script.voiceover.strip()
    if not voiceover:
        reasons.append("missing voiceover")
        return fail(*reasons)

    word_count = len(voiceover.split())
    target_words = max(1.0, target_seconds * 2.2)
    low, high = target_words * (1 - tolerance), target_words * (1 + tolerance)
    if not (low <= word_count <= high):
        reasons.append(
            f"voiceover word count {word_count} outside tolerance "
            f"({low:.0f}-{high:.0f} for a {target_seconds}s target)"
        )
    if _contains_placeholder(voiceover):
        reasons.append("voiceover contains placeholder text")
    if _has_excessive_repetition(voiceover):
        reasons.append("voiceover has excessive repeated sentences")

    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# Storyboard
# ---------------------------------------------------------------------------


def validate_storyboard(storyboard: Storyboard, *, target_seconds: int) -> ValidationResult:
    reasons: list[str] = []
    scenes = storyboard.scenes
    if not scenes:
        return fail("no scenes")

    expected_count = scenes_for_duration(target_seconds)
    if len(scenes) != expected_count:
        reasons.append(f"expected {expected_count} scenes, got {len(scenes)}")

    if scenes[0].story_role != "hook":
        reasons.append("first scene is not the hook")
    if scenes[-1].story_role != "final_line":
        reasons.append("last scene is not the final_line")
    if scenes[0].start_second != 0:
        reasons.append("first scene does not start at second 0")

    last_end = scenes[-1].end_second
    if abs(last_end - target_seconds) > max(3, round(target_seconds * 0.1)):
        reasons.append(f"last scene ends at {last_end}s, expected near {target_seconds}s")

    for previous, current in zip(scenes, scenes[1:]):
        if current.start_second < previous.start_second:
            reasons.append("scene timing is not monotonic")
            break

    for scene in scenes:
        if not scene.narration.strip() and not scene.visual_direction.strip():
            reasons.append(f"scene {scene.number} has neither narration nor visual_direction")
            break

    if len(scenes) >= 3 and len({scene.shot_type for scene in scenes}) <= 1:
        reasons.append("no visual diversity across scenes (shot_type never varies)")

    if not storyboard.story_arc_summary.strip():
        reasons.append("missing story_arc_summary")

    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# Character bible
# ---------------------------------------------------------------------------


def validate_character(character: CharacterBible, *, expected_gender: str | None = None) -> ValidationResult:
    reasons: list[str] = []
    gender = character.gender.strip().casefold()
    if gender not in {"male", "female"}:
        reasons.append("gender must be exactly 'male' or 'female'")
    elif expected_gender and gender != expected_gender.strip().casefold():
        reasons.append(
            f"gender {character.gender!r} does not match the explicit user preference {expected_gender!r}"
        )
    if not character.name.strip():
        reasons.append("missing name")
    if not character.prompt_anchor.strip():
        reasons.append("missing prompt_anchor")
    if not character.negative_constraints.strip():
        reasons.append("missing negative_constraints")
    if not character.continuity_tags:
        reasons.append("missing continuity_tags")
    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# SEO / metadata
# ---------------------------------------------------------------------------


def validate_seo(seo: SeoPackage, *, max_hashtags: int = 8) -> ValidationResult:
    reasons: list[str] = []
    title = seo.title.strip()
    if not (5 <= len(title) <= 100):
        reasons.append(f"title length {len(title)} outside 5-100 characters")

    description = seo.description.strip()
    if len(description) < 20:
        reasons.append("description too short")
    if _contains_placeholder(description) or _contains_placeholder(title):
        reasons.append("placeholder content in title/description")

    hashtags = [tag.strip() for tag in seo.hashtags if tag.strip()]
    if not hashtags:
        reasons.append("no hashtags")
    if len(hashtags) > max_hashtags:
        reasons.append(f"too many hashtags ({len(hashtags)})")
    for tag in hashtags:
        if not re.match(r"^#?[A-Za-z0-9_]+$", tag):
            reasons.append(f"malformed hashtag {tag!r}")

    return fail(*reasons) if reasons else ok()


# ---------------------------------------------------------------------------
# Factories -- build a ``Callable[[output], ValidationResult]`` closure with
# whatever per-call context (target_seconds, expected preferences, ...) a
# stage needs, so agent call sites can pass a single ``validate`` argument
# into ``app.model_router.execution.run_agent_stage``.
# ---------------------------------------------------------------------------


def research_validator() -> Callable[[ResearchBrief], ValidationResult]:
    return validate_research


def script_validator(*, target_seconds: int) -> Callable[[ShortScript], ValidationResult]:
    return lambda script: validate_script(script, target_seconds=target_seconds)


def storyboard_validator(*, target_seconds: int) -> Callable[[Storyboard], ValidationResult]:
    return lambda storyboard: validate_storyboard(storyboard, target_seconds=target_seconds)


def character_validator(*, expected_gender: str | None = None) -> Callable[[CharacterBible], ValidationResult]:
    return lambda character: validate_character(character, expected_gender=expected_gender)


def seo_validator() -> Callable[[SeoPackage], ValidationResult]:
    return validate_seo


def creative_director_questions_validator() -> Callable[[QuestionResponse], ValidationResult]:
    return validate_creative_director_questions


def creative_director_brief_validator(
    *, expected_answers: dict | None = None
) -> Callable[[ProductionBrief], ValidationResult]:
    return lambda brief: validate_creative_director_brief(brief, expected_answers=expected_answers)


def inconclusive_validator(
    reason: str = "no deterministic quality check implemented for this stage",
) -> Callable[[object], ValidationResult]:
    return lambda _output: inconclusive(reason)
