"""Canonical creator intent shared by every production entry point.

The legacy application historically passed only ``topic`` and
``target_seconds``.  ``ProductionSpecification`` is deliberately additive so
old callers can be converted without losing their existing behavior while new
callers retain the decisions made with the Creative Director.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


ShortDirection = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
LongDirection = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=3000),
]
AspectRatio = Literal["9:16", "16:9", "1:1", "4:5"]


class ProductionSpecification(BaseModel):
    """Validated, domain-agnostic instructions for one production."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    original_prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=3000),
    ]
    target_seconds: int = Field(default=45, ge=20, le=180)
    creative_objective: LongDirection | None = None
    subject: LongDirection | None = None
    audience: ShortDirection | None = None
    output_format: ShortDirection | None = "short-form video"
    aspect_ratio: AspectRatio = "9:16"
    tone: ShortDirection | None = None
    narration_style: ShortDirection | None = None
    visual_style: ShortDirection | None = None
    pacing: ShortDirection | None = None
    hook_strategy: ShortDirection | None = None
    narrative_structure: LongDirection | None = None
    ending_direction: ShortDirection | None = None
    music_direction: ShortDirection | None = None
    caption_style: ShortDirection | None = None
    accuracy_level: ShortDirection | None = None
    protagonist_direction: LongDirection | None = None
    production_constraints: list[ShortDirection] = Field(default_factory=list, max_length=20)
    negative_constraints: list[ShortDirection] = Field(default_factory=list, max_length=20)
    channel_id: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=100,
            pattern=r"^[A-Za-z0-9_.-]+$",
        ),
    ] | None = None
    source_brief_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=12000),
    ] | None = None

    @field_validator("aspect_ratio", mode="before")
    @classmethod
    def normalize_aspect_ratio(cls, value: object) -> object:
        if value is None or value == "":
            return "9:16"
        text = str(value).strip().casefold().replace(" ", "")
        aliases = {
            "vertical": "9:16",
            "portrait": "9:16",
            "vertical(9:16)": "9:16",
            "landscape": "16:9",
            "widescreen": "16:9",
            "landscape(16:9)": "16:9",
            "square": "1:1",
            "square(1:1)": "1:1",
            "portrait(4:5)": "4:5",
        }
        return aliases.get(text, text)

    @field_validator("production_constraints", "negative_constraints", mode="before")
    @classmethod
    def normalize_constraint_lists(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in re.split(r"[;\n]", value) if part.strip()]
            return parts or [value]
        return value

    @property
    def effective_subject(self) -> str:
        return self.subject or self.original_prompt

    @property
    def requires_character(self) -> bool:
        if not self.protagonist_direction:
            return False
        normalized = self.protagonist_direction.casefold()
        return normalized not in {
            "none",
            "no",
            "no protagonist",
            "no recurring character",
            "not required",
        }

    @classmethod
    def from_legacy(
        cls,
        topic: str,
        target_seconds: int = 45,
    ) -> "ProductionSpecification":
        """Convert the original public request contract into the canonical form."""

        return cls(
            original_prompt=topic,
            subject=topic,
            target_seconds=target_seconds,
        )

