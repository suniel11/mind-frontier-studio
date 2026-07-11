from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


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


BEAT_TEMPLATE = [
    {"beat_name": "hook", "purpose": "Stop the scroll with a provocative idea or unresolved question.", "target_emotion": "curiosity", "intensity": 7, "pacing": "fast", "transition": "cut", "caption_mode": "hook", "weight": 0.11},
    {"beat_name": "setup", "purpose": "Make the viewer recognize the problem in their own life.", "target_emotion": "recognition", "intensity": 5, "pacing": "medium", "transition": "cut", "caption_mode": "standard", "weight": 0.17},
    {"beat_name": "conflict", "purpose": "Expose the hidden cost, contradiction, or uncomfortable truth.", "target_emotion": "discomfort", "intensity": 8, "pacing": "fast", "transition": "cut", "caption_mode": "emphasis", "weight": 0.18},
    {"beat_name": "insight", "purpose": "Reveal the central explanation or shift in perspective.", "target_emotion": "realization", "intensity": 8, "pacing": "medium", "transition": "dissolve", "caption_mode": "emphasis", "weight": 0.20},
    {"beat_name": "resolution", "purpose": "Show the practical or philosophical way forward.", "target_emotion": "hope", "intensity": 6, "pacing": "slow", "transition": "fade", "caption_mode": "standard", "weight": 0.22},
    {"beat_name": "final_line", "purpose": "Leave one concise sentence the viewer remembers.", "target_emotion": "reflection", "intensity": 7, "pacing": "hold", "transition": "hold", "caption_mode": "resolution", "weight": 0.12},
]


def _allocate_durations(target_seconds: int) -> list[int]:
    durations = [max(2, round(target_seconds * beat["weight"])) for beat in BEAT_TEMPLATE]
    difference = target_seconds - sum(durations)
    index = 0

    while difference != 0:
        direction = 1 if difference > 0 else -1
        slot = index % len(durations)
        candidate = durations[slot] + direction
        if candidate >= 2:
            durations[slot] = candidate
            difference -= direction
        index += 1

    return durations


def apply_narrative_beats(storyboard, target_seconds: int):
    scenes = list(storyboard.scenes)
    if len(scenes) != 6:
        raise ValueError(f"Narrative Beat Engine expects exactly 6 scenes, found {len(scenes)}.")

    durations = _allocate_durations(target_seconds)
    beats: list[NarrativeBeat] = []
    cursor = 0

    for scene, template, duration in zip(scenes, BEAT_TEMPLATE, durations):
        scene.start_second = cursor
        scene.end_second = cursor + duration
        scene.story_role = template["beat_name"]
        scene.narrative_goal = template["purpose"]
        scene.visual_emotion = template["target_emotion"]
        scene.emotional_intensity = template["intensity"]
        scene.pacing = template["pacing"]
        scene.transition_type = template["transition"]

        beats.append(
            NarrativeBeat(
                scene_number=int(scene.number),
                beat_name=template["beat_name"],
                purpose=template["purpose"],
                target_emotion=template["target_emotion"],
                intensity=template["intensity"],
                pacing=template["pacing"],
                transition=template["transition"],
                caption_mode=template["caption_mode"],
                target_duration=duration,
            )
        )
        cursor += duration

    scenes[-1].end_second = target_seconds
    storyboard.story_arc_summary = "Hook → Recognition → Conflict → Insight → Resolution → Final Reflection"
    return storyboard, beats
