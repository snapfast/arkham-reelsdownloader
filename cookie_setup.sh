#!/usr/bin/env bash
set -euo pipefail

# Find Firefox cookies, copy them to the project, and encrypt.
#
# Usage:
#   1. Set your key in config.txt:  COOKIES_KEY=your_secret
#   2. Run:  bash step0_cookie_setup.sh
#
# The script will auto-detect your Firefox profile and copy cookies.sqlite.
# If cookies.sqlite already exists in the project dir, it skips the copy.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

CONFIG_FILE="$PROJECT_DIR/config.txt"
INPUT_FILE="$PROJECT_DIR/cookies.sqlite"
OUTPUT_FILE="$PROJECT_DIR/cookies.sqlite.enc"

# ── Step 1: Read COOKIES_KEY from config.txt ──

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.txt not found. Create it with: COOKIES_KEY=your_secret"
    exit 1
fi

COOKIES_KEY="$(grep -E '^COOKIES_KEY=' "$CONFIG_FILE" | cut -d'=' -f2-)"
if [ -z "$COOKIES_KEY" ] || [ "$COOKIES_KEY" = "changeme" ]; then
    echo "Error: Set a real COOKIES_KEY in config.txt (not 'changeme')"
    exit 1
fi

# ── Step 2: Find and copy cookies.sqlite from Firefox profile ──

if [ -f "$INPUT_FILE" ]; then
    echo "cookies.sqlite already exists in project dir, skipping copy."
else
    echo "Searching for Firefox cookies.sqlite..."
    FOUND=""
    for BASE_DIR in "$HOME/.mozilla/firefox" "$HOME/.config/mozilla/firefox"; do
        [ -d "$BASE_DIR" ] || continue
        for PROFILE in "$BASE_DIR"/*/; do
            if [ -f "${PROFILE}cookies.sqlite" ]; then
                FOUND="${PROFILE}cookies.sqlite"
                break 2
            fi
        done
    done

    if [ -z "$FOUND" ]; then
        echo "Error: No Firefox profile with cookies.sqlite found."
        echo "Searched: ~/.mozilla/firefox/*/ and ~/.config/mozilla/firefox/*/"
        echo "You can manually copy it:  cp /path/to/cookies.sqlite ."
        exit 1
    fi

    echo "Found: $FOUND"
    cp "$FOUND" "$INPUT_FILE"
    echo "Copied to project dir."
fi

# ── Step 3: Encrypt ──

echo "Encrypting cookies.sqlite ($(stat -c%s "$INPUT_FILE") bytes)..."

openssl enc -aes-256-cbc -salt -pbkdf2 \
    -in "$INPUT_FILE" \
    -out "$OUTPUT_FILE" \
    -pass "pass:$COOKIES_KEY"

echo "Created cookies.sqlite.enc ($(stat -c%s "$OUTPUT_FILE") bytes)"
echo "You can now commit cookies.sqlite.enc and push."
echo "Set the same COOKIES_KEY in your Render dashboard environment variables."
