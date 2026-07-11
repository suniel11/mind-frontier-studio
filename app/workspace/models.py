from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    target_seconds: int = Field(default=45, ge=20, le=90)
    hook_type: str = Field(default="direct contradiction", max_length=80)


class WorkspaceSaveRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    target_seconds: int = Field(default=45, ge=20, le=90)
    hook_type: str = Field(default="direct contradiction", max_length=80)
    notes: str = Field(default="", max_length=5000)
