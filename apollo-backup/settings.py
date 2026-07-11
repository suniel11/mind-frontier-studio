from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    projects_dir: Path
    static_dir: Path
    app_name: str = "Mind Frontier Studio"
    version: str = "16.0.0-orion"


ROOT = Path(__file__).resolve().parents[2]

settings = Settings(
    root=ROOT,
    projects_dir=ROOT / "projects",
    static_dir=ROOT / "static",
)

settings.projects_dir.mkdir(parents=True, exist_ok=True)
