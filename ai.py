import httpx

from config import (
    AI_API_URL,
    AI_API_KEY,
    AI_MODEL,
    MAX_MESSAGE_LENGTH,
)

SYSTEM_PROMPT = """
You are MK AI, a helpful Telegram assistant.

You can speak Egyptian Arabic, Arabic or English.

You are running through an OpenCode server.
Use the capabilities/tools available to you when appropriate.
If web access or another tool is available, use it instead of
pretending that you know current information.

Never claim that you performed an action unless you actually did it.

Answer naturally and clearly.
For Android, ROM development, Linux, GitHub, programming and
technical questions, give practical and technically accurate answers.
"""


async def ask_ai(history):

    if not AI_API_URL:
        raise RuntimeError("OPENCODE_URL / AI_API_URL is missing")

    # --------------------------------------------------------
    # OpenCode Server:
    #
    # POST /session
    # POST /session/:id/message
    #
    # We create a temporary session for every request.
    # The Telegram bot already handles conversation memory.
    # --------------------------------------------------------

    base_url = AI_API_URL.rstrip("/")

    headers = {
        "Content-Type": "application/json",
    }

    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=30,
            read=180,
            write=30,
            pool=30,
        )
    ) as client:

        # Create OpenCode session
        session_response = await client.post(
            f"{base_url}/session",
            headers=headers,
            json={
                "title": "MK AI Telegram"
            },
        )

        if session_response.status_code >= 400:
            body = session_response.text[:4000]
            print(
                f"OpenCode session HTTP "
                f"{session_response.status_code}"
            )
            print(body)

            raise RuntimeError(
                f"OpenCode session failed: "
                f"HTTP {session_response.status_code}: {body}"
            )

        session_data = session_response.json()

        session_id = session_data.get("id")

        if not session_id:
            raise RuntimeError(
                "OpenCode did not return a session ID: "
                + str(session_data)
            )

        # ----------------------------------------------------
        # Convert Telegram history into one OpenCode prompt.
        # ----------------------------------------------------

        conversation = []

        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")

            if role == "system":
                conversation.append(
                    f"SYSTEM:\n{content}"
                )
            elif role == "assistant":
                conversation.append(
                    f"ASSISTANT:\n{content}"
                )
            else:
                conversation.append(
                    f"USER:\n{content}"
                )

        prompt = (
            SYSTEM_PROMPT.strip()
            + "\n\n"
            + "\n\n".join(conversation)
            + "\n\nASSISTANT:"
        )

        # ----------------------------------------------------
        # Ask OpenCode.
        #
        # model is optional. If AI_MODEL is empty, OpenCode
        # uses its configured default model.
        # ----------------------------------------------------

        message_payload = {
            "parts": [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
        }

        if AI_MODEL:
            message_payload["model"] = {
                "providerID": AI_MODEL.split("/", 1)[0],
                "modelID": (
                    AI_MODEL.split("/", 1)[1]
                    if "/" in AI_MODEL
                    else AI_MODEL
                ),
            }

        response = await client.post(
            f"{base_url}/session/{session_id}/message",
            headers=headers,
            json=message_payload,
        )

        if response.status_code >= 400:
            body = response.text[:4000]

            print(
                f"OpenCode message HTTP "
                f"{response.status_code}"
            )
            print(body)

            raise RuntimeError(
                f"OpenCode returned HTTP "
                f"{response.status_code}: {body}"
            )

        data = response.json()

    # --------------------------------------------------------
    # Extract assistant text from OpenCode parts.
    # --------------------------------------------------------

    answer_parts = []

    for part in data.get("parts", []):
        if part.get("type") == "text":
            text = part.get("text")

            if text:
                answer_parts.append(text)

    answer = "\n".join(answer_parts).strip()

    if not answer:
        raise RuntimeError(
            "OpenCode returned no text response: "
            + str(data)[:4000]
        )

    return answer[:MAX_MESSAGE_LENGTH]
