from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

_NO_PROJECT = "_no_project"


@dataclass
class UsageRecord:
    """One text-model call. Deliberately holds no prompt text, no
    instructions, no API keys/headers -- only structural/numeric/label data
    (Phase 10: "Do not store... complete secrets... full sensitive
    prompts")."""

    stage: str
    profile: str
    attempted_model: str
    baseline_model: str
    final_model: str
    fallback_triggered: bool
    fallback_reason: str | None
    validation_passed: bool | None
    validation_reasons: list[str]
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    latency_seconds: float
    retry_count: int
    success: bool
    error_category: str | None
    project_id: str | None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_lock = Lock()
_records: dict[str, list[UsageRecord]] = {}


def record(project_id: str | None, entry: UsageRecord) -> None:
    key = project_id or _NO_PROJECT
    with _lock:
        _records.setdefault(key, []).append(entry)


def records_for(project_id: str | None) -> list[UsageRecord]:
    key = project_id or _NO_PROJECT
    with _lock:
        return list(_records.get(key, []))


def reset(project_id: str | None = None) -> None:
    """Test-only helper."""

    with _lock:
        if project_id is None:
            _records.clear()
        else:
            _records.pop(project_id, None)


def _aggregate(entries: list[UsageRecord]) -> dict:
    calls_by_model: dict[str, int] = {}
    calls_by_stage: dict[str, int] = {}
    tokens_by_model: dict[str, int] = {}
    tokens_by_stage: dict[str, int] = {}
    latency_by_stage: dict[str, list[float]] = {}
    accepted_lower_cost = 0
    baseline_fallbacks = 0
    failed_calls = 0
    retry_count = 0
    circuit_breaker_events = 0

    for entry in entries:
        calls_by_model[entry.final_model] = calls_by_model.get(entry.final_model, 0) + 1
        calls_by_stage[entry.stage] = calls_by_stage.get(entry.stage, 0) + 1
        total_tokens = (entry.input_tokens or 0) + (entry.output_tokens or 0)
        tokens_by_model[entry.final_model] = tokens_by_model.get(entry.final_model, 0) + total_tokens
        tokens_by_stage[entry.stage] = tokens_by_stage.get(entry.stage, 0) + total_tokens
        latency_by_stage.setdefault(entry.stage, []).append(entry.latency_seconds)
        if entry.fallback_triggered:
            baseline_fallbacks += 1
        elif entry.success and entry.final_model != entry.baseline_model:
            accepted_lower_cost += 1
        if not entry.success:
            failed_calls += 1
        retry_count += entry.retry_count
        if entry.fallback_reason == "circuit_breaker_open":
            circuit_breaker_events += 1

    latency_avg_by_stage = {
        stage: round(sum(values) / len(values), 4) for stage, values in latency_by_stage.items()
    }

    return {
        "total_calls": len(entries),
        "accepted_lower_cost_calls": accepted_lower_cost,
        "baseline_fallbacks": baseline_fallbacks,
        "calls_by_model": calls_by_model,
        "calls_by_stage": calls_by_stage,
        "tokens_by_model": tokens_by_model,
        "tokens_by_stage": tokens_by_stage,
        "latency_by_stage_seconds": latency_avg_by_stage,
        "failed_calls": failed_calls,
        "retry_count": retry_count,
        "circuit_breaker_events": circuit_breaker_events,
    }


def build_usage_document(project_id: str | None) -> dict:
    entries = records_for(project_id)
    return {
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calls": [asdict(entry) for entry in entries],
        "aggregate": _aggregate(entries),
    }


def save_model_usage(project_dir: Path, project_id: str | None) -> Path:
    document = build_usage_document(project_id)
    path = Path(project_dir) / "model-usage.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path
