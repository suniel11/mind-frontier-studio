from __future__ import annotations

import json
from pathlib import Path

from app.visual_continuity import cost_guard
from app.visual_continuity.models import VisualAssetPlan
from app.visual_continuity.scoring import continuity_score


def _group_explanations(plan: VisualAssetPlan) -> list[dict]:
    return [
        {
            "group_id": group.group_id,
            "semantic_category": group.semantic_category,
            "canonical_prompt": group.canonical_prompt,
            "grouping_confidence": group.grouping_confidence,
            "justification": group.justification,
            "member_scenes": group.scene_numbers,
        }
        for group in plan.groups
    ]


def _reused_scene_explanations(plan: VisualAssetPlan) -> list[dict]:
    """Per the spec: for every reused scene, why reuse was selected and
    which semantic evidence supported it -- the first scene in a group is
    the one that actually generates the image; every other member "reuses"
    it, so those are the entries recorded here."""

    explanations: list[dict] = []
    for group in plan.groups:
        if len(group.scene_numbers) <= 1:
            continue
        ordered = sorted(group.scene_numbers)
        for scene_number in ordered[1:]:
            explanations.append(
                {
                    "scene": scene_number,
                    "group_id": group.group_id,
                    "reused_from_scene": ordered[0],
                    "reason": group.justification,
                    "semantic_evidence": group.semantic_category,
                    "grouping_confidence": group.grouping_confidence,
                }
            )
    return explanations


def build_visual_asset_report(plan: VisualAssetPlan, storyboard, planner_meta: dict | None = None) -> dict:
    planner_meta = planner_meta or {}
    scene_count = len(storyboard.scenes)
    generated_images = len(plan.groups)
    reused_images = max(0, scene_count - generated_images)
    average_scenes_per_asset = round(scene_count / generated_images, 3) if generated_images else 0.0
    reuse_percentage = round((reused_images / scene_count) * 100, 2) if scene_count else 0.0

    input_tokens = planner_meta.get("planner_input_tokens")
    output_tokens = planner_meta.get("planner_output_tokens")
    total_tokens = (input_tokens or 0) + (output_tokens or 0) if (input_tokens is not None or output_tokens is not None) else None
    planner_execution_time = planner_meta.get("planner_execution_time", 0.0)

    # Single source of truth for cost/time math -- the exact same
    # cost_guard.evaluate() the planner itself used to decide whether to
    # keep or discard this plan, so the report can never disagree with the
    # decision that produced it.
    guard = cost_guard.evaluate(
        planner_input_tokens=input_tokens,
        planner_output_tokens=output_tokens,
        reused_images=reused_images,
        planner_execution_time=planner_execution_time,
    )
    planner_estimated_cost = guard.planner_estimated_cost_usd
    estimated_image_cost_saved = guard.estimated_image_cost_saved_usd
    estimated_render_time_saved = guard.estimated_render_time_saved_seconds
    estimated_net_cost_saved = guard.estimated_net_cost_saved_usd
    estimated_net_time_saved = guard.estimated_net_time_saved_seconds

    return {
        "scene_count": scene_count,
        "generated_images": generated_images,
        "reused_images": reused_images,
        "visual_asset_groups": generated_images,
        "average_scenes_per_asset": average_scenes_per_asset,
        "continuity_score": continuity_score(plan, storyboard),
        "reuse_percentage": reuse_percentage,
        # Planner execution cost (Section 2: "did this planner actually
        # save more money than it cost?").
        "planner_enabled": planner_meta.get("planner_enabled", True),
        "planner_disabled_reason": planner_meta.get("planner_disabled_reason"),
        "planner_model": planner_meta.get("planner_model"),
        "planner_input_tokens": input_tokens,
        "planner_output_tokens": output_tokens,
        "planner_total_tokens": total_tokens,
        "planner_execution_time": planner_execution_time,
        "planner_estimated_cost": planner_estimated_cost,
        # Image-generation side.
        "images_generated": generated_images,
        "images_reused": reused_images,
        "estimated_image_cost_saved": estimated_image_cost_saved,
        "estimated_render_time_saved": estimated_render_time_saved,
        # Net (image savings minus planner's own cost/time).
        "estimated_net_cost_saved": estimated_net_cost_saved,
        "estimated_net_time_saved": estimated_net_time_saved,
        # Backward-compatible aliases from v3.
        "estimated_image_api_calls_saved": reused_images,
        "estimated_render_time_saved_seconds": estimated_render_time_saved,
        # Explainability (Section 6).
        "groups": _group_explanations(plan),
        "reused_scenes": _reused_scene_explanations(plan),
    }


def save_visual_asset_report(project_dir: Path, plan: VisualAssetPlan, storyboard, planner_meta: dict | None = None) -> Path:
    document = build_visual_asset_report(plan, storyboard, planner_meta)
    path = Path(project_dir) / "visual-asset-report.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def save_visual_continuity_debug(project_dir: Path, planner_meta: dict | None) -> Path | None:
    """VISUAL_CONTINUITY_DEBUG-only output: the raw planner proposal before
    enforcement plus every constraint decision (repetition splits, cost
    guard, identity fallbacks). Never written when the debug flag is off."""

    if not planner_meta or planner_meta.get("debug") is None:
        return None
    path = Path(project_dir) / "visual-continuity-debug.json"
    path.write_text(json.dumps(planner_meta["debug"], indent=2), encoding="utf-8")
    return path
