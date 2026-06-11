#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402

APPS_DIR = ROOT / "apps"
QUEUE_DIR = APPS_DIR / "Apply queues" / "current_apply_queue"
ARCHIVE_ROOT = APPS_DIR / "archive" / "generated"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"


def _load_ready_entries() -> list[dict]:
    priority_json = QUEUE_DIR / "priority_order.json"
    if not priority_json.exists():
        return []
    try:
        payload = json.loads(priority_json.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _archive_target(role_dir: Path, archived_on: str) -> Path:
    try:
        rel = role_dir.resolve().relative_to(APPS_DIR.resolve())
    except ValueError:
        rel = Path(role_dir.name)
    return ARCHIVE_ROOT / archived_on / rel


def _prune_empty_ancestors(start_dir: Path) -> None:
    current = start_dir.parent.resolve()
    stop_dirs = {APPS_DIR.resolve(), QUEUE_DIR.resolve()}
    while current not in stop_dirs and current.exists():
        try:
            next(current.iterdir())
            break
        except StopIteration:
            parent = current.parent.resolve()
            current.rmdir()
            current = parent


def main() -> int:
    entries = [
        entry
        for entry in _load_ready_entries()
        if str(entry.get("status") or "").strip().lower() == "generated"
        and str(entry.get("folder_path") or "").strip()
    ]
    if not entries:
        print("No generated current-queue entries to archive.")
        return 0

    archived_on = datetime.now().strftime("%Y-%m-%d")
    moved = 0
    updated = 0

    with jobs.XlsxLock():
        df = jobs.load_jobs()
        for entry in entries:
            row_id = str(entry.get("id") or "").strip()
            role_dir = Path(str(entry.get("folder_path") or "")).expanduser()
            if not row_id or not role_dir.exists():
                continue
            target = _archive_target(role_dir, archived_on)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(role_dir), str(target))
            _prune_empty_ancestors(role_dir)
            moved += 1

            mask = df["id"].astype(str).eq(row_id)
            if mask.any():
                df.loc[mask, "folder_path"] = str(target)
                df.loc[mask, "status"] = "generated"
                if "date_applied" in df.columns:
                    df.loc[mask, "date_applied"] = ""
                updated += int(mask.sum())
            print(f"[generated-archive] {entry.get('company')} -> {target}")
        jobs.save_jobs(df)

    print(f"Archived generated queue entries: {moved}")
    print(f"Updated tracker rows: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
