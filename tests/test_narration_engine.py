import json
from pathlib import Path

from app.models import CharacterBible
from app.narration.instructions import build_narration_instructions
from app.narration.pauses import plan_pauses
from app.narration.pronunciation import apply_pronunciation_hints
from app.narration.report import build_narration_report, save_narration_report
from app.narration.style_presets import PACE_GUIDANCE, PACE_SPEED_MULTIPLIER, STYLE_GUIDANCE, TONE_GUIDANCE
from app.narration.voice_selection import (
    FEMALE_VOICES,
    MALE_VOICES,
    effective_speed,
    select_voice,
)
from app.production.preferences import NarratorPreferences, UserCreativePreferences


def _prefs(**narrator_kwargs) -> UserCreativePreferences:
    return UserCreativePreferences(narrator=NarratorPreferences(**narrator_kwargs))


def _character_bible(gender: str) -> CharacterBible:
    return CharacterBible(
        name="Alex Morgan", narrative_role="host", gender=gender, age_range="35-45",
        facial_features="warm eyes", hair="short hair", wardrobe="navy coat",
        accessories="none", body_language="calm", color_palette="cool tones",
        lighting_anchor="soft light", prompt_anchor="a narrator", negative_constraints="none",
    )


# ---------------------------------------------------------------------------
# Narrator preference propagation.
# ---------------------------------------------------------------------------

def test_narrator_gender_propagates():
    selection = select_voice(None, _prefs(gender="female"), default_voice="onyx")
    assert selection.voice in FEMALE_VOICES
    assert selection.gender == "female"
    assert selection.source == "explicit_preference"

    selection = select_voice(None, _prefs(gender="male"), default_voice="onyx")
    assert selection.voice in MALE_VOICES


def test_narrator_tone_propagates():
    instructions = build_narration_instructions(_prefs(tone="investigative"))
    assert TONE_GUIDANCE["investigative"] in instructions

    instructions = build_narration_instructions(_prefs(tone="calm"))
    assert TONE_GUIDANCE["calm"] in instructions


def test_narrator_style_propagates():
    instructions = build_narration_instructions(_prefs(style="podcast"))
    assert STYLE_GUIDANCE["podcast"] in instructions

    instructions = build_narration_instructions(_prefs(style="national_geographic"))
    assert STYLE_GUIDANCE["national_geographic"] in instructions


def test_narrator_pace_propagates():
    instructions = build_narration_instructions(_prefs(pace="fast"))
    assert PACE_GUIDANCE["fast"] in instructions

    assert effective_speed(_prefs(pace="slow")) == PACE_SPEED_MULTIPLIER["slow"]
    assert effective_speed(_prefs(pace="fast")) == PACE_SPEED_MULTIPLIER["fast"]
    # An explicit numeric speaking_speed always outranks the pace preset.
    assert effective_speed(_prefs(pace="slow", speaking_speed=1.3)) == 1.3


def test_narrator_energy_and_age_propagate_into_instructions():
    instructions = build_narration_instructions(_prefs(energy="high", age="mature"))
    assert "high" in instructions.casefold() or "dynamic" in instructions.casefold()
    assert "sixties" in instructions.casefold() or "seasoned" in instructions.casefold()


def test_baseline_instructions_present_without_any_preferences():
    instructions = build_narration_instructions(None)
    assert "robotic" in instructions.casefold()
    assert "pause" in instructions.casefold()


# ---------------------------------------------------------------------------
# Voice selection.
# ---------------------------------------------------------------------------

def test_voice_selection_honors_explicit_user_preference_over_character_bible():
    # Character Bible says male; explicit narrator preference says female --
    # the explicit preference must win.
    selection = select_voice(_character_bible("male"), _prefs(gender="female"))
    assert selection.voice in FEMALE_VOICES
    assert selection.source == "explicit_preference"


def test_voice_selection_falls_back_to_character_bible_gender():
    selection = select_voice(_character_bible("female"), None)
    assert selection.voice in FEMALE_VOICES
    assert selection.source == "character_bible"


def test_voice_selection_falls_back_to_default_with_no_signal():
    selection = select_voice(None, None, default_voice="onyx")
    assert selection.voice == "onyx"
    assert selection.source == "default"


def test_explicit_accent_always_produces_a_validation_warning():
    selection = select_voice(None, _prefs(gender="female", accent="british"))
    assert any("accent" in warning.casefold() for warning in selection.warnings)
    assert any("not guarantee" in warning.casefold() for warning in selection.warnings)

    unaccented = select_voice(None, _prefs(gender="female"))
    assert unaccented.warnings == []


# ---------------------------------------------------------------------------
# Validation / narration report.
# ---------------------------------------------------------------------------

def test_validation_report_generated(tmp_path: Path):
    preferences = _prefs(gender="female", tone="investigative", style="bbc", pace="slow", accent="british")
    selection = select_voice(None, preferences)

    report = build_narration_report(preferences, selection, provider="openai")
    assert report.selected_voice == selection.voice
    assert report.style == "bbc"
    assert report.tone == "investigative"
    assert report.pace == "slow"
    assert report.provider == "openai"
    assert report.warnings  # accent warning present
    assert report.requested["gender"] == "female"

    path = save_narration_report(tmp_path, report)
    assert path.name == "narration-report.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["selected_voice"] == selection.voice
    assert set(saved) == {"requested", "selected_voice", "style", "tone", "pace", "provider", "warnings"}


# ---------------------------------------------------------------------------
# Pauses / pronunciation never touch caption source text.
# ---------------------------------------------------------------------------

def test_pause_planning_inserts_cues_without_mutating_original():
    original = "Scientists discovered a new species. In the end, the finding changed everything."
    tts_copy = plan_pauses(original)
    assert tts_copy != original or "discovered" not in original
    assert original == "Scientists discovered a new species. In the end, the finding changed everything."
    assert "..." in tts_copy


def test_pronunciation_hints_apply_only_to_tts_copy():
    caption_text = "Nietzsche wrote about the eternal return."
    tts_copy = apply_pronunciation_hints(caption_text)
    assert tts_copy != caption_text
    assert "NEE-cha" in tts_copy
    # The original (what captions would read) is untouched.
    assert caption_text == "Nietzsche wrote about the eternal return."


def test_pronunciation_hints_are_whole_word_and_case_insensitive():
    assert "NEE-cha" in apply_pronunciation_hints("NIETZSCHE said so.")
    assert "EYEN-stine" in apply_pronunciation_hints("Einstein published the paper.")
    # Must not match inside an unrelated longer word that merely contains
    # "einstein" as a substring.
    assert "EYEN-stine" not in apply_pronunciation_hints("An einsteinian idea.")
