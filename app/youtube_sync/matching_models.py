from __future__ import annotations

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    video_id: str = Field(min_length=3, max_length=100)
    project_id: str = Field(min_length=1, max_length=180)


class AutoMatchRequest(BaseModel):
    threshold: int = Field(default=85, ge=60, le=100)
