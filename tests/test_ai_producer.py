from pathlib import Path

from app.producer_ai.reviewer import assess_topic


def test_topic_assessment(tmp_path: Path):
    assessment = assess_topic(
        tmp_path,
        "Why constant comparison quietly damages your sense of self worth",
    )
    assert assessment.overall_score >= 60
    assert assessment.verdict in {
        "MAKE IT",
        "GOOD WITH REFINEMENT",
        "REWRITE BEFORE PRODUCTION",
        "SKIP",
    }
