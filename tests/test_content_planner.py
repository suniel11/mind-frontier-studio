from app.planning.planner import get_recommendations


def test_content_planner_returns_ranked_ideas():
    ideas = get_recommendations(limit=5)
    assert len(ideas) == 5
    assert all(idea.overall_score >= 80 for idea in ideas)
    assert ideas[0].overall_score >= ideas[-1].overall_score
