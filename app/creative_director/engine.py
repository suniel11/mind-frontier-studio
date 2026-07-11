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


logger = logging.getLogger(__name__)


class CreativeDirectorServiceError(RuntimeError):
    """A safe error that may be translated by the HTTP layer."""


def fallback_questionnaire(prompt: str = "") -> QuestionResponse:
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
    return QuestionResponse(questions=questions)


class CreativeDirector:
    def __init__(
        self,
        llm_factory: Callable[[], CreativeDirectorLLM | None] | None = None,
    ) -> None:
        self._llm_factory = llm_factory

    def generate_questions(self, prompt: str) -> list[DirectorQuestion]:
        clean_prompt = CreativePrompt(prompt=prompt).prompt
        llm = self._get_llm()
        if llm is None:
            return fallback_questionnaire(clean_prompt).questions

        try:
            result = QuestionResponse.model_validate(
                llm.generate_questions(clean_prompt)
            )
            return result.questions
        except Exception as exc:
            self._log_fallback("question generation", exc)
            return fallback_questionnaire(clean_prompt).questions

    def build_brief(
        self,
        prompt: str,
        answers: dict[str, Any],
    ) -> ProductionBrief:
        validated = CreativeAnswers(prompt=prompt, answers=answers)
        llm = self._get_llm()
        if llm is not None:
            try:
                result = ProductionBrief.model_validate(
                    llm.generate_brief(validated.prompt, validated.answers)
                )
                if _contains_raw_answers(result.creative_brief, validated.answers):
                    raise ValueError("The generated brief serialized the answer mapping.")
                return result.model_copy(update={"topic": validated.prompt})
            except Exception as exc:
                self._log_fallback("brief generation", exc)

        return build_deterministic_brief(validated.prompt, validated.answers)

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
    return ProductionBrief(
        topic=prompt,
        target_seconds=target_seconds,
        hook_type=hook_type,
        creative_brief=creative_brief,
    )


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
