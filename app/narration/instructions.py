from __future__ import annotations

"""Speech prompting: turn NarratorPreferences into a natural-language
delivery instruction for the TTS ``instructions`` parameter, instead of
sending only the script text. Every voice generation request includes this.
"""

from app.narration.style_presets import (
    ACCENT_LABELS,
    AGE_GUIDANCE,
    ENERGY_GUIDANCE,
    PACE_GUIDANCE,
    STYLE_GUIDANCE,
    TONE_GUIDANCE,
)

_BASELINE = (
    "Avoid sounding robotic or monotone. Pause naturally between ideas and "
    "emphasize discoveries and key moments."
)
_DEFAULT_FALLBACK = "Maintain a calm, thoughtful documentary pace."


def build_narration_instructions(preferences) -> str:
    narrator = getattr(preferences, "narrator", None)
    parts = [_BASELINE]

    if narrator is None:
        parts.append(_DEFAULT_FALLBACK)
        return " ".join(parts)

    if narrator.tone:
        parts.append(TONE_GUIDANCE.get(narrator.tone, f"Tone: {narrator.tone}."))
    if narrator.style:
        parts.append(STYLE_GUIDANCE.get(narrator.style, f"Style: {narrator.style}."))
    if narrator.pace:
        parts.append(PACE_GUIDANCE.get(narrator.pace, f"Pace: {narrator.pace}."))
    if narrator.energy:
        parts.append(ENERGY_GUIDANCE.get(narrator.energy, f"Energy: {narrator.energy}."))
    if narrator.age:
        parts.append(AGE_GUIDANCE.get(narrator.age, ""))
    if narrator.emotion:
        parts.append(f"Emotional quality: {narrator.emotion}.")
    if narrator.voice_style:
        parts.append(f"Voice style: {narrator.voice_style}.")
    if narrator.accent:
        label = ACCENT_LABELS.get(narrator.accent, narrator.accent)
        parts.append(
            f"Lean toward {label} pronunciation where natural "
            "(best effort; the voice provider does not guarantee accent control)."
        )

    if not narrator.tone and not narrator.style:
        parts.append(_DEFAULT_FALLBACK)

    return " ".join(part for part in parts if part)
