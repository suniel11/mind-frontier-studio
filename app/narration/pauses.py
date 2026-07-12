from __future__ import annotations

"""Automatic pause planning for TTS input text.

Inserts pause cues (extra punctuation the TTS model reads as a delivery
beat) after discoveries, before conclusions, and before major transitions.
This only ever modifies a *copy* of the text used for narration synthesis
-- never ``scene.narration``, which the caption engine reads verbatim. Cue
detection is structural (a handful of common English discourse markers),
not topic-specific, so it applies the same way across every documentary
subject.
"""

import re

SHORT_PAUSE = ","
MEDIUM_PAUSE = "..."
LONG_PAUSE = "...\n\n"

_DISCOVERY_CUES = (
    "discovered", "revealed", "found that", "realized", "breakthrough",
    "uncovered", "turns out",
)
_CONCLUSION_CUES = (
    "in the end", "ultimately", "in conclusion", "and so", "in the final analysis",
)
_TRANSITION_CUES = (
    "however", "but then", "meanwhile", "years later", "at the same time",
    "eventually", "from there",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def plan_pauses(text: str) -> str:
    """Return a TTS-input copy of ``text`` with pause cues inserted before
    conclusions/transitions and after discoveries."""

    sentences = [s for s in _SENTENCE_SPLIT.split(text.strip()) if s]
    if not sentences:
        return text

    result: list[str] = []
    for sentence in sentences:
        lowered = sentence.casefold()
        prefix = ""
        if any(cue in lowered for cue in _CONCLUSION_CUES) or any(
            cue in lowered for cue in _TRANSITION_CUES
        ):
            prefix = MEDIUM_PAUSE + " "

        rendered = prefix + sentence
        if any(cue in lowered for cue in _DISCOVERY_CUES):
            rendered = rendered.rstrip() + " " + MEDIUM_PAUSE
        result.append(rendered)

    return " ".join(result)


def join_sections_with_pauses(sections: list[str]) -> str:
    """Join separate narration sections (e.g. per-scene text) into one TTS
    input with a long pause between each -- "between sections"."""

    return LONG_PAUSE.join(section.strip() for section in sections if section.strip())
