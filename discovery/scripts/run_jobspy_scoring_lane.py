#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs as resume_jobs  # noqa: E402
from discovery.scripts.validate_source_breadth import linkedin_job_key, load_jobs, normalize  # noqa: E402

if str(ROOT / "discovery" / "auto") not in sys.path:
    sys.path.insert(0, str(ROOT / "discovery" / "auto"))

from discovery.auto.linkedin_live import (  # noqa: E402
    DEFAULT_MODEL,
    _run_post_extract_pipeline,
    title_company_hash,
    url_hash,
)


def _latest_file(pattern: str, directory: Path) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {directory / pattern}")
    return matches[-1]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _candidate_key(item: dict[str, Any]) -> str:
    url = _clean(item.get("url"))
    if url:
        return linkedin_job_key({"url": url, "company": item.get("company"), "role_title": item.get("role_title")})
    return f"ct:{normalize(item.get('company'))}|{normalize(item.get('role_title'))}"


def _raw_job_index(raw_jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for job in raw_jobs:
        indexed[linkedin_job_key(job)] = job
        url = _clean(job.get("url"))
        if url:
            indexed[f"url:{url.lower().rstrip('/')}"] = job
    return indexed


def _selected_classified_jobs(
    source_breadth: dict[str, Any],
    *,
    include_review: bool,
    include_overlap: bool,
) -> list[dict[str, Any]]:
    verdicts = ["app_score_now"]
    if include_review:
        verdicts.append("app_review")

    buckets = ["jobspy_only"]
    if include_overlap:
        buckets.append("overlap")

    selected: list[dict[str, Any]] = []
    for bucket in buckets:
        classified = source_breadth.get("classified", {}).get(bucket, {})
        for verdict in verdicts:
            for item in classified.get(verdict) or []:
                row = dict(item)
                row["source_bucket"] = bucket
                row["source_verdict"] = verdict
                selected.append(row)
    return selected


def _to_score_job(raw: dict[str, Any], classified: dict[str, Any]) -> dict[str, Any]:
    company = _clean(classified.get("company")) or _clean(raw.get("company"))
    role = _clean(classified.get("role_title")) or _clean(raw.get("role_title") or raw.get("title"))
    url = _clean(classified.get("url")) or _clean(raw.get("url"))
    notes = " ".join(
        value
        for value in [
            _clean(raw.get("notes")),
            "tag=jobspy_filtered_v1",
            f"source_bucket={_clean(classified.get('source_bucket'))}",
            f"source_verdict={_clean(classified.get('source_verdict'))}",
            f"filter_reasons={'; '.join(classified.get('reasons') or [])}",
        ]
        if value
    )
    return {
        **raw,
        "id": None,
        "date_found": _clean(raw.get("date_found")) or datetime.now().strftime("%Y-%m-%d"),
        "company": company,
        "role_title": role,
        "role_type": _clean(raw.get("role_type")) or "Other",
        "location": _clean(raw.get("location")),
        "url": url,
        "url_hash": _clean(raw.get("url_hash")) or (url_hash(url) if url else ""),
        "source": "jobspy_filtered_v1",
        "fit_score": None,
        "fit_rationale": None,
        "status": "new",
        "date_applied": None,
        "folder_path": None,
        "jd_text": _clean(raw.get("jd_text")),
        "notes": notes,
        "tc_hash": _clean(raw.get("tc_hash")) or title_company_hash(role, company),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score hard-filtered JobSpy breadth candidates through the normal write gate.")
    parser.add_argument("--source-breadth", type=Path, default=None)
    parser.add_argument("--jobspy-raw", type=Path, default=None)
    parser.add_argument("--include-review", action="store_true", help="Also score app_review candidates, not just app_score_now.")
    parser.add_argument("--include-overlap", action="store_true", help="Also score JobSpy/Playwright overlap candidates from the breadth report.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum filtered candidates to score.")
    parser.add_argument("--dry-run", action="store_true", help="Score and report without writing jobs.xlsx.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_breadth_path = args.source_breadth or _latest_file("*source-breadth-filtered.json", SOURCE_VALIDATION_DIR)
    source_breadth = _load_json(source_breadth_path)
    jobspy_raw_path = args.jobspy_raw or Path(source_breadth.get("inputs", {}).get("jobspy_raw") or "")
    if not jobspy_raw_path:
        jobspy_raw_path = _latest_file("jobspy_linkedin_equiv_raw_24h_*.json", LOGS_DIR)
    if not jobspy_raw_path.is_absolute():
        jobspy_raw_path = ROOT / jobspy_raw_path

    raw_jobs = load_jobs(jobspy_raw_path)
    raw_by_key = _raw_job_index(raw_jobs)
    blocklist = resume_jobs._load_blocklist()

    selected: list[dict[str, Any]] = []
    skipped_blocklist: list[str] = []
    missing_raw: list[str] = []
    missing_jd: list[str] = []
    seen: set[str] = set()
    for classified in _selected_classified_jobs(
        source_breadth,
        include_review=args.include_review,
        include_overlap=args.include_overlap,
    ):
        key = _candidate_key(classified)
        if key in seen:
            continue
        seen.add(key)
        raw = raw_by_key.get(key) or raw_by_key.get(f"url:{_clean(classified.get('url')).lower().rstrip('/')}")
        label = f"{_clean(classified.get('company'))} | {_clean(classified.get('role_title'))}"
        if not raw:
            missing_raw.append(label)
            continue
        if resume_jobs._is_blocklisted(_clean(classified.get("company") or raw.get("company")), blocklist):
            skipped_blocklist.append(label)
            continue
        job = _to_score_job(raw, classified)
        if not _clean(job.get("jd_text")):
            missing_jd.append(label)
            continue
        selected.append(job)
        if args.limit > 0 and len(selected) >= args.limit:
            break

    if not args.quiet:
        print(f"Source breadth: {source_breadth_path}")
        print(f"JobSpy raw: {jobspy_raw_path}")
        print(f"Filtered candidates selected for scoring: {len(selected)}")
        print(f"Skipped blocklist before scoring: {len(skipped_blocklist)}")
        print(f"Missing raw matches: {len(missing_raw)}")
        print(f"Missing JD text: {len(missing_jd)}")
        for job in selected:
            print(f"- {job['company']} | {job['role_title']} | {job['url']}")

    if not selected:
        print("No JobSpy candidates survived the scoring-lane preflight.")
        return 0

    _run_post_extract_pipeline(
        run_label="jobspy_filtered_24h",
        searches=[("JobSpy filtered app_score_now", "24h")],
        search_runs=[
            {
                "search_term": "JobSpy filtered app_score_now",
                "time_filter": "24h",
                "extracted_count": len(selected),
                "route_used": "source-breadth-filtered",
            }
        ],
        jobs=selected,
        extracted_count=len(selected),
        dry_run=args.dry_run,
        model=args.model,
        quiet=args.quiet,
        max_workers=args.max_workers,
        source_raw_artifacts=[str(source_breadth_path), str(jobspy_raw_path)],
        artifact_prefix="jobspy_filtered",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
