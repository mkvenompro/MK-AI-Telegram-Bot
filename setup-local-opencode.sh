#!/usr/bin/env bash
set -e

REPO="$(pwd)"

echo "======================================"
echo " MK-AI-Telegram-Bot"
echo " Local OpenCode + Ollama Setup"
echo "======================================"

# --------------------------------------
# 1. Verify Git repository
# --------------------------------------
if [ ! -d ".git" ]; then
    echo "[ERROR] This is not a Git repository."
    exit 1
fi

# --------------------------------------
# 2. Verify Ollama
# --------------------------------------
echo
echo "[1/7] Checking Ollama..."

if ! command -v ollama >/dev/null 2>&1; then
    echo "[ERROR] Ollama is not installed."
    exit 1
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "[ERROR] Ollama API is not responding."
    echo "Run:"
    echo "  sudo systemctl start ollama"
    exit 1
fi

echo "[OK] Ollama is running."

# --------------------------------------
# 3. Verify Qwen3 8B
# --------------------------------------
echo
echo "[2/7] Checking qwen3:8b..."

if ! ollama list | awk '{print $1}' | grep -qx 'qwen3:8b'; then
    echo "[INFO] qwen3:8b is not installed."
    echo "[INFO] Pulling qwen3:8b..."
    ollama pull qwen3:8b
fi

echo "[OK] qwen3:8b is available."

# --------------------------------------
# 4. Create OpenCode config
# --------------------------------------
echo
echo "[3/7] Creating opencode.json..."

cat > "$REPO/opencode.json" <<'JSON'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "ollama/qwen3:8b",
  "small_model": "ollama/qwen3:4b"
}
JSON

echo "[OK] opencode.json created."

# --------------------------------------
# 5. Create local development instructions
# --------------------------------------
echo
echo "[4/7] Creating OpenCode instructions..."

cat > "$REPO/AGENTS.md" <<'EOF'
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
EOF

echo "[OK] AGENTS.md created."

# --------------------------------------
# 6. Add useful Git ignores
# --------------------------------------
echo
echo "[5/7] Updating .gitignore..."

touch .gitignore

add_ignore() {
    local line="$1"

    if ! grep -Fxq "$line" .gitignore 2>/dev/null; then
        echo "$line" >> .gitignore
    fi
}

add_ignore ".env"
add_ignore ".env.*"
add_ignore "!.env.example"
add_ignore "__pycache__/"
add_ignore "*.pyc"
add_ignore ".venv/"
add_ignore "venv/"
add_ignore ".pytest_cache/"
add_ignore ".mypy_cache/"
add_ignore ".ruff_cache/"

echo "[OK] .gitignore updated."

# --------------------------------------
# 7. Git status / commit / push
# --------------------------------------
echo
echo "[6/7] Checking Git changes..."

git status --short

echo
echo "[7/7] Committing configuration..."

git add opencode.json AGENTS.md .gitignore

if git diff --cached --quiet; then
    echo "[INFO] No new configuration changes to commit."
else
    git commit -m "chore: configure local OpenCode with Ollama"
fi

echo
echo "======================================"
echo " Git remote"
echo "======================================"

git remote -v

echo
echo "======================================"
echo " Pushing changes"
echo "======================================"

BRANCH="$(git branch --show-current)"

if [ -z "$BRANCH" ]; then
    echo "[ERROR] Could not determine current branch."
    exit 1
fi

git push origin "$BRANCH"

echo
echo "======================================"
echo " DONE"
echo "======================================"

echo
echo "OpenCode model:"
echo "  ollama/qwen3:8b"

echo
echo "Run:"
echo "  opencode"

echo
echo "Or explicitly:"
echo "  opencode --model ollama/qwen3:8b"

echo
echo "Branch pushed:"
echo "  $BRANCH"
