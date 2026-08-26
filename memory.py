import json
import os
import threading

MEMORY_FILE = os.path.expanduser(
    "~/MK-AI-Telegram-Bot/memory.json"
)

_lock = threading.Lock()

MAX_STORED = 40


def _load():

    if not os.path.exists(MEMORY_FILE):
        return {}

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except Exception:
        return {}


def _save(data):

    tmp = MEMORY_FILE + ".tmp"

    with open(
        tmp,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        tmp,
        MEMORY_FILE,
    )


def get_history(
    chat_id,
    limit=12,
):

    key = str(chat_id)

    with _lock:

        data = _load()

        history = data.get(
            key,
            [],
        )

        if not isinstance(history, list):
            return []

        return history[-limit:]


def add_message(
    chat_id,
    role,
    content,
    limit=12,
):

    key = str(chat_id)

    with _lock:

        data = _load()

        history = data.get(
            key,
            [],
        )

        if not isinstance(history, list):
            history = []

        history.append({
            "role": role,
            "content": str(content),
        })

        data[key] = history[-MAX_STORED:]

        _save(data)


def clear_history(chat_id):

    key = str(chat_id)

    with _lock:

        data = _load()

        data.pop(
            key,
            None,
        )

        _save(data)
