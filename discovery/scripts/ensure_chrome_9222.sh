#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DEBUG_PORT="${LINKEDIN_DEBUG_PORT:-9222}"
TARGET_URL="${1:-https://www.linkedin.com/feed/}"

if ! lsof -nP -iTCP:${DEBUG_PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  ./discovery/scripts/launch_linkedin_browser.sh "$TARGET_URL"
  sleep "${LINKEDIN_BROWSER_LAUNCH_WAIT:-5}"
fi

./discovery/scripts/check_linkedin_live.sh
