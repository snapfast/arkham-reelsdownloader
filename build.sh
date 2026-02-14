#!/usr/bin/env bash
set -euo pipefail

# Build script for Render.com
# ---------------------------
# Build Command:  bash build.sh
# Start Command:  ./run.sh
#
# Cookie setup (one-time):
#   1. cp ~/.mozilla/firefox/<your-profile>/cookies.sqlite .
#   2. Set your key in config.txt:  COOKIES_KEY=your_secret
#   3. bash cookie_setup.sh
#   4. Commit cookies.sqlite.enc and push
#   5. Set the same COOKIES_KEY in Render dashboard env vars
#   To refresh cookies: repeat steps 1, 3-4.

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading latest yt-dlp binary..."
python3 download_ytdlp.py

echo "Build step completed."
