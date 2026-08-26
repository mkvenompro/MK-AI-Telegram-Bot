import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

AI_API_URL = os.getenv("AI_API_URL", "https://openrouter.ai/api/v1/chat/completions").strip()

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()

AI_MODEL = os.getenv("AI_MODEL", "qwen/qwen3-30b-a3b:free").strip()

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))

MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY is missing")