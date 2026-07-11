from __future__ import annotations

from pydantic import BaseModel, Field


class YouTubeMetricInput(BaseModel):
    project_id: str = Field(min_length=1, max_length=180)
    published_at: str | None = None
    channel: str = Field(default="Mind Frontier", max_length=100)
    youtube_video_id: str | None = Field(default=None, max_length=100)
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    subscribers_gained: int = Field(default=0, ge=0)
    watch_time_hours: float = Field(default=0, ge=0)
    average_view_duration_seconds: float = Field(default=0, ge=0)
    average_percentage_viewed: float = Field(default=0, ge=0, le=1000)
    viewed_percentage: float = Field(default=0, ge=0, le=100)
    swiped_away_percentage: float = Field(default=0, ge=0, le=100)
    impressions: int = Field(default=0, ge=0)
    click_through_rate: float = Field(default=0, ge=0, le=100)


class ProjectStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|ready|published|archived)$")
