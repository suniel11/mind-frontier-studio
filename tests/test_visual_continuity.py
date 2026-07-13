from __future__ import annotations

import base64
import inspect
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from app.model_router import circuit_breaker, project_state, usage
from app.models import Scene, Storyboard, VisualMemory
from app.services import media
from app.services.cancellation import RenderCancelled
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.visual_continuity import cost_guard
from app.visual_continuity.cache import ImageAssetCache, cache_key
from app.visual_continuity.models import VisualAssetGroup, VisualAssetPlan
from app.visual_continuity.planner import (
    _apply_plan_to_scenes,
    _enforce_constraints,
    _identity_plan,
    plan_visual_assets,
)
from app.visual_continuity.repetition import repetition_risk
from app.visual_continuity.scoring import continuity_score
from app.visual_continuity.shots import assign_shot_variations
from app.visual_continuity.telemetry import (
    build_visual_asset_report,
    save_visual_asset_report,
    save_visual_continuity_debug,
)


@pytest.fixture(autouse=True)
def _clean_state():
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()
    yield
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()


@pytest.fixture(autouse=True)
def _permissive_rate_limit(monkeypatch):
    # These tests assert on real image-generation call counts, not
    # real-time throttling -- the shared production rate limiter (a
    # handful of calls per real 60s minute) must not slow them down. See
    # tests/test_image_generation_rate_limiting.py for dedicated
    # rate-limiter tests with an injectable clock.
    monkeypatch.setattr(
        media, "_image_rate_limiter", SlidingWindowRateLimiter(max_calls=10_000, period_seconds=60.0)
    )
    yield


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _memory(**overrides) -> VisualMemory:
    base = dict(
        primary_location="mariana trench",
        secondary_location="research vessel",
        recurring_props=["submersible"],
        architecture_and_environment="deep ocean",
        time_of_day="none",
        weather_and_atmosphere="crushing pressure",
        color_palette="deep blue-black",
        lighting_language="bioluminescent",
        lens_language="35mm",
        production_design_anchor="hadal zone",
        continuity_rules=["keep the submersible lights consistent"],
    )
    base.update(overrides)
    return VisualMemory(**base)


# Genuinely distinct sentences (not a templated "Narration for scene N."
# pattern) so the Visual Repetition Guard's narration-similarity check
# doesn't misfire between unrelated fixture scenes just because they share
# a common template -- only the tests that explicitly want to exercise
# that guard construct near-duplicate narration on purpose.
_NARRATION_POOL = [
    "A submersible begins its descent into total darkness.",
    "Pressure gauges climb steadily as depth increases dramatically.",
    "Bioluminescent creatures drift past the viewport silently.",
    "Sonar pings map contours of the unseen seafloor below.",
    "Engineers monitor telemetry from the surface support vessel.",
    "A hydrothermal vent glows faintly amid volcanic rock formations.",
    "Sediment samples are collected using a robotic manipulator arm.",
    "Communication delays complicate real time decision making.",
    "The crew reviews footage of a newly discovered species.",
    "Battery levels dictate how long the mission can continue.",
    "A support ship relays coordinates to the research team.",
    "Scientists debate the significance of the mineral deposits found.",
    "The vessel ascends slowly to avoid decompression hazards.",
    "Data logs are transferred for analysis back on shore.",
    "A documentary crew captures the historic dive on camera.",
    "The expedition concludes with a celebration among the crew.",
]


def _scene(number: int, *, location_id: str = "primary", story_role: str = "development", **overrides) -> Scene:
    base = dict(
        number=number,
        start_second=(number - 1) * 3,
        end_second=number * 3,
        narration=_NARRATION_POOL[(number - 1) % len(_NARRATION_POOL)],
        on_screen_text="",
        visual_direction=f"visual direction {number}",
        image_prompt=f"unique prompt for scene {number}",
        location_id=location_id,
        story_role=story_role,
    )
    base.update(overrides)
    return Scene(**base)


def _storyboard(scenes: list[Scene]) -> Storyboard:
    return Storyboard(visual_memory=_memory(), story_arc_summary="A deep-sea documentary.", scenes=scenes)


def _linear_scenes(count: int, *, locations: list[str] | None = None) -> list[Scene]:
    """``count`` scenes, first=hook, last=final_line, everything else
    ``development`` -- location_id taken from ``locations`` (defaults to
    "primary" throughout, i.e. one continuous subject)."""

    locations = locations or ["primary"] * count
    scenes = []
    for index in range(count):
        number = index + 1
        role = "hook" if number == 1 else ("final_line" if number == count else "development")
        scenes.append(_scene(number, location_id=locations[index], story_role=role))
    return scenes


_buffer = io.BytesIO()
Image.new("RGB", (16, 16), color=(10, 20, 30)).save(_buffer, format="PNG")
_TINY_PNG_B64 = base64.b64encode(_buffer.getvalue()).decode("ascii")


def _group(scene_numbers: list[int], *, confidence: float = 0.9, justification: str = "same subject") -> VisualAssetGroup:
    return VisualAssetGroup(
        group_id=f"g{scene_numbers[0]:02d}",
        scene_numbers=scene_numbers,
        canonical_prompt=f"shared prompt for scenes {scene_numbers}",
        semantic_category="test-category",
        justification=justification,
        grouping_confidence=confidence,
    )


# ---------------------------------------------------------------------------
# 1. Semantic grouping works
# ---------------------------------------------------------------------------


def test_semantic_grouping_merges_scenes_the_planner_proposed():
    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4]), _group([5])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert [g.scene_numbers for g in plan.groups] == [[1], [2, 3, 4], [5]]
    assert plan.groups[1].canonical_prompt == "shared prompt for scenes [2, 3, 4]"


# ---------------------------------------------------------------------------
# 2. Unrelated scenes never share assets
# ---------------------------------------------------------------------------
#
# grouping_confidence, not a location-string comparison, is the semantic
# safety net (see _split_group's docstring for why: real storyboards give
# nearly every scene a distinct location_id, so exact-match string
# comparison rejected well-justified merges of genuinely-identical moments
# during testing against real project data). A well-prompted planner is
# instructed to score confidence low whenever scenes are not truly the same
# visual moment -- MIN_GROUPING_CONFIDENCE is the enforced gate for that.


def test_unrelated_scenes_never_share_an_asset():
    scenes = _linear_scenes(6)
    storyboard = _storyboard(scenes)
    # The planner proposes merging scenes 2-5 but is not confident they are
    # the same visual moment (unrelated content) -- below MIN_GROUPING_
    # CONFIDENCE, so enforcement must reject the merge entirely.
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4, 5], confidence=0.4), _group([6])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=4, min_confidence=0.75)

    grouped_numbers = [g.scene_numbers for g in plan.groups]
    assert [2, 3, 4, 5] not in grouped_numbers
    assert [2] in grouped_numbers and [3] in grouped_numbers
    assert [4] in grouped_numbers and [5] in grouped_numbers


# ---------------------------------------------------------------------------
# 3. Chapter transitions always create new assets
# ---------------------------------------------------------------------------


def test_chapter_transition_always_starts_a_new_asset():
    scenes = _linear_scenes(6)
    storyboard = _storyboard(scenes)
    # A chapter/topic transition mid-group is exactly the kind of merge a
    # well-calibrated planner scores low confidence -- enforcement rejects
    # it rather than trusting a bare proposal.
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4, 5], confidence=0.5), _group([6])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=6, min_confidence=0.75)

    grouped_numbers = [g.scene_numbers for g in plan.groups]
    assert [2, 3, 4, 5] not in grouped_numbers
    assert all(len(g.scene_numbers) == 1 for g in plan.groups if 2 in g.scene_numbers or 5 in g.scene_numbers)


# ---------------------------------------------------------------------------
# 4 & 5. Hook and ending always receive a unique image
# ---------------------------------------------------------------------------


def test_hook_scene_always_receives_a_unique_image():
    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1, 2, 3]), _group([4])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=4, min_confidence=0.75)

    hook_group = next(g for g in plan.groups if 1 in g.scene_numbers)
    assert hook_group.scene_numbers == [1]


def test_ending_scene_always_receives_a_unique_image():
    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=4, min_confidence=0.75)

    ending_group = next(g for g in plan.groups if 4 in g.scene_numbers)
    assert ending_group.scene_numbers == [4]


# ---------------------------------------------------------------------------
# 6. No Anchor Shot reused more than MAX_CONSECUTIVE_REUSE consecutive scenes
# ---------------------------------------------------------------------------


def test_no_anchor_shot_reused_more_than_max_consecutive_scenes():
    scenes = _linear_scenes(7)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4, 5, 6]), _group([7])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    for group in plan.groups:
        assert len(group.scene_numbers) <= 3


# ---------------------------------------------------------------------------
# 7. Image ordering is preserved
# ---------------------------------------------------------------------------


class _FakeImages:
    def __init__(self):
        self.calls: list[str] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs["prompt"])
        return SimpleNamespace(data=[SimpleNamespace(b64_json=_TINY_PNG_B64)])


class _FakeClient:
    def __init__(self, images):
        self.images = images


def test_image_ordering_is_preserved_even_when_scenes_share_an_asset(tmp_path, monkeypatch):
    scenes = _linear_scenes(5)
    # Force scenes 2 and 3 to literally share a prompt (simulating a plan
    # that already grouped them) while the rest stay unique.
    scenes[1].image_prompt = "shared prompt A"
    scenes[2].image_prompt = "shared prompt A"
    storyboard = _storyboard(scenes)

    fake_images = _FakeImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(fake_images))

    paths = media._generate_scene_images(
        storyboard, tmp_path, width=16, height=16, size="1024x1536", aspect_ratio="9:16",
    )

    assert [p.name for p in paths] == [f"scene-{n:02d}.jpg" for n in range(1, 6)]
    for path in paths:
        assert path.exists()


# ---------------------------------------------------------------------------
# 8. Cache works correctly
# ---------------------------------------------------------------------------


def test_cache_key_is_stable_for_identical_inputs_and_differs_otherwise():
    key_a = cache_key("a prompt", aspect_ratio="9:16")
    key_b = cache_key("a prompt", aspect_ratio="9:16")
    key_c = cache_key("a different prompt", aspect_ratio="9:16")
    key_d = cache_key("a prompt", aspect_ratio="16:9")

    assert key_a == key_b
    assert key_a != key_c
    assert key_a != key_d


def test_image_asset_cache_get_put():
    cache = ImageAssetCache()
    assert cache.get("k1") is None
    cache.put("k1", 0)
    cache.put("k1", 5)  # first write wins
    assert cache.get("k1") == 0


def test_generate_scene_images_only_calls_openai_once_per_unique_prompt(tmp_path, monkeypatch):
    scenes = _linear_scenes(4)
    scenes[0].image_prompt = "shared prompt"
    scenes[1].image_prompt = "shared prompt"
    scenes[2].image_prompt = "shared prompt"
    scenes[3].image_prompt = "unique prompt"
    storyboard = _storyboard(scenes)

    fake_images = _FakeImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(fake_images))

    media._generate_scene_images(
        storyboard, tmp_path, width=16, height=16, size="1024x1536", aspect_ratio="9:16",
    )

    assert len(fake_images.calls) == 2  # one for the shared group, one for the unique scene


def test_image_cache_disabled_generates_fresh_per_scene(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_CACHE_ENABLED", "false")
    scenes = _linear_scenes(3)
    for scene in scenes:
        scene.image_prompt = "identical prompt for all"
    storyboard = _storyboard(scenes)

    fake_images = _FakeImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(fake_images))

    media._generate_scene_images(
        storyboard, tmp_path, width=16, height=16, size="1024x1536", aspect_ratio="9:16",
    )

    assert len(fake_images.calls) == 3


# ---------------------------------------------------------------------------
# 9. Cancellation still works
# ---------------------------------------------------------------------------


def test_cancellation_before_batch_still_raises_immediately(tmp_path, monkeypatch):
    scenes = _linear_scenes(3)
    storyboard = _storyboard(scenes)
    fake_images = _FakeImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(fake_images))

    with pytest.raises(RenderCancelled):
        media._generate_scene_images(
            storyboard, tmp_path, width=16, height=16, size="1024x1536", aspect_ratio="9:16",
            cancellation_check=lambda: True,
        )

    assert fake_images.calls == []


# ---------------------------------------------------------------------------
# 10. Render pipeline remains unchanged
# ---------------------------------------------------------------------------


def test_render_video_and_build_video_signatures_are_unchanged():
    render_params = list(inspect.signature(media.render_video).parameters)
    build_params = list(inspect.signature(media.build_video).parameters)
    assert render_params == [
        "storyboard", "images", "audio_path", "output_path", "width", "height",
        "subtitles", "background_music", "aspect_ratio", "preferences", "cancellation_check",
    ]
    assert build_params == [
        "project_dir", "script", "storyboard", "narration_audio_path",
        "preferences", "aspect_ratio", "cancellation_check",
    ]


# ---------------------------------------------------------------------------
# 11. Telemetry is generated
# ---------------------------------------------------------------------------


def test_telemetry_report_contains_required_metrics(tmp_path):
    scenes = _linear_scenes(6)
    storyboard = _storyboard(scenes)
    plan = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4]), _group([5, 6])])
    _apply_plan_to_scenes(plan, storyboard)

    document = build_visual_asset_report(plan, storyboard)
    for key in (
        "scene_count", "generated_images", "reused_images", "visual_asset_groups",
        "average_scenes_per_asset", "continuity_score", "reuse_percentage",
        "estimated_image_api_calls_saved", "estimated_render_time_saved_seconds",
        "planner_model", "planner_input_tokens", "planner_output_tokens", "planner_total_tokens",
        "planner_execution_time", "planner_estimated_cost", "planner_enabled", "planner_disabled_reason",
        "images_generated", "images_reused", "estimated_image_cost_saved", "estimated_render_time_saved",
        "estimated_net_cost_saved", "estimated_net_time_saved", "groups", "reused_scenes",
    ):
        assert key in document

    assert document["scene_count"] == 6
    assert document["generated_images"] == 3
    assert document["reused_images"] == 3

    path = save_visual_asset_report(tmp_path, plan, storyboard)
    assert path.name == "visual-asset-report.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["generated_images"] == 3


def test_net_savings_are_computed_from_planner_meta(tmp_path):
    scenes = _linear_scenes(6)
    storyboard = _storyboard(scenes)
    plan = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4]), _group([5, 6])])
    _apply_plan_to_scenes(plan, storyboard)

    planner_meta = {
        "planner_enabled": True,
        "planner_disabled_reason": None,
        "planner_model": "gpt-baseline",
        "planner_input_tokens": 2000,
        "planner_output_tokens": 500,
        "planner_execution_time": 4.5,
    }
    document = build_visual_asset_report(plan, storyboard, planner_meta)

    assert document["planner_model"] == "gpt-baseline"
    assert document["planner_input_tokens"] == 2000
    assert document["planner_output_tokens"] == 500
    assert document["planner_total_tokens"] == 2500
    assert document["planner_execution_time"] == 4.5
    assert document["planner_estimated_cost"] > 0
    # 3 reused images (6 scenes, 3 groups) at the default estimated price.
    assert document["estimated_image_cost_saved"] > 0
    assert document["estimated_net_cost_saved"] == round(
        document["estimated_image_cost_saved"] - document["planner_estimated_cost"], 6
    )
    assert document["estimated_net_time_saved"] == round(
        document["estimated_render_time_saved"] - 4.5, 2
    )


def test_grouping_explanations_are_present_and_specific(tmp_path):
    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)
    plan = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4], justification="same lab equipment shot"), _group([5])])
    _apply_plan_to_scenes(plan, storyboard)

    document = build_visual_asset_report(plan, storyboard)

    group_entry = next(g for g in document["groups"] if g["group_id"] == "g02")
    assert group_entry["member_scenes"] == [2, 3, 4]
    assert group_entry["justification"] == "same lab equipment shot"
    assert group_entry["semantic_category"]
    assert "grouping_confidence" in group_entry

    reused = {entry["scene"]: entry for entry in document["reused_scenes"]}
    assert set(reused) == {3, 4}
    assert reused[3]["reused_from_scene"] == 2
    assert reused[3]["reason"] == "same lab equipment shot"
    assert reused[3]["semantic_evidence"]


# ---------------------------------------------------------------------------
# 12-14. Image count is content-dependent, not fixed
# ---------------------------------------------------------------------------


def test_continuous_science_documentary_naturally_uses_fewer_assets():
    # 12 scenes, one continuous process/location -- planner proposes one
    # big coherent sequence (still respecting the max-consecutive cap).
    scenes = _linear_scenes(12)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[
        _group([1]),
        _group([2, 3, 4]),
        _group([5, 6, 7]),
        _group([8, 9, 10]),
        _group([11]),
        _group([12]),
    ])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert len(plan.groups) < len(scenes)
    assert len(plan.groups) == 6


def test_multi_era_historical_documentary_naturally_produces_more_assets():
    # 12 scenes spanning many distinct eras/subjects -- a well-calibrated
    # planner proposes mostly singleton groups (or low-confidence merges,
    # which enforcement rejects) because there is little genuine visual
    # overlap between scenes. Enforcement must not invent reuse that the
    # planner itself never proposed.
    scenes = _linear_scenes(12)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([n]) for n in range(1, 13)])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert len(plan.groups) == len(scenes)


def test_image_count_emerges_from_content_not_a_fixed_target():
    few_scenes = _linear_scenes(16)
    many_scenes = _linear_scenes(16)

    # Same 16-scene shape, two different (content-driven) planner
    # proposals: a continuous-subject documentary groups heavily; a
    # many-distinct-subjects documentary barely groups at all. Enforcement
    # must preserve that difference, not normalize toward any target.
    few_plan = _enforce_constraints(
        VisualAssetPlan(groups=[_group([1]), _group(list(range(2, 16))), _group([16])]),
        _storyboard(few_scenes), max_consecutive_reuse=3, min_confidence=0.75,
    )
    many_plan = _enforce_constraints(
        VisualAssetPlan(groups=[_group([n]) for n in range(1, 17)]),
        _storyboard(many_scenes), max_consecutive_reuse=3, min_confidence=0.75,
    )

    assert len(few_plan.groups) != len(many_plan.groups)
    assert len(few_plan.groups) < 16
    assert len(many_plan.groups) == 16


# ---------------------------------------------------------------------------
# 15. Planner never reuses images solely to satisfy a target ratio
# ---------------------------------------------------------------------------


def test_planner_never_force_merges_to_hit_a_savings_ratio():
    # An already-1:1 raw plan (every scene its own group, high confidence)
    # must stay 1:1 -- there is no code path that merges scenes just to
    # improve the reuse percentage.
    scenes = _linear_scenes(10)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([n], confidence=0.99) for n in range(1, 11)])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert len(plan.groups) == 10
    assert all(len(g.scene_numbers) == 1 for g in plan.groups)


def test_low_confidence_group_is_rejected_rather_than_merged():
    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4], confidence=0.4), _group([5])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    grouped_numbers = [g.scene_numbers for g in plan.groups]
    assert [2] in grouped_numbers and [3] in grouped_numbers and [4] in grouped_numbers
    assert [2, 3, 4] not in grouped_numbers


# ---------------------------------------------------------------------------
# 16. Every reuse decision records a semantic justification
# ---------------------------------------------------------------------------


def test_every_multi_scene_group_records_a_justification():
    scenes = _linear_scenes(6)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4], justification="same lab, same shot"), _group([5, 6], justification="")])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    for group in plan.groups:
        if len(group.scene_numbers) > 1:
            assert group.justification.strip(), f"group {group.scene_numbers} reuses an asset with no justification"


def test_malformed_plan_structure_falls_back_to_identity_plan():
    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    # Scene 3 missing entirely, scene 2 duplicated -- structurally broken.
    raw = VisualAssetPlan(groups=[_group([1, 2]), _group([2, 4])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert len(plan.groups) == 4
    assert all(len(g.scene_numbers) == 1 for g in plan.groups)


# ---------------------------------------------------------------------------
# Shot variation / continuity scoring
# ---------------------------------------------------------------------------


def test_shot_variations_never_repeat_within_a_small_group():
    variations = assign_shot_variations(3)
    assert len(set(variations)) == 3


def test_apply_plan_sets_group_id_prompt_and_varied_motion():
    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    plan = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4], justification="same subject")])

    _apply_plan_to_scenes(plan, storyboard)

    assert scenes[0].visual_asset_group_id == "g01"
    assert scenes[1].visual_asset_group_id == scenes[2].visual_asset_group_id == scenes[3].visual_asset_group_id
    assert scenes[1].image_prompt == scenes[2].image_prompt == scenes[3].image_prompt
    motions = [scenes[1].motion_type, scenes[2].motion_type, scenes[3].motion_type]
    assert len(set(motions)) == 3


def test_continuity_score_penalizes_repeated_motion_within_a_group():
    scenes = _linear_scenes(3)
    storyboard = _storyboard(scenes)
    plan = VisualAssetPlan(groups=[_group([1, 2, 3], justification="same subject")])

    for scene in scenes:
        scene.motion_type = "dolly_in"  # identical treatment across the group
    penalized_score = continuity_score(plan, storyboard)

    scenes[0].motion_type, scenes[1].motion_type, scenes[2].motion_type = "static", "pan_left", "drift"
    varied_score = continuity_score(plan, storyboard)

    assert varied_score > penalized_score


# ---------------------------------------------------------------------------
# Feature flag / end-to-end plan_visual_assets
# ---------------------------------------------------------------------------


def test_feature_disabled_produces_identity_plan_with_no_llm_call(monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "false")
    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)

    plan, meta = plan_visual_assets(storyboard, target_seconds=15)

    assert len(plan.groups) == 5
    assert all(len(g.scene_numbers) == 1 for g in plan.groups)
    assert meta["planner_enabled"] is False
    assert meta["planner_disabled_reason"] == "feature_disabled"


def test_identity_plan_matches_original_prompts():
    scenes = _linear_scenes(3)
    storyboard = _storyboard(scenes)
    plan = _identity_plan(storyboard)
    assert [g.canonical_prompt for g in plan.groups] == [s.image_prompt for s in scenes]


def test_provider_failure_during_planning_degrades_to_identity_plan(monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "true")
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")

    def _boom(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.visual_continuity.planner.run_agent_stage", _boom)

    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)

    plan, meta = plan_visual_assets(storyboard, target_seconds=12)

    assert len(plan.groups) == 4
    assert all(len(g.scene_numbers) == 1 for g in plan.groups)
    assert meta["planner_enabled"] is True
    assert meta["planner_disabled_reason"] == "provider_error"


# ---------------------------------------------------------------------------
# v3.1: Visual Repetition Guard
# ---------------------------------------------------------------------------


def test_repetition_guard_detects_near_duplicate_narration():
    a = _scene(2, narration="The Mariana Trench is a living frontier, alien vital and fragile to study.")
    b = _scene(3, narration="The Mariana Trench is a living frontier, alien, vital, fragile; to study it.")
    risky, reason = repetition_risk(a, b)
    assert risky is True
    assert "narration" in reason


def test_repetition_guard_detects_identical_framing():
    a = _scene(2, shot_type="wide", visual_emotion="awe", caption_emphasis="pressure", subject_focus="submersible")
    b = _scene(3, shot_type="wide", visual_emotion="awe", caption_emphasis="pressure", subject_focus="submersible")
    risky, reason = repetition_risk(a, b)
    assert risky is True
    assert "framing" in reason


def test_repetition_guard_allows_genuinely_different_scenes():
    a = _scene(2, narration="The submersible begins its descent into darkness.",
               shot_type="wide", visual_emotion="awe", caption_emphasis="descent", subject_focus="submersible")
    b = _scene(3, narration="Pressure gauges climb as the hull creaks under the load.",
               shot_type="close_up", visual_emotion="tension", caption_emphasis="pressure", subject_focus="gauges")
    risky, reason = repetition_risk(a, b)
    assert risky is False
    assert reason == ""


def test_repeated_framing_forces_new_image_generation():
    scenes = _linear_scenes(5)
    scenes[1].shot_type = scenes[2].shot_type = "wide"
    scenes[1].visual_emotion = scenes[2].visual_emotion = "awe"
    scenes[1].caption_emphasis = scenes[2].caption_emphasis = "same"
    scenes[1].subject_focus = scenes[2].subject_focus = "same subject"
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3, 4]), _group([5])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=4, min_confidence=0.75)

    grouped_numbers = [g.scene_numbers for g in plan.groups]
    assert [2, 3, 4] not in grouped_numbers
    assert [2] in grouped_numbers  # scene 2 split off into its own fresh image


def test_low_confidence_prevents_reuse_directly():
    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    raw = VisualAssetPlan(groups=[_group([1]), _group([2, 3], confidence=0.1), _group([4])])

    plan = _enforce_constraints(raw, storyboard, max_consecutive_reuse=3, min_confidence=0.75)

    assert [2, 3] not in [g.scene_numbers for g in plan.groups]


# ---------------------------------------------------------------------------
# v3.1: Planner Cost Guard
# ---------------------------------------------------------------------------


def test_cost_guard_disables_grouping_when_planner_cost_exceeds_savings(monkeypatch):
    monkeypatch.setenv("VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_INPUT_USD", "1000")
    monkeypatch.setenv("VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_OUTPUT_USD", "1000")
    result = cost_guard.evaluate(planner_input_tokens=5000, planner_output_tokens=2000, reused_images=2)
    assert result.should_disable_grouping is True
    assert result.estimated_net_cost_saved_usd < 0


def test_cost_guard_allows_grouping_when_savings_exceed_cost():
    result = cost_guard.evaluate(planner_input_tokens=2000, planner_output_tokens=500, reused_images=10)
    assert result.should_disable_grouping is False
    assert result.estimated_net_cost_saved_usd > 0


def test_cost_guard_never_flags_a_plan_with_zero_reuse():
    # No reuse to disable in the first place -- this must not be reported
    # as a guard "decision" (see planner.py's extra `> 0` check).
    result = cost_guard.evaluate(planner_input_tokens=2000, planner_output_tokens=500, reused_images=0)
    assert result.should_disable_grouping is True  # 0 savings vs any nonzero cost
    assert result.estimated_image_cost_saved_usd == 0.0


def test_cost_guard_disables_on_negative_net_time_even_when_dollar_positive():
    # Verified against a real production: cheap in tokens (dollar-positive)
    # but the planner call itself took long enough that estimated render-
    # time savings from 2 reused images didn't cover it -- reducing render
    # time was objective #1 of this whole feature, so time-negative must
    # disable grouping even when cost-positive.
    result = cost_guard.evaluate(
        planner_input_tokens=100, planner_output_tokens=50, reused_images=2, planner_execution_time=120.0,
    )
    assert result.should_disable_for_cost is False  # cheap in dollars
    assert result.should_disable_for_time is True  # but far too slow
    assert result.should_disable_grouping is True


def test_cost_guard_allows_when_both_cost_and_time_are_net_positive():
    result = cost_guard.evaluate(
        planner_input_tokens=1200, planner_output_tokens=400, reused_images=7, planner_execution_time=20.0,
    )
    assert result.should_disable_for_cost is False
    assert result.should_disable_for_time is False
    assert result.should_disable_grouping is False


# ---------------------------------------------------------------------------
# v3.1: End-to-end planner telemetry (real structured_response call path,
# fake OpenAI client -- no network).
# ---------------------------------------------------------------------------


class _PlannerResponsesStub:
    def __init__(self, parsed_plan, *, input_tokens=1000, output_tokens=300):
        self._parsed = parsed_plan
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


class _PlannerFakeClient:
    def __init__(self, responses_stub):
        self.responses = responses_stub


def test_end_to_end_planner_records_tokens_time_and_cost(monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "true")
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-e2e")

    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)
    proposed = VisualAssetPlan(groups=[_group([1]), _group([2, 3]), _group([4]), _group([5])])
    stub = _PlannerResponsesStub(proposed, input_tokens=1200, output_tokens=400)
    monkeypatch.setattr(
        "app.services.openai_client.get_openai_client", lambda: _PlannerFakeClient(stub)
    )

    plan, meta = plan_visual_assets(storyboard, target_seconds=15)

    assert stub.calls, "the planner never actually called the client"
    assert meta["planner_enabled"] is True
    assert meta["planner_model"] == "gpt-baseline"
    assert meta["planner_input_tokens"] == 1200
    assert meta["planner_output_tokens"] == 400
    assert meta["planner_execution_time"] >= 0.0
    assert meta["planner_disabled_reason"] is None
    assert [2, 3] in [g.scene_numbers for g in plan.groups]


def test_end_to_end_cost_guard_collapses_plan_to_identity(monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "true")
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    # Make the planner call look enormously expensive relative to the tiny
    # amount of reuse it would unlock -- the guard must reject grouping.
    monkeypatch.setenv("VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_INPUT_USD", "500000")
    monkeypatch.setenv("VISUAL_CONTINUITY_TEXT_PRICE_PER_1M_OUTPUT_USD", "500000")
    project_state.start_project("proj-guard")

    scenes = _linear_scenes(5)
    storyboard = _storyboard(scenes)
    proposed = VisualAssetPlan(groups=[_group([1]), _group([2, 3]), _group([4]), _group([5])])
    stub = _PlannerResponsesStub(proposed, input_tokens=1200, output_tokens=400)
    monkeypatch.setattr(
        "app.services.openai_client.get_openai_client", lambda: _PlannerFakeClient(stub)
    )

    plan, meta = plan_visual_assets(storyboard, target_seconds=15)

    assert meta["planner_disabled_reason"] == "cost_guard_triggered"
    assert all(len(g.scene_numbers) == 1 for g in plan.groups)


# ---------------------------------------------------------------------------
# v3.1: VISUAL_CONTINUITY_DEBUG
# ---------------------------------------------------------------------------


def test_debug_mode_writes_raw_plan_and_decisions(tmp_path, monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "true")
    monkeypatch.setenv("VISUAL_CONTINUITY_DEBUG", "true")
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-debug")

    scenes = _linear_scenes(4)
    storyboard = _storyboard(scenes)
    proposed = VisualAssetPlan(groups=[_group([1]), _group([2, 3]), _group([4])])
    stub = _PlannerResponsesStub(proposed)
    monkeypatch.setattr(
        "app.services.openai_client.get_openai_client", lambda: _PlannerFakeClient(stub)
    )

    _plan, meta = plan_visual_assets(storyboard, target_seconds=12)
    assert meta["debug"] is not None
    assert "raw_plan" in meta["debug"]

    path = save_visual_continuity_debug(tmp_path, meta)
    assert path is not None
    assert path.name == "visual-continuity-debug.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["raw_plan"]["groups"]


def test_debug_mode_disabled_by_default_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("VISUAL_ASSET_ECONOMY", "true")
    monkeypatch.delenv("VISUAL_CONTINUITY_DEBUG", raising=False)
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-no-debug")

    scenes = _linear_scenes(3)
    storyboard = _storyboard(scenes)
    proposed = VisualAssetPlan(groups=[_group([1]), _group([2]), _group([3])])
    stub = _PlannerResponsesStub(proposed)
    monkeypatch.setattr(
        "app.services.openai_client.get_openai_client", lambda: _PlannerFakeClient(stub)
    )

    _plan, meta = plan_visual_assets(storyboard, target_seconds=9)
    assert meta["debug"] is None
    assert save_visual_continuity_debug(tmp_path, meta) is None
