import os
import re
import json
import asyncio
from typing import Optional
from urllib.parse import quote_plus

import httpx


LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080"
).strip().rstrip("/")

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B-Q4_K_M.gguf"
).strip()

THINKING = os.getenv(
    "AI_THINKING",
    "false"
).lower() == "true"

WEB_ENABLED = True
GITHUB_ENABLED = True

MAX_TOKENS = int(
    os.getenv("AI_MAX_TOKENS", "500")
)

TEMPERATURE = float(
    os.getenv("AI_TEMPERATURE", "0.25")
)

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    ""
).strip()


SYSTEM_PROMPT = """
أنت Spider AI Assistant داخل Telegram.

أنت مساعد ذكي مصري.

القواعد المهمة:

1. أجب بالعربية المصرية عندما المستخدم يتكلم عربي.
2. لا تدّعي أنك بحثت إذا لم يتم البحث فعلياً.
3. عندما يطلب المستخدم البحث في الإنترنت أو GitHub:
   - استخدم نتائج أدوات البحث الموجودة في السياق.
   - لا تعتمد على ذاكرتك فقط.
   - قارن أكثر من نتيجة.
   - لا تعتبر فشل أول query دليلاً على عدم وجود الشيء.
4. أسماء GitHub يجب التعامل معها بمرونة:
   - spaces
   - hyphens
   - underscores
   - lowercase/uppercase
   - username بدون كلمات إضافية.
5. إذا وجدت نتيجة قوية، أعطِ الحساب أو الرابط الصحيح مباشرة.
6. إذا لم تجد نتيجة مؤكدة، قل إن النتائج غير كافية بدلاً من اختراع إجابة.
7. لا تقل "لا أستطيع تصفح الإنترنت" إذا كانت أدوات البحث متاحة.
8. لا تكتب reasoning داخلي.
9. لا تقل Okay أو Let me check.
10. في السؤال البسيط اجعل الإجابة قصيرة.
""".strip()


def normalize_name(text: str) -> str:
    text = text.lower().strip()

    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )

    text = re.sub(
        r"[^a-z0-9_\-\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def generate_variants(query: str) -> list[str]:

    q = normalize_name(query)

    variants = []

    def add(x):
        x = x.strip()

        if x and x not in variants:
            variants.append(x)

    add(q)

    compact = re.sub(
        r"[\s_\-]+",
        "",
        q
    )

    hyphen = re.sub(
        r"[\s_]+",
        "-",
        q
    )

    underscore = re.sub(
        r"[\s\-]+",
        "_",
        q
    )

    spaced = re.sub(
        r"[_\-]+",
        " ",
        q
    )

    add(compact)
    add(hyphen)
    add(underscore)
    add(spaced)

    words = q.split()

    if words:
        add(words[0])

    if len(words) > 1:
        add("".join(words))
        add("-".join(words))
        add("_".join(words))

    return variants[:12]


async def github_search(
    query: str
) -> list[dict]:

    if not GITHUB_ENABLED:
        return []

    variants = generate_variants(query)

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "MK-AI-Telegram-Bot",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = (
            f"Bearer {GITHUB_TOKEN}"
        )

    results = []

    timeout = httpx.Timeout(
        connect=8,
        read=20,
        write=10,
        pool=10,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:

        # =================================
        # 1. DIRECT USER LOOKUPS
        # =================================
        for variant in variants:

            if not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9\-]*",
                variant
            ):
                continue

            try:

                r = await client.get(
                    f"https://api.github.com/users/"
                    f"{quote_plus(variant)}"
                )

                if r.status_code == 200:

                    data = r.json()

                    results.append({
                        "type": "github_user",
                        "login": data.get("login"),
                        "name": data.get("name"),
                        "bio": data.get("bio"),
                        "followers": data.get(
                            "followers"
                        ),
                        "public_repos": data.get(
                            "public_repos"
                        ),
                        "html_url": data.get(
                            "html_url"
                        ),
                        "source": "GitHub API direct",
                    })

            except Exception as e:

                print(
                    "GitHub direct error:",
                    repr(e),
                    flush=True
                )

        # =================================
        # 2. GITHUB USER SEARCH
        # =================================
        for variant in variants:

            try:

                r = await client.get(
                    "https://api.github.com/search/users",
                    params={
                        "q": variant,
                        "per_page": 10,
                    },
                )

                if r.status_code != 200:
                    continue

                data = r.json()

                for item in data.get(
                    "items",
                    []
                ):

                    results.append({
                        "type": "github_search_user",
                        "login": item.get("login"),
                        "avatar_url": item.get(
                            "avatar_url"
                        ),
                        "html_url": item.get(
                            "html_url"
                        ),
                        "source": (
                            "GitHub API user search"
                        ),
                    })

            except Exception as e:

                print(
                    "GitHub search error:",
                    repr(e),
                    flush=True
                )

        # =================================
        # 3. GITHUB CODE / REPOSITORY SEARCH
        # =================================
        search_queries = []

        for variant in variants[:6]:

            search_queries.extend([
                f'"{variant}"',
                variant,
            ])

        for q in search_queries:

            try:

                r = await client.get(
                    "https://api.github.com/search/"
                    "repositories",
                    params={
                        "q": q,
                        "per_page": 5,
                    },
                )

                if r.status_code != 200:
                    continue

                data = r.json()

                for item in data.get(
                    "items",
                    []
                ):

                    results.append({
                        "type": "github_repository",
                        "name": item.get(
                            "full_name"
                        ),
                        "description": item.get(
                            "description"
                        ),
                        "html_url": item.get(
                            "html_url"
                        ),
                        "owner": (
                            item.get("owner", {})
                            .get("login")
                        ),
                        "stars": item.get(
                            "stargazers_count"
                        ),
                        "source": (
                            "GitHub repository search"
                        ),
                    })

            except Exception as e:

                print(
                    "GitHub repo error:",
                    repr(e),
                    flush=True
                )

    # =================================
    # DEDUPLICATE
    # =================================
    unique = {}
    for item in results:

        key = (
            item.get("type"),
            item.get("login")
            or item.get("html_url")
            or item.get("name")
        )

        unique[key] = item

    return list(unique.values())[:60]


async def web_search(
    query: str
) -> list[dict]:

    if not WEB_ENABLED:
        return []

    variants = generate_variants(query)

    results = []

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={
            "User-Agent":
            "Mozilla/5.0 MK-AI-Telegram-Bot"
        },
    ) as client:

        for variant in variants[:6]:

            urls = [
                (
                    "https://www.google.com/search?"
                    f"q={quote_plus(variant)}"
                ),
                (
                    "https://html.duckduckgo.com/"
                    "html/?q="
                    f"{quote_plus(variant)}"
                ),
            ]

            for url in urls:

                try:

                    r = await client.get(url)

                    if r.status_code != 200:
                        continue

                    text = r.text[:15000]

                    # Keep useful URLs/text only
                    links = re.findall(
                        r'https?://[^\s"<>&]+',
                        text
                    )

                    for link in links[:15]:

                        if (
                            "google.com/search"
                            in link
                        ):
                            continue

                        results.append({
                            "type": "web",
                            "query": variant,
                            "url": link,
                            "source": "Web search",
                        })

                except Exception as e:

                    print(
                        "Web search error:",
                        repr(e),
                        flush=True
                    )

    return results[:80]


async def perform_search(
    query: str
) -> list[dict]:

    github_task = github_search(query)
    web_task = web_search(query)

    github_results, web_results = (
        await asyncio.gather(
            github_task,
            web_task,
            return_exceptions=True,
        )
    )

    if isinstance(
        github_results,
        Exception
    ):
        github_results = []

    if isinstance(
        web_results,
        Exception
    ):
        web_results = []

    return (
        github_results
        + web_results
    )


def looks_like_search_request(
    text: str
) -> bool:

    text_lower = text.lower()

    keywords = [
        "ابحث",
        "دور",
        "شوف على النت",
        "شوف في الويب",
        "github",
        "git hub",
        "حساب",
        "repo",
        "repository",
        "لينك",
        "رابط",
        "search",
        "find",
        "look up",
        "who is",
    ]

    return any(
        word in text_lower
        for word in keywords
    )


async def _llama_chat(
    messages: list,
) -> str:

    payload = {
        "model": LLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "cache_prompt": True,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    if THINKING:
        payload["think"] = True
    else:
        payload["think"] = False

    timeout = httpx.Timeout(
        connect=10,
        read=120,
        write=20,
        pool=10,
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:

        response = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        choice = (
            data.get("choices", [{}])[0]
        )

        message = (
            choice.get("message") or {}
        )

        content = message.get(
            "content",
            ""
        )

        if not isinstance(
            content,
            str
        ):
            content = str(content)

        content = content.strip()

        if not content:

            # llama.cpp Qwen may put thinking
            # in reasoning_content
            reasoning = message.get(
                "reasoning_content",
                ""
            )

            if isinstance(
                reasoning,
                str
            ):
                content = reasoning.strip()

        if not content:
            raise RuntimeError(
                "Empty llama.cpp response"
            )

        return content


def format_search_context(
    results: list[dict]
) -> str:

    if not results:
        return (
            "لم يتم العثور على نتائج بحث "
            "قابلة للاستخدام."
        )

    lines = [
        "=== REAL SEARCH RESULTS ==="
    ]

    for i, item in enumerate(
        results[:60],
        1
    ):

        lines.append(
            f"\n[{i}] "
            + json.dumps(
                item,
                ensure_ascii=False
            )
        )

    return "\n".join(lines)


async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    prompt = str(prompt).strip()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # =================================
    # REAL SEARCH
    # =================================
    if looks_like_search_request(
        prompt
    ):

        print(
            "SEARCH REQUEST:",
            prompt,
            flush=True
        )

        results = await perform_search(
            prompt
        )

        print(
            "SEARCH RESULTS:",
            len(results),
            flush=True
        )

        search_context = (
            format_search_context(
                results
            )
        )

        messages.append({
            "role": "system",
            "content":
                "نتائج بحث حقيقية تم جمعها "
                "قبل الإجابة:\n\n"
                + search_context
                + "\n\n"
                "حلل النتائج ولا تعتمد على "
                "تخمين الاسم فقط."
        })

    # =================================
    # HISTORY
    # =================================
    if history:

        for msg in history[-6:]:

            if not isinstance(
                msg,
                dict
            ):
                continue

            role = msg.get("role")
            content = msg.get("content")

            if role not in (
                "user",
                "assistant"
            ):
                continue

            if not isinstance(
                content,
                str
            ):
                continue

            content = content.strip()

            if content:

                messages.append({
                    "role": role,
                    "content": content,
                })

    messages.append({
        "role": "user",
        "content": prompt,
    })

    try:

        return await _llama_chat(
            messages
        )

    except Exception as e:

        print(
            "llama.cpp error:",
            repr(e),
            flush=True
        )

        return (
            "❌ حصلت مشكلة في الـAI المحلي. "
            "اتأكد إن llama-server شغال."
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
        "thinking": THINKING,
        "web_search": WEB_ENABLED,
        "github_search": GITHUB_ENABLED,
    }
