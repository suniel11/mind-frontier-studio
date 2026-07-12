from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.creative_director import routes
from app.creative_director.preferences import PreferenceStore


def test_preferences_api_never_requires_or_returns_project_prompt(tmp_path, monkeypatch):
    store = PreferenceStore(tmp_path / "creator-preferences.json")
    monkeypatch.setattr(routes, "preference_store", store)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)

    saved = client.put(
        "/api/creative-director/preferences",
        json={
            "target_seconds": 60,
            "aspect_ratio": "16:9",
            "tone": "Warm",
            "visual_style": "Minimal",
            "narration_style": "Conversational",
            "caption_style": "Clean lower thirds",
            "music_preference": "Subtle ambient",
        },
    )
    assert saved.status_code == 200
    assert set(saved.json()) == {
        "target_seconds",
        "aspect_ratio",
        "tone",
        "visual_style",
        "narration_style",
        "caption_style",
        "music_preference",
        "narrator_gender",
        "narrator_tone",
        "narrator_style",
    }
    assert "prompt" not in saved.text.casefold()

    loaded = client.get("/api/creative-director/preferences")
    assert loaded.status_code == 200
    assert loaded.json()["target_seconds"] == 60

    cleared = client.delete("/api/creative-director/preferences")
    assert cleared.status_code == 200
    assert client.get("/api/creative-director/preferences").json()["target_seconds"] is None


def test_preferences_api_rejects_unknown_or_secret_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(
        routes,
        "preference_store",
        PreferenceStore(tmp_path / "creator-preferences.json"),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)

    response = client.put(
        "/api/creative-director/preferences",
        json={"api_key": "must-not-be-stored"},
    )

    assert response.status_code == 422
