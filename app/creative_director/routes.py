"""FastAPI routes for the Creative Director conversation."""

from fastapi import APIRouter

from app.creative_director.engine import director
from app.creative_director.models import CreativeAnswers, CreativePrompt


router = APIRouter(prefix="/creative-director", tags=["Creative Director"])


@router.get("")
def health_check():
    return {"status": "ok", "module": "creative_director"}


@router.post("/questions")
def creative_director_questions(payload: CreativePrompt):
    return {
        "questions": [
            question.model_dump()
            for question in director.generate_questions(payload.prompt)
        ]
    }


@router.post("/brief")
def creative_director_brief(payload: CreativeAnswers):
    return director.build_brief(payload.prompt, payload.answers)
