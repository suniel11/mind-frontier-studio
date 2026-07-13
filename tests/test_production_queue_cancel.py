from __future__ import annotations

import threading
import time

from app.production.jobs import ProductionJobRunner
from app.production.specification import ProductionSpecification


def _spec(prompt: str, seconds: int = 45) -> ProductionSpecification:
    return ProductionSpecification(original_prompt=prompt, target_seconds=seconds)


def _make_polling_pipeline(*, render_seconds: float, poll_interval: float = 0.02, started_event=None):
    """Stands in for ``create_project_pipeline``. Only jobs whose topic
    contains "long-render" simulate a long "render" stage; every other job
    completes immediately. This mirrors the real scenario: job A is the one
    caught mid-render when cancelled, job B is a normal, fast job started
    right after -- like the fixed ``app.services.media`` render loop, which
    now polls ``cancellation_check`` between every scene clip/subprocess
    instead of only at top-level pipeline stage boundaries, the simulated
    render checks cancellation frequently and bails out the moment it is
    requested, instead of blocking until the simulated work finishes
    naturally."""

    def pipeline(request, *, project_id, progress_callback=None, cancellation_check=None):
        if "long-render" not in request.topic.casefold():
            return {"video_url": f"/projects/{project_id}/mind-frontier-short.mp4"}

        if progress_callback:
            progress_callback("render", "started")
        if started_event is not None:
            started_event.set()
        deadline = time.monotonic() + render_seconds
        while time.monotonic() < deadline:
            if cancellation_check and cancellation_check():
                # Any exception works here -- ProductionJobRunner._worker
                # routes an exception to "cancelled" by checking its own
                # cancellation_check() first, not by the exception's type.
                raise RuntimeError("render interrupted by cancellation")
            time.sleep(poll_interval)
        if progress_callback:
            progress_callback("render", "complete")
        return {"video_url": f"/projects/{project_id}/mind-frontier-short.mp4"}

    return pipeline


def _wait_for_status(runner: ProductionJobRunner, job_id: str, terminal_statuses: set[str], timeout: float):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = runner.get(job_id)
        if last.status in terminal_statuses:
            return last
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {terminal_statuses} in time (last status: {last})")


def test_cancel_midrender_frees_worker_and_starts_next_job_automatically(tmp_path):
    """The exact lifecycle from the bug report:

    Start Job A -> Cancel -> Job A becomes cancelled -> Worker becomes idle
    -> Job B starts automatically -> Queue empties normally.
    """

    job_a_started = threading.Event()
    # 10 simulated "render seconds" -- if cancellation only updated a status
    # flag without ever interrupting the in-flight work (the original bug),
    # job A's worker would stay occupied for the full 10 seconds and job B
    # would remain queued the whole time.
    pipeline = _make_polling_pipeline(render_seconds=10.0, started_event=job_a_started)
    runner = ProductionJobRunner(tmp_path, pipeline=pipeline)
    try:
        created_a = runner.create(_spec("Job A - a long-render documentary about volcanoes"))
        assert job_a_started.wait(timeout=5), "job A never started rendering"
        time.sleep(0.1)  # ensure job A is genuinely mid-render, not just starting

        cancel_start = time.monotonic()
        cancel_result = runner.cancel(created_a.job_id)
        assert cancel_result.status in {"cancelling", "cancelled"}

        # Start job B *while job A is still cancelling* -- this is step 3 of
        # the reported bug ("start another production").
        created_b = runner.create(_spec("Job B - a short video about tides"))

        job_a = _wait_for_status(runner, created_a.job_id, {"cancelled"}, timeout=3.0)
        elapsed = time.monotonic() - cancel_start
        assert job_a.status == "cancelled"
        # The regression assertion: job A must reach a terminal state almost
        # immediately, not after the full 10-second render would have
        # finished on its own.
        assert elapsed < 3.0, f"job A took {elapsed:.2f}s to cancel -- worker was not released promptly"

        # Job B must start automatically (no manual resubmission) and run
        # to completion -- the queue is not stuck behind the cancelled job.
        job_b = _wait_for_status(runner, created_b.job_id, {"complete"}, timeout=5.0)
        assert job_b.status == "complete"
        assert job_b.output_links.get("video") == f"/projects/{created_b.project_id}/mind-frontier-short.mp4"

        # The queue empties normally: nothing left active or pending.
        with runner._lock:
            assert runner._active == set()
            assert runner._resubmit == set()
    finally:
        runner.shutdown()


def test_cancel_while_queued_never_runs_and_next_job_still_starts(tmp_path):
    """Cancelling a job that hasn't started yet (still 'queued' behind a
    running job) must not block the job after it either."""

    job_a_started = threading.Event()
    release_a = threading.Event()

    def pipeline(request, *, project_id, progress_callback=None, cancellation_check=None):
        if "job-a" in request.topic.casefold():
            job_a_started.set()
            release_a.wait(timeout=5)
            return {"video_url": f"/projects/{project_id}/mind-frontier-short.mp4"}
        return {"video_url": f"/projects/{project_id}/mind-frontier-short.mp4"}

    runner = ProductionJobRunner(tmp_path, pipeline=pipeline)
    try:
        created_a = runner.create(_spec("job-a is running"))
        assert job_a_started.wait(timeout=5)

        created_b = runner.create(_spec("job-b is queued behind job-a"))
        cancelled_b = runner.cancel(created_b.job_id)
        assert cancelled_b.status == "cancelled"

        release_a.set()
        job_a = _wait_for_status(runner, created_a.job_id, {"complete"}, timeout=5.0)
        assert job_a.status == "complete"

        job_b = runner.get(created_b.job_id)
        assert job_b.status == "cancelled"

        with runner._lock:
            assert runner._active == set()
            assert runner._resubmit == set()
    finally:
        runner.shutdown()


def test_existing_completed_jobs_continue_working_unaffected_by_cancellation_elsewhere(tmp_path):
    def pipeline(request, *, project_id, progress_callback=None, cancellation_check=None):
        return {"video_url": f"/projects/{project_id}/mind-frontier-short.mp4"}

    runner = ProductionJobRunner(tmp_path, pipeline=pipeline)
    try:
        created = runner.create(_spec("A normal, uncancelled production"))
        job = _wait_for_status(runner, created.job_id, {"complete"}, timeout=5.0)
        assert job.status == "complete"
        assert job.progress_percent == 100
    finally:
        runner.shutdown()
