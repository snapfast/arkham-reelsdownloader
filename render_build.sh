#!/usr/bin/env bash
set -euo pipefail

# Build script for Render.com
# ---------------------------
# Use this as your "Build Command" on Render.
#
# It will:
#   1. Install Firefox browser and open YouTube (via setup_firefox_youtube.py)
#   2. Install Python dependencies
#   3. Download the latest yt-dlp binary into the project directory
#
# Example Render configuration:
#   Build Command:  bash render_build.sh
#   Start Command:  uvicorn yt_dlp_fastapi:app --host 0.0.0.0 --port 8000

echo "Installing Deno (JS runtime required by yt-dlp for YouTube)..."
# Install Deno into the project directory so it persists at runtime on Render
# (Render only preserves the project dir between build and runtime)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DENO_INSTALL="$SCRIPT_DIR/.deno"
curl -fsSL https://deno.land/install.sh | sh
export PATH="$DENO_INSTALL/bin:$PATH"
deno --version

echo "Setting up Firefox and opening YouTube..."
python3 setup_firefox_youtube.py || echo "Firefox setup had issues, continuing anyway..."

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading latest yt-dlp binary..."
python3 download_yt_dlp.py

echo "Build step completed."

