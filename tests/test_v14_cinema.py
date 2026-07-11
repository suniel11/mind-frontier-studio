from types import SimpleNamespace

from app.cinema.director import apply_cinematic_direction


def test_cinematic_direction_produces_variety():
    roles = ["hook", "setup", "conflict", "insight", "resolution", "final_line"]
    scenes = [
        SimpleNamespace(
            number=index + 1,
            story_role=role,
            emotional_intensity=6,
            start_second=index * 5,
            end_second=(index + 1) * 5,
            visual_direction="",
        )
        for index, role in enumerate(roles)
    ]
    storyboard = SimpleNamespace(scenes=scenes)

    storyboard, report = apply_cinematic_direction(storyboard)

    assert report.cinema_score >= 70
    assert len({scene.motion_type for scene in storyboard.scenes}) >= 4
    assert len({scene.shot_type for scene in storyboard.scenes}) >= 4
