from __future__ import annotations

from pydantic import BaseModel, Field


class ApolloQueueRequest(BaseModel):
    objective: str = Field(min_length=8, max_length=500)
    count: int = Field(default=5, ge=1, le=10)
    target_seconds: int = Field(default=45, ge=20, le=60)


class ApolloRunRequest(BaseModel):
    max_items: int = Field(default=1, ge=1, le=10)
