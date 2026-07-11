from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.producer_ai.engine import build_daily_brief
from app.producer_ai.health import calculate_channel_health
from app.producer_ai.calendar import build_weekly_calendar
from app.producer_ai.reviewer import assess_topic

router = APIRouter(prefix="/producer", tags=["AI Producer"])


class TopicAnalysisRequest(BaseModel):
    topic: str = Field(min_length=8, max_length=500)


@router.get("/brief")
def producer_brief():
    return build_daily_brief(settings.root)


@router.post("/analyze")
def analyze_topic(request: TopicAnalysisRequest):
    return assess_topic(settings.root, request.topic).model_dump()


@router.get("/calendar")
def producer_calendar():
    return {"calendar": build_weekly_calendar()}


@router.get("/health")
def producer_health():
    return calculate_channel_health(settings.root).model_dump()
