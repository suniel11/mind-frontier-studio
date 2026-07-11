import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5-mini").strip()
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx").strip()
PORT = int(os.getenv("PORT", "8000"))

MUSIC_ENABLED = os.getenv("MUSIC_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.16"))
MUSIC_TRACK = os.getenv("MUSIC_TRACK", "").strip()

if not OPENAI_API_KEY or "put_your" in OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing. Add it to the .env file.")
