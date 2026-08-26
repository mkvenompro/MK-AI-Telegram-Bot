# MK AI Telegram Bot

Open Source Telegram AI Bot written in Python.

## Features

- Telegram groups
- Mention based replies
- Private chat support
- Conversation memory
- /start
- /help
- /reset
- Async AI requests
- Docker support

## Installation

```bash
pip install -r requirements.txt
```

Create .env:

```text
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_TOKEN
AI_API_KEY=YOUR_AI_API_KEY
```

Run:

```bash
python bot.py
```

## Telegram

Add the bot to your group.

Mention it:

```text
@YourBot hello
```

## Security

Never publish your Telegram Bot Token or AI API key.

## OpenCode Server

The bot can use an OpenCode HTTP server as its AI backend.

Required GitHub Secrets:

- `BOT_TOKEN`
- `OPENCODE_URL`
- `OPENCODE_API_KEY` (only if the OpenCode server requires authentication)

Optional repository variable:

- `OPENCODE_MODEL`

Example:

`OPENCODE_URL=https://your-opencode-server.example.com`

The Telegram bot keeps its own conversation memory.
OpenCode is used as the AI/agent backend.
