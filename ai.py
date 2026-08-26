import os
from typing import Optional

import httpx


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
).strip()

PRIMARY_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:1.7b"
).strip()

FALLBACK_MODEL = os.getenv(
    "OLLAMA_FALLBACK_MODEL",
    "qwen3:4b"
).strip()

NUM_PREDICT = int(
    os.getenv("OLLAMA_NUM_PREDICT", "160")
)

TEMPERATURE = float(
    os.getenv("OLLAMA_TEMPERATURE", "0.4")
)


SYSTEM_PROMPT = """أنت مساعد عربي داخل Telegram.

القواعد:
- أجب على المستخدم مباشرة.
- استخدم العربية إذا كان سؤال المستخدم بالعربية.
- استخدم اللهجة المصرية بشكل طبيعي في الكلام العادي.
- لا تكتب أي تحليل أو reasoning.
- لا تكتب "Okay" أو "Let me check".
- لا تشرح طريقة تفكيرك.
- لا تكرر سؤال المستخدم.
- أعطِ الإجابة النهائية فقط.
- في الأسئلة البسيطة اجعل الرد قصيراً ومباشراً.
""".strip()


async def _ollama_chat(
    model: str,
    messages: list,
    timeout: float = 75.0,
) -> str:

    clean_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Only keep useful recent history
    for msg in messages[-4:]:

        if not isinstance(msg, dict):
            continue

        role = msg.get("role")
        content = msg.get("content")

        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if not content:
            continue

        clean_messages.append({
            "role": role,
            "content": content,
        })

    payload = {
        "model": model,
        "messages": clean_messages,

        # Important for Qwen3
        "think": False,

        "stream": False,

        "options": {
            "temperature": TEMPERATURE,
            "num_predict": NUM_PREDICT,
            "top_p": 0.8,
        },

        "keep_alive": "15m",
    }

    timeout_config = httpx.Timeout(
        connect=5.0,
        read=timeout,
        write=10.0,
        pool=5.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout_config
    ) as client:

        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        message = data.get("message") or {}

        content = message.get("content", "")

        if not isinstance(content, str):
            content = str(content)

        content = content.strip()

        if not content:
            raise RuntimeError(
                f"Empty response from {model}"
            )

        return content


async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    prompt = str(prompt).strip()

    messages = []

    if history:

        for msg in history[-4:]:

            if not isinstance(msg, dict):
                continue

            role = msg.get("role")
            content = msg.get("content")

            if role in ("user", "assistant") and isinstance(content, str):

                messages.append({
                    "role": role,
                    "content": content,
                })

    # Prevent duplicated current message
    if not messages or messages[-1].get("content") != prompt:

        messages.append({
            "role": "user",
            "content": prompt,
        })

    # Primary FAST model
    try:

        return await _ollama_chat(
            PRIMARY_MODEL,
            messages,
        )

    except Exception as primary_error:

        print(
            "Primary model error:",
            repr(primary_error),
            flush=True,
        )

    # Fallback
    try:

        return await _ollama_chat(
            FALLBACK_MODEL,
            messages,
        )

    except Exception as fallback_error:

        print(
            "Fallback model error:",
            repr(fallback_error),
            flush=True,
        )

        return (
            "❌ الـ AI مش قادر يرد دلوقتي، "
            "جرب تاني بعد شوية."
        )


async def generate_response(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(prompt, history)


async def chat(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(prompt, history)


def get_model_info():

    return {
        "provider": "ollama",
        "url": OLLAMA_URL,
        "model": PRIMARY_MODEL,
        "fallback": FALLBACK_MODEL,
    }
