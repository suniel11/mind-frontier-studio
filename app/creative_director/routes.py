"""HTTP routes for the Creative Director conversation."""

from fastapi import APIRouter, HTTPException, status

from app.creative_director.engine import CreativeDirectorServiceError, director
from app.creative_director.models import (
    CreativeAnswers,
    CreativePrompt,
    ProductionBrief,
    QuestionResponse,
)
from app.creative_director.preferences import CreatorPreferences, preference_store


router = APIRouter(prefix="/creative-director", tags=["Creative Director"])


@router.get("")
def health_check() -> dict[str, str]:
    return {"status": "ok", "module": "creative_director"}


@router.post("/questions", response_model=QuestionResponse)
def creative_director_questions(payload: CreativePrompt) -> QuestionResponse:
    try:
        return QuestionResponse(questions=director.generate_questions(payload.prompt))
    except CreativeDirectorServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Creative Director is temporarily unavailable.",
        ) from exc


@router.post("/brief", response_model=ProductionBrief)
def creative_director_brief(payload: CreativeAnswers) -> ProductionBrief:
    try:
        return director.build_brief(payload.prompt, payload.answers)
    except CreativeDirectorServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Creative Director is temporarily unavailable.",
        ) from exc


@router.get("/preferences", response_model=CreatorPreferences)
def creative_director_preferences() -> CreatorPreferences:
    return preference_store.load()


@router.put("/preferences", response_model=CreatorPreferences)
def update_creative_director_preferences(
    payload: CreatorPreferences,
) -> CreatorPreferences:
    try:
        return preference_store.update(payload.model_dump(exclude_unset=True))
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Creator preferences could not be saved.",
        ) from exc


@router.delete("/preferences")
def clear_creative_director_preferences() -> dict[str, str]:
    try:
        preference_store.clear()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Creator preferences could not be cleared.",
        ) from exc
    return {"status": "cleared"}
