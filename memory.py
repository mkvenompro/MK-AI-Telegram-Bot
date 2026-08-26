import json
import os
from threading import Lock

MEMORY_FILE = "data/memory.json"
_lock = Lock()

def _load():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(MEMORY_FILE):
        return {}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data):
    os.makedirs("data", exist_ok=True)
    temp = MEMORY_FILE + ".tmp"

    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(temp, MEMORY_FILE)

def get_history(chat_id, max_messages=12):
    with _lock:
        data = _load()
        return data.get(str(chat_id), [])[-max_messages:]

def add_message(chat_id, role, content, max_messages=12):
    with _lock:
        data = _load()
        key = str(chat_id)

        if key not in data:
            data[key] = []

        data[key].append({"role": role, "content": content})
        data[key] = data[key][-max_messages:]

        _save(data)

def clear_history(chat_id):
    with _lock:
        data = _load()
        data.pop(str(chat_id), None)
        _save(data)