from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from app.creative_director.llm import CreativeDirectorLLM
from app.creative_director.models import (
    CreativeAnswers,
    CreativePrompt,
    DirectorQuestion,
    ProductionBrief,
    QuestionResponse,
)
from app.creative_director.preferences import (
    CreatorPreferences,
    PreferenceStore,
    preference_store,
)
from app.production.specification import ProductionSpecification


logger = logging.getLogger(__name__)


class CreativeDirectorServiceError(RuntimeError):
    """A safe error that may be translated by the HTTP layer."""


def fallback_questionnaire(
    prompt: str = "",
    preferences: CreatorPreferences | None = None,
) -> QuestionResponse:
    questions = [
        DirectorQuestion(
            id="target_audience",
            question="Who should this be created for?",
            type="single_choice",
            options=[
                "General audience",
                "Specific community",
                "Professional audience",
                "Younger audience",
            ],
        ),
        DirectorQuestion(
            id="output_format",
            question="Which output format best fits the idea?",
            type="single_choice",
            options=[
                "Short-form video",
                "Long-form video",
                "Audio-led piece",
                "Visual concept",
            ],
        ),
        DirectorQuestion(
            id="runtime",
            question="What target runtime should production use?",
            type="single_choice",
            options=["30 seconds", "45 seconds", "60 seconds", "90 seconds"],
        ),
        DirectorQuestion(
            id="creative_direction",
            question="Which overall creative direction should lead?",
            type="single_choice",
            options=["Informative", "Cinematic", "Emotional", "Playful"],
        ),
    ]
    if _duration_seconds(prompt) is not None:
        questions = [question for question in questions if question.id != "runtime"]
    questions = _without_resolved_preference_questions(questions, preferences)
    return QuestionResponse(questions=questions)


class CreativeDirector:
    def __init__(
        self,
        llm_factory: Callable[[], CreativeDirectorLLM | None] | None = None,
        preferences: PreferenceStore | None = None,
    ) -> None:
        self._llm_factory = llm_factory
        self._preferences = preferences or preference_store

    def generate_questions(self, prompt: str) -> list[DirectorQuestion]:
        clean_prompt = CreativePrompt(prompt=prompt).prompt
        preferences = self._preferences.load()
        llm = self._get_llm()
        if llm is None:
            return fallback_questionnaire(clean_prompt, preferences).questions

        try:
            try:
                generated = llm.generate_questions(
                    clean_prompt,
                    preferences=preferences.populated(),
                )
            except TypeError:
                # Keep injected/legacy client adapters compatible.
                generated = llm.generate_questions(clean_prompt)
            result = QuestionResponse.model_validate(
                generated
            )
            return _without_resolved_preference_questions(
                result.questions,
                preferences,
            )
        except Exception as exc:
            self._log_fallback("question generation", exc)
            return fallback_questionnaire(clean_prompt, preferences).questions

    def build_brief(
        self,
        prompt: str,
        answers: dict[str, Any],
    ) -> ProductionBrief:
        validated = CreativeAnswers(prompt=prompt, answers=answers)
        effective_answers = _answers_with_preferences(
            validated.answers,
            self._preferences.load(),
        )
        llm = self._get_llm()
        if llm is not None:
            try:
                result = ProductionBrief.model_validate(
                    llm.generate_brief(validated.prompt, effective_answers)
                )
                if _contains_raw_answers(result.creative_brief, effective_answers):
                    raise ValueError("The generated brief serialized the answer mapping.")
                specification = result.production_specification.model_copy(
                    update={
                        "original_prompt": validated.prompt,
                        "subject": result.production_specification.subject
                        or validated.prompt,
                        "target_seconds": result.target_seconds,
                        "hook_strategy": result.production_specification.hook_strategy
                        or result.hook_type,
                        "source_brief_text": result.creative_brief,
                    }
                )
                return result.model_copy(
                    update={
                        "topic": validated.prompt,
                        "production_specification": specification,
                    }
                )
            except Exception as exc:
                self._log_fallback("brief generation", exc)

        return build_deterministic_brief(validated.prompt, effective_answers)

    def _get_llm(self) -> CreativeDirectorLLM | None:
        factory = self._llm_factory or CreativeDirectorLLM.from_environment
        try:
            return factory()
        except Exception as exc:
            self._log_fallback("client initialization", exc)
            return None

    @staticmethod
    def _log_fallback(operation: str, exc: Exception) -> None:
        logger.warning(
            "Creative Director %s failed; using fallback (%s).",
            operation,
            type(exc).__name__,
        )


def build_deterministic_brief(
    prompt: str,
    answers: dict[str, Any],
) -> ProductionBrief:
    target_seconds = _target_seconds(prompt, answers)
    hook_type = _answer_text(answers, "hook_type", "hook_strategy")
    hook_type = (hook_type or "curiosity-led opening")[:80]
    brief_subject = prompt if len(prompt) <= 1800 else f"{prompt[:1797].rstrip()}..."

    sections: list[tuple[str, str]] = [
        (
            "Creative Objective",
            "Create a clear, engaging production that realizes the user's central intent.",
        ),
        ("Core Subject", brief_subject),
    ]

    optional_sections = [
        ("Target Audience", ("target_audience", "audience")),
        ("Format", ("output_format", "format")),
        ("Visual Direction", ("visual_direction", "visual_style", "creative_direction")),
        ("Narration Direction", ("narration", "narration_direction", "voice")),
        ("Emotional Arc", ("emotional_arc", "emotion", "tone")),
        ("Ending", ("ending", "ending_direction")),
        ("Production Constraints", ("constraints", "production_constraints")),
    ]
    for heading, keys in optional_sections:
        value = _answer_text(answers, *keys)
        if value:
            sections.append((heading, value))

    sections.extend(
        [
            ("Runtime", f"Target approximately {target_seconds} seconds."),
            (
                "Hook Strategy",
                f"Use a {hook_type} that establishes the central promise immediately.",
            ),
            (
                "Narrative Structure",
                "Open with the core promise, develop the idea through a clear progression, "
                "and close with a memorable resolution.",
            ),
            (
                "Pacing and Editing",
                "Keep every beat purposeful, maintain continuity between ideas, and let "
                "important moments breathe without losing momentum.",
            ),
            (
                "Music and Sound",
                "Use sound to support clarity, rhythm, and emotional movement without "
                "competing with the primary message.",
            ),
            (
                "Success Criteria",
                "The finished piece should communicate its premise quickly, remain coherent "
                "throughout, and deliver an ending that feels earned.",
            ),
        ]
    )

    represented_keys = {
        key
        for _, keys in optional_sections
        for key in keys
    } | {"runtime", "duration", "target_seconds", "hook_type", "hook_strategy"}
    remaining = [
        (_label(key), _format_answer(value))
        for key, value in sorted(answers.items())
        if key not in represented_keys and _format_answer(value)
    ][:10]
    if remaining:
        sections.append(
            (
                "Additional Production Decisions",
                "\n".join(f"- {label}: {value}" for label, value in remaining),
            )
        )

    creative_brief = "\n\n".join(
        f"{heading}\n{body}" for heading, body in sections
    )
    if len(creative_brief) > 12000:
        creative_brief = f"{creative_brief[:11997].rstrip()}..."
    specification = _build_specification(
        prompt,
        answers,
        target_seconds=target_seconds,
        hook_type=hook_type,
        source_brief_text=creative_brief,
    )
    return ProductionBrief(
        topic=prompt,
        target_seconds=target_seconds,
        hook_type=hook_type,
        creative_brief=creative_brief,
        production_specification=specification,
    )


def _build_specification(
    prompt: str,
    answers: dict[str, Any],
    *,
    target_seconds: int,
    hook_type: str,
    source_brief_text: str,
) -> ProductionSpecification:
    return ProductionSpecification(
        original_prompt=prompt,
        subject=prompt,
        creative_objective=_answer_text(answers, "creative_objective", "objective") or None,
        audience=_answer_text(answers, "target_audience", "audience") or None,
        output_format=_answer_text(answers, "output_format", "format")
        or "short-form video",
        target_seconds=target_seconds,
        aspect_ratio=_answer_text(answers, "aspect_ratio", "orientation") or "9:16",
        tone=_answer_text(answers, "tone", "creative_direction", "emotion") or None,
        narration_style=_answer_text(
            answers,
            "narration_style",
            "narration_direction",
            "narration",
            "voice",
        )
        or None,
        visual_style=_answer_text(
            answers,
            "visual_style",
            "visual_direction",
        )
        or None,
        pacing=_answer_text(answers, "pacing", "editing_pace") or None,
        hook_strategy=hook_type,
        narrative_structure=_answer_text(
            answers,
            "narrative_structure",
            "structure",
        )
        or None,
        ending_direction=_answer_text(answers, "ending", "ending_direction") or None,
        music_direction=_answer_text(
            answers,
            "music_direction",
            "music_preference",
            "music",
        )
        or None,
        caption_style=_answer_text(answers, "caption_style", "captions") or None,
        accuracy_level=_answer_text(
            answers,
            "accuracy_level",
            "accuracy",
            "factual_treatment",
        )
        or None,
        protagonist_direction=_answer_text(
            answers,
            "protagonist_direction",
            "protagonist",
            "character_direction",
            "recurring_character",
        )
        or None,
        production_constraints=_answer_list(
            answers,
            "production_constraints",
            "constraints",
        ),
        negative_constraints=_answer_list(
            answers,
            "negative_constraints",
            "avoid",
        ),
        channel_id=_safe_channel_id(_answer_text(answers, "channel_id")),
        source_brief_text=source_brief_text,
    )


def _answers_with_preferences(
    answers: dict[str, Any],
    preferences: CreatorPreferences,
) -> dict[str, Any]:
    effective = dict(answers)
    aliases = {
        "target_seconds": ("target_seconds", "runtime", "duration"),
        "aspect_ratio": ("aspect_ratio", "orientation"),
        "tone": ("tone", "creative_direction", "emotion"),
        "visual_style": ("visual_style", "visual_direction"),
        "narration_style": (
            "narration_style",
            "narration_direction",
            "narration",
            "voice",
        ),
        "caption_style": ("caption_style", "captions"),
        "music_preference": ("music_preference", "music_direction", "music"),
    }
    for preference_key, answer_keys in aliases.items():
        value = getattr(preferences, preference_key)
        if value is not None and not any(key in effective for key in answer_keys):
            effective[preference_key] = value
    return effective


def _without_resolved_preference_questions(
    questions: list[DirectorQuestion],
    preferences: CreatorPreferences | None,
) -> list[DirectorQuestion]:
    if preferences is None:
        return questions
    resolved_ids: set[str] = set()
    preference_question_ids = {
        "target_seconds": {"runtime", "duration", "target_seconds"},
        "aspect_ratio": {"aspect_ratio", "orientation"},
        "tone": {"tone", "creative_direction"},
        "visual_style": {"visual_style", "visual_direction"},
        "narration_style": {"narration", "narration_style", "voice"},
        "caption_style": {"captions", "caption_style"},
        "music_preference": {"music", "music_direction", "music_preference"},
    }
    for key, ids in preference_question_ids.items():
        if getattr(preferences, key) is not None:
            resolved_ids.update(ids)
    return [question for question in questions if question.id not in resolved_ids]


def _answer_list(answers: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        if key not in answers:
            continue
        value = answers[key]
        values = value if isinstance(value, list) else [value]
        result = [_format_answer(item) for item in values]
        return [item for item in result if item][:20]
    return []


def _safe_channel_id(value: str) -> str | None:
    if not value:
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) else None


def _target_seconds(prompt: str, answers: dict[str, Any]) -> int:
    for key in ("target_seconds", "runtime", "duration"):
        value = answers.get(key)
        if isinstance(value, bool) or value is None:
            continue
        seconds = _duration_seconds(str(value), allow_plain_number=True)
        if seconds is not None:
            return seconds
    prompt_seconds = _duration_seconds(prompt)
    if prompt_seconds is not None:
        return prompt_seconds
    return 45


def _duration_seconds(
    value: str,
    *,
    allow_plain_number: bool = False,
) -> int | None:
    normalized = value.casefold()
    minute_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|\s)?(?:minutes?|mins?)\b",
        normalized,
    )
    if minute_match:
        return max(20, min(180, round(float(minute_match.group(1)) * 60)))

    second_match = re.search(
        r"\b(\d{1,3})\s*(?:-|\s)?(?:seconds?|secs?)\b",
        normalized,
    )
    if second_match:
        return max(20, min(180, int(second_match.group(1))))

    if allow_plain_number:
        plain_match = re.search(r"\b\d{1,3}\b", normalized)
        if plain_match:
            return max(20, min(180, int(plain_match.group(0))))
    return None


def _answer_text(answers: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in answers:
            return _format_answer(answers[key])
    return ""


def _format_answer(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = ", ".join(part for item in value if (part := _format_answer(item)))
        return text if len(text) <= 400 else f"{text[:397].rstrip()}..."
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value).strip()
    return text if len(text) <= 400 else f"{text[:397].rstrip()}..."


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _contains_raw_answers(creative_brief: str, answers: dict[str, Any]) -> bool:
    if answers and str(answers) in creative_brief:
        return True
    return bool(re.search(r"\{\s*['\"][^'\"]+['\"]\s*:", creative_brief))


director = CreativeDirector()
