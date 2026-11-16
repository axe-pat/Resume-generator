#!/usr/bin/env bash
set -euo pipefail

WINDOW="${1:-24h}"
RUN_ARTIFACT="${2:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-venv/bin/python}"
TWELVETWENTY_SCORE="${TWELVETWENTY_SCORE:-1}"

case "$WINDOW" in
  24h|7d|30d) ;;
  *) echo "Usage: $0 [24h|7d|30d] [exact-run-artifact.json]" >&2; exit 2 ;;
esac

./discovery/scripts/ensure_chrome_9222.sh \
  "https://marshall-usc.12twenty.com/jobPostings#/jobPostings/index?tab=all"

CMD=(
  "$PYTHON_BIN" discovery/auto/twelvetwenty_live.py
  --window "$WINDOW"
  --quiet
)
if [[ "$TWELVETWENTY_SCORE" == "1" ]]; then
  CMD+=(--score --write)
fi
if [[ -n "$RUN_ARTIFACT" ]]; then
  CMD+=(--run-artifact "$RUN_ARTIFACT")
fi

"${CMD[@]}"
