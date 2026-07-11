from pathlib import Path

from app.atlas_agents.producer_agent import run_producer_agent
from app.atlas_agents.strategy_agent import recommend_next_topics
from app.atlas_agents.thumbnail_agent import run_thumbnail_agent


def test_agents_empty_state(tmp_path: Path):
    producer = run_producer_agent(tmp_path, "comparison", 45)
    thumbnail = run_thumbnail_agent(tmp_path, "comparison")
    strategy = recommend_next_topics(tmp_path, 3)

    assert producer["recommended_runtime_seconds"] == 45
    assert "thumbnail_prompt" in thumbnail
    assert len(strategy["recommendations"]) == 3
