from __future__ import annotations

import threading
from dataclasses import dataclass, field

from app.model_router.stages import Stage

_NO_PROJECT = "_no_project"


@dataclass
class _BreakerState:
    failure_count: int = 0
    tripped: bool = False
    reasons: list[str] = field(default_factory=list)


_lock = threading.Lock()
# project_id (or _NO_PROJECT for calls made outside a tracked project, e.g.
# Creative Director question/brief generation before a project exists) ->
# stage -> breaker state.
_state: dict[str, dict[Stage, _BreakerState]] = {}


def _bucket(project_id: str | None) -> dict[Stage, _BreakerState]:
    return _state.setdefault(project_id or _NO_PROJECT, {})


def record_failure(
    stage: Stage,
    *,
    project_id: str | None = None,
    threshold: int = 3,
    reason: str = "",
) -> bool:
    """Record one lower-cost quality/schema failure for a stage.

    Scoped to ``project_id`` when given (Phase 8: "for the remainder of the
    current project... do not disable lower-cost models globally for
    unrelated stages"). Calls made with no project context (Creative
    Director question/brief generation, which happens before a project
    exists) share a process-level bucket, which is an explicitly allowed
    option ("optionally persist the stage disablement for the current
    process/session").

    Returns ``True`` if this failure trips the breaker for the stage.
    """

    stage = Stage(stage)
    with _lock:
        bucket = _bucket(project_id)
        state = bucket.setdefault(stage, _BreakerState())
        state.failure_count += 1
        if reason:
            state.reasons.append(reason)
        if state.failure_count >= threshold:
            state.tripped = True
        return state.tripped


def is_disabled(stage: Stage, *, project_id: str | None = None) -> bool:
    stage = Stage(stage)
    with _lock:
        state = _state.get(project_id or _NO_PROJECT, {}).get(stage)
        return bool(state and state.tripped)


def status(stage: Stage, *, project_id: str | None = None) -> dict:
    stage = Stage(stage)
    with _lock:
        state = _state.get(project_id or _NO_PROJECT, {}).get(stage) or _BreakerState()
        return {
            "stage": stage.value,
            "project_id": project_id,
            "failure_count": state.failure_count,
            "tripped": state.tripped,
            "reasons": list(state.reasons),
        }


def all_status(*, project_id: str | None = None) -> list[dict]:
    with _lock:
        bucket = dict(_state.get(project_id or _NO_PROJECT, {}))
    return [
        {
            "stage": stage.value,
            "project_id": project_id,
            "failure_count": state.failure_count,
            "tripped": state.tripped,
            "reasons": list(state.reasons),
        }
        for stage, state in bucket.items()
    ]


def reset_all() -> None:
    """Test-only helper to clear every circuit-breaker bucket."""

    with _lock:
        _state.clear()
