from __future__ import annotations

ROLE_WEIGHTS = {
    "hook": 0.80,
    "setup": 1.00,
    "tension": 0.90,
    "expansion": 1.05,
    "climax": 1.15,
    "resolution": 1.10,
}


def apply_edit_plan(storyboard, target_seconds: int):
    scenes = list(storyboard.scenes)
    if not scenes:
        return storyboard

    weights = []
    for scene in scenes:
        role = str(getattr(scene, "story_role", "")).lower()
        intensity = int(getattr(scene, "emotional_intensity", 5) or 5)
        base = ROLE_WEIGHTS.get(role, 1.0)
        weights.append(base * (0.9 + intensity / 50))

    total_weight = sum(weights)
    cursor = 0
    for index, (scene, weight) in enumerate(zip(scenes, weights)):
        if index == len(scenes) - 1:
            end = target_seconds
        else:
            duration = max(2, round(target_seconds * weight / total_weight))
            end = min(target_seconds, cursor + duration)

        scene.start_second = cursor
        scene.end_second = end
        cursor = end

        role = str(getattr(scene, "story_role", "")).lower()
        if role == "hook":
            scene.pacing = "fast"
            scene.transition_type = "cut"
        elif role in {"climax", "resolution"}:
            scene.pacing = "hold"
            scene.transition_type = "fade"
        else:
            scene.pacing = "medium"

    return storyboard
