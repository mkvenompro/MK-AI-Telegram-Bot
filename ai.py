import os
from typing import Optional

import httpx


# ============================================================
# LLAMA.CPP CONFIG
# ============================================================

LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080"
).strip().rstrip("/")

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B-Q4_K_M.gguf"
).strip()

MAX_TOKENS = int(
    os.getenv(
        "AI_MAX_TOKENS",
        "768"
    )
)

TEMPERATURE = float(
    os.getenv(
        "AI_TEMPERATURE",
        "0.4"
    )
)

TOP_P = float(
    os.getenv(
        "AI_TOP_P",
        "0.8"
    )
)

TIMEOUT = float(
    os.getenv(
        "AI_TIMEOUT",
        "120"
    )
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
أنت Spider AI Assistant داخل Telegram.

القواعد المهمة:

- أجب مباشرة على سؤال المستخدم.
- إذا كان المستخدم يتكلم بالعربية، استخدم العربية.
- في الكلام العادي استخدم اللهجة المصرية بشكل طبيعي.
- كن محترماً حتى لو المستخدم بيتكلم بعصبية أو هزار.
- لا تكرر كلام المستخدم بدون سبب.
- لا تبدأ الرد بكلمات مثل:
  Okay
  Sure
  Let me check
  I understand
- لا تعرض reasoning أو التفكير الداخلي للمستخدم.
- فكّر داخلياً قبل الإجابة عندما يكون السؤال يحتاج تحليلاً.
- بعد التفكير أعطِ النتيجة النهائية فقط.
- الأسئلة البسيطة يكون ردها قصيراً.
- لا تتفلسف في الأسئلة البسيطة.
- لا تخترع معلومات.
- إذا لم تكن متأكداً، قل إنك غير متأكد.
""".strip()


# ============================================================
# EXTRACT FINAL ANSWER
# ============================================================

def extract_final_content(message: dict) -> str:
    """
    llama.cpp with reasoning-format=deepseek normally returns:

    {
        "content": "...",
        "reasoning_content": "..."
    }

    We ONLY return content.

    Also handles models/configurations that put
    <think>...</think> directly inside content.
    """

    content = message.get("content")

    if content is None:
        content = ""

    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    # Handle raw <think> blocks just in case
    if "<think>" in content and "</think>" in content:
        after = content.split("</think>", 1)[1]
        content = after.strip()

    # Remove an unfinished thinking prefix
    if content.startswith("<think>"):
        content = content.replace("<think>", "", 1).strip()

    return content


# ============================================================
# LLAMA.CPP REQUEST
# ============================================================

async def _llama_chat(
    messages: list,
    timeout: float = TIMEOUT,
) -> str:

    clean_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for msg in messages[-8:]:

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

        # Never send internal reasoning back into history
        if role == "assistant":

            if "<think>" in content:
                if "</think>" in content:
                    content = content.split(
                        "</think>",
                        1
                    )[1].strip()
                else:
                    continue

        clean_messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    payload = {
        "model": LLAMA_MODEL,
        "messages": clean_messages,

        # llama.cpp OpenAI-compatible endpoint
        "stream": False,

        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
    }

    timeout_config = httpx.Timeout(
        connect=5.0,
        read=timeout,
        write=10.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout_config
    ) as client:

        response = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        choices = data.get("choices") or []

        if not choices:
            raise RuntimeError(
                f"llama.cpp returned no choices: {data}"
            )

        message = choices[0].get("message") or {}

        answer = extract_final_content(message)

        if not answer:

            reasoning = message.get(
                "reasoning_content",
                ""
            )

            raise RuntimeError(
                "llama.cpp returned reasoning but no "
                "final answer. Increase AI_MAX_TOKENS. "
                f"reasoning_chars={len(str(reasoning))}"
            )

        return answer


# ============================================================
# PUBLIC AI FUNCTION
# ============================================================

async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    prompt = str(prompt).strip()

    if not prompt:
        return "اكتبلي سؤالك الأول 😄"

    messages = []

    if history:

        for msg in history[-8:]:

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

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    # Prevent duplicate current message
    if (
        not messages
        or messages[-1].get("content") != prompt
    ):
        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

    try:

        return await _llama_chat(
            messages
        )

    except Exception as error:

        print(
            "llama.cpp error:",
            repr(error),
            flush=True,
        )

        return (
            "❌ حصل خطأ في الـAI دلوقتي، "
            "جرب تاني بعد شوية."
        )


async def generate_response(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(
        prompt,
        history
    )


async def chat(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await ask_ai(
        prompt,
        history
    )


def get_model_info():

    return {
        "provider": "llama.cpp",
        "url": LLAMA_URL,
        "model": LLAMA_MODEL,
        "thinking": True,
    }
