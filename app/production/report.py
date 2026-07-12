from __future__ import annotations

import json
from pathlib import Path

from app.production.validation import ValidationReport


def save_production_report(project_dir: Path, report: ValidationReport) -> Path:
    path = project_dir / "production-report.json"
    path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    return path
