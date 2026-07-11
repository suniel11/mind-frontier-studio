from __future__ import annotations

from pydantic import BaseModel, Field


class VideoSyncRequest(BaseModel):
    mode: str = Field(default="incremental", pattern="^(incremental|full)$")
