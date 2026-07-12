from __future__ import annotations

from enum import Enum

import openai


class ErrorCategory(str, Enum):
    SCHEMA_VALIDATION = "schema_validation"
    QUALITY = "quality"
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_MODEL = "unsupported_model"
    UNKNOWN = "unknown"


# Only these categories are worth retrying at all, and only with a bounded
# backoff (see app.model_router.execution) -- never blindly, and never for
# authentication/quota/invalid-request/unsupported-model, which cannot
# succeed by simply trying again (Phase 9).
RETRYABLE_CATEGORIES = frozenset({ErrorCategory.TRANSIENT, ErrorCategory.TIMEOUT})
NO_RETRY_CATEGORIES = frozenset(
    {
        ErrorCategory.AUTHENTICATION,
        ErrorCategory.QUOTA,
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.UNSUPPORTED_MODEL,
    }
)

_UNSUPPORTED_MODEL_HINTS = ("does not exist", "not found", "unsupported", "unknown model", "invalid model")


def classify_error(exc: Exception) -> ErrorCategory:
    if isinstance(exc, openai.AuthenticationError):
        return ErrorCategory.AUTHENTICATION
    if isinstance(exc, openai.APITimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(exc, openai.RateLimitError):
        message = str(exc).casefold()
        return ErrorCategory.QUOTA if "quota" in message else ErrorCategory.TRANSIENT
    if isinstance(exc, openai.NotFoundError):
        return ErrorCategory.UNSUPPORTED_MODEL
    if isinstance(exc, openai.BadRequestError):
        message = str(exc).casefold()
        if "model" in message and any(hint in message for hint in _UNSUPPORTED_MODEL_HINTS):
            return ErrorCategory.UNSUPPORTED_MODEL
        return ErrorCategory.INVALID_REQUEST
    if isinstance(exc, (openai.APIConnectionError, openai.InternalServerError)):
        return ErrorCategory.TRANSIENT
    if isinstance(exc, openai.APIStatusError):
        status_code = getattr(exc, "status_code", None)
        if status_code in (500, 502, 503, 504):
            return ErrorCategory.TRANSIENT
        if status_code == 429:
            return ErrorCategory.QUOTA
        return ErrorCategory.INVALID_REQUEST
    if isinstance(exc, (ValueError, RuntimeError)):
        # Our own "the model returned no structured output" / pydantic
        # validation failures raised by structured_response.
        return ErrorCategory.SCHEMA_VALIDATION
    return ErrorCategory.UNKNOWN
