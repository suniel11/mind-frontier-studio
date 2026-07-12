from __future__ import annotations

"""Narration guidance text registries.

Each of these maps a closed preference value (see
app/production/preferences.py:NarratorPreferences) to a natural-language
delivery instruction fed to the TTS ``instructions`` parameter -- the
"speech prompting" mechanism: instead of just sending script text, every
voice generation request carries explicit style guidance.
"""

STYLE_GUIDANCE: dict[str, str] = {
    "netflix_documentary": (
        "Warm, cinematic, unhurried delivery with a sense of scale and "
        "wonder, like a premium streaming documentary."
    ),
    "bbc": (
        "Measured, authoritative, precise diction with restrained warmth, "
        "in the register of a BBC documentary narrator."
    ),
    "national_geographic": (
        "Awe-driven, exploratory, confident delivery that treats every "
        "fact like a discovery worth marveling at."
    ),
    "vox_explainer": (
        "Clear, brisk, conversational explainer energy -- friendly "
        "authority, get-to-the-point pacing."
    ),
    "teacher": (
        "Patient, clear, encouraging delivery that checks for "
        "understanding, as if explaining to an attentive student."
    ),
    "podcast": (
        "Relaxed, intimate, conversational close-microphone presence, "
        "like talking to one listener directly."
    ),
    "storyteller": (
        "Evocative, character-driven delivery with expressive pacing, "
        "building tension and release like a story being told aloud."
    ),
}

TONE_GUIDANCE: dict[str, str] = {
    "calm": "Speak calmly and steadily, with a settled, unhurried presence.",
    "documentary": "Speak with grounded, matter-of-fact documentary authority.",
    "inspirational": "Speak with uplifting, motivating warmth that builds toward hope.",
    "serious": "Speak with gravity and restraint, treating the subject with weight.",
    "dramatic": "Speak with dramatic tension, letting key moments land with impact.",
    "emotional": "Speak with genuine emotional resonance, letting feeling show through.",
    "curious": "Speak with open, inquisitive curiosity, as if discovering this alongside the listener.",
    "investigative": "Speak with probing, alert, uncover-the-truth energy.",
    "educational": "Speak clearly and instructively, prioritizing comprehension.",
}

AGE_GUIDANCE: dict[str, str] = {
    "young_adult": "Sound like a voice in their twenties or early thirties.",
    "adult": "Sound like a voice in their thirties to fifties.",
    "mature": "Sound like a seasoned voice, sixties or older.",
}

PACE_GUIDANCE: dict[str, str] = {
    "slow": "Speak at a slower, deliberate pace with generous space between ideas.",
    "normal": "Speak at a natural, moderate conversational pace.",
    "fast": "Speak at a brisk, energetic pace without rushing words together.",
}

# Best-effort secondary lever alongside the instructions text -- passed to
# the TTS API's own speed parameter when the model honors it.
PACE_SPEED_MULTIPLIER: dict[str, float] = {"slow": 0.85, "normal": 1.0, "fast": 1.15}

ENERGY_GUIDANCE: dict[str, str] = {
    "low": "Keep energy low and subdued, with minimal vocal peaks.",
    "medium": "Keep energy balanced and present, neither flat nor excitable.",
    "high": "Keep energy high and dynamic, with lively vocal peaks.",
}

ACCENT_LABELS: dict[str, str] = {
    "american": "American English",
    "british": "British English",
    "australian": "Australian English",
    "indian": "Indian English",
    "neutral_english": "neutral, accent-light English",
}
