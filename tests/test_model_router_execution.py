from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest

from app.model_router import circuit_breaker, comparison, project_state, usage
from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import ValidationResult, ok
from app.model_router.stages import Stage
from app.models import ResearchBrief, SeoPackage, ShortScript, Storyboard, VisualMemory, Scene


@pytest.fixture(autouse=True)
def _clean_state():
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()
    yield
    circuit_breaker.reset_all()
    project_state.reset()
    usage.reset()


def _no_sleep(_seconds: float) -> None:
    return None


class _ResponsesStub:
    """A stand-in for ``client.responses`` that plays back a scripted
    sequence of results/exceptions, one per call, and records every call's
    kwargs (never any secrets -- these are test doubles, not real prompts)."""

    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if not self._script:
            raise AssertionError("ScriptedClient ran out of scripted responses")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeClient:
    def __init__(self, script):
        self.responses = _ResponsesStub(script)

    @property
    def calls(self):
        return self.responses.calls


def _response(parsed, *, input_tokens=100, output_tokens=50):
    usage_obj = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    return SimpleNamespace(output_parsed=parsed, usage=usage_obj)


def _research_brief(*, valid: bool = True) -> ResearchBrief:
    if valid:
        return ResearchBrief(
            central_question="Why do tides happen?",
            core_insight="Gravity from the moon and sun pulls ocean water.",
            verified_points=["The moon's gravity dominates.", "Tides cycle roughly twice daily."],
            cautions=["Local geography changes exact timing."],
            audience_relevance="Curious general audience.",
            possible_angles=["Historical navigation", "Modern tide prediction"],
        )
    return ResearchBrief(
        central_question="",
        core_insight="",
        verified_points=[],
        cautions=[],
        audience_relevance="",
        possible_angles=[],
    )


def _http_error(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(status_code, request=request, json={"error": {"message": "boom"}})


def _always_ok(_output) -> ValidationResult:
    return ok()


def _always_fail(_output) -> ValidationResult:
    return ValidationResult(passed=False, reasons=["forced failure for test"])


# ---------------------------------------------------------------------------
# Happy path: lower-cost model succeeds and passes validation -> baseline is
# never invoked.
# ---------------------------------------------------------------------------


def test_successful_lower_cost_output_never_invokes_baseline(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-happy")

    brief = _research_brief(valid=True)
    client = FakeClient([_response(brief)])

    result = run_agent_stage(
        Stage.STORYBOARD,  # routed to the lower-cost tier in Standard
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=_always_ok,
        client=client,
        sleep=_no_sleep,
    )

    assert result.output is brief
    assert result.final_model == "gpt-cheap"
    assert result.fallback_triggered is False
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "gpt-cheap"

    records = usage.records_for("proj-happy")
    assert len(records) == 1
    assert records[0].fallback_triggered is False
    assert records[0].final_model == "gpt-cheap"
    assert records[0].input_tokens == 100


# ---------------------------------------------------------------------------
# Schema/provider failure on the lower-cost model -> baseline invoked and
# used; failure is recorded, not hidden.
# ---------------------------------------------------------------------------


def test_schema_failure_on_lower_cost_model_falls_back_to_baseline(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-schema")

    good_brief = _research_brief(valid=True)
    # First call: no output_parsed at all (the "model returned no
    # structured output" failure mode structured_response already raises
    # today). Second call (baseline): succeeds.
    client = FakeClient([_response(None), _response(good_brief)])

    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=_always_ok,
        client=client,
        sleep=_no_sleep,
    )

    assert result.output is good_brief
    assert result.final_model == "gpt-baseline"
    assert result.fallback_triggered is True
    assert "schema_validation" in result.fallback_reason
    assert [call["model"] for call in client.calls] == ["gpt-cheap", "gpt-baseline"]

    records = usage.records_for("proj-schema")
    assert records[-1].fallback_triggered is True
    assert records[-1].attempted_model == "gpt-cheap"
    assert records[-1].final_model == "gpt-baseline"


# ---------------------------------------------------------------------------
# Deterministic quality-check failure -> baseline invoked; rejected output
# never reaches the caller.
# ---------------------------------------------------------------------------


def test_quality_failure_on_lower_cost_model_falls_back_and_rejected_output_is_discarded(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-quality")

    rejected_brief = _research_brief(valid=True)
    accepted_brief = _research_brief(valid=True)
    client = FakeClient([_response(rejected_brief), _response(accepted_brief)])

    validate_calls: list[object] = []

    def validate(output):
        validate_calls.append(output)
        # Reject the first (lower-cost) output, accept the second (baseline).
        return _always_fail(output) if output is rejected_brief else _always_ok(output)

    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=validate,
        client=client,
        sleep=_no_sleep,
    )

    assert result.output is accepted_brief
    assert result.output is not rejected_brief
    assert result.fallback_triggered is True
    assert "quality_validation_failed" in result.fallback_reason


# ---------------------------------------------------------------------------
# Circuit breaker: N failures for one stage trip it; only that stage is
# affected.
# ---------------------------------------------------------------------------


def test_repeated_quality_failures_trip_the_stage_circuit_breaker(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    monkeypatch.setenv("MODEL_FALLBACK_FAILURE_THRESHOLD", "2")
    project_state.start_project("proj-breaker")

    brief = _research_brief(valid=True)

    def make_client():
        return FakeClient([_response(brief), _response(brief)])

    for _ in range(2):
        run_agent_stage(
            Stage.STORYBOARD,
            instructions="x",
            prompt="y",
            schema=ResearchBrief,
            validate=_always_fail,
            client=make_client(),
            sleep=_no_sleep,
        )

    assert circuit_breaker.is_disabled(Stage.STORYBOARD, project_id="proj-breaker") is True
    # A different stage in the same project is unaffected.
    assert circuit_breaker.is_disabled(Stage.SEO, project_id="proj-breaker") is False

    # Now the stage goes straight to baseline -- a single-call client proves
    # the lower-cost model is never attempted again.
    single_call_client = FakeClient([_response(brief)])
    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=_always_ok,
        client=single_call_client,
        sleep=_no_sleep,
    )
    assert result.attempted_model == "gpt-baseline"
    assert len(single_call_client.calls) == 1


# ---------------------------------------------------------------------------
# Provider error classification / retry policy.
# ---------------------------------------------------------------------------


def test_unsupported_model_falls_back_immediately_without_retry(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-unsupported")

    brief = _research_brief(valid=True)
    not_found = openai.NotFoundError("model not found", response=_http_error(404), body=None)
    client = FakeClient([not_found, _response(brief)])

    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=_always_ok,
        client=client,
        sleep=_no_sleep,
    )

    assert result.final_model == "gpt-baseline"
    # Exactly 2 calls total: one failed lower-cost attempt (no retries for
    # an unsupported model) + one baseline attempt.
    assert len(client.calls) == 2


def test_authentication_and_quota_errors_are_not_retried_blindly(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-auth")

    auth_error = openai.AuthenticationError("bad key", response=_http_error(401), body=None)
    # Baseline also fails with auth error -- there is nothing left to fall
    # back to, so the exception must propagate rather than retry forever.
    client = FakeClient([auth_error, openai.AuthenticationError("bad key", response=_http_error(401), body=None)])

    with pytest.raises(openai.AuthenticationError):
        run_agent_stage(
            Stage.STORYBOARD,
            instructions="x",
            prompt="y",
            schema=ResearchBrief,
            validate=_always_ok,
            client=client,
            sleep=_no_sleep,
        )

    # Exactly 2 calls -- no retry loop against either model.
    assert len(client.calls) == 2


def test_transient_errors_are_retried_then_succeed_without_fallback(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    monkeypatch.setenv("MODEL_LOWER_COST_DEFAULT", "gpt-cheap")
    project_state.start_project("proj-transient")

    brief = _research_brief(valid=True)
    transient = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    client = FakeClient([transient, _response(brief)])

    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions="x",
        prompt="y",
        schema=ResearchBrief,
        validate=_always_ok,
        client=client,
        sleep=_no_sleep,
    )

    assert result.output is brief
    assert result.fallback_triggered is False
    assert result.retries == 1
    assert len(client.calls) == 2
    # Both retry attempts used the *same* (lower-cost) model -- retry never
    # silently swaps models.
    assert all(call["model"] == "gpt-cheap" for call in client.calls)


def test_no_infinite_retry_loop_on_persistent_transient_errors(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")  # attempted == baseline
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")

    def _persistent_transient():
        return openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))

    client = FakeClient([_persistent_transient() for _ in range(10)])

    with pytest.raises(openai.APIConnectionError):
        run_agent_stage(
            Stage.STORYBOARD,
            instructions="x",
            prompt="y",
            schema=ResearchBrief,
            validate=_always_ok,
            client=client,
            sleep=_no_sleep,
        )

    # Bounded retry: MAX_RETRIES_PER_MODEL=2 -> 3 total attempts, not 10.
    assert len(client.calls) == 3


# ---------------------------------------------------------------------------
# Phase 10: usage telemetry never stores prompts/secrets.
# ---------------------------------------------------------------------------


def test_model_usage_document_has_no_prompt_or_secret_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "studio")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")
    project_state.start_project("proj-usage")

    brief = _research_brief(valid=True)
    client = FakeClient([_response(brief)])
    run_agent_stage(
        Stage.RESEARCH,
        instructions="super secret instructions",
        prompt="the entire user prompt goes here",
        schema=ResearchBrief,
        validate=_always_ok,
        client=client,
        sleep=_no_sleep,
    )

    path = usage.save_model_usage(tmp_path, "proj-usage")
    document = path.read_text(encoding="utf-8")
    assert "super secret instructions" not in document
    assert "the entire user prompt goes here" not in document
    assert "api_key" not in document.casefold()

    import json

    parsed = json.loads(document)
    assert parsed["aggregate"]["total_calls"] == 1
    assert parsed["calls"][0]["attempted_model"] == "gpt-baseline"
    assert parsed["calls"][0]["final_model"] == "gpt-baseline"


# ---------------------------------------------------------------------------
# Phase 12: A/B comparison mode (no live OpenAI calls -- injected fakes).
# ---------------------------------------------------------------------------


def _fake_storyboard() -> Storyboard:
    return Storyboard(
        visual_memory=VisualMemory(
            primary_location="lighthouse",
            secondary_location="shoreline",
            recurring_props=["lantern"],
            architecture_and_environment="stone tower",
            time_of_day="dusk",
            weather_and_atmosphere="misty",
            color_palette="cool blues",
            lighting_language="soft rim light",
            lens_language="35mm",
            production_design_anchor="coastal minimalism",
            continuity_rules=["keep the lantern lit"],
        ),
        story_arc_summary="A lighthouse keeper reflects on decades of guiding ships home.",
        scenes=[
            Scene(
                number=1, start_second=0, end_second=8, narration="Hook narration.",
                on_screen_text="", visual_direction="wide shot", image_prompt="a lighthouse at dusk",
                story_role="hook", shot_type="wide",
            ),
            Scene(
                number=2, start_second=8, end_second=16, narration="Setup narration.",
                on_screen_text="", visual_direction="medium shot", image_prompt="the keeper climbing stairs",
                story_role="final_line", shot_type="medium",
            ),
        ],
    )


def test_ab_comparison_mode_runs_both_profiles_and_saves_report(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-baseline")

    def fake_research_run(topic, production_specification=None):
        return _research_brief(valid=True)

    def fake_script_run(topic, research, target_seconds, production_specification=None):
        return ShortScript(
            title="The Lighthouse Keeper",
            hook="Every night, one light refuses to go out.",
            voiceover=" ".join(["word"] * 100),
            ending="And the light goes on.",
            estimated_seconds=target_seconds,
        )

    def fake_storyboard_run(script, target_seconds, character_bible, production_specification=None):
        return _fake_storyboard()

    def fake_seo_run(script, production_specification=None):
        return SeoPackage(
            title="The Lighthouse Keeper's Story",
            description="A short documentary about a lighthouse keeper's decades of service.",
            hashtags=["#lighthouse", "#documentary", "#history"],
        )

    result = comparison.run_comparison(
        "A lighthouse keeper's story",
        45,
        profile_a="studio",
        profile_b="standard",
        research_run=fake_research_run,
        script_run=fake_script_run,
        storyboard_run=fake_storyboard_run,
        seo_run=fake_seo_run,
    )

    assert result["profile_a"] == "studio"
    assert result["profile_b"] == "standard"
    assert "accepted" in result["result_a"]
    assert "accepted" in result["result_b"]

    path = comparison.save_comparison(tmp_path, result)
    assert path.name == "model-comparison.json"
    import json

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["profile_a"] == "studio"
    assert saved["result_a"]["structural_checks"]["script_valid"] is True
