import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080",
).strip()

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B-Q4_K_M.gguf",
).strip()

MAX_HISTORY = int(
    os.getenv(
        "MAX_HISTORY",
        "12",
    )
)

MAX_MESSAGE_LENGTH = int(
    os.getenv(
        "MAX_MESSAGE_LENGTH",
        "4000",
    )
)

AGENT_MAX_STEPS = int(
    os.getenv(
        "AGENT_MAX_STEPS",
        "8",
    )
)

AGENT_TIMEOUT = float(
    os.getenv(
        "AGENT_TIMEOUT",
        "45",
    )
)

WEB_ENABLED = os.getenv(
    "WEB_ENABLED",
    "true",
).lower() == "true"

GITHUB_ENABLED = os.getenv(
    "GITHUB_ENABLED",
    "true",
).lower() == "true"

TERMINAL_ENABLED = os.getenv(
    "TERMINAL_ENABLED",
    "true",
).lower() == "true"

AUTO_INSTALL = os.getenv(
    "AUTO_INSTALL",
    "true",
).lower() == "true"

AUTO_GIT_PUSH = os.getenv(
    "AUTO_GIT_PUSH",
    "false",
).lower() == "true"

if not TELEGRAM_BOT_TOKEN:

    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing"
    )
