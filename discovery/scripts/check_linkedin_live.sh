#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/.."

INHERITED_USER_DATA_DIR="${LINKEDIN_CHROME_USER_DATA_DIR:-}"
INHERITED_PROFILE_NAME="${LINKEDIN_PROFILE_NAME:-}"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -n "${INHERITED_USER_DATA_DIR}" ]]; then
  LINKEDIN_CHROME_USER_DATA_DIR="${INHERITED_USER_DATA_DIR}"
fi
if [[ -n "${INHERITED_PROFILE_NAME}" ]]; then
  LINKEDIN_PROFILE_NAME="${INHERITED_PROFILE_NAME}"
fi

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
DEBUG_PORT="${LINKEDIN_DEBUG_PORT:-9222}"
BAD_PROFILE_PATH="$ROOT/playwright/chrome-data"
EXPECTED_USER_DATA_DIR="${LINKEDIN_CHROME_USER_DATA_DIR:-}"
EXPECTED_PROFILE_NAME="${LINKEDIN_PROFILE_NAME:-}"

if [[ -z "${EXPECTED_USER_DATA_DIR}" || -z "${EXPECTED_PROFILE_NAME}" ]]; then
  echo "ERROR: LINKEDIN_CHROME_USER_DATA_DIR and LINKEDIN_PROFILE_NAME must both be configured." >&2
  exit 1
fi

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

if [[ "${LISTENER_CMD}" != *"--remote-debugging-port"* ]]; then
  cat <<EOF >&2
ERROR: Port ${DEBUG_PORT} is not owned by a Chrome process launched with remote debugging enabled.
EOF
  exit 1
fi

if [[ "${LISTENER_CMD}" == *"${BAD_PROFILE_PATH}"* ]]; then
  cat <<EOF >&2
ERROR: Refusing to proceed because port ${DEBUG_PORT} is owned by the forbidden unsigned profile:
  ${BAD_PROFILE_PATH}
EOF
  exit 1
fi

if [[ "${LISTENER_CMD}" != *"--user-data-dir=${EXPECTED_USER_DATA_DIR}"* ]]; then
  cat <<EOF >&2
ERROR: CDP owner is using the wrong Chrome user-data directory.
Expected:
  ${EXPECTED_USER_DATA_DIR}
EOF
  exit 1
fi

if [[ "${LISTENER_CMD}" != *"--profile-directory=${EXPECTED_PROFILE_NAME}"* ]]; then
  cat <<EOF >&2
ERROR: CDP owner is using the wrong Chrome subprofile.
Expected:
  ${EXPECTED_PROFILE_NAME}
EOF
  exit 1
fi

"$PYTHON_BIN" discovery/auto/check_linkedin_live.py "$@"
