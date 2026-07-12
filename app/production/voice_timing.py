from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.models import ShortScript
from app.narrative.duration_planning import (
    duration_within_tolerance,
    estimate_words_for_duration,
)

MAX_ATTEMPTS = 2


def synthesize_narration(
    script: ShortScript,
    target_seconds: int,
    output_path: Path,
    *,
    synthesize: Callable[[ShortScript, Path], None],
    probe_duration: Callable[[Path], float],
    resize_script: Callable[[ShortScript, int], ShortScript] | None = None,
    tolerance: float = 0.05,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[ShortScript, float]:
    """Synthesize narration audio and reconcile its measured length with the
    requested runtime.

    This is what makes the render pipeline stop silently truncating a video
    to whatever length the narration happened to come out to: the script is
    the thing that actually determines narration length, so a duration miss
    is corrected by resizing the script and re-synthesizing -- not by
    stretching or cropping the video after the fact.

    ``synthesize``, ``probe_duration``, and ``resize_script`` are injected so
    this can be exercised in tests without real TTS/LLM calls; the pipeline
    wires in the real OpenAI-backed implementations.

    Returns the (possibly corrected) script and the final measured duration.
    Callers should use the returned duration -- not ``target_seconds`` -- as
    the ground truth for scene timing, since it may still be outside
    tolerance after ``max_attempts`` (a bounded number of corrective passes,
    not a guarantee).
    """

    current_script = script
    measured = 0.0
    for attempt in range(max(1, max_attempts)):
        synthesize(current_script, output_path)
        measured = probe_duration(output_path)
        if duration_within_tolerance(measured, target_seconds, tolerance):
            break
        if resize_script is None or attempt == max_attempts - 1:
            break
        spoken_words = max(1, len(current_script.voiceover.split()))
        words_per_second = max(0.5, spoken_words / max(measured, 0.1))
        corrected_words = estimate_words_for_duration(target_seconds, words_per_second)
        current_script = resize_script(current_script, corrected_words)

    return current_script, measured
