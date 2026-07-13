from __future__ import annotations

"""Voice selection: map narration preferences to the best available voice.

An explicit user gender choice always wins, independent of whether a
Character Bible exists at all (a video can have a female narrator with no
on-screen presenter). Every selection is logged. Accent is captured and
reflected in the speech-prompting instructions (see instructions.py) but
this OpenAI TTS integration cannot guarantee accent -- requesting one always
produces a validation warning rather than a silent unmet promise.
"""

import logging
from dataclasses import dataclass, field

from app.narration.style_presets import ACCENT_LABELS, PACE_SPEED_MULTIPLIER

logger = logging.getLogger(__name__)

# Voice pools split by gender. Two voices per gender leaves room for a
# secondary lever without pretending to guarantee accent.
MALE_VOICES = ("onyx", "echo")
FEMALE_VOICES = ("nova", "shimmer")


@dataclass
class VoiceSelection:
    voice: str
    gender: str | None
    source: str  # "explicit_preference" | "character_bible" | "default"
    speed: float | None
    warnings: list[str] = field(default_factory=list)


def _normalize_gender(value: str | None) -> str | None:
    gender = str(value or "").strip().casefold()
    if gender in {"male", "man", "masculine", "m"}:
        return "male"
    if gender in {"female", "woman", "feminine", "f"}:
        return "female"
    return None


def gender_for_voice(voice: str) -> str | None:
    if voice in MALE_VOICES:
        return "male"
    if voice in FEMALE_VOICES:
        return "female"
    return None


def effective_speed(preferences) -> float | None:
    narrator = getattr(preferences, "narrator", None)
    if narrator is None:
        return None
    if narrator.speaking_speed is not None:
        return narrator.speaking_speed
    if narrator.pace is not None:
        return PACE_SPEED_MULTIPLIER.get(narrator.pace)
    return None


def select_voice(character_bible, preferences=None, default_voice: str = "onyx") -> VoiceSelection:
    narrator = getattr(preferences, "narrator", None)
    explicit_gender = _normalize_gender(getattr(narrator, "gender", None))
    bible_gender = _normalize_gender(getattr(character_bible, "gender", None))
    gender = explicit_gender or bible_gender

    if gender == "male":
        voice = MALE_VOICES[0]
    elif gender == "female":
        voice = FEMALE_VOICES[0]
    else:
        voice = default_voice

    source = "explicit_preference" if explicit_gender else ("character_bible" if bible_gender else "default")

    warnings: list[str] = []
    accent = getattr(narrator, "accent", None)
    if accent:
        label = ACCENT_LABELS.get(accent, accent)
        warnings.append(
            f"Narrator accent '{label}' was requested but the configured TTS provider "
            "does not offer explicit accent selection -- it is reflected in delivery "
            "instructions on a best-effort basis only, not guaranteed."
        )

    selection = VoiceSelection(
        voice=voice,
        gender=gender,
        source=source,
        speed=effective_speed(preferences),
        warnings=warnings,
    )

    logger.info(
        "Narrator voice selected: %s (gender=%s, source=%s, speed=%s)",
        selection.voice,
        selection.gender or "unspecified",
        selection.source,
        selection.speed,
    )
    return selection
