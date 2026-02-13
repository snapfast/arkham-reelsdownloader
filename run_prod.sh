#!/usr/bin/env bash
set -e

# Run the FastAPI app in "prod" mode, without creating/using any virtualenv.
# Assumes all dependencies from requirements.txt are already installed.
#
# Usage:
#   chmod +x run_prod.sh   # first time only
#   ./run_prod.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Add Deno to PATH (installed into project dir during build)
if [ -d "$PROJECT_DIR/.deno/bin" ]; then
    export PATH="$PROJECT_DIR/.deno/bin:$PATH"
    echo "Deno found: $(deno --version | head -1)"
fi

# Decrypt cookies.sqlite.enc into a Firefox profile directory so
# yt-dlp --cookies-from-browser firefox can find it at runtime.
# COOKIES_KEY env var must be set in Render dashboard.
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

    echo "Firefox cookie profile ready ($(stat -c%s "$PROFILE_DIR/cookies.sqlite") bytes)"
else
    echo "No cookie decryption (COOKIES_KEY or cookies.sqlite.enc missing)"
fi

echo "Starting FastAPI server (no virtualenv)..."
exec uvicorn yt_dlp_fastapi:app --host 0.0.0.0 --port 10000

