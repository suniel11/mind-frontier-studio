from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable


class SlidingWindowRateLimiter:
    """Thread-safe "at most N calls per rolling `period_seconds`" limiter.

    Used to keep concurrent scene-image generation from bursting past an
    OpenAI account's actual per-minute image rate limit -- parallelizing
    those calls (see app.services.media._generate_scene_images) only
    changes *when* requests are dispatched, not how many the account
    allows per minute, so without this a burst of concurrent requests
    fails with ``openai.RateLimitError`` (429 rate_limit_exceeded) instead
    of the whole batch simply taking as long as the account's rate tier
    requires.

    ``acquire()`` blocks the calling thread until a slot is free rather
    than raising, so callers behind a ``ThreadPoolExecutor`` naturally
    queue up instead of erroring.
    """

    def __init__(self, max_calls: int, period_seconds: float = 60.0):
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1.")
        self._max_calls = max_calls
        self._period_seconds = period_seconds
        self._lock = threading.Lock()
        self._call_times: deque[float] = deque()

    def acquire(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        while True:
            with self._lock:
                now = clock()
                while self._call_times and now - self._call_times[0] >= self._period_seconds:
                    self._call_times.popleft()
                if len(self._call_times) < self._max_calls:
                    self._call_times.append(now)
                    return
                wait_for = self._period_seconds - (now - self._call_times[0])
            sleep(max(0.01, wait_for))
