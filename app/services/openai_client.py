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
):
    """Request schema-validated structured output.

    ``model`` and ``client`` default to the original global behavior
    (``OPENAI_TEXT_MODEL`` / ``get_openai_client()``) so every pre-existing
    caller is unaffected. ``app.model_router.execution`` passes both
    explicitly to run a stage against a specific routed model (and, for the
    Creative Director, a dedicated client instance).
    """

    resolved_client = client or get_openai_client()
    response = resolved_client.responses.parse(
        model=model or OPENAI_TEXT_MODEL,
        instructions=instructions,
        input=prompt,
        text_format=schema,
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
