import os
import re
import json
import asyncio
import subprocess
from typing import Optional

import httpx

from config import (
    LLAMA_URL,
    LLAMA_MODEL,
    LLAMA_MAX_TOKENS,
    LLAMA_TEMPERATURE,
)

WEB_SEARCH_URL = os.getenv(
    "WEB_SEARCH_URL",
    ""
).strip()

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    ""
).strip()

TOOL_TIMEOUT = float(
    os.getenv("TOOL_TIMEOUT", "20")
)

MAX_TOOL_STEPS = int(
    os.getenv("MAX_TOOL_STEPS", "6")
)

SYSTEM_PROMPT = """
أنت MK AI Agent.

أنت لست chatbot عادي.

عندما يطلب المستخدم:
- البحث في الإنترنت
- البحث في GitHub
- البحث عن مستخدم GitHub
- البحث عن repository
- قراءة README
- فتح رابط
- قراءة ملف من GitHub
- تنفيذ أمر Linux
- فحص ملفات أو Git repository

يجب استخدام الأداة المناسبة فعلياً قبل إعطاء النتيجة.

ممنوع اختلاق نتيجة بحث.

ممنوع قول "بحثت" بدون تنفيذ أداة.

ممنوع افتراض أن الحساب أو repository غير موجود
بدون محاولة البحث فعلياً.

في GitHub:
ابدأ بالبحث المباشر، ثم جرّب:
- username variants
- repository search
- GitHub API
- web search

مثال:
إذا طلب المستخدم البحث عن "yfmarco dev"،
لا تعتبر العبارة username حرفياً فقط.
جرّب:
yfmarco
yfmarco-dev
YFMARCO-Dev
yfmarco_dev
ثم ابحث عن النتائج ذات الصلة.

إذا وجدت نتيجة حقيقية، اعرض الرابط والمعلومات الفعلية.

إذا فشلت أداة، جرّب طريقة أخرى قبل إعلان الفشل.

استخدم العربية/المصرية عندما يكون المستخدم عربياً.

لا تعرض reasoning الداخلي.
أعط النتيجة النهائية فقط.
""".strip()


async def http_get(url, headers=None, timeout=20):
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True
    ) as client:
        r = await client.get(
            url,
            headers=headers or {}
        )
        r.raise_for_status()
        return r


async def github_api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MK-AI-Agent",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = (
            f"Bearer {GITHUB_TOKEN}"
        )

    return await http_get(
        f"https://api.github.com{path}",
        headers=headers,
        timeout=TOOL_TIMEOUT
    )


async def github_search_users(query):
    r = await github_api(
        "/search/users?q=" +
        httpx.QueryParams({"q": query}).get("q")
    )

    return r.json()


async def github_search_repositories(query):
    params = httpx.QueryParams({
        "q": query,
        "per_page": "10"
    })

    r = await github_api(
        "/search/repositories?" + str(params)
    )

    return r.json()


async def github_user(username):
    r = await github_api(
        "/users/" + username
    )

    return r.json()


async def github_repo(owner, repo):
    r = await github_api(
        f"/repos/{owner}/{repo}"
    )

    return r.json()


async def github_readme(owner, repo):
    r = await github_api(
        f"/repos/{owner}/{repo}/readme"
    )

    data = r.json()

    import base64

    content = data.get("content", "")
    if content:
        return base64.b64decode(
            content
        ).decode(
            "utf-8",
            errors="replace"
        )

    return ""


async def url_fetch(url):
    r = await http_get(
        url,
        timeout=TOOL_TIMEOUT
    )

    text = r.text

    if len(text) > 50000:
        text = text[:50000]

    return text


async def web_search(query):
    """
    Uses configured external search endpoint.

    WEB_SEARCH_URL should return JSON.
    Example response:
    {
      "results": [
        {
          "title": "...",
          "url": "...",
          "snippet": "..."
        }
      ]
    }
    """

    if not WEB_SEARCH_URL:
        return {
            "error": "WEB_SEARCH_URL is not configured"
        }

    params = {
        "q": query
    }

    r = await http_get(
        WEB_SEARCH_URL,
        timeout=TOOL_TIMEOUT
    )

    try:
        return r.json()
    except Exception:
        return {
            "text": r.text[:30000]
        }


async def linux_terminal(command):
    """
    Restricted Linux terminal.

    Dangerous commands are blocked.
    """

    command = command.strip()

    blocked = [
        "rm -rf /",
        "mkfs",
        "dd if=",
        ":(){",
        "shutdown",
        "reboot",
        "init 0",
        "init 6",
        "chmod -R 777 /",
        "chown -R",
    ]

    low = command.lower()

    for item in blocked:
        if item in low:
            return {
                "error": "Dangerous command blocked"
            }

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=5
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=TOOL_TIMEOUT
        )

        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode(
                errors="replace"
            )[-30000:],
            "stderr": stderr.decode(
                errors="replace"
            )[-10000:],
        }

    except Exception as e:
        return {
            "error": repr(e)
        }


async def git_command(command):
    allowed = (
        "git status",
        "git log",
        "git diff",
        "git branch",
        "git remote",
        "git show",
    )

    if not command.startswith(allowed):
        return {
            "error": "Git command not allowed"
        }

    return await linux_terminal(command)


async def tool_dispatch(name, args):
    try:
        if name == "github_search_users":
            return await github_search_users(
                args["query"]
            )

        if name == "github_search_repositories":
            return await github_search_repositories(
                args["query"]
            )

        if name == "github_user":
            return await github_user(
                args["username"]
            )

        if name == "github_repo":
            return await github_repo(
                args["owner"],
                args["repo"]
            )

        if name == "github_readme":
            return await github_readme(
                args["owner"],
                args["repo"]
            )

        if name == "url_fetch":
            return await url_fetch(
                args["url"]
            )

        if name == "web_search":
            return await web_search(
                args["query"]
            )

        if name == "terminal":
            return await linux_terminal(
                args["command"]
            )

        if name == "git":
            return await git_command(
                args["command"]
            )

        return {
            "error": f"Unknown tool: {name}"
        }

    except Exception as e:
        return {
            "error": repr(e)
        }


def detect_tools(prompt):
    """
    Deterministic tool routing.

    This is intentionally outside the LLM so Qwen
    cannot simply claim that it searched.
    """

    p = prompt.lower()

    tools = []

    if (
        "github" in p
        or "جيت هب" in p
        or "حساب" in p and "dev" in p
    ):
        tools.append("github")

    if (
        "ابحث" in p
        or "بحث" in p
        or "search" in p
        or "الويب" in p
        or "web" in p
        or "internet" in p
        or "الانترنت" in p
    ):
        tools.append("web")

    if (
        "http://" in p
        or "https://" in p
        or "افتح الرابط" in p
        or "اقرأ الرابط" in p
        or "readme" in p
    ):
        tools.append("url")

    return tools


async def forced_github_search(prompt):
    """
    Performs real GitHub searches before Qwen answers.
    """

    # Extract likely search phrase.
    query = prompt

    variants = [
        query,
        "yfmarco",
        "yfmarco-dev",
        "YFMARCO-Dev",
        "yfmarco_dev",
    ]

    results = {
        "users": [],
        "repositories": []
    }

    seen_users = set()
    seen_repos = set()

    for q in variants:
        try:
            data = await github_search_users(q)

            for item in data.get("items", []):
                login = item.get("login")

                if login and login.lower() not in seen_users:
                    seen_users.add(login.lower())

                    results["users"].append({
                        "login": login,
                        "url": item.get(
                            "html_url"
                        ),
                        "score": item.get(
                            "score"
                        )
                    })

        except Exception as e:
            results.setdefault(
                "errors", []
            ).append(repr(e))

        try:
            data = await github_search_repositories(q)

            for item in data.get("items", []):
                full = item.get(
                    "full_name"
                )

                if (
                    full
                    and full.lower()
                    not in seen_repos
                ):
                    seen_repos.add(
                        full.lower()
                    )

                    results["repositories"].append({
                        "full_name": full,
                        "url": item.get(
                            "html_url"
                        ),
                        "description": item.get(
                            "description"
                        ),
                        "stars": item.get(
                            "stargazers_count"
                        )
                    })

        except Exception as e:
            results.setdefault(
                "errors", []
            ).append(repr(e))

    return results


async def llama_chat(messages):
    payload = {
        "model": LLAMA_MODEL,
        "messages": messages,
        "temperature": LLAMA_TEMPERATURE,
        "max_tokens": LLAMA_MAX_TOKENS,
        "stream": False,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5,
            read=90,
            write=10,
            pool=5
        )
    ) as client:

        r = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload
        )

        r.raise_for_status()

        data = r.json()

        choice = (
            data.get("choices") or [{}]
        )[0]

        message = (
            choice.get("message") or {}
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            content = (
                message.get(
                    "reasoning_content",
                    ""
                )
            )

        return str(content).strip()


async def ask_ai(
    prompt: str,
    history: Optional[list] = None
) -> str:

    prompt = str(prompt).strip()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if history:
        for msg in history[-8:]:
            if (
                isinstance(msg, dict)
                and msg.get("role")
                in ("user", "assistant")
                and isinstance(
                    msg.get("content"),
                    str
                )
            ):
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

    # ---------------------------------------------
    # REAL GITHUB SEARCH
    # ---------------------------------------------

    tools = detect_tools(prompt)

    if "github" in tools:

        print(
            "[AGENT] Real GitHub search:",
            prompt,
            flush=True
        )

        github_results = (
            await forced_github_search(
                prompt
            )
        )

        messages.append({
            "role": "system",
            "content":
                "نتائج GitHub الحقيقية "
                "التي تم جلبها الآن:\n"
                + json.dumps(
                    github_results,
                    ensure_ascii=False,
                    indent=2
                )
        })

    # ---------------------------------------------
    # URL FETCH
    # ---------------------------------------------

    urls = re.findall(
        r'https?://[^\s]+',
        prompt
    )

    for url in urls[:3]:

        try:
            print(
                "[AGENT] Fetching:",
                url,
                flush=True
            )

            content = await url_fetch(
                url.rstrip(".,)")
            )

            messages.append({
                "role": "system",
                "content":
                    f"محتوى الرابط الحقيقي "
                    f"{url}:\n{content[:30000]}"
            })

        except Exception as e:
            messages.append({
                "role": "system",
                "content":
                    f"فشل فتح {url}: {e}"
            })

    # ---------------------------------------------
    # WEB SEARCH
    # ---------------------------------------------

    if "web" in tools:

        try:

            print(
                "[AGENT] Web search:",
                prompt,
                flush=True
            )

            result = await web_search(
                prompt
            )

            messages.append({
                "role": "system",
                "content":
                    "نتيجة بحث الويب الحقيقية:\n"
                    + json.dumps(
                        result,
                        ensure_ascii=False
                    )[:30000]
            })

        except Exception as e:

            messages.append({
                "role": "system",
                "content":
                    f"Web search failed: {e}"
            })

    # ---------------------------------------------
    # FINAL ANSWER
    # ---------------------------------------------

    messages.append({
        "role": "user",
        "content": prompt,
    })

    return await llama_chat(
        messages
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
        "model": LLAMA_MODEL,
        "url": LLAMA_URL,
        "github": True,
        "web": bool(WEB_SEARCH_URL),
        "url_fetch": True,
        "terminal": True,
        "git": True,
    }
