from pydantic import BaseModel, Field
from typing import List

class ProjectRequest(BaseModel):
    topic: str = Field(min_length=5, max_length=300)
    target_seconds: int = Field(default=45, ge=20, le=60)

class ResearchBrief(BaseModel):
    central_question: str
    core_insight: str
    verified_points: List[str]
    cautions: List[str]
    audience_relevance: str
    possible_angles: List[str]

class ShortScript(BaseModel):
    title: str
    hook: str
    voiceover: str
    ending: str
    estimated_seconds: int

class Scene(BaseModel):
    number: int
    start_second: int
    end_second: int
    narration: str
    on_screen_text: str
    visual_direction: str
    image_prompt: str

class Storyboard(BaseModel):
    scenes: List[Scene]

class SeoPackage(BaseModel):
    title: str
    description: str
    hashtags: List[str]

class ProjectOutput(BaseModel):
    project_id: str
    topic: str
    research: ResearchBrief
    script: ShortScript
    storyboard: Storyboard
    seo: SeoPackage
    video_url: str | None = None
