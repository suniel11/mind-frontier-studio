from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

from app.model_router.config import load_router_config


@dataclass
class ProjectFallbackState:
    """Phase 11 project-level reversion: once ``fallback_count`` reaches
    ``threshold`` within a single production run, the remainder of that
    project is forced onto baseline models for every stage, regardless of
    profile."""

    project_id: str
    threshold: int
    fallback_count: int = 0
    forced_baseline: bool = False
    events: list[dict] = field(default_factory=list)


_current: "contextvars.ContextVar[ProjectFallbackState | None]" = contextvars.ContextVar(
    "model_router_project_state", default=None
)


def start_project(project_id: str) -> ProjectFallbackState:
    """Begin tracking project-level fallbacks for one pipeline run.

    Uses a ``contextvars.ContextVar`` so the active project is implicitly
    available to the router/executor for the duration of this run without
    threading a project-id argument through every agent function signature
    (research.run, script.run, storyboard.run, character.run, seo.run all
    keep their existing signatures unchanged).
    """

    cfg = load_router_config()
    state = ProjectFallbackState(project_id=project_id, threshold=cfg.project_fallback_threshold)
    _current.set(state)
    return state


def current() -> ProjectFallbackState | None:
    return _current.get()


def record_fallback(stage, reason: str) -> None:
    state = _current.get()
    if state is None:
        return
    state.fallback_count += 1
    state.events.append(
        {"stage": stage.value if hasattr(stage, "value") else str(stage), "reason": reason}
    )
    if state.fallback_count >= state.threshold:
        state.forced_baseline = True


def reset() -> None:
    """Test-only helper to clear the active project state."""

    _current.set(None)
