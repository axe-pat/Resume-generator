#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


ARCHIVE_APPLIED_DIR = jobs.APPS_DIR / "archive" / "applied"
CURRENT_QUEUE_ROOT = jobs.CURRENT_APPLY_QUEUE_DIR.resolve()
PDF_PATTERN = re.compile(r"\.pdf$", re.I)
PARK_NOTE_PREFIX = "[cleanup] parked stale active row"
APPLY_NOTE_PREFIX = "[cleanup] reconciled applied from archived pdf"


def _norm(text: str) -> str:
    raw = (text or "").lower()
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(raw.split())


def _role_tokens(text: str) -> list[str]:
    stop = {
        "intern",
        "internship",
        "summer",
        "fall",
        "spring",
        "product",
        "manager",
        "management",
        "mba",
        "new",
        "grad",
        "program",
        "co",
        "op",
        "associate",
        "strategy",
        "operations",
        "business",
        "global",
    }
    return [t for t in _norm(text).split() if len(t) >= 4 and t not in stop]


def _append_note(existing: str, message: str) -> str:
    existing = str(existing or "").strip()
    return f"{existing}\n{message}".strip() if existing else message


def _is_live_folder(folder_path: str) -> bool:
    raw = str(folder_path or "").strip()
    if not raw:
        return False
    path = Path(raw).expanduser()
    try:
        resolved = path.resolve()
    except FileNotFoundError:
        return False
    return resolved.exists() and CURRENT_QUEUE_ROOT in resolved.parents


def _build_archive_index() -> list[dict]:
    candidates: list[dict] = []
    if not ARCHIVE_APPLIED_DIR.exists():
        return candidates
    for path in ARCHIVE_APPLIED_DIR.rglob("*"):
        if not path.is_dir():
            continue
        pdfs = [f for f in path.rglob("*") if f.is_file() and PDF_PATTERN.search(f.name)]
        if not pdfs:
            continue
        newest_pdf = max(pdfs, key=lambda item: item.stat().st_mtime)
        candidates.append(
            {
                "dir": path,
                "path_norm": _norm(str(path.relative_to(ARCHIVE_APPLIED_DIR))),
                "date_applied": datetime.fromtimestamp(newest_pdf.stat().st_mtime).strftime("%Y-%m-%d"),
            }
        )
    return candidates


def _find_confident_archive_match(company: str, role_title: str, archive_index: list[dict]) -> dict | None:
    company_norm = _norm(company)
    tokens = _role_tokens(role_title)
    strong: list[tuple[int, dict]] = []
    for candidate in archive_index:
        path_norm = candidate["path_norm"]
        if not company_norm or company_norm not in path_norm:
            continue
        overlap = sum(1 for token in tokens if token in path_norm)
        if overlap >= 2:
            strong.append((overlap, candidate))
    if len(strong) != 1:
        return None
    return strong[0][1]


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archive_index = _build_archive_index()

    with jobs.XlsxLock():
        df = jobs.load_jobs().copy()
        statuses = df["status"].fillna("").astype(str).str.strip().str.lower()
        target_mask = statuses.isin(["promoted", "generated"])

        parked_count = 0
        applied_count = 0

        for idx, row in df[target_mask].iterrows():
            status = str(row.get("status") or "").strip().lower()
            folder_path = str(row.get("folder_path") or "").strip()
            if _is_live_folder(folder_path):
                continue

            archive_match = None
            if status == "generated":
                archive_match = _find_confident_archive_match(
                    str(row.get("company") or ""),
                    str(row.get("role_title") or ""),
                    archive_index,
                )

            if archive_match is not None:
                df.at[idx, "status"] = "applied"
                df.at[idx, "date_applied"] = archive_match["date_applied"]
                df.at[idx, "folder_path"] = str(archive_match["dir"])
                df.at[idx, "notes"] = _append_note(
                    row.get("notes") or "",
                    f"{APPLY_NOTE_PREFIX} at {timestamp}",
                )
                applied_count += 1
                continue

            df.at[idx, "status"] = "parked"
            df.at[idx, "notes"] = _append_note(
                row.get("notes") or "",
                f"{PARK_NOTE_PREFIX} at {timestamp}",
            )
            parked_count += 1

        jobs.save_jobs(df)

    print(f"Reconciled to applied: {applied_count}")
    print(f"Parked stale active rows: {parked_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
