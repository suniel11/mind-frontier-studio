from __future__ import annotations

import json
import logging
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


LOGGER = logging.getLogger("mind_frontier.pipeline")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"{stage}: {message}")


class PipelineTelemetry:
    def __init__(self, root: Path, project_id: str):
        self.root = root
        self.project_id = project_id
        self.started_at = _now()
        self.started_monotonic = time.perf_counter()
        self.events: list[dict[str, Any]] = []

        self.logs_dir = root / "studio_memory" / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"{project_id}.jsonl"

    def record(
        self,
        stage: str,
        status: str,
        duration_seconds: float = 0.0,
        detail: str = "",
        error: str = "",
    ) -> None:
        event = {
            "project_id": self.project_id,
            "stage": stage,
            "status": status,
            "timestamp": _now(),
            "duration_seconds": round(duration_seconds, 3),
            "detail": detail,
            "error": error,
        }
        self.events.append(event)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        self.record(name, "started")
        try:
            yield
        except Exception as exc:
            duration = time.perf_counter() - started
            trace = traceback.format_exc()
            self.record(
                name,
                "failed",
                duration_seconds=duration,
                error=str(exc),
                detail=trace[-5000:],
            )
            LOGGER.exception("Pipeline stage failed: %s", name)
            raise PipelineStageError(name, str(exc)) from exc
        else:
            self.record(
                name,
                "complete",
                duration_seconds=time.perf_counter() - started,
            )

    def finish(self, project_dir: Path | None, success: bool) -> dict[str, Any]:
        report = {
            "project_id": self.project_id,
            "started_at": self.started_at,
            "finished_at": _now(),
            "success": success,
            "total_duration_seconds": round(
                time.perf_counter() - self.started_monotonic,
                3,
            ),
            "events": self.events,
        }

        destination = (
            project_dir / "pipeline-report.json"
            if project_dir is not None and project_dir.exists()
            else self.logs_dir / f"{self.project_id}-report.json"
        )
        destination.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        return report
