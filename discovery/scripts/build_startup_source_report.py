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
SCRIPT_DIR = ROOT / "discovery" / "scripts"
OUT_DIR = ROOT / "discovery" / "source_validation"
OUTREACH_ARTIFACTS_DIR = ROOT.parent / "Outreach" / "artifacts"

for path in (ROOT, AUTO_DIR, SCRIPT_DIR):
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


class StartupRunArtifactError(ValueError):
    """The caller-provided startup run artifact is absent or cannot be trusted."""


class RelationshipArtifactError(ValueError):
    """An exact relationship-source artifact cannot be trusted."""


def _artifact_count(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise StartupRunArtifactError(f"{field} must be a non-negative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise StartupRunArtifactError(f"{field} must be a non-negative integer")
    if parsed < 0:
        raise StartupRunArtifactError(f"{field} must be a non-negative integer")
    return parsed


def _artifact_source_counts(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise StartupRunArtifactError(f"{field} must be an object")
    return {
        str(source_id): _artifact_count(count, f"{field}.{source_id}")
        for source_id, count in value.items()
        if str(source_id).strip()
    }


def _load_startup_run_artifact(path: Path) -> dict[str, Any]:
    exact_path = path.expanduser().resolve(strict=False)
    if not exact_path.is_file():
        raise StartupRunArtifactError(
            f"Exact startup run artifact is missing: {exact_path}"
        )
    try:
        payload = json.loads(exact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StartupRunArtifactError(
            f"Exact startup run artifact is unreadable or invalid JSON: {exact_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise StartupRunArtifactError("Startup run artifact root must be an object")
    if payload.get("schema") != startup_apply.STARTUP_RUN_ARTIFACT_SCHEMA:
        raise StartupRunArtifactError(
            f"Unexpected startup run artifact schema: {payload.get('schema')!r}"
        )
    if payload.get("version") != startup_apply.STARTUP_RUN_ARTIFACT_VERSION:
        raise StartupRunArtifactError(
            f"Unsupported startup run artifact version: {payload.get('version')!r}"
        )
    counts = payload.get("counts")
    candidates = payload.get("candidates")
    if not isinstance(counts, dict):
        raise StartupRunArtifactError("Startup run artifact counts must be an object")
    if not isinstance(candidates, dict):
        raise StartupRunArtifactError("Startup run artifact candidates must be an object")
    discovered_counts = _artifact_source_counts(
        counts.get("discovered_by_source"),
        "counts.discovered_by_source",
    )
    new_counts = _artifact_source_counts(
        counts.get("new_by_source"),
        "counts.new_by_source",
    )
    selected_counts = _artifact_source_counts(
        counts.get("selected_by_source"),
        "counts.selected_by_source",
    )
    selected = candidates.get("selected")
    scored = candidates.get("scored")
    if not isinstance(selected, list) or any(
        not isinstance(item, dict) for item in selected
    ):
        raise StartupRunArtifactError("candidates.selected must be a list of objects")
    if not isinstance(scored, list) or any(not isinstance(item, dict) for item in scored):
        raise StartupRunArtifactError("candidates.scored must be a list of objects")

    discovered_total = _artifact_count(counts.get("discovered"), "counts.discovered")
    new_total = _artifact_count(counts.get("new"), "counts.new")
    selected_total = _artifact_count(counts.get("selected"), "counts.selected")
    scored_total = _artifact_count(counts.get("scored"), "counts.scored")
    error_total = _artifact_count(counts.get("error_count"), "counts.error_count")
    scoring_errors = _artifact_count(
        counts.get("scoring_error_count"),
        "counts.scoring_error_count",
    )
    processing_errors = _artifact_count(
        counts.get("processing_error_count"),
        "counts.processing_error_count",
    )
    run_errors = _artifact_count(
        counts.get("run_error_count"),
        "counts.run_error_count",
    )
    if discovered_total != sum(discovered_counts.values()):
        raise StartupRunArtifactError(
            "counts.discovered does not match counts.discovered_by_source"
        )
    if new_total != sum(new_counts.values()):
        raise StartupRunArtifactError(
            "counts.new does not match counts.new_by_source"
        )
    if selected_total != len(selected):
        raise StartupRunArtifactError(
            "counts.selected does not match candidates.selected"
        )
    if scored_total != len(scored) or scored_total > selected_total:
        raise StartupRunArtifactError(
            "counts.scored does not match candidates.scored"
        )
    actual_scoring_errors = sum(
        1
        for item in scored
        if _clean(item.get("decision")).casefold() == "error"
        or _clean(item.get("status")).casefold() == "error"
    )
    if scoring_errors != actual_scoring_errors:
        raise StartupRunArtifactError(
            "counts.scoring_error_count does not match candidates.scored"
        )
    if processing_errors != max(0, selected_total - scored_total):
        raise StartupRunArtifactError(
            "counts.processing_error_count does not match selected/scored counts"
        )
    if error_total != scoring_errors + processing_errors + run_errors:
        raise StartupRunArtifactError(
            "counts.error_count does not match scoring/processing errors"
        )
    if new_total > discovered_total or selected_total > new_total:
        raise StartupRunArtifactError(
            "Startup run artifact count ordering is impossible"
        )
    if set(discovered_counts) != set(new_counts) or set(new_counts) != set(
        selected_counts
    ):
        raise StartupRunArtifactError(
            "Per-source discovered/new/selected count keys do not match"
        )
    candidate_source_counts = Counter(
        _clean(item.get("source_id")) for item in selected
    )
    if not all(candidate_source_counts) or dict(candidate_source_counts) != {
        source_id: count for source_id, count in selected_counts.items() if count
    }:
        raise StartupRunArtifactError(
            "counts.selected_by_source does not match candidates.selected"
        )
    for source_id in discovered_counts:
        if not (
            selected_counts[source_id]
            <= new_counts[source_id]
            <= discovered_counts[source_id]
        ):
            raise StartupRunArtifactError(
                f"Per-source count ordering is impossible for {source_id}"
            )
    if run_errors:
        expected_status = "failed"
    elif selected_total == 0 or error_total == 0:
        expected_status = "completed"
    elif error_total >= selected_total:
        expected_status = "failed"
    else:
        expected_status = "partial_failed"
    if payload.get("status") != expected_status:
        raise StartupRunArtifactError(
            "Startup run artifact status does not match its scoring error counts"
        )

    payload["_exact_path"] = str(exact_path)
    payload["_discovered_counts"] = discovered_counts
    payload["_new_counts"] = new_counts
    return payload


def _classify_startup_run_artifact(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int], dict[str, Any]]:
    payload = _load_startup_run_artifact(path)
    rows: list[dict[str, Any]] = []
    for item in payload["candidates"]["selected"]:
        job_dict = dict(item)
        classified = classify_job(job_dict, "startup_apply")
        row = asdict(classified)
        row.update(
            {
                "source_id": _clean(item.get("source_id")),
                "location": _clean(item.get("location")),
                "date_posted": _clean(item.get("date_posted")),
                "list_url": _clean(item.get("list_url")),
                "notes": str(item.get("notes") or ""),
            }
        )
        rows.append(row)
    return (
        rows,
        payload["_discovered_counts"],
        payload["_new_counts"],
        payload,
    )


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


def _latest_outreach_artifact(
    source_id: str,
    artifacts_dir: Path,
    *,
    since_epoch: float | None = None,
) -> Path | None:
    matches = [
        path
        for path in artifacts_dir.glob(f"*-discover-{source_id}.json")
        if since_epoch is None or path.stat().st_mtime >= since_epoch
    ]
    matches.sort(key=lambda path: path.stat().st_mtime)
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
    artifact_since_epoch: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    for source_id in source_ids:
        artifact = _latest_outreach_artifact(
            source_id,
            artifacts_dir,
            since_epoch=artifact_since_epoch,
        )
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


def _parse_key_value_args(values: list[str], label: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        key = key.strip()
        item = item.strip()
        if not separator or not key or not item:
            raise RelationshipArtifactError(
                f"{label} must use SOURCE_ID=VALUE; got {value!r}"
            )
        if key in parsed:
            raise RelationshipArtifactError(f"Duplicate {label} for {key}")
        parsed[key] = item
    return parsed


def _exact_relationship_payload(
    path: Path,
    expected_source_id: str,
) -> tuple[dict[str, Any], str]:
    exact_path = path.expanduser().resolve(strict=False)
    if not exact_path.is_file():
        raise RelationshipArtifactError(
            f"Exact relationship artifact is missing for {expected_source_id}: {exact_path}"
        )
    try:
        payload = json.loads(exact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RelationshipArtifactError(
            f"Exact relationship artifact is invalid for {expected_source_id}: {exact_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RelationshipArtifactError(
            f"Relationship artifact root must be an object for {expected_source_id}"
        )
    source = payload.get("source")
    actual_source_id = (
        _clean(source.get("source_id")) if isinstance(source, dict) else ""
    )
    if actual_source_id != expected_source_id:
        raise RelationshipArtifactError(
            f"Relationship artifact source mismatch: expected {expected_source_id}, "
            f"found {actual_source_id or 'missing'}"
        )
    results = payload.get("results")
    if not isinstance(results, list) or any(
        not isinstance(item, dict) for item in results
    ):
        raise RelationshipArtifactError(
            f"Relationship artifact results must be a list for {expected_source_id}"
        )
    try:
        kept_count = int(payload.get("count"))
        raw_count = int(payload.get("raw_count"))
    except (TypeError, ValueError) as exc:
        raise RelationshipArtifactError(
            f"Relationship artifact counts are invalid for {expected_source_id}"
        ) from exc
    if kept_count != len(results) or raw_count < kept_count or kept_count < 0:
        raise RelationshipArtifactError(
            f"Relationship artifact counts are inconsistent for {expected_source_id}"
        )
    artifact_status = _clean(payload.get("status") or "completed").casefold()
    if artifact_status in {"ran", "success", "ok"}:
        artifact_status = "completed"
    return payload, artifact_status


def _relationship_target(item: dict[str, Any], source_id: str) -> dict[str, Any]:
    score, reasons = _relationship_score(item, source_id)
    return {
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


def _sort_and_limit_relationship_targets(
    targets: list[dict[str, Any]],
    limit_per_source: int,
) -> list[dict[str, Any]]:
    targets = sorted(
        targets,
        key=lambda item: (
            int(item.get("relationship_score") or 0),
            _clean(item.get("organization_name")).lower(),
        ),
        reverse=True,
    )
    if limit_per_source <= 0:
        return targets
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        bucket = grouped[target["source_id"]]
        if len(bucket) < limit_per_source:
            bucket.append(target)
    return sorted(
        [target for bucket in grouped.values() for target in bucket],
        key=lambda item: (
            int(item.get("relationship_score") or 0),
            _clean(item.get("organization_name")).lower(),
        ),
        reverse=True,
    )


def _load_exact_relationship_targets(
    *,
    artifact_paths: dict[str, str],
    command_statuses: dict[str, str],
    source_ids: tuple[str, ...],
    limit_per_source: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, int]:
    targets: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    completed_sources = 0
    error_count = 0
    for source_id in source_ids:
        raw_path = artifact_paths.get(source_id, "")
        command_status = _clean(
            command_statuses.get(source_id) or "completed"
        ).casefold()
        if command_status in {"ran", "success", "ok"}:
            command_status = "completed"
        if not raw_path:
            artifacts[source_id] = {
                "artifact": "",
                "count": 0,
                "raw_count": 0,
                "status": "missing",
                "error": "No exact artifact pointer was provided.",
            }
            error_count += 1
            continue
        exact_path = Path(raw_path).expanduser().resolve(strict=False)
        try:
            payload, artifact_status = _exact_relationship_payload(
                exact_path,
                source_id,
            )
        except RelationshipArtifactError as exc:
            artifacts[source_id] = {
                "artifact": str(exact_path),
                "count": 0,
                "raw_count": 0,
                "status": "invalid",
                "error": str(exc),
            }
            error_count += 1
            continue

        source_status = artifact_status
        if command_status != "completed":
            source_status = command_status
        is_green = source_status == "completed"
        if is_green:
            completed_sources += 1
        else:
            error_count += 1
        artifacts[source_id] = {
            "artifact": str(exact_path),
            "count": len(payload["results"]),
            "raw_count": int(payload["raw_count"]),
            "status": source_status,
            "command_status": command_status,
            "artifact_status": artifact_status,
        }
        targets.extend(
            _relationship_target(item, source_id) for item in payload["results"]
        )

    if error_count == 0:
        status = "completed"
    elif completed_sources:
        status = "partial_failed"
    else:
        status = "failed"
    return (
        _sort_and_limit_relationship_targets(targets, limit_per_source),
        artifacts,
        status,
        error_count,
    )


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
        f"- Status: {payload['startup_apply']['status']}",
        f"- Mode: {payload['startup_apply']['mode']}",
        f"- Exact run artifact: {payload['startup_apply']['run_artifact'] or 'n/a'}",
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
            f"- Status: {payload['relationship_lane']['status']}",
            f"- Mode: {payload['relationship_lane']['mode']}",
            f"- Errors: {payload['relationship_lane']['error_count']}",
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
    parser = argparse.ArgumentParser(
        description="Build a startup source report from one explicit startup lane mode."
    )
    parser.add_argument("--limit-companies", type=int, default=startup_apply.DEFAULT_LIMIT_COMPANIES)
    parser.add_argument("--limit-jobs", type=int, default=startup_apply.DEFAULT_LIMIT_JOBS)
    parser.add_argument("--source", action="append", default=[], help="Startup apply source_id filter, repeatable.")
    parser.add_argument("--ignore-existing", action="store_true", help="Ignore jobs.xlsx dedupe for validation.")
    parser.add_argument("--quiet", action="store_true", help="Suppress source discovery output.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help=(
            "Write JSON to this exact path and Markdown beside it. The daily engine "
            "sets this explicitly; standalone mode otherwise uses a timestamped path."
        ),
    )
    parser.add_argument("--outreach-artifacts-dir", type=Path, default=OUTREACH_ARTIFACTS_DIR)
    relationship_mode = parser.add_mutually_exclusive_group(required=True)
    relationship_mode.add_argument(
        "--exact-relationship-artifacts",
        action="store_true",
        help="Use only the explicit SOURCE_ID=PATH mappings supplied for this run.",
    )
    relationship_mode.add_argument(
        "--rediscover-relationship-artifacts",
        action="store_true",
        help=(
            "Standalone/manual mode: select relationship artifacts from the artifact "
            "directory. Never use this mode to represent a production daily run."
        ),
    )
    relationship_mode.add_argument(
        "--no-relationship-artifacts",
        action="store_true",
        help="Represent the relationship lane as skipped.",
    )
    parser.add_argument(
        "--relationship-artifact",
        action="append",
        default=[],
        metavar="SOURCE_ID=PATH",
        help="Exact relationship discovery artifact mapping, repeatable.",
    )
    parser.add_argument(
        "--relationship-artifact-status",
        action="append",
        default=[],
        metavar="SOURCE_ID=STATUS",
        help="Run-scoped command health for an exact relationship artifact.",
    )
    parser.add_argument(
        "--required-relationship-source",
        action="append",
        default=[],
        help="Required configured source id in exact mode, repeatable.",
    )
    parser.add_argument(
        "--relationship-artifact-since-epoch",
        type=float,
        default=None,
        help="Only ingest relationship discovery artifacts written at or after this run cutoff.",
    )
    startup_mode = parser.add_mutually_exclusive_group(required=True)
    startup_mode.add_argument(
        "--startup-run-artifact",
        type=Path,
        help=(
            "Consume this exact structured startup-apply run artifact. This is the "
            "production/daily-engine mode and never re-fetches startup sources."
        ),
    )
    startup_mode.add_argument(
        "--rediscover-startup-apply",
        action="store_true",
        help=(
            "Standalone/manual source-health mode: fetch startup sources again for "
            "this report. Never use this mode to represent a daily engine run."
        ),
    )
    startup_mode.add_argument(
        "--no-startup-apply",
        action="store_true",
        help="Represent the startup-apply lane as skipped without fetching sources.",
    )
    parser.add_argument("--relationship-limit-per-source", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_sources = {value.strip() for value in args.source if value.strip()} or None
    startup_mode = "skipped"
    startup_run_artifact = ""
    startup_run_status = "skipped"
    startup_run_config: dict[str, Any] = {}
    if args.no_startup_apply:
        startup_items, discovered_counts, new_counts = [], {}, {}
    elif args.startup_run_artifact:
        startup_mode = "exact_run_artifact"
        if include_sources or args.ignore_existing:
            print(
                "ERROR: --source and --ignore-existing are only valid with "
                "--rediscover-startup-apply.",
                file=sys.stderr,
            )
            return 2
        try:
            (
                startup_items,
                discovered_counts,
                new_counts,
                run_payload,
            ) = _classify_startup_run_artifact(args.startup_run_artifact)
        except StartupRunArtifactError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        startup_run_artifact = run_payload["_exact_path"]
        startup_run_status = str(run_payload.get("status") or "unknown")
        startup_run_config = (
            dict(run_payload.get("config") or {})
            if isinstance(run_payload.get("config"), dict)
            else {}
        )
    else:
        startup_mode = "standalone_rediscovery"
        startup_run_status = "manual_rediscovery"
        startup_items, discovered_counts, new_counts = _classify_startup_apply(
            limit_companies=max(args.limit_companies, 1),
            limit_jobs=max(args.limit_jobs, 1) if args.limit_jobs is not None else None,
            include_sources=include_sources,
            ignore_existing=args.ignore_existing,
            verbose=not args.quiet,
        )

    relationship_items: list[dict[str, Any]] = []
    relationship_artifacts: dict[str, Any] = {}
    relationship_status = "skipped"
    relationship_error_count = 0
    relationship_mode = "skipped"
    if args.exact_relationship_artifacts:
        relationship_mode = "exact_run_artifacts"
        if args.relationship_artifact_since_epoch is not None:
            print(
                "ERROR: --relationship-artifact-since-epoch is only valid with "
                "--rediscover-relationship-artifacts.",
                file=sys.stderr,
            )
            return 2
        try:
            artifact_paths = _parse_key_value_args(
                args.relationship_artifact,
                "--relationship-artifact",
            )
            command_statuses = _parse_key_value_args(
                args.relationship_artifact_status,
                "--relationship-artifact-status",
            )
        except RelationshipArtifactError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        required_sources = tuple(
            dict.fromkeys(args.required_relationship_source or artifact_paths)
        )
        if not required_sources:
            print(
                "ERROR: exact relationship mode requires at least one configured source.",
                file=sys.stderr,
            )
            return 2
        unknown_paths = set(artifact_paths) - set(required_sources)
        unknown_statuses = set(command_statuses) - set(required_sources)
        if unknown_paths or unknown_statuses:
            print(
                "ERROR: exact relationship mappings contain unconfigured sources: "
                f"{sorted(unknown_paths | unknown_statuses)}",
                file=sys.stderr,
            )
            return 2
        (
            relationship_items,
            relationship_artifacts,
            relationship_status,
            relationship_error_count,
        ) = _load_exact_relationship_targets(
            artifact_paths=artifact_paths,
            command_statuses=command_statuses,
            source_ids=required_sources,
            limit_per_source=max(args.relationship_limit_per_source, 0),
        )
    elif args.rediscover_relationship_artifacts:
        relationship_mode = "standalone_latest_rediscovery"
        relationship_items, relationship_artifacts = _load_relationship_targets(
            artifacts_dir=args.outreach_artifacts_dir,
            source_ids=RELATIONSHIP_SOURCE_IDS,
            limit_per_source=max(args.relationship_limit_per_source, 0),
            artifact_since_epoch=args.relationship_artifact_since_epoch,
        )
        relationship_error_count = sum(
            1
            for item in relationship_artifacts.values()
            if str(item.get("status") or "") != "loaded"
        )
        loaded_count = len(relationship_artifacts) - relationship_error_count
        if relationship_error_count == 0:
            relationship_status = "completed"
        elif loaded_count:
            relationship_status = "partial_failed"
        else:
            relationship_status = "failed"
    elif (
        args.relationship_artifact
        or args.relationship_artifact_status
        or args.required_relationship_source
    ):
        print(
            "ERROR: exact relationship mappings require "
            "--exact-relationship-artifacts.",
            file=sys.stderr,
        )
        return 2

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "limit_companies": args.limit_companies,
            "limit_jobs": args.limit_jobs,
            "sources": sorted(include_sources) if include_sources else "all",
            "ignore_existing": args.ignore_existing,
            "startup_apply_mode": startup_mode,
            "startup_run_artifact": startup_run_artifact,
            "startup_run_config": startup_run_config,
            "relationship_artifacts_dir": str(args.outreach_artifacts_dir),
            "relationship_artifact_since_epoch": args.relationship_artifact_since_epoch,
            "relationship_mode": relationship_mode,
        },
        "startup_apply": {
            "status": startup_run_status,
            "mode": startup_mode,
            "run_artifact": startup_run_artifact,
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
            "status": relationship_status,
            "mode": relationship_mode,
            "error_count": relationship_error_count,
            "artifacts": relationship_artifacts,
            "source_counts": _counts_by(relationship_items, "source_id"),
            "items": relationship_items,
        },
    }

    if args.output_json:
        json_path = args.output_json.expanduser().resolve(strict=False)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path = json_path.with_suffix(".md")
    else:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        json_path = args.out_dir / f"{stamp}-startup-source-report.json"
        md_path = args.out_dir / f"{stamp}-startup-source-report.md"
    json_temp = json_path.with_name(f".{json_path.name}.tmp")
    json_temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    json_temp.replace(json_path)
    _write_markdown(md_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    print(f"startup_apply: {payload['startup_apply']['verdict_counts']}")
    print(f"relationship_lane: {payload['relationship_lane']['source_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
