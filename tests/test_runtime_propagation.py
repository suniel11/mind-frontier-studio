from types import SimpleNamespace

from app.models import ShortScript
from app.narrative.beats import apply_narrative_beats
from app.narrative.duration_planning import (
    allocate_durations,
    duration_within_tolerance,
    retime_scenes,
    scenes_for_duration,
)
from app.production.voice_timing import synthesize_narration


def _script(words: int) -> ShortScript:
    voiceover = " ".join(f"word{i}" for i in range(words))
    return ShortScript(title="T", hook="H?", voiceover=voiceover, ending="E", estimated_seconds=45)


def test_default_duration_still_yields_six_scenes():
    # The original fixed-six-scene behavior must be unchanged at the
    # template's own baseline (45s / 7.5s per scene == 6).
    assert scenes_for_duration(45) == 6


def test_longer_target_creates_more_scenes_instead_of_stretching_a_few():
    assert scenes_for_duration(120) > scenes_for_duration(45)
    assert scenes_for_duration(240) > scenes_for_duration(120)
    # bounded, not unbounded
    assert scenes_for_duration(10_000) <= 24


def test_120_second_request_lands_within_tolerance_after_one_retry():
    # Reproduces the reported bug directly: a script sized for ~28s of
    # narration against a 120s target. The reconciliation loop must resize
    # the script and land close to 120s -- not silently ship a 28s video.
    measured_durations = iter([28.0, 118.0])
    attempts = {"count": 0}

    def fake_synthesize(script, path):
        attempts["count"] += 1

    def fake_probe(path):
        return next(measured_durations)

    def fake_resize(script, target_words):
        return _script(target_words)

    original = _script(70)
    final_script, measured = synthesize_narration(
        original,
        target_seconds=120,
        output_path="unused",
        synthesize=fake_synthesize,
        probe_duration=fake_probe,
        resize_script=fake_resize,
    )

    assert attempts["count"] == 2
    assert duration_within_tolerance(measured, 120, tolerance=0.05)
    assert measured == 118.0


def test_reconciliation_stops_immediately_when_already_within_tolerance():
    def fake_synthesize(script, path):
        pass

    def fake_probe(path):
        return 121.0

    def fake_resize(script, target_words):
        raise AssertionError("resize should not be called when already within tolerance")

    _, measured = synthesize_narration(
        _script(260),
        target_seconds=120,
        output_path="unused",
        synthesize=fake_synthesize,
        probe_duration=fake_probe,
        resize_script=fake_resize,
    )
    assert measured == 121.0


def test_retime_scenes_matches_measured_narration_duration_exactly():
    count = scenes_for_duration(120)
    scenes = [
        SimpleNamespace(number=i, narration="word " * (i * 3), start_second=0, end_second=0)
        for i in range(1, count + 1)
    ]
    storyboard = SimpleNamespace(scenes=scenes)

    retime_scenes(storyboard, 118.0)

    assert storyboard.scenes[0].start_second == 0
    assert storyboard.scenes[-1].end_second == 118
    total = sum(s.end_second - s.start_second for s in storyboard.scenes)
    assert total == 118


def test_scene_durations_are_weighted_by_narration_length_when_present():
    scenes = [
        SimpleNamespace(number=1, narration="one two three"),
        SimpleNamespace(number=2, narration=" ".join(["word"] * 30)),
    ]
    durations = allocate_durations(scenes, 40)
    # The scene with ~10x more narration should get meaningfully more time.
    assert durations[1] > durations[0]
    assert sum(durations) == 40


def test_apply_narrative_beats_generalizes_beyond_six_scenes():
    scenes = [SimpleNamespace(number=i, narration="") for i in range(1, 13)]
    storyboard = SimpleNamespace(scenes=scenes, story_arc_summary="")

    storyboard, beats = apply_narrative_beats(storyboard, 90)

    assert len(beats) == 12
    assert storyboard.scenes[0].story_role == "hook"
    assert storyboard.scenes[-1].story_role == "final_line"
    for scene in storyboard.scenes[1:-1]:
        assert scene.story_role in {"setup", "conflict", "insight", "resolution"}
    assert storyboard.scenes[0].start_second == 0
    assert storyboard.scenes[-1].end_second == 90
    assert sum(beat.target_duration for beat in beats) == 90
