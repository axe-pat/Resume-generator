#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAD_USER_DATA_DIR="$ROOT/playwright/chrome-data"
USER_DATA_DIR="${LINKEDIN_CHROME_USER_DATA_DIR:-}"
PROFILE_NAME="${LINKEDIN_PROFILE_NAME:-}"
DEBUG_PORT="${LINKEDIN_DEBUG_PORT:-9222}"
TARGET_URL="${1:-https://www.linkedin.com/feed/}"
OWNER_TOKEN="${RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN:-}"

if [[ -z "${USER_DATA_DIR}" ]]; then
  cat <<'EOF' >&2
ERROR: LINKEDIN_CHROME_USER_DATA_DIR is not set.

This launcher only works with an explicitly approved persistent Chrome profile.
Use an absolute path to the signed-in profile you want discovery to reuse.

Example:
  export LINKEDIN_CHROME_USER_DATA_DIR="/absolute/path/to/your/signed-in/chrome-data"
  export LINKEDIN_PROFILE_NAME="Default"
  ./discovery/scripts/launch_linkedin_browser.sh
EOF
  exit 1
fi

if [[ -z "${PROFILE_NAME}" ]]; then
  cat <<'EOF' >&2
ERROR: LINKEDIN_PROFILE_NAME is not set.

Set it to the exact Chrome subprofile directory, for example:
  export LINKEDIN_PROFILE_NAME="Default"
EOF
  exit 1
fi

if [[ "${PROFILE_NAME}" == "." || "${PROFILE_NAME}" == ".." || "${PROFILE_NAME}" == *"/"* ]]; then
  echo "ERROR: LINKEDIN_PROFILE_NAME must be a Chrome subprofile directory name, not a path." >&2
  exit 1
fi

if [[ "${USER_DATA_DIR}" != /* ]]; then
  cat <<EOF >&2
ERROR: LINKEDIN_CHROME_USER_DATA_DIR must be an absolute path.
Current value:
  ${USER_DATA_DIR}
EOF
  exit 1
fi

if [[ "${USER_DATA_DIR}" == "${BAD_USER_DATA_DIR}" ]]; then
  cat <<EOF >&2
ERROR: Refusing to use the unsigned fallback profile:
  ${BAD_USER_DATA_DIR}
EOF
  exit 1
fi

if [[ ! -d "${USER_DATA_DIR}" ]]; then
  cat <<EOF >&2
ERROR: Chrome user-data-dir does not exist:
  ${USER_DATA_DIR}
EOF
  exit 1
fi

CHROME_ARGS=(
  "--user-data-dir=${USER_DATA_DIR}"
  "--profile-directory=${PROFILE_NAME}"
  "--remote-debugging-port=${DEBUG_PORT}"
  "--enable-automation"
  "--disable-extensions"
)
if [[ -n "${OWNER_TOKEN}" ]]; then
  if [[ ! "${OWNER_TOKEN}" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "ERROR: Invalid RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN." >&2
    exit 2
  fi
  # The opaque switch is only an ownership marker in the local process table.
  # Chrome ignores it; terminal cleanup requires the exact token before kill.
  CHROME_ARGS+=("--resume-generator-browser-owner=${OWNER_TOKEN}")
fi
CHROME_ARGS+=("${TARGET_URL}")

open -na "Google Chrome" --args "${CHROME_ARGS[@]}"
