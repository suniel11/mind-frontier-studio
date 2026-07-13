from __future__ import annotations

from app.visual_continuity.models import VisualAssetPlan


def continuity_score(plan: VisualAssetPlan, storyboard) -> float:
    """A deterministic 0-100 score reflecting whether the plan's reuse
    decisions look like coherent visual sequences rather than arbitrary
    merges.

    Rewarded:
    - Multi-scene groups (a deliberate, justified visual sequence).
    - Shot variety within a group (no two scenes in the same group share a
      camera treatment).

    Penalized:
    - Repetitive framing/identical camera movement within a shared group.

    A single-scene group (its own fresh shot) is scored neutrally -- it is
    never wrong to give a scene its own image, so it neither rewards nor
    penalizes the plan.
    """

    if not plan.groups:
        return 0.0

    scenes_by_number = {scene.number: scene for scene in storyboard.scenes}
    points = 0.0
    max_points = 0.0

    for group in plan.groups:
        max_points += 10.0
        size = len(group.scene_numbers)
        if size == 1:
            points += 7.0
            continue

        points += 10.0
        motions = [scenes_by_number[number].motion_type for number in group.scene_numbers if number in scenes_by_number]
        if len(set(motions)) < len(motions):
            points -= 4.0  # identical camera movement reused within one group
        if not group.justification.strip():
            points -= 3.0  # unjustified reuse

    if max_points == 0:
        return 0.0
    return round(max(0.0, min(100.0, (points / max_points) * 100)), 2)
