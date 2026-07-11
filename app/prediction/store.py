from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.atlas.database import connect, migrate


def ensure_prediction_tables(root: Path) -> None:
    migrate(root)

    with connect(root) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_predictions (
                prediction_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                target_seconds INTEGER NOT NULL,
                hook_type TEXT NOT NULL,
                publish_day TEXT,
                publish_hour_utc INTEGER,
                predicted_views_low INTEGER NOT NULL,
                predicted_views_high INTEGER NOT NULL,
                predicted_retention REAL NOT NULL,
                predicted_subscribers_low INTEGER NOT NULL,
                predicted_subscribers_high INTEGER NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                actual_views INTEGER,
                actual_retention REAL,
                actual_subscribers_gained INTEGER,
                reviewed_at TEXT
            )
            """
        )
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_created
            ON performance_predictions(created_at DESC)
            """
        )


def save_prediction(root: Path, prediction: dict[str, Any]) -> None:
    ensure_prediction_tables(root)

    with connect(root) as db:
        db.execute(
            """
            INSERT INTO performance_predictions (
                prediction_id,
                created_at,
                topic,
                target_seconds,
                hook_type,
                publish_day,
                publish_hour_utc,
                predicted_views_low,
                predicted_views_high,
                predicted_retention,
                predicted_subscribers_low,
                predicted_subscribers_high,
                confidence,
                risk_level,
                evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction["prediction_id"],
                prediction["created_at"],
                prediction["topic"],
                prediction["target_seconds"],
                prediction["hook_type"],
                prediction.get("publish_day"),
                prediction.get("publish_hour_utc"),
                prediction["predicted_views_low"],
                prediction["predicted_views_high"],
                prediction["predicted_retention"],
                prediction["predicted_subscribers_low"],
                prediction["predicted_subscribers_high"],
                prediction["confidence"],
                prediction["risk_level"],
                json.dumps(prediction["evidence"], ensure_ascii=False),
            ),
        )


def review_prediction(
    root: Path,
    prediction_id: str,
    actual_views: int,
    actual_retention: float,
    actual_subscribers_gained: int,
    reviewed_at: str,
) -> dict[str, Any]:
    ensure_prediction_tables(root)

    with connect(root) as db:
        row = db.execute(
            """
            SELECT *
            FROM performance_predictions
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        ).fetchone()

        if row is None:
            raise FileNotFoundError(prediction_id)

        db.execute(
            """
            UPDATE performance_predictions
            SET
                actual_views = ?,
                actual_retention = ?,
                actual_subscribers_gained = ?,
                reviewed_at = ?
            WHERE prediction_id = ?
            """,
            (
                actual_views,
                actual_retention,
                actual_subscribers_gained,
                reviewed_at,
                prediction_id,
            ),
        )

    item = dict(row)
    item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
    return item


def list_predictions(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    ensure_prediction_tables(root)

    with connect(root) as db:
        rows = db.execute(
            """
            SELECT *
            FROM performance_predictions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()

    output = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
        output.append(item)
    return output
