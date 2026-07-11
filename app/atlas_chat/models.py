from __future__ import annotations

from pydantic import BaseModel, Field


class AtlasChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=100)


class AtlasChatClearRequest(BaseModel):
    conversation_id: str = Field(min_length=5, max_length=100)
