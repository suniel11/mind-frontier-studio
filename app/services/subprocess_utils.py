from __future__ import annotations

import subprocess
from typing import Callable

from app.services.cancellation import RenderCancelled

_DEFAULT_POLL_INTERVAL = 0.2
_TERMINATE_GRACE_SECONDS = 3.0


def run_cancellable(
    command: list[str],
    *,
    cancellation_check: Callable[[], bool] | None = None,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
) -> subprocess.CompletedProcess:
    """Run ``command`` to completion, equivalent to
    ``subprocess.run(command, capture_output=True, text=True)``.

    When ``cancellation_check`` is given, it is polled while the child
    process runs; the moment it reports cancellation, the child is
    terminated (then killed, if it doesn't exit within the grace period)
    instead of being left to block the caller until it exits on its own.
    This is what lets a cancelled production job's worker thread actually
    return promptly instead of staying occupied by an ffmpeg subprocess for
    the rest of its natural run time (or forever, if it hangs) -- see the
    production-queue-stall investigation this was added for.

    Raises ``RenderCancelled`` if the process was terminated for that
    reason. Never leaves the child running: on the cancellation path it is
    always waited on after being signalled; on the normal path
    ``subprocess.run``'s own semantics apply unchanged.
    """

    if cancellation_check is None:
        return subprocess.run(command, capture_output=True, text=True)

    if cancellation_check():
        raise RenderCancelled("Rendering cancelled before subprocess start.")

    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=poll_interval)
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                # Safe to retry communicate() after a timeout -- no output is
                # lost (see the subprocess module documentation).
                if not cancellation_check():
                    continue
                process.terminate()
                try:
                    process.communicate(timeout=_TERMINATE_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise RenderCancelled("Rendering cancelled during subprocess execution.")
    finally:
        if process.poll() is None:
            # Defensive only -- every path above already waits on the child
            # after signalling it. Never return with it still alive.
            process.kill()
            process.communicate()
