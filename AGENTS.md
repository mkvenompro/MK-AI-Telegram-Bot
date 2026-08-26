# MK-AI-Telegram-Bot - OpenCode Instructions

## Environment

This project is developed on Linux.

Primary local AI provider:

- Ollama
- Endpoint: http://127.0.0.1:11434
- Main model: qwen3:8b
- Small model: qwen3:4b

## Rules

- Work directly with the existing repository structure.
- Inspect existing files before modifying them.
- Do not delete or replace large parts of the project without checking dependencies.
- Prefer minimal, targeted changes.
- Preserve existing functionality.
- Never expose API keys, tokens, passwords, or secrets.
- Never commit `.env` files containing secrets.
- Test changes whenever practical.
- Explain important changes briefly after completing a task.

## Python

- Use the existing virtual environment when available.
- Prefer the project's existing dependencies.
- Do not add dependencies unless necessary.
- Keep scripts simple and maintainable.

## Git

Before committing:

1. Inspect `git diff`.
2. Inspect `git status`.
3. Make sure no secrets are included.
4. Make a focused commit.

Never force-push unless explicitly requested.
