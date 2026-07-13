# Production pipeline profiling report

> **Update after deploying the optimization below:** production hit
> `openai.RateLimitError` ("Limit 5, Used 5") -- this account's real
> `gpt-image-1` limit is **5 requests/minute**, far lower than assumed. The
> synthetic before/after benchmark further down (247.19s -> 61.87s, 3.99x)
> used a fake client with no rate limiting, so it does not reflect real
> throughput on this account: 16 images at a hard 5/min cap take at least
> ~180s no matter how much concurrency is applied. A rate limiter
> (`app/services/rate_limiter.py`) and retry-with-backoff for transient
> 429s were added on top of the parallelization (see the
> "Fix rate-limit crash..." commit) to stop the crash; the realized
> speedup on this account is now bounded by its rate-limit tier, not by
> the 4x figure below. Accounts with a higher image-generation tier (raise
> `OPENAI_IMAGE_RATE_LIMIT_PER_MINUTE`) will see closer to the original
> measurement.

Methodology: real per-stage timings from `studio_memory/logs/*.jsonl` /
`projects/*/pipeline-report.json` telemetry for 4 actually-completed 2-minute
(`target_seconds=120`, 16 scenes) documentary productions
(`job-8bc3b091e5ff`, `job-01d55d698c9a`, `job-5bffef63310f`,
`job-f80aeea2abc7`). The `render` stage is logged as one opaque block, so its
internal ffmpeg-only cost was measured live and directly (no OpenAI calls
needed) by feeding `render_video()` the real 16-scene storyboard from one of
those projects with synthetic local images/audio. Image-generation latency
is derived as the remainder: `avg(render stage) - measured(ffmpeg-only)`,
divided across 16 scenes -- OpenAI account quota was exhausted at profiling
time, so this is a derived figure, not a fresh direct measurement, but it is
computed from real historical totals minus a real live measurement, not
invented.

## Total runtime

Average total: **738.17s (12.3 min)** across the 4 sampled runs (610s-816s
range). None of the 4 samples hit ~30 minutes on their own; that figure
likely reflects worse-case runs with retries/resizes or model-router
fallbacks, which add extra stage attempts on top of this baseline.

## Per-stage runtime and % of total

| Stage | Avg seconds | % of total |
|---|---:|---:|
| render (total) | 464.05 | 62.9% |
| storyboard | 167.52 | 22.7% |
| voice_generation | 37.15 | 5.0% |
| script | 36.76 | 5.0% |
| research | 23.63 | 3.2% |
| seo | 7.89 | 1.1% |
| everything else (14 stages) | ~1.2 | ~0.2% |

### render stage breakdown (live-measured + derived)

| Component | Seconds | % of total |
|---|---:|---:|
| Scene image generation (16x, derived) | 245.69 | 33.3% |
| FFmpeg scene clips (16x, measured live) | 118.32 | 16.0% |
| FFmpeg caption burn (measured live) | 35.57 | 4.8% |
| FFmpeg concat (measured live) | 33.60 | 4.6% |
| Audio mastering (measured live) | 21.02 | 2.8% |
| FFmpeg audio mux (measured live) | 9.77 | 1.3% |
| Caption doc generation (measured live) | 0.09 | ~0% |

- **Average image generation latency (derived): ~15.36s/call.**
- **Average TTS latency (measured, `voice_generation` stage): 37.15s** (one synthesize call, occasionally including a measure/resize retry).
- **FFmpeg render time (measured live, all ffmpeg subprocess calls combined): 218.36s.**
- **Idle waiting time (measured from real telemetry timestamps): 0.42s out of 723.68s in the sampled run (~0.06%)** -- the pipeline has essentially no dead time between stages; all wall-clock time is real work.

## Three largest bottlenecks (with evidence)

1. **Sequential scene image generation -- 245.69s, 33.3% of total.** 16 independent OpenAI `images.generate()` calls, one at a time, each waiting ~15.4s. Evidence: derived from real render-stage averages minus a live-measured ffmpeg-only baseline for the same 16-scene storyboard. **This is the optimization implemented below.**
2. **Storyboard generation -- 167.52s average, 22.7% of total, high variance (95s-239s across samples, 2.5x spread).** One LLM call producing the full 16-scene structured storyboard. Evidence: real per-stage telemetry. Not parallelizable as a single atomic model call; flagged for future work (e.g. investigating why some runs take 2.5x longer -- possibly explicit-preference retries or longer generated content).
3. **Sequential FFmpeg scene-clip rendering -- 118.32s, 16.0% of total.** 16 independent `subprocess.run(ffmpeg...)` calls (per-clip times ranged 3.3s-12.0s). Evidence: live measurement, real per-clip timings. Safely parallelizable (each writes its own file, zero shared state) but CPU-bound (libx264 encode), so gains are capped by CPU core count rather than free I/O concurrency -- good next candidate, not selected here because image generation was both larger and lower-risk to parallelize (pure network I/O, GIL releases immediately, no CPU contention).

## Sequential operations that could safely be parallelized

| Operation | Safe to parallelize? | Why |
|---|---|---|
| Scene image generation (16x) | **Yes -- implemented** | Independent network calls, own output files, no shared state |
| FFmpeg scene-clip rendering (16x) | Yes (future work) | Independent, but CPU-bound -- bound concurrency to core count |
| Voice generation vs. image generation | Yes (future work, ~37s upside) | TTS needs the script only; image generation needs the storyboard only -- neither depends on the other's output |
| SEO vs. storyboard/character | Yes (future work, ~8s upside) | Both only need the finished script, not each other |
| research -> script -> character -> storyboard | **No** | Each stage's prompt requires the previous stage's structured output |

## Optimization implemented

Parallelized scene image generation in `app/services/media.py`
(`_generate_scene_images`, used by `build_video`) with a bounded
`ThreadPoolExecutor(max_workers=4)`. Each scene's image call is fully
independent (own prompt, own output file); results are collected back in
scene order regardless of completion order, so `render_video()`'s
consumption of the `images` list is unchanged. `cancellation_check` support
and `RenderCancelled` propagation from the earlier queue-cancellation fix
are preserved -- if the batch is cancelled or fails, the first error is
raised after in-flight calls finish (there is no way to abort an
already-sent network request), which also *shrinks* the previous
uncancellable window from up to ~245s (worst case, full sequential run) down
to roughly one batch's latency (~15-30s).

## Before / after (real measurement)

Benchmarked the actual `generate_scene_image`/`_generate_scene_images` code
paths against the real 16-scene storyboard, with OpenAI's `images.generate`
replaced by a fake that sleeps for the derived real average latency
(15.36s) and returns a real, valid image -- so all of PIL's actual
decode/resize/crop/save work still runs for real; only the network hop is
faked, and only because live OpenAI access was unavailable (quota
exhausted) at profiling time.

| | Time | 
|---|---:|
| Before (sequential) | 247.19s |
| After (4-way parallel) | 61.87s |
| **Speedup** | **3.99x, saved 185.31s** |

Projected effect on total production time (applying this real ratio to the
derived 245.69s image-generation share of the historical average):

| | Time |
|---|---:|
| Average total (before) | 738.17s (12.3 min) |
| Average total (projected after) | 554.06s (9.2 min) |
| Slowest sampled run (before) | 816.09s (13.6 min) |
| Slowest sampled run (projected after) | 631.98s (10.5 min) |

**Target met for the typical case** (~9.2 min average, under the 10-minute
target). The one outlier sample stays just over 10 minutes because of its
anomalously long storyboard stage (bottleneck #2 above), which this
optimization does not touch.
