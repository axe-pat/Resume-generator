#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"


def _latest_file(pattern: str, directory: Path) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {directory / pattern}")
    return matches[-1]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _job_key(item: dict[str, Any]) -> str:
    url = _clean(item.get("url"))
    if url:
        return f"url:{url.lower()}"
    return f"ct:{_clean(item.get('company')).lower()}|{_clean(item.get('role_title')).lower()}"


def _org_key(item: dict[str, Any]) -> str:
    url = _clean(item.get("company_url") or item.get("source_item_url") or item.get("website"))
    if url:
        return f"url:{url.lower()}"
    return f"name:{_clean(item.get('organization_name')).lower()}"


def _collect_jobs(
    source_breadth: dict[str, Any],
    startup_report: dict[str, Any],
    verdicts: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, classified in source_breadth.get("classified", {}).items():
        for verdict in verdicts:
            for item in classified.get(verdict) or []:
                row = dict(item)
                row["lane_source"] = f"linkedin_breadth:{source_name}"
                rows.append(row)

    for item in startup_report.get("startup_apply", {}).get("items") or []:
        if item.get("verdict") not in verdicts:
            continue
        row = dict(item)
        row["lane_source"] = f"startup_apply:{item.get('source_id') or item.get('source') or 'unknown'}"
        rows.append(row)

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _job_key(row)
        if key not in deduped:
            deduped[key] = row
            continue
        existing = deduped[key]
        existing["lane_source"] = f"{existing['lane_source']};{row['lane_source']}"
    return list(deduped.values())


def _collect_relationship_targets(
    source_breadth: dict[str, Any],
    startup_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for source_name, classified in source_breadth.get("classified", {}).items():
        for item in classified.get("outreach_signal") or []:
            rows.append(
                {
                    "kind": "job_signal",
                    "lane_source": f"linkedin_breadth:{source_name}",
                    "organization_name": _clean(item.get("company")),
                    "signal_title": _clean(item.get("role_title")),
                    "url": _clean(item.get("url")),
                    "relationship_score": 0,
                    "reasons": item.get("reasons") or [],
                }
            )

    for item in startup_report.get("startup_apply", {}).get("items") or []:
        if item.get("verdict") != "outreach_signal":
            continue
        rows.append(
            {
                "kind": "job_signal",
                "lane_source": f"startup_apply:{item.get('source_id') or item.get('source') or 'unknown'}",
                "organization_name": _clean(item.get("company")),
                "signal_title": _clean(item.get("role_title")),
                "url": _clean(item.get("url")),
                "relationship_score": 0,
                "reasons": item.get("reasons") or [],
            }
        )

    for item in startup_report.get("relationship_lane", {}).get("items") or []:
        row = dict(item)
        row["kind"] = "org_signal"
        row["lane_source"] = f"startup_org:{item.get('source_id') or 'unknown'}"
        rows.append(row)

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _org_key(row)
        if key not in deduped:
            deduped[key] = row
            continue
        existing = deduped[key]
        existing["lane_source"] = f"{existing['lane_source']};{row['lane_source']}"
        existing["relationship_score"] = max(
            int(existing.get("relationship_score") or 0),
            int(row.get("relationship_score") or 0),
        )
    return sorted(
        deduped.values(),
        key=lambda item: (
            int(item.get("relationship_score") or 0),
            _clean(item.get("organization_name")).lower(),
        ),
        reverse=True,
    )


def _counts_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_clean(item.get(key)) for item in items if _clean(item.get(key))).most_common())


def _top_jobs(items: list[dict[str, Any]], limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items[:limit]:
        rows.append(
            {
                "company": _clean(item.get("company")),
                "role_title": _clean(item.get("role_title")),
                "url": _clean(item.get("url")),
                "lane_source": _clean(item.get("lane_source")),
                "reasons": "; ".join(item.get("reasons") or []),
            }
        )
    return rows


def _top_relationships(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items[:limit]:
        rows.append(
            {
                "organization_name": _clean(item.get("organization_name")),
                "relationship_score": int(item.get("relationship_score") or 0),
                "lane_source": _clean(item.get("lane_source")),
                "city": _clean(item.get("city") or item.get("location")),
                "company_url": _clean(item.get("company_url") or item.get("source_item_url") or item.get("url")),
                "signal_title": _clean(item.get("signal_title")),
                "reasons": "; ".join(item.get("reasons") or []),
            }
        )
    return rows


def _build_payload(
    *,
    source_breadth_path: Path,
    startup_report_path: Path,
    top_limit: int,
) -> dict[str, Any]:
    source_breadth = _load_json(source_breadth_path)
    startup_report = _load_json(startup_report_path)
    app_score_now = _collect_jobs(source_breadth, startup_report, ("app_score_now",))
    app_review = _collect_jobs(source_breadth, startup_report, ("app_review", "unsure"))
    unsure = _collect_jobs(source_breadth, startup_report, ("unsure",))
    relationship_targets = _collect_relationship_targets(source_breadth, startup_report)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "source_breadth": str(source_breadth_path),
            "startup_source_report": str(startup_report_path),
        },
        "summary": {
            "app_score_now": len(app_score_now),
            "app_review": len(app_review),
            "unsure": len(unsure),
            "relationship_targets": len(relationship_targets),
            "skip_noise": _skip_noise_count(source_breadth, startup_report),
        },
        "application_lane": {
            "score_now_count": len(app_score_now),
            "review_count": len(app_review),
            "score_now_by_source": _counts_by(app_score_now, "lane_source"),
            "review_by_source": _counts_by(app_review, "lane_source"),
            "score_now": _top_jobs(app_score_now, top_limit),
            "review": _top_jobs(app_review, top_limit),
            "unsure_count": len(unsure),
            "unsure": _top_jobs(unsure, top_limit),
        },
        "relationship_lane": {
            "target_count": len(relationship_targets),
            "targets_by_source": _counts_by(relationship_targets, "lane_source"),
            "top_targets": _top_relationships(relationship_targets, top_limit),
        },
        "source_health": {
            "linkedin_breadth_raw_counts": source_breadth.get("raw_counts", {}),
            "linkedin_breadth_jobspy_only": (
                source_breadth.get("classified", {}).get("jobspy_only", {}).get("verdict_counts", {})
            ),
            "startup_apply_discovered": startup_report.get("startup_apply", {}).get("discovered_counts", {}),
            "startup_apply_verdicts": startup_report.get("startup_apply", {}).get("verdict_counts", {}),
            "relationship_source_counts": startup_report.get("relationship_lane", {}).get("source_counts", {}),
        },
        "policy": [
            "Score app_score_now candidates in the application lane.",
            "Triage app_review before normal scoring.",
            "Review unsure rows separately; their titles are unknown but their JDs contain target signals.",
            "Send relationship_targets to Outreach/contact enrichment.",
            "Do not spend API calls on skip_noise.",
        ],
    }


def _skip_noise_count(source_breadth: dict[str, Any], startup_report: dict[str, Any]) -> int:
    total = 0
    for classified in source_breadth.get("classified", {}).values():
        total += int(classified.get("skip_noise_count") or 0)
    for item in startup_report.get("startup_apply", {}).get("items") or []:
        if item.get("verdict") == "skip_noise":
            total += 1
    return total


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Daily Source Dashboard",
        "",
        f"Generated: {payload['generated_at']}",
        f"Source breadth: `{payload['inputs']['source_breadth']}`",
        f"Startup source report: `{payload['inputs']['startup_source_report']}`",
        "",
        "## Summary",
        "",
        f"- App score now: {summary['app_score_now']}",
        f"- App review: {summary['app_review']}",
        f"- Unsure (unknown title, JD signals): {summary['unsure']}",
        f"- Relationship targets: {summary['relationship_targets']}",
        f"- Skip noise: {summary['skip_noise']}",
        "",
        "## Application Lane",
        "",
        f"- Score now by source: {payload['application_lane']['score_now_by_source']}",
        f"- Review by source: {payload['application_lane']['review_by_source']}",
        "",
        "### Score now",
        "",
    ]
    for item in payload["application_lane"]["score_now"]:
        lines.append(f"- {item['company']} | {item['role_title']} | {item['url']}")
        lines.append(f"  - {item['lane_source']}")
    if not payload["application_lane"]["score_now"]:
        lines.append("- None")

    lines.extend(["", "### Review", ""])
    for item in payload["application_lane"]["review"]:
        lines.append(f"- {item['company']} | {item['role_title']} | {item['url']}")
        lines.append(f"  - {item['lane_source']}")
    if not payload["application_lane"]["review"]:
        lines.append("- None")

    lines.extend(["", "### Unsure", ""])
    for item in payload["application_lane"]["unsure"]:
        lines.append(f"- {item['company']} | {item['role_title']} | {item['url']}")
        lines.append(f"  - {item['lane_source']}")
        if item["reasons"]:
            lines.append(f"  - {item['reasons']}")
    if not payload["application_lane"]["unsure"]:
        lines.append("- None")

    lines.extend(["", "## Relationship Lane", ""])
    lines.append(f"- Targets by source: {payload['relationship_lane']['targets_by_source']}")
    lines.append("")
    for item in payload["relationship_lane"]["top_targets"]:
        title = f" | {item['signal_title']}" if item["signal_title"] else ""
        lines.append(
            f"- [{item['relationship_score']}] {item['organization_name']}{title} "
            f"| {item['city']} | {item['company_url']}"
        )
        lines.append(f"  - {item['lane_source']}")

    lines.extend(
        [
            "",
            "## Source Health",
            "",
            f"- LinkedIn raw counts: {payload['source_health']['linkedin_breadth_raw_counts']}",
            f"- JobSpy-only verdicts: {payload['source_health']['linkedin_breadth_jobspy_only']}",
            f"- Startup apply discovered: {payload['source_health']['startup_apply_discovered']}",
            f"- Startup apply verdicts: {payload['source_health']['startup_apply_verdicts']}",
            f"- Relationship source counts: {payload['source_health']['relationship_source_counts']}",
            "",
            "## Policy",
            "",
        ]
    )
    for item in payload["policy"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a no-write daily source dashboard from validation artifacts.")
    parser.add_argument("--source-breadth", type=Path)
    parser.add_argument("--startup-source-report", type=Path)
    parser.add_argument("--out-dir", type=Path, default=SOURCE_VALIDATION_DIR)
    parser.add_argument("--top-limit", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_breadth_path = args.source_breadth or _latest_file("*source-breadth-filtered.json", SOURCE_VALIDATION_DIR)
    startup_report_path = args.startup_source_report or _latest_file("*startup-source-report.json", SOURCE_VALIDATION_DIR)
    payload = _build_payload(
        source_breadth_path=source_breadth_path,
        startup_report_path=startup_report_path,
        top_limit=max(args.top_limit, 1),
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = args.out_dir / f"{stamp}-daily-source-dashboard.json"
    md_path = args.out_dir / f"{stamp}-daily-source-dashboard.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(md_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    print(f"summary: {payload['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
