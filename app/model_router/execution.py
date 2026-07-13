from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from app.model_router import circuit_breaker, project_state, usage
from app.model_router import config as router_config
from app.model_router import router as model_router
from app.model_router.errors import RETRYABLE_CATEGORIES, ErrorCategory, classify_error
from app.model_router.quality_checks import ValidationResult
from app.model_router.stages import Stage
from app.services.openai_client import structured_response

# Bounded retry -- never infinite (Phase 9). Only transient/timeout errors
# are retried, and only against the *same* model already selected; a model
# that is unsupported/unauthenticated/out of quota is never retried, it
# falls back to baseline_model immediately instead.
MAX_RETRIES_PER_MODEL = 2
BASE_BACKOFF_SECONDS = 0.5
MAX_BACKOFF_SECONDS = 4.0


@dataclass(frozen=True)
class StageExecutionResult:
    output: object
    stage: Stage
    profile: str
    attempted_model: str
    baseline_model: str
    final_model: str
    fallback_triggered: bool
    fallback_reason: str | None
    validation: ValidationResult | None
    retries: int
    circuit_breaker_tripped: bool


def _current_project_id() -> str | None:
    state = project_state.current()
    return state.project_id if state else None


def _usage_fields(info: dict) -> dict:
    return {
        "input_tokens": info.get("input_tokens"),
        "output_tokens": info.get("output_tokens"),
        "cached_tokens": info.get("cached_tokens"),
    }


def _call_once(
    *,
    instructions: str,
    prompt: str,
    schema,
    model: str,
    client,
    sleep: Callable[[float], None],
    temperature: float | None = None,
):
    """Call ``model`` once, with bounded retry for transient/timeout errors.

    Returns ``(output, usage_info, exception, error_category, retries)``.
    Exactly one of ``output``/``exception`` is set.
    """

    attempt = 0
    while True:
        try:
            output, usage_info = structured_response(
                instructions=instructions,
                prompt=prompt,
                schema=schema,
                model=model,
                client=client,
                return_usage=True,
                temperature=temperature,
            )
            return output, usage_info, None, None, attempt
        except Exception as exc:  # noqa: BLE001 - classified immediately below
            category = classify_error(exc)
            if category in RETRYABLE_CATEGORIES and attempt < MAX_RETRIES_PER_MODEL:
                sleep(min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2**attempt)))
                attempt += 1
                continue
            return None, {}, exc, category, attempt


def run_agent_stage(
    stage: Stage,
    *,
    instructions: str,
    prompt: str,
    schema,
    validate: Callable[[object], ValidationResult],
    client=None,
    sleep: Callable[[float], None] = time.sleep,
    temperature: float | None = None,
) -> StageExecutionResult:
    """Run one text-model stage with cost-aware routing and baseline
    quality fallback (Phases 3, 6, 8, 9, 10).

    1. Resolve a model for ``stage`` via the central router.
    2. Call it (bounded retry for transient/timeout provider errors only).
    3. If it failed outright (schema/provider error) or failed
       ``validate()``, and this wasn't already the baseline attempt: record
       a circuit-breaker failure + a project-level fallback event, then
       rerun once on ``baseline_model`` and use *that* output unconditionally.
    4. Record local usage telemetry (no prompts, no secrets) either way.

    ``temperature`` is passed straight through to every underlying call
    (both the initial attempt and any baseline fallback attempt) and
    omitted entirely when ``None`` -- unused by any existing caller, opt-in
    only for stages that have verified the resolved model actually accepts
    it (see app.services.openai_client.structured_response).

    Raises the underlying exception only when the *baseline* attempt itself
    fails -- there is nothing left to fall back to at that point.
    """

    stage = Stage(stage)
    project_id = _current_project_id()
    cfg = router_config.load_router_config()
    selection = model_router.resolve(stage, project_id=project_id)

    start = time.monotonic()
    output, usage_info, exc, category, retries = _call_once(
        instructions=instructions,
        prompt=prompt,
        schema=schema,
        model=selection.attempted_model,
        client=client,
        sleep=sleep,
        temperature=temperature,
    )

    validation: ValidationResult | None = None
    needs_fallback = False
    fallback_reason: str | None = None

    if exc is not None:
        needs_fallback = True
        fallback_reason = f"provider_error[{category.value if category else 'unknown'}]: {exc}"[:300]
    else:
        validation = validate(output)
        if not validation.passed:
            needs_fallback = True
            fallback_reason = "quality_validation_failed: " + "; ".join(validation.reasons)
        elif validation.inconclusive and cfg.require_baseline_quality and not selection.is_baseline_attempt:
            needs_fallback = True
            fallback_reason = "quality_comparison_inconclusive: " + "; ".join(validation.reasons)

    if needs_fallback and selection.is_baseline_attempt:
        # This *was* the baseline attempt -- nothing left to fall back to.
        latency = time.monotonic() - start
        usage.record(
            project_id,
            usage.UsageRecord(
                stage=stage.value,
                profile=selection.profile,
                attempted_model=selection.attempted_model,
                baseline_model=selection.baseline_model,
                final_model=selection.attempted_model,
                fallback_triggered=False,
                fallback_reason=None,
                validation_passed=(validation.passed if validation else None),
                validation_reasons=(validation.reasons if validation else []),
                **_usage_fields(usage_info),
                latency_seconds=round(latency, 4),
                retry_count=retries,
                success=exc is None,
                error_category=(category.value if category else None),
                project_id=project_id,
            ),
        )
        if exc is not None:
            raise exc
        return StageExecutionResult(
            output=output,
            stage=stage,
            profile=selection.profile,
            attempted_model=selection.attempted_model,
            baseline_model=selection.baseline_model,
            final_model=selection.attempted_model,
            fallback_triggered=False,
            fallback_reason=None,
            validation=validation,
            retries=retries,
            circuit_breaker_tripped=False,
        )

    if not needs_fallback:
        latency = time.monotonic() - start
        usage.record(
            project_id,
            usage.UsageRecord(
                stage=stage.value,
                profile=selection.profile,
                attempted_model=selection.attempted_model,
                baseline_model=selection.baseline_model,
                final_model=selection.attempted_model,
                fallback_triggered=False,
                fallback_reason=None,
                validation_passed=(validation.passed if validation else None),
                validation_reasons=(validation.reasons if validation else []),
                **_usage_fields(usage_info),
                latency_seconds=round(latency, 4),
                retry_count=retries,
                success=True,
                error_category=None,
                project_id=project_id,
            ),
        )
        return StageExecutionResult(
            output=output,
            stage=stage,
            profile=selection.profile,
            attempted_model=selection.attempted_model,
            baseline_model=selection.baseline_model,
            final_model=selection.attempted_model,
            fallback_triggered=False,
            fallback_reason=None,
            validation=validation,
            retries=retries,
            circuit_breaker_tripped=False,
        )

    # --- Automatic baseline fallback (Phase 6/8) -----------------------
    tripped = circuit_breaker.record_failure(
        stage,
        project_id=project_id,
        threshold=cfg.fallback_failure_threshold,
        reason=fallback_reason or "",
    )
    project_state.record_fallback(stage, fallback_reason or "")

    baseline_output, baseline_usage_info, baseline_exc, baseline_category, baseline_retries = _call_once(
        instructions=instructions,
        prompt=prompt,
        schema=schema,
        model=selection.baseline_model,
        client=client,
        sleep=sleep,
        temperature=temperature,
    )
    retries += baseline_retries
    latency = time.monotonic() - start

    if baseline_exc is not None:
        usage.record(
            project_id,
            usage.UsageRecord(
                stage=stage.value,
                profile=selection.profile,
                attempted_model=selection.attempted_model,
                baseline_model=selection.baseline_model,
                final_model=selection.baseline_model,
                fallback_triggered=True,
                fallback_reason=fallback_reason,
                validation_passed=None,
                validation_reasons=[],
                **_usage_fields({}),
                latency_seconds=round(latency, 4),
                retry_count=retries,
                success=False,
                error_category=(baseline_category.value if baseline_category else None),
                project_id=project_id,
            ),
        )
        raise baseline_exc

    baseline_validation = validate(baseline_output)
    usage.record(
        project_id,
        usage.UsageRecord(
            stage=stage.value,
            profile=selection.profile,
            attempted_model=selection.attempted_model,
            baseline_model=selection.baseline_model,
            final_model=selection.baseline_model,
            fallback_triggered=True,
            fallback_reason=fallback_reason,
            validation_passed=baseline_validation.passed,
            validation_reasons=baseline_validation.reasons,
            **_usage_fields(baseline_usage_info),
            latency_seconds=round(latency, 4),
            retry_count=retries,
            success=True,
            error_category=None,
            project_id=project_id,
        ),
    )

    return StageExecutionResult(
        output=baseline_output,
        stage=stage,
        profile=selection.profile,
        attempted_model=selection.attempted_model,
        baseline_model=selection.baseline_model,
        final_model=selection.baseline_model,
        fallback_triggered=True,
        fallback_reason=fallback_reason,
        validation=baseline_validation,
        retries=retries,
        circuit_breaker_tripped=tripped,
    )
