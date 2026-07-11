from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.creative_director.engine import CreativeDirector
from app.creative_director.llm import CreativeDirectorLLM
from app.creative_director.models import QuestionResponse
from app.creative_director.routes import router as creative_director_router
from app.orchestrator.models import OrchestratorRequest


PROMPT = "Create an atmospheric launch film for a neighborhood arts space."


class StaticLLM:
    def __init__(self, *, questions=None, brief=None, error: Exception | None = None):
        self.questions = questions
        self.brief = brief
        self.error = error

    def generate_questions(self, prompt: str):
        if self.error:
            raise self.error
        return self.questions

    def generate_brief(self, prompt: str, answers: dict):
        if self.error:
            raise self.error
        return self.brief


class FakeResponses:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed
        self.call = None

    def parse(self, **kwargs):
        self.call = kwargs
        return type("Response", (), {"output_parsed": self.output_parsed})()


class FakeOpenAI:
    def __init__(self, output_parsed):
        self.responses = FakeResponses(output_parsed)


def question(identifier: str) -> dict:
    return {
        "id": identifier,
        "question": f"Choose {identifier.replace('_', ' ')}?",
        "type": "single_choice",
        "options": ["Option A", "Option B"],
    }


def test_question_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    questions = CreativeDirector().generate_questions(PROMPT)

    assert 0 < len(questions) <= 5
    assert all(item.type == "single_choice" for item in questions)


def test_question_fallback_does_not_repeat_supplied_runtime(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    questions = CreativeDirector().generate_questions(
        "Create a 60-second launch film for the new venue."
    )

    assert "runtime" not in {item.id for item in questions}


def test_model_output_cannot_exceed_five_questions():
    with pytest.raises(ValidationError):
        QuestionResponse.model_validate(
            {"questions": [question(f"decision_{index}") for index in range(6)]}
        )


def test_duplicate_question_ids_are_rejected():
    with pytest.raises(ValidationError, match="Question IDs must be unique"):
        QuestionResponse.model_validate(
            {"questions": [question("audience"), question("audience")]}
        )


def test_invalid_model_response_uses_question_fallback():
    service = CreativeDirector(
        llm_factory=lambda: StaticLLM(questions={"questions": "invalid"})
    )

    questions = service.generate_questions(PROMPT)

    assert 0 < len(questions) <= 5
    assert {item.id for item in questions} == {
        "target_audience",
        "output_format",
        "runtime",
        "creative_direction",
    }


def test_llm_uses_pydantic_structured_output():
    client = FakeOpenAI({"questions": [question("audience")]})
    llm = CreativeDirectorLLM(client, "test-model")

    result = llm.generate_questions(PROMPT)

    assert result.questions[0].id == "audience"
    assert client.responses.call["model"] == "test-model"
    assert client.responses.call["text_format"] is QuestionResponse


def test_duplicate_model_question_ids_use_fallback():
    service = CreativeDirector(
        llm_factory=lambda: StaticLLM(
            questions={
                "questions": [question("audience"), question("audience")]
            }
        )
    )

    questions = service.generate_questions(PROMPT)

    assert [item.id for item in questions] != ["audience", "audience"]
    assert len(questions) <= 5


def test_deterministic_brief_fallback_is_clean_and_stable():
    answers = {
        "target_audience": "Local families",
        "runtime": "60 seconds",
        "creative_direction": "Warm and handmade",
        "constraints": ["No on-camera dialogue", "Use available light"],
    }
    service = CreativeDirector(llm_factory=lambda: None)

    first = service.build_brief(PROMPT, answers)
    second = service.build_brief(PROMPT, answers)

    assert first == second
    assert first.target_seconds == 60
    assert first.topic == PROMPT
    assert str(answers) not in first.creative_brief
    assert "{'" not in first.creative_brief
    assert "Creative Objective" in first.creative_brief
    assert "Success Criteria" in first.creative_brief
    assert "Local families" in first.creative_brief


def test_deterministic_brief_uses_runtime_from_prompt():
    service = CreativeDirector(llm_factory=lambda: None)

    brief = service.build_brief(
        "Create a 2-minute launch film for the new venue.",
        {},
    )

    assert brief.target_seconds == 120


def test_failed_brief_model_call_uses_deterministic_fallback():
    service = CreativeDirector(
        llm_factory=lambda: StaticLLM(error=RuntimeError("provider secret"))
    )

    brief = service.build_brief(PROMPT, {"runtime": "45 seconds"})

    assert brief.target_seconds == 45
    assert "provider secret" not in brief.creative_brief
    assert "Core Subject" in brief.creative_brief


def test_brief_with_serialized_answer_mapping_uses_fallback():
    answers = {"audience": "Everyone"}
    unsafe_brief = {
        "topic": PROMPT,
        "target_seconds": 45,
        "hook_type": "question",
        "creative_brief": (
            "Creative Objective\nCreate the piece.\n\n"
            "Answers\n{'audience': 'Everyone'}"
        ),
    }
    service = CreativeDirector(
        llm_factory=lambda: StaticLLM(brief=unsafe_brief)
    )

    brief = service.build_brief(PROMPT, answers)

    assert "{'audience': 'Everyone'}" not in brief.creative_brief
    assert "Target Audience\nEveryone" in brief.creative_brief


def test_creative_director_route_response_shapes(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = FastAPI()
    app.include_router(creative_director_router, prefix="/api")
    client = TestClient(app)

    question_response = client.post(
        "/api/creative-director/questions",
        json={"prompt": PROMPT},
    )
    assert question_response.status_code == 200
    question_body = question_response.json()
    assert set(question_body) == {"questions"}
    assert len(question_body["questions"]) <= 5
    assert set(question_body["questions"][0]) == {
        "id",
        "question",
        "type",
        "options",
    }

    brief_response = client.post(
        "/api/creative-director/brief",
        json={"prompt": PROMPT, "answers": {"runtime": "45 seconds"}},
    )
    assert brief_response.status_code == 200
    assert set(brief_response.json()) == {
        "topic",
        "target_seconds",
        "hook_type",
        "creative_brief",
    }


def test_creative_brief_is_compatible_with_orchestrator_payload():
    brief = CreativeDirector(llm_factory=lambda: None).build_brief(
        PROMPT,
        {"runtime": "120 seconds", "creative_direction": "Immersive"},
    )

    payload = OrchestratorRequest.model_validate(
        {
            "topic": brief.creative_brief,
            "target_seconds": brief.target_seconds,
            "hook_type": brief.hook_type,
            "save_workspace": True,
        }
    )

    assert payload.target_seconds == 120
    assert payload.topic == brief.creative_brief
