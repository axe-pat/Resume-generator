#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_LABEL="${RESUMEGEN_NIGHTLY_LABEL:-com.akshat.resumegenerator.nightly}"
EVENING_TIME="${1:-20:00}"
OVERNIGHT_TIME="${2:-01:00}"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/venv/bin/python}"
LOG_DIR="${RESUMEGEN_NIGHTLY_LOG_DIR:-${HOME}/Library/Logs/ResumeGenerator}"
NIGHTLY_MODE="${RESUMEGEN_NIGHTLY_MODE:-unattended}"
ATTESTATION_PATH="${RESUMEGEN_PRODUCTION_ATTESTATION:-${HOME}/Library/Application Support/ResumeGenerator/production_release.json}"
LOAD_AFTER_WRITE="${RESUMEGEN_NIGHTLY_LOAD:-0}"
CONTRACT_SCRIPT="${ROOT_DIR}/discovery/scripts/nightly_contract.py"
PROMPT_SCRIPT="${ROOT_DIR}/discovery/scripts/nightly_prompt.py"
APP_SUPPORT="${HOME}/Library/Application Support/ResumeGenerator"
DISCOVERY_STATE_PATH="${APP_SUPPORT}/nightly_discovery_cadence.json"
SHARED_LOCK_PATH="${APP_SUPPORT}/nightly_scheduler.lock"
SCHEDULE_TIMEZONE="Asia/Kolkata"
DISCOVERY_CADENCE_HOURS="48"

validate_time() {
  local value="$1"
  if [[ ! "$value" =~ ^[0-2][0-9]:[0-5][0-9]$ ]]; then
    echo "Use HH:MM 24-hour time, for example 20:00" >&2
    exit 2
  fi
  local hour="${value%%:*}"
  if (( 10#${hour} > 23 )); then
    echo "Use an hour from 00 through 23" >&2
    exit 2
  fi
}

validate_time "$EVENING_TIME"
validate_time "$OVERNIGHT_TIME"
if [[ "$EVENING_TIME" != "20:00" || "$OVERNIGHT_TIME" != "01:00" ]]; then
  echo "The reviewed production slots are fixed at 20:00 and 01:00 Asia/Kolkata." >&2
  exit 2
fi
if [[ "$NIGHTLY_MODE" != "unattended" && "$NIGHTLY_MODE" != "prompt" && "$NIGHTLY_MODE" != "check" ]]; then
  echo "RESUMEGEN_NIGHTLY_MODE must be unattended, prompt, or check" >&2
  exit 2
fi
if [[ -n "${RESUMEGEN_NIGHTLY_ARGS:-}" ]]; then
  echo "RESUMEGEN_NIGHTLY_ARGS is not supported by the two-slot installer; use the reviewed per-slot contracts." >&2
  exit 2
fi

# Validate all four dynamic vectors before writing either plist. The scheduler
# revalidates the exact selected vector immediately before each production run.
for slot in evening_delivery overnight_maintenance; do
  for mode in discovery maintenance; do
    candidate="$("${PYTHON_BIN}" "${CONTRACT_SCRIPT}" print-slot "$slot" "$mode")"
    "${PYTHON_BIN}" "${CONTRACT_SCRIPT}" validate-slot "$slot" "$mode" "$candidate"
  done
done

mkdir -p "${HOME}/Library/LaunchAgents" "${LOG_DIR}"

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

write_slot_plist() {
  local slot="$1"
  local suffix="$2"
  local scheduled_time="$3"
  local label="$BASE_LABEL"
  if [[ "$suffix" != "evening" ]]; then
    label="${BASE_LABEL}.${suffix}"
  fi
  local plist_path="${HOME}/Library/LaunchAgents/${label}.plist"
  local state_path="${APP_SUPPORT}/nightly_scheduler_state.${suffix}.json"
  local stdout_path="${LOG_DIR}/nightly_${suffix}_launchd.out.log"
  local stderr_path="${LOG_DIR}/nightly_${suffix}_launchd.err.log"
  local mode_argument=""

  if [[ "$NIGHTLY_MODE" == "prompt" ]]; then
    mode_argument="    <string>--prompt</string>"
  elif [[ "$NIGHTLY_MODE" == "check" ]]; then
    mode_argument="    <string>--production-check-only</string>"
  else
    mode_argument="    <string>--require-production-slot-contract</string>"
  fi

  local label_xml python_xml prompt_xml slot_xml time_xml timezone_xml state_xml
  local discovery_state_xml lock_xml attestation_xml log_dir_xml stdout_xml stderr_xml
  label_xml="$(xml_escape "$label")"
  python_xml="$(xml_escape "$PYTHON_BIN")"
  prompt_xml="$(xml_escape "$PROMPT_SCRIPT")"
  slot_xml="$(xml_escape "$slot")"
  time_xml="$(xml_escape "$scheduled_time")"
  timezone_xml="$(xml_escape "$SCHEDULE_TIMEZONE")"
  state_xml="$(xml_escape "$state_path")"
  discovery_state_xml="$(xml_escape "$DISCOVERY_STATE_PATH")"
  lock_xml="$(xml_escape "$SHARED_LOCK_PATH")"
  attestation_xml="$(xml_escape "$ATTESTATION_PATH")"
  log_dir_xml="$(xml_escape "$LOG_DIR")"
  stdout_xml="$(xml_escape "$stdout_path")"
  stderr_xml="$(xml_escape "$stderr_path")"

  cat > "$plist_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label_xml}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${python_xml}</string>
    <string>${prompt_xml}</string>
    <string>--production-slot</string>
    <string>${slot_xml}</string>
    <string>--scheduled-time</string>
    <string>${time_xml}</string>
    <string>--timezone</string>
    <string>${timezone_xml}</string>
    <string>--state-path</string>
    <string>${state_xml}</string>
    <string>--discovery-state-path</string>
    <string>${discovery_state_xml}</string>
    <string>--discovery-cadence-hours</string>
    <string>${DISCOVERY_CADENCE_HOURS}</string>
    <string>--lock-path</string>
    <string>${lock_xml}</string>
    <string>--require-production-attestation</string>
    <string>--production-attestation</string>
    <string>${attestation_xml}</string>
${mode_argument}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TZ</key>
    <string>${timezone_xml}</string>
    <key>RESUMEGEN_NIGHTLY_LOG_DIR</key>
    <string>${log_dir_xml}</string>
    <key>RESUMEGEN_PRODUCTION_ATTESTATION</key>
    <string>${attestation_xml}</string>
  </dict>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>${stdout_xml}</string>
  <key>StandardErrorPath</key>
  <string>${stderr_xml}</string>
</dict>
</plist>
PLIST

  echo "Wrote ${plist_path}"
  echo "  slot=${slot} time=${scheduled_time} timezone=${SCHEDULE_TIMEZONE} state=${state_path}"
}

write_slot_plist "evening_delivery" "evening" "$EVENING_TIME"
write_slot_plist "overnight_maintenance" "overnight" "$OVERNIGHT_TIME"

echo "Mode: ${NIGHTLY_MODE}"
echo "Discovery cadence: one reserved attempt per ${DISCOVERY_CADENCE_HOURS} hours"
echo "Shared discovery state: ${DISCOVERY_STATE_PATH}"
echo "Shared overlap lock: ${SHARED_LOCK_PATH}"
echo "Production attestation: ${ATTESTATION_PATH}"

PLIST_PATHS=(
  "${HOME}/Library/LaunchAgents/${BASE_LABEL}.plist"
  "${HOME}/Library/LaunchAgents/${BASE_LABEL}.overnight.plist"
)
if [[ "$LOAD_AFTER_WRITE" == "1" ]]; then
  for plist_path in "${PLIST_PATHS[@]}"; do
    launchctl bootout "gui/$(id -u)" "$plist_path" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$plist_path"
    echo "Loaded ${plist_path}"
  done
else
  cat <<EOF
Not loaded yet. To enable both reviewed slots:
  launchctl bootout gui/$(id -u) "${PLIST_PATHS[0]}" 2>/dev/null || true
  launchctl bootstrap gui/$(id -u) "${PLIST_PATHS[0]}"
  launchctl bootstrap gui/$(id -u) "${PLIST_PATHS[1]}"

To disable later:
  launchctl bootout gui/$(id -u) "${PLIST_PATHS[0]}"
  launchctl bootout gui/$(id -u) "${PLIST_PATHS[1]}"
EOF
fi
