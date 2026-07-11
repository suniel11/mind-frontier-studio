from __future__ import annotations

from pydantic import BaseModel, Field


class OrionPlanRequest(BaseModel):
    objective: str = Field(min_length=8, max_length=500)
    count: int = Field(default=3, ge=1, le=5)
    target_seconds: int = Field(default=45, ge=20, le=60)


class OrionExecuteRequest(BaseModel):
    item_index: int = Field(default=0, ge=0, le=4)
