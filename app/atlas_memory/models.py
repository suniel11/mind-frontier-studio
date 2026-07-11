from __future__ import annotations

from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=20, ge=1, le=100)
