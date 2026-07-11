from pydantic import BaseModel
from typing import List, Dict, Any


class CreativePrompt(BaseModel):
    prompt: str


class CreativeAnswers(BaseModel):
    prompt: str
    answers: Dict[str, Any]


class DirectorQuestion(BaseModel):
    id: str
    question: str
    type: str = "single_choice"
    options: List[str]


class ProductionBrief(BaseModel):
    topic: str
    target_seconds: int
    hook_type: str
    creative_brief: str