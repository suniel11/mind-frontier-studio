"""Local, non-sensitive Creative Director preference memory."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.settings import settings
from app.production.specification import ProductionSpecification


PreferenceText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class CreatorPreferences(BaseModel):
    """Stable production choices safe to reuse across unrelated projects."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_seconds: int | None = Field(default=None, ge=20, le=180)
    aspect_ratio: str | None = Field(default=None, pattern=r"^(9:16|16:9|1:1|4:5)$")
    tone: PreferenceText | None = None
    visual_style: PreferenceText | None = None
    narration_style: PreferenceText | None = None
    caption_style: PreferenceText | None = None
    music_preference: PreferenceText | bool | None = None
    narrator_gender: str | None = Field(default=None, pattern=r"^(male|female)$")
    narrator_tone: PreferenceText | None = None
    narrator_style: PreferenceText | None = None

    def populated(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True)


class PreferenceStore:
    """Atomic JSON store suitable for the single-user desktop application."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (
            settings.root / "studio_memory" / "creative-director-preferences.json"
        )
        self._lock = threading.RLock()

    def load(self) -> CreatorPreferences:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                return CreatorPreferences.model_validate(payload)
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
                return CreatorPreferences()

    def replace(self, preferences: CreatorPreferences) -> CreatorPreferences:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary.write_text(
                json.dumps(preferences.populated(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary.replace(self.path)
            return preferences

    def update(self, values: dict[str, object]) -> CreatorPreferences:
        current = self.load().model_dump()
        current.update(values)
        return self.replace(CreatorPreferences.model_validate(current))

    def clear(self) -> None:
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def remember_successful_production(
        self,
        specification: ProductionSpecification,
    ) -> CreatorPreferences:
        """Persist only reusable direction after a production succeeds."""

        values = {
            "target_seconds": specification.target_seconds,
            "aspect_ratio": specification.aspect_ratio,
            "tone": specification.tone,
            "visual_style": specification.visual_style,
            "narration_style": specification.narration_style,
            "caption_style": specification.caption_style,
            "music_preference": specification.music_direction,
            "narrator_gender": specification.preferences.narrator.gender,
            "narrator_tone": specification.preferences.narrator.tone,
            "narrator_style": specification.preferences.narrator.style,
        }
        return self.update({key: value for key, value in values.items() if value is not None})


preference_store = PreferenceStore()


def remember_successful_production(
    specification: ProductionSpecification,
) -> CreatorPreferences:
    """Public integration hook used by the production-job service on success."""

    return preference_store.remember_successful_production(specification)

