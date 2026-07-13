from __future__ import annotations

from pathlib import Path

from app.visual.art_director import enrich_prompt
from app.visual.camera import normalize_motion
from app.visual.shot_planner import plan_shots
from app.visual.styles import load_style


def apply_visual_storytelling(
    storyboard,
    project_root: Path,
    style_name: str = "documentary",
    production_specification=None,
):
    style = load_style(project_root, style_name)
    shots = plan_shots(storyboard, production_specification)
    shot_map = {shot.scene_number: shot for shot in shots}

    for scene in storyboard.scenes:
        shot = shot_map[scene.number]
        continuity = getattr(scene, "continuity_anchor", "") or ""
        scene.image_prompt = enrich_prompt(
            base_prompt=scene.image_prompt,
            shot=shot,
            style=style,
            continuity_anchor=continuity,
        )
        scene.shot_type = shot.framing
        scene.motion_type = normalize_motion(shot.camera_motion)
        scene.visual_type = shot.visual_type
        scene.caption_safe_area = shot.caption_safe_area
        scene.subject_focus = shot.subject_focus

    return storyboard, shots
