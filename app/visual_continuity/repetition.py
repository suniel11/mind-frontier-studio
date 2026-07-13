from __future__ import annotations

import re

# Verified against real produced storyboards: shot_type and visual_emotion
# cycle through a small repeating set across a whole video as a deliberate
# directorial rhythm (e.g. wide_environment/recognition recurring every 4th
# scene) -- matching on those two fields alone would misfire constantly.
# caption_emphasis and subject_focus are the opposite: essentially unique
# per scene in practice. Requiring *all* comparable framing fields to agree
# (not just a couple) means this only fires when scenes are framed
# identically in every dimension we can see -- a real, if rare, signal --
# while narration similarity independently catches the more common failure
# mode observed in real data: two scenes with near-duplicate narration text
# (a script-level repeat, not a deliberate continuity shot).
_FRAMING_FIELDS = ("shot_type", "visual_emotion", "caption_emphasis", "subject_focus")
_MIN_COMPARABLE_FRAMING_SIGNALS = 3
_NARRATION_SIMILARITY_THRESHOLD = 0.6


_PUNCTUATION = re.compile(r"[^\w\s]")


def _narration_similarity(a: str, b: str) -> float:
    """Jaccard word-overlap similarity, 0.0-1.0, ignoring punctuation (two
    scenes saying the same words with a different comma/period should
    still count as near-duplicate). A cheap, deterministic proxy for
    "these two scenes are saying almost the same thing" -- no
    embedding/model call, in keeping with "do not introduce additional
    models"."""

    words_a = set(_PUNCTUATION.sub("", a.casefold()).split())
    words_b = set(_PUNCTUATION.sub("", b.casefold()).split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def repetition_risk(previous_scene, candidate_scene) -> tuple[bool, str]:
    """Would reusing the shared anchor for ``candidate_scene`` right after
    ``previous_scene`` risk looking like the same shot twice, even with a
    different camera treatment?

    Returns ``(is_risky, reason)``. ``reason`` is empty when not risky.
    """

    similarity = _narration_similarity(previous_scene.narration, candidate_scene.narration)
    if similarity >= _NARRATION_SIMILARITY_THRESHOLD:
        return True, f"narration is {similarity:.0%} similar to the previous scene in this group"

    comparable = 0
    matched = 0
    for field_name in _FRAMING_FIELDS:
        a = (getattr(previous_scene, field_name, "") or "").strip().casefold()
        b = (getattr(candidate_scene, field_name, "") or "").strip().casefold()
        if a and b:
            comparable += 1
            if a == b:
                matched += 1

    if comparable >= _MIN_COMPARABLE_FRAMING_SIGNALS and matched == comparable:
        return True, f"identical framing across all {comparable} comparable signals (shot_type/visual_emotion/caption_emphasis/subject_focus)"

    return False, ""
