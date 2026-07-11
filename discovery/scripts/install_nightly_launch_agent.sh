#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="${RESUMEGEN_NIGHTLY_LABEL:-com.akshat.resumegenerator.nightly}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
SCHEDULED_TIME="${1:-01:00}"
PIPELINE_ARGS="${RESUMEGEN_NIGHTLY_ARGS:---generate}"
PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/venv/bin/python}"
LOG_DIR="${RESUMEGEN_NIGHTLY_LOG_DIR:-${HOME}/Library/Logs/ResumeGenerator}"
NIGHTLY_MODE="${RESUMEGEN_NIGHTLY_MODE:-unattended}"
ATTESTATION_PATH="${RESUMEGEN_PRODUCTION_ATTESTATION:-${HOME}/Library/Application Support/ResumeGenerator/production_release.json}"
LOAD_AFTER_WRITE="${RESUMEGEN_NIGHTLY_LOAD:-0}"

if [[ ! "$SCHEDULED_TIME" =~ ^[0-2][0-9]:[0-5][0-9]$ ]]; then
  echo "Use HH:MM 24-hour time, for example 20:00" >&2
  exit 2
fi
if [[ "$NIGHTLY_MODE" != "unattended" && "$NIGHTLY_MODE" != "prompt" && "$NIGHTLY_MODE" != "check" ]]; then
  echo "RESUMEGEN_NIGHTLY_MODE must be unattended, prompt, or check" >&2
  exit 2
fi

HOUR="${SCHEDULED_TIME%%:*}"
MINUTE="${SCHEDULED_TIME##*:}"
HOUR="$((10#$HOUR))"
MINUTE="$((10#$MINUTE))"

mkdir -p "${HOME}/Library/LaunchAgents" "${LOG_DIR}"

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

STDOUT_XML="$(xml_escape "${LOG_DIR}/nightly_launchd.out.log")"
STDERR_XML="$(xml_escape "${LOG_DIR}/nightly_launchd.err.log")"
LAUNCHER_XML="$(xml_escape "${ROOT_DIR}/discovery/scripts/nightly_prompt_launcher.sh")"
PIPELINE_ARGS_XML="$(xml_escape "$PIPELINE_ARGS")"
LOG_DIR_XML="$(xml_escape "$LOG_DIR")"
ATTESTATION_XML="$(xml_escape "$ATTESTATION_PATH")"
PROMPT_ARGUMENT_XML=""
if [[ "$NIGHTLY_MODE" == "prompt" ]]; then
  PROMPT_ARGUMENT_XML="    <string>--prompt</string>"
elif [[ "$NIGHTLY_MODE" == "check" ]]; then
  PROMPT_ARGUMENT_XML="    <string>--production-check-only</string>"
fi

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${LAUNCHER_XML}</string>
    <string>--scheduled-time</string>
    <string>${SCHEDULED_TIME}</string>
    <string>--require-production-attestation</string>
    <string>--production-attestation</string>
    <string>${ATTESTATION_XML}</string>
${PROMPT_ARGUMENT_XML}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>RESUMEGEN_NIGHTLY_ARGS</key>
    <string>${PIPELINE_ARGS_XML}</string>
    <key>RESUMEGEN_NIGHTLY_LOG_DIR</key>
    <string>${LOG_DIR_XML}</string>
    <key>RESUMEGEN_PRODUCTION_ATTESTATION</key>
    <string>${ATTESTATION_XML}</string>
  </dict>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>${HOUR}</integer>
    <key>Minute</key>
    <integer>${MINUTE}</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${STDOUT_XML}</string>
  <key>StandardErrorPath</key>
  <string>${STDERR_XML}</string>
</dict>
</plist>
PLIST

echo "Wrote ${PLIST_PATH}"
echo "Scheduled run time: ${SCHEDULED_TIME}"
echo "Mode: ${NIGHTLY_MODE}"
echo "Production attestation: ${ATTESTATION_PATH}"
echo "Pipeline args: ${PIPELINE_ARGS}"

if [[ "$LOAD_AFTER_WRITE" == "1" ]]; then
  launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
  echo "Loaded ${LABEL}"
else
  cat <<EOF
Not loaded yet. To enable:
  launchctl bootstrap gui/$(id -u) "$PLIST_PATH"

To disable later:
  launchctl bootout gui/$(id -u) "$PLIST_PATH"
EOF
fi
