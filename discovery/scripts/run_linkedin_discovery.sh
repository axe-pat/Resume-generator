#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
WINDOW="${1:-24h}"
MODE="$(printf '%s' "$WINDOW" | tr '[:upper:]' '[:lower:]')"
CLOSE_TABS=0

if [[ "${2:-}" == "--close-tabs" ]]; then
  CLOSE_TABS=1
fi

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
  ./discovery/scripts/run_linkedin_discovery.sh [24h|7d] [--close-tabs]

Examples:
  ./discovery/scripts/run_linkedin_discovery.sh
  ./discovery/scripts/run_linkedin_discovery.sh 24h
  ./discovery/scripts/run_linkedin_discovery.sh 7d
  ./discovery/scripts/run_linkedin_discovery.sh 24h --close-tabs
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

SCORED_ARTIFACT="$(
"$PYTHON_BIN" - "$RUN_STARTED_EPOCH" <<'PY'
from pathlib import Path
import sys

started_epoch = int(sys.argv[1])
logs_dir = Path("discovery/auto/logs")
candidates = [
    path for path in logs_dir.glob("linkedin_live_scored_*.json")
    if path.is_file() and int(path.stat().st_mtime) >= started_epoch
]
if candidates:
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print(str(candidates[0]))
PY
)"

REPORT_MD="$(
"$PYTHON_BIN" - "$RUN_STARTED_EPOCH" "$RUN_LABEL" <<'PY'
from pathlib import Path
import sys

started_epoch = int(sys.argv[1])
run_label = sys.argv[2]
logs_dir = Path("discovery/auto/logs")
candidates = [
    path for path in logs_dir.glob(f"linkedin_live_report_*_{run_label}.md")
    if path.is_file() and int(path.stat().st_mtime) >= started_epoch
]
if candidates:
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    print(str(candidates[0]))
PY
)"

echo
echo "==> Post-run queue refresh"
"$PYTHON_BIN" discovery/scripts/refresh_current_apply_queue.py
"$PYTHON_BIN" discovery/scripts/refresh_forgotten_queue.py

QUEUE_SUMMARY="$(
"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

priority = Path("apps/Apply queues/current_apply_queue/priority_order.json")
manual = Path("apps/Apply queues/current_apply_queue/manual_review/manifest.json")

ready_count = 0
if priority.exists():
    try:
        ready_count = len(json.loads(priority.read_text()))
    except Exception:
        pass

manual_count = 0
if manual.exists():
    try:
        payload = json.loads(manual.read_text())
        manual_count = int(payload.get("count", 0))
    except Exception:
        pass

print(f"{ready_count}|{manual_count}")
PY
)"

READY_COUNT="${QUEUE_SUMMARY%%|*}"
MANUAL_COUNT="${QUEUE_SUMMARY##*|}"

if [[ "$CLOSE_TABS" == "1" ]]; then
  echo
  echo "==> Closing extra LinkedIn Jobs tabs"
  "$PYTHON_BIN" - <<'PY'
from playwright.sync_api import sync_playwright
from discovery.auto.linkedin_live import _open_linkedin_browser_session

closed = 0
with sync_playwright() as playwright:
    session = _open_linkedin_browser_session(playwright, 9222)
    try:
        context = session["context"]
        pages = list(context.pages)
        keep = None
        for page in pages:
            try:
                url = page.url or ""
            except Exception:
                continue
            if "linkedin.com/feed" in url:
                keep = page
                break
        for page in pages:
            if page is keep:
                continue
            try:
                url = page.url or ""
            except Exception:
                url = ""
            if "linkedin.com/jobs" in url or "linkedin.com/feed" in url:
                try:
                    page.close()
                    closed += 1
                except Exception:
                    pass
    finally:
        try:
            session["cleanup"]()
        except Exception:
            pass
print(f"Closed tabs: {closed}")
PY
fi

echo
echo "============================================================"
echo "LinkedIn discovery complete"
echo "Window: ${RUN_LABEL}"
echo "Raw: ${RAW_ARTIFACT}"
if [[ -n "${SCORED_ARTIFACT}" ]]; then
  echo "Scored: ${SCORED_ARTIFACT}"
fi
if [[ -n "${REPORT_MD}" ]]; then
  echo "Report: ${REPORT_MD}"
fi
echo "Queue: ready=${READY_COUNT} manual_review=${MANUAL_COUNT}"
echo "============================================================"
