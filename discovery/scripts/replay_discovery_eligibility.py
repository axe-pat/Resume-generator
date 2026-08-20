#!/usr/bin/env python3
"""Offline replay of deterministic discovery rules over discovery/jobs.xlsx."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_DIR = ROOT / "discovery"
JOBS_XLSX = DISCOVERY_DIR / "jobs.xlsx"
OUTPUT_DIR = DISCOVERY_DIR / "source_validation"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.job_eligibility import classify_discovery_job_offline  # noqa: E402


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return value


def _row_dict(row: pd.Series) -> dict[str, Any]:
    return {str(key): _clean(value) for key, value in row.to_dict().items()}


def _reason_for(classified: dict[str, Any]) -> str:
    classification = str(classified.get("classification") or "").strip().lower()
    if classification in {"reject", "unsure"}:
        return str(classified.get("reject_reason") or "Unspecified").strip()
    return str(classified.get("discovery_reason") or "Passed deterministic eligibility rules").strip()


def replay(path: Path = JOBS_XLSX) -> dict[str, Any]:
    frame = pd.read_excel(path, sheet_name="Jobs", dtype=str)
    rows: list[dict[str, Any]] = []
    split: Counter[str] = Counter()
    lane_split: dict[str, Counter[str]] = defaultdict(Counter)
    reasons: dict[str, Counter[str]] = defaultdict(Counter)

    for zero_index, (_, source_row) in enumerate(frame.iterrows()):
        job = _row_dict(source_row)
        classified = classify_discovery_job_offline(job)
        classification = str(classified.get("classification") or "unsure").strip().lower()
        if classification not in {"keep", "reject", "unsure"}:
            classification = "unsure"
        lane = str(classified.get("lane") or "A").strip().upper()
        reason = _reason_for(classified)

        split[classification] += 1
        lane_split[lane][classification] += 1
        reasons[classification][reason] += 1
        rows.append(
            {
                "excel_row": zero_index + 2,
                "id": str(job.get("id") or ""),
                "company": str(job.get("company") or ""),
                "role_title": str(job.get("role_title") or ""),
                "url": str(job.get("url") or ""),
                "lane": lane,
                "deadline": str(classified.get("deadline") or ""),
                "deadline_source": str(classified.get("deadline_source") or ""),
                "everify_status": str(classified.get("everify_status") or ""),
                "sponsorship_flag": str(classified.get("sponsorship_flag") or ""),
                "classification": classification,
                "reject_reason": reason if classification in {"reject", "unsure"} else "",
                "classification_reason": reason,
                "notes_clean": str(classified.get("notes") or ""),
            }
        )

    def target_rows(company_pattern: str, title_pattern: str) -> list[dict[str, Any]]:
        company_pattern = company_pattern.lower()
        title_pattern = title_pattern.lower()
        return [
            row for row in rows
            if company_pattern in row["company"].lower()
            and title_pattern in row["role_title"].lower()
        ]

    report = {
        "schema": "resume_generator.discovery_existing_replay",
        "version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_workbook": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "row_count": len(rows),
        "classification_split": dict(split),
        "lane_split": {lane: dict(counts) for lane, counts in sorted(lane_split.items())},
        "reason_counts": {
            classification: dict(counts.most_common())
            for classification, counts in reasons.items()
        },
        "required_checks": {
            "salesforce_summer_2027_apm": target_rows(
                "Salesforce", "Summer 2027 Intern - Associate Product Manager"
            ),
            "amazon_2027_mldp_intern": target_rows(
                "Amazon", "2027 MBA Leadership Development Program (MLDP) Intern"
            ),
        },
        "existing_program_watch": {
            "google_apm": [
                row for row in rows
                if "google" in row["company"].lower()
                and ("associate product manager" in row["role_title"].lower()
                     or "apm" in row["role_title"].lower())
            ],
            "meta_rpm": [
                row for row in rows
                if row["company"].strip().lower() in {"meta", "facebook"}
                and ("rotational product manager" in row["role_title"].lower()
                     or "rpm" in row["role_title"].lower())
            ],
        },
        "unsure_review": [row for row in rows if row["classification"] == "unsure"],
        "rows": rows,
    }
    return report


def _markdown(report: dict[str, Any]) -> str:
    split = report["classification_split"]
    lines = [
        "# Existing jobs eligibility replay",
        "",
        f"Generated: {report['generated_at']}",
        f"Rows: {report['row_count']}",
        f"Workbook SHA-256: `{report['source_sha256']}`",
        "",
        "## Classification split",
        "",
        f"- Keep: {split.get('keep', 0)}",
        f"- Reject: {split.get('reject', 0)}",
        f"- Unsure: {split.get('unsure', 0)}",
        "",
        "## Lane split",
        "",
    ]
    for lane, counts in report["lane_split"].items():
        lines.append(
            f"- Lane {lane}: keep={counts.get('keep', 0)}, "
            f"reject={counts.get('reject', 0)}, unsure={counts.get('unsure', 0)}"
        )

    for classification in ("reject", "unsure", "keep"):
        lines += ["", f"## {classification.title()} reasons", ""]
        for reason, count in report["reason_counts"].get(classification, {}).items():
            lines.append(f"- {count}: {reason}")

    lines += ["", "## Required row checks", ""]
    for label, matches in report["required_checks"].items():
        lines.append(f"### {label}")
        if not matches:
            lines.append("- Not found")
        for row in matches:
            lines.append(
                f"- {row['company']} — {row['role_title']}: "
                f"{row['classification']} — {row['classification_reason']}"
            )

    lines += ["", "## Unsure review", ""]
    if not report["unsure_review"]:
        lines.append("- None")
    for row in report["unsure_review"]:
        lines.append(
            f"- {row['company']} — {row['role_title']} — {row['classification_reason']} — {row['url']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=JOBS_XLSX)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    args = parser.parse_args()

    report = replay(args.workbook)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_json = args.output_json or OUTPUT_DIR / f"{timestamp}-discovery-2027-existing-replay.json"
    output_md = args.output_md or OUTPUT_DIR / f"{timestamp}-discovery-2027-existing-replay.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    output_md.write_text(_markdown(report), encoding="utf-8")

    print(json.dumps({
        "row_count": report["row_count"],
        "classification_split": report["classification_split"],
        "lane_split": report["lane_split"],
        "required_checks": report["required_checks"],
        "unsure_count": len(report["unsure_review"]),
        "output_json": str(output_json),
        "output_md": str(output_md),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
