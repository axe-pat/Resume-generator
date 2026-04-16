#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


CURRENT_QUEUE_ROOT = jobs.CURRENT_APPLY_QUEUE_DIR.resolve()
PARK_NOTE_PREFIX = "[cleanup] parked legacy queued row"


def _is_current_queue_folder(folder_path: str) -> bool:
    raw = str(folder_path or "").strip()
    if not raw:
        return False
    path = Path(raw).expanduser()
    try:
        resolved = path.resolve()
    except FileNotFoundError:
        return False
    return resolved.is_dir() and CURRENT_QUEUE_ROOT in resolved.parents


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with jobs.XlsxLock():
        df = jobs.load_jobs().copy()
        status = df["status"].fillna("").astype(str).str.strip().str.lower()
        folder = df["folder_path"].fillna("").astype(str)

        queued_mask = status.eq("queued")
        current_queue_mask = folder.apply(_is_current_queue_folder)
        park_mask = queued_mask & ~current_queue_mask

        if not park_mask.any():
            print("No legacy queued rows found outside the current apply queue.")
            return 0

        df.loc[park_mask, "status"] = "parked"
        df.loc[park_mask, "notes"] = df.loc[park_mask, "notes"].fillna("").astype(str).apply(
            lambda notes: (
                f"{notes}\n{PARK_NOTE_PREFIX} at {timestamp}".strip()
                if notes.strip()
                else f"{PARK_NOTE_PREFIX} at {timestamp}"
            )
        )

        jobs.save_jobs(df)

    parked_count = int(park_mask.sum())
    remaining_queued = int((df["status"].fillna("").astype(str).str.strip().str.lower() == "queued").sum())
    print(f"Parked legacy queued rows: {parked_count}")
    print(f"Remaining live queued rows: {remaining_queued}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
