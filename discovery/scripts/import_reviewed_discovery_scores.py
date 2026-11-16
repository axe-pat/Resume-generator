#!/usr/bin/env python3
"""Import explicitly reviewed discovery scores without invoking a paid model.

The review file is intentionally small and auditable.  This tool refuses to
write a row unless the full JD is present, deterministic eligibility still
classifies it as ``keep``, and its rubric total matches the normalized score.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs
from discovery.auto.linkedin_live import append_new_jobs
from discovery.scripts.refresh_current_apply_queue import main as refresh_apply_queue
from shared.job_eligibility import classify_discovery_job_offline


def _load_jobs_payload(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("jobs") or [])


def _validate_review(review: dict) -> None:
    if str(review.get("decision") or "").strip() != "Proceed":
        raise ValueError("reviewed imports must have decision=Proceed")
    score = float(review["fit_score"])
    match = re.search(r"Total:\s*(\d+)\s*/\s*25", str(review.get("breakdown") or ""))
    if not match:
        raise ValueError(f"missing rubric total for {review.get('url')}")
    total = int(match.group(1))
    expected = round((total / 25) * 10, 1)
    if score != expected:
        raise ValueError(f"fit score {score} does not match {total}/25 ({expected})")
    expected_category = "High Priority" if total >= 18 else "Medium Priority" if total >= 14 else "Low Priority"
    if str(review.get("category") or "") != expected_category:
        raise ValueError(f"category does not match rubric total for {review.get('url')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--artifact-prefix", default="linkedin_live_scored_reviewed")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    raw_jobs = _load_jobs_payload(args.raw)
    reviews_payload = json.loads(args.reviews.read_text(encoding="utf-8"))
    reviews = list(reviews_payload.get("reviews") or [])
    by_url = {str(row.get("url") or "").strip(): row for row in raw_jobs}

    reviewed_jobs: list[dict] = []
    for review in reviews:
        _validate_review(review)
        url = str(review.get("url") or "").strip()
        raw = by_url.get(url)
        if raw is None:
            raise ValueError(f"review URL not found in raw artifact: {url}")
        classified = classify_discovery_job_offline(raw)
        if classified.get("classification") != "keep":
            raise ValueError(
                f"deterministic eligibility is not keep for {raw.get('company')} | "
                f"{raw.get('role_title')}: {classified.get('reject_reason')}"
            )
        merged = {**classified, **review}
        merged["status"] = "queued"
        merged["classification"] = "keep"
        merged["reject_reason"] = ""
        reviewed_jobs.append(merged)

    existing = jobs.load_jobs()
    merged_df, written = append_new_jobs(existing, reviewed_jobs)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifact = ROOT / "discovery" / "auto" / "logs" / f"{args.artifact_prefix}_{stamp}.json"
    artifact_payload = {
        "review_method": reviews_payload.get("review_method") or "explicit rubric review",
        "raw_artifact": str(args.raw),
        "review_file": str(args.reviews),
        "reviewed": len(reviewed_jobs),
        "new_after_dedup": len(written),
        "dry_run": not args.write,
        "jobs": reviewed_jobs,
    }
    artifact.write_text(json.dumps(artifact_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Validated reviewed roles: {len(reviewed_jobs)}")
    print(f"New/updated after dedup: {len(written)}")
    print(f"Artifact: {artifact}")
    for row in reviewed_jobs:
        print(f"  [{row['fit_score']}] {row['company']} | {row['role_title']}")

    if not args.write:
        print("Dry run only; workbook not changed.")
        return 0

    jobs.save_jobs(merged_df)
    try:
        refresh_apply_queue([])
    except PermissionError as exc:
        print(f"Workbook saved; apply-queue refresh needs separate host permission: {exc}")
    print(f"Workbook updated: {jobs.JOBS_XLSX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
