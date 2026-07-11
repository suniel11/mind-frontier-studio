from types import SimpleNamespace

from app.visual.shot_planner import plan_shots


def test_shot_planner_avoids_three_identical_visuals():
    roles = ["hook", "setup", "tension", "expansion", "climax", "resolution"]
    storyboard = SimpleNamespace(
        scenes=[SimpleNamespace(number=i, story_role=role) for i, role in enumerate(roles, start=1)]
    )
    shots = plan_shots(storyboard)
    assert len(shots) == 6
    for index in range(2, len(shots)):
        assert not (
            shots[index].visual_type
            == shots[index - 1].visual_type
            == shots[index - 2].visual_type
        )
