#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

INHERITED_OWNER_TOKEN="${RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN:-}"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -n "${INHERITED_OWNER_TOKEN}" ]]; then
  # A repo-local .env must never replace the exact invocation's ownership token.
  export RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN="${INHERITED_OWNER_TOKEN}"
else
  unset RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN || true
fi

DEBUG_PORT="${LINKEDIN_DEBUG_PORT:-9222}"
TARGET_URL="${1:-https://www.linkedin.com/feed/}"
OWNER_TOKEN="${RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN:-}"
USER_DATA_DIR="${LINKEDIN_CHROME_USER_DATA_DIR:-}"
PROFILE_NAME="${LINKEDIN_PROFILE_NAME:-}"
CHROME_BINARY="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ -n "${OWNER_TOKEN}" && ! "${OWNER_TOKEN}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: Invalid RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN." >&2
  exit 2
fi

listener_pid() {
  lsof -tiTCP:"${DEBUG_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

listener_command() {
  local pid="$1"
  ps -p "${pid}" -o command= 2>/dev/null || true
}

command_owner_token() {
  local command="$1"
  local marker="--resume-generator-browser-owner="
  if [[ "${command}" != *"${marker}"* ]]; then
    return 0
  fi
  local suffix="${command#*${marker}}"
  printf '%s' "${suffix%% *}"
}

sound_owned_chrome() {
  local command="$1"
  local expected_token="$2"
  local command_token
  command_token="$(command_owner_token "${command}")"
  [[ "${command}" == "${CHROME_BINARY}"* ]] &&
    [[ -n "${USER_DATA_DIR}" ]] &&
    [[ -n "${PROFILE_NAME}" ]] &&
    [[ "${command}" == *"--user-data-dir=${USER_DATA_DIR}"* ]] &&
    [[ "${command}" == *"--profile-directory=${PROFILE_NAME}"* ]] &&
    [[ "${command}" == *"--remote-debugging-port=${DEBUG_PORT}"* ]] &&
    [[ "${command_token}" == "${expected_token}" ]]
}

close_stale_owned_chrome() {
  local stale_pid="$1"
  local stale_command="$2"
  local stale_token="$3"
  if ! sound_owned_chrome "${stale_command}" "${stale_token}"; then
    echo "ERROR: Refusing to terminate an unsound or unrelated CDP listener on ${DEBUG_PORT}." >&2
    return 1
  fi
  local current_pid current_command
  current_pid="$(listener_pid)"
  current_command="$(listener_command "${current_pid}")"
  if [[ "${current_pid}" != "${stale_pid}" ]] ||
    [[ "${current_command}" != "${stale_command}" ]] ||
    ! sound_owned_chrome "${current_command}" "${stale_token}"; then
    echo "ERROR: Stale CDP listener changed identity before cleanup." >&2
    return 1
  fi
  echo "Closing stale ResumeGenerator-owned LinkedIn Chrome pid=${stale_pid}." >&2
  kill -TERM "${stale_pid}" 2>/dev/null || true
  for _ in $(seq 1 40); do
    current_pid="$(listener_pid)"
    if [[ -z "${current_pid}" ]]; then
      return 0
    fi
    if [[ "${current_pid}" != "${stale_pid}" ]]; then
      echo "ERROR: CDP port ${DEBUG_PORT} changed owners during stale-session cleanup." >&2
      return 1
    fi
    sleep 0.25
  done
  local final_command
  final_command="$(listener_command "${stale_pid}")"
  if ! sound_owned_chrome "${final_command}" "${stale_token}"; then
    echo "ERROR: Stale CDP listener changed identity before forced cleanup." >&2
    return 1
  fi
  kill -KILL "${stale_pid}" 2>/dev/null || true
  sleep 0.25
  if [[ -n "$(listener_pid)" ]]; then
    echo "ERROR: Stale ResumeGenerator-owned Chrome still holds ${DEBUG_PORT}." >&2
    return 1
  fi
}

launch_browser() {
  ./discovery/scripts/launch_linkedin_browser.sh "$TARGET_URL"
  sleep "${LINKEDIN_BROWSER_LAUNCH_WAIT:-5}"
}

PID="$(listener_pid)"
if [[ -n "${OWNER_TOKEN}" ]]; then
  if [[ -n "${PID}" ]]; then
    LISTENER_CMD="$(listener_command "${PID}")"
    LISTENER_OWNER_TOKEN="$(command_owner_token "${LISTENER_CMD}")"
    if [[ "${LISTENER_OWNER_TOKEN}" == "${OWNER_TOKEN}" ]]; then
      if ! sound_owned_chrome "${LISTENER_CMD}" "${OWNER_TOKEN}"; then
        echo "ERROR: Current-token CDP listener failed canonical Chrome/profile validation." >&2
        exit 1
      fi
    elif [[ -n "${LISTENER_OWNER_TOKEN}" ]]; then
      close_stale_owned_chrome \
        "${PID}" "${LISTENER_CMD}" "${LISTENER_OWNER_TOKEN}"
      launch_browser
    else
      echo "ERROR: Refusing to reuse unowned CDP listener pid=${PID} on ${DEBUG_PORT}." >&2
      exit 1
    fi
  else
    launch_browser
  fi

  PID="$(listener_pid)"
  LISTENER_CMD="$(listener_command "${PID}")"
  if [[ -z "${PID}" ]] || ! sound_owned_chrome "${LISTENER_CMD}" "${OWNER_TOKEN}"; then
    echo "ERROR: Nightly Chrome did not acquire ${DEBUG_PORT} with the current owner token." >&2
    exit 1
  fi
elif [[ -z "${PID}" ]]; then
  launch_browser
fi

attempts="${LINKEDIN_BROWSER_CHECK_ATTEMPTS:-4}"
delay="${LINKEDIN_BROWSER_CHECK_RETRY_DELAY:-5}"
if [[ ! "${attempts}" =~ ^[1-9][0-9]*$ ]]; then
  echo "LINKEDIN_BROWSER_CHECK_ATTEMPTS must be an integer >= 1" >&2
  exit 2
fi
last_status=0
for attempt in $(seq 1 "${attempts}"); do
  if ./discovery/scripts/check_linkedin_live.sh; then
    exit 0
  else
    last_status=$?
  fi
  if [[ "${attempt}" -lt "${attempts}" ]]; then
    echo "LinkedIn Chrome preflight failed on attempt ${attempt}/${attempts}; retrying in ${delay}s..." >&2
    sleep "${delay}"
  fi
done

exit "${last_status}"
