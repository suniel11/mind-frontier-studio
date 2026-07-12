from __future__ import annotations

import logging
from dataclasses import dataclass

from app.model_router import circuit_breaker, project_state
from app.model_router import config as router_config
from app.model_router.stages import Stage

logger = logging.getLogger("model_router")


@dataclass(frozen=True)
class ModelSelection:
    stage: Stage
    profile: str
    attempted_model: str
    baseline_model: str
    is_baseline_attempt: bool
    auto_fallback: bool
    reason: str


def resolve(stage: Stage, *, project_id: str | None = None) -> ModelSelection:
    """Resolve which model to attempt for ``stage``, plus its baseline.

    Precedence (Phase 3):
      1. A valid per-stage ``MODEL_<STAGE>`` environment override.
      2. Baseline, if this stage's circuit breaker has tripped.
      3. Baseline, if ``MODEL_AUTO_FALLBACK=false`` (no lower-cost model is
         even attempted -- the safest reading of "auto fallback disabled"
         is "don't experiment", not "accept unvalidated output").
      4. Baseline, if this project has crossed
         ``MODEL_PROJECT_FALLBACK_THRESHOLD`` fallbacks already.
      5. Baseline, in ``studio`` profile.
      6. Otherwise the active profile's stage mapping (which may itself be
         ``None`` -> baseline, for stages a profile intentionally keeps
         strong, e.g. script/research in Standard).
    """

    stage = Stage(stage)
    cfg = router_config.load_router_config()
    baseline = router_config.baseline_model_for(stage)

    override = router_config.stage_override(stage)
    if override:
        return _selection(stage, cfg, override, baseline, "stage_env_override")

    if circuit_breaker.is_disabled(stage, project_id=project_id):
        return _selection(stage, cfg, baseline, baseline, "circuit_breaker_open")

    if not cfg.auto_fallback:
        return _selection(stage, cfg, baseline, baseline, "auto_fallback_disabled")

    state = project_state.current()
    if state is not None and state.forced_baseline:
        return _selection(stage, cfg, baseline, baseline, "project_fallback_threshold")

    if cfg.profile == "studio":
        return _selection(stage, cfg, baseline, baseline, "studio_profile")

    candidate = router_config.profile_stage_model(cfg.profile, stage)
    if not candidate:
        return _selection(stage, cfg, baseline, baseline, "profile_keeps_baseline")

    return _selection(stage, cfg, candidate, baseline, f"{cfg.profile}_profile")


def _selection(stage: Stage, cfg, attempted: str, baseline: str, reason: str) -> ModelSelection:
    selection = ModelSelection(
        stage=stage,
        profile=cfg.profile,
        attempted_model=attempted,
        baseline_model=baseline,
        is_baseline_attempt=attempted == baseline,
        auto_fallback=cfg.auto_fallback,
        reason=reason,
    )
    # Log stage/model/reason only -- never secrets, never prompt content
    # (Phase 3 #7).
    logger.info(
        "model_router stage=%s profile=%s model=%s baseline=%s reason=%s",
        selection.stage.value,
        selection.profile,
        selection.attempted_model,
        selection.baseline_model,
        selection.reason,
    )
    return selection
