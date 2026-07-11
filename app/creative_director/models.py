from __future__ import annotations

import math
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


PromptText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=3000),
]
QuestionId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$",
    ),
]
QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]
OptionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
AnswerScalar: TypeAlias = str | int | float | bool | None
AnswerValue: TypeAlias = AnswerScalar | list[AnswerScalar]


class CreativeDirectorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreativePrompt(CreativeDirectorModel):
    prompt: PromptText


class CreativeAnswers(CreativeDirectorModel):
    prompt: PromptText
    answers: dict[QuestionId, AnswerValue] = Field(max_length=50)

    @field_validator("answers")
    @classmethod
    def validate_answer_values(
        cls,
        answers: dict[str, AnswerValue],
    ) -> dict[str, AnswerValue]:
        for value in answers.values():
            values = value if isinstance(value, list) else [value]
            if len(values) > 20:
                raise ValueError("An answer list may contain at most 20 values.")
            for item in values:
                if isinstance(item, str) and len(item) > 1000:
                    raise ValueError("Answer text may contain at most 1000 characters.")
                if isinstance(item, float) and not math.isfinite(item):
                    raise ValueError("Answers must contain finite numbers.")
        return answers


class DirectorQuestion(CreativeDirectorModel):
    id: QuestionId
    question: QuestionText
    type: Literal["single_choice"]
    options: list[OptionText] = Field(min_length=2, max_length=6)

    @field_validator("options")
    @classmethod
    def options_must_be_unique(cls, options: list[str]) -> list[str]:
        normalized = [option.casefold() for option in options]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Question options must be unique.")
        return options


class QuestionResponse(CreativeDirectorModel):
    questions: list[DirectorQuestion] = Field(max_length=5)

    @model_validator(mode="after")
    def question_ids_must_be_unique(self) -> QuestionResponse:
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question IDs must be unique.")
        return self


class ProductionBrief(CreativeDirectorModel):
    topic: PromptText
    target_seconds: int = Field(ge=20, le=180)
    hook_type: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    ]
    creative_brief: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=20, max_length=12000),
    ]
