from pathlib import Path
import json

from app.atlas.analytics import dashboard_data
from app.atlas.registry import sync_project_library


def test_atlas_syncs_project(tmp_path: Path):
    project = tmp_path / "projects" / "demo"
    project.mkdir(parents=True)

    (project / "project.json").write_text(
        json.dumps({
            "topic": "comparison psychology",
            "script": {
                "title": "The Quiet Damage of Comparison",
                "estimated_seconds": 45
            }
        }),
        encoding="utf-8",
    )
    (project / "quality-report.json").write_text(
        json.dumps({"overall_score": 91, "publish_ready": True}),
        encoding="utf-8",
    )
    (project / "cinema-report.json").write_text(
        json.dumps({"cinema_score": 88}),
        encoding="utf-8",
    )

    assert sync_project_library(tmp_path, "14.0.0") == 1

    data = dashboard_data(tmp_path)
    assert data["summary"]["total_projects"] == 1
    assert data["projects"][0]["quality_score"] == 91
    assert data["projects"][0]["category"] == "psychology"
