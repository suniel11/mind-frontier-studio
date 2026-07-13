from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.narration.voice_selection import VoiceSelection


@dataclass
class NarrationReport:
    requested: dict[str, Any]
    selected_voice: str
    style: str | None
    tone: str | None
    pace: str | None
    provider: str
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def build_narration_report(
    preferences,
    voice_selection: VoiceSelection,
    *,
    provider: str = "openai",
) -> NarrationReport:
    narrator = getattr(preferences, "narrator", None)
    requested = narrator.model_dump(exclude_none=True) if narrator is not None else {}
    return NarrationReport(
        requested=requested,
        selected_voice=voice_selection.voice,
        style=getattr(narrator, "style", None),
        tone=getattr(narrator, "tone", None),
        pace=getattr(narrator, "pace", None),
        provider=provider,
        warnings=list(voice_selection.warnings),
    )


def save_narration_report(project_dir: Path, report: NarrationReport) -> Path:
    path = project_dir / "narration-report.json"
    path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    return path
