from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from app.model_router.quality_checks import (
    research_validator,
    script_validator,
    seo_validator,
    storyboard_validator,
)


@contextmanager
def _profile_override(profile: str):
    previous = os.environ.get("MODEL_PROFILE")
    os.environ["MODEL_PROFILE"] = profile
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("MODEL_PROFILE", None)
        else:
            os.environ["MODEL_PROFILE"] = previous


def _run_text_stages(
    topic: str,
    target_seconds: int,
    production_specification,
    *,
    research_run: Callable,
    script_run: Callable,
    storyboard_run: Callable,
    seo_run: Callable,
) -> dict:
    from app.model_router import usage as usage_module
    from app.model_router.project_state import reset as reset_project_state
    from app.model_router.project_state import start_project

    marker_project_id = f"__comparison__{time.monotonic_ns()}"
    start_project(marker_project_id)
    try:
        start = time.monotonic()
        research_result = research_run(topic, production_specification=production_specification)
        research_validation = research_validator()(research_result)

        script_result = script_run(
            topic,
            research_result,
            target_seconds,
            production_specification=production_specification,
        )
        script_validation = script_validator(target_seconds=target_seconds)(script_result)

        storyboard_result = storyboard_run(
            script_result,
            target_seconds,
            None,
            production_specification=production_specification,
        )
        storyboard_validation = storyboard_validator(target_seconds=target_seconds)(storyboard_result)

        seo_result = seo_run(script_result, production_specification=production_specification)
        seo_validation = seo_validator()(seo_result)
        latency = time.monotonic() - start

        calls = usage_module.records_for(marker_project_id)
        return {
            "latency_seconds": round(latency, 4),
            "token_usage": {
                "input_tokens": sum(call.input_tokens or 0 for call in calls),
                "output_tokens": sum(call.output_tokens or 0 for call in calls),
            },
            "models_used": {call.stage: call.final_model for call in calls},
            "fallback_events": [
                {"stage": call.stage, "reason": call.fallback_reason}
                for call in calls
                if call.fallback_triggered
            ],
            "validation_scores": {
                "research": asdict(research_validation),
                "script": asdict(script_validation),
                "storyboard": asdict(storyboard_validation),
                "seo": asdict(seo_validation),
            },
            "output_lengths": {
                "research_verified_points": len(research_result.verified_points),
                "script_voiceover_words": len(script_result.voiceover.split()),
                "storyboard_scenes": len(storyboard_result.scenes),
                "seo_hashtags": len(seo_result.hashtags),
            },
            "structural_checks": {
                "research_valid": research_validation.passed,
                "script_valid": script_validation.passed,
                "storyboard_valid": storyboard_validation.passed,
                "seo_valid": seo_validation.passed,
            },
            "accepted": all(
                (
                    research_validation.passed,
                    script_validation.passed,
                    storyboard_validation.passed,
                    seo_validation.passed,
                )
            ),
        }
    finally:
        reset_project_state()
        usage_module.reset(marker_project_id)


def run_comparison(
    topic: str,
    target_seconds: int,
    *,
    production_specification=None,
    profile_a: str = "studio",
    profile_b: str = "standard",
    research_run: Callable | None = None,
    script_run: Callable | None = None,
    storyboard_run: Callable | None = None,
    seo_run: Callable | None = None,
) -> dict:
    """Developer-only text-stage A/B comparison utility (Phase 12).

    Runs research -> script -> storyboard -> SEO once per profile and scores
    each run with the same deterministic checks the production pipeline
    uses -- never another LLM as judge. Never regenerates images, narration,
    or the final video.

    The ``*_run`` parameters default to the real agent modules (real OpenAI
    calls) but are injectable so this utility -- and its tests -- can run
    against fakes.
    """

    from app.agents import research as research_agent
    from app.agents import script as script_agent
    from app.agents import seo as seo_agent
    from app.agents import storyboard as storyboard_agent

    research_run = research_run or research_agent.run
    script_run = script_run or script_agent.run
    storyboard_run = storyboard_run or storyboard_agent.run
    seo_run = seo_run or seo_agent.run

    with _profile_override(profile_a):
        result_a = _run_text_stages(
            topic,
            target_seconds,
            production_specification,
            research_run=research_run,
            script_run=script_run,
            storyboard_run=storyboard_run,
            seo_run=seo_run,
        )
    with _profile_override(profile_b):
        result_b = _run_text_stages(
            topic,
            target_seconds,
            production_specification,
            research_run=research_run,
            script_run=script_run,
            storyboard_run=storyboard_run,
            seo_run=seo_run,
        )

    return {
        "topic": topic,
        "target_seconds": target_seconds,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "result_a": result_a,
        "result_b": result_b,
    }


def save_comparison(project_dir: Path, comparison: dict) -> Path:
    path = Path(project_dir) / "model-comparison.json"
    path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return path
