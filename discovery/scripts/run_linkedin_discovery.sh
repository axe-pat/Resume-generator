#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
WINDOW="${1:-24h}"
MODE="$(printf '%s' "$WINDOW" | tr '[:upper:]' '[:lower:]')"

case "$MODE" in
  24h|past-24h)
    SEARCH_ARGS=(
      --search "Product Manager Intern" --time r86400
      --search "MBA Intern" --time r86400
    )
    RUN_LABEL="past-24h"
    ;;
  7d|7day|7-day|week|weekly|past-week)
    SEARCH_ARGS=(
      --search "Product Manager Intern" --time r604800
      --search "MBA Intern" --time r604800
    )
    RUN_LABEL="past-week"
    ;;
  *)
    cat >&2 <<EOF
Usage:
  ./discovery/scripts/run_linkedin_discovery.sh [24h|7d]

Examples:
  ./discovery/scripts/run_linkedin_discovery.sh
  ./discovery/scripts/run_linkedin_discovery.sh 24h
  ./discovery/scripts/run_linkedin_discovery.sh 7d
EOF
    exit 1
    ;;
esac

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python env not found at $PYTHON_BIN" >&2
  exit 1
fi

RUN_STARTED_EPOCH="$(date +%s)"
EXTRACT_LOG="$(mktemp -t linkedin_extract.XXXXXX.log)"
trap 'rm -f "$EXTRACT_LOG"' EXIT

echo
echo "==> Pre-run queue hygiene"
"$PYTHON_BIN" discovery/scripts/sync_applied_pdfs.py
"$PYTHON_BIN" discovery/scripts/refresh_current_apply_queue.py
"$PYTHON_BIN" discovery/scripts/refresh_forgotten_queue.py

echo
echo "==> LinkedIn extract-only run ($RUN_LABEL)"
"$PYTHON_BIN" discovery/auto/linkedin_live.py \
  --launch-chrome \
  --extract-only \
  --allow-jobs-search-fallback \
  "${SEARCH_ARGS[@]}" | tee "$EXTRACT_LOG"

RAW_ARTIFACT="$(
"$PYTHON_BIN" - "$EXTRACT_LOG" "$RUN_STARTED_EPOCH" <<'PY'
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
started_epoch = int(sys.argv[2])
raw = ""

for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("Raw artifact: "):
        raw = line.split("Raw artifact: ", 1)[1].strip()

if raw and Path(raw).exists():
    print(raw)
    raise SystemExit

logs_dir = Path("discovery/auto/logs")
candidates = [
    path for path in logs_dir.glob("linkedin_live_raw_*.json")
    if path.is_file() and int(path.stat().st_mtime) >= started_epoch
]
if candidates:
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print(str(candidates[0]))
PY
)"

if [[ -z "${RAW_ARTIFACT}" || ! -f "${RAW_ARTIFACT}" ]]; then
  echo "ERROR: Could not determine raw artifact for this run." >&2
  exit 1
fi

echo
echo "==> Scoring from raw artifact"
echo "Raw artifact: ${RAW_ARTIFACT}"
"$PYTHON_BIN" discovery/auto/linkedin_live.py --score-from-raw "${RAW_ARTIFACT}"

echo
echo "==> Post-run queue refresh"
"$PYTHON_BIN" discovery/scripts/refresh_current_apply_queue.py
"$PYTHON_BIN" discovery/scripts/refresh_forgotten_queue.py

echo
echo "Done. Window: ${RUN_LABEL}"
