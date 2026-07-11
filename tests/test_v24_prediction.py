from pathlib import Path

from app.prediction.engine import predict_performance
from app.prediction.learning import calibration_report, record_actuals


def test_prediction_empty_state(tmp_path: Path):
    result = predict_performance(
        tmp_path,
        topic="comparison",
        target_seconds=45,
        hook_type="question",
    )

    assert result["predicted_views_low"] >= 0
    assert result["predicted_views_high"] >= result["predicted_views_low"]
    assert 0 <= result["confidence"] <= 1


def test_prediction_review(tmp_path: Path):
    result = predict_performance(
        tmp_path,
        topic="identity",
        target_seconds=45,
        hook_type="story",
    )

    review = record_actuals(
        tmp_path,
        result["prediction_id"],
        actual_views=1000,
        actual_retention=70,
        actual_subscribers_gained=5,
    )

    assert "views_percentage_error" in review
    assert calibration_report(tmp_path)["reviewed_predictions"] == 1
