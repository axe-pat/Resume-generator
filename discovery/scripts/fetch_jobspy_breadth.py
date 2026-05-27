#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO_DIR = ROOT / "discovery" / "auto"
LOGS_DIR = AUTO_DIR / "logs"

if str(AUTO_DIR) not in sys.path:
    sys.path.insert(0, str(AUTO_DIR))

from scraper import scrape  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a raw JobSpy breadth artifact without scoring.")
    parser.add_argument("--hours-old", type=int, default=24)
    parser.add_argument("--results", type=int, default=None, help="Override JobSpy results per query/site.")
    parser.add_argument("--query-index", action="append", type=int, default=[], help="Optional scraper query index; repeatable.")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query_indices = args.query_index or None
    jobs = scrape(
        hours_old=args.hours_old,
        query_indices=query_indices,
        existing_hashes=set(),
        results_override=args.results,
        verbose=not args.quiet,
    )
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = LOGS_DIR / f"jobspy_breadth_raw_{args.hours_old}h_{stamp}.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "jobspy_breadth_v1",
        "hours_old": args.hours_old,
        "results_override": args.results,
        "query_indices": query_indices or "all",
        "count": len(jobs),
        "jobs": jobs,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote JobSpy raw artifact: {path}")
    print(f"JobSpy jobs: {len(jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
