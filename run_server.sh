#!/usr/bin/env bash
set -e

# Simple helper to:
# 1. Create/activate a virtualenv
# 2. Install requirements
# 3. Run the FastAPI server

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"

echo "Using project directory: $PROJECT_DIR"
echo "Virtualenv directory: $VENV_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting FastAPI server (yt_dlp_fastapi.py)..."
python3 yt_dlp_fastapi.py

