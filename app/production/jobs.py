from __future__ import annotations

import inspect
import json
import logging
import re
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.production.models import (
    ProductionJobCreated,
    ProductionJobStatus,
    ProductionSpecification,
)
from app.stability.migrations import migrate


LOGGER = logging.getLogger(__name__)
JOB_TYPE = "production"
JOB_ID_PATTERN = re.compile(r"^job-[a-f0-9]{12}$")
PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,119}$")

PRODUCTION_STAGES: tuple[str, ...] = (
    "preflight",
    "research",
    "script",
    "producer_review",
    "character",
    "storyboard",
    "narrative_beats",
    "director",
    "visual_storytelling",
    "cinema_direction",
    "prompt_compilation",
    "seo",
    "storage",
    "voice_generation",
    "image_generation",
    "render",
    "quality_inspection",
    "thumbnail",
    "release_package",
    "publish_package",
    "memory",
    "complete",
)

_STAGE_ALIASES = {
    "producer_preflight": "preflight",
    "project_storage": "storage",
    "studio_memory": "memory",
    "final_save": "complete",
}
_TERMINAL_STATUSES = {"complete", "failed", "cancelled"}


class ProductionJobNotFound(LookupError):
    pass


class ProductionJobConflict(RuntimeError):
    pass


class ProductionCancelled(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_load(value: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback
    return parsed


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (slug[:48].strip("-") or "untitled")


def _new_project_id(specification: ProductionSpecification) -> str:
    values = specification.model_dump(mode="json")
    subject = str(
        values.get("subject")
        or values.get("original_prompt")
        or "untitled"
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{_safe_slug(subject)}-{uuid.uuid4().hex[:8]}"[:120].rstrip("-")


def _normalize_stage(stage: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(stage).casefold()).strip("_")
    normalized = _STAGE_ALIASES.get(normalized, normalized)
    return normalized if normalized in PRODUCTION_STAGES else ""


def _public_error(stage: str) -> str:
    label = stage.replace("_", " ") if stage else "production"
    return f"Production failed during {label}. You can retry the job."


class ProductionJobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        migrate(self.root)
        self.database = self.root / "studio_memory" / "atlas.db"

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 30000")
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def create(self, specification: ProductionSpecification) -> ProductionJobCreated:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        project_id = _new_project_id(specification)
        now = _now()
        payload = {
            "production_specification": specification.model_dump(mode="json")
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO background_jobs (
                    job_id, job_type, status, progress,
                    created_at, updated_at, payload_json,
                    project_id, current_stage, completed_stages_json,
                    total_stages, warnings_json, cancel_requested, retry_count
                )
                VALUES (?, ?, 'queued', 0, ?, ?, ?, ?, 'queued', '[]', ?, '[]', 0, 0)
                """,
                (
                    job_id,
                    JOB_TYPE,
                    now,
                    now,
                    json.dumps(payload, ensure_ascii=False, allow_nan=False),
                    project_id,
                    len(PRODUCTION_STAGES),
                ),
            )
        return ProductionJobCreated(job_id=job_id, project_id=project_id)

    def raw(self, job_id: str) -> dict[str, Any] | None:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM background_jobs WHERE job_id = ? AND job_type = ?",
                (job_id, JOB_TYPE),
            ).fetchone()
        return dict(row) if row is not None else None

    def public(self, job_id: str) -> ProductionJobStatus | None:
        row = self.raw(job_id)
        if row is None:
            return None
        completed = _safe_json_load(row.get("completed_stages_json"), [])
        warnings = _safe_json_load(row.get("warnings_json"), [])
        result = _safe_json_load(row.get("result_json"), {})
        if not isinstance(completed, list):
            completed = []
        if not isinstance(warnings, list):
            warnings = []
        if not isinstance(result, dict):
            result = {}
        links = result.get("output_links", {})
        if not isinstance(links, dict):
            links = {}
        links = {
            str(key): str(value)
            for key, value in links.items()
            if isinstance(key, str)
            and isinstance(value, str)
            and value.startswith(("/projects/", "https://www.youtube.com/"))
        }
        error = str(row.get("error") or "").strip() or None
        return ProductionJobStatus(
            job_id=str(row["job_id"]),
            project_id=str(row.get("project_id") or ""),
            status=str(row["status"]),
            current_stage=str(row.get("current_stage") or "queued"),
            completed_stages=[str(item) for item in completed if isinstance(item, str)],
            total_stages=max(1, int(row.get("total_stages") or len(PRODUCTION_STAGES))),
            progress_percent=float(row.get("progress") or 0),
            warnings=[str(item)[:500] for item in warnings if isinstance(item, str)][:50],
            error=error,
            output_links=links,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            retry_count=max(0, int(row.get("retry_count") or 0)),
        )

    def mark_running(self, job_id: str) -> bool:
        now = _now()
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE background_jobs
                SET status = 'running', updated_at = ?,
                    started_at = COALESCE(started_at, ?), finished_at = NULL
                WHERE job_id = ? AND job_type = ?
                  AND status = 'queued' AND cancel_requested = 0
                """,
                (now, now, job_id, JOB_TYPE),
            )
        return cursor.rowcount == 1

    def record_stage(self, job_id: str, stage: str, status: str) -> None:
        stage = _normalize_stage(stage)
        status = str(status).casefold().strip()
        if not stage or status not in {"started", "complete", "failed", "skipped"}:
            return
        with self._connect() as db:
            row = db.execute(
                """
                SELECT completed_stages_json, total_stages, cancel_requested
                FROM background_jobs
                WHERE job_id = ? AND job_type = ?
                """,
                (job_id, JOB_TYPE),
            ).fetchone()
            if row is None:
                return
            completed = _safe_json_load(row["completed_stages_json"], [])
            if not isinstance(completed, list):
                completed = []
            completed = [item for item in completed if item in PRODUCTION_STAGES]
            if status in {"complete", "skipped"} and stage not in completed:
                completed.append(stage)
                completed.sort(key=PRODUCTION_STAGES.index)
            total = max(1, int(row["total_stages"] or len(PRODUCTION_STAGES)))
            progress = min(99.0, round(len(completed) / total * 100, 2))
            db.execute(
                """
                UPDATE background_jobs
                SET current_stage = ?, completed_stages_json = ?,
                    progress = ?, updated_at = ?
                WHERE job_id = ? AND job_type = ?
                """,
                (
                    stage,
                    json.dumps(completed),
                    progress,
                    _now(),
                    job_id,
                    JOB_TYPE,
                ),
            )

    def add_warning(self, job_id: str, warning: str) -> None:
        clean = " ".join(str(warning).split())[:500]
        if not clean:
            return
        with self._connect() as db:
            row = db.execute(
                "SELECT warnings_json FROM background_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            warnings = _safe_json_load(row["warnings_json"], [])
            if not isinstance(warnings, list):
                warnings = []
            if clean not in warnings:
                warnings.append(clean)
            db.execute(
                """
                UPDATE background_jobs
                SET warnings_json = ?, updated_at = ?
                WHERE job_id = ? AND job_type = ?
                """,
                (json.dumps(warnings[-50:]), _now(), job_id, JOB_TYPE),
            )

    def cancellation_requested(self, job_id: str) -> bool:
        row = self.raw(job_id)
        return row is None or bool(row.get("cancel_requested"))

    def request_cancel(self, job_id: str) -> ProductionJobStatus:
        row = self.raw(job_id)
        if row is None:
            raise ProductionJobNotFound(job_id)
        status = str(row["status"])
        if status == "cancelled":
            result = self.public(job_id)
            assert result is not None
            return result
        if status in {"complete", "failed"}:
            raise ProductionJobConflict(f"A {status} job cannot be cancelled.")

        now = _now()
        with self._connect() as db:
            if status == "queued":
                db.execute(
                    """
                    UPDATE background_jobs
                    SET status = 'cancelled', cancel_requested = 1,
                        current_stage = 'cancelled', updated_at = ?, finished_at = ?
                    WHERE job_id = ? AND job_type = ?
                    """,
                    (now, now, job_id, JOB_TYPE),
                )
            else:
                db.execute(
                    """
                    UPDATE background_jobs
                    SET status = 'cancelling', cancel_requested = 1, updated_at = ?
                    WHERE job_id = ? AND job_type = ?
                    """,
                    (now, job_id, JOB_TYPE),
                )
        result = self.public(job_id)
        assert result is not None
        return result

    def retry(self, job_id: str) -> ProductionJobStatus:
        row = self.raw(job_id)
        if row is None:
            raise ProductionJobNotFound(job_id)
        if row["status"] not in {"failed", "cancelled"}:
            raise ProductionJobConflict("Only failed or cancelled jobs can be retried.")

        completed = _safe_json_load(row.get("completed_stages_json"), [])
        if not isinstance(completed, list):
            completed = []
        completed = [item for item in completed if item in PRODUCTION_STAGES]
        next_stage = next(
            (stage for stage in PRODUCTION_STAGES if stage not in completed),
            "preflight",
        )
        progress = min(99.0, round(len(completed) / len(PRODUCTION_STAGES) * 100, 2))
        with self._connect() as db:
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'queued', current_stage = ?, progress = ?,
                    cancel_requested = 0, error = '', result_json = '{}',
                    retry_count = retry_count + 1, updated_at = ?,
                    started_at = NULL, finished_at = NULL
                WHERE job_id = ? AND job_type = ?
                """,
                (next_stage, progress, _now(), job_id, JOB_TYPE),
            )
        result = self.public(job_id)
        assert result is not None
        return result

    def mark_cancelled(self, job_id: str) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'cancelled', current_stage = 'cancelled',
                    cancel_requested = 1, updated_at = ?, finished_at = ?
                WHERE job_id = ? AND job_type = ?
                """,
                (now, now, job_id, JOB_TYPE),
            )

    def mark_failed(self, job_id: str, stage: str) -> None:
        safe_stage = _normalize_stage(stage) or "production"
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'failed', current_stage = ?, error = ?,
                    updated_at = ?, finished_at = ?
                WHERE job_id = ? AND job_type = ?
                """,
                (safe_stage, _public_error(safe_stage), now, now, job_id, JOB_TYPE),
            )

    def mark_complete(self, job_id: str, output_links: dict[str, str]) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'complete', current_stage = 'complete', progress = 100,
                    completed_stages_json = ?, error = '', result_json = ?,
                    updated_at = ?, finished_at = ?
                WHERE job_id = ? AND job_type = ?
                """,
                (
                    json.dumps(list(PRODUCTION_STAGES)),
                    json.dumps({"output_links": output_links}),
                    now,
                    now,
                    job_id,
                    JOB_TYPE,
                ),
            )

    def payload_specification(self, job_id: str) -> ProductionSpecification:
        row = self.raw(job_id)
        if row is None:
            raise ProductionJobNotFound(job_id)
        payload = _safe_json_load(row.get("payload_json"), {})
        if not isinstance(payload, dict):
            raise ValueError("Stored job payload is invalid.")
        return ProductionSpecification.model_validate(
            payload.get("production_specification", {})
        )

    def recover(self) -> list[str]:
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'cancelled', current_stage = 'cancelled',
                    updated_at = ?, finished_at = ?
                WHERE job_type = ? AND status IN ('running', 'cancelling')
                  AND cancel_requested = 1
                """,
                (now, now, JOB_TYPE),
            )
            db.execute(
                """
                UPDATE background_jobs
                SET status = 'queued', updated_at = ?, started_at = NULL,
                    finished_at = NULL
                WHERE job_type = ? AND status IN ('running', 'cancelling')
                  AND cancel_requested = 0
                """,
                (now, JOB_TYPE),
            )
            rows = db.execute(
                """
                SELECT job_id FROM background_jobs
                WHERE job_type = ? AND status = 'queued' AND cancel_requested = 0
                ORDER BY created_at
                """,
                (JOB_TYPE,),
            ).fetchall()
        return [str(row["job_id"]) for row in rows]

    def job_for_project(self, project_id: str) -> ProductionJobStatus | None:
        if not PROJECT_ID_PATTERN.fullmatch(project_id):
            return None
        with self._connect() as db:
            row = db.execute(
                """
                SELECT job_id FROM background_jobs
                WHERE job_type = ? AND project_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (JOB_TYPE, project_id),
            ).fetchone()
        return self.public(str(row["job_id"])) if row is not None else None


PipelineCallable = Callable[..., Any]


class ProductionJobRunner:
    def __init__(
        self,
        root: Path,
        *,
        pipeline: PipelineCallable | None = None,
    ):
        self.root = root.resolve()
        self.store = ProductionJobStore(self.root)
        self._pipeline = pipeline or self._default_pipeline
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="production-job",
        )
        self._lock = threading.Lock()
        self._active: set[str] = set()
        self._resubmit: set[str] = set()

    def create(self, specification: ProductionSpecification) -> ProductionJobCreated:
        created = self.store.create(specification)
        self.submit(created.job_id)
        return created

    def get(self, job_id: str) -> ProductionJobStatus:
        job = self.store.public(job_id)
        if job is None:
            raise ProductionJobNotFound(job_id)
        return job

    def retry(self, job_id: str) -> ProductionJobStatus:
        job = self.store.retry(job_id)
        self.submit(job_id, resubmit_if_active=True)
        return job

    def cancel(self, job_id: str) -> ProductionJobStatus:
        return self.store.request_cancel(job_id)

    def recover(self) -> int:
        job_ids = self.store.recover()
        for job_id in job_ids:
            self.submit(job_id)
        return len(job_ids)

    def submit(self, job_id: str, *, resubmit_if_active: bool = False) -> None:
        with self._lock:
            if job_id in self._active:
                if resubmit_if_active:
                    self._resubmit.add(job_id)
                return
            self._active.add(job_id)
        future = self._executor.submit(self._worker, job_id)
        future.add_done_callback(lambda _future: self._finished(job_id))

    def _finished(self, job_id: str) -> None:
        should_resubmit = False
        with self._lock:
            self._active.discard(job_id)
            if job_id in self._resubmit:
                self._resubmit.discard(job_id)
                should_resubmit = True
        if should_resubmit:
            self.submit(job_id)

    def _worker(self, job_id: str) -> None:
        if not self.store.mark_running(job_id):
            return
        current_stage = "preflight"

        def progress_callback(stage: str, status: str) -> None:
            nonlocal current_stage
            normalized = _normalize_stage(stage)
            if normalized:
                current_stage = normalized
            self.store.record_stage(job_id, stage, status)

        def cancellation_check() -> bool:
            return self.store.cancellation_requested(job_id)

        try:
            specification = self.store.payload_specification(job_id)
            job = self.store.public(job_id)
            if job is None:
                return
            if cancellation_check():
                raise ProductionCancelled()
            result = self._invoke_pipeline(
                specification,
                project_id=job.project_id,
                progress_callback=progress_callback,
                cancellation_check=cancellation_check,
            )
            if cancellation_check():
                raise ProductionCancelled()
            self.store.mark_complete(
                job_id,
                self._output_links(job.project_id, result),
            )
        except ProductionCancelled:
            self.store.mark_cancelled(job_id)
        except Exception as exc:
            if cancellation_check() or type(exc).__name__ in {
                "PipelineCancelledError",
                "CancelledError",
            }:
                self.store.mark_cancelled(job_id)
            else:
                self.store.mark_failed(job_id, current_stage)
                LOGGER.error(
                    "Production job %s failed during %s (%s).",
                    job_id,
                    current_stage,
                    type(exc).__name__,
                )

    def _invoke_pipeline(
        self,
        specification: ProductionSpecification,
        *,
        project_id: str,
        progress_callback: Callable[[str, str], None],
        cancellation_check: Callable[[], bool],
    ) -> Any:
        from app.models import ProjectRequest

        values = specification.model_dump(mode="python")
        topic = str(values.get("original_prompt") or values.get("subject") or "")
        request_values: dict[str, Any] = {
            "topic": topic,
            "target_seconds": int(values.get("target_seconds") or 45),
        }
        if "production_specification" in ProjectRequest.model_fields:
            request_values["production_specification"] = specification
        request = ProjectRequest.model_validate(request_values)

        parameters = inspect.signature(self._pipeline).parameters
        keyword_arguments: dict[str, Any] = {}
        if "project_id" in parameters:
            keyword_arguments["project_id"] = project_id
        if "progress_callback" in parameters:
            keyword_arguments["progress_callback"] = progress_callback
        if "cancellation_check" in parameters:
            keyword_arguments["cancellation_check"] = cancellation_check
        return self._pipeline(request, **keyword_arguments)

    @staticmethod
    def _default_pipeline(request, **kwargs):
        from app.orchestration.project_pipeline import create_project_pipeline

        return create_project_pipeline(request, **kwargs)

    def _output_links(self, project_id: str, result: Any) -> dict[str, str]:
        project_dir = self.root / "projects" / project_id
        prefix = f"/projects/{project_id}"
        links: dict[str, str] = {}
        result_values = (
            result.model_dump(mode="json")
            if hasattr(result, "model_dump")
            else result
            if isinstance(result, dict)
            else {}
        )
        video_url = result_values.get("video_url") if isinstance(result_values, dict) else None
        if (
            isinstance(video_url, str)
            and video_url.startswith(f"{prefix}/")
            and ".." not in video_url
        ):
            links["video"] = video_url

        candidates = {
            "video": "mind-frontier-short.mp4",
            "thumbnail": "thumbnail.jpg",
            "release_package": "release-package.json",
            "publish_package": "publish-package.json",
            "project": "project.json",
        }
        for key, filename in candidates.items():
            if (project_dir / filename).is_file():
                links[key] = f"{prefix}/{filename}"
        return links

    def shutdown(self, *, wait: bool = False) -> None:
        with self._lock:
            active = list(self._active)
        for job_id in active:
            try:
                self.store.request_cancel(job_id)
            except (ProductionJobNotFound, ProductionJobConflict):
                pass
        self._executor.shutdown(wait=wait, cancel_futures=True)


_RUNNERS: dict[Path, ProductionJobRunner] = {}
_RUNNERS_LOCK = threading.Lock()


def get_production_job_runner(root: Path) -> ProductionJobRunner:
    key = root.resolve()
    with _RUNNERS_LOCK:
        runner = _RUNNERS.get(key)
        if runner is None:
            runner = ProductionJobRunner(key)
            _RUNNERS[key] = runner
        return runner


def shutdown_production_job_runner(root: Path, *, wait: bool = False) -> None:
    key = root.resolve()
    with _RUNNERS_LOCK:
        runner = _RUNNERS.pop(key, None)
    if runner is not None:
        runner.shutdown(wait=wait)

