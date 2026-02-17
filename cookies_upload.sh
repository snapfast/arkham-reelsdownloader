#!/usr/bin/env bash
set -euo pipefail

# Exports Firefox cookies to Netscape format and uploads to GCP Secret Manager.
# Run this once, and again whenever YouTube starts rejecting requests.
#
# Usage:  bash cookies_upload.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$PROJECT_DIR/config.txt"

# ── Read GCP config ──
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.txt not found"
    exit 1
fi

GCP_PROJECT="$(grep -E '^GCP_PROJECT=' "$CONFIG_FILE" | cut -d'=' -f2-)"
GCP_REGION="$(grep  -E '^GCP_REGION='  "$CONFIG_FILE" | cut -d'=' -f2-)"
GCP_SERVICE="$(grep  -E '^GCP_SERVICE=' "$CONFIG_FILE" | cut -d'=' -f2-)"
SECRET_NAME="yt-dlp-cookies"
COOKIES_MOUNT="/secrets/cookies.txt"

FIREFOX_PROFILE="$HOME/.mozilla/firefox/efyw5lcy.default-esr"
COOKIES_DB="$FIREFOX_PROFILE/cookies.sqlite"
TMP_COOKIES="$(mktemp /tmp/cookies_XXXXXX.txt)"

trap 'rm -f "$TMP_COOKIES"' EXIT

# ── Export Firefox cookies → Netscape format ──
echo "Exporting Firefox cookies..."
python3 - "$COOKIES_DB" "$TMP_COOKIES" <<'PYEOF'
import sqlite3, shutil, tempfile, sys, os

cookies_db, output_file = sys.argv[1], sys.argv[2]

# Only export cookies for sites yt-dlp needs
ALLOWED_DOMAINS = (
    "youtube.com", "youtu.be", "yt.be",
    "googlevideo.com", "google.com", "googleapis.com", "accounts.google.com",
    "instagram.com", "cdninstagram.com",
)

def is_relevant(host):
    h = host.lstrip('.')
    return any(h == d or h.endswith('.' + d) for d in ALLOWED_DOMAINS)

# Copy DB (Firefox may hold a lock)
with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
    tmp_path = tmp.name
shutil.copy2(cookies_db, tmp_path)

try:
    conn = sqlite3.connect(tmp_path)
    rows = conn.execute(
        "SELECT host, path, isSecure, expiry, name, value FROM moz_cookies"
    ).fetchall()
    conn.close()
finally:
    os.unlink(tmp_path)

import time
now = int(time.time())

filtered = [r for r in rows if is_relevant(r[0]) and r[3] > now]

with open(output_file, 'w') as f:
    f.write("# Netscape HTTP Cookie File\n")
    for host, path, is_secure, expiry, name, value in filtered:
        subdomain = "TRUE" if host.startswith('.') else "FALSE"
        secure    = "TRUE" if is_secure else "FALSE"
        f.write(f"{host}\t{subdomain}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

size_kb = os.path.getsize(output_file) / 1024
print(f"Exported {len(filtered)} / {len(rows)} cookies (non-expired, relevant domains) — {size_kb:.1f} KB")
PYEOF

# ── Upload to Secret Manager ──
echo "Uploading to GCP Secret Manager (project: $GCP_PROJECT)..."

if gcloud secrets describe "$SECRET_NAME" --project "$GCP_PROJECT" &>/dev/null; then
    # Secret exists — add a new version
    gcloud secrets versions add "$SECRET_NAME" \
        --data-file="$TMP_COOKIES" \
        --project "$GCP_PROJECT"
    echo "Updated secret '$SECRET_NAME' with new version."
else
    # First time — create the secret
    gcloud secrets create "$SECRET_NAME" \
        --data-file="$TMP_COOKIES" \
        --project "$GCP_PROJECT" \
        --replication-policy="automatic"
    echo "Created secret '$SECRET_NAME'."
fi

# ── Mount secret in Cloud Run service ──
echo "Mounting secret in Cloud Run service '$GCP_SERVICE'..."
gcloud run services update "$GCP_SERVICE" \
    --region "$GCP_REGION" \
    --project "$GCP_PROJECT" \
    --set-secrets "${COOKIES_MOUNT}=${SECRET_NAME}:latest"

echo ""
echo "Done. Cloud Run will now use cookies from Secret Manager."
