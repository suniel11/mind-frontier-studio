from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field, model_validator

from app.production.specification import ProductionSpecification

class ProjectRequest(BaseModel):
    """Backward-compatible project request with structured creator intent."""

    topic: str | None = Field(default=None, min_length=3, max_length=3000)
    target_seconds: int = Field(default=45, ge=20, le=180)
    production_specification: ProductionSpecification | None = None

    @model_validator(mode="before")
    @classmethod
    def fill_compatibility_fields(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        specification = data.get("production_specification")
        if specification:
            parsed = ProductionSpecification.model_validate(specification)
            data.setdefault("topic", parsed.effective_subject)
            data.setdefault("target_seconds", parsed.target_seconds)
        return data

    @model_validator(mode="after")
    def ensure_canonical_specification(self):
        if self.topic is None and self.production_specification is None:
            raise ValueError("Either topic or production_specification is required.")

        if self.production_specification is None:
            self.production_specification = ProductionSpecification.from_legacy(
                self.topic or "Untitled production",
                self.target_seconds,
            )
        else:
            updates: dict[str, object] = {}
            if "target_seconds" in self.model_fields_set:
                updates["target_seconds"] = self.target_seconds
            if updates:
                self.production_specification = self.production_specification.model_copy(
                    update=updates
                )
            self.topic = self.topic or self.production_specification.effective_subject
            self.target_seconds = self.production_specification.target_seconds
        return self

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
    gender: str
    age_range: str
    facial_features: str
    hair: str
    facial_hair: str = ""
    wardrobe: str
    accessories: str
    ethnicity: str = ""
    body_language: str
    color_palette: str
    lighting_anchor: str
    visual_style: str = ""
    continuity_tags: List[str] = Field(default_factory=list)
    prompt_anchor: str
    negative_constraints: str


class VisualMemory(BaseModel):
    primary_location: str
    secondary_location: str
    recurring_props: List[str]
    architecture_and_environment: str
    time_of_day: str
    weather_and_atmosphere: str
    color_palette: str
    lighting_language: str
    lens_language: str
    production_design_anchor: str
    continuity_rules: List[str]

class Scene(BaseModel):
    number: int
    start_second: int
    end_second: int
    narration: str
    on_screen_text: str
    visual_direction: str
    image_prompt: str

    story_role: str = "development"
    narrative_goal: str = ""
    continuity_anchor: str = ""
    location_id: str = "primary"
    emotional_intensity: int = Field(default=5, ge=1, le=10)
    pacing: str = "medium"

    visual_type: str = "character_action"
    caption_safe_area: str = "lower_third"
    subject_focus: str = ""

    shot_type: str = "medium"
    motion_type: str = "dolly_in"
    transition_type: str = "fade"
    visual_emotion: str = "reflective"
    caption_emphasis: str = ""

    lens_mm: int = 50
    composition: str = ""
    lighting_style: str = ""
    color_tone: str = ""
    focus_target: str = ""
    film_look: str = ""

    # Visual Asset Economy v3 (app.visual_continuity): the Visual Asset
    # Group this scene's image_prompt was resolved to. Empty means the
    # scene has its own unique image (identity plan / feature disabled) --
    # existing storyboards from before this feature default to "" and are
    # unaffected.
    visual_asset_group_id: str = ""

class Storyboard(BaseModel):
    visual_memory: VisualMemory
    story_arc_summary: str
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
    production_specification: ProductionSpecification | None = None
    warnings: List[str] = Field(default_factory=list)
    status: str = "complete"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    thumbnail_url: str | None = None
    publish_package_url: str | None = None
    media_validation: dict | None = None
    job_id: str | None = None
