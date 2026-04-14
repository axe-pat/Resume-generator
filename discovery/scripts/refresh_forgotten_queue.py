#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
RUNS_DIR = APPS_DIR / "runs"
FORGOTTEN_DIR = RUNS_DIR / "forgotten_queue"
LEGACY_DIR = FORGOTTEN_DIR / "manual_legacy"
AGED_OUT_DIR = FORGOTTEN_DIR / "aged_out"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"
AGE_OUT_DAYS = 10


def _safe_move(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))


def _age_days(date_found: str) -> int | None:
    raw = (date_found or "").strip()
    if len(raw) < 10:
        return None
    try:
        return (date.today() - datetime.strptime(raw[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return None


def _remaining_top_level_dirs() -> list[Path]:
    keep = {"runs", "archive"}
    return sorted(
        p for p in APPS_DIR.iterdir()
        if p.is_dir() and p.name not in keep
    )


def _move_legacy_dirs() -> list[str]:
    moved: list[str] = []
    for src in _remaining_top_level_dirs():
        dst = LEGACY_DIR / src.name
        _safe_move(src, dst)
        moved.append(src.name)
    return moved


def _age_out_current_queue_rows() -> list[dict]:
    if not JOBS_XLSX.exists():
        return []

    df = pd.read_excel(JOBS_XLSX, sheet_name="Jobs", dtype=str).fillna("")
    moved: list[dict] = []

    for idx, row in df.iterrows():
        source = str(row.get("source") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        folder_path = str(row.get("folder_path") or "").strip()
        if source != "linkedin_live_jobs_v1":
            continue
        if status in {"applied", "reject", "rejected", "deprioritized", "ignore"}:
            continue
        if "current_apply_queue" not in folder_path:
            continue
        days_old = _age_days(str(row.get("date_found") or ""))
        if days_old is None or days_old <= AGE_OUT_DAYS:
            continue

        src = Path(folder_path).resolve().parent
        dst = AGED_OUT_DIR / src.name
        _safe_move(src, dst)

        role_dir = next((p for p in dst.iterdir() if p.is_dir()), None) if dst.exists() else None
        if role_dir is not None:
            df.at[idx, "folder_path"] = str(role_dir)
            moved.append({
                "id": str(row.get("id") or ""),
                "company": str(row.get("company") or ""),
                "days_old": days_old,
                "folder_path": str(role_dir),
            })

    if moved:
        with pd.ExcelWriter(JOBS_XLSX, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="Jobs", index=False)

    return moved


def main() -> int:
    FORGOTTEN_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    AGED_OUT_DIR.mkdir(parents=True, exist_ok=True)

    moved_legacy = _move_legacy_dirs()
    moved_aged = _age_out_current_queue_rows()

    print(f"Forgotten queue: {FORGOTTEN_DIR}")
    print(f"Moved legacy dirs: {len(moved_legacy)}")
    for name in moved_legacy:
        print(f"  - {name}")
    print(f"Aged out current queue jobs: {len(moved_aged)}")
    for item in moved_aged:
        print(f"  - {item['company']} ({item['days_old']} days)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
