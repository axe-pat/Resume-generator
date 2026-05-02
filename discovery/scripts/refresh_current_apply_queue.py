#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs

from discovery.scripts.build_linkedin_apply_queue import (
    EXCLUDED_COMPANIES,
    MIN_SCORE,
    _dir_slug,
    _is_blocklisted,
    _load_blocklist,
)
from shared.discovery_sources import APPLY_QUEUE_SOURCES, queue_company_label

APPS_DIR = ROOT / "apps"
RUNS_DIR = APPS_DIR / "runs"
APPLY_QUEUES_DIR = APPS_DIR / "Apply queues"
ARCHIVE_DIR = APPS_DIR / "archive"
DISCOVERY_ARCHIVE_DIR = ARCHIVE_DIR / "discovery_runs"
QUEUE_DIR = APPLY_QUEUES_DIR / "current_apply_queue"
QUEUE_TMP_DIR = APPLY_QUEUES_DIR / ".current_apply_queue_tmp"
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
    company = _dir_slug(
        queue_company_label(
            str(row.get("company") or ""),
            str(row.get("source") or ""),
        )
    )
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
            target.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(child, target)
        else:
            # Queue refresh should preserve generated artifacts, but the freshly
            # written queue metadata/intel files are the source of truth for the
            # rebuilt surface. Do not let copied historical artifacts overwrite
            # them with stale values like company="Unknown".
            if child.name in {"metadata.json", "intel.txt"} and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
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


def _normalize_tmp_queue_path(path_str: str) -> str:
    raw = str(path_str or "").strip()
    if not raw:
        return raw
    return raw.replace(str(QUEUE_TMP_DIR), str(QUEUE_DIR))


def _archived_queue_metadata_index() -> dict[str, list[Path]]:
    roots = [ARCHIVE_DIR / "stale_apply_queues", APPLY_QUEUES_DIR]
    indexed: dict[str, list[Path]] = {}
    for root in roots:
        if not root.exists():
            continue
        for metadata_path in root.rglob("metadata.json"):
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            row_id = str(data.get("id") or "").strip()
            if not row_id:
                continue
            indexed.setdefault(row_id, [])
            role_dir = metadata_path.parent
            if role_dir not in indexed[row_id]:
                indexed[row_id].append(role_dir)
    return indexed


def _archived_top_level_company_index() -> dict[str, list[Path]]:
    roots = [ARCHIVE_DIR / "redundant_top_level"]
    indexed: dict[str, list[Path]] = {}
    for root in roots:
        if not root.exists():
            continue
        for company_dir in root.rglob("*"):
            if not company_dir.is_dir():
                continue
            if company_dir.name in {"redundant_top_level"}:
                continue
            if (company_dir / "jd.txt").exists() or (company_dir / "strategy.json").exists():
                key = _dir_slug(company_dir.name).lower()
                indexed.setdefault(key, [])
                if company_dir not in indexed[key]:
                    indexed[key].append(company_dir)
    return indexed


def _artifact_source_candidates(
    row: dict,
    *,
    queue_metadata_index: dict[str, list[Path]],
    top_level_company_index: dict[str, list[Path]],
) -> list[Path]:
    candidates: list[Path] = []

    def _add(path: Path | None) -> None:
        if path is None:
            return
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if not resolved.exists():
            return
        if resolved not in candidates:
            candidates.append(resolved)

    src_str = str(row.get("folder_path") or "").strip()
    if src_str:
        _add(Path(src_str))

    row_id = str(row.get("id") or "").strip()
    for path in queue_metadata_index.get(row_id, []):
        _add(path)

    company_key = _dir_slug(str(row.get("company") or "")).lower()
    for path in top_level_company_index.get(company_key, []):
        _add(path)

    return candidates


def _sync_existing_artifacts(candidate_dirs: list[Path], target_dir: Path) -> None:
    if not candidate_dirs:
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for src in candidate_dirs:
        if not src.exists():
            continue
        if src.resolve() == target_dir.resolve():
            continue
        _copy_tree_contents(src, target_dir)


def _cleanup_redundant_top_level_dirs(entries: list[dict]) -> list[Path]:
    removed: list[Path] = []
    seen: set[Path] = set()
    for entry in entries:
        company_slug = _dir_slug(str(entry.get("company") or ""))
        if not company_slug:
            continue
        top_level_dir = APPS_DIR / company_slug
        if top_level_dir in seen or not top_level_dir.exists() or not top_level_dir.is_dir():
            continue
        seen.add(top_level_dir)
        shutil.rmtree(top_level_dir)
        removed.append(top_level_dir)
    return removed


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


def _load_manual_queue_entries() -> list[dict]:
    priority_json = QUEUE_DIR / "priority_order.json"
    if not priority_json.exists():
        return []
    try:
        entries = json.loads(priority_json.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(entries, list):
        return []

    manual_entries: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row_id = str(entry.get("id") or "").strip()
        folder_path = str(entry.get("folder_path") or "").strip()
        company = str(entry.get("company") or "").strip()
        role_title = str(entry.get("role_title") or "").strip()
        if not row_id.startswith("manual-") or not folder_path:
            continue
        role_dir = Path(folder_path)
        if not role_dir.exists():
            continue
        manual_entries.append(
            {
                "id": row_id,
                "company": company,
                "role_title": role_title,
                "fit_score": str(entry.get("fit_score") or ""),
                "priority_score": str(entry.get("priority_score") or ""),
                "status": str(entry.get("status") or "manual_queue"),
                "url": str(entry.get("url") or ""),
                "queue_bucket": str(entry.get("queue_bucket") or "manual"),
                "in_latest_run": bool(entry.get("in_latest_run")),
                "latest_run": str(entry.get("latest_run") or "manual"),
                "origin_runs": entry.get("origin_runs") or ["manual"],
                "priority_meta": entry.get("priority_meta") or {},
                "folder_path": str(role_dir),
                "reason": str(entry.get("reason") or "manual_queue"),
            }
        )
    return manual_entries


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
    df = df[df["source"].isin(APPLY_QUEUE_SOURCES)].copy()
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

    queue_metadata_index = _archived_queue_metadata_index()
    top_level_company_index = _archived_top_level_company_index()

    if QUEUE_TMP_DIR.exists():
        shutil.rmtree(QUEUE_TMP_DIR)
    temp_jobs_dir = QUEUE_TMP_DIR / "jobs"
    temp_manual_dir = QUEUE_TMP_DIR / "manual_review"
    temp_jobs_dir.mkdir(parents=True, exist_ok=True)
    temp_manual_dir.mkdir(parents=True, exist_ok=True)

    ready_entries: list[dict] = []
    manual_entries: list[dict] = []

    preserved_manual_entries = _load_manual_queue_entries()
    for manual_entry in preserved_manual_entries:
        source_dir = Path(str(manual_entry["folder_path"]))
        role_dir = _job_dir(temp_jobs_dir, {
            "company": manual_entry["company"],
            "role_title": manual_entry["role_title"],
            "date_found": date.today().isoformat(),
            "fit_score": manual_entry["fit_score"],
        }, "manual")
        _sync_existing_artifacts([source_dir], role_dir)
        # Refresh metadata/intel after copying artifacts so the rebuilt queue
        # stays self-consistent.
        metadata = _write_job_files(
            role_dir,
            {
                "id": manual_entry["id"],
                "company": manual_entry["company"],
                "role_title": manual_entry["role_title"],
                "fit_score": manual_entry["fit_score"],
                "status": manual_entry["status"],
                "url": manual_entry["url"],
                "date_found": date.today().isoformat(),
                "priority_score": manual_entry["priority_score"],
                "notes": f"manual_queue=true reason={manual_entry['reason']}",
            },
            bucket="manual",
            latest_run_name=str(manual_entry.get("latest_run") or "manual"),
            in_latest_run=False,
            origin_runs=list(manual_entry.get("origin_runs") or ["manual"]),
            reason=str(manual_entry.get("reason") or "manual_queue"),
        )
        manual_entry["folder_path"] = str(role_dir)
        manual_entry["status"] = metadata["status"]
        ready_entries.append(manual_entry)

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        company = str(row_dict.get("company") or "")
        company_lc = company.strip().lower()
        url = str(row_dict.get("url") or "").strip()
        bucket = str(row_dict.get("queue_bucket") or "carry")
        in_latest_run = bool(row_dict.get("in_latest_run"))
        role_dir = _job_dir(temp_jobs_dir, row_dict, bucket)
        reason = ""
        is_manual = False

        if company_lc in EXCLUDED_COMPANIES:
            is_manual = True
            reason = "excluded_company"
            role_dir = _job_dir(temp_manual_dir, row_dict, bucket)
        elif _is_blocklisted(company, blocklist):
            is_manual = True
            reason = "blocklisted"
            role_dir = _job_dir(temp_manual_dir, row_dict, bucket)

        metadata = _write_job_files(
            role_dir,
            row_dict,
            bucket=bucket,
            latest_run_name=latest_run_name,
            in_latest_run=in_latest_run,
            origin_runs=origin_runs.get(url, []),
            reason=reason,
        )
        _sync_existing_artifacts(
            _artifact_source_candidates(
                row_dict,
                queue_metadata_index=queue_metadata_index,
                top_level_company_index=top_level_company_index,
            ),
            role_dir,
        )

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

    # Several tracker rows can share one parent folder (e.g. company="Unknown" + same
    # date/fit bucket). Rename each physical parent once using the best (min) rank in
    # that group — otherwise the second rename raises FileNotFoundError.
    parent_buckets: defaultdict[Path, list[dict]] = defaultdict(list)
    for entry in ready_entries:
        role_dir = Path(str(entry["folder_path"]))
        parent_buckets[role_dir.parent].append(entry)

    for parent_dir, entries in parent_buckets.items():
        min_rank = min(int(e["priority_rank"]) for e in entries)
        sample_role = Path(str(entries[0]["folder_path"])).name
        target_parent = parent_dir.parent / f"{min_rank:02d}_{parent_dir.name}"
        if parent_dir != target_parent:
            if target_parent.exists():
                shutil.rmtree(target_parent)
            parent_dir.rename(target_parent)
            new_parent = target_parent
        else:
            new_parent = parent_dir
        for entry in entries:
            entry["folder_path"] = str(new_parent / Path(str(entry["folder_path"])).name)
    for priority_rank, entry in enumerate(manual_entries, start=1):
        entry["priority_rank"] = priority_rank

    for entry in ready_entries + manual_entries:
        entry["folder_path"] = _normalize_tmp_queue_path(str(entry.get("folder_path") or ""))

    _update_folder_paths(ready_entries + manual_entries)

    priority_txt = QUEUE_TMP_DIR / "priority_order.txt"
    priority_json = QUEUE_TMP_DIR / "priority_order.json"
    latest_txt = QUEUE_TMP_DIR / "latest_run_jobs.txt"
    carry_txt = QUEUE_TMP_DIR / "carry_over_jobs.txt"
    manual_txt = QUEUE_TMP_DIR / "manual_review.txt"
    command_sh = QUEUE_TMP_DIR / "generate_command.sh"
    final_priority_txt = QUEUE_DIR / "priority_order.txt"
    final_priority_json = QUEUE_DIR / "priority_order.json"
    final_latest_txt = QUEUE_DIR / "latest_run_jobs.txt"
    final_carry_txt = QUEUE_DIR / "carry_over_jobs.txt"
    final_manual_txt = QUEUE_DIR / "manual_review.txt"
    final_command_sh = QUEUE_DIR / "generate_command.sh"

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
        "export RUN_APP_SEQUENTIAL=1",
        "",
        "./venv/bin/python jobs.py --no-color generate --queue --queue-path 'apps/Apply queues/current_apply_queue/priority_order.json'",
    ]
    command_sh.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
    command_sh.chmod(0o755)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "queue_type": "current_apply_queue",
        "sources": sorted(APPLY_QUEUE_SOURCES),
        "latest_discovery_run": latest_run_name,
        "ready_count": len(ready_entries),
        "manual_review_count": len(manual_entries),
        "ready_jobs": ready_entries,
        "manual_review_jobs": manual_entries,
        "files": {
            "priority_order": str(final_priority_txt),
            "latest_run_jobs": str(final_latest_txt),
            "carry_over_jobs": str(final_carry_txt),
            "manual_review": str(final_manual_txt),
            "generate_command": str(final_command_sh),
        },
    }
    (QUEUE_TMP_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if QUEUE_DIR.exists():
        backup_dir = APPLY_QUEUES_DIR / ".current_apply_queue_prev"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        QUEUE_DIR.rename(backup_dir)
    QUEUE_TMP_DIR.rename(QUEUE_DIR)
    removed_dirs = _cleanup_redundant_top_level_dirs(ready_entries + manual_entries)

    print(f"Queue: {QUEUE_DIR}")
    print(f"Latest discovery run: {latest_run_name or 'none'}")
    print(f"Ready jobs: {len(ready_entries)}")
    print(f"Manual review jobs: {len(manual_entries)}")
    if removed_dirs:
        print(f"Removed redundant top-level app dirs: {len(removed_dirs)}")
    print(f"Generate command: bash {final_command_sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
