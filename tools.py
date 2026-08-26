import json
import re
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup


HTTP_TIMEOUT = httpx.Timeout(
    connect=8.0,
    read=25.0,
    write=10.0,
    pool=10.0,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130 Safari/537.36"
    )
}


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the public web for current information. "
                "Use this when the user explicitly asks to search "
                "the internet, find a person, project, website, "
                "news, documentation, or current information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results.",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": (
                "Open and read a public webpage. "
                "Use this after web search when a result "
                "needs to be inspected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full HTTP/HTTPS URL."
                    }
                },
                "required": ["url"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "github_search",
            "description": (
                "Search GitHub public users, repositories, "
                "issues and general public GitHub resources. "
                "Use this when the user asks about GitHub."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "GitHub search query."
                    },
                    "search_type": {
                        "type": "string",
                        "enum": [
                            "repositories",
                            "users",
                            "issues"
                        ],
                        "description": "GitHub search category."
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 5
                    }
                },
                "required": [
                    "query",
                    "search_type"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "github_user",
            "description": (
                "Get public information about a GitHub user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string"
                    }
                },
                "required": ["username"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "github_repo",
            "description": (
                "Get public information about a GitHub repository."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string"
                    },
                    "repo": {
                        "type": "string"
                    }
                },
                "required": [
                    "owner",
                    "repo"
                ]
            }
        }
    }
]


# ============================================================
# WEB SEARCH
# ============================================================

async def web_search(
    query: str,
    max_results: int = 5,
):

    max_results = max(
        1,
        min(int(max_results), 10)
    )

    url = (
        "https://html.duckduckgo.com/html/?q="
        + quote(query)
    )

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:

        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = []

    for item in soup.select(
        ".result"
    )[:max_results]:

        title_el = item.select_one(
            ".result__title"
        )

        link_el = item.select_one(
            ".result__a"
        )

        snippet_el = item.select_one(
            ".result__snippet"
        )

        if not link_el:
            continue

        title = (
            title_el.get_text(
                " ",
                strip=True
            )
            if title_el
            else link_el.get_text(
                " ",
                strip=True
            )
        )

        href = link_el.get(
            "href",
            ""
        )

        snippet = (
            snippet_el.get_text(
                " ",
                strip=True
            )
            if snippet_el
            else ""
        )

        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
        })

    return {
        "query": query,
        "results": results,
    }


# ============================================================
# OPEN URL
# ============================================================

async def open_url(url: str):

    parsed = urlparse(url)

    if parsed.scheme not in (
        "http",
        "https"
    ):
        raise ValueError(
            "Only HTTP/HTTPS URLs are allowed."
        )

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:

        response = await client.get(url)
        response.raise_for_status()

    content_type = (
        response.headers.get(
            "content-type",
            ""
        )
        .lower()
    )

    if "text/html" not in content_type:
        return {
            "url": str(response.url),
            "content_type": content_type,
            "text": response.text[:12000],
        }

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg"
    ]):
        tag.decompose()

    text = soup.get_text(
        "\n",
        strip=True
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return {
        "url": str(response.url),
        "title": (
            soup.title.get_text(
                " ",
                strip=True
            )
            if soup.title
            else ""
        ),
        "text": text[:18000],
    }


# ============================================================
# GITHUB API
# ============================================================

async def github_request(
    endpoint: str,
    params=None,
):

    url = (
        "https://api.github.com"
        + endpoint
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MK-AI-Agent"
    }

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers=headers,
    ) as client:

        response = await client.get(
            url,
            params=params
        )

        response.raise_for_status()

        return response.json()


async def github_search(
    query: str,
    search_type: str,
    max_results: int = 5,
):

    max_results = max(
        1,
        min(int(max_results), 10)
    )

    if search_type == "users":

        data = await github_request(
            "/search/users",
            {
                "q": query,
                "per_page": max_results,
            }
        )

    elif search_type == "issues":

        data = await github_request(
            "/search/issues",
            {
                "q": query,
                "per_page": max_results,
            }
        )

    else:

        data = await github_request(
            "/search/repositories",
            {
                "q": query,
                "per_page": max_results,
            }
        )

    return data


# ============================================================
# GITHUB USER
# ============================================================

async def github_user(
    username: str
):

    username = username.strip().lstrip("@")

    return await github_request(
        "/users/" + quote(username)
    )


# ============================================================
# GITHUB REPOSITORY
# ============================================================

async def github_repo(
    owner: str,
    repo: str
):

    owner = owner.strip()
    repo = repo.strip()

    return await github_request(
        "/repos/"
        + quote(owner)
        + "/"
        + quote(repo)
    )


# ============================================================
# DISPATCH
# ============================================================

async def execute_tool(
    name: str,
    arguments: dict,
):

    if name == "web_search":

        return await web_search(
            arguments["query"],
            arguments.get(
                "max_results",
                5
            ),
        )

    if name == "open_url":

        return await open_url(
            arguments["url"]
        )

    if name == "github_search":

        return await github_search(
            arguments["query"],
            arguments["search_type"],
            arguments.get(
                "max_results",
                5
            ),
        )

    if name == "github_user":

        return await github_user(
            arguments["username"]
        )

    if name == "github_repo":

        return await github_repo(
            arguments["owner"],
            arguments["repo"]
        )

    raise ValueError(
        f"Unknown tool: {name}"
    )
