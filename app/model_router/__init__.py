"""Cost-aware OpenAI text-model routing with baseline-quality fallback.

This package centralizes every text-model selection decision for the
production pipeline. It never touches image generation or TTS models.

The current/original model configuration (``OPENAI_TEXT_MODEL`` /
``CREATIVE_DIRECTOR_MODEL``) is always available as ``baseline_model`` -- see
``app.model_router.config``. Lower-cost models are only ever an experiment
layered on top: every lower-cost output is validated with deterministic
checks (``app.model_router.quality_checks``) before it is allowed downstream,
and any failure reruns the stage on ``baseline_model`` automatically
(``app.model_router.execution.run_agent_stage``).
"""
