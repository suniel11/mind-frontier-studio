from pathlib import Path
import json

from app.projects.manager import dashboard_stats, list_projects


def test_dashboard_lists_projects(tmp_path: Path):
    project = tmp_path / "demo-project"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"script": {"title": "Demo Project"}, "topic": "demo"}),
        encoding="utf-8",
    )
    (project / "quality-report.json").write_text(
        json.dumps({"overall_score": 91, "publish_ready": True}),
        encoding="utf-8",
    )
    (project / "mind-frontier-short.mp4").write_bytes(b"")

    projects = list_projects(tmp_path)
    assert len(projects) == 1
    assert projects[0]["title"] == "Demo Project"
    assert projects[0]["quality_score"] == 91
    assert dashboard_stats(projects)["ready_projects"] == 1
