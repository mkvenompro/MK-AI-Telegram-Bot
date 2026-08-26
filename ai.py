import os
from typing import Optional

import httpx


# ============================================================
# OLLAMA CONFIG
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
).strip().rstrip("/")

PRIMARY_MODEL = os.getenv(
    "OLLAMA_MODEL",
    os.getenv("AI_MODEL", "qwen3:4b"),
).strip()

FALLBACK_MODEL = os.getenv(
    "OLLAMA_FALLBACK_MODEL",
    os.getenv("AI_FALLBACK_MODEL", "qwen3:1.7b"),
).strip()

THINKING = os.getenv(
    "AI_THINKING",
    "true",
).strip().lower() in ("1", "true", "yes", "on")

NUM_PREDICT = int(
    os.getenv(
        "OLLAMA_NUM_PREDICT",
        os.getenv("AI_MAX_TOKENS", "512"),
    )
)

TEMPERATURE = float(
    os.getenv(
        "OLLAMA_TEMPERATURE",
        os.getenv("AI_TEMPERATURE", "0.6"),
    )
)

TOP_P = float(
    os.getenv("OLLAMA_TOP_P", "0.95")
)

TOP_K = int(
    os.getenv("OLLAMA_TOP_K", "20")
)

KEEP_ALIVE = os.getenv(
    "OLLAMA_KEEP_ALIVE",
    "15m",
).strip()


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
أنت Spider AI Assistant داخل Telegram.

قواعد مهمة:

- افهم كلام المستخدم قبل الرد.
- أجب مباشرة على السؤال.
- إذا كان المستخدم يتحدث بالعربية، استخدم العربية.
- في الكلام العادي استخدم اللهجة المصرية بشكل طبيعي.
- لا تكرر رسالة المستخدم.
- لا تقل "أنا شارب ايه يا أبو صلاح" عندما يسأل المستخدم "انت شارب ايه".
- لا تعيد صياغة السؤال بدل الإجابة عليه.
- لا تبدأ الرد بـ Okay أو Let me check أو ما شابه.
- لا تعرض عملية التفكير الداخلية أو reasoning للمستخدم.
- استخدم التفكير الداخلي للوصول لإجابة أفضل عندما يكون ذلك مفيداً.
- بعد التفكير أعطِ النتيجة النهائية فقط.
- الأسئلة البسيطة: رد قصير وطبيعي.
- الأسئلة التقنية: قدم حلاً واضحاً ومباشراً.
- لا تخترع معلومات غير مؤكدة.
- تعامل مع المستخدم باحترام حتى لو كان أسلوبه هزاراً أو عامياً.
""".strip()


# ============================================================
# OLLAMA CHAT
# ============================================================

async def _ollama_chat(
    model: str,
    messages: list,
    timeout: float = 120.0,
) -> str:

    clean_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for msg in messages[-6:]:

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

        clean_messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    payload = {
        "model": model,
        "messages": clean_messages,

        # Qwen3 thinking
        "think": THINKING,

        "stream": False,

        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "num_predict": NUM_PREDICT,
        },

        "keep_alive": KEEP_ALIVE,
    }

    timeout_config = httpx.Timeout(
        connect=5.0,
        read=timeout,
        write=15.0,
        pool=10.0,
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

    # IMPORTANT:
    # Ollama may return:
    # message.thinking
    # message.content
    #
    # We NEVER expose message.thinking to Telegram.

    content = message.get("content", "")

    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    if not content:
        raise RuntimeError(
            f"Empty final response from {model}"
        )

    return content


# ============================================================
# PUBLIC AI FUNCTION
# ============================================================

async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    prompt = str(prompt).strip()

    if not prompt:
        return "قولّي سؤالك وأنا معاك 😄"

    messages = []

    if history:

        for msg in history[-6:]:

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
        or messages[-1].get("role") != "user"
        or messages[-1].get("content") != prompt
    ):
        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

    # ========================================================
    # PRIMARY
    # ========================================================

    try:

        return await _ollama_chat(
            PRIMARY_MODEL,
            messages,
        )

    except Exception as primary_error:

        print(
            f"[AI] Primary model error ({PRIMARY_MODEL}): "
            f"{primary_error!r}",
            flush=True,
        )

    # ========================================================
    # FALLBACK
    # ========================================================

    if FALLBACK_MODEL and FALLBACK_MODEL != PRIMARY_MODEL:

        try:

            return await _ollama_chat(
                FALLBACK_MODEL,
                messages,
            )

        except Exception as fallback_error:

            print(
                f"[AI] Fallback model error ({FALLBACK_MODEL}): "
                f"{fallback_error!r}",
                flush=True,
            )

    return (
        "❌ الـ AI مش قادر يرد دلوقتي، "
        "جرب تاني بعد شوية."
    )


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================

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
        "thinking": THINKING,
        "num_predict": NUM_PREDICT,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
    }
