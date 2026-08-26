import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

MAX_HISTORY = int(
    os.getenv(
        "MAX_HISTORY",
        "12"
    )
)

MAX_MESSAGE_LENGTH = int(
    os.getenv(
        "MAX_MESSAGE_LENGTH",
        "4000"
    )
)

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing"
    )
