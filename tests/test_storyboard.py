from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.storyboard import (
    SceneDraft,
    StoryboardDraft,
    _draft_to_storyboard,
    _draft_validator,
    run as storyboard_run,
)
from app.model_router import circuit_breaker, project_state, usage
from app.models import Scene, ShortScript, Storyboard, VisualMemory

# Fields the storyboard LLM is deliberately no longer asked to generate --
# each is either never read anywhere downstream, or unconditionally
# overwritten before any downstream code reads it (see the Storyboard
# Performance Audit report for the full field-by-field trace).
REMOVED_FIELDS = {
    "pacing",
    "transition_type",
    "lens_mm",
    "composition",
    "lighting_style",
    "color_tone",
    "focus_target",
    "film_look",
    "visual_type",
    "caption_safe_area",
    "visual_asset_group_id",
}

# Fields that genuinely survive to the render (or gate storyboard_validator's
# structural checks) and must keep being requested from the model.
KEPT_FIELDS = {
    "number",
    "start_second",
    "end_second",
    "narration",
    "on_screen_text",
    "visual_direction",
    "image_prompt",
    "story_role",
    "narrative_goal",
    "continuity_anchor",
    "location_id",
    "emotional_intensity",
    "subject_focus",
    "shot_type",
    "motion_type",
    "visual_emotion",
    "caption_emphasis",
}


@pytest.fixture(autouse=True)
def _clean_state():
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()
    yield
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()


def _visual_memory() -> VisualMemory:
    return VisualMemory(
        primary_location="a research vessel deck at dusk",
        secondary_location="a dim control room lit by monitors",
        recurring_props=["a weathered logbook", "a brass compass"],
        architecture_and_environment="steel hull, narrow corridors",
        time_of_day="dusk",
        weather_and_atmosphere="calm sea, light mist",
        color_palette="deep blues and amber highlights",
        lighting_language="directional practicals with soft fill",
        lens_language="35mm, shallow depth of field",
        production_design_anchor="analog instruments, worn brass fittings",
        continuity_rules=["compass stays in frame when present"],
    )


def _scene_draft(number: int, *, story_role: str, start: int, end: int) -> SceneDraft:
    return SceneDraft(
        number=number,
        start_second=start,
        end_second=end,
        narration=f"Narration text unique to scene {number} about the deep ocean.",
        on_screen_text="",
        visual_direction=f"Editor direction for scene {number}.",
        image_prompt=f"A cinematic still describing scene {number} in detail.",
        story_role=story_role,
        narrative_goal="Make the viewer feel curious.",
        continuity_anchor="brass compass visible on the console",
        location_id="primary",
        emotional_intensity=6,
        subject_focus="the compass",
        shot_type="wide" if number % 2 == 0 else "close_up",
        motion_type="dolly_in",
        visual_emotion="curiosity",
        caption_emphasis="",
    )


def _storyboard_draft(scene_count: int = 6, target_seconds: int = 45) -> StoryboardDraft:
    roles = ["hook"] + ["setup", "conflict", "insight", "resolution"] * scene_count
    roles = roles[: scene_count - 1] + ["final_line"]
    per_scene = target_seconds // scene_count
    scenes = []
    cursor = 0
    for index in range(scene_count):
        end = cursor + per_scene if index < scene_count - 1 else target_seconds
        scenes.append(_scene_draft(index + 1, story_role=roles[index], start=cursor, end=end))
        cursor = end
    return StoryboardDraft(
        visual_memory=_visual_memory(),
        story_arc_summary="Hook, deepen the mystery, resolve with a memorable final line.",
        scenes=scenes,
    )


def _script() -> ShortScript:
    return ShortScript(
        title="The Deep",
        hook="What lies beneath?",
        voiceover="A long voiceover describing the deep ocean and its mysteries.",
        ending="The deep still keeps its secrets.",
        estimated_seconds=45,
    )


# ---------------------------------------------------------------------------
# Schema audit: the wire schema sent to the model must omit exactly the
# fields that are dead or fully recomputed downstream, and keep everything
# else -- this is the regression test that guards the field-removal decision
# itself, independent of any live model call.
# ---------------------------------------------------------------------------


def test_slim_schema_omits_dead_and_overwritten_fields():
    scene_schema = StoryboardDraft.model_json_schema()["$defs"]["SceneDraft"]
    properties = set(scene_schema["properties"])

    assert properties.isdisjoint(REMOVED_FIELDS), (
        "SceneDraft must never ask the model for a field that is dead or "
        f"unconditionally overwritten downstream: {properties & REMOVED_FIELDS}"
    )
    assert KEPT_FIELDS <= properties, (
        f"SceneDraft dropped a field that genuinely has a downstream reader: "
        f"{KEPT_FIELDS - properties}"
    )
    # No stray fields beyond the two known sets -- catches accidental drift
    # (e.g. someone adding a brand-new Scene field without deciding whether
    # the model should be asked to produce it).
    assert properties == KEPT_FIELDS


def test_removed_fields_are_not_in_the_required_list():
    scene_schema = StoryboardDraft.model_json_schema()["$defs"]["SceneDraft"]
    required = set(scene_schema.get("required", []))
    assert required.isdisjoint(REMOVED_FIELDS)


def test_slim_schema_is_smaller_than_the_full_scene_schema():
    import json

    old_size = len(json.dumps(Storyboard.model_json_schema()))
    new_size = len(json.dumps(StoryboardDraft.model_json_schema()))
    assert new_size < old_size, (
        "the slimmed wire schema regressed to be the same size as (or "
        "larger than) the full Scene schema -- check for a reintroduced "
        "docstring or field"
    )


# ---------------------------------------------------------------------------
# Conversion correctness: removed fields must take Scene's own Python
# defaults (exactly what they'd be overwritten to downstream regardless of
# what the LLM said), and every kept field must survive unchanged.
# ---------------------------------------------------------------------------


def test_draft_to_storyboard_fills_removed_fields_with_scene_defaults():
    draft = _storyboard_draft()
    storyboard = _draft_to_storyboard(draft)

    default_scene = Scene(
        number=0, start_second=0, end_second=0, narration="", on_screen_text="",
        visual_direction="", image_prompt="",
    )
    for scene in storyboard.scenes:
        for field in REMOVED_FIELDS:
            assert getattr(scene, field) == getattr(default_scene, field), (
                f"{field} should carry Scene's own default, not something "
                "invented by the draft-to-storyboard conversion"
            )


def test_draft_to_storyboard_preserves_kept_fields():
    draft = _storyboard_draft()
    storyboard = _draft_to_storyboard(draft)

    for draft_scene, scene in zip(draft.scenes, storyboard.scenes):
        for field in KEPT_FIELDS:
            assert getattr(scene, field) == getattr(draft_scene, field)

    assert storyboard.story_arc_summary == draft.story_arc_summary
    assert storyboard.visual_memory == draft.visual_memory


def test_draft_to_storyboard_produces_a_real_storyboard_instance():
    storyboard = _draft_to_storyboard(_storyboard_draft())
    assert isinstance(storyboard, Storyboard)
    assert all(isinstance(scene, Scene) for scene in storyboard.scenes)


# ---------------------------------------------------------------------------
# Validator still enforces structure against the draft (before conversion),
# via _draft_validator's on-the-fly conversion.
# ---------------------------------------------------------------------------


def test_draft_validator_passes_a_well_formed_draft():
    draft = _storyboard_draft(scene_count=6, target_seconds=45)
    result = _draft_validator(target_seconds=45)(draft)
    assert result.passed, result.reasons


def test_draft_validator_still_catches_a_missing_hook():
    draft = _storyboard_draft(scene_count=6, target_seconds=45)
    draft.scenes[0].story_role = "setup"  # not "hook"
    result = _draft_validator(target_seconds=45)(draft)
    assert not result.passed
    assert any("hook" in reason for reason in result.reasons)


def test_draft_validator_still_catches_shot_type_uniformity():
    draft = _storyboard_draft(scene_count=6, target_seconds=45)
    for scene in draft.scenes:
        scene.shot_type = "medium"
    result = _draft_validator(target_seconds=45)(draft)
    assert not result.passed
    assert any("shot_type" in reason for reason in result.reasons)


# ---------------------------------------------------------------------------
# End-to-end: storyboard.run() must send the slim schema to the model (not
# the full Scene schema) and return a genuine, fully-populated Storyboard.
# ---------------------------------------------------------------------------


class _ResponsesStub:
    def __init__(self, parsed, *, input_tokens=900, output_tokens=250):
        self._parsed = parsed
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        usage_obj = SimpleNamespace(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
        )
        return SimpleNamespace(output_parsed=self._parsed, usage=usage_obj)


class _FakeClient:
    def __init__(self, stub):
        self.responses = stub


def test_run_sends_the_slim_schema_not_the_full_scene_schema(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-storyboard-schema")

    draft = _storyboard_draft(scene_count=6, target_seconds=45)
    stub = _ResponsesStub(draft)
    monkeypatch.setattr("app.services.openai_client.get_openai_client", lambda: _FakeClient(stub))

    storyboard_run(_script(), 45, None, production_specification=None)

    assert stub.calls, "storyboard.run() never actually called the model"
    assert stub.calls[0]["text_format"] is StoryboardDraft
    assert stub.calls[0]["text_format"] is not Storyboard


def test_run_returns_a_fully_populated_storyboard(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-storyboard-output")

    draft = _storyboard_draft(scene_count=6, target_seconds=45)
    stub = _ResponsesStub(draft)
    monkeypatch.setattr("app.services.openai_client.get_openai_client", lambda: _FakeClient(stub))

    storyboard = storyboard_run(_script(), 45, None, production_specification=None)

    assert isinstance(storyboard, Storyboard)
    assert len(storyboard.scenes) == 6
    assert storyboard.scenes[0].story_role == "hook"
    assert storyboard.scenes[-1].story_role == "final_line"
    # Removed fields are present (Scene still carries them for downstream
    # stages) but hold Scene's own defaults, never model-invented values.
    assert storyboard.scenes[0].pacing == "medium"
    assert storyboard.scenes[0].transition_type == "fade"
    assert storyboard.scenes[0].visual_type == "character_action"
    # Kept, genuinely-consumed fields carry the model's real output through.
    assert "scene 1" in storyboard.scenes[0].narration.lower()
    assert storyboard.scenes[0].continuity_anchor == "brass compass visible on the console"


def test_run_falls_back_to_baseline_when_draft_fails_validation(monkeypatch):
    # "standard" (not "studio") so STORYBOARD actually resolves to a
    # lower-cost attempted model distinct from the baseline -- otherwise
    # there is nothing left to fall back to and only one call is made.
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-storyboard-fallback")

    bad_draft = _storyboard_draft(scene_count=6, target_seconds=45)
    bad_draft.scenes[0].story_role = "setup"  # fails validate_storyboard
    good_draft = _storyboard_draft(scene_count=6, target_seconds=45)

    stub = _ResponsesStub(bad_draft)
    # Second call (baseline fallback) should get a well-formed draft.
    original_parse = stub.parse

    def _parse(**kwargs):
        result = original_parse(**kwargs)
        stub._parsed = good_draft
        return result

    stub.parse = _parse
    monkeypatch.setattr("app.services.openai_client.get_openai_client", lambda: _FakeClient(stub))

    storyboard = storyboard_run(_script(), 45, None, production_specification=None)

    assert len(stub.calls) == 2, "a failed validation must trigger exactly one baseline retry"
    assert storyboard.scenes[0].story_role == "hook"
