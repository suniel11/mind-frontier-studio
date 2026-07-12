from types import SimpleNamespace

from app.models import CharacterBible
from app.orchestration.project_pipeline import requires_character_bible
from app.production.preference_extraction import extract_explicit_preferences
from app.production.preference_resolver import resolve_preferences
from app.production.preferences import UserCreativePreferences
from app.production.specification import ProductionSpecification
from app.production.validation import validate_production
from app.services.media import (
    FEMALE_VOICES,
    MALE_VOICES,
    gender_for_voice,
    resolution_for_aspect_ratio,
    voice_for_character,
)
from app.visual.shot_planner import plan_shots
from app.visual.taxonomy import resolve_category


def _character_bible(gender: str) -> CharacterBible:
    return CharacterBible(
        name="Alex Morgan", narrative_role="host", gender=gender, age_range="35-45",
        facial_features="warm eyes", hair="short hair", wardrobe="navy coat",
        accessories="none", body_language="calm", color_palette="cool tones",
        lighting_anchor="soft light", prompt_anchor="a narrator", negative_constraints="none",
    )


# ---------------------------------------------------------------------------
# Voice selection: explicit narrator gender always wins.
# ---------------------------------------------------------------------------

def test_female_narrator_always_produces_female_voice():
    preferences = UserCreativePreferences(narrator={"gender": "female"})
    # Even with a male Character Bible (a mismatched/legacy bible), the
    # explicit narrator preference must still win.
    voice = voice_for_character(_character_bible("male"), preferences=preferences)
    assert voice in FEMALE_VOICES


def test_male_narrator_always_produces_male_voice():
    preferences = UserCreativePreferences(narrator={"gender": "male"})
    voice = voice_for_character(_character_bible("female"), preferences=preferences)
    assert voice in MALE_VOICES


def test_no_gender_specified_falls_back_to_character_bible():
    voice = voice_for_character(_character_bible("female"), preferences=None)
    assert voice in FEMALE_VOICES


def test_explicit_narrator_gender_applies_even_with_no_presenter_at_all():
    # A video can have a female narrator with no on-screen presenter at all
    # -- narrator gender must not require a Character Bible to exist.
    preferences = UserCreativePreferences(narrator={"gender": "female"})
    voice = voice_for_character(None, preferences=preferences, default_voice="onyx")
    assert voice in FEMALE_VOICES


# ---------------------------------------------------------------------------
# Presenter enabled/disabled -> Character Bible generation.
# ---------------------------------------------------------------------------

def test_no_presenter_disables_character_bible():
    spec = ProductionSpecification(
        original_prompt="A documentary with no presenter, female narrator.",
    )
    resolved = resolve_preferences(spec)
    assert resolved.preferences.presenter.enabled is False
    assert resolved.requires_character is False
    assert requires_character_bible(resolved) is False


def test_presenter_enabled_creates_character_bible():
    spec = ProductionSpecification(
        original_prompt="A documentary with an on-camera presenter explaining history.",
    )
    resolved = resolve_preferences(spec)
    assert resolved.preferences.presenter.enabled is True
    assert resolved.requires_character is True
    assert requires_character_bible(resolved) is True


def test_presenter_preference_overrides_protagonist_direction_default():
    # protagonist_direction alone would normally imply a character is
    # required; an explicit "no presenter" in the prompt must still win.
    spec = ProductionSpecification(
        original_prompt="A history video, no presenter please.",
        protagonist_direction="Create a recurring host character.",
    )
    resolved = resolve_preferences(spec)
    assert resolved.requires_character is False


# ---------------------------------------------------------------------------
# Runtime and aspect ratio preserved.
# ---------------------------------------------------------------------------

def test_runtime_preserved_from_explicit_prompt():
    spec = ProductionSpecification(
        original_prompt="Create a cinematic 2-minute documentary on how Earth was formed.",
        target_seconds=45,  # what the Creative Director guessed, priority 2
    )
    resolved = resolve_preferences(spec)
    assert resolved.target_seconds == 120  # priority 1 (explicit prompt) wins


def test_aspect_ratio_preserved_from_explicit_prompt():
    spec = ProductionSpecification(
        original_prompt="A vertical 60 second explainer video.",
        aspect_ratio="16:9",  # what the Creative Director guessed, priority 2
    )
    resolved = resolve_preferences(spec)
    assert resolved.aspect_ratio == "9:16"  # priority 1 (explicit prompt) wins

    width, height, _ = resolution_for_aspect_ratio(resolved.aspect_ratio)
    assert (width, height) == (1080, 1920)


def test_aspect_ratio_resolution_default_matches_historical_constants():
    assert resolution_for_aspect_ratio(None) == (1080, 1920, "1024x1536")
    assert resolution_for_aspect_ratio("16:9") == (1920, 1080, "1536x1024")


# ---------------------------------------------------------------------------
# User preferences override defaults (priority order).
# ---------------------------------------------------------------------------

def test_explicit_prompt_overrides_production_specification_defaults():
    # production_specification.preferences already has a (lower-priority)
    # value set, as if the Creative Director had guessed; the explicit
    # prompt text must still win once resolved.
    spec = ProductionSpecification(
        original_prompt="Use a FEMALE narrator for this piece.",
        preferences=UserCreativePreferences(narrator={"gender": "male"}),
    )
    resolved = resolve_preferences(spec)
    assert resolved.preferences.narrator.gender == "female"


def test_unset_fields_fall_through_to_lower_priority():
    spec = ProductionSpecification(
        original_prompt="A documentary about rivers.",  # no explicit narrator gender
        preferences=UserCreativePreferences(narrator={"gender": "male"}),
    )
    resolved = resolve_preferences(spec)
    assert resolved.preferences.narrator.gender == "male"  # priority 2 survives


def test_resolve_preferences_is_idempotent():
    spec = ProductionSpecification(original_prompt="A 90 second female-narrated documentary.")
    once = resolve_preferences(spec)
    twice = resolve_preferences(once)
    assert twice.preferences == once.preferences
    assert twice.target_seconds == once.target_seconds


# ---------------------------------------------------------------------------
# Visual Director respects presenter settings.
# ---------------------------------------------------------------------------

def test_visual_director_respects_presenter_disabled():
    spec = ProductionSpecification(original_prompt="A science documentary, no presenter.")
    resolved = resolve_preferences(spec)
    scenes = [
        SimpleNamespace(number=i, story_role=role, narration="he said it clearly")
        for i, role in enumerate(["hook", "setup", "conflict", "insight", "resolution", "final_line"], start=1)
    ]
    shots = plan_shots(SimpleNamespace(scenes=scenes), resolved)
    assert all(resolve_category(shot.visual_type).subject_kind != "character" for shot in shots)


def test_visual_director_respects_explicit_presenter_frequency():
    spec = ProductionSpecification(
        original_prompt="A documentary with an on-camera presenter.",
        preferences=UserCreativePreferences(visuals={"presenter_frequency": 0.5}),
    )
    resolved = resolve_preferences(spec)
    from app.visual.genre import presenter_frequency_cap
    assert presenter_frequency_cap(resolved) == 0.5


def test_visual_director_respects_explicit_diagram_preference():
    spec = ProductionSpecification(
        original_prompt="A business explainer.",
        preferences=UserCreativePreferences(visuals={"diagrams": True}),
    )
    resolved = resolve_preferences(spec)
    scene = SimpleNamespace(number=1, story_role="hook", narration="")
    shots = plan_shots(SimpleNamespace(scenes=[scene]), resolved)
    assert shots[0].visual_type == "process_diagram"


# ---------------------------------------------------------------------------
# Validation report.
# ---------------------------------------------------------------------------

def test_validation_report_matches_when_everything_honored():
    spec = ProductionSpecification(
        original_prompt="Use a FEMALE narrator, no presenter, 120 seconds, vertical, scientific documentary.",
    )
    resolved = resolve_preferences(spec)
    report = validate_production(
        resolved,
        actual_duration_seconds=118.0,
        narrator_voice="nova",
        narrator_gender_actual="female",
        character_bible=None,
        aspect_ratio_actual="9:16",
    )
    assert report.all_passed
    assert report.warnings == []


def test_validation_report_flags_mismatch_instead_of_hiding_it():
    spec = ProductionSpecification(original_prompt="Use a FEMALE narrator for this piece.")
    resolved = resolve_preferences(spec)
    report = validate_production(
        resolved,
        actual_duration_seconds=45.0,
        narrator_voice="onyx",
        narrator_gender_actual="male",  # wrong on purpose
        character_bible=None,
        aspect_ratio_actual="9:16",
    )
    assert report.all_passed is False
    assert any("female" in warning.casefold() for warning in report.warnings)


def test_gender_for_voice_round_trips_with_voice_for_character():
    preferences = UserCreativePreferences(narrator={"gender": "female"})
    voice = voice_for_character(None, preferences=preferences)
    assert gender_for_voice(voice) == "female"
