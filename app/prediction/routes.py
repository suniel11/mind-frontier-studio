from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.prediction.engine import predict_performance
from app.prediction.learning import calibration_report, record_actuals
from app.prediction.models import (
    PredictionRequest,
    PredictionReviewRequest,
)
from app.prediction.store import list_predictions

router = APIRouter(prefix="/prediction", tags=["Prediction Engine"])


@router.post("/forecast")
def prediction_forecast(payload: PredictionRequest):
    return predict_performance(
        settings.root,
        payload.topic,
        payload.target_seconds,
        payload.hook_type,
        payload.publish_day,
        payload.publish_hour_utc,
    )


@router.post("/review")
def prediction_review(payload: PredictionReviewRequest):
    try:
        return record_actuals(
            settings.root,
            payload.prediction_id,
            payload.actual_views,
            payload.actual_retention,
            payload.actual_subscribers_gained,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Prediction not found.")


@router.get("/history")
def prediction_history(limit: int = 50):
    return {"predictions": list_predictions(settings.root, limit)}


@router.get("/calibration")
def prediction_calibration():
    return calibration_report(settings.root)
