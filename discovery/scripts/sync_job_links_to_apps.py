#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


MIN_SCORE = 5.9
SOURCE = "linkedin_live_jobs_v1"
ACTIVE_STATUSES = {"queued", "promoted", "generated"}


def _load_rows() -> pd.DataFrame:
    df = pd.read_excel(jobs.JOBS_XLSX, sheet_name=jobs.JOBS_SHEET, dtype=str).fillna("")
    df = df[df["source"].eq(SOURCE)].copy()
    df = df[df["status"].isin(ACTIVE_STATUSES)].copy()
    df["fit_score_num"] = pd.to_numeric(df["fit_score"], errors="coerce")
    df = df[df["fit_score_num"] >= MIN_SCORE].copy()
    return df.sort_values(["fit_score_num", "date_found"], ascending=[False, False])


def _ensure_job_link_files(app_dir: Path, url: str) -> tuple[bool, bool]:
    created_or_updated_link = False
    intel_updated = False

    job_link_path = app_dir / "job_link.txt"
    desired_link_text = f"{url}\n"
    current_link_text = job_link_path.read_text(encoding="utf-8") if job_link_path.exists() else None
    if current_link_text != desired_link_text:
        job_link_path.write_text(desired_link_text, encoding="utf-8")
        created_or_updated_link = True

    intel_path = app_dir / "intel.txt"
    desired_line = f"job_link={url}"
    if intel_path.exists():
        intel_text = intel_path.read_text(encoding="utf-8").strip()
        lines = [line.strip() for line in intel_text.splitlines() if line.strip()]
        if not any(line.startswith("job_link=") for line in lines):
            new_text = desired_line if not intel_text else f"{desired_line}\n{intel_text}"
            intel_path.write_text(new_text + "\n", encoding="utf-8")
            intel_updated = True
    return created_or_updated_link, intel_updated


def main() -> int:
    df = _load_rows()
    updated = 0
    intel_updated = 0
    skipped: list[str] = []

    for _, row in df.iterrows():
        company = str(row.get("company") or "").strip()
        url = str(row.get("url") or "").strip()
        if not company or not url:
            continue
        try:
            target = jobs._resolve_generate_target(df, company)
        except Exception:
            skipped.append(company)
            continue

        app_dir = Path(str(target.get("app_dir") or "")).resolve()
        if not app_dir.exists():
            skipped.append(company)
            continue

        link_changed, intel_changed = _ensure_job_link_files(app_dir, url)
        if link_changed:
            updated += 1
        if intel_changed:
            intel_updated += 1
        print(f"{company} -> {app_dir}")

    print(f"job_link.txt updated: {updated}")
    print(f"intel.txt backfilled: {intel_updated}")
    if skipped:
        print("skipped (no app dir):")
        for company in skipped:
            print(f"  - {company}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
