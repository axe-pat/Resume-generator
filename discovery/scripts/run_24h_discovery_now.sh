#!/usr/bin/env bash
# One-shot durable 24h LinkedIn discovery launcher.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p discovery/auto/logs
LOG="discovery/auto/logs/linkedin_discovery_24h_$(date +%Y%m%d-%H%M%S).log"
LATEST="discovery/auto/logs/linkedin_discovery_24h_latest.log"

echo "RUN_START=$(date -Iseconds)" | tee "$LOG"
echo "LOG=$LOG" | tee -a "$LOG"
ln -sfn "$(basename "$LOG")" "$LATEST" 2>/dev/null || cp "$LOG" "$LATEST"

set +e
caffeinate -dims ./discovery/scripts/run_linkedin_discovery.sh 24h 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e

echo "EXIT_CODE=$RC" | tee -a "$LOG"
echo "DONE" | tee -a "$LOG"
# keep latest pointer current
cp "$LOG" "$LATEST" 2>/dev/null || true
exit "$RC"
