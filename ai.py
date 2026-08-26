import httpx

from config import (
    AI_API_URL,
    AI_API_KEY,
    AI_MODEL,
    MAX_MESSAGE_LENGTH,
)

SYSTEM_PROMPT = "You are MK AI, a helpful Telegram assistant. Answer naturally and clearly. You can speak Egyptian Arabic, Arabic or English. Give practical answers for Android, ROM, Linux, GitHub and programming. Never pretend you performed an action you did not perform."

async def ask_ai(history):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    messages.extend(history)

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1200,
    }

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            AI_API_URL,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()
        data = response.json()

    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Invalid AI response: " + str(data))

    if not answer:
        return "مش عارف أطلع رد دلوقتي 😅"

    return answer[:MAX_MESSAGE_LENGTH]