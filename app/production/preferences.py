from __future__ import annotations

"""The single source of truth for explicit creator preferences.

Every downstream stage (character generation, voice selection, the Visual
Director, prompt compilation, the renderer) should read the resolved
``UserCreativePreferences`` on a project's ``ProductionSpecification``
instead of inventing its own default. See
``app/production/preference_resolver.py`` for how a field gets its final
value: explicit prompt text beats the Creative Director's structured
specification, which beats genre defaults, which beats system defaults.

All fields are optional. ``None`` means "not specified at this priority
level" -- it is a distinct state from an explicit False/off, which callers
must preserve while merging.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Gender = Literal["male", "female"]
NarratorAge = Literal["young_adult", "adult", "mature"]
NarratorTone = Literal[
    "calm", "documentary", "inspirational", "serious", "dramatic",
    "emotional", "curious", "investigative", "educational",
]
NarratorStyle = Literal[
    "netflix_documentary", "bbc", "national_geographic", "vox_explainer",
    "teacher", "podcast", "storyteller",
]
NarratorPace = Literal["slow", "normal", "fast"]
NarratorEnergy = Literal["low", "medium", "high"]
NarratorAccent = Literal["american", "british", "australian", "indian", "neutral_english"]

CaptionTheme = Literal[
    "netflix_documentary", "bbc_documentary", "national_geographic",
    "vox", "minimal", "modern", "cinematic",
]
CaptionAnimation = Literal["fade", "slide", "pop", "none"]
CaptionPosition = Literal["bottom", "lower_third", "middle", "top"]


class NarratorPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gender: Gender | None = None
    age: NarratorAge | None = None
    accent: NarratorAccent | None = None
    language: str | None = None
    speaking_speed: float | None = Field(default=None, ge=0.5, le=2.0)
    tone: NarratorTone | None = None
    style: NarratorStyle | None = None
    pace: NarratorPace | None = None
    energy: NarratorEnergy | None = None
    emotion: str | None = None
    voice_style: str | None = None


class PresenterPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    gender: Gender | None = None
    age: str | None = None
    appearance: str | None = None
    wardrobe: str | None = None
    continuity: str | None = None


class VideoPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_seconds: int | None = Field(default=None, ge=20, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] | None = None
    cinematic_style: str | None = None
    pacing: str | None = None
    documentary_style: str | None = None
    realism: str | None = None
    motion_intensity: str | None = None


class VisualsPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realism: str | None = None
    illustration: bool | None = None
    diagrams: bool | None = None
    presenter_frequency: float | None = Field(default=None, ge=0.0, le=1.0)
    scientific_visuals: bool | None = None
    archival_visuals: bool | None = None


class RenderingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtitles: bool | None = None
    background_music: bool | None = None
    transitions: str | None = None


class CaptionsPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: CaptionTheme | None = None
    animation: CaptionAnimation | None = None
    position: CaptionPosition | None = None


class UserCreativePreferences(BaseModel):
    """Composed preference set covering every stage of the pipeline."""

    model_config = ConfigDict(extra="forbid")

    narrator: NarratorPreferences = Field(default_factory=NarratorPreferences)
    presenter: PresenterPreferences = Field(default_factory=PresenterPreferences)
    video: VideoPreferences = Field(default_factory=VideoPreferences)
    visuals: VisualsPreferences = Field(default_factory=VisualsPreferences)
    rendering: RenderingPreferences = Field(default_factory=RenderingPreferences)
    captions: CaptionsPreferences = Field(default_factory=CaptionsPreferences)

    def merged_over(self, lower_priority: "UserCreativePreferences") -> "UserCreativePreferences":
        """Return preferences with ``self``'s explicit fields taking priority
        over ``lower_priority``'s, falling back field-by-field where ``self``
        left a field unset (``None``)."""

        def merge_model(high: BaseModel, low: BaseModel) -> BaseModel:
            data = {}
            for field in type(high).model_fields:
                high_value = getattr(high, field)
                data[field] = high_value if high_value is not None else getattr(low, field)
            return type(high).model_validate(data)

        return UserCreativePreferences(
            narrator=merge_model(self.narrator, lower_priority.narrator),
            presenter=merge_model(self.presenter, lower_priority.presenter),
            video=merge_model(self.video, lower_priority.video),
            visuals=merge_model(self.visuals, lower_priority.visuals),
            rendering=merge_model(self.rendering, lower_priority.rendering),
            captions=merge_model(self.captions, lower_priority.captions),
        )
