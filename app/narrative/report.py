from __future__ import annotations

import json
from pathlib import Path


def save_beat_map(project_dir: Path, beats) -> Path:
    path = project_dir / "narrative-beat-map.json"
    path.write_text(
        json.dumps({"beats": [beat.model_dump() for beat in beats]}, indent=2),
        encoding="utf-8",
    )
    return path
