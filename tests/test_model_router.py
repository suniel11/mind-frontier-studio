from __future__ import annotations

import pytest

from app.model_router import circuit_breaker, config, project_state, router
from app.model_router.errors import ErrorCategory, classify_error
from app.model_router.quality_checks import (
    character_validator,
    inconclusive_validator,
    research_validator,
    script_validator,
    seo_validator,
    storyboard_validator,
    validate_creative_director_brief,
    validate_creative_director_questions,
)
from app.model_router.stages import Stage
from app.models import CharacterBible, ResearchBrief, SeoPackage, ShortScript


@pytest.fixture(autouse=True)
def _clean_router_state():
    circuit_breaker.reset_all()
    project_state.reset()
    yield
    circuit_breaker.reset_all()
    project_state.reset()


# ---------------------------------------------------------------------------
# Phase 2: baseline mapping is preserved and available.
# ---------------------------------------------------------------------------


def test_baseline_mapping_covers_every_stage():
    mapping = config.baseline_mapping()
    assert set(mapping) == {stage.value for stage in Stage}
    assert all(value for value in mapping.values())


def test_baseline_model_reads_openai_text_model(monkeypatch):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-custom-baseline")
    monkeypatch.delenv("CREATIVE_DIRECTOR_MODEL", raising=False)
    assert config.baseline_model_for(Stage.RESEARCH) == "gpt-custom-baseline"
    # Creative Director stages fall back to OPENAI_TEXT_MODEL when
    # CREATIVE_DIRECTOR_MODEL is unset -- same precedence as before routing
    # existed (app/creative_director/llm.py's original from_environment).
    assert config.baseline_model_for(Stage.CREATIVE_DIRECTOR_BRIEF) == "gpt-custom-baseline"


def test_creative_director_model_env_var_takes_precedence_for_baseline(monkeypatch):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-text")
    monkeypatch.setenv("CREATIVE_DIRECTOR_MODEL", "gpt-director-only")
    assert config.baseline_model_for(Stage.CREATIVE_DIRECTOR_QUESTIONS) == "gpt-director-only"
    assert config.baseline_model_for(Stage.RESEARCH) == "gpt-text"


# ---------------------------------------------------------------------------
# Phase 3/4: central router, profiles.
# ---------------------------------------------------------------------------


def test_studio_profile_uses_baseline_directly_for_every_stage(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    for stage in Stage:
        selection = router.resolve(stage)
        assert selection.attempted_model == selection.baseline_model == "gpt-baseline"
        assert selection.is_baseline_attempt is True


def test_standard_profile_routes_supporting_stages_to_smaller_model(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")

    storyboard = router.resolve(Stage.STORYBOARD)
    assert storyboard.attempted_model == "gpt-cheap"
    assert storyboard.baseline_model == "gpt-baseline"
    assert storyboard.is_baseline_attempt is False

    # Standard keeps research/script/brief on the strong/baseline model.
    for stage in (Stage.RESEARCH, Stage.SCRIPT, Stage.CREATIVE_DIRECTOR_BRIEF):
        selection = router.resolve(stage)
        assert selection.attempted_model == "gpt-baseline"
        assert selection.is_baseline_attempt is True

    # ...but routes Creative Director questions to the smaller model.
    questions = router.resolve(Stage.CREATIVE_DIRECTOR_QUESTIONS)
    assert questions.attempted_model == "gpt-cheap"


def test_economy_profile_uses_smaller_model_more_aggressively(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "economy")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")

    # Even the Creative Director brief goes to the smaller model in Economy.
    brief = router.resolve(Stage.CREATIVE_DIRECTOR_BRIEF)
    assert brief.attempted_model == "gpt-cheap"

    # Final script and research synthesis still stay strong even in Economy.
    for stage in (Stage.RESEARCH, Stage.SCRIPT):
        selection = router.resolve(stage)
        assert selection.is_baseline_attempt is True


def test_stage_environment_override_takes_priority(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("MODEL_STORYBOARD", "gpt-explicit-override")
    selection = router.resolve(Stage.STORYBOARD)
    assert selection.attempted_model == "gpt-explicit-override"
    assert selection.reason == "stage_env_override"


def test_empty_or_malformed_stage_override_is_ignored_safely(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_STORYBOARD", "   ")
    selection = router.resolve(Stage.STORYBOARD)
    assert selection.reason != "stage_env_override"

    monkeypatch.setenv("MODEL_STORYBOARD", "not a valid model id!!")
    selection = router.resolve(Stage.STORYBOARD)
    assert selection.reason != "stage_env_override"


def test_invalid_profile_value_falls_back_safely_to_standard(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "ultra-deluxe-nonsense")
    cfg = config.load_router_config()
    assert cfg.profile == "standard"


def test_model_auto_fallback_false_forces_baseline_resolution(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "economy")
    monkeypatch.setenv("MODEL_AUTO_FALLBACK", "false")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    for stage in Stage:
        selection = router.resolve(stage)
        assert selection.attempted_model == selection.baseline_model
    # Disabling auto-fallback does not remove access to baseline models.
    assert config.baseline_model_for(Stage.STORYBOARD) == "gpt-baseline"


def test_model_profile_studio_restores_original_behavior_regardless_of_other_flags(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("MODEL_AUTO_FALLBACK", "true")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    selection = router.resolve(Stage.SEO)
    assert selection.attempted_model == "gpt-baseline"


# ---------------------------------------------------------------------------
# Phase 8: circuit breaker.
# ---------------------------------------------------------------------------


def test_circuit_breaker_trips_after_threshold_and_is_scoped_to_its_stage():
    circuit_breaker.record_failure(Stage.STORYBOARD, project_id="proj-1", threshold=3, reason="x")
    circuit_breaker.record_failure(Stage.STORYBOARD, project_id="proj-1", threshold=3, reason="x")
    assert circuit_breaker.is_disabled(Stage.STORYBOARD, project_id="proj-1") is False
    tripped = circuit_breaker.record_failure(Stage.STORYBOARD, project_id="proj-1", threshold=3, reason="x")
    assert tripped is True
    assert circuit_breaker.is_disabled(Stage.STORYBOARD, project_id="proj-1") is True
    # A different stage in the same project is unaffected.
    assert circuit_breaker.is_disabled(Stage.SEO, project_id="proj-1") is False
    # A different project is unaffected.
    assert circuit_breaker.is_disabled(Stage.STORYBOARD, project_id="proj-2") is False


def test_router_uses_baseline_once_circuit_breaker_is_tripped(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    for _ in range(3):
        circuit_breaker.record_failure(Stage.STORYBOARD, project_id="proj-9", threshold=3, reason="x")
    selection = router.resolve(Stage.STORYBOARD, project_id="proj-9")
    assert selection.attempted_model == "gpt-baseline"
    assert selection.reason == "circuit_breaker_open"


# ---------------------------------------------------------------------------
# Phase 11: project-level fallback threshold.
# ---------------------------------------------------------------------------


def test_project_level_fallback_forces_remaining_stages_to_baseline(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    monkeypatch.setenv("MODEL_PROJECT_FALLBACK_THRESHOLD", "2")

    state = project_state.start_project("proj-threshold")
    assert router.resolve(Stage.STORYBOARD).attempted_model == "gpt-cheap"

    project_state.record_fallback(Stage.STORYBOARD, "reason one")
    assert state.forced_baseline is False
    project_state.record_fallback(Stage.CHARACTER, "reason two")
    assert state.forced_baseline is True

    # Every stage now resolves to baseline for the rest of this project.
    assert router.resolve(Stage.SEO).is_baseline_attempt is True
    assert router.resolve(Stage.STORYBOARD).is_baseline_attempt is True


# ---------------------------------------------------------------------------
# Phase 9: provider error classification.
# ---------------------------------------------------------------------------


def test_classify_error_categories():
    import openai

    assert classify_error(ValueError("The model returned no structured output.")) == ErrorCategory.SCHEMA_VALIDATION
    assert classify_error(RuntimeError("boom")) == ErrorCategory.SCHEMA_VALIDATION

    auth_error = openai.AuthenticationError(
        "bad key", response=_fake_http_response(401), body=None
    )
    assert classify_error(auth_error) == ErrorCategory.AUTHENTICATION

    not_found = openai.NotFoundError(
        "model not found", response=_fake_http_response(404), body=None
    )
    assert classify_error(not_found) == ErrorCategory.UNSUPPORTED_MODEL

    bad_request_model = openai.BadRequestError(
        "The model `gpt-does-not-exist` does not exist",
        response=_fake_http_response(400),
        body=None,
    )
    assert classify_error(bad_request_model) == ErrorCategory.UNSUPPORTED_MODEL

    bad_request_other = openai.BadRequestError(
        "invalid parameter", response=_fake_http_response(400), body=None
    )
    assert classify_error(bad_request_other) == ErrorCategory.INVALID_REQUEST


def _fake_http_response(status_code: int):
    import httpx

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(status_code, request=request, json={"error": {"message": "boom"}})


# ---------------------------------------------------------------------------
# Phase 7: deterministic stage quality checks.
# ---------------------------------------------------------------------------


def test_research_validator_rejects_empty_brief():
    brief = ResearchBrief(
        central_question="",
        core_insight="",
        verified_points=[],
        cautions=[],
        audience_relevance="",
        possible_angles=[],
    )
    result = research_validator()(brief)
    assert result.passed is False
    assert result.reasons


def test_research_validator_accepts_well_formed_brief():
    brief = ResearchBrief(
        central_question="Why do tides happen?",
        core_insight="Gravity from the moon and sun pulls ocean water.",
        verified_points=["The moon's gravity dominates.", "Tides cycle roughly twice daily."],
        cautions=["Local geography changes exact timing."],
        audience_relevance="Curious general audience.",
        possible_angles=["Historical navigation", "Modern tide prediction"],
    )
    assert research_validator()(brief).passed is True


def test_script_validator_rejects_wrong_word_count():
    script = ShortScript(
        title="Tides",
        hook="Have you ever wondered why the ocean moves?",
        voiceover="Short.",
        ending="That's the tide.",
        estimated_seconds=45,
    )
    result = script_validator(target_seconds=45)(script)
    assert result.passed is False
    assert any("word count" in reason for reason in result.reasons)


def test_script_validator_accepts_reasonable_length_script():
    voiceover = " ".join(["word"] * 100)
    script = ShortScript(
        title="Tides Explained",
        hook="Have you ever wondered why the ocean moves twice a day?",
        voiceover=voiceover,
        ending="And that is the quiet power of the moon.",
        estimated_seconds=45,
    )
    result = script_validator(target_seconds=45)(script)
    assert result.passed is True


def test_character_validator_enforces_explicit_gender_preference():
    character = CharacterBible(
        name="Jordan",
        narrative_role="host",
        gender="male",
        age_range="30-40",
        facial_features="warm eyes",
        hair="short hair",
        wardrobe="navy coat",
        accessories="none",
        body_language="calm",
        color_palette="cool tones",
        lighting_anchor="soft light",
        prompt_anchor="a narrator",
        negative_constraints="no changes to face or wardrobe",
        continuity_tags=["navy coat"],
    )
    result = character_validator(expected_gender="female")(character)
    assert result.passed is False
    assert any("female" in reason for reason in result.reasons)

    result_ok = character_validator(expected_gender="male")(character)
    assert result_ok.passed is True


def test_seo_validator_rejects_missing_hashtags():
    seo = SeoPackage(title="A great video about tides", description="Learn how tides work in two minutes.", hashtags=[])
    assert seo_validator()(seo).passed is False


def test_creative_director_questions_validator_rejects_duplicate_ids():
    from app.creative_director.models import DirectorQuestion, QuestionResponse

    with pytest.raises(Exception):
        # QuestionResponse itself already forbids duplicate ids via its
        # own pydantic validator -- construct two *different* ids with
        # duplicate question text instead, which pydantic allows through.
        QuestionResponse(
            questions=[
                DirectorQuestion(id="a", question="Pick one?", type="single_choice", options=["A", "B"]),
                DirectorQuestion(id="a", question="Pick one?", type="single_choice", options=["A", "B"]),
            ]
        )

    response = QuestionResponse(
        questions=[
            DirectorQuestion(id="a", question="Pick one?", type="single_choice", options=["A", "B"]),
            DirectorQuestion(id="b", question="Pick one?", type="single_choice", options=["C", "D"]),
        ]
    )
    result = validate_creative_director_questions(response)
    assert result.passed is False
    assert any("duplicate question text" in reason for reason in result.reasons)


def test_creative_director_brief_validator_flags_leaked_answers():
    from app.production.specification import ProductionSpecification

    spec = ProductionSpecification.from_legacy("A film about lighthouses", 60)
    answers = {"creative_direction": "A deeply specific and unusual answer text"}
    brief = _brief(spec, answers["creative_direction"])
    result = validate_creative_director_brief(brief, expected_answers=answers)
    assert result.passed is False
    assert any("leak" in reason for reason in result.reasons)


def _brief(spec, leaked_text: str):
    from app.creative_director.models import ProductionBrief

    return ProductionBrief(
        topic="A film about lighthouses",
        target_seconds=60,
        hook_type="curiosity",
        creative_brief=f"This production uses the direction: {leaked_text} throughout the piece.",
        production_specification=spec,
    )


def test_inconclusive_validator_marks_result_inconclusive():
    result = inconclusive_validator("no rule yet")(object())
    assert result.passed is True
    assert result.inconclusive is True
