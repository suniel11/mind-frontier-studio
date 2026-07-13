from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from app.creative_director.models import ProductionBrief, QuestionResponse
from app.creative_director.prompts import BRIEF_SYSTEM_PROMPT, QUESTION_SYSTEM_PROMPT
from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import (
    creative_director_brief_validator,
    creative_director_questions_validator,
)
from app.model_router.stages import Stage
from app.services.openai_client import structured_response


DEFAULT_CREATIVE_DIRECTOR_MODEL = "gpt-5-mini"


class CreativeDirectorLLMError(RuntimeError):
    """A safe, provider-neutral Creative Director model error."""


class CreativeDirectorLLM:
    def __init__(self, client: OpenAI, model: str, *, use_router: bool = False) -> None:
        self._client = client
        self._model = model
        # ``use_router`` is False by default so a directly-constructed
        # instance (as tests do) keeps using ``model`` verbatim with no
        # cost-aware substitution -- only the real production path
        # (``from_environment``) opts into routing/baseline-fallback, since
        # only it knows which env-configured baseline to fall back to.
        self._use_router = use_router

    @classmethod
    def from_environment(cls) -> CreativeDirectorLLM | None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or "put_your" in api_key.casefold():
            return None

        model = (
            os.getenv("CREATIVE_DIRECTOR_MODEL", "").strip()
            or os.getenv("OPENAI_TEXT_MODEL", "").strip()
            or DEFAULT_CREATIVE_DIRECTOR_MODEL
        )
        return cls(
            OpenAI(api_key=api_key, timeout=45.0, max_retries=2),
            model,
            use_router=True,
        )

    def generate_questions(
        self,
        prompt: str,
        preferences: dict[str, Any] | None = None,
    ) -> QuestionResponse:
        input_text = prompt
        if preferences:
            input_text = json.dumps(
                {
                    "prompt": prompt,
                    "reusable_creator_preferences": preferences,
                    "instruction": (
                        "Treat these preferences as defaults and do not ask about them "
                        "unless this prompt clearly conflicts with them."
                    ),
                },
                ensure_ascii=False,
                allow_nan=False,
            )
        return self._parse(
            instructions=QUESTION_SYSTEM_PROMPT,
            input_text=input_text,
            response_model=QuestionResponse,
            stage=Stage.CREATIVE_DIRECTOR_QUESTIONS,
            validate=creative_director_questions_validator(),
        )

    def generate_brief(
        self,
        prompt: str,
        answers: dict[str, Any],
    ) -> ProductionBrief:
        input_text = json.dumps(
            {"prompt": prompt, "answers": answers},
            ensure_ascii=False,
            allow_nan=False,
        )
        return self._parse(
            instructions=BRIEF_SYSTEM_PROMPT,
            input_text=input_text,
            response_model=ProductionBrief,
            stage=Stage.CREATIVE_DIRECTOR_BRIEF,
            validate=creative_director_brief_validator(expected_answers=answers),
        )

    def _parse(self, *, instructions: str, input_text: str, response_model, stage: Stage, validate):
        try:
            if self._use_router:
                parsed = run_agent_stage(
                    stage,
                    instructions=instructions,
                    prompt=input_text,
                    schema=response_model,
                    validate=validate,
                    client=self._client,
                ).output
            else:
                parsed = structured_response(
                    instructions=instructions,
                    prompt=input_text,
                    schema=response_model,
                    model=self._model,
                    client=self._client,
                )
            return response_model.model_validate(parsed)
        except Exception as exc:
            raise CreativeDirectorLLMError(
                "Creative Director model generation failed."
            ) from exc
