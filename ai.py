import os
import json
import shlex
import asyncio
import subprocess
import re
from typing import Optional

import httpx

from config import (
    LLAMA_URL,
    LLAMA_MODEL,
    AGENT_MAX_STEPS,
    AGENT_TIMEOUT,
    WEB_ENABLED,
    GITHUB_ENABLED,
    TERMINAL_ENABLED,
    AUTO_INSTALL,
)


# ==================================================
# BASIC HTTP
# ==================================================

async def http_get(
    url: str,
    timeout: float = 20.0,
    headers: Optional[dict] = None,
):
    timeout_cfg = httpx.Timeout(
        connect=5,
        read=timeout,
        write=10,
        pool=5,
    )

    async with httpx.AsyncClient(
        timeout=timeout_cfg,
        follow_redirects=True,
        headers=headers or {
            "User-Agent": "MK-AI-Agent/1.0"
        },
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response


# ==================================================
# WEB SEARCH
# ==================================================

async def web_search(query: str) -> str:

    if not WEB_ENABLED:
        return "Web search is disabled."

    query = str(query).strip()

    if not query:
        return "Empty search query."

    try:
        response = await http_get(
            "https://html.duckduckgo.com/html/",
            timeout=20,
        )

        # GET fallback isn't enough for DDG search,
        # so use direct query endpoint.
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent":
                "Mozilla/5.0 MK-AI-Agent"
            },
        ) as client:

            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )

            r.raise_for_status()

            html = r.text

        results = []

        # Extract result blocks without external parser.
        pattern = re.compile(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.I | re.S,
        )

        for match in pattern.finditer(html):

            url = match.group(1)

            title = re.sub(
                r"<.*?>",
                "",
                match.group(2),
            )

            title = (
                title
                .replace("&amp;", "&")
                .replace("&quot;", '"')
            )

            if url and title:
                results.append(
                    f"- {title.strip()}\n  {url}"
                )

            if len(results) >= 8:
                break

        if not results:
            return (
                f"No search results found for: {query}"
            )

        return (
            f"WEB SEARCH: {query}\n\n"
            + "\n".join(results)
        )

    except Exception as e:
        return f"Web search error: {e}"


# ==================================================
# GITHUB API
# ==================================================

async def github_search(
    query: str,
    search_type: str = "users",
) -> str:

    if not GITHUB_ENABLED:
        return "GitHub search is disabled."

    query = str(query).strip()

    endpoints = {
        "users":
            "https://api.github.com/search/users",
        "repos":
            "https://api.github.com/search/repositories",
        "code":
            "https://api.github.com/search/code",
    }

    endpoint = endpoints.get(
        search_type,
        endpoints["users"],
    )

    try:

        response = await http_get(
            endpoint,
            timeout=20,
            headers={
                "Accept":
                    "application/vnd.github+json",
                "User-Agent":
                    "MK-AI-Agent",
            },
        )

        # The previous request didn't contain params.
        # Do the actual API request here.
        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "Accept":
                    "application/vnd.github+json",
                "User-Agent":
                    "MK-AI-Agent",
            },
        ) as client:

            r = await client.get(
                endpoint,
                params={
                    "q": query,
                    "per_page": 10,
                },
            )

            r.raise_for_status()
            data = r.json()

        items = data.get("items", [])

        if not items:
            return (
                f"GitHub: no {search_type} results "
                f"for `{query}`"
            )

        output = [
            f"GITHUB {search_type.upper()}: {query}",
            "",
        ]

        for item in items[:10]:

            if search_type == "users":

                output.append(
                    f"- {item.get('login')}\n"
                    f"  {item.get('html_url')}"
                )

            elif search_type == "repos":

                output.append(
                    f"- {item.get('full_name')}\n"
                    f"  {item.get('html_url')}\n"
                    f"  {item.get('description') or ''}"
                )

            else:

                output.append(
                    f"- {item.get('name')}\n"
                    f"  {item.get('html_url')}"
                )

        return "\n".join(output)

    except Exception as e:
        return f"GitHub error: {e}"


# ==================================================
# URL FETCH
# ==================================================

async def fetch_url(url: str) -> str:

    url = str(url).strip()

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):
        return "Invalid URL."

    try:

        response = await http_get(
            url,
            timeout=30,
        )

        text = response.text

        # Remove scripts/styles.
        text = re.sub(
            r"<script.*?</script>",
            " ",
            text,
            flags=re.I | re.S,
        )

        text = re.sub(
            r"<style.*?</style>",
            " ",
            text,
            flags=re.I | re.S,
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            text,
        )

        text = (
            text
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        # Keep context under control.
        text = text[:18000]

        return (
            f"URL: {url}\n\n"
            f"{text}"
        )

    except Exception as e:
        return f"URL fetch error: {e}"


# ==================================================
# GITHUB REPOSITORY FILE
# ==================================================

async def github_file(
    owner: str,
    repo: str,
    path: str = "README.md",
    branch: str = "main",
) -> str:

    url = (
        f"https://raw.githubusercontent.com/"
        f"{owner}/{repo}/{branch}/{path}"
    )

    try:
        response = await http_get(
            url,
            timeout=20,
        )

        return (
            f"GITHUB FILE\n"
            f"{owner}/{repo}/{path}\n\n"
            f"{response.text[:30000]}"
        )

    except Exception as e:

        # Try master branch.
        if branch == "main":
            return await github_file(
                owner,
                repo,
                path,
                "master",
            )

        return f"GitHub file error: {e}"


# ==================================================
# LINUX TERMINAL
# ==================================================

BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "poweroff",
    "init 0",
    "init 6",
    "halt",
    "passwd",
    "userdel",
    "usermod",
    "chmod -R 777 /",
    "chown -R",
]

ALLOWED_SHELL_PREFIXES = [
    "pwd",
    "ls",
    "find",
    "cat",
    "head",
    "tail",
    "grep",
    "sed",
    "awk",
    "sort",
    "wc",
    "du",
    "df",
    "ps",
    "pgrep",
    "git",
    "curl",
    "wget",
    "python",
    "python3",
    "pip",
    "pip3",
    "apt",
    "apt-get",
    "dpkg",
    "which",
    "whereis",
    "uname",
    "free",
    "uptime",
    "systemctl",
    "journalctl",
    "mkdir",
    "cp",
    "mv",
    "touch",
    "file",
    "stat",
    "tree",
]


def command_allowed(command: str) -> bool:

    normalized = command.lower().strip()

    for blocked in BLOCKED_COMMANDS:
        if blocked in normalized:
            return False

    first = normalized.split()[0] if normalized else ""

    return first in ALLOWED_SHELL_PREFIXES


async def terminal(
    command: str,
    timeout: int = 30,
) -> str:

    if not TERMINAL_ENABLED:
        return "Terminal is disabled."

    command = str(command).strip()

    if not command:
        return "Empty command."

    if not command_allowed(command):
        return (
            "Command blocked by security policy:\n"
            + command
        )

    try:

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.expanduser("~"),
        )

        try:

            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

        except asyncio.TimeoutError:

            process.kill()

            return (
                "Terminal command timed out."
            )

        output = stdout.decode(
            "utf-8",
            errors="replace",
        )

        if len(output) > 16000:
            output = output[-16000:]

        return (
            f"$ {command}\n\n"
            f"{output}"
        )

    except Exception as e:

        return f"Terminal error: {e}"


# ==================================================
# AUTO INSTALL
# ==================================================

PACKAGE_MAP = {
    "git": "git",
    "curl": "curl",
    "wget": "wget",
    "jq": "jq",
    "ripgrep": "ripgrep",
    "rg": "ripgrep",
    "tree": "tree",
    "python": "python3",
    "python3": "python3",
    "pip": "python3-pip",
    "unzip": "unzip",
    "zip": "zip",
    "7zip": "7zip",
}


async def install_tool(
    tool: str,
) -> str:

    if not AUTO_INSTALL:
        return "Automatic installation is disabled."

    tool = str(tool).strip().lower()

    package = PACKAGE_MAP.get(tool)

    if not package:
        return (
            f"Tool `{tool}` is not in the "
            f"safe auto-install allowlist."
        )

    result = await terminal(
        f"apt-get update -qq && "
        f"DEBIAN_FRONTEND=noninteractive "
        f"apt-get install -y {shlex.quote(package)}",
        timeout=120,
    )

    return result


# ==================================================
# LOCAL FILE READER
# ==================================================

async def read_file(
    path: str,
) -> str:

    path = os.path.abspath(
        os.path.expanduser(str(path))
    )

    home = os.path.abspath(
        os.path.expanduser("~")
    )

    # Restrict reading to home.
    if not (
        path == home
        or path.startswith(home + os.sep)
    ):
        return "File access outside HOME is blocked."

    if not os.path.isfile(path):
        return f"File not found: {path}"

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as f:

            data = f.read(30000)

        return (
            f"FILE: {path}\n\n"
            f"{data}"
        )

    except Exception as e:

        return f"File read error: {e}"


# ==================================================
# TOOL REGISTRY
# ==================================================

TOOLS_DESCRIPTION = """
AVAILABLE TOOLS

web_search(query)
Search the public web.

github_search(query, type)
Search GitHub users, repositories, or code.

fetch_url(url)
Open a webpage and extract readable text.

github_file(owner, repo, path, branch)
Read a raw file from a GitHub repository.

terminal(command)
Execute an allowed Linux shell command.

install_tool(tool)
Install a missing Linux utility using apt.

read_file(path)
Read a local text file.

IMPORTANT:
You can call multiple tools.
You are an agent.
Do not guess when a tool can verify the answer.
"""


SYSTEM_PROMPT = f"""
You are MK AI Agent.

You are NOT a simple chatbot.

You have access to a real Linux environment and tools.

{TOOLS_DESCRIPTION}

RULES:

1. When the user asks you to search the internet,
   actually use web_search.

2. When the user asks about GitHub,
   actually use github_search.

3. If a GitHub username is uncertain,
   search multiple variants automatically.

Example:
"yfmarco dev"

Try:
yfmarco dev
yfmarco-dev
yfmarco
YFMARCO-Dev
site:github.com/yfmarco

Do not immediately tell the user that
the account does not exist.

4. If you find a GitHub repository and the user
   asks for README content, use github_file or
   fetch_url and READ THE ACTUAL FILE.

5. Never invent webpage contents.

6. If a Linux tool is missing and installing it
   is useful, use install_tool.

7. You can use several tools sequentially.

8. Verify important information before answering.

9. Answer in Egyptian Arabic when the user
   speaks Egyptian Arabic.

10. Do not expose internal chain-of-thought.

11. Give concise final answers unless the user
   requests details.

12. Tool results are evidence.
"""


# ==================================================
# LLAMA CHAT
# ==================================================

async def llama_chat(
    messages: list,
) -> dict:

    payload = {
        "model": LLAMA_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 700,
        "stream": False,
    }

    timeout_cfg = httpx.Timeout(
        connect=5,
        read=90,
        write=10,
        pool=5,
    )

    async with httpx.AsyncClient(
        timeout=timeout_cfg,
    ) as client:

        response = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
        )

        response.raise_for_status()

        return response.json()


def extract_text(data: dict) -> str:

    choices = data.get("choices") or []

    if not choices:
        return ""

    message = choices[0].get(
        "message"
    ) or {}

    content = message.get(
        "content",
        "",
    )

    if not isinstance(content, str):
        return str(content)

    return content.strip()


# ==================================================
# TOOL CALL PARSER
# ==================================================

def parse_tool_call(text: str):

    text = text.strip()

    # Preferred format:
    #
    # TOOL_CALL
    # {"tool":"web_search","query":"..."}

    match = re.search(
        r"TOOL_CALL\s*```?\s*(\{.*?\})\s*```?",
        text,
        re.I | re.S,
    )

    if not match:
        match = re.search(
            r"(\{\s*\"tool\"\s*:.*?\})",
            text,
            re.I | re.S,
        )

    if not match:
        return None

    raw = match.group(1)

    try:
        data = json.loads(raw)

        if not isinstance(data, dict):
            return None

        if "tool" not in data:
            return None

        return data

    except Exception:
        return None


# ==================================================
# TOOL EXECUTION
# ==================================================

async def execute_tool(
    call: dict,
) -> str:

    tool = str(
        call.get("tool", "")
    ).strip()

    try:

        if tool == "web_search":

            return await web_search(
                call.get("query", "")
            )

        if tool == "github_search":

            return await github_search(
                call.get("query", ""),
                call.get("type", "users"),
            )

        if tool == "fetch_url":

            return await fetch_url(
                call.get("url", "")
            )

        if tool == "github_file":

            return await github_file(
                call.get("owner", ""),
                call.get("repo", ""),
                call.get("path", "README.md"),
                call.get("branch", "main"),
            )

        if tool == "terminal":

            return await terminal(
                call.get("command", "")
            )

        if tool == "install_tool":

            return await install_tool(
                call.get("tool_name", "")
            )

        if tool == "read_file":

            return await read_file(
                call.get("path", "")
            )

        return (
            f"Unknown tool: {tool}"
        )

    except Exception as e:

        return (
            f"Tool `{tool}` failed: "
            f"{repr(e)}"
        )


# ==================================================
# AGENT LOOP
# ==================================================

async def agent(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if history:

        for item in history[-8:]:

            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role in (
                "user",
                "assistant",
            ) and isinstance(content, str):

                messages.append({
                    "role": role,
                    "content": content[:8000],
                })

    messages.append({
        "role": "user",
        "content": prompt,
    })

    for step in range(
        1,
        AGENT_MAX_STEPS + 1,
    ):

        try:

            result = await asyncio.wait_for(
                llama_chat(messages),
                timeout=AGENT_TIMEOUT,
            )

            answer = extract_text(result)

            if not answer:
                return (
                    "❌ الـ AI رجع رد فاضي."
                )

            tool_call = parse_tool_call(
                answer
            )

            # No tool required.
            if not tool_call:

                return answer

            # Tool execution.
            tool_name = tool_call.get(
                "tool",
                "unknown",
            )

            print(
                f"[AGENT] step={step} "
                f"tool={tool_name}",
                flush=True,
            )

            tool_result = await asyncio.wait_for(
                execute_tool(tool_call),
                timeout=130,
            )

            messages.append({
                "role": "assistant",
                "content": answer,
            })

            messages.append({
                "role": "user",
                "content": (
                    "TOOL RESULT\n"
                    f"Tool: {tool_name}\n\n"
                    f"{tool_result}\n\n"
                    "Continue the task. "
                    "Use another tool if necessary. "
                    "If enough evidence exists, "
                    "give the final answer."
                ),
            })

        except Exception as e:

            print(
                "[AGENT ERROR]",
                repr(e),
                flush=True,
            )

            return (
                "❌ حصل خطأ أثناء تنفيذ مهمة الـ AI."
            )

    return (
        "⚠️ المهمة احتاجت خطوات أكتر من الحد "
        "المسموح، فهوقف هنا بدل ما أفضل ألف."
    )


# ==================================================
# PUBLIC API
# ==================================================

async def ask_ai(
    prompt: str,
    history: Optional[list] = None,
) -> str:

    return await agent(
        prompt,
        history,
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


def get_model_info():

    return {
        "provider": "llama.cpp",
        "model": LLAMA_MODEL,
        "url": LLAMA_URL,
        "agent": True,
        "web_search": WEB_ENABLED,
        "github_search": GITHUB_ENABLED,
        "terminal": TERMINAL_ENABLED,
        "auto_install": AUTO_INSTALL,
        "max_steps": AGENT_MAX_STEPS,
    }
