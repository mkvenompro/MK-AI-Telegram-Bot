import os
import re
import json
import httpx
from typing import Optional


LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080"
).strip()

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B-Q4_K_M.gguf"
).strip()

MAX_TOKENS = int(
    os.getenv("LLAMA_MAX_TOKENS", "512")
)

TEMPERATURE = float(
    os.getenv("LLAMA_TEMPERATURE", "0.3")
)

THINKING = os.getenv(
    "LLAMA_THINKING",
    "true"
).lower() in ("1", "true", "yes", "on")

WEB_ENABLED = os.getenv(
    "WEB_SEARCH_ENABLED",
    "true"
).lower() in ("1", "true", "yes", "on")

GITHUB_ENABLED = os.getenv(
    "GITHUB_SEARCH_ENABLED",
    "true"
).lower() in ("1", "true", "yes", "on")


SYSTEM_PROMPT = """
أنت Spider AI Assistant داخل Telegram.

أنت مساعد عربي ذكي.

القواعد:

- رد بالمصري بشكل طبيعي عندما المستخدم يتكلم بالمصري.
- افهم السياق والمحادثة السابقة.
- لا تكرر كلام المستخدم.
- لا تقل إنك لا تستطيع الوصول للإنترنت إذا كانت أدوات البحث متاحة.
- عندما يطلب المستخدم البحث على الويب، استخدم أداة البحث.
- عندما يطلب البحث في GitHub، استخدم GitHub search.
- عندما تكون المعلومة حديثة أو تحتاج تحقق، ابحث أولاً.
- لا تخترع نتائج بحث.
- إذا وجدت نتيجة، اذكر المعلومات المهمة بوضوح.
- يمكن استخدام نتائج الويب وGitHub كمصادر للمساعدة في الإجابة.
- لا تعرض reasoning الداخلي.
- لا تقل Okay أو Let me check.
- أعطِ الإجابة النهائية مباشرة.
""".strip()


async def web_search(query: str) -> str:

    if not WEB_ENABLED:
        return ""

    try:

        url = "https://www.google.com/search"

        params = {
            "q": query
        }

        headers = {
            "User-Agent":
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        }

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True
        ) as client:

            r = await client.get(
                url,
                params=params,
                headers=headers
            )

            r.raise_for_status()

            text = re.sub(
                r"<[^>]+>",
                " ",
                r.text
            )

            text = re.sub(
                r"\s+",
                " ",
                text
            )

            return text[:10000]

    except Exception as e:

        print(
            "Web search error:",
            repr(e),
            flush=True
        )

        return ""


async def github_search(query: str) -> str:

    if not GITHUB_ENABLED:
        return ""

    try:

        url = "https://api.github.com/search/users"

        params = {
            "q": query,
            "per_page": 10
        }

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "MK-AI-Telegram-Bot"
        }

        async with httpx.AsyncClient(
            timeout=15
        ) as client:

            r = await client.get(
                url,
                params=params,
                headers=headers
            )

            r.raise_for_status()

            data = r.json()

            results = []

            for item in data.get("items", []):

                results.append({
                    "login": item.get("login"),
                    "html_url": item.get("html_url"),
                    "type": item.get("type"),
                })

            return json.dumps(
                results,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print(
            "GitHub search error:",
            repr(e),
            flush=True
        )

        return ""


async def llama_chat(
    messages: list,
    think: bool = True
) -> str:

    payload = {
        "model": LLAMA_MODEL,
        "messages": messages,

        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,

        "stream": False,

        "think": think,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=10,
            read=180,
            write=30,
            pool=10
        )
    ) as client:

        response = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload
        )

        response.raise_for_status()

        data = response.json()

        choice = (
            data.get("choices") or [{}]
        )[0]

        message = choice.get(
            "message"
        ) or {}

        content = message.get(
            "content",
            ""
        )

        # Some llama.cpp/Qwen configurations
        # return reasoning separately.
        if not content:

            content = message.get(
                "reasoning_content",
                ""
            )

        if not isinstance(content, str):
            content = str(content)

        return content.strip()


async def ask_ai(
    prompt: str,
    history: Optional[list] = None
) -> str:

    prompt = str(prompt).strip()

    context = []

    # ==================================
    # SEARCH INTENT
    # ==================================

    lower = prompt.lower()

    wants_github = (
        "github" in lower
        or "جيت هب" in lower
        or "حساب" in lower and (
            "dev" in lower
            or "developer" in lower
        )
    )

    wants_web = any(
        x in lower
        for x in [
            "ابحث",
            "دور",
            "شوف على النت",
            "الويب",
            "internet",
            "search",
            "find",
            "latest",
            "github"
        ]
    )

    # ==================================
    # GITHUB SEARCH
    # ==================================

    if wants_github:

        result = await github_search(prompt)

        if result:

            context.append(
                "\nنتائج GitHub:\n"
                + result
            )

    # ==================================
    # WEB SEARCH
    # ==================================

    elif wants_web:

        result = await web_search(prompt)

        if result:

            context.append(
                "\nنتائج الويب:\n"
                + result
            )

    # ==================================
    # MESSAGES
    # ==================================

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if history:

        for msg in history[-8:]:

            if not isinstance(msg, dict):
                continue

            role = msg.get("role")
            content = msg.get("content")

            if role in (
                "user",
                "assistant"
            ) and isinstance(
                content,
                str
            ):

                messages.append({
                    "role": role,
                    "content": content
                })

    final_prompt = prompt

    if context:

        final_prompt += (
            "\n\n"
            "استخدم نتائج البحث التالية للتحقق "
            "من المعلومات:\n"
            + "\n".join(context)
        )

    messages.append({
        "role": "user",
        "content": final_prompt
    })

    # ==================================
    # LOCAL QWEN3 THINKING
    # ==================================

    try:

        answer = await llama_chat(
            messages,
            think=THINKING
        )

        if answer:
            return answer

    except Exception as e:

        print(
            "llama.cpp error:",
            repr(e),
            flush=True
        )

    return (
        "❌ حصلت مشكلة في الـ AI المحلي. "
        "اتأكد إن llama-server شغال."
    )


async def generate_response(
    prompt: str,
    history: Optional[list] = None
) -> str:

    return await ask_ai(
        prompt,
        history
    )


async def chat(
    prompt: str,
    history: Optional[list] = None
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
        "thinking": THINKING,
        "web_search": WEB_ENABLED,
        "github_search": GITHUB_ENABLED
    }
