#!/usr/bin/env bash
set -euo pipefail

# Run locally using Docker (mirrors the Cloud Run environment).
# Usage:  bash run.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

IMAGE="reels-downloader-local"
PORT=8080

echo "[local] Building Docker image..."
docker build -t "$IMAGE" "$PROJECT_DIR"

echo "[local] Starting container on http://localhost:$PORT ..."
docker run --rm \
    -p "$PORT:$PORT" \
    -e PORT="$PORT" \
    "$IMAGE"
