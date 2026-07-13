from __future__ import annotations

import subprocess
import sys
import time

import pytest

from app.services.cancellation import RenderCancelled
from app.services.subprocess_utils import run_cancellable

# A long-running but fully controllable "subprocess" standing in for
# ffmpeg -- this is what the production render pipeline used to run via a
# bare ``subprocess.run(command, capture_output=True, text=True)`` with no
# timeout and no way to interrupt it once cancellation was requested.
_SLEEP_10S = [sys.executable, "-c", "import time; time.sleep(10)"]
_QUICK_ECHO = [sys.executable, "-c", "print('done')"]
_FAILING = [sys.executable, "-c", "import sys; sys.exit(3)"]


def _cancel_after(calls: int):
    state = {"count": 0}

    def check() -> bool:
        state["count"] += 1
        return state["count"] > calls

    return check


def test_run_cancellable_matches_subprocess_run_when_no_cancellation_check():
    completed = run_cancellable(_QUICK_ECHO)
    assert completed.returncode == 0
    assert "done" in completed.stdout


def test_run_cancellable_propagates_nonzero_exit_code_unchanged():
    completed = run_cancellable(_FAILING, cancellation_check=lambda: False)
    assert completed.returncode == 3


def test_run_cancellable_terminates_a_hanging_process_promptly():
    # Without the fix, this would block for the full 10 seconds (or forever,
    # for a genuinely hung ffmpeg) no matter what cancellation_check says --
    # exactly the bug that starved the queue's single worker thread.
    start = time.monotonic()
    with pytest.raises(RenderCancelled):
        run_cancellable(_SLEEP_10S, cancellation_check=_cancel_after(2), poll_interval=0.05)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"cancellation took {elapsed:.2f}s -- process was not interrupted promptly"


def test_run_cancellable_leaves_no_zombie_process_behind():
    process_holder: dict[str, subprocess.Popen] = {}
    real_popen = subprocess.Popen

    def spying_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        process_holder["process"] = process
        return process

    import app.services.subprocess_utils as subprocess_utils

    original = subprocess_utils.subprocess.Popen
    subprocess_utils.subprocess.Popen = spying_popen
    try:
        with pytest.raises(RenderCancelled):
            run_cancellable(_SLEEP_10S, cancellation_check=_cancel_after(1), poll_interval=0.05)
    finally:
        subprocess_utils.subprocess.Popen = original

    process = process_holder["process"]
    # Give the OS a brief moment to reap the terminated child, then assert
    # it is no longer running.
    deadline = time.monotonic() + 2.0
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert process.poll() is not None, "child process was left running (zombie/orphan)"


def test_cancellation_before_start_never_spawns_the_process():
    process_holder: dict[str, subprocess.Popen] = {}
    real_popen = subprocess.Popen

    def spying_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        process_holder["process"] = process
        return process

    import app.services.subprocess_utils as subprocess_utils

    original = subprocess_utils.subprocess.Popen
    subprocess_utils.subprocess.Popen = spying_popen
    try:
        with pytest.raises(RenderCancelled):
            run_cancellable(_SLEEP_10S, cancellation_check=lambda: True)
    finally:
        subprocess_utils.subprocess.Popen = original

    assert "process" not in process_holder
