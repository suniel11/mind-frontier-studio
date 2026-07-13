from __future__ import annotations

import base64
import io
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from app.models import Scene, Storyboard, VisualMemory
from app.services import media
from app.services.cancellation import RenderCancelled
from app.services.rate_limiter import SlidingWindowRateLimiter

_buffer = io.BytesIO()
Image.new("RGB", (32, 32), color=(50, 60, 70)).save(_buffer, format="PNG")
_FAKE_B64 = base64.b64encode(_buffer.getvalue()).decode("ascii")


def _storyboard(count: int) -> Storyboard:
    scenes = [
        Scene(
            number=index + 1, start_second=index * 5, end_second=(index + 1) * 5,
            narration=f"Scene {index + 1} narration.", on_screen_text="",
            visual_direction="wide shot", image_prompt=f"scene {index + 1} prompt",
        )
        for index in range(count)
    ]
    memory = VisualMemory(
        primary_location="lab", secondary_location="hallway", recurring_props=[],
        architecture_and_environment="modern", time_of_day="day",
        weather_and_atmosphere="clear", color_palette="cool", lighting_language="soft",
        lens_language="35mm", production_design_anchor="minimal", continuity_rules=[],
    )
    return Storyboard(visual_memory=memory, story_arc_summary="A short arc.", scenes=scenes)


class _VariableLatencyImages:
    """Later-numbered scenes finish *faster* than earlier ones, so
    completion order is guaranteed to differ from submission order --
    proving the result list is reordered back to scene order rather than
    just trusting as_completed()."""

    def __init__(self):
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def generate(self, **kwargs):
        prompt = kwargs["prompt"]
        with self._lock:
            self.calls.append(prompt)
        scene_number = int("".join(ch for ch in prompt.split()[1] if ch.isdigit()) or "1")
        time.sleep(0.05 * (10 - scene_number) if scene_number <= 9 else 0.01)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=_FAKE_B64)])


class _FailingImages:
    def generate(self, **kwargs):
        raise RuntimeError("simulated image generation failure")


class _FakeClient:
    def __init__(self, images):
        self.images = images


@pytest.fixture(autouse=True)
def _permissive_rate_limit(monkeypatch):
    # These tests assert on real elapsed wall-clock time to prove
    # concurrency, so the shared production rate limiter (a handful of
    # calls per real 60s minute) must not throttle them -- rate-limiting
    # behavior itself is covered separately in
    # test_image_generation_rate_limiting.py with an injectable clock.
    monkeypatch.setattr(
        media, "_image_rate_limiter", SlidingWindowRateLimiter(max_calls=10_000, period_seconds=60.0)
    )
    yield


def test_images_are_generated_concurrently_not_sequentially(tmp_path, monkeypatch):
    storyboard = _storyboard(8)
    images_api = _VariableLatencyImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    start = time.perf_counter()
    result = media._generate_scene_images(
        storyboard, tmp_path, width=64, height=64, size="1024x1536", aspect_ratio="9:16",
    )
    elapsed = time.perf_counter() - start

    # Sequential would take sum(0.05*(10-n) for n in 1..8) ~= 1.4s; with
    # bounded 4-way concurrency this must be well under half that.
    assert elapsed < 0.9, f"took {elapsed:.2f}s -- calls do not appear to run concurrently"
    assert len(images_api.calls) == 8


def test_results_are_returned_in_scene_order_regardless_of_completion_order(tmp_path, monkeypatch):
    storyboard = _storyboard(6)
    images_api = _VariableLatencyImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    result = media._generate_scene_images(
        storyboard, tmp_path, width=64, height=64, size="1024x1536", aspect_ratio="9:16",
    )

    assert [path.name for path in result] == [f"scene-{n:02d}.jpg" for n in range(1, 7)]
    for path in result:
        assert path.exists()


def test_concurrency_is_bounded_to_max_workers(tmp_path, monkeypatch):
    storyboard = _storyboard(10)
    concurrent_count = {"current": 0, "max_seen": 0}
    lock = threading.Lock()

    class _TrackedImages:
        def generate(self, **kwargs):
            with lock:
                concurrent_count["current"] += 1
                concurrent_count["max_seen"] = max(concurrent_count["max_seen"], concurrent_count["current"])
            time.sleep(0.05)
            with lock:
                concurrent_count["current"] -= 1
            return SimpleNamespace(data=[SimpleNamespace(b64_json=_FAKE_B64)])

    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(_TrackedImages()))

    media._generate_scene_images(
        storyboard, tmp_path, width=64, height=64, size="1024x1536", aspect_ratio="9:16",
    )

    assert concurrent_count["max_seen"] <= media.MAX_CONCURRENT_IMAGE_GENERATIONS
    assert concurrent_count["max_seen"] > 1, "no concurrency was observed at all"


def test_a_failure_in_one_scene_propagates_and_does_not_hang(tmp_path, monkeypatch):
    storyboard = _storyboard(4)
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(_FailingImages()))

    with pytest.raises(RuntimeError, match="simulated image generation failure"):
        media._generate_scene_images(
            storyboard, tmp_path, width=64, height=64, size="1024x1536", aspect_ratio="9:16",
        )


def test_cancellation_before_batch_start_raises_immediately_without_any_calls(tmp_path, monkeypatch):
    storyboard = _storyboard(4)
    images_api = _VariableLatencyImages()
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    with pytest.raises(RenderCancelled):
        media._generate_scene_images(
            storyboard, tmp_path, width=64, height=64, size="1024x1536", aspect_ratio="9:16",
            cancellation_check=lambda: True,
        )

    assert images_api.calls == []
