#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
RUNS_DIR = APPS_DIR / "runs"
ARCHIVE_DIR = APPS_DIR / "archive"

# Legacy top-level auto-run dirs that are now represented inside current_apply_queue.
REDUNDANT_TOP_LEVEL_DIRS = [
    "Alo",
    "Amperesand",
    "Applied Materials",
    "Applied_Materials",
    "BioTrillion",
    "Fanatics",
    "Hypertherm_Associates",
    "Macys",
    "MindFort_AI_YC_X25",
    "Momentum",
    "Nuvo",
    "WayUp_1687",
]


def _safe_move(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))


def main() -> int:
    stamp = date.today().isoformat()
    top_level_archive = ARCHIVE_DIR / "redundant_top_level" / stamp
    queue_archive = ARCHIVE_DIR / "stale_apply_queues" / stamp
    discovery_archive = ARCHIVE_DIR / "discovery_runs" / stamp

    moved_top_level: list[str] = []
    moved_queues: list[str] = []
    moved_discovery: list[str] = []

    for name in REDUNDANT_TOP_LEVEL_DIRS:
        src = APPS_DIR / name
        if not src.exists():
            continue
        _safe_move(src, top_level_archive / name)
        moved_top_level.append(name)

    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        name = run_dir.name
        if name == "current_apply_queue":
            continue
        if name.endswith("_linkedin_apply_queue"):
            _safe_move(run_dir, queue_archive / name)
            moved_queues.append(name)
        elif name.endswith("_past-24h"):
            _safe_move(run_dir, discovery_archive / name)
            moved_discovery.append(name)

    print(f"Archived top-level dirs: {len(moved_top_level)}")
    for name in moved_top_level:
        print(f"  - {name}")
    print(f"Archived stale apply queues: {len(moved_queues)}")
    for name in moved_queues:
        print(f"  - {name}")
    print(f"Archived discovery runs: {len(moved_discovery)}")
    for name in moved_discovery:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
