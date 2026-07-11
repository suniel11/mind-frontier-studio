from __future__ import annotations

from pydantic import BaseModel, Field


class AgentBriefRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    target_seconds: int = Field(default=45, ge=20, le=90)


class StrategyRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)
