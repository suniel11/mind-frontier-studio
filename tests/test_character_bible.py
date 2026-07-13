from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models import CharacterBible
from app.narrative.duration_planning import scenes_for_duration
from app.orchestration.project_pipeline import requires_character_bible
from app.production.scene_composer import compose_scene
from app.production.prompt_compiler import compile_prompt
from app.production.specification import ProductionSpecification
from app.services.media import FEMALE_VOICES, MALE_VOICES, voice_for_character
from app.visual.genre import classify_genre, presenter_frequency_cap
from app.visual.shot_planner import plan_shots
from app.visual.taxonomy import resolve_category

_STYLE = {"lens": "35mm", "color": "muted", "texture": "grain", "atmosphere": "clean", "composition": "thirds"}


def _character_bible(gender: str = "male") -> CharacterBible:
    return CharacterBible(
        name="Alex Morgan",
        narrative_role="host",
        gender=gender,
        age_range="35-45",
        facial_features="angular jaw, warm brown eyes",
        hair="short grey hair",
        wardrobe="navy wool coat",
        accessories="thin silver watch",
        body_language="calm, confident posture",
        color_palette="cool neutral tones",
        lighting_anchor="soft window light",
        prompt_anchor="a distinctive 40-year-old narrator, short grey hair, navy wool coat, warm brown eyes",
        negative_constraints="no change to face, age, hair, wardrobe, or accessories",
    )


def test_character_bible_requires_a_gender_field():
    with pytest.raises(ValidationError):
        CharacterBible.model_validate(
            {
                "name": "Alex Morgan",
                "narrative_role": "host",
                "age_range": "35-45",
                "facial_features": "angular jaw",
                "hair": "short grey hair",
                "wardrobe": "navy coat",
                "accessories": "watch",
                "body_language": "calm",
                "color_palette": "cool tones",
                "lighting_anchor": "soft light",
                "prompt_anchor": "anchor",
                "negative_constraints": "none",
            }
        )
    _character_bible()  # does not raise


def test_requires_character_bible_helper():
    assert requires_character_bible(None) is True
    assert requires_character_bible(
        ProductionSpecification(original_prompt="topic", protagonist_direction="none")
    ) is False
    assert requires_character_bible(
        ProductionSpecification(original_prompt="topic", protagonist_direction="a recurring scientist host")
    ) is True


def test_presenter_prompt_reuses_the_character_bible_anchor():
    bible = _character_bible()
    scene = SimpleNamespace(
        number=1, visual_type="presenter", subject_focus="", location_id="primary",
        continuity_anchor="same presenter", visual_emotion="warm", story_role="hook",
        narrative_goal="introduce the topic", narration="Welcome back.",
    )
    storyboard = SimpleNamespace(visual_memory=None)

    composition = compose_scene(scene, storyboard, character_bible=bible)
    assert bible.prompt_anchor in composition.subject

    prompt = compile_prompt(scene, composition, style=_STYLE, character_bible=bible)
    assert bible.prompt_anchor in prompt


def test_no_presenter_identity_injected_without_a_character_bible():
    # This is the requires_character == False path: character.run() is
    # skipped entirely upstream, so character_bible is None here.
    scene = SimpleNamespace(
        number=1, visual_type="presenter", subject_focus="", location_id="primary",
        continuity_anchor="", visual_emotion="", story_role="hook",
        narrative_goal="", narration="",
    )
    storyboard = SimpleNamespace(visual_memory=None)

    composition = compose_scene(scene, storyboard, character_bible=None)
    assert "protagonist" not in composition.subject.casefold()
    assert composition.subject == composition.environment


def test_visual_director_never_selects_a_presenter_when_not_required():
    spec = ProductionSpecification(original_prompt="physics documentary", protagonist_direction="none")
    roles = ["hook", "setup", "conflict", "insight", "resolution", "final_line"]
    scenes = [SimpleNamespace(number=i, story_role=role, narration="") for i, role in enumerate(roles, start=1)]
    storyboard = SimpleNamespace(scenes=scenes)

    shots = plan_shots(storyboard, spec)
    assert all(resolve_category(shot.visual_type).subject_kind != "character" for shot in shots)


def test_voice_gender_matches_character_bible_gender():
    assert voice_for_character(_character_bible(gender="male")) in MALE_VOICES
    assert voice_for_character(_character_bible(gender="female")) in FEMALE_VOICES
    assert not set(MALE_VOICES) & set(FEMALE_VOICES)


def test_no_gender_bias_when_no_character_bible_exists():
    assert voice_for_character(None, default_voice="onyx") == "onyx"


def test_presenter_frequency_caps_by_genre():
    def spec(subject: str) -> ProductionSpecification:
        return ProductionSpecification(original_prompt=subject, subject=subject)

    assert classify_genre(spec("laboratory physics experiments")) == "science"
    assert presenter_frequency_cap(spec("laboratory physics experiments")) == 0.15

    assert classify_genre(spec("ancient Roman empire history")) == "historical"
    assert presenter_frequency_cap(spec("ancient Roman empire history")) == 0.25

    assert classify_genre(spec("startup market strategy and revenue")) == "business"
    assert presenter_frequency_cap(spec("startup market strategy and revenue")) == 0.20

    assert classify_genre(spec("backpacking travel destination guide")) == "travel"
    assert presenter_frequency_cap(spec("backpacking travel destination guide")) == 0.30

    assert presenter_frequency_cap(None) == 0.25


def test_scientific_documentary_presenter_frequency_under_20_percent():
    spec = ProductionSpecification(
        original_prompt="laboratory physics experiments",
        subject="laboratory physics experiments and the scientific method",
        protagonist_direction="A recurring scientist host explains each experiment",
    )
    assert classify_genre(spec) == "science"
    assert presenter_frequency_cap(spec) < 0.20

    scene_count = scenes_for_duration(90)
    # Every scene's narration is written to strongly signal testimony/direct
    # address (quote + "she said"), which is exactly the content that would
    # otherwise push the Visual Director toward a presenter shot -- proving
    # the cap is actually enforcing a limit, not just an artifact of content
    # that never asked for a presenter in the first place.
    scenes = [
        SimpleNamespace(number=i, story_role="insight", narration='"This is remarkable," she said.')
        for i in range(1, scene_count + 1)
    ]
    storyboard = SimpleNamespace(scenes=scenes)

    shots = plan_shots(storyboard, spec)
    presenter_count = sum(
        1 for shot in shots if resolve_category(shot.visual_type).subject_kind == "character"
    )
    assert presenter_count / len(shots) < 0.20
