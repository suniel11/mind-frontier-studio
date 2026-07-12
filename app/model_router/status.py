from __future__ import annotations

from app.model_router import circuit_breaker, project_state
from app.model_router import config as router_config
from app.model_router import router as model_router
from app.model_router.stages import Stage


def get_model_routing_status(project_id: str | None = None) -> dict:
    """Phase 13: expose the active model profile via a safe, read-only,
    backend-only status document. Never exposes API keys -- environment
    variables remain authoritative; this only reports what they currently
    resolve to."""

    cfg = router_config.load_router_config()
    active_by_stage: dict[str, str] = {}
    baseline_by_stage: dict[str, str] = {}
    for stage in Stage:
        selection = model_router.resolve(stage, project_id=project_id)
        active_by_stage[stage.value] = selection.attempted_model
        baseline_by_stage[stage.value] = selection.baseline_model

    state = project_state.current()
    fallback_count = state.fallback_count if state and state.project_id == project_id else 0

    return {
        "profile": cfg.profile,
        "auto_fallback_enabled": cfg.auto_fallback,
        "require_baseline_quality": cfg.require_baseline_quality,
        "fallback_failure_threshold": cfg.fallback_failure_threshold,
        "project_fallback_threshold": cfg.project_fallback_threshold,
        "active_model_per_stage": active_by_stage,
        "baseline_model_per_stage": baseline_by_stage,
        "project_id": project_id,
        "fallbacks_in_current_project": fallback_count,
        "circuit_breakers": circuit_breaker.all_status(project_id=project_id),
    }
