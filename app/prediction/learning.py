from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.prediction.store import list_predictions, review_prediction


def record_actuals(
    root: Path,
    prediction_id: str,
    actual_views: int,
    actual_retention: float,
    actual_subscribers_gained: int,
) -> dict[str, Any]:
    prediction = review_prediction(
        root,
        prediction_id,
        actual_views,
        actual_retention,
        actual_subscribers_gained,
        datetime.now(timezone.utc).isoformat(),
    )

    predicted_mid_views = (
        int(prediction["predicted_views_low"])
        + int(prediction["predicted_views_high"])
    ) / 2
    predicted_mid_subscribers = (
        int(prediction["predicted_subscribers_low"])
        + int(prediction["predicted_subscribers_high"])
    ) / 2

    return {
        "prediction_id": prediction_id,
        "views_absolute_error": round(abs(actual_views - predicted_mid_views), 1),
        "views_percentage_error": round(
            abs(actual_views - predicted_mid_views)
            / max(1, actual_views)
            * 100,
            1,
        ),
        "retention_absolute_error": round(
            abs(actual_retention - float(prediction["predicted_retention"])),
            1,
        ),
        "subscribers_absolute_error": round(
            abs(actual_subscribers_gained - predicted_mid_subscribers),
            1,
        ),
    }


def calibration_report(root: Path) -> dict[str, Any]:
    predictions = [
        row for row in list_predictions(root, limit=200)
        if row.get("actual_views") is not None
    ]

    if not predictions:
        return {
            "reviewed_predictions": 0,
            "mean_views_percentage_error": None,
            "mean_retention_absolute_error": None,
            "mean_subscribers_absolute_error": None,
            "status": "insufficient_data",
        }

    view_errors = []
    retention_errors = []
    subscriber_errors = []

    for row in predictions:
        predicted_mid_views = (
            int(row["predicted_views_low"])
            + int(row["predicted_views_high"])
        ) / 2
        predicted_mid_subscribers = (
            int(row["predicted_subscribers_low"])
            + int(row["predicted_subscribers_high"])
        ) / 2

        actual_views = int(row["actual_views"])
        actual_retention = float(row["actual_retention"])
        actual_subscribers = int(row["actual_subscribers_gained"])

        view_errors.append(
            abs(actual_views - predicted_mid_views)
            / max(1, actual_views)
            * 100
        )
        retention_errors.append(
            abs(actual_retention - float(row["predicted_retention"]))
        )
        subscriber_errors.append(
            abs(actual_subscribers - predicted_mid_subscribers)
        )

    return {
        "reviewed_predictions": len(predictions),
        "mean_views_percentage_error": round(
            sum(view_errors) / len(view_errors),
            1,
        ),
        "mean_retention_absolute_error": round(
            sum(retention_errors) / len(retention_errors),
            1,
        ),
        "mean_subscribers_absolute_error": round(
            sum(subscriber_errors) / len(subscriber_errors),
            1,
        ),
        "status": "calibrating" if len(predictions) < 10 else "measured",
    }
