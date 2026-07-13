from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

try:
    from app.production.specification import ProductionSpecification
except ImportError:  # Kept only for compatibility while older installations migrate.
    class ProductionSpecification(BaseModel):
        model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

        original_prompt: str = Field(min_length=3, max_length=3000)
        subject: str | None = Field(default=None, max_length=1000)
        target_seconds: int = Field(default=45, ge=20, le=180)
        aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"


JobStatus = Literal[
    "queued",
    "running",
    "cancelling",
    "complete",
    "failed",
    "cancelled",
]

SafeText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=3000),
]


class ProductionJobModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductionJobRequest(ProductionJobModel):
    production_specification: ProductionSpecification | None = None
    topic: SafeText | None = None
    target_seconds: int | None = Field(default=None, ge=20, le=180)

    @model_validator(mode="after")
    def require_one_input(self) -> ProductionJobRequest:
        if self.production_specification is None and self.topic is None:
            raise ValueError("Provide production_specification or topic.")
        if self.production_specification is not None and self.topic is not None:
            raise ValueError(
                "Provide production_specification or legacy topic fields, not both."
            )
        return self

    def resolved_specification(self) -> ProductionSpecification:
        if self.production_specification is not None:
            return self.production_specification

        topic = self.topic or ""
        values: dict[str, Any] = {
            "original_prompt": topic,
            "subject": topic,
            "target_seconds": self.target_seconds or 45,
        }
        return ProductionSpecification.model_validate(values)


class ProductionJobCreated(ProductionJobModel):
    job_id: str
    project_id: str
    status: Literal["queued"] = "queued"


class ProductionJobStatus(ProductionJobModel):
    job_id: str
    project_id: str
    status: JobStatus
    current_stage: str
    completed_stages: list[str]
    total_stages: int = Field(ge=1)
    progress_percent: float = Field(ge=0, le=100)
    warnings: list[str]
    error: str | None = None
    output_links: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    retry_count: int = Field(default=0, ge=0)


class ProductionJobAction(ProductionJobStatus):
    pass

