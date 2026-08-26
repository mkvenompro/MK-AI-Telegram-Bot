import json
import os
from typing import Optional

import httpx


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

PRIMARY_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:8b"
)

FALLBACK_MODEL = os.getenv(
    "OLLAMA_FALLBACK_MODEL",
    "qwen3:4b"
)


async def _ollama_chat(
    model: str,
    messages: list,
    timeout: float = 180.0,
) -> str:

    payload = {
        "model": model,
        "messages": messages,
        "think": False,
        "stream": False,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout)
    ) as client:

        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    message = data.get("message", {})
    content = message.get("content", "")

    if not isinstance(content, str):
        return str(content)

    return content.strip()


async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    messages = []

    if history:
        messages.extend(history)

    messages.append({
        "role": "user",
        "content": prompt,
    })

    # Primary model
    try:
        return await _ollama_chat(
            PRIMARY_MODEL,
            messages,
        )

    except Exception as primary_error:

        # Fallback model
        try:
            return await _ollama_chat(
                FALLBACK_MODEL,
                messages,
            )

        except Exception as fallback_error:

            print(
                "Ollama primary error:",
                repr(primary_error),
            )

            print(
                "Ollama fallback error:",
                repr(fallback_error),
            )

            return (
                "❌ حصل خطأ وأنا بحاول أتواصل مع الـ AI.\n"
                "جرب تاني بعد شوية."
            )


async def generate_response(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(
        prompt,
        history,
    )


async def chat(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(
        prompt,
        history,
    )


def get_model_info() -> dict:

    return {
        "provider": "ollama",
        "url": OLLAMA_URL,
        "model": PRIMARY_MODEL,
        "fallback": FALLBACK_MODEL,
    }
