#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.scripts.build_linkedin_apply_queue import (
    EXCLUDED_COMPANIES,
    MIN_SCORE,
    SOURCE,
    _dir_slug,
    _is_blocklisted,
    _load_blocklist,
)

APPS_DIR = ROOT / "apps"
RUNS_DIR = APPS_DIR / "runs"
ARCHIVE_DIR = APPS_DIR / "archive"
DISCOVERY_ARCHIVE_DIR = ARCHIVE_DIR / "discovery_runs"
QUEUE_DIR = RUNS_DIR / "current_apply_queue"
JOBS_DIR = QUEUE_DIR / "jobs"
MANUAL_DIR = QUEUE_DIR / "manual_review"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"


def _discovery_manifest_paths() -> list[Path]:
    manifests = list(RUNS_DIR.glob("*_past-*/manifest.json"))
    manifests += list(DISCOVERY_ARCHIVE_DIR.glob("*/*/manifest.json"))
    manifests += list(DISCOVERY_ARCHIVE_DIR.glob("*/manifest.json"))
    return sorted({p.resolve() for p in manifests}, key=lambda p: p.parent.name)


def _latest_discovery_manifest() -> tuple[Path | None, dict]:
    for manifest_path in reversed(_discovery_manifest_paths()):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("accepted_jobs"):
            return manifest_path, data
    return None, {}


def _job_dir(base_dir: Path, row: dict, bucket: str) -> Path:
    company = _dir_slug(str(row.get("company") or ""))
    role = _dir_slug(str(row.get("role_title") or ""))
    date_found = str(row.get("date_found") or "").strip()
    mmdd = "unknown"
    if len(date_found) >= 10 and date_found[4] == "-" and date_found[7] == "-":
        mmdd = f"{date_found[5:7]}-{date_found[8:10]}"
    fit_score_num = pd.to_numeric(str(row.get("fit_score") or "").strip(), errors="coerce")
    fit_slug = f"{int(round(float(fit_score_num) * 10)):02d}" if pd.notna(fit_score_num) else "na"
    bucket_slug = "NEW" if bucket == "new" else "CARRY"
    return base_dir / f"{mmdd}_{bucket_slug}_{fit_slug}_{company}" / role


def _write_job_files(role_dir: Path, row: dict, *, bucket: str, latest_run_name: str, in_latest_run: bool, origin_runs: list[str], reason: str = "") -> dict:
    role_dir.mkdir(parents=True, exist_ok=True)

    jd_text = str(row.get("jd_text") or "").strip()
    if jd_text:
        (role_dir / "jd.txt").write_text(jd_text, encoding="utf-8")

    lines: list[str] = []
    url = str(row.get("url") or "").strip()
    if url:
        lines.append(f"job_link={url}")
    fit_score = str(row.get("fit_score") or "").strip()
    if fit_score and fit_score.lower() != "nan":
        lines.append(f"fit_score={fit_score}")
    priority_score = str(row.get("priority_score") or "").strip()
    if priority_score and priority_score.lower() != "nan":
        lines.append(f"priority_score={priority_score}")
    status = str(row.get("status") or "").strip()
    if status:
        lines.append(f"tracker_status={status}")
    lines.append(f"queue_bucket={bucket}")
    lines.append(f"in_latest_run={'true' if in_latest_run else 'false'}")
    if latest_run_name:
        lines.append(f"latest_run={latest_run_name}")
    if origin_runs:
        lines.append(f"origin_runs={', '.join(origin_runs)}")
    if reason:
        lines.append(f"reason={reason}")
    notes = str(row.get("notes") or "").strip()
    if notes:
        lines.append(notes)
    (role_dir / "intel.txt").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    metadata = {
        "id": str(row.get("id") or ""),
        "company": str(row.get("company") or ""),
        "role_title": str(row.get("role_title") or ""),
        "fit_score": str(row.get("fit_score") or ""),
        "priority_score": str(row.get("priority_score") or ""),
        "status": str(row.get("status") or ""),
        "url": url,
        "date_found": str(row.get("date_found") or ""),
        "queue_bucket": bucket,
        "in_latest_run": in_latest_run,
        "latest_run": latest_run_name,
        "origin_runs": origin_runs,
        "reason": reason,
    }
    (role_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _copy_tree_contents(src: Path, dst: Path) -> None:
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def _move_tree_contents(src: Path, dst: Path) -> None:
    for child in list(src.iterdir()):
        target = dst / child.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
    try:
        src.rmdir()
    except OSError:
        pass


def _sync_existing_artifacts(row: dict, target_dir: Path) -> None:
    src_str = str(row.get("folder_path") or "").strip()
    if not src_str:
        return
    src = Path(src_str)
    if not src.exists() or src.resolve() == target_dir.resolve():
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    root_apps_children = [p.resolve() for p in APPS_DIR.iterdir() if p.name not in {"runs", "archive"}]
    is_top_level_app = any(src.resolve() == child for child in root_apps_children)

    if is_top_level_app:
        _move_tree_contents(src, target_dir)
    else:
        _copy_tree_contents(src, target_dir)


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
    with pd.ExcelWriter(JOBS_XLSX, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="Jobs", index=False)


def _origin_runs_by_url() -> dict[str, list[str]]:
    by_url: dict[str, list[str]] = {}
    manifests = list(RUNS_DIR.glob("*/manifest.json"))
    manifests += list(DISCOVERY_ARCHIVE_DIR.glob("*/*/manifest.json"))
    manifests += list(DISCOVERY_ARCHIVE_DIR.glob("*/manifest.json"))
    for manifest_path in sorted({p.resolve() for p in manifests}, key=lambda p: p.parent.name):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_name = manifest_path.parent.name
        for collection_name in ("accepted_jobs", "ready_jobs"):
            for job in data.get(collection_name, []):
                url = str(job.get("url") or "").strip()
                if not url:
                    continue
                by_url.setdefault(url, [])
                if run_name not in by_url[url]:
                    by_url[url].append(run_name)
    return by_url


def _priority_components(row: pd.Series) -> tuple[float, dict]:
    fit_score = float(row.get("fit_score_num") or 0.0)
    status = str(row.get("status") or "").strip().lower()
    in_latest_run = bool(row.get("in_latest_run"))

    days_old = 999
    date_found = str(row.get("date_found") or "").strip()
    if len(date_found) >= 10:
        try:
            days_old = max(0, (date.today() - datetime.strptime(date_found[:10], "%Y-%m-%d").date()).days)
        except ValueError:
            pass

    fit_component = fit_score * 10.0
    freshness_component = max(0.0, 14.0 - (days_old * 1.5)) if days_old != 999 else 0.0
    latest_run_component = 4.0 if in_latest_run else 0.0
    readiness_component = 5.0 if status == "generated" else 2.0 if status == "promoted" else 0.0
    total = fit_component + freshness_component + latest_run_component + readiness_component

    return total, {
        "fit_component": round(fit_component, 2),
        "freshness_component": round(freshness_component, 2),
        "latest_run_component": round(latest_run_component, 2),
        "readiness_component": round(readiness_component, 2),
        "days_old": days_old if days_old != 999 else "",
    }


def main() -> int:
    latest_manifest_path, latest_manifest = _latest_discovery_manifest()
    latest_run_name = latest_manifest_path.parent.name if latest_manifest_path else ""
    latest_urls = {
        str(job.get("url") or "").strip()
        for job in latest_manifest.get("accepted_jobs", [])
        if str(job.get("url") or "").strip()
    }

    df = pd.read_excel(JOBS_XLSX, sheet_name="Jobs", dtype=str).fillna("")
    df = df[df["source"].eq(SOURCE)].copy()
    df["fit_score_num"] = pd.to_numeric(df["fit_score"], errors="coerce")
    df = df[df["status"].isin(["queued", "promoted", "generated"])]
    df = df[df["fit_score_num"] >= MIN_SCORE]

    df["url_str"] = df["url"].astype(str).str.strip()
    df["in_latest_run"] = df["url_str"].isin(latest_urls)
    df["queue_bucket"] = df["in_latest_run"].map(lambda v: "new" if v else "carry")
    priority_info = df.apply(_priority_components, axis=1)
    df["priority_score"] = priority_info.map(lambda item: item[0])
    df["priority_meta"] = priority_info.map(lambda item: item[1])
    df = df.sort_values(["priority_score", "fit_score_num", "date_found"], ascending=[False, False, False])

    blocklist = _load_blocklist()
    origin_runs = _origin_runs_by_url()

    if QUEUE_DIR.exists():
        shutil.rmtree(QUEUE_DIR)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)

    ready_entries: list[dict] = []
    manual_entries: list[dict] = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        company = str(row_dict.get("company") or "")
        company_lc = company.strip().lower()
        url = str(row_dict.get("url") or "").strip()
        bucket = str(row_dict.get("queue_bucket") or "carry")
        in_latest_run = bool(row_dict.get("in_latest_run"))
        role_dir = _job_dir(JOBS_DIR, row_dict, bucket)
        reason = ""
        is_manual = False

        if company_lc in EXCLUDED_COMPANIES:
            is_manual = True
            reason = "excluded_company"
            role_dir = _job_dir(MANUAL_DIR, row_dict, bucket)
        elif _is_blocklisted(company, blocklist):
            is_manual = True
            reason = "blocklisted"
            role_dir = _job_dir(MANUAL_DIR, row_dict, bucket)

        metadata = _write_job_files(
            role_dir,
            row_dict,
            bucket=bucket,
            latest_run_name=latest_run_name,
            in_latest_run=in_latest_run,
            origin_runs=origin_runs.get(url, []),
            reason=reason,
        )
        _sync_existing_artifacts(row_dict, role_dir)

        entry = {
            "id": metadata["id"],
            "company": metadata["company"],
            "role_title": metadata["role_title"],
            "fit_score": metadata["fit_score"],
            "priority_score": str(row_dict.get("priority_score") or ""),
            "status": metadata["status"],
            "url": metadata["url"],
            "queue_bucket": bucket,
            "in_latest_run": in_latest_run,
            "latest_run": latest_run_name,
            "origin_runs": metadata["origin_runs"],
            "priority_meta": row_dict.get("priority_meta") or {},
            "folder_path": str(role_dir),
            "reason": reason,
        }
        if is_manual:
            manual_entries.append(entry)
        else:
            ready_entries.append(entry)

    for priority_rank, entry in enumerate(ready_entries, start=1):
        entry["priority_rank"] = priority_rank
        role_dir = Path(str(entry["folder_path"]))
        parent_dir = role_dir.parent
        target_parent = parent_dir.parent / f"{priority_rank:02d}_{parent_dir.name}"
        if parent_dir != target_parent:
            if target_parent.exists():
                shutil.rmtree(target_parent)
            parent_dir.rename(target_parent)
            entry["folder_path"] = str(target_parent / role_dir.name)
    for priority_rank, entry in enumerate(manual_entries, start=1):
        entry["priority_rank"] = priority_rank

    _update_folder_paths(ready_entries + manual_entries)

    priority_txt = QUEUE_DIR / "priority_order.txt"
    priority_json = QUEUE_DIR / "priority_order.json"
    latest_txt = QUEUE_DIR / "latest_run_jobs.txt"
    carry_txt = QUEUE_DIR / "carry_over_jobs.txt"
    manual_txt = QUEUE_DIR / "manual_review.txt"
    command_sh = QUEUE_DIR / "generate_command.sh"

    def _line(entry: dict) -> str:
        bucket = "NEW" if entry.get("in_latest_run") else "CARRY"
        return (
            f"{entry['priority_rank']}. [{bucket}] {entry['company']} | {entry['role_title']} | "
            f"score={entry['fit_score']} | priority={entry.get('priority_score','')} | status={entry['status']}"
        )

    priority_txt.write_text("\n".join(_line(entry) for entry in ready_entries), encoding="utf-8")
    priority_json.write_text(json.dumps(ready_entries, indent=2), encoding="utf-8")
    latest_txt.write_text(
        "\n".join(_line(entry) for entry in ready_entries if entry.get("in_latest_run")),
        encoding="utf-8",
    )
    carry_txt.write_text(
        "\n".join(_line(entry) for entry in ready_entries if not entry.get("in_latest_run")),
        encoding="utf-8",
    )
    manual_txt.write_text(
        "\n".join(
            f"{entry['priority_rank']}. {entry['company']} | {entry['role_title']} | score={entry['fit_score']} | reason={entry['reason']}"
            for entry in manual_entries
        ),
        encoding="utf-8",
    )

    companies_to_generate = [entry for entry in ready_entries if str(entry.get("status") or "").lower() != "generated"]
    script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'cd "$(dirname "$0")/../../.."',
        "",
    ]
    for entry in companies_to_generate:
        script_lines.append(f"./venv/bin/python jobs.py --no-color generate --id {entry['id']}")
    command_sh.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
    command_sh.chmod(0o755)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "queue_type": "current_apply_queue",
        "latest_discovery_run": latest_run_name,
        "ready_count": len(ready_entries),
        "manual_review_count": len(manual_entries),
        "ready_jobs": ready_entries,
        "manual_review_jobs": manual_entries,
        "files": {
            "priority_order": str(priority_txt),
            "latest_run_jobs": str(latest_txt),
            "carry_over_jobs": str(carry_txt),
            "manual_review": str(manual_txt),
            "generate_command": str(command_sh),
        },
    }
    (QUEUE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Queue: {QUEUE_DIR}")
    print(f"Latest discovery run: {latest_run_name or 'none'}")
    print(f"Ready jobs: {len(ready_entries)}")
    print(f"Manual review jobs: {len(manual_entries)}")
    print(f"Generate command: bash {command_sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
