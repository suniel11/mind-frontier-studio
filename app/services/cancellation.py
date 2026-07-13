from __future__ import annotations


class RenderCancelled(RuntimeError):
    """Raised when a production job's cancellation flag is observed while a
    subprocess or long-running render step is in flight.

    Distinct from a genuine ffmpeg/render failure so callers (and tests) can
    tell the two apart. ``app.production.jobs.ProductionJobRunner._worker``
    still routes this to "cancelled" rather than "failed" like any other
    exception raised once cancellation was requested -- it checks its own
    ``cancellation_check()`` first, before looking at the exception at all.
    """
