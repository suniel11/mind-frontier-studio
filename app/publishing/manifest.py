from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write_release_manifest(
    project_dir: Path,
    version: str,
    project_id: str,
    video_path: Path,
    thumbnail_path: Path,
    quality_report_path: Path,
) -> Path:
    manifest = {
        "version": version,
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video": str(video_path),
        "thumbnail": str(thumbnail_path),
        "quality_report": str(quality_report_path),
        "status": "ready_for_review",
    }

    path = project_dir / "release-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
