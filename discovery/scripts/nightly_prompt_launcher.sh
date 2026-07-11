#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${RESUMEGEN_NIGHTLY_LOG_DIR:-${HOME}/Library/Logs/ResumeGenerator}"
mkdir -p "$LOG_DIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"
LAUNCH_LOG="${LOG_DIR}/nightly_launcher_${STAMP}.log"

{
  printf '[%s] nightly_prompt_launcher start\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"
  printf 'ROOT_DIR=%s\n' "$ROOT_DIR"
  printf 'RESUMEGEN_NIGHTLY_ARGS=%s\n' "${RESUMEGEN_NIGHTLY_ARGS:-}"
  printf 'ARGS=%s\n' "$*"
} >> "$LAUNCH_LOG"

cd "$ROOT_DIR"
exec "${ROOT_DIR}/venv/bin/python" discovery/scripts/nightly_prompt.py "$@"
