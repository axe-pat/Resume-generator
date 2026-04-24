#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
RUNS_DIR = APPS_DIR / "runs"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"
BLOCKLIST = ROOT / "discovery" / "blocklist.txt"
MIN_SCORE = 5.9
EXCLUDED_COMPANIES = {"comcast"}

import jobs
from shared.discovery_sources import APPLY_QUEUE_SOURCES, queue_company_label


def _dir_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._ -]+", "", (text or "").strip())
    slug = re.sub(r"\s+", "_", slug).strip("._ ")
    return slug or "item"


def _load_blocklist() -> list[str]:
    if not BLOCKLIST.exists():
        return []
    lines = []
    for line in BLOCKLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line.lower())
    return lines


def _is_blocklisted(company: str, patterns: list[str]) -> bool:
    import fnmatch

    name = (company or "").strip().lower()
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _origin_runs_by_url() -> dict[str, list[str]]:
    by_url: dict[str, list[str]] = {}
    for manifest_path in sorted(RUNS_DIR.glob("*/manifest.json")):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_name = manifest_path.parent.name
        for job in data.get("accepted_jobs", []):
            url = str(job.get("url") or "").strip()
            if not url:
                continue
            by_url.setdefault(url, []).append(run_name)
    return by_url


def _intel_text(row: dict, origin_runs: list[str]) -> str:
    lines = []
    url = str(row.get("url") or "").strip()
    if url:
        lines.append(f"job_link={url}")
    fit_score = str(row.get("fit_score") or "").strip()
    if fit_score and fit_score.lower() != "nan":
        lines.append(f"fit_score={fit_score}")
    status = str(row.get("status") or "").strip()
    if status:
        lines.append(f"tracker_status={status}")
    if origin_runs:
        lines.append(f"origin_runs={', '.join(origin_runs)}")
    notes = str(row.get("notes") or "").strip()
    if notes:
        lines.append(notes)
    return "\n".join(lines).strip()


def _write_job_dir(base_dir: Path, rank: int, row: dict, origin_runs: list[str], category: str, reason: str = "") -> dict:
    company = str(row.get("company") or "")
    role = str(row.get("role_title") or "")
    source = str(row.get("source") or "")
    ranked_company_dir = base_dir / f"{rank:02d}_{_dir_slug(queue_company_label(company, source))}"
    role_dir = ranked_company_dir / _dir_slug(role)
    role_dir.mkdir(parents=True, exist_ok=True)

    jd_text = str(row.get("jd_text") or "").strip()
    (role_dir / "jd.txt").write_text(jd_text, encoding="utf-8")

    intel = _intel_text(row, origin_runs)
    if intel:
        (role_dir / "intel.txt").write_text(intel, encoding="utf-8")

    metadata = {
        "id": str(row.get("id") or ""),
        "company": company,
        "role_title": role,
        "fit_score": str(row.get("fit_score") or ""),
        "status": str(row.get("status") or ""),
        "url": str(row.get("url") or ""),
        "date_found": str(row.get("date_found") or ""),
        "folder_path": str(row.get("folder_path") or ""),
        "source": source,
        "origin_runs": origin_runs,
        "category": category,
        "reason": reason,
        "app_dir_hint": _dir_slug(company),
    }
    (role_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "priority_rank": rank,
        "id": metadata["id"],
        "company": company,
        "role_title": role,
        "fit_score": metadata["fit_score"],
        "status": metadata["status"],
        "url": metadata["url"],
        "origin_runs": origin_runs,
        "bundle_dir": str(role_dir),
        "folder_path": str(role_dir),
        "reason": reason,
    }


def _update_folder_paths(entries: list[dict]) -> None:
    if not entries:
        return
    df = pd.read_excel(JOBS_XLSX, sheet_name="Jobs", dtype=str).fillna("")
    for entry in entries:
        row_id = str(entry.get("id") or "").strip()
        folder_path = str(entry.get("folder_path") or "").strip()
        if not row_id or not folder_path:
            continue
        mask = df["id"].astype(str) == row_id
        if mask.any():
            df.loc[mask, "folder_path"] = folder_path
    jobs.save_jobs(df)


def main() -> int:
    df = pd.read_excel(JOBS_XLSX, sheet_name="Jobs", dtype=str).fillna("")
    df = df[df["source"].isin(APPLY_QUEUE_SOURCES)].copy()
    df["fit_score_num"] = pd.to_numeric(df["fit_score"], errors="coerce")
    df = df[df["status"].isin(["queued", "promoted", "generated"])]
    df = df[df["fit_score_num"] >= MIN_SCORE]
    df = df.sort_values(["fit_score_num", "date_found"], ascending=[False, False])

    blocklist = _load_blocklist()
    origin_runs = _origin_runs_by_url()

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    queue_dir = RUNS_DIR / f"{stamp}_linkedin_apply_queue"
    ready_dir = queue_dir / "ready"
    manual_dir = queue_dir / "manual_review"
    queue_dir.mkdir(parents=True, exist_ok=True)
    ready_dir.mkdir(exist_ok=True)
    manual_dir.mkdir(exist_ok=True)

    ready_entries: list[dict] = []
    manual_entries: list[dict] = []

    for _, row in df.iterrows():
        company_lc = str(row.get("company") or "").strip().lower()
        company = str(row.get("company") or "")
        url = str(row.get("url") or "").strip()
        runs = origin_runs.get(url, [])

        if company_lc in EXCLUDED_COMPANIES:
            manual_entries.append(
                _write_job_dir(manual_dir, len(manual_entries) + 1, row, runs, "manual_review", "excluded_company")
            )
            continue
        if _is_blocklisted(company, blocklist):
            manual_entries.append(
                _write_job_dir(manual_dir, len(manual_entries) + 1, row, runs, "manual_review", "blocklisted")
            )
            continue
        ready_entries.append(
            _write_job_dir(ready_dir, len(ready_entries) + 1, row, runs, "ready")
        )

    _update_folder_paths(ready_entries)

    companies_to_generate = [
        entry["company"]
        for entry in ready_entries
        if str(entry.get("status") or "").lower() != "generated"
    ]

    priority_txt = queue_dir / "priority_order.txt"
    priority_json = queue_dir / "priority_order.json"
    manual_txt = queue_dir / "manual_review.txt"
    companies_txt = queue_dir / "companies_to_generate.txt"
    command_sh = queue_dir / "generate_command.sh"

    priority_txt.write_text(
        "\n".join(
            f"{entry['priority_rank']}. {entry['company']} | {entry['role_title']} | score={entry['fit_score']} | status={entry['status']}"
            for entry in ready_entries
        ),
        encoding="utf-8",
    )
    priority_json.write_text(json.dumps(ready_entries, indent=2), encoding="utf-8")
    manual_txt.write_text(
        "\n".join(
            f"{entry['priority_rank']}. {entry['company']} | {entry['role_title']} | score={entry['fit_score']} | reason={entry['reason']}"
            for entry in manual_entries
        ),
        encoding="utf-8",
    )
    companies_txt.write_text("\n".join(companies_to_generate), encoding="utf-8")

    queue_priority_rel = "apps/Apply queues/current_apply_queue/priority_order.json"
    script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'cd "$(dirname "$0")/../../.."',
        "export RUN_APP_SEQUENTIAL=1",
        "",
        f'./venv/bin/python jobs.py --no-color generate --queue --queue-path {shlex.quote(queue_priority_rel)}',
    ]
    command_sh.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
    command_sh.chmod(0o755)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sources": sorted(APPLY_QUEUE_SOURCES),
        "min_score": MIN_SCORE,
        "ready_count": len(ready_entries),
        "manual_review_count": len(manual_entries),
        "companies_to_generate": companies_to_generate,
        "priority_files": {
            "text": str(priority_txt),
            "json": str(priority_json),
            "manual_review": str(manual_txt),
            "companies_to_generate": str(companies_txt),
            "generate_command": str(command_sh),
        },
        "ready_jobs": ready_entries,
        "manual_review_jobs": manual_entries,
    }
    (queue_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Queue: {queue_dir}")
    print(f"Ready jobs: {len(ready_entries)}")
    print(f"Manual review jobs: {len(manual_entries)}")
    print(f"Generate command: bash {command_sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
