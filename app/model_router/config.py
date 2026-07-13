from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.model_router.stages import Stage, env_suffix

DEFAULT_CREATIVE_DIRECTOR_MODEL = "gpt-5-mini"
DEFAULT_TEXT_MODEL = "gpt-5-mini"
DEFAULT_PROFILE = "standard"
VALID_PROFILES = ("economy", "standard", "studio")

# The smaller/cheaper sibling model the economy and standard profiles try
# first. There is no evidence anywhere in this repository of a cheaper tier
# ever having been configured -- the existing baseline is already
# "gpt-5-mini" -- so this is a best-effort choice within the *same* model
# family already in production use (OPENAI_TEXT_MODEL / CREATIVE_DIRECTOR_
# MODEL). It is fully overridable per stage via MODEL_<STAGE>, and if it
# turns out to be unsupported by an account, the router's provider-error
# classification (app.model_router.errors) treats that as
# "unsupported_model" and falls back to baseline_model immediately -- so a
# wrong guess here degrades safely instead of breaking production.
_DEFAULT_LOWER_COST_MODEL = "gpt-5-nano"

_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{1,127}$")


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "")
    try:
        return max(minimum, min(maximum, int(raw)))
    except (TypeError, ValueError):
        return default


def is_plausible_model_id(value: str) -> bool:
    """Reject empty or malformed model configuration safely (Phase 3 #5)."""

    value = value.strip()
    return bool(value) and bool(_MODEL_ID_PATTERN.match(value))


def lower_cost_default() -> str:
    value = os.getenv("MODEL_LOWER_COST_DEFAULT", "").strip()
    if value and is_plausible_model_id(value):
        return value
    return _DEFAULT_LOWER_COST_MODEL


# ---------------------------------------------------------------------------
# Phase 2: baseline model mapping -- "the original/current model already
# used by the application". Every function here reads the exact same
# environment variables, with the exact same precedence, that the
# application already used *before* cost-aware routing existed
# (app/config.py, app/creative_director/llm.py). Nothing here ever mutates
# that mapping; Studio profile always resolves to it directly.
# ---------------------------------------------------------------------------


def _text_model_baseline() -> str:
    return os.getenv("OPENAI_TEXT_MODEL", DEFAULT_TEXT_MODEL).strip() or DEFAULT_TEXT_MODEL


def _creative_director_baseline() -> str:
    return (
        os.getenv("CREATIVE_DIRECTOR_MODEL", "").strip()
        or _text_model_baseline()
        or DEFAULT_CREATIVE_DIRECTOR_MODEL
    )


def baseline_model_for(stage: Stage) -> str:
    stage = Stage(stage)
    if stage in (Stage.CREATIVE_DIRECTOR_QUESTIONS, Stage.CREATIVE_DIRECTOR_BRIEF):
        return _creative_director_baseline()
    return _text_model_baseline()


def baseline_mapping() -> dict[str, str]:
    """The full stage -> baseline_model mapping, for reporting/tests."""

    return {stage.value: baseline_model_for(stage) for stage in Stage}


# ---------------------------------------------------------------------------
# Phase 4: profile -> stage -> "lower cost candidate" mapping. ``None`` means
# "use baseline_model for this stage in this profile" -- the profile keeps
# that stage on the verified-quality model on purpose (e.g. final script,
# difficult research, and the Creative Director brief in Standard).
# ---------------------------------------------------------------------------


def _economy_mapping() -> dict[Stage, str | None]:
    lower = lower_cost_default()
    return {
        Stage.CREATIVE_DIRECTOR_QUESTIONS: lower,
        Stage.CREATIVE_DIRECTOR_BRIEF: lower,
        Stage.RESEARCH: None,  # difficult research synthesis stays strong
        Stage.SCRIPT: None,  # final script stays strong
        Stage.STORYBOARD: lower,
        Stage.CHARACTER: lower,
        Stage.VISUAL_DIRECTOR: lower,
        Stage.PROMPT_COMPILER: lower,
        Stage.SEO: lower,
        Stage.QUALITY_REVIEW: lower,
        Stage.MEMORY: lower,
        Stage.METADATA: lower,
        Stage.VALIDATION: lower,
    }


def _standard_mapping() -> dict[Stage, str | None]:
    lower = lower_cost_default()
    return {
        Stage.CREATIVE_DIRECTOR_QUESTIONS: lower,
        Stage.CREATIVE_DIRECTOR_BRIEF: None,  # stronger model
        Stage.RESEARCH: None,  # stronger model
        Stage.SCRIPT: None,  # stronger model
        Stage.STORYBOARD: lower,
        Stage.CHARACTER: lower,
        Stage.VISUAL_DIRECTOR: lower,
        Stage.PROMPT_COMPILER: lower,
        Stage.SEO: lower,
        Stage.QUALITY_REVIEW: lower,
        Stage.MEMORY: lower,
        Stage.METADATA: lower,
        Stage.VALIDATION: lower,
    }


def _studio_mapping() -> dict[Stage, str | None]:
    return {stage: None for stage in Stage}


def profile_mapping(profile: str) -> dict[Stage, str | None]:
    profile = (profile or "").strip().lower()
    if profile == "economy":
        return _economy_mapping()
    if profile == "studio":
        return _studio_mapping()
    return _standard_mapping()


def profile_stage_model(profile: str, stage: Stage) -> str | None:
    return profile_mapping(profile).get(Stage(stage))


@dataclass(frozen=True)
class RouterConfig:
    profile: str
    auto_fallback: bool
    require_baseline_quality: bool
    fallback_failure_threshold: int
    project_fallback_threshold: int


def load_router_config() -> RouterConfig:
    profile = os.getenv("MODEL_PROFILE", DEFAULT_PROFILE).strip().lower() or DEFAULT_PROFILE
    if profile not in VALID_PROFILES:
        # Reject malformed/unknown profile values safely (Phase 14: "invalid
        # profile values fall back safely").
        profile = DEFAULT_PROFILE
    return RouterConfig(
        profile=profile,
        auto_fallback=_truthy(os.getenv("MODEL_AUTO_FALLBACK", "true")),
        require_baseline_quality=_truthy(os.getenv("MODEL_REQUIRE_BASELINE_QUALITY", "true")),
        fallback_failure_threshold=_bounded_int("MODEL_FALLBACK_FAILURE_THRESHOLD", 3, 1, 1000),
        project_fallback_threshold=_bounded_int("MODEL_PROJECT_FALLBACK_THRESHOLD", 5, 1, 1000),
    )


def stage_override(stage: Stage) -> str | None:
    """A per-stage ``MODEL_<STAGE>`` override, if validly set.

    Malformed/empty overrides are rejected safely by returning ``None`` so
    the caller falls through to the profile default instead of sending an
    empty/garbage model string to the OpenAI client.
    """

    value = os.getenv(f"MODEL_{env_suffix(stage)}", "").strip()
    if value and is_plausible_model_id(value):
        return value
    return None
