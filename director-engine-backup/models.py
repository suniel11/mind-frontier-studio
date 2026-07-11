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


class CharacterBible(BaseModel):
    name: str
    narrative_role: str
    age_range: str
    facial_features: str
    hair: str
    wardrobe: str
    accessories: str
    body_language: str
    color_palette: str
    lighting_anchor: str
    prompt_anchor: str
    negative_constraints: str

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
    character_bible: CharacterBible | None = None
    seo: SeoPackage
    video_url: str | None = None
