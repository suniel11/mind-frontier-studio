from __future__ import annotations

"""Pure, network-free helpers for propagating a requested runtime through the
storyboard and render pipeline.

These exist because the pipeline previously had two independent, disconnected
ideas of "how long is this video": the requested ``target_seconds`` (used only
to size a fixed six-scene template) and the actual narration audio duration
(determined solely by however many words the script happened to contain).
Nothing reconciled the two, so a 120s request could render a 20-30s video
whenever the generated script was short. Everything here is deterministic so
it can be unit tested without an OpenAI call.
"""

# Matches the average per-scene screen time implied by the original fixed
# six-scene / 45-second template (45 / 6 == 7.5s). Using it as the scaling
# ratio means a 45s request still yields exactly 6 scenes -- unchanged
# behavior at the default -- while longer requests get proportionally more
# scenes instead of stretching a handful of scenes to fill the runtime.
SECONDS_PER_SCENE = 7.5
MIN_SCENES = 6
MAX_SCENES = 24

DEFAULT_TOLERANCE = 0.05


def scenes_for_duration(target_seconds: int) -> int:
    """How many scenes a storyboard of this length should have.

    Scales with duration instead of silently defaulting to a fixed count.
    """

    raw = round(max(1, int(target_seconds)) / SECONDS_PER_SCENE)
    return max(MIN_SCENES, min(MAX_SCENES, raw))


def _narration_word_count(scene) -> int:
    text = str(getattr(scene, "narration", "") or "").strip()
    return len(text.split()) if text else 0


def allocate_durations(scenes: list, total_seconds: float) -> list[int]:
    """Split ``total_seconds`` across ``scenes``, weighted by each scene's own
    narration length whenever narration text exists (voice timing should
    influence scene duration), falling back to an equal split otherwise.

    Every scene gets at least 2 seconds and the returned durations always sum
    to exactly ``round(total_seconds)``.
    """

    count = len(scenes)
    if count == 0:
        return []

    target = max(count * 2, round(total_seconds))
    word_counts = [_narration_word_count(scene) for scene in scenes]
    total_words = sum(word_counts)

    if total_words > 0:
        weights = [max(wc, 1) for wc in word_counts]
    else:
        weights = [1] * count
    total_weight = sum(weights)

    durations = [max(2, round(target * weight / total_weight)) for weight in weights]

    difference = target - sum(durations)
    index = 0
    while difference != 0:
        direction = 1 if difference > 0 else -1
        slot = index % count
        candidate = durations[slot] + direction
        if candidate >= 2:
            durations[slot] = candidate
            difference -= direction
        index += 1
        if index > count * 1000:
            break  # pathological input guard; never loops in practice

    return durations


def retime_scenes(storyboard, actual_seconds: float) -> None:
    """Rewrite every scene's start/end seconds to match the real, measured
    narration duration instead of the originally requested target.

    Called after the narration audio has actually been synthesized, so the
    rendered video and its audio track always agree on total length --
    voice timing becomes the ground truth for scene duration.
    """

    scenes = list(storyboard.scenes)
    if not scenes:
        return

    durations = allocate_durations(scenes, actual_seconds)
    cursor = 0
    for scene, duration in zip(scenes, durations):
        scene.start_second = cursor
        scene.end_second = cursor + duration
        cursor += duration
    scenes[-1].end_second = max(scenes[-1].end_second, round(actual_seconds))


def duration_within_tolerance(
    actual_seconds: float,
    target_seconds: float,
    tolerance: float = DEFAULT_TOLERANCE,
) -> bool:
    if target_seconds <= 0:
        return True
    return abs(actual_seconds - target_seconds) / target_seconds <= tolerance


def estimate_words_for_duration(target_seconds: int, words_per_second: float = 2.5) -> int:
    """A calibratable estimate used to ask the script agent for narration
    sized to the target runtime. ``words_per_second`` should be replaced with
    an observed rate (measured words / measured seconds) on retry so the
    correction is based on how the actual TTS voice speaks, not a guess.
    """

    return max(10, round(max(1, target_seconds) * words_per_second))
