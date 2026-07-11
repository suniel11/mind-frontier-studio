from __future__ import annotations

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    target_seconds: int = Field(default=45, ge=20, le=90)
    hook_type: str = Field(
        default="direct contradiction",
        max_length=80,
    )
    publish_day: str | None = Field(default=None, max_length=20)
    publish_hour_utc: int | None = Field(default=None, ge=0, le=23)


class PredictionReviewRequest(BaseModel):
    prediction_id: str = Field(min_length=5, max_length=100)
    actual_views: int = Field(ge=0)
    actual_retention: float = Field(ge=0, le=1000)
    actual_subscribers_gained: int = Field(ge=0)
