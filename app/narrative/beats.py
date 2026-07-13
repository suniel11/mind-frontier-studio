from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.narrative.duration_planning import allocate_durations


@dataclass
class NarrativeBeat:
    scene_number: int
    beat_name: str
    purpose: str
    target_emotion: str
    intensity: int
    pacing: str
    transition: str
    caption_mode: str
    target_duration: int

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


BEAT_META = {
    "hook": {"purpose": "Stop the scroll with a provocative idea or unresolved question.", "target_emotion": "curiosity", "intensity": 7, "pacing": "fast", "transition": "cut", "caption_mode": "hook"},
    "setup": {"purpose": "Make the viewer recognize the problem in their own life.", "target_emotion": "recognition", "intensity": 5, "pacing": "medium", "transition": "cut", "caption_mode": "standard"},
    "conflict": {"purpose": "Expose the hidden cost, contradiction, or uncomfortable truth.", "target_emotion": "discomfort", "intensity": 8, "pacing": "fast", "transition": "cut", "caption_mode": "emphasis"},
    "insight": {"purpose": "Reveal the central explanation or shift in perspective.", "target_emotion": "realization", "intensity": 8, "pacing": "medium", "transition": "dissolve", "caption_mode": "emphasis"},
    "resolution": {"purpose": "Show the practical or philosophical way forward.", "target_emotion": "hope", "intensity": 6, "pacing": "slow", "transition": "fade", "caption_mode": "standard"},
    "final_line": {"purpose": "Leave one concise sentence the viewer remembers.", "target_emotion": "reflection", "intensity": 7, "pacing": "hold", "transition": "hold", "caption_mode": "resolution"},
}

# The original template's fixed 6-beat order. Longer storyboards keep the
# same open (hook) and close (final_line) but cycle the middle beats to give
# each additional scene its own purpose instead of stretching one of these
# six across more screen time.
_MIDDLE_CYCLE = ("setup", "conflict", "insight", "resolution")
_FULL_ORDER = ("hook", "setup", "conflict", "insight", "resolution", "final_line")


def _role_sequence(count: int) -> list[str]:
    if count <= 0:
        return []
    if count <= len(_FULL_ORDER):
        # Small/edge-case counts: use a prefix of the canonical order so a
        # 6-scene storyboard behaves exactly as before.
        if count == len(_FULL_ORDER):
            return list(_FULL_ORDER)
        return list(_FULL_ORDER[: count - 1]) + ["final_line"] if count > 1 else ["hook"]

    middle_count = count - 2
    middle = [_MIDDLE_CYCLE[i % len(_MIDDLE_CYCLE)] for i in range(middle_count)]
    return ["hook", *middle, "final_line"]


def apply_narrative_beats(storyboard, target_seconds: int):
    scenes = list(storyboard.scenes)
    if not scenes:
        raise ValueError("Narrative Beat Engine requires at least one scene.")

    roles = _role_sequence(len(scenes))
    durations = allocate_durations(scenes, target_seconds)

    beats: list[NarrativeBeat] = []
    cursor = 0

    for scene, role, duration in zip(scenes, roles, durations):
        meta = BEAT_META[role]
        scene.start_second = cursor
        scene.end_second = cursor + duration
        scene.story_role = role
        scene.narrative_goal = meta["purpose"]
        scene.visual_emotion = meta["target_emotion"]
        scene.emotional_intensity = meta["intensity"]
        scene.pacing = meta["pacing"]
        scene.transition_type = meta["transition"]

        beats.append(
            NarrativeBeat(
                scene_number=int(scene.number),
                beat_name=role,
                purpose=meta["purpose"],
                target_emotion=meta["target_emotion"],
                intensity=meta["intensity"],
                pacing=meta["pacing"],
                transition=meta["transition"],
                caption_mode=meta["caption_mode"],
                target_duration=duration,
            )
        )
        cursor += duration

    scenes[-1].end_second = cursor  # already equals sum(durations) exactly
    storyboard.story_arc_summary = "Hook → Recognition → Conflict → Insight → Resolution → Final Reflection"
    return storyboard, beats
