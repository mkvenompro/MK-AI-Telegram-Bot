import json
import os
from typing import Optional

import httpx

from tools import TOOLS, execute_tool


LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080"
).strip().rstrip("/")

MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-4B"
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
        "0.35"
    )
)

TIMEOUT = float(
    os.getenv(
        "AI_TIMEOUT",
        "120"
    )
)

MAX_TOOL_ROUNDS = int(
    os.getenv(
        "AI_MAX_TOOL_ROUNDS",
        "5"
    )
)


SYSTEM_PROMPT = """
أنت Spider AI Assistant داخل Telegram.

أنت Agent حقيقي ولديك أدوات خارجية.

الأدوات المتاحة لك:

1. web_search
للبحث في الإنترنت.

2. open_url
لفتح وقراءة صفحات الإنترنت.

3. github_search
للبحث في GitHub.

4. github_user
لجلب بيانات GitHub العامة لمستخدم.

5. github_repo
لجلب بيانات GitHub العامة لمستودع.

قواعد الأدوات:

- إذا قال المستخدم "ابحث في الويب" استخدم web_search.
- إذا قال "ابحث في GitHub" استخدم github_search.
- إذا طلب البحث عن شخص أو مشروع، استخدم الأدوات المناسبة.
- لو السؤال يحتاج Web + GitHub استخدم الاثنين.
- لا تقل إنك لا تستطيع تصفح الإنترنت طالما الأداة متاحة.
- بعد استخدام الأدوات، حلل النتائج وأجب المستخدم.
- لا تخبر المستخدم عن reasoning الداخلي.
- لا تعرض reasoning_content.
- لا تخترع نتائج لم تحصل عليها من الأدوات.
- إذا فشل Tool، وضح ذلك باختصار وحاول Tool آخر إذا كان مناسباً.

أسلوب الرد:

- العربية عند الكلام بالعربية.
- اللهجة المصرية بشكل طبيعي.
- محترم دائماً.
- لا تقل Okay أو Let me check.
- لا تكرر السؤال.
- الإجابة النهائية مباشرة.
- في الأسئلة البسيطة كن مختصراً.
""".strip()


async def llama_request(
    messages,
    tools=True,
):

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "top_p": 0.8,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }

    if tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"

    timeout = httpx.Timeout(
        connect=5.0,
        read=TIMEOUT,
        write=15.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:

        response = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
        )

        response.raise_for_status()

        return response.json()


def clean_answer(
    content: str
):

    if not content:
        return ""

    content = str(content).strip()

    if "<think>" in content:

        if "</think>" in content:

            content = content.split(
                "</think>",
                1
            )[1].strip()

        else:

            content = ""

    return content.strip()


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

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    if history:

        for msg in history[-8:]:

            if not isinstance(msg, dict):
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

            content = clean_answer(
                content
            )

            if not content:
                continue

            messages.append({
                "role": role,
                "content": content,
            })

    messages.append({
        "role": "user",
        "content": prompt,
    })

    # --------------------------------------------------------
    # AGENT LOOP
    # --------------------------------------------------------

    for round_number in range(
        MAX_TOOL_ROUNDS
    ):

        try:

            data = await llama_request(
                messages,
                tools=True,
            )

        except Exception as error:

            print(
                "[LLAMA ERROR]",
                repr(error),
                flush=True,
            )

            return (
                "❌ حصل خطأ في الـAI. "
                "جرب تاني بعد شوية."
            )

        choices = (
            data.get("choices")
            or []
        )

        if not choices:

            return (
                "❌ الـAI رجّع نتيجة فاضية."
            )

        message = (
            choices[0].get("message")
            or {}
        )

        content = message.get(
            "content",
            ""
        )

        tool_calls = (
            message.get(
                "tool_calls"
            )
            or []
        )

        # ----------------------------------------------------
        # NO TOOL CALL
        # ----------------------------------------------------

        if not tool_calls:

            answer = clean_answer(
                content
            )

            if answer:

                return answer

            # Sometimes model can return
            # reasoning only. Ask for final answer.
            messages.append({
                "role": "assistant",
                "content": (
                    "أعطِ الإجابة النهائية فقط "
                    "بدون reasoning."
                ),
            })

            continue

        # ----------------------------------------------------
        # ASSISTANT TOOL MESSAGE
        # ----------------------------------------------------

        assistant_message = {
            "role": "assistant",
            "content": content or "",
            "tool_calls": tool_calls,
        }

        messages.append(
            assistant_message
        )

        # ----------------------------------------------------
        # EXECUTE TOOLS
        # ----------------------------------------------------

        for tool_call in tool_calls:

            function = (
                tool_call.get(
                    "function"
                )
                or {}
            )

            name = function.get(
                "name"
            )

            raw_arguments = (
                function.get(
                    "arguments",
                    "{}"
                )
            )

            try:

                if isinstance(
                    raw_arguments,
                    str
                ):

                    arguments = json.loads(
                        raw_arguments
                    )

                else:

                    arguments = raw_arguments

            except Exception as error:

                result = {
                    "error": (
                        "Invalid tool arguments: "
                        + repr(error)
                    )
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get(
                        "id",
                        ""
                    ),
                    "content": json.dumps(
                        result,
                        ensure_ascii=False
                    ),
                })

                continue

            print(
                "[TOOL]",
                name,
                arguments,
                flush=True,
            )

            try:

                result = await execute_tool(
                    name,
                    arguments,
                )

            except Exception as error:

                result = {
                    "error": str(error)
                }

            result_text = json.dumps(
                result,
                ensure_ascii=False
            )

            # Avoid huge context
            if len(result_text) > 24000:
                result_text = (
                    result_text[:24000]
                    + "\n...[truncated]"
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get(
                    "id",
                    ""
                ),
                "content": result_text,
            })

    return (
        "❌ وصلت للحد الأقصى من عمليات البحث "
        "في نفس الطلب. جرّب السؤال بشكل أبسط."
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
        "model": MODEL,
        "url": LLAMA_URL,
        "thinking": True,
        "tools": [
            "web_search",
            "open_url",
            "github_search",
            "github_user",
            "github_repo",
        ],
    }
