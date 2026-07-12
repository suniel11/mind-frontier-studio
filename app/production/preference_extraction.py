from __future__ import annotations

"""Deterministic extraction of explicit preferences from the raw user prompt.

This is priority level 1 -- "explicit user prompt" -- in the resolution
order described in app/production/preference_resolver.py. It exists because
an LLM (the Creative Director) carrying a instruction like "use a FEMALE
narrator" through several structured-output hops is not a guarantee; a
regex/keyword pass over the user's own words is. Every pattern here detects
the *shape* of an instruction (a gender word next to a narrator/presenter
anchor word, a number next to a duration unit, ...), not any topic -- it
works the same regardless of subject matter.
"""

import re

from app.production.preferences import UserCreativePreferences

_CLAUSE_SPLIT = re.compile(r"[.!?;\n]+")

_NARRATOR_ANCHORS = ("narrator", "narration", "voiceover", "voice-over", "voice over", "narrated", "narrate", "narrating")
_PRESENTER_ANCHORS = ("presenter", "host", "on-camera", "on camera", "protagonist", "spokesperson")

_FEMALE_WORDS = ("female", "woman", "women", "feminine", "actress")
_MALE_WORDS = ("male", "man", "men", "masculine", "actor")

_PRESENTER_DISABLE_CUES = (
    "no presenter", "without a presenter", "no host", "without a host",
    "no on-camera", "no on camera", "faceless", "voice only", "voiceover only",
    "no character", "no protagonist", "no recurring character", "not required",
)
_PRESENTER_ENABLE_CUES = (
    "with a presenter", "with a host", "on-camera presenter", "on camera presenter",
    "on-camera host", "on camera host", "featuring a presenter", "featuring a host",
    "presenter explains", "host explains", "recurring character", "recurring presenter",
)

_SUBTITLES_DISABLE_CUES = ("no subtitles", "without subtitles", "no captions", "without captions")
_SUBTITLES_ENABLE_CUES = ("with subtitles", "with captions", "include subtitles", "include captions")

_MUSIC_DISABLE_CUES = ("no music", "without music", "no background music", "silent background", "no soundtrack")
_MUSIC_ENABLE_CUES = ("with music", "background music", "with a soundtrack")

_ASPECT_RATIO_CUES = (
    ("9:16", "9:16"), ("vertical", "9:16"), ("portrait", "9:16"),
    ("16:9", "16:9"), ("landscape", "16:9"), ("widescreen", "16:9"),
    ("4:5", "4:5"),
    ("1:1", "1:1"), ("square", "1:1"),
)

_MINUTE_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:-|\s)?(?:minutes?|mins?)\b")
_SECOND_PATTERN = re.compile(r"\b(\d{1,3})\s*(?:-|\s)?(?:seconds?|secs?)\b")


def _clauses(text: str) -> list[str]:
    return list(_CLAUSE_SPLIT.split(text.casefold()))


def _gender_near(text: str, anchors: tuple[str, ...]) -> str | None:
    for clause in _clauses(text):
        if not any(anchor in clause for anchor in anchors):
            continue
        if any(re.search(rf"\b{re.escape(word)}\b", clause) for word in _FEMALE_WORDS):
            return "female"
        if any(re.search(rf"\b{re.escape(word)}\b", clause) for word in _MALE_WORDS):
            return "male"
    return None


def _first_cue(text: str, cues: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(cue in lowered for cue in cues)


def _extract_runtime_seconds(text: str) -> int | None:
    lowered = text.casefold()
    minute_match = _MINUTE_PATTERN.search(lowered)
    if minute_match:
        return max(20, min(180, round(float(minute_match.group(1)) * 60)))
    second_match = _SECOND_PATTERN.search(lowered)
    if second_match:
        return max(20, min(180, int(second_match.group(1))))
    return None


def _extract_aspect_ratio(text: str) -> str | None:
    lowered = text.casefold()
    for cue, ratio in _ASPECT_RATIO_CUES:
        if cue in lowered:
            return ratio
    return None


def extract_explicit_preferences(prompt: str) -> UserCreativePreferences:
    """Scan the raw prompt for unambiguous, explicit instructions.

    Only fields the prompt actually states are set; everything else is left
    ``None`` so the resolver can fall through to lower-priority sources.
    """

    preferences = UserCreativePreferences()

    preferences.narrator.gender = _gender_near(prompt, _NARRATOR_ANCHORS)

    # Disable cues always win when both match: a phrase like "no on-camera
    # presenter" legitimately contains the enable cue "on-camera presenter"
    # as a substring, so enable cues are only trusted when no negation is
    # present anywhere in the prompt.
    if _first_cue(prompt, _PRESENTER_DISABLE_CUES):
        preferences.presenter.enabled = False
    elif _first_cue(prompt, _PRESENTER_ENABLE_CUES):
        preferences.presenter.enabled = True

    # A presenter's gender is only taken from clauses anchored on a
    # presenter/host word -- distinct from the narrator's voice, since a
    # video can have a female narrator with no on-screen presenter at all.
    preferences.presenter.gender = _gender_near(prompt, _PRESENTER_ANCHORS)

    preferences.video.runtime_seconds = _extract_runtime_seconds(prompt)
    preferences.video.aspect_ratio = _extract_aspect_ratio(prompt)

    if _first_cue(prompt, _SUBTITLES_DISABLE_CUES):
        preferences.rendering.subtitles = False
    elif _first_cue(prompt, _SUBTITLES_ENABLE_CUES):
        preferences.rendering.subtitles = True

    if _first_cue(prompt, _MUSIC_DISABLE_CUES):
        preferences.rendering.background_music = False
    elif _first_cue(prompt, _MUSIC_ENABLE_CUES):
        preferences.rendering.background_music = True

    return preferences
