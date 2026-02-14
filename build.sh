#!/usr/bin/env bash
set -euo pipefail

# Build script for Render.com
# ---------------------------
# Build Command:  bash build.sh
# Start Command:  ./run.sh
#
# Cookie setup (one-time):
#   1. Set your key in config.txt:  COOKIES_KEY=your_secret
#   2. bash encrypt_cookies.sh   (encrypts from local Firefox profile)
#   3. Commit cookies.sqlite.enc and push
#   4. Set the same COOKIES_KEY in Render dashboard env vars
#   To refresh cookies: repeat steps 2-3.

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading latest yt-dlp binary..."
python3 download_ytdlp.py

echo "Build step completed."
