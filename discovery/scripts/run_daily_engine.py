#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
OUTREACH_ROOT = ROOT.parent / "Outreach"
PYTHON = ROOT / "venv" / "bin" / "python"
OUTREACH_PYTHON = OUTREACH_ROOT / ".venv" / "bin" / "python"

RELATIONSHIP_SOURCES = (
    "yc_sf_bay_hiring",
    "yc_los_angeles",
    "builtin_la_companies",
    "builtin_sf_companies",
)
DAILY_JOBSPY_QUERY_INDICES = (0, 1, 2, 3, 7, 8, 9, 10, 11)
WEEKLY_JOBSPY_QUERY_INDICES = (0, 1, 2, 3, 7, 8, 9, 10, 11)
WEEKLY_JOBSPY_RESULTS = 60

COMMON_COMPANY_TOKENS = {
    "ai",
    "and",
    "co",
    "company",
    "corp",
    "corporation",
    "defense",
    "group",
    "inc",
    "industries",
    "labs",
    "systems",
    "technologies",
    "technology",
    "the",
}


def _cmd_text(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(cmd: list[object], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n$ {_cmd_text(cmd)}")
    return subprocess.run([str(part) for part in cmd], cwd=cwd, check=check)


def run_capture(
    cmd: list[object],
    *,
    cwd: Path = ROOT,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    print(f"\n$ {_cmd_text(cmd)}")
    try:
        result = subprocess.run(
            [str(part) for part in cmd],
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"[warn] Command timed out after {timeout}s: {_cmd_text(cmd)}", file=sys.stderr)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        return subprocess.CompletedProcess([str(part) for part in cmd], 124, stdout, stderr)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result


def start(cmd: list[object], *, cwd: Path = ROOT) -> subprocess.Popen:
    print(f"\n$ {_cmd_text(cmd)}")
    return subprocess.Popen([str(part) for part in cmd], cwd=cwd)


def sync_applied_pdfs() -> None:
    run([PYTHON, "discovery/scripts/sync_applied_pdfs.py"])


def latest(pattern: str, directory: Path) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {directory / pattern}")
    return matches[-1]


def latest_since(pattern: str, directory: Path, since_ts: float) -> Path | None:
    matches = [
        path
        for path in directory.glob(pattern)
        if path.stat().st_mtime >= since_ts - 2
    ]
    matches = sorted(matches, key=lambda path: path.stat().st_mtime)
    return matches[-1] if matches else None


def _load_json(path: Path | None) -> dict:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_count(pattern: str, text: str) -> int:
    match = re.search(pattern, text, re.M)
    if not match:
        return 0
    return int(match.group(1))


def _decision_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        decision = str(item.get("decision") or item.get("status") or "").strip() or "unknown"
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def _accepted_per_minute(accepted: int, runtime_seconds: float | int | None) -> float | None:
    if not runtime_seconds or runtime_seconds <= 0:
        return None
    return round(accepted / (runtime_seconds / 60), 3)


def _score_artifact_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    jobs = payload.get("jobs") or []
    decision_counts = _decision_counts(jobs)
    return {
        "artifact": str(path) if path else "",
        "raw_count": payload.get("extracted"),
        "reviewed_count": payload.get("reviewed"),
        "freshly_scored_count": payload.get("scored"),
        "existing_skipped": payload.get("existing_skipped"),
        "cache_skipped": payload.get("cache_skipped"),
        "accepted_for_write": payload.get("accepted_for_write"),
        "new_after_dedup": payload.get("new_after_dedup"),
        "decision_counts": decision_counts,
        "error_count": decision_counts.get("Error", 0),
    }


def _handshake_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    counts = payload.get("counts") or {}
    scored = payload.get("scored") or []
    decision_counts = _decision_counts(scored)
    return {
        "artifact": str(path) if path else "",
        "raw_count": counts.get("input_rows"),
        "deduped_candidates": counts.get("deduped_candidates"),
        "skipped_duplicates": counts.get("skipped_duplicates"),
        "historical_seen_urls": counts.get("historical_seen_urls"),
        "title_prefilter_skipped": counts.get("title_prefilter_skipped"),
        "fetch_ok": counts.get("fetch_ok"),
        "fetch_failed": counts.get("fetch_failed"),
        "freshly_scored_count": counts.get("scored"),
        "accepted_for_write": counts.get("accepted_min_score"),
        "decision_counts": decision_counts,
        "error_count": counts.get("fetch_failed", 0),
    }


def _jobspy_metrics_from_artifacts(raw_path: Path | None, breadth_path: Path | None, scored_path: Path | None) -> dict:
    raw = _load_json(raw_path)
    breadth = _load_json(breadth_path)
    scored = _score_artifact_metrics(scored_path)
    jobspy_bucket = (breadth.get("classified") or {}).get("jobspy_only") or {}
    verdict_counts = jobspy_bucket.get("verdict_counts") or {}
    return {
        "raw_artifact": str(raw_path) if raw_path else "",
        "breadth_artifact": str(breadth_path) if breadth_path else "",
        "scored_artifact": str(scored_path) if scored_path else "",
        "raw_count": raw.get("count") or len(raw.get("jobs") or []),
        "jobspy_only": (breadth.get("raw_counts") or {}).get("jobspy_only"),
        "verdict_counts": verdict_counts,
        "app_score_now": len(jobspy_bucket.get("app_score_now") or []),
        "app_review": len(jobspy_bucket.get("app_review") or []),
        "outreach_signal": len(jobspy_bucket.get("outreach_signal") or []),
        "selected_for_scoring": scored.get("raw_count"),
        "freshly_scored_count": scored.get("freshly_scored_count"),
        "accepted_for_write": scored.get("accepted_for_write"),
        "cache_skipped": scored.get("cache_skipped"),
        "existing_skipped": scored.get("existing_skipped"),
        "decision_counts": scored.get("decision_counts") or {},
        "error_count": scored.get("error_count") or 0,
    }


def _startup_apply_log_metrics(path: Path | None) -> dict:
    if not path:
        return {"artifact": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    source_rows: dict[str, dict[str, int]] = {}
    for line in text.splitlines():
        if " | discovered=" not in line:
            continue
        label, _, rest = line.partition(" | ")
        source_match = re.search(r"\[([^\]]+)\]", label)
        source_id = source_match.group(1) if source_match else label.strip()
        source_rows[source_id] = {
            "discovered": _parse_count(r"discovered=(\d+)", rest),
            "new": _parse_count(r"new=(\d+)", rest),
            "scored": _parse_count(r"scored=(\d+)", rest),
            "queued": _parse_count(r"queued=(\d+)", rest),
            "review": _parse_count(r"review=(\d+)", rest),
            "skipped": _parse_count(r"skipped=(\d+)", rest),
        }
    return {
        "artifact": str(path),
        "discovered_count": sum(item["discovered"] for item in source_rows.values()),
        "new_count": sum(item["new"] for item in source_rows.values()),
        "freshly_scored_count": sum(item["scored"] for item in source_rows.values()),
        "accepted_for_write": _parse_count(r"^Queued:\s+(\d+)", text),
        "review_count": _parse_count(r"^Review:\s+(\d+)", text),
        "skipped_count": _parse_count(r"^Skipped:\s+(\d+)", text),
        "source_counts": source_rows,
    }


def _startup_report_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    startup_apply = payload.get("startup_apply") or {}
    relationship = payload.get("relationship_lane") or {}
    return {
        "artifact": str(path) if path else "",
        "startup_apply_discovered": startup_apply.get("discovered_counts") or {},
        "startup_apply_new": startup_apply.get("new_counts") or {},
        "startup_apply_verdicts": startup_apply.get("verdict_counts") or {},
        "startup_apply_source_verdicts": startup_apply.get("source_verdict_counts") or {},
        "relationship_source_counts": relationship.get("source_counts") or {},
        "relationship_targets": len(relationship.get("items") or []),
    }


def _action_queue_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    return {
        "artifact": str(path) if path else "",
        "counts": payload.get("counts") or {},
        "source_counts": payload.get("source_counts") or {},
    }


def _source_row(
    *,
    stage: dict,
    metrics: dict,
    raw_key: str = "raw_count",
    selected_key: str = "reviewed_count",
    scored_key: str = "freshly_scored_count",
    accepted_key: str = "accepted_for_write",
    outreach_key: str = "outreach_signal",
) -> dict:
    runtime = stage.get("runtime_seconds")
    accepted = int(metrics.get(accepted_key) or 0)
    return {
        "status": stage.get("status", "unknown"),
        "runtime_seconds": runtime,
        "raw_count": metrics.get(raw_key),
        "selected_count": metrics.get(selected_key),
        "freshly_scored_count": metrics.get(scored_key),
        "accepted_for_write": accepted,
        "outreach_signals": metrics.get(outreach_key),
        "error_count": metrics.get("error_count", 0),
        "accepted_per_minute": _accepted_per_minute(accepted, runtime),
        "details": metrics,
    }


def write_source_run_metrics(
    *,
    args: argparse.Namespace,
    run_started_at: str,
    stage_metrics: dict[str, dict],
    artifacts: dict[str, Path | None],
    action_queue_path: Path | None,
) -> Path:
    linkedin = _score_artifact_metrics(artifacts.get("linkedin_scored"))
    handshake = _handshake_metrics(artifacts.get("handshake_log"))
    jobspy = _jobspy_metrics_from_artifacts(
        artifacts.get("jobspy_raw"),
        artifacts.get("source_breadth"),
        artifacts.get("jobspy_scored"),
    )
    startup_apply = _startup_apply_log_metrics(artifacts.get("startup_apply_log"))
    startup_report = _startup_report_metrics(artifacts.get("startup_report"))
    action_queue = _action_queue_metrics(action_queue_path)
    relationship_stage = stage_metrics.get("relationship_discovery", {})

    sources = {
        "linkedin": _source_row(stage=stage_metrics.get("linkedin", {}), metrics=linkedin),
        "handshake": _source_row(
            stage=stage_metrics.get("handshake", {}),
            metrics=handshake,
            raw_key="raw_count",
            selected_key="deduped_candidates",
        ),
        "jobspy": _source_row(
            stage=stage_metrics.get("jobspy", {}),
            metrics=jobspy,
            raw_key="raw_count",
            selected_key="selected_for_scoring",
            outreach_key="outreach_signal",
        ),
        "startup_apply": _source_row(
            stage=stage_metrics.get("startup_apply", {}),
            metrics=startup_apply,
            raw_key="discovered_count",
            selected_key="new_count",
        ),
        "startup_relationship": {
            "status": relationship_stage.get("status", "unknown"),
            "runtime_seconds": relationship_stage.get("runtime_seconds"),
            "relationship_targets": startup_report.get("relationship_targets"),
            "source_counts": startup_report.get("relationship_source_counts"),
        },
    }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_started_at": run_started_at,
        "window": args.window,
        "jobspy_policy": {
            "query_indices": artifacts.get("jobspy_query_indices", []),
            "results_per_site": artifacts.get("jobspy_results"),
            "fetch_timeout_seconds": artifacts.get("jobspy_fetch_timeout"),
            "score_limit": args.jobspy_score_limit,
        },
        "stage_metrics": stage_metrics,
        "sources": sources,
        "startup_source_report": startup_report,
        "action_queue": action_queue,
    }

    SOURCE_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = SOURCE_VALIDATION_DIR / f"{stamp}-source-run-metrics.json"
    md_path = json_path.with_suffix(".md")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    write_source_run_metrics_markdown(md_path, payload)
    print(f"\nSource metrics: {json_path}")
    print(f"Source metrics report: {md_path}")
    return json_path


def write_source_run_metrics_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Source Run Metrics",
        "",
        f"Generated: {payload['generated_at']}",
        f"Run started: {payload['run_started_at']}",
        f"Window: {payload['window']}",
        "",
        "## Source Scorecard",
        "",
        "| Source | Status | Runtime | Raw | Selected/New | Scored | Errors | Accepted | Outreach | Accepted/min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["sources"].items():
        if name == "startup_relationship":
            lines.append(
                "| startup_relationship | "
                f"{row.get('status', '')} | {row.get('runtime_seconds', '')} |  |  |  |  |  | "
                f"{row.get('relationship_targets', '')} |  |"
            )
            continue
        lines.append(
            f"| {name} | {row.get('status', '')} | {row.get('runtime_seconds', '')} | "
            f"{row.get('raw_count', '')} | {row.get('selected_count', '')} | "
            f"{row.get('freshly_scored_count', '')} | {row.get('error_count', '')} | "
            f"{row.get('accepted_for_write', '')} | {row.get('outreach_signals', '')} | "
            f"{row.get('accepted_per_minute', '')} |"
        )

    lines.extend(
        [
            "",
            "## JobSpy Policy",
            "",
            f"- Query indices: {payload['jobspy_policy']['query_indices']}",
            f"- Results per site: {payload['jobspy_policy']['results_per_site']}",
            f"- Fetch timeout seconds: {payload['jobspy_policy']['fetch_timeout_seconds']}",
            f"- Score limit: {payload['jobspy_policy']['score_limit']}",
            "",
            "## Action Queue",
            "",
            f"- Counts: {payload['action_queue']['counts']}",
            f"- Source counts: {payload['action_queue']['source_counts']}",
            "",
            "## Startup Split",
            "",
            f"- Startup apply discovered: {payload['startup_source_report']['startup_apply_discovered']}",
            f"- Startup apply new: {payload['startup_source_report']['startup_apply_new']}",
            f"- Startup apply verdicts: {payload['startup_source_report']['startup_apply_verdicts']}",
            f"- Startup relationship targets: {payload['startup_source_report']['relationship_targets']}",
            f"- Startup relationship sources: {payload['startup_source_report']['relationship_source_counts']}",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def window_to_hours(window: str) -> int:
    if window == "24h":
        return 24
    if window == "7d":
        return 168
    raise SystemExit("--window must be 24h or 7d")


def build_action_queue(args: argparse.Namespace) -> Path:
    run(
        [
            PYTHON,
            "discovery/scripts/build_daily_action_queue.py",
            "--report-stage",
            "post_score",
            "--relationship-today",
            args.relationship_today,
        ]
    )
    return latest("*daily-action-queue.json", SOURCE_VALIDATION_DIR)


def _company_key(company: str) -> str:
    return " ".join(company.lower().split())


def _append_company(companies: list[str], seen: set[str], company: str) -> bool:
    company = company.strip()
    if not company:
        return False
    key = _company_key(company)
    if key in seen:
        return False
    companies.append(company)
    seen.add(key)
    return True


def selected_outreach_companies(action_queue_path: Path, *, app_limit: int, relationship_limit: int) -> list[str]:
    payload = json.loads(action_queue_path.read_text(encoding="utf-8"))
    companies: list[str] = []
    seen: set[str] = set()

    for item in payload.get("application_plus_outreach") or []:
        company = str(item.get("company") or "").strip()
        _append_company(companies, seen, company)
        if len(companies) >= app_limit:
            break

    relationship_added = 0
    for item in payload.get("outreach_only_today") or []:
        company = str(item.get("company") or "").strip()
        if _append_company(companies, seen, company):
            relationship_added += 1
        if relationship_added >= relationship_limit:
            break
    return companies


def target_outreach_companies(action_queue_path: Path, *, company_limit: int) -> list[str]:
    payload = json.loads(action_queue_path.read_text(encoding="utf-8"))
    companies: list[str] = []
    seen: set[str] = set()
    for bucket in ("application_plus_outreach", "outreach_only_today", "relationship_buffer"):
        for item in payload.get(bucket) or []:
            _append_company(companies, seen, str(item.get("company") or ""))
            if len(companies) >= company_limit:
                return companies
    return companies


def _artifact_from_output(output: str) -> Path | None:
    for line in output.splitlines():
        if line.startswith("Artifact: "):
            raw = line.split("Artifact: ", 1)[1].strip()
            path = Path(raw)
            return path if path.is_absolute() else OUTREACH_ROOT / path
    return None


def _company_tokens(company: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    return [token for token in tokens if len(token) >= 3 and token not in COMMON_COMPANY_TOKENS]


def _candidate_mentions_company(company: str, candidate: dict) -> bool:
    text = " ".join(
        str(candidate.get(field) or "")
        for field in ("title", "subtitle", "snippet", "raw_text", "company")
    ).lower()
    return any(token in text for token in _company_tokens(company))


def _candidate_score(candidate: dict) -> int:
    try:
        return int(candidate.get("score"))
    except (TypeError, ValueError):
        return -999


def _note_is_sendable(candidate: dict) -> bool:
    qc = candidate.get("polished_note_qc") or candidate.get("note_qc") or {}
    return qc.get("verdict") == "send"


def _safe_unattended_candidate(company: str, candidate: dict, *, min_score: int) -> bool:
    if not candidate.get("linkedin_url") or candidate.get("existing_connection"):
        return False
    if not _note_is_sendable(candidate):
        return False
    score = _candidate_score(candidate)
    if score < min_score:
        return False
    if _candidate_mentions_company(company, candidate):
        return True
    if str(candidate.get("connection_degree") or "") == "2nd" and score >= max(min_score, 35):
        return True
    return score >= 70


def _filtered_send_artifact(source_artifact: Path, *, company: str, min_score: int, limit: int) -> tuple[Path | None, int]:
    payload = json.loads(source_artifact.read_text(encoding="utf-8"))
    safe_results = [
        item
        for item in payload.get("results") or []
        if _safe_unattended_candidate(company, item, min_score=min_score)
    ]
    if limit > 0:
        safe_results = safe_results[:limit]
    if not safe_results:
        return None, 0
    filtered_payload = {**payload, "results": safe_results, "target_send_filter": {
        "source_artifact": str(source_artifact),
        "min_score": min_score,
        "limit": limit,
        "safe_count": len(safe_results),
    }}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "company"
    out_path = OUTREACH_ROOT / "artifacts" / f"{stamp}-target-send-{slug}.json"
    out_path.write_text(json.dumps(filtered_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path, len(safe_results)


def _sent_count_from_batch(batch_artifact: Path | None) -> int:
    if not batch_artifact or not batch_artifact.exists():
        return 0
    payload = json.loads(batch_artifact.read_text(encoding="utf-8"))
    return sum(1 for item in payload.get("results") or [] if str(item.get("status") or "").lower() == "sent")


def run_targeted_outreach_from_action_queue(args: argparse.Namespace, action_queue_path: Path) -> None:
    run(
        [
            OUTREACH_PYTHON,
            "main.py",
            "import-resume-jobs",
            "--jobs-xlsx",
            "../ResumeGenerator v1/discovery/jobs.xlsx",
        ],
        cwd=OUTREACH_ROOT,
    )
    companies = target_outreach_companies(action_queue_path, company_limit=max(args.max_outreach_companies, 1))
    print(f"\nTargeted outreach companies selected from {action_queue_path.name}: {companies}")
    target_sends = max(args.target_sends, 0)
    sent_total = 0
    failures: list[str] = []
    skipped: list[str] = []
    for company in companies:
        if sent_total >= target_sends:
            break
        prep = run_capture(
            [
                OUTREACH_PYTHON,
                "main.py",
                "run",
                "--company",
                company,
                "--company-mode",
                "startup",
            ],
            cwd=OUTREACH_ROOT,
            check=False,
            timeout=args.company_prep_timeout,
        )
        if prep.returncode != 0:
            failures.append(company)
            print(f"[warn] Outreach artifact generation failed for {company}; continuing.")
            continue
        artifact = _artifact_from_output(prep.stdout)
        if not artifact or not artifact.exists():
            failures.append(company)
            print(f"[warn] Could not resolve outreach artifact for {company}; continuing.")
            continue
        remaining = target_sends - sent_total
        per_company_limit = args.send_limit or args.per_company_send_limit
        send_limit = min(remaining, per_company_limit) if per_company_limit > 0 else remaining
        filtered_artifact, safe_count = _filtered_send_artifact(
            artifact,
            company=company,
            min_score=args.send_min_score,
            limit=send_limit,
        )
        if not filtered_artifact:
            skipped.append(company)
            print(f"[info] No safe unattended invite candidates for {company}; continuing.")
            continue
        print(f"[info] Sending up to {safe_count} safe candidates for {company}; target remaining={remaining}.")
        send = run_capture(
            [
                OUTREACH_PYTHON,
                "main.py",
                "send-invites",
                "--artifact-path",
                filtered_artifact,
                "--limit",
                send_limit,
                "--min-score",
                args.send_min_score,
                "--no-adaptive-min-score",
                "--execute",
            ],
            cwd=OUTREACH_ROOT,
            check=False,
            timeout=args.send_timeout,
        )
        if send.returncode != 0:
            failures.append(company)
            print(f"[warn] Invite send failed for {company}; continuing.")
            continue
        batch_artifact = _artifact_from_output(send.stdout)
        sent_now = _sent_count_from_batch(batch_artifact)
        sent_total += sent_now
        print(f"[info] {company}: sent_now={sent_now}; sent_total={sent_total}/{target_sends}.")
    print(f"\nTargeted outreach send total: {sent_total}/{target_sends}")
    if skipped:
        print(f"[info] Companies skipped with no safe unattended candidates: {skipped}")
    if failures:
        print(f"[warn] Outreach failures: {failures}")


def run_outreach_from_action_queue(args: argparse.Namespace, action_queue_path: Path) -> None:
    if args.execute_sends and args.target_sends > 0:
        run_targeted_outreach_from_action_queue(args, action_queue_path)
        return
    run(
        [
            OUTREACH_PYTHON,
            "main.py",
            "import-resume-jobs",
            "--jobs-xlsx",
            "../ResumeGenerator v1/discovery/jobs.xlsx",
        ],
        cwd=OUTREACH_ROOT,
    )
    companies = selected_outreach_companies(
        action_queue_path,
        app_limit=max(args.app_outreach_limit, 0),
        relationship_limit=max(args.relationship_outreach_limit, 0),
    )
    print(f"\nOutreach companies selected from {action_queue_path.name}: {companies}")
    failures: list[str] = []
    for company in companies:
        cmd: list[object] = [
            OUTREACH_PYTHON,
            "main.py",
            "run",
            "--company",
            company,
            "--company-mode",
            "startup",
        ]
        if args.execute_sends:
            cmd.extend(
                [
                    "--auto-send",
                    "--send-limit",
                    str(args.send_limit),
                    "--send-min-score",
                    str(args.send_min_score),
                ]
            )
        result = run(cmd, cwd=OUTREACH_ROOT, check=False)
        if result.returncode != 0:
            failures.append(company)
            print(f"[warn] Outreach artifact generation failed for {company}; continuing.")
    if failures:
        print(f"[warn] Outreach failures: {failures}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supervised daily application + outreach engine.")
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument("--skip-linkedin", action="store_true")
    parser.add_argument("--skip-handshake", action="store_true")
    parser.add_argument("--skip-jobspy", action="store_true")
    parser.add_argument("--skip-startup-apply", action="store_true")
    parser.add_argument("--skip-relationship-discovery", action="store_true")
    parser.add_argument("--jobspy-results", type=int, default=0, help="Override JobSpy results per query/site. Default: 40 for 24h, 60 for 7d.")
    parser.add_argument("--jobspy-query-index", action="append", type=int, default=[], help="JobSpy query index to run; repeatable. Defaults: 24h uses PM/Product Ops/Growth/Strategy/APM/AI-PM; 7d adds focused MBA/AI strategy queries.")
    parser.add_argument("--jobspy-score-limit", type=int, default=10)
    parser.add_argument("--jobspy-fetch-timeout", type=int, default=0, help="Seconds before skipping the JobSpy breadth scrape. Default: 600 for 24h, 1800 for 7d.")
    parser.add_argument("--startup-limit-companies", type=int, default=20)
    parser.add_argument("--startup-limit-jobs", type=int, default=50)
    parser.add_argument("--relationship-source-limit", type=int, default=25)
    parser.add_argument("--relationship-today", type=int, default=8)
    parser.add_argument("--run-generation", action="store_true")
    parser.add_argument("--resume-parallel", type=int, default=3)
    parser.add_argument("--prepare-outreach", action="store_true")
    parser.add_argument("--app-outreach-limit", type=int, default=3)
    parser.add_argument("--relationship-outreach-limit", type=int, default=2)
    parser.add_argument("--max-outreach-companies", type=int, default=24)
    parser.add_argument("--parallel-generation-outreach", action="store_true")
    parser.add_argument("--execute-sends", action="store_true", help="Actually send LinkedIn invites after artifact generation.")
    parser.add_argument("--target-sends", type=int, default=25, help="Global send target for unattended --execute-sends runs.")
    parser.add_argument("--per-company-send-limit", type=int, default=15, help="Per-company cap while filling --target-sends.")
    parser.add_argument("--send-limit", type=int, default=0)
    parser.add_argument("--send-min-score", type=int, default=20)
    parser.add_argument("--skip-linkedin-preflight", action="store_true")
    parser.add_argument("--company-prep-timeout", type=int, default=420)
    parser.add_argument("--send-timeout", type=int, default=420)
    return parser.parse_args()


def _effective_jobspy_query_indices(args: argparse.Namespace) -> list[int]:
    if args.jobspy_query_index:
        return args.jobspy_query_index
    if args.window == "24h":
        return list(DAILY_JOBSPY_QUERY_INDICES)
    return list(WEEKLY_JOBSPY_QUERY_INDICES)


def _effective_jobspy_results(args: argparse.Namespace) -> int | None:
    if args.jobspy_results and args.jobspy_results > 0:
        return args.jobspy_results
    if args.window == "24h":
        return 40
    return WEEKLY_JOBSPY_RESULTS


def _effective_jobspy_fetch_timeout(args: argparse.Namespace) -> int:
    if args.jobspy_fetch_timeout and args.jobspy_fetch_timeout > 0:
        return args.jobspy_fetch_timeout
    return 600 if args.window == "24h" else 1800


def _start_stage(stage_metrics: dict[str, dict], name: str) -> float:
    stage_metrics[name] = {"status": "running", "runtime_seconds": None}
    return time.monotonic()


def _finish_stage(
    stage_metrics: dict[str, dict],
    name: str,
    started: float,
    *,
    status: str = "ran",
    returncode: int | None = None,
) -> None:
    stage_metrics[name] = {
        "status": status,
        "runtime_seconds": round(time.monotonic() - started, 1),
    }
    if returncode is not None:
        stage_metrics[name]["returncode"] = returncode


def _skip_stage(stage_metrics: dict[str, dict], name: str) -> None:
    stage_metrics[name] = {"status": "skipped", "runtime_seconds": 0}


def _write_empty_jobspy_raw(hours_old: int, reason: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = LOGS_DIR / f"jobspy_breadth_raw_{hours_old}h_{stamp}.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "jobspy_breadth_v1",
        "hours_old": hours_old,
        "results_override": 0,
        "query_indices": [],
        "count": 0,
        "skipped_reason": reason,
        "jobs": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _build_source_breadth(jobspy_raw: Path, *, since_ts: float) -> Path | None:
    try:
        playwright_raw = latest("linkedin_live_raw_*.json", LOGS_DIR)
    except SystemExit as exc:
        print(f"[warn] Could not build source breadth without LinkedIn raw artifact: {exc}", file=sys.stderr)
        return None
    run(
        [
            PYTHON,
            "discovery/scripts/validate_source_breadth.py",
            "--playwright-raw",
            playwright_raw,
            "--jobspy-raw",
            jobspy_raw,
        ]
    )
    return latest_since("*source-breadth-filtered.json", SOURCE_VALIDATION_DIR, since_ts)


def main() -> int:
    args = parse_args()
    run_started_at = datetime.now().isoformat(timespec="seconds")
    stage_metrics: dict[str, dict] = {}
    artifacts: dict[str, object] = {}
    if args.execute_sends and args.parallel_generation_outreach:
        raise SystemExit("--execute-sends is intentionally not supported with --parallel-generation-outreach.")
    hours_old = window_to_hours(args.window)

    sync_applied_pdfs()

    needs_linkedin = (not args.skip_linkedin) or bool(args.prepare_outreach)
    if needs_linkedin and not args.skip_linkedin_preflight:
        run(["./discovery/scripts/ensure_chrome_9222.sh"])

    if not args.skip_linkedin:
        stage_started = _start_stage(stage_metrics, "linkedin")
        artifact_since = time.time()
        run(["./discovery/scripts/run_linkedin_discovery.sh", args.window])
        _finish_stage(stage_metrics, "linkedin", stage_started)
        artifacts["linkedin_scored"] = latest_since("linkedin_live_scored_*.json", LOGS_DIR, artifact_since)
    else:
        _skip_stage(stage_metrics, "linkedin")

    if not args.skip_handshake:
        stage_started = _start_stage(stage_metrics, "handshake")
        artifact_since = time.time()
        run(["./discovery/scripts/run_handshake_discovery.sh", args.window])
        _finish_stage(stage_metrics, "handshake", stage_started)
        artifacts["handshake_log"] = latest_since("handshake_import_*.json", LOGS_DIR, artifact_since)
    else:
        _skip_stage(stage_metrics, "handshake")

    if not args.skip_jobspy:
        stage_started = _start_stage(stage_metrics, "jobspy")
        artifact_since = time.time()
        jobspy_results = _effective_jobspy_results(args)
        jobspy_query_indices = _effective_jobspy_query_indices(args)
        jobspy_timeout = _effective_jobspy_fetch_timeout(args)
        artifacts["jobspy_query_indices"] = jobspy_query_indices or "all"
        artifacts["jobspy_results"] = jobspy_results or "scraper_default"
        artifacts["jobspy_fetch_timeout"] = jobspy_timeout
        fetch_cmd: list[object] = [PYTHON, "discovery/scripts/fetch_jobspy_breadth.py", "--hours-old", hours_old]
        if jobspy_results:
            fetch_cmd.extend(["--results", jobspy_results])
        for query_index in jobspy_query_indices:
            fetch_cmd.extend(["--query-index", query_index])
        jobspy_fetch = run_capture(fetch_cmd, check=False, timeout=jobspy_timeout)
        if jobspy_fetch.returncode != 0:
            print(f"[warn] Skipping JobSpy validation/scoring because fetch exited with {jobspy_fetch.returncode}.", file=sys.stderr)
            fallback_raw = _write_empty_jobspy_raw(hours_old, "timeout" if jobspy_fetch.returncode == 124 else "fetch_failed")
            artifacts["jobspy_raw"] = fallback_raw
            artifacts["source_breadth"] = _build_source_breadth(fallback_raw, since_ts=artifact_since)
            _finish_stage(
                stage_metrics,
                "jobspy",
                stage_started,
                status="timed_out" if jobspy_fetch.returncode == 124 else "failed",
                returncode=jobspy_fetch.returncode,
            )
        else:
            jobspy_raw = latest(f"jobspy_breadth_raw_{hours_old}h_*.json", LOGS_DIR)
            artifacts["jobspy_raw"] = jobspy_raw
            source_breadth = _build_source_breadth(jobspy_raw, since_ts=artifact_since)
            if source_breadth is None:
                _finish_stage(stage_metrics, "jobspy", stage_started, status="failed")
                raise SystemExit("Could not build source breadth after JobSpy fetch.")
            artifacts["source_breadth"] = source_breadth
            run(
                [
                    PYTHON,
                    "discovery/scripts/run_jobspy_scoring_lane.py",
                    "--source-breadth",
                    source_breadth,
                    "--jobspy-raw",
                    jobspy_raw,
                    "--limit",
                    args.jobspy_score_limit,
                ]
            )
            artifacts["jobspy_scored"] = latest_since("jobspy_filtered_scored_*.json", LOGS_DIR, artifact_since)
            _finish_stage(stage_metrics, "jobspy", stage_started)
    else:
        _skip_stage(stage_metrics, "jobspy")
        artifact_since = time.time()
        fallback_raw = _write_empty_jobspy_raw(hours_old, "skip_jobspy")
        artifacts["jobspy_raw"] = fallback_raw
        artifacts["source_breadth"] = _build_source_breadth(fallback_raw, since_ts=artifact_since)

    if not args.skip_startup_apply:
        stage_started = _start_stage(stage_metrics, "startup_apply")
        artifact_since = time.time()
        run(
            [
                PYTHON,
                "discovery/auto/startup_apply_pipeline.py",
                "--limit-companies",
                args.startup_limit_companies,
                "--limit-jobs",
                args.startup_limit_jobs,
            ]
        )
        _finish_stage(stage_metrics, "startup_apply", stage_started)
        artifacts["startup_apply_log"] = latest_since("startup_apply_*.txt", LOGS_DIR, artifact_since)
    else:
        _skip_stage(stage_metrics, "startup_apply")

    if not args.skip_relationship_discovery:
        stage_started = _start_stage(stage_metrics, "relationship_discovery")
        for source_id in RELATIONSHIP_SOURCES:
            run(
                [
                    OUTREACH_PYTHON,
                    "main.py",
                    "discover-source",
                    "--source-id",
                    source_id,
                    "--limit",
                    args.relationship_source_limit,
                ],
                cwd=OUTREACH_ROOT,
            )
        _finish_stage(stage_metrics, "relationship_discovery", stage_started)
    else:
        _skip_stage(stage_metrics, "relationship_discovery")

    stage_started = _start_stage(stage_metrics, "startup_source_report")
    artifact_since = time.time()
    run(
        [
            PYTHON,
            "discovery/scripts/build_startup_source_report.py",
            "--limit-companies",
            args.startup_limit_companies,
            "--limit-jobs",
            args.startup_limit_jobs,
        ]
    )
    _finish_stage(stage_metrics, "startup_source_report", stage_started)
    artifacts["startup_report"] = latest_since("*startup-source-report.json", SOURCE_VALIDATION_DIR, artifact_since)

    stage_started = _start_stage(stage_metrics, "action_queue")
    action_queue_path = build_action_queue(args)
    _finish_stage(stage_metrics, "action_queue", stage_started)
    print(f"\nFinal action queue: {action_queue_path}")
    print(f"Final action report: {action_queue_path.with_suffix('.html')}")
    source_metrics_path = write_source_run_metrics(
        args=args,
        run_started_at=run_started_at,
        stage_metrics=stage_metrics,
        artifacts=artifacts,
        action_queue_path=action_queue_path,
    )
    print(f"Final source metrics: {source_metrics_path}")

    generation_proc: subprocess.Popen | None = None
    if args.run_generation and args.prepare_outreach and args.parallel_generation_outreach:
        run(
            [
                OUTREACH_PYTHON,
                "main.py",
                "import-resume-jobs",
                "--jobs-xlsx",
                "../ResumeGenerator v1/discovery/jobs.xlsx",
            ],
            cwd=OUTREACH_ROOT,
        )
        generation_proc = start(
            [
                PYTHON,
                "jobs.py",
                "--no-color",
                "generate",
                "--queue",
                "--parallel",
                args.resume_parallel,
            ]
        )
        companies = selected_outreach_companies(
            action_queue_path,
            app_limit=max(args.app_outreach_limit, 0),
            relationship_limit=max(args.relationship_outreach_limit, 0),
        )
        print(f"\nOutreach companies selected from {action_queue_path.name}: {companies}")
        failures: list[str] = []
        for company in companies:
            result = run(
                [OUTREACH_PYTHON, "main.py", "run", "--company", company, "--company-mode", "startup"],
                cwd=OUTREACH_ROOT,
                check=False,
            )
            if result.returncode != 0:
                failures.append(company)
                print(f"[warn] Outreach artifact generation failed for {company}; continuing.")
        if failures:
            print(f"[warn] Outreach failures: {failures}")
    else:
        if args.run_generation:
            run([PYTHON, "jobs.py", "--no-color", "generate", "--queue", "--parallel", args.resume_parallel])
        if args.prepare_outreach:
            run_outreach_from_action_queue(args, action_queue_path)

    if generation_proc is not None:
        return_code = generation_proc.wait()
        if return_code != 0:
            raise SystemExit(return_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
