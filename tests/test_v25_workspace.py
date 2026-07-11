from pathlib import Path

from app.workspace.orchestrator import build_workspace_brief
from app.workspace.store import get_workspace, save_workspace


def test_workspace_build_and_save(tmp_path: Path):
    brief = build_workspace_brief(
        tmp_path,
        "comparison",
        45,
        "question",
    )

    assert "prediction" in brief
    assert "producer" in brief
    assert "thumbnail" in brief

    saved = save_workspace(
        tmp_path,
        "comparison",
        45,
        "question",
        "test notes",
        brief,
    )

    loaded = get_workspace(tmp_path, saved["workspace_id"])
    assert loaded is not None
    assert loaded["topic"] == "comparison"
