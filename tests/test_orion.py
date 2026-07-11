from pathlib import Path

from app.orion.planner import build_mission, load_mission


def test_orion_creates_persistent_mission(tmp_path: Path):
    mission = build_mission(
        root=tmp_path,
        objective="Create a psychology series about comparison and identity",
        count=2,
        target_seconds=45,
    )

    assert mission["mission_id"].startswith("orion-")
    assert len(mission["items"]) <= 2
    assert load_mission(tmp_path, mission["mission_id"])["objective"] == mission["objective"]
