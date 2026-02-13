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

echo "Starting FastAPI server (no virtualenv)..."
exec uvicorn yt_dlp_fastapi:app --host 0.0.0.0 --port 10000

