"""HTTP routes for the Creative Director conversation."""

from fastapi import APIRouter, HTTPException, status

from app.creative_director.engine import CreativeDirectorServiceError, director
from app.creative_director.models import (
    CreativeAnswers,
    CreativePrompt,
    ProductionBrief,
    QuestionResponse,
)


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
