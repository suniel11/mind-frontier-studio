from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from app.creative_director.models import ProductionBrief, QuestionResponse
from app.creative_director.prompts import BRIEF_SYSTEM_PROMPT, QUESTION_SYSTEM_PROMPT


DEFAULT_CREATIVE_DIRECTOR_MODEL = "gpt-5-mini"


class CreativeDirectorLLMError(RuntimeError):
    """A safe, provider-neutral Creative Director model error."""


class CreativeDirectorLLM:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

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
        )

    def _parse(self, *, instructions: str, input_text: str, response_model):
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=input_text,
                text_format=response_model,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise ValueError("The model returned no structured output.")
            return response_model.model_validate(parsed)
        except Exception as exc:
            raise CreativeDirectorLLMError(
                "Creative Director model generation failed."
            ) from exc
