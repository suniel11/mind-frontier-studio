from pathlib import Path

from app.orchestrator.engine import build_autonomous_project
from app.orchestrator.store import get_project


def test_orchestrator_empty_state(tmp_path: Path):
    result = build_autonomous_project(
        tmp_path,
        topic="comparison",
        target_seconds=45,
        hook_type="question",
        save_workspace_enabled=True,
    )

    assert result["project_id"].startswith("orch-")
    assert "plan" in result
    assert "prediction" in result["plan"]

    stored = get_project(tmp_path, result["project_id"])
    assert stored is not None
    assert stored["steps"]
