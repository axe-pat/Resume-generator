#!/usr/bin/env bash
set -euo pipefail

WINDOW="${1:-24h}"
RUN_ARTIFACT="${2:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-venv/bin/python}"
HANDSHAKE_SEARCH_URL="${HANDSHAKE_SEARCH_URL:-}"
HANDSHAKE_LANE="${HANDSHAKE_LANE:-A}"

if [[ "$HANDSHAKE_LANE" != "A" && "$HANDSHAKE_LANE" != "C" ]]; then
  echo "HANDSHAKE_LANE must be A or C (got: ${HANDSHAKE_LANE})" >&2
  exit 2
fi

case "$WINDOW" in
  24h|past-24h)
    MAX_PAGES="${HANDSHAKE_MAX_PAGES:-1}"
    MAX_RESULTS="${HANDSHAKE_MAX_RESULTS:-25}"
    STOP_AFTER_EXISTING="${HANDSHAKE_STOP_AFTER_EXISTING:-8}"
    ;;
  7d|week|weekly)
    MAX_PAGES="${HANDSHAKE_MAX_PAGES:-3}"
    MAX_RESULTS="${HANDSHAKE_MAX_RESULTS:-75}"
    STOP_AFTER_EXISTING="${HANDSHAKE_STOP_AFTER_EXISTING:-18}"
    ;;
  *)
    cat >&2 <<'USAGE'
Usage:
  ./discovery/scripts/run_handshake_discovery.sh [24h|7d] [exact-run-artifact.json]

Environment overrides:
  HANDSHAKE_SEARCH_URL
  HANDSHAKE_LANE (A or C; Lane C requires a saved search URL)
  HANDSHAKE_MAX_PAGES
  HANDSHAKE_MAX_RESULTS
  HANDSHAKE_STOP_AFTER_EXISTING
USAGE
    exit 2
    ;;
esac

echo "==> Handshake discovery (${WINDOW})"
echo "    lane=${HANDSHAKE_LANE} max_pages=${MAX_PAGES} max_results=${MAX_RESULTS} stop_after_existing=${STOP_AFTER_EXISTING}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 && [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python not found at ${PYTHON_BIN}" >&2
  exit 1
fi

./discovery/scripts/ensure_chrome_9222.sh "https://app.joinhandshake.com/"

CMD=(
  "$PYTHON_BIN"
  discovery/auto/import_handshake_csv.py
  --lane "$HANDSHAKE_LANE"
  --max-pages "$MAX_PAGES"
  --max-search-results "$MAX_RESULTS"
  --stop-after-existing "$STOP_AFTER_EXISTING"
  --min-score 4.5
  --include-deprioritized
  --write
  --quiet
)

if [[ -n "$HANDSHAKE_SEARCH_URL" ]]; then
  CMD+=(--search-url "$HANDSHAKE_SEARCH_URL")
elif [[ "$HANDSHAKE_LANE" == "C" ]]; then
  echo "Lane C requires HANDSHAKE_SEARCH_URL for a saved on-campus/part-time search." >&2
  exit 2
else
  CMD+=(--default-search)
fi

if [[ -n "$RUN_ARTIFACT" ]]; then
  CMD+=(--run-artifact "$RUN_ARTIFACT")
fi

"${CMD[@]}"
