from __future__ import annotations

import json
from pathlib import Path

from app.visual_continuity.models import VisualAssetPlan
from app.visual_continuity.scoring import continuity_score

# Derived, real, historical average latency for one gpt-image-1 scene-image
# call (see PROFILING_REPORT.md: "Average image generation latency
# (derived): ~15.36s/call"). Used only to estimate render-time savings from
# reuse counts -- an estimate, not a fresh live measurement.
_ESTIMATED_SECONDS_PER_IMAGE = 15.36


def build_visual_asset_report(plan: VisualAssetPlan, storyboard) -> dict:
    scene_count = len(storyboard.scenes)
    generated_images = len(plan.groups)
    reused_images = max(0, scene_count - generated_images)
    average_scenes_per_asset = round(scene_count / generated_images, 3) if generated_images else 0.0
    reuse_percentage = round((reused_images / scene_count) * 100, 2) if scene_count else 0.0

    return {
        "scene_count": scene_count,
        "generated_images": generated_images,
        "reused_images": reused_images,
        "visual_asset_groups": generated_images,
        "average_scenes_per_asset": average_scenes_per_asset,
        "continuity_score": continuity_score(plan, storyboard),
        "reuse_percentage": reuse_percentage,
        "estimated_image_api_calls_saved": reused_images,
        "estimated_render_time_saved_seconds": round(reused_images * _ESTIMATED_SECONDS_PER_IMAGE, 2),
        "groups": [group.model_dump() for group in plan.groups],
    }


def save_visual_asset_report(project_dir: Path, plan: VisualAssetPlan, storyboard) -> Path:
    document = build_visual_asset_report(plan, storyboard)
    path = Path(project_dir) / "visual-asset-report.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path
