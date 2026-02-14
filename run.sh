#!/usr/bin/env bash
set -euo pipefail

# Unified entry point — auto-detects local vs prod (Render.com).
#
# Usage:
#   bash run.sh      # just run it — environment is detected automatically

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ──────────────────────────────────────────────
#  PROD  (Render.com sets RENDER=true)
# ──────────────────────────────────────────────
if [ "${RENDER:-}" = "true" ]; then
    echo "[prod] Detected Render.com environment"

    # Load COOKIES_KEY from config.txt if not already in env.
    if [ -z "${COOKIES_KEY:-}" ] && [ -f "$PROJECT_DIR/config.txt" ]; then
        COOKIES_KEY="$(grep -E '^COOKIES_KEY=' "$PROJECT_DIR/config.txt" | cut -d'=' -f2-)"
        [ "$COOKIES_KEY" = "changeme" ] && COOKIES_KEY=""
    fi

    # Decrypt cookies into a Firefox profile directory.
    if [ -n "${COOKIES_KEY:-}" ] && [ -f "$PROJECT_DIR/cookies.sqlite.enc" ]; then
        PROFILE_DIR="$HOME/.mozilla/firefox/render.default"
        mkdir -p "$PROFILE_DIR"

        openssl enc -aes-256-cbc -d -salt -pbkdf2 \
            -in "$PROJECT_DIR/cookies.sqlite.enc" \
            -out "$PROFILE_DIR/cookies.sqlite" \
            -pass "pass:$COOKIES_KEY"

        cat > "$HOME/.mozilla/firefox/profiles.ini" <<'PROFILES'
[General]
StartWithLastProfile=1
Version=2

[Profile0]
Name=default
IsRelative=1
Path=render.default
Default=1
PROFILES

        echo "[prod] Firefox cookie profile ready ($(stat -c%s "$PROFILE_DIR/cookies.sqlite") bytes)"
    else
        echo "[prod] No cookie decryption (COOKIES_KEY or cookies.sqlite.enc missing)"
    fi

    echo "[prod] Starting server..."
    exec uvicorn app:app --host 0.0.0.0 --port 10000

# ──────────────────────────────────────────────
#  LOCAL
# ──────────────────────────────────────────────
else
    echo "[local] Setting up local environment"

    VENV_DIR="$PROJECT_DIR/.venv"

    if [ ! -d "$VENV_DIR" ]; then
        echo "[local] Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    echo "[local] Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    echo "[local] Installing requirements..."
    pip install --upgrade pip
    pip install -r requirements.txt

    # Download yt-dlp binary if missing.
    if [ ! -f "$PROJECT_DIR/yt-dlp_linux" ]; then
        echo "[local] Downloading yt-dlp binary..."
        python3 download_ytdlp.py
    fi

    # Encrypt cookies from local Firefox profile.
    echo "[local] Encrypting cookies from Firefox profile..."
    bash "$PROJECT_DIR/encrypt_cookies.sh"

    echo "[local] Starting server (with reload)..."
    python3 app.py
fi
