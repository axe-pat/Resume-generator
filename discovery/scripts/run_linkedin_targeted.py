#!/usr/bin/env python3
"""Capture weekly/daily cards, filter cheaply, hydrate, then score exact artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.discovery_search_policy import linkedin_search_terms


def stage(arguments: list[str], marker: str) -> Path:
    result = subprocess.run(
        [sys.executable, "-u", *arguments], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=None,
    )
    print(result.stdout, end="", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    paths = [line[len(marker):].strip() for line in result.stdout.splitlines()
             if line.startswith(marker)]
    if len(paths) != 1 or not Path(paths[0]).is_file():
        raise SystemExit(f"Missing or ambiguous exact artifact for {marker}")
    return Path(paths[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--capture-only", action="store_true", help="Save filtered cards; fetch JDs in the separately budgeted stage.")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--limit-per-search", type=int, default=None)
    parser.add_argument("--max-hydrate", type=int, default=None)
    args = parser.parse_args()
    args.limit_per_search = args.limit_per_search or (50 if args.window == "7d" else 30)
    args.max_hydrate = args.max_hydrate or (75 if args.window == "7d" else 25)
    time_filter = "r604800" if args.window == "7d" else "r86400"
    search_args = [value for term in linkedin_search_terms(args.window)
                   for value in ("--search", term, "--time", time_filter)]
    raw = stage([
        "discovery/auto/linkedin_live.py", "--launch-chrome", "--extract-only",
        "--count-only", "--pages", str(args.pages), "--limit-per-search", str(args.limit_per_search),
        "--allow-jobs-search-fallback", *search_args,
    ], "Raw artifact: ")
    selected = stage([
        "discovery/scripts/select_linkedin_2027_candidates.py", str(raw),
        "--exclude-workbook",
    ], "Selected raw artifact: ")
    if json.loads(selected.read_text())["count"] and not args.capture_only:
        selected = stage([
            "discovery/auto/linkedin_live.py", "--hydrate-from-raw", str(selected),
            "--max-hydrate", str(args.max_hydrate),
        ], "Hydrated raw artifact: ")
    print(f"Raw artifact: {selected}", flush=True)
    if args.extract_only or args.capture_only:
        return 0
    return subprocess.run([
        sys.executable, "-u", "discovery/auto/linkedin_live.py",
        "--score-from-raw", str(selected),
    ], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
