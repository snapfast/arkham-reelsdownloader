#!/usr/bin/env bash
set -euo pipefail

# Encrypt cookies.sqlite from the local Firefox profile.
# Reads COOKIES_KEY from config.txt.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="$PROJECT_DIR/config.txt"
FIREFOX_COOKIES="$HOME/.mozilla/firefox/efyw5lcy.default-esr/cookies.sqlite"
OUTPUT_FILE="$PROJECT_DIR/cookies.sqlite.enc"

# Read key from config.txt
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.txt not found. Create it with: COOKIES_KEY=your_secret"
    exit 1
fi
COOKIES_KEY="$(grep -E '^COOKIES_KEY=' "$CONFIG_FILE" | cut -d'=' -f2-)"
if [ -z "$COOKIES_KEY" ] || [ "$COOKIES_KEY" = "changeme" ]; then
    echo "Error: Set a real COOKIES_KEY in config.txt"
    exit 1
fi

# Check Firefox cookies exist
if [ ! -f "$FIREFOX_COOKIES" ]; then
    echo "Error: $FIREFOX_COOKIES not found"
    exit 1
fi

echo "Encrypting $(stat -c%s "$FIREFOX_COOKIES") bytes from Firefox profile..."
openssl enc -aes-256-cbc -salt -pbkdf2 \
    -in "$FIREFOX_COOKIES" \
    -out "$OUTPUT_FILE" \
    -pass "pass:$COOKIES_KEY"

echo "Created cookies.sqlite.enc ($(stat -c%s "$OUTPUT_FILE") bytes)"
