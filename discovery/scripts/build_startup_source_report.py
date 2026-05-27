#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTO_DIR = ROOT / "discovery" / "auto"
OUT_DIR = ROOT / "discovery" / "source_validation"
OUTREACH_ARTIFACTS_DIR = ROOT.parent / "Outreach" / "artifacts"

for path in (ROOT, AUTO_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import startup_apply_pipeline as startup_apply  # noqa: E402
from validate_source_breadth import classify_job  # noqa: E402


RELATIONSHIP_SOURCE_IDS = (
    "yc_sf_bay_hiring",
    "yc_los_angeles",
    "builtin_la_companies",
    "builtin_sf_companies",
)

DOMAIN_SIGNAL_RE = re.compile(
    r"\b(ai|artificial intelligence|data|developer|devtools?|api|platform|infra|"
    r"fintech|health|healthcare|healthtech|robotics|marketplace|productivity|"
    r"b2b|saas|climate|security|analytics|automation)\b",
    re.I,
)


def _url_hash(url: str) -> str:
    return startup_apply._url_hash(url)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _candidate_to_job_dict(item: startup_apply.StartupJobCandidate) -> dict[str, Any]:
    return {
        "company": item.company,
        "role_title": item.role_title,
        "location": item.location,
        "url": item.url,
        "source": item.source,
        "source_id": item.source_id,
        "date_posted": item.date_posted,
        "jd_text": item.jd_text,
        "notes": item.notes,
        "list_url": item.list_url,
    }


def _load_existing_hashes() -> set[str]:
    df_existing = startup_apply.jobs.load_jobs()
    return set(df_existing["url_hash"].dropna().astype(str).tolist())


def _classify_startup_apply(
    *,
    limit_companies: int,
    limit_jobs: int | None,
    include_sources: set[str] | None,
    ignore_existing: bool,
    verbose: bool,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    discovered, discovered_counts = startup_apply._discover_startup_jobs(
        limit_companies=limit_companies,
        include_sources=include_sources,
        verbose=verbose,
    )
    existing_hashes = set() if ignore_existing else _load_existing_hashes()
    new_items = [item for item in discovered if _url_hash(item.url) not in existing_hashes]
    new_counts: dict[str, int] = defaultdict(int)
    for item in new_items:
        new_counts[item.source_id] += 1

    ordered = sorted(new_items, key=startup_apply._startup_candidate_priority, reverse=True)
    if limit_jobs is not None:
        ordered = ordered[:limit_jobs]

    rows: list[dict[str, Any]] = []
    for item in ordered:
        job_dict = _candidate_to_job_dict(item)
        classified = classify_job(job_dict, "startup_apply")
        row = asdict(classified)
        row.update(
            {
                "source_id": item.source_id,
                "location": item.location,
                "date_posted": item.date_posted,
                "list_url": item.list_url,
                "notes": item.notes,
            }
        )
        rows.append(row)
    return rows, dict(discovered_counts), dict(new_counts)


def _latest_outreach_artifact(source_id: str, artifacts_dir: Path) -> Path | None:
    matches = sorted(
        artifacts_dir.glob(f"*-discover-{source_id}.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return matches[-1] if matches else None


def _parse_team_size(value: str) -> int | None:
    match = re.search(r"([\d,]+)", value or "")
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _relationship_score(item: dict[str, Any], source_id: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    text = " ".join(
        [
            _clean(item.get("organization_name")),
            _clean(item.get("description")),
            " ".join(_clean(tag) for tag in item.get("tags") or []),
            _clean(item.get("location")),
            _clean(item.get("city")),
        ]
    )
    source_kind = _clean(item.get("source_kind"))
    jobs_count = int(item.get("jobs_count") or 0)
    team_size = _parse_team_size(_clean(item.get("team_size")))
    location = f"{_clean(item.get('city'))} {_clean(item.get('location'))}".lower()

    if source_id.startswith("yc_") or source_kind == "yc_directory":
        score += 4
        reasons.append("YC-backed/source-quality signal")
    if jobs_count > 0 or _clean(item.get("jobs_url")):
        score += 4
        reasons.append("active hiring/jobs signal")
    if any(city in location for city in ("san francisco", "bay area", "los angeles", "remote")):
        score += 2
        reasons.append("target geography signal")
    if DOMAIN_SIGNAL_RE.search(text):
        score += 2
        reasons.append("domain fit signal")
    if team_size is not None:
        if team_size <= 250:
            score += 2
            reasons.append("small-team founder/operator access")
        elif team_size <= 1000:
            score += 1
            reasons.append("mid-size startup access")

    return score, reasons


def _load_relationship_targets(
    *,
    artifacts_dir: Path,
    source_ids: tuple[str, ...],
    limit_per_source: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    for source_id in source_ids:
        artifact = _latest_outreach_artifact(source_id, artifacts_dir)
        if artifact is None:
            artifacts[source_id] = {"artifact": "", "count": 0, "status": "missing"}
            continue
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        results = payload.get("results") or []
        artifacts[source_id] = {
            "artifact": str(artifact),
            "count": len(results),
            "status": "loaded",
        }
        for item in results:
            score, reasons = _relationship_score(item, source_id)
            targets.append(
                {
                    "verdict": "outreach_signal",
                    "source_id": source_id,
                    "relationship_score": score,
                    "reasons": reasons,
                    "organization_name": _clean(item.get("organization_name")),
                    "company_url": _clean(item.get("company_url")),
                    "jobs_url": _clean(item.get("jobs_url")),
                    "website": _clean(item.get("website")),
                    "city": _clean(item.get("city")),
                    "location": _clean(item.get("location")),
                    "team_size": _clean(item.get("team_size")),
                    "batch": _clean(item.get("batch")),
                    "tags": item.get("tags") or [],
                    "description": _clean(item.get("description")),
                    "source_item_url": _clean(item.get("source_item_url")),
                }
            )
    targets = sorted(
        targets,
        key=lambda item: (
            int(item.get("relationship_score") or 0),
            _clean(item.get("organization_name")).lower(),
        ),
        reverse=True,
    )
    if limit_per_source > 0:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for target in targets:
            bucket = grouped[target["source_id"]]
            if len(bucket) < limit_per_source:
                bucket.append(target)
        targets = sorted(
            [target for bucket in grouped.values() for target in bucket],
            key=lambda item: (
                int(item.get("relationship_score") or 0),
                _clean(item.get("organization_name")).lower(),
            ),
            reverse=True,
        )
    return targets, artifacts


def _counts_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_clean(item.get(key)) for item in items if _clean(item.get(key))).most_common())


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Startup Source Report",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Startup Apply Lane",
        "",
        f"- Discovered by source: {payload['startup_apply']['discovered_counts']}",
        f"- New after existing-job dedupe: {payload['startup_apply']['new_counts']}",
        f"- Verdicts: {payload['startup_apply']['verdict_counts']}",
        "",
    ]

    for verdict in ("app_score_now", "app_review", "outreach_signal", "skip_noise"):
        rows = [item for item in payload["startup_apply"]["items"] if item["verdict"] == verdict]
        if not rows:
            continue
        lines.append(f"### {verdict}")
        lines.append("")
        for item in rows[:25]:
            reason = "; ".join(item.get("reasons") or [])
            lines.append(f"- {item['company']} | {item['role_title']} | {item['url']}")
            if reason:
                lines.append(f"  - {reason}")
        lines.append("")

    lines.extend(
        [
            "## Relationship Org Lane",
            "",
            f"- Artifacts: {payload['relationship_lane']['artifacts']}",
            f"- Total relationship targets in report: {len(payload['relationship_lane']['items'])}",
            "",
        ]
    )
    for item in payload["relationship_lane"]["items"][:40]:
        reason = "; ".join(item.get("reasons") or [])
        lines.append(
            f"- [{item.get('relationship_score', 0)}] {item['organization_name']} "
            f"| {item.get('city') or item.get('location')} | {item.get('company_url') or item.get('source_item_url')}"
        )
        if reason:
            lines.append(f"  - {reason}")

    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Score `app_score_now` in the application lane.",
            "- Triage `app_review` before normal scoring.",
            "- Send `outreach_signal` to Outreach/contact enrichment instead of resume generation.",
            "- Keep this report no-write until the daily source mix looks stable.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a no-write startup source report.")
    parser.add_argument("--limit-companies", type=int, default=startup_apply.DEFAULT_LIMIT_COMPANIES)
    parser.add_argument("--limit-jobs", type=int, default=startup_apply.DEFAULT_LIMIT_JOBS)
    parser.add_argument("--source", action="append", default=[], help="Startup apply source_id filter, repeatable.")
    parser.add_argument("--ignore-existing", action="store_true", help="Ignore jobs.xlsx dedupe for validation.")
    parser.add_argument("--quiet", action="store_true", help="Suppress source discovery output.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--outreach-artifacts-dir", type=Path, default=OUTREACH_ARTIFACTS_DIR)
    parser.add_argument("--no-relationship-artifacts", action="store_true")
    parser.add_argument("--relationship-limit-per-source", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_sources = {value.strip() for value in args.source if value.strip()} or None
    startup_items, discovered_counts, new_counts = _classify_startup_apply(
        limit_companies=max(args.limit_companies, 1),
        limit_jobs=max(args.limit_jobs, 1) if args.limit_jobs is not None else None,
        include_sources=include_sources,
        ignore_existing=args.ignore_existing,
        verbose=not args.quiet,
    )

    relationship_items: list[dict[str, Any]] = []
    relationship_artifacts: dict[str, Any] = {}
    if not args.no_relationship_artifacts:
        relationship_items, relationship_artifacts = _load_relationship_targets(
            artifacts_dir=args.outreach_artifacts_dir,
            source_ids=RELATIONSHIP_SOURCE_IDS,
            limit_per_source=max(args.relationship_limit_per_source, 0),
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "limit_companies": args.limit_companies,
            "limit_jobs": args.limit_jobs,
            "sources": sorted(include_sources) if include_sources else "all",
            "ignore_existing": args.ignore_existing,
            "relationship_artifacts_dir": str(args.outreach_artifacts_dir),
        },
        "startup_apply": {
            "discovered_counts": discovered_counts,
            "new_counts": new_counts,
            "verdict_counts": _counts_by(startup_items, "verdict"),
            "source_verdict_counts": {
                source_id: dict(Counter(item["verdict"] for item in startup_items if item["source_id"] == source_id))
                for source_id in sorted({item["source_id"] for item in startup_items})
            },
            "items": startup_items,
        },
        "relationship_lane": {
            "artifacts": relationship_artifacts,
            "source_counts": _counts_by(relationship_items, "source_id"),
            "items": relationship_items,
        },
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = args.out_dir / f"{stamp}-startup-source-report.json"
    md_path = args.out_dir / f"{stamp}-startup-source-report.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(md_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    print(f"startup_apply: {payload['startup_apply']['verdict_counts']}")
    print(f"relationship_lane: {payload['relationship_lane']['source_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
