from __future__ import annotations

import json
from pathlib import Path


def save_cinema_report(project_dir: Path, report) -> Path:
    path = project_dir / "cinema-report.json"
    path.write_text(
        json.dumps(report.model_dump(), indent=2),
        encoding="utf-8",
    )
    return path
