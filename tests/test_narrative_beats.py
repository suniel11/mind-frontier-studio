from types import SimpleNamespace

from app.narrative.beats import apply_narrative_beats


def test_narrative_beats_cover_full_duration():
    storyboard = SimpleNamespace(
        scenes=[SimpleNamespace(number=i) for i in range(1, 7)],
        story_arc_summary="",
    )
    storyboard, beats = apply_narrative_beats(storyboard, 45)

    assert len(beats) == 6
    assert storyboard.scenes[0].start_second == 0
    assert storyboard.scenes[-1].end_second == 45
    assert sum(beat.target_duration for beat in beats) == 45
