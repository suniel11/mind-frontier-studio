import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5-mini").strip()
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx").strip()


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default


# Longer structured outputs such as a two-minute storyboard can legitimately
# take more than the OpenAI SDK's short interactive-request timeout. Keep this
# configurable for slower connections while retaining a finite upper bound.
OPENAI_TIMEOUT_SECONDS = _bounded_float(
    "OPENAI_TIMEOUT_SECONDS",
    120.0,
    15.0,
    600.0,
)


PORT = _bounded_int("PORT", 8000, 1, 65535)

MUSIC_ENABLED = os.getenv("MUSIC_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
MUSIC_VOLUME = _bounded_float("MUSIC_VOLUME", 0.16, 0.0, 1.0)
MUSIC_TRACK = os.getenv("MUSIC_TRACK", "").strip()
