from __future__ import annotations

from fastapi import APIRouter

from app.atlas_agents.models import AgentBriefRequest, StrategyRequest
from app.atlas_agents.producer_agent import run_producer_agent
from app.atlas_agents.publishing_agent import run_publishing_agent
from app.atlas_agents.research_agent import run_research_agent
from app.atlas_agents.strategy_agent import recommend_next_topics
from app.atlas_agents.thumbnail_agent import run_thumbnail_agent
from app.core.settings import settings

router = APIRouter(prefix="/agents", tags=["Atlas Agents"])


@router.post("/research")
def research_agent(payload: AgentBriefRequest):
    return run_research_agent(settings.root, payload.topic)


@router.post("/producer")
def producer_agent(payload: AgentBriefRequest):
    return run_producer_agent(
        settings.root,
        payload.topic,
        payload.target_seconds,
    )


@router.post("/thumbnail")
def thumbnail_agent(payload: AgentBriefRequest):
    return run_thumbnail_agent(settings.root, payload.topic)


@router.get("/publishing")
def publishing_agent():
    return run_publishing_agent(settings.root)


@router.post("/strategy")
def strategy_agent(payload: StrategyRequest):
    return recommend_next_topics(settings.root, payload.count)
