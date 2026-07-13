from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_TEXT_MODEL,
    OPENAI_TIMEOUT_SECONDS,
)

client = (
    OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=2,
    )
    if OPENAI_API_KEY
    else None
)


def get_openai_client() -> OpenAI:
    if client is None:
        raise RuntimeError("OpenAI API is not configured.")
    return client


def structured_response(
    *,
    instructions: str,
    prompt: str,
    schema,
    model: str | None = None,
    client=None,
    return_usage: bool = False,
    temperature: float | None = None,
):
    """Request schema-validated structured output.

    ``model`` and ``client`` default to the original global behavior
    (``OPENAI_TEXT_MODEL`` / ``get_openai_client()``) so every pre-existing
    caller is unaffected. ``app.model_router.execution`` passes both
    explicitly to run a stage against a specific routed model (and, for the
    Creative Director, a dedicated client instance).

    ``temperature`` is omitted from the request entirely unless explicitly
    given (``None`` -> today's exact behavior for every existing caller).
    Only pass it for models actually known to accept it -- OpenAI's
    reasoning-model families (gpt-5*, o1*, o3*, o4*) reject it outright
    with a 400 error on the Responses API (verified directly against
    gpt-5-mini), so callers must check model capability first (see
    app.visual_continuity.planner._model_supports_sampling_controls).
    """

    resolved_client = client or get_openai_client()
    optional_kwargs = {}
    if temperature is not None:
        optional_kwargs["temperature"] = temperature
    response = resolved_client.responses.parse(
        model=model or OPENAI_TEXT_MODEL,
        instructions=instructions,
        input=prompt,
        text_format=schema,
        **optional_kwargs,
    )
    if response.output_parsed is None:
        raise RuntimeError("The model returned no structured output.")
    if return_usage:
        return response.output_parsed, _extract_usage(response)
    return response.output_parsed


def _extract_usage(response) -> dict:
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return {}
    details = getattr(usage_obj, "input_tokens_details", None)
    return {
        "input_tokens": getattr(usage_obj, "input_tokens", None),
        "output_tokens": getattr(usage_obj, "output_tokens", None),
        "cached_tokens": getattr(details, "cached_tokens", None) if details else None,
    }
