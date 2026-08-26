import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

MAX_HISTORY = int(
    os.getenv("MAX_HISTORY", "12")
)

MAX_MESSAGE_LENGTH = int(
    os.getenv("MAX_MESSAGE_LENGTH", "4000")
)

LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080"
).strip()

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B-Q4_K_M.gguf"
).strip()

LLAMA_MAX_TOKENS = int(
    os.getenv("LLAMA_MAX_TOKENS", "384")
)

LLAMA_TEMPERATURE = float(
    os.getenv("LLAMA_TEMPERATURE", "0.3")
)

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing"
    )
