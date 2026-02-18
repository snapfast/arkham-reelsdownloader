#!/usr/bin/env bash
set -euo pipefail

# Deploy to GCP Cloud Run from source (Cloud Build builds the image).
# Reads GCP_PROJECT, GCP_REGION, GCP_SERVICE from config.txt.
#
# Usage:  bash build_prod.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

CONFIG_FILE="$PROJECT_DIR/config.txt"

# ── Read GCP config ──
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.txt not found"
    exit 1
fi

GCP_PROJECT="$(grep -E '^GCP_PROJECT=' "$CONFIG_FILE" | cut -d'=' -f2-)"
GCP_REGION="$(grep -E '^GCP_REGION='  "$CONFIG_FILE" | cut -d'=' -f2-)"
GCP_SERVICE="$(grep -E '^GCP_SERVICE=' "$CONFIG_FILE" | cut -d'=' -f2-)"

if [ -z "$GCP_PROJECT" ] || [ "$GCP_PROJECT" = "your-project-id" ]; then
    echo "Error: Set GCP_PROJECT in config.txt"
    exit 1
fi

# ── Deploy from source (Cloud Build builds the image) ──
echo "Deploying $GCP_SERVICE to Cloud Run ($GCP_REGION)..."
gcloud run deploy "$GCP_SERVICE" \
    --source "$PROJECT_DIR" \
    --region "$GCP_REGION" \
    --project "$GCP_PROJECT" \
    --port 8080 \
    --allow-unauthenticated

echo ""
echo "Deploy complete. Service URL:"
gcloud run services describe "$GCP_SERVICE" \
    --region "$GCP_REGION" \
    --project "$GCP_PROJECT" \
    --format "value(status.url)"
