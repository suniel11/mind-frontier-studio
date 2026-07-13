from __future__ import annotations

import base64
import io
from types import SimpleNamespace

import httpx
import openai
import pytest
from PIL import Image

from app.services import media
from app.services.rate_limiter import SlidingWindowRateLimiter

_buffer = io.BytesIO()
Image.new("RGB", (32, 32), color=(80, 80, 80)).save(_buffer, format="PNG")
_FAKE_B64 = base64.b64encode(_buffer.getvalue()).decode("ascii")


def _fake_response(status_code: int = 429) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    return httpx.Response(status_code, request=request, json={"error": {"message": "boom"}})


def _rate_limit_error(message: str) -> openai.RateLimitError:
    return openai.RateLimitError(message, response=_fake_response(), body=None)


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ---------------------------------------------------------------------------
# SlidingWindowRateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_allows_up_to_max_calls_without_waiting():
    limiter = SlidingWindowRateLimiter(max_calls=5, period_seconds=60.0)
    clock = _FakeClock()
    sleeps: list[float] = []

    for _ in range(5):
        limiter.acquire(clock=clock, sleep=sleeps.append)

    assert sleeps == []


def test_rate_limiter_blocks_the_6th_call_until_the_window_frees_up():
    limiter = SlidingWindowRateLimiter(max_calls=5, period_seconds=60.0)
    clock = _FakeClock()
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    for _ in range(5):
        limiter.acquire(clock=clock, sleep=sleep)

    limiter.acquire(clock=clock, sleep=sleep)  # the 6th call must wait

    assert sleeps, "the 6th call should have had to wait for a free slot"
    assert sum(sleeps) >= 60.0 - 5 * 0.01  # waited out ~the full window


def test_rate_limiter_expires_old_calls_out_of_the_window():
    limiter = SlidingWindowRateLimiter(max_calls=2, period_seconds=60.0)
    clock = _FakeClock()
    sleeps: list[float] = []

    limiter.acquire(clock=clock, sleep=sleeps.append)
    limiter.acquire(clock=clock, sleep=sleeps.append)
    clock.advance(61.0)  # both calls are now outside the window
    limiter.acquire(clock=clock, sleep=sleeps.append)

    assert sleeps == [], "calls outside the window must not block new ones"


def test_rate_limiter_rejects_invalid_max_calls():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(max_calls=0)


# ---------------------------------------------------------------------------
# generate_scene_image / _generate_image retry-with-backoff
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _permissive_rate_limit(monkeypatch):
    monkeypatch.setattr(
        media, "_image_rate_limiter", SlidingWindowRateLimiter(max_calls=10_000, period_seconds=60.0)
    )
    yield


class _FlakyThenOkImages:
    def __init__(self, failures: list[Exception]):
        self._failures = list(failures)
        self.call_count = 0

    def generate(self, **kwargs):
        self.call_count += 1
        if self._failures:
            raise self._failures.pop(0)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=_FAKE_B64)])


class _FakeClient:
    def __init__(self, images):
        self.images = images


def test_transient_rate_limit_error_is_retried_and_recovers(monkeypatch):
    error = _rate_limit_error(
        "Rate limit reached for gpt-image-1 ... Please try again in 0s."
    )
    images_api = _FlakyThenOkImages([error, error])
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    sleeps: list[float] = []
    result = media._generate_image("a prompt", "1024x1536", "9:16", sleep=sleeps.append)

    assert result.data[0].b64_json == _FAKE_B64
    assert images_api.call_count == 3  # 2 failures + 1 success
    assert len(sleeps) == 2


def test_retry_honors_the_provider_supplied_wait_hint(monkeypatch):
    error = _rate_limit_error("Rate limit reached. Please try again in 12s.")
    images_api = _FlakyThenOkImages([error])
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    sleeps: list[float] = []
    media._generate_image("a prompt", "1024x1536", "9:16", sleep=sleeps.append)

    assert sleeps == [pytest.approx(12.5)]


def test_quota_exhaustion_is_never_retried(monkeypatch):
    error = _rate_limit_error(
        "You exceeded your current quota, please check your plan and billing details."
    )
    images_api = _FlakyThenOkImages([error])
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    with pytest.raises(openai.RateLimitError):
        media._generate_image("a prompt", "1024x1536", "9:16", sleep=lambda _s: None)

    assert images_api.call_count == 1  # no retry attempted


def test_rate_limit_retries_are_bounded_not_infinite(monkeypatch):
    error = _rate_limit_error("Rate limit reached. Please try again in 0s.")
    images_api = _FlakyThenOkImages([error] * 100)
    monkeypatch.setattr(media, "get_openai_client", lambda: _FakeClient(images_api))

    with pytest.raises(openai.RateLimitError):
        media._generate_image("a prompt", "1024x1536", "9:16", sleep=lambda _s: None)

    assert images_api.call_count == media.MAX_IMAGE_GENERATION_RETRIES + 1
