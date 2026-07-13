from __future__ import annotations

import json
import time

from app.model_router import project_state, usage
from app.model_router import router as model_router
from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import visual_asset_plan_validator
from app.model_router.stages import Stage
from app.visual_continuity import config as vc_config
from app.visual_continuity import cost_guard
from app.visual_continuity.models import VisualAssetGroup, VisualAssetPlan
from app.visual_continuity.repetition import repetition_risk
from app.visual_continuity.shots import assign_shot_variations

INSTRUCTIONS = """
You are the Visual Continuity Planner for Mind Frontier Studio.

You receive a finished storyboard -- every scene's narration, visual
direction, compiled image prompt, location, and continuity anchor are
already final. Your only job is deciding which *adjacent* scenes are
genuinely the same visual moment closely enough that they can share one
high-quality generated image (an "Anchor Shot"), each scene then presented
with a different camera treatment.

This is a professional documentary editing decision, not a cost-cutting
exercise. Group scenes together only when they remain within the same
location, historical era, scientific process, object, person, organism,
environment, event, timeline segment, or visual concept. Start a new group
the instant narration introduces a new location, country, planet, building,
civilization, historical era, scientific mechanism, object, species,
diagram, presenter, architecture, or any major environmental or narrative
transition.

Hard rules:
- Never group the opening hook scene or the final scene with anything else.
- Never group scenes across a chapter/topic transition, even if adjacent.
- When you are not confident two scenes are the same visual moment, keep
  them separate -- a lower grouping_confidence is expected and correct in
  that case, never inflate confidence to justify a merge.
- Do not aim for any particular number of groups. A documentary about one
  continuous process may naturally need very few groups; a documentary
  spanning many distinct subjects may naturally need almost one group per
  scene. Both are correct outcomes -- let the content decide.

For every group, write:
- canonical_prompt: one single, generation-ready image prompt describing
  the shared shot (equivalent in detail/style to a normal scene image
  prompt) that works for every scene in the group.
- semantic_category: the shared subject (e.g. "location:arctic_test_site",
  "process:asteroid_bombardment", "object:tsar_bomba_device").
- justification: one sentence explaining why these scenes are the same
  visual moment. Required and must be specific whenever a group has more
  than one scene.
- grouping_confidence: 0.0-1.0, your honest confidence that this merge
  preserves educational clarity and cinematic quality.

Every scene number from the storyboard must appear in exactly one group.
Groups must be contiguous, ascending scene-number ranges.
"""


def _scene_payload(scene) -> dict:
    return {
        "number": scene.number,
        "story_role": scene.story_role,
        "location_id": scene.location_id,
        "continuity_anchor": scene.continuity_anchor,
        "narration": scene.narration,
        "visual_direction": scene.visual_direction,
        "image_prompt": scene.image_prompt,
    }


def _prompt_for(storyboard, *, target_seconds: int) -> str:
    scenes_payload = [_scene_payload(scene) for scene in storyboard.scenes]
    return f"""
Target duration: {target_seconds} seconds
Scene count: {len(storyboard.scenes)}
First scene number (hook, must be its own group): {storyboard.scenes[0].number}
Last scene number (final line, must be its own group): {storyboard.scenes[-1].number}

Storyboard scenes (in order):
{json.dumps(scenes_payload, ensure_ascii=False, indent=2)}
"""


def _identity_plan(storyboard) -> VisualAssetPlan:
    """One group per scene -- exactly today's one-image-per-scene behavior.

    Used when the feature is disabled and as the guaranteed-safe fallback
    whenever planning fails or produces an unusable result: this function
    can never make a production worse than it already is.
    """

    groups = [
        VisualAssetGroup(
            group_id=f"g{scene.number:02d}",
            scene_numbers=[scene.number],
            canonical_prompt=scene.image_prompt,
            semantic_category=scene.location_id or "scene",
            justification="",
            grouping_confidence=1.0,
        )
        for scene in storyboard.scenes
    ]
    return VisualAssetPlan(groups=groups)


def _validate_coverage(plan: VisualAssetPlan, all_numbers: list[int]) -> bool:
    seen: set[int] = set()
    for group in plan.groups:
        if not group.scene_numbers:
            return False
        for number in group.scene_numbers:
            if number in seen:
                return False
            seen.add(number)
    return seen == set(all_numbers)


def _split_group(
    scene_numbers: list[int],
    scenes_by_number: dict,
    *,
    hook_number: int,
    ending_number: int,
    max_consecutive_reuse: int,
    min_confidence: float,
    confidence: float,
    debug_log: list | None = None,
) -> list[list[int]]:
    """Split one proposed group into the largest sub-runs that satisfy every
    hard constraint: the hook and ending scenes are always alone, no run
    exceeds ``max_consecutive_reuse``, a run never skips a scene number, a
    below-threshold confidence collapses the whole group to singletons, and
    a run never continues into a scene that would look "substantially
    identical" to the previous one even with a different camera treatment
    (the Visual Repetition Guard -- see app.visual_continuity.repetition).

    grouping_confidence -- which the planner is explicitly instructed to
    lower whenever it is unsure -- is the semantic "same visual moment"
    safety net (MIN_GROUPING_CONFIDENCE is the knob the spec names for
    this). An earlier version of this function also hard-split on
    ``scene.location_id`` changing between consecutive scenes; reverted
    after real-data testing showed the storyboard-authoring stage assigns a
    distinct, highly specific location_id to nearly every scene in
    practice, so exact-match rejected well-justified merges.
    """

    if confidence < min_confidence:
        return [[number] for number in scene_numbers]

    runs: list[list[int]] = []
    current: list[int] = []
    prev_number: int | None = None

    def close_current() -> None:
        nonlocal current
        if current:
            runs.append(current)
            current = []

    for number in scene_numbers:
        if number in (hook_number, ending_number):
            close_current()
            runs.append([number])
            prev_number = number
            continue

        non_adjacent = prev_number is not None and number != prev_number + 1
        force_new_run = non_adjacent or len(current) >= max_consecutive_reuse

        if not force_new_run and current:
            risky, reason = repetition_risk(scenes_by_number[current[-1]], scenes_by_number[number])
            if risky:
                force_new_run = True
                if debug_log is not None:
                    debug_log.append(
                        {"scenes": [current[-1], number], "decision": "repetition_guard_split", "reason": reason}
                    )

        if force_new_run:
            close_current()
        current.append(number)
        prev_number = number

    close_current()
    return runs


def _enforce_constraints(
    raw_plan: VisualAssetPlan,
    storyboard,
    *,
    max_consecutive_reuse: int,
    min_confidence: float,
    debug_log: list | None = None,
) -> VisualAssetPlan:
    all_numbers = [scene.number for scene in storyboard.scenes]
    if not _validate_coverage(raw_plan, all_numbers):
        if debug_log is not None:
            debug_log.append({"decision": "identity_fallback", "reason": "raw plan failed coverage validation"})
        return _identity_plan(storyboard)

    scenes_by_number = {scene.number: scene for scene in storyboard.scenes}
    hook_number = storyboard.scenes[0].number
    ending_number = storyboard.scenes[-1].number

    result_groups: list[VisualAssetGroup] = []
    for group in sorted(raw_plan.groups, key=lambda g: min(g.scene_numbers)):
        scene_numbers = sorted(group.scene_numbers)
        runs = _split_group(
            scene_numbers,
            scenes_by_number,
            hook_number=hook_number,
            ending_number=ending_number,
            max_consecutive_reuse=max_consecutive_reuse,
            min_confidence=min_confidence,
            confidence=group.grouping_confidence,
            debug_log=debug_log,
        )
        for run in runs:
            if len(run) > 1:
                result_groups.append(
                    VisualAssetGroup(
                        group_id=f"g{run[0]:02d}",
                        scene_numbers=run,
                        canonical_prompt=group.canonical_prompt,
                        semantic_category=group.semantic_category,
                        justification=group.justification,
                        grouping_confidence=group.grouping_confidence,
                    )
                )
            else:
                scene = scenes_by_number[run[0]]
                result_groups.append(
                    VisualAssetGroup(
                        group_id=f"g{run[0]:02d}",
                        scene_numbers=run,
                        canonical_prompt=scene.image_prompt,
                        semantic_category=group.semantic_category,
                        justification="",
                        grouping_confidence=group.grouping_confidence,
                    )
                )

    result_groups.sort(key=lambda g: min(g.scene_numbers))
    return VisualAssetPlan(groups=result_groups)


def _apply_plan_to_scenes(plan: VisualAssetPlan, storyboard) -> None:
    scenes_by_number = {scene.number: scene for scene in storyboard.scenes}
    for group in plan.groups:
        variations = assign_shot_variations(len(group.scene_numbers))
        for position, number in enumerate(sorted(group.scene_numbers)):
            scene = scenes_by_number.get(number)
            if scene is None:
                continue
            scene.visual_asset_group_id = group.group_id
            scene.image_prompt = group.canonical_prompt
            scene.motion_type = variations[position]


def _current_project_id() -> str | None:
    state = project_state.current()
    return state.project_id if state else None


def _last_usage_record(project_id: str | None):
    for record in reversed(usage.records_for(project_id)):
        if record.stage == Stage.VISUAL_CONTINUITY_PLANNER.value:
            return record
    return None


def _reused_image_count(plan: VisualAssetPlan) -> int:
    return sum(len(group.scene_numbers) - 1 for group in plan.groups if len(group.scene_numbers) > 1)


def _base_meta(*, enabled: bool, model: str | None, disabled_reason: str | None) -> dict:
    return {
        "planner_enabled": enabled,
        "planner_disabled_reason": disabled_reason,
        "planner_model": model,
        "planner_input_tokens": None,
        "planner_output_tokens": None,
        "planner_execution_time": 0.0,
        "debug": None,
    }


def plan_visual_assets(storyboard, *, target_seconds: int) -> tuple[VisualAssetPlan, dict]:
    """Build (and apply to ``storyboard`` in place) the Visual Asset
    Economy v3 plan: which scenes share a generated image, each scene's
    resolved image_prompt, and each scene's shot-variation motion_type.

    Returns ``(plan, meta)`` -- ``meta`` carries the planner's own
    execution cost (model, tokens, wall-clock time, and whether/why
    grouping ended up disabled for this project) so telemetry can answer
    "did this planner actually save more than it cost?" without a second
    LLM call.

    Safe by construction: disabled, a provider failure, a structurally
    unusable model output, or the Planner Cost Guard (grouping not
    economically worth its own cost) all degrade to the identity plan
    (today's unmodified one-image-per-scene behavior) rather than ever
    risking a broken, lower-quality, or money-losing production.
    """

    debug_enabled = vc_config.debug_enabled()

    if not vc_config.visual_asset_economy_enabled():
        plan = _identity_plan(storyboard)
        _apply_plan_to_scenes(plan, storyboard)
        return plan, _base_meta(enabled=False, model=None, disabled_reason="feature_disabled")

    project_id = _current_project_id()
    attempted_model = model_router.resolve(Stage.VISUAL_CONTINUITY_PLANNER, project_id=project_id).attempted_model
    scene_numbers = [scene.number for scene in storyboard.scenes]

    start = time.monotonic()
    try:
        result = run_agent_stage(
            Stage.VISUAL_CONTINUITY_PLANNER,
            instructions=INSTRUCTIONS,
            prompt=_prompt_for(storyboard, target_seconds=target_seconds),
            schema=VisualAssetPlan,
            validate=visual_asset_plan_validator(scene_numbers=scene_numbers),
        )
    except Exception:
        # Planning is an optimization on top of a working pipeline, never a
        # hard dependency -- any failure must degrade to the identity plan,
        # never break or delay production.
        elapsed = time.monotonic() - start
        plan = _identity_plan(storyboard)
        _apply_plan_to_scenes(plan, storyboard)
        meta = _base_meta(enabled=True, model=attempted_model, disabled_reason="provider_error")
        meta["planner_execution_time"] = round(elapsed, 4)
        return plan, meta

    elapsed = time.monotonic() - start
    record = _last_usage_record(project_id)
    meta = _base_meta(enabled=True, model=record.final_model if record else attempted_model, disabled_reason=None)
    meta["planner_execution_time"] = round(elapsed, 4)
    meta["planner_input_tokens"] = record.input_tokens if record else None
    meta["planner_output_tokens"] = record.output_tokens if record else None

    debug_log: list | None = [] if debug_enabled else None

    if result.validation is not None and not result.validation.passed:
        plan = _identity_plan(storyboard)
        meta["planner_disabled_reason"] = "malformed_planner_output"
        if debug_log is not None:
            debug_log.append({"decision": "identity_fallback", "reason": "validation failed"})
    else:
        raw_plan = result.output
        plan = _enforce_constraints(
            raw_plan,
            storyboard,
            max_consecutive_reuse=vc_config.max_consecutive_reuse(),
            min_confidence=vc_config.min_grouping_confidence(),
            debug_log=debug_log,
        )

        guard = cost_guard.evaluate(
            planner_input_tokens=meta["planner_input_tokens"],
            planner_output_tokens=meta["planner_output_tokens"],
            reused_images=_reused_image_count(plan),
            planner_execution_time=meta["planner_execution_time"],
        )
        if guard.should_disable_grouping and _reused_image_count(plan) > 0:
            meta["planner_disabled_reason"] = (
                "cost_guard_triggered" if guard.should_disable_for_cost else "cost_guard_time_negative"
            )
            if debug_log is not None:
                debug_log.append(
                    {
                        "decision": "cost_guard_disabled_grouping",
                        "planner_estimated_cost_usd": guard.planner_estimated_cost_usd,
                        "estimated_image_cost_saved_usd": guard.estimated_image_cost_saved_usd,
                        "estimated_net_time_saved_seconds": guard.estimated_net_time_saved_seconds,
                    }
                )
            plan = _identity_plan(storyboard)

        if debug_enabled:
            meta["debug"] = {
                "raw_plan": raw_plan.model_dump(),
                "decisions": debug_log or [],
            }

    _apply_plan_to_scenes(plan, storyboard)
    return plan, meta
