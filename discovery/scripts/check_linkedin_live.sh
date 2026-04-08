#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/.."

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"

"$PYTHON_BIN" discovery/auto/check_linkedin_live.py "$@"
