from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field


class AnalyticsSyncRequest(BaseModel):
    start_date: str = Field(
        default_factory=lambda: (date.today() - timedelta(days=365)).isoformat()
    )
    end_date: str | None = None
