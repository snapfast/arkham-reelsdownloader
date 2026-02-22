#!/usr/bin/env bash
# Runs cookies_upload.sh every 10 minutes in a loop.
# Usage:  bash cookies_loop.sh
#         bash cookies_loop.sh &   # run in background; kill %1 to stop

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPLOAD_SCRIPT="$SCRIPT_DIR/cookies_upload.sh"
INTERVAL=$((15 * 60))  # 900 seconds

if [ ! -f "$UPLOAD_SCRIPT" ]; then
    echo "Error: cookies_upload.sh not found at $UPLOAD_SCRIPT"
    exit 1
fi

echo "Starting cookie refresh loop (every 15 minutes). Press Ctrl+C to stop."

while true; do
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running cookies_upload.sh..."
    bash "$UPLOAD_SCRIPT" && echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done." \
                          || echo "[$(date '+%Y-%m-%d %H:%M:%S')] Upload failed (exit $?)."
    echo "Next run in 15 minutes..."
    sleep "$INTERVAL"
done
