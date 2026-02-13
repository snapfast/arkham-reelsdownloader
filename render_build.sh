#!/usr/bin/env bash
set -euo pipefail

# Build script for Render.com
# ---------------------------
# Build Command:  bash render_build.sh
# Start Command:  ./run_prod.sh
#
# Cookie setup (one-time):
#   1. cp ~/.mozilla/firefox/<your-profile>/cookies.sqlite .
#   2. openssl enc -aes-256-cbc -salt -pbkdf2 -in cookies.sqlite -out cookies.sqlite.enc -pass pass:YOUR_SECRET
#   3. Commit cookies.sqlite.enc and push
#   4. Set COOKIES_KEY=YOUR_SECRET in Render dashboard
#   To refresh cookies: repeat steps 1-3.

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading latest yt-dlp binary..."
python3 download_yt_dlp.py

echo "Build step completed."
