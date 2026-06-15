#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


APPS_DIR = ROOT / "apps"
ARCHIVE_ROOT = APPS_DIR / "archive" / "applied"
QUEUE_ROOT = APPS_DIR / "Apply queues"


def _find_resume_pdf_dirs() -> list[Path]:
    dirs: list[Path] = []
    for pdf_path in APPS_DIR.rglob("Resume.pdf"):
        if "archive" in pdf_path.parts:
            continue
        if ".current_apply_queue_prev" in pdf_path.parts:
            continue
        if "forgotten_queue" in pdf_path.parts:
            continue
        dirs.append(pdf_path.parent.resolve())
    return sorted(set(dirs))


def _dir_slug(path: Path) -> str:
    return jobs._dir_slug(path.name).lower()


def _match_rows(df, app_dir: Path):
    dir_str = str(app_dir.resolve())
    slug = _dir_slug(app_dir)
    exact = df["folder_path"].fillna("").astype(str).eq(dir_str)
    if exact.any():
        return exact

    contains = df["folder_path"].fillna("").astype(str).str.contains(dir_str, regex=False)
    if contains.any():
        return contains

    slug_match = df["company"].fillna("").astype(str).apply(lambda value: jobs._dir_slug(value).lower() == slug)
    status_match = df["status"].fillna("").astype(str).str.lower().isin(["generated", "promoted", "queued", "applied"])
    combined = slug_match & status_match
    return combined


def _archive_target(app_dir: Path, applied_on: str) -> Path:
    rel = app_dir.relative_to(APPS_DIR)
    return ARCHIVE_ROOT / applied_on / rel


def _prune_empty_ancestors(start_dir: Path) -> None:
    current = start_dir.parent.resolve()
    stop_dirs = {
        APPS_DIR.resolve(),
        QUEUE_ROOT.resolve(),
    }
    while current not in stop_dirs and current.exists():
        try:
            next(current.iterdir())
            break
        except StopIteration:
            parent = current.parent.resolve()
            current.rmdir()
            current = parent


def main() -> int:
    resume_dirs = _find_resume_pdf_dirs()
    if not resume_dirs:
        print("No Resume.pdf files found.")
        return 0

    applied_on = datetime.now().strftime("%Y-%m-%d")
    updated_rows = 0
    moved_dirs = 0

    with jobs.XlsxLock():
        df = jobs.load_jobs()

        for app_dir in resume_dirs:
            mask = _match_rows(df, app_dir)
            if not mask.any():
                print(f"[skip] No tracker row matched {app_dir}")
                continue

            archive_target = _archive_target(app_dir, applied_on)
            archive_target.parent.mkdir(parents=True, exist_ok=True)
            if archive_target.exists():
                print(f"[skip] Archive target already exists for {app_dir}: {archive_target}")
                continue

            matching = df[mask]
            df.loc[mask, "status"] = "applied"
            df.loc[mask, "date_applied"] = applied_on
            df.loc[mask, "folder_path"] = str(archive_target)
            updated_rows += matching.shape[0]

            shutil.move(str(app_dir), str(archive_target))
            _prune_empty_ancestors(app_dir)
            moved_dirs += 1
            companies = ", ".join(sorted(set(matching["company"].astype(str).tolist())))
            print(f"[applied] {companies} -> {archive_target}")

        jobs.save_jobs(df)

    print(f"Updated rows: {updated_rows}")
    print(f"Archived dirs: {moved_dirs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
