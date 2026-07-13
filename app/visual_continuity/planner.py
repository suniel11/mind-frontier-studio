from __future__ import annotations

from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import visual_asset_plan_validator
from app.model_router.stages import Stage
from app.visual_continuity import config as vc_config
from app.visual_continuity.models import VisualAssetGroup, VisualAssetPlan
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
    import json

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
) -> list[list[int]]:
    """Split one proposed group into the largest sub-runs that satisfy every
    hard constraint: the hook and ending scenes are always alone, no run
    exceeds ``max_consecutive_reuse``, a run never crosses a location
    change (the deterministic backstop for "unrelated scenes"/"chapter
    transitions"), and a below-threshold confidence collapses the whole
    group to singletons."""

    if confidence < min_confidence:
        return [[number] for number in scene_numbers]

    runs: list[list[int]] = []
    current: list[int] = []
    prev_location: str | None = None
    prev_number: int | None = None

    def close_current() -> None:
        nonlocal current
        if current:
            runs.append(current)
            current = []

    for number in scene_numbers:
        scene = scenes_by_number[number]
        if number in (hook_number, ending_number):
            close_current()
            runs.append([number])
            prev_location = scene.location_id
            prev_number = number
            continue

        non_adjacent = prev_number is not None and number != prev_number + 1
        location_changed = prev_location is not None and scene.location_id != prev_location
        if non_adjacent or location_changed or len(current) >= max_consecutive_reuse:
            close_current()
        current.append(number)
        prev_location = scene.location_id
        prev_number = number

    close_current()
    return runs


def _enforce_constraints(
    raw_plan: VisualAssetPlan,
    storyboard,
    *,
    max_consecutive_reuse: int,
    min_confidence: float,
) -> VisualAssetPlan:
    all_numbers = [scene.number for scene in storyboard.scenes]
    if not _validate_coverage(raw_plan, all_numbers):
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


def plan_visual_assets(storyboard, *, target_seconds: int) -> VisualAssetPlan:
    """Build (and apply to ``storyboard`` in place) the Visual Asset
    Economy v3 plan: which scenes share a generated image, each scene's
    resolved image_prompt, and each scene's shot-variation motion_type.

    Safe by construction: disabled, a provider failure, or a structurally
    unusable model output all degrade to the identity plan (today's
    unmodified one-image-per-scene behavior) rather than ever risking a
    broken or lower-quality production.
    """

    if not vc_config.visual_asset_economy_enabled():
        plan = _identity_plan(storyboard)
        _apply_plan_to_scenes(plan, storyboard)
        return plan

    scene_numbers = [scene.number for scene in storyboard.scenes]

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
        plan = _identity_plan(storyboard)
        _apply_plan_to_scenes(plan, storyboard)
        return plan

    if result.validation is not None and not result.validation.passed:
        plan = _identity_plan(storyboard)
    else:
        plan = _enforce_constraints(
            result.output,
            storyboard,
            max_consecutive_reuse=vc_config.max_consecutive_reuse(),
            min_confidence=vc_config.min_grouping_confidence(),
        )

    _apply_plan_to_scenes(plan, storyboard)
    return plan
