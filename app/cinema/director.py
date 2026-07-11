from __future__ import annotations

from app.cinema.models import CinemaReport, CinematicShot


ROLE_DIRECTION = {
    "hook": {
        "shot_type": "extreme_close_up",
        "motion_type": "cinematic_push",
        "lens_mm": 85,
        "composition": "tight asymmetrical framing with strong negative space",
        "lighting": "high-contrast window light",
        "color_tone": "cool neutral shadows with restrained warm highlights",
        "focus_target": "eyes or hands",
    },
    "setup": {
        "shot_type": "wide_environment",
        "motion_type": "slow_pan_right",
        "lens_mm": 35,
        "composition": "wide rule-of-thirds composition",
        "lighting": "soft natural ambient light",
        "color_tone": "muted earth tones",
        "focus_target": "subject within environment",
    },
    "conflict": {
        "shot_type": "object_detail",
        "motion_type": "parallax_left",
        "lens_mm": 70,
        "composition": "layered foreground and background separation",
        "lighting": "low-key directional light",
        "color_tone": "cool desaturated contrast",
        "focus_target": "symbolic object or hands",
    },
    "insight": {
        "shot_type": "over_shoulder",
        "motion_type": "drift",
        "lens_mm": 50,
        "composition": "over-the-shoulder with leading lines",
        "lighting": "balanced natural window light",
        "color_tone": "neutral cinematic palette",
        "focus_target": "action and environment",
    },
    "resolution": {
        "shot_type": "medium_wide",
        "motion_type": "cinematic_pull",
        "lens_mm": 40,
        "composition": "open frame with breathing room",
        "lighting": "warm directional light",
        "color_tone": "soft amber highlights",
        "focus_target": "forward movement",
    },
    "final_line": {
        "shot_type": "hero_wide",
        "motion_type": "micro_push",
        "lens_mm": 35,
        "composition": "clean centered silhouette or spacious final frame",
        "lighting": "golden-hour backlight",
        "color_tone": "warm resolved palette",
        "focus_target": "subject and horizon",
    },
}


def _score_report(shots: list[CinematicShot]) -> CinemaReport:
    motions = {shot.motion_type for shot in shots}
    shot_types = {shot.shot_type for shot in shots}
    lenses = {shot.lens_mm for shot in shots}
    tones = {shot.color_tone for shot in shots}

    movement_score = min(100, 55 + len(motions) * 8)
    shot_variety_score = min(100, 50 + len(shot_types) * 9)
    composition_score = min(100, 55 + len(lenses) * 8)
    emotion_score = min(100, 60 + len(tones) * 7)

    durations = [shot.duration for shot in shots]
    spread = max(durations) - min(durations) if durations else 0
    rhythm_score = min(100, 72 + round(spread * 6))

    cinema_score = round(
        movement_score * 0.24
        + shot_variety_score * 0.24
        + rhythm_score * 0.18
        + emotion_score * 0.18
        + composition_score * 0.16
    )

    return CinemaReport(
        cinema_score=cinema_score,
        movement_score=movement_score,
        shot_variety_score=shot_variety_score,
        rhythm_score=rhythm_score,
        emotion_score=emotion_score,
        composition_score=composition_score,
        shots=shots,
    )


def apply_cinematic_direction(storyboard):
    recent_shots: list[str] = []
    recent_motions: list[str] = []
    shots: list[CinematicShot] = []

    for scene in storyboard.scenes:
        role = str(getattr(scene, "story_role", "") or "").lower()
        direction = ROLE_DIRECTION.get(role, ROLE_DIRECTION["insight"]).copy()

        shot_type = direction["shot_type"]
        motion_type = direction["motion_type"]

        if recent_shots and recent_shots[-1] == shot_type:
            shot_type = "environment_detail"

        if recent_motions and recent_motions[-1] == motion_type:
            motion_type = "drift" if motion_type != "drift" else "micro_push"

        intensity = int(getattr(scene, "emotional_intensity", 6) or 6)
        duration = max(1.0, float(scene.end_second) - float(scene.start_second))

        scene.shot_type = shot_type
        scene.motion_type = motion_type
        scene.lens_mm = direction["lens_mm"]
        scene.composition = direction["composition"]
        scene.lighting_style = direction["lighting"]
        scene.color_tone = direction["color_tone"]
        scene.focus_target = direction["focus_target"]
        scene.film_look = "subtle grain, restrained vignette, documentary contrast"
        scene.caption_safe_area = (
            "upper_third"
            if role in {"conflict", "insight"} and scene.number % 2 == 0
            else "lower_third"
        )
        scene.visual_direction = (
            f"{getattr(scene, 'visual_direction', '')} "
            f"Cinematic direction: {shot_type}, {direction['lens_mm']}mm lens, "
            f"{direction['composition']}, {direction['lighting']}, "
            f"{direction['color_tone']}, focus on {direction['focus_target']}."
        ).strip()

        shots.append(
            CinematicShot(
                scene_number=int(scene.number),
                story_role=role,
                shot_type=shot_type,
                motion_type=motion_type,
                lens_mm=direction["lens_mm"],
                composition=direction["composition"],
                lighting=direction["lighting"],
                color_tone=direction["color_tone"],
                focus_target=direction["focus_target"],
                intensity=intensity,
                duration=duration,
            )
        )

        recent_shots.append(shot_type)
        recent_motions.append(motion_type)

    return storyboard, _score_report(shots)
