#!/usr/bin/env bash
set -euo pipefail

# Build script for Render.com
# ---------------------------
# Use this as your "Build Command" on Render.
#
# It will:
#   1. Install Python dependencies
#   2. Download the latest yt-dlp binary into the project directory
#
# Example Render configuration:
#   Build Command:  bash render_build.sh
#   Start Command:  uvicorn yt_dlp_fastapi:app --host 0.0.0.0 --port 8000

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading latest yt-dlp binary..."
python3 download_yt_dlp.py

echo "Build step completed."

