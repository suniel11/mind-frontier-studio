from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CinematicShot:
    scene_number: int
    story_role: str
    shot_type: str
    motion_type: str
    lens_mm: int
    composition: str
    lighting: str
    color_tone: str
    focus_target: str
    intensity: int
    duration: float

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CinemaReport:
    cinema_score: int
    movement_score: int
    shot_variety_score: int
    rhythm_score: int
    emotion_score: int
    composition_score: int
    shots: list[CinematicShot]

    def model_dump(self) -> dict[str, Any]:
        return {
            "cinema_score": self.cinema_score,
            "movement_score": self.movement_score,
            "shot_variety_score": self.shot_variety_score,
            "rhythm_score": self.rhythm_score,
            "emotion_score": self.emotion_score,
            "composition_score": self.composition_score,
            "shots": [shot.model_dump() for shot in self.shots],
        }
