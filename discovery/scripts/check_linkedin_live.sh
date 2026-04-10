#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/.."

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
DEBUG_PORT="${LINKEDIN_DEBUG_PORT:-9222}"
BAD_PROFILE_PATH="$ROOT/playwright/chrome-data"

if ! command -v lsof >/dev/null 2>&1; then
  echo "ERROR: lsof is required to verify the Chrome debug owner." >&2
  exit 1
fi

LISTENER_LINE="$(lsof -nP -iTCP:${DEBUG_PORT} -sTCP:LISTEN | awk 'NR==2 {print}')"
if [[ -z "${LISTENER_LINE}" ]]; then
  echo "ERROR: Nothing is listening on 127.0.0.1:${DEBUG_PORT}." >&2
  exit 1
fi

LISTENER_PID="$(awk 'NR==2 {print $2}' <<<"$(lsof -nP -iTCP:${DEBUG_PORT} -sTCP:LISTEN)")"
LISTENER_CMD="$(ps -p "${LISTENER_PID}" -o command= 2>/dev/null || true)"

echo "CDP owner (${DEBUG_PORT}): ${LISTENER_CMD}"

if [[ "${LISTENER_CMD}" == *"${BAD_PROFILE_PATH}"* ]]; then
  cat <<EOF >&2
ERROR: Refusing to proceed because port ${DEBUG_PORT} is owned by the forbidden unsigned profile:
  ${BAD_PROFILE_PATH}
EOF
  exit 1
fi

"$PYTHON_BIN" discovery/auto/check_linkedin_live.py "$@"
