#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, NamedTuple

ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
OUTREACH_ROOT = ROOT.parent / "Outreach"
PYTHON = ROOT / "venv" / "bin" / "python"
OUTREACH_PYTHON = OUTREACH_ROOT / ".venv" / "bin" / "python"
LINKEDIN_BROWSER_OWNER_ENV = "RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN"

RELATIONSHIP_SOURCES = (
    "yc_sf_bay_hiring",
    "yc_los_angeles",
    "builtin_la_companies",
    "builtin_sf_companies",
)
# JobSpy remains available for ad-hoc Lane B breadth tests, but its active daily
# and weekly write path is deliberately demoted to the 13 Lane A queries. Lane B
# discovery is owned by the higher-yield LinkedIn browser path.
DAILY_JOBSPY_QUERY_INDICES = tuple(range(13))
WEEKLY_JOBSPY_QUERY_INDICES = tuple(range(13))
WEEKLY_JOBSPY_RESULTS = 60

class ArtifactCommandResult(NamedTuple):
    status: str
    returncode: int
    artifact: Path | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "returncode": self.returncode,
            "artifact": str(self.artifact or ""),
        }


def _cmd_text(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(
    cmd: list[object], *, cwd: Path = ROOT, check: bool = True
) -> subprocess.CompletedProcess:
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
    popen_args = [str(part) for part in cmd]
    try:
        proc = subprocess.Popen(
            popen_args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        result = subprocess.CompletedProcess(popen_args, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        print(
            f"[warn] Command timed out after {timeout}s: {_cmd_text(cmd)}",
            file=sys.stderr,
        )
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
            stdout, stderr = proc.communicate()
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        return subprocess.CompletedProcess(popen_args, 124, stdout, stderr)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result


def start(cmd: list[object], *, cwd: Path = ROOT) -> subprocess.Popen:
    print(f"\n$ {_cmd_text(cmd)}")
    return subprocess.Popen([str(part) for part in cmd], cwd=cwd)


def applied_pdf_status_report() -> dict[str, object]:
    return {
        "status": "skipped_deprecated",
        "mutated": False,
        "reason": (
            "Resume.pdf presence is not proof of submission; applied/closed "
            "status requires the reviewed archive-first lifecycle command"
        ),
    }


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _browser_is_owned_by_current_run(command: str, port: str) -> bool:
    token = os.environ.get(LINKEDIN_BROWSER_OWNER_ENV, "").strip()
    if not token:
        return _env_flag("RESUMEGEN_ALLOW_UNOWNED_LINKEDIN_BROWSER_RESET")
    return (
        f"--resume-generator-browser-owner={token}" in command
        and f"--remote-debugging-port={port}" in command
    )


def reset_linkedin_chrome_session(reason: str) -> bool:
    """Restart the dedicated Chrome/CDP session when it becomes attach-hostile."""
    print(f"\n==> Resetting LinkedIn Chrome session ({reason})")
    port = os.environ.get("LINKEDIN_DEBUG_PORT", "9222").strip() or "9222"
    try:
        pids_result = subprocess.run(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print("[warn] lsof not found; cannot reset Chrome by port.", file=sys.stderr)
        return False

    pids = [int(line) for line in pids_result.stdout.splitlines() if line.strip().isdigit()]
    reset = False
    for pid in pids:
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            capture_output=True,
            check=False,
        ).stdout
        if (
            "Google Chrome" not in command
            or f"--remote-debugging-port={port}" not in command
        ):
            print(
                f"[warn] Refusing to kill non-canonical port owner pid={pid}: {command.strip()}",
                file=sys.stderr,
            )
            continue
        if not _browser_is_owned_by_current_run(command, port):
            print(
                f"[warn] Refusing to reset an unowned LinkedIn debug session pid={pid}.",
                file=sys.stderr,
            )
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            reset = True
        except ProcessLookupError:
            pass
    if reset:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            still_listening = subprocess.run(
                ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
                text=True,
                capture_output=True,
                check=False,
            ).stdout.strip()
            if not still_listening:
                break
            time.sleep(0.5)
    launch = run(
        ["./discovery/scripts/ensure_chrome_9222.sh", "https://www.linkedin.com/feed/"],
        check=False,
    )
    if launch.returncode != 0:
        print(f"[warn] Chrome relaunch failed with {launch.returncode}.", file=sys.stderr)
        return False
    time.sleep(5)
    check = run(["./discovery/scripts/check_linkedin_live.sh"], check=False)
    return check.returncode == 0


def ensure_linkedin_chrome_session(reason: str) -> bool:
    """Keep a healthy CDP session, resetting it only after preflight fails."""
    preflight = run(
        ["./discovery/scripts/ensure_chrome_9222.sh", "https://www.linkedin.com/feed/"],
        check=False,
    )
    if preflight.returncode == 0:
        return True
    return reset_linkedin_chrome_session(reason)


def latest(pattern: str, directory: Path) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {directory / pattern}")
    return matches[-1]


def latest_since(pattern: str, directory: Path, since_ts: float) -> Path | None:
    matches = [
        path for path in directory.glob(pattern) if path.stat().st_mtime >= since_ts - 2
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
        decision = (
            str(item.get("decision") or item.get("status") or "").strip() or "unknown"
        )
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def _decision_count(counts: dict[str, int], decision: str) -> int:
    wanted = decision.casefold()
    return sum(
        count
        for name, count in counts.items()
        if str(name).strip().casefold() == wanted
    )


def _fresh_score_rows(payload: dict) -> tuple[int, list[dict]]:
    try:
        attempted = max(0, int(payload.get("scored") or 0))
    except (TypeError, ValueError):
        attempted = 0
    jobs = payload.get("jobs") or []
    if not isinstance(jobs, list):
        jobs = []
    # linkedin_live writes freshly scored rows first, followed by review-cache hits.
    # The explicit scored count is therefore the artifact boundary between the two.
    return attempted, [row for row in jobs[:attempted] if isinstance(row, dict)]


def _accepted_per_minute(
    accepted: int, runtime_seconds: float | int | None
) -> float | None:
    if not runtime_seconds or runtime_seconds <= 0:
        return None
    return round(accepted / (runtime_seconds / 60), 3)


def _score_artifact_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    jobs = [row for row in (payload.get("jobs") or []) if isinstance(row, dict)]
    decision_counts = _decision_counts(jobs)
    freshly_scored_count, freshly_scored_rows = _fresh_score_rows(payload)
    fresh_decision_counts = _decision_counts(freshly_scored_rows)
    return {
        "artifact": str(path) if path else "",
        "raw_count": payload.get("extracted"),
        "reviewed_count": payload.get("reviewed"),
        "freshly_scored_count": freshly_scored_count,
        "existing_skipped": payload.get("existing_skipped"),
        "cache_skipped": payload.get("cache_skipped"),
        "accepted_for_write": payload.get("accepted_for_write"),
        "new_after_dedup": payload.get("new_after_dedup"),
        "decision_counts": decision_counts,
        "fresh_decision_counts": fresh_decision_counts,
        "error_count": _decision_count(fresh_decision_counts, "Error"),
        "reviewed_error_count": _decision_count(decision_counts, "Error"),
    }


def _linkedin_scoring_stage_status(path: Path | None) -> str:
    if path is None or path.is_symlink() or not path.is_file():
        return "failed_missing_scored_artifact"
    payload = _load_json(path)
    jobs = payload.get("jobs")
    try:
        attempted_raw = payload["scored"]
        reviewed_raw = payload["reviewed"]
        cache_skipped_raw = payload["cache_skipped"]
        if any(
            isinstance(value, bool)
            for value in (attempted_raw, reviewed_raw, cache_skipped_raw)
        ):
            raise ValueError
        attempted = int(attempted_raw)
        reviewed = int(reviewed_raw)
        cache_skipped = int(cache_skipped_raw)
    except (KeyError, TypeError, ValueError):
        return "failed_invalid_scored_artifact"
    if (
        not isinstance(jobs, list)
        or any(not isinstance(row, dict) for row in jobs)
        or min(attempted, reviewed, cache_skipped) < 0
        or reviewed != len(jobs)
        or attempted + cache_skipped != reviewed
    ):
        return "failed_invalid_scored_artifact"
    metrics = _score_artifact_metrics(path)
    errors = int(metrics.get("error_count") or 0)
    if attempted <= 0:
        # A cache-only run did not attempt scoring and must not be treated as a
        # scorer outage because cached review decisions happen to be present.
        return "ran"
    if errors >= attempted:
        return "failed_scoring"
    if errors:
        return "partial_failed_scoring"
    return "ran"


def _handshake_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    counts = payload.get("counts") or {}
    scored = payload.get("scored") or []
    decision_counts = _decision_counts(scored)
    return {
        "artifact": str(path) if path else "",
        "artifact_status": payload.get("status"),
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
        "error_count": counts.get("error_count", counts.get("fetch_failed", 0)),
    }


def _jobspy_metrics_from_artifacts(
    raw_path: Path | None, breadth_path: Path | None, scored_path: Path | None
) -> dict:
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
        "unsure": len(jobspy_bucket.get("unsure") or []),
        "outreach_signal": len(jobspy_bucket.get("outreach_signal") or []),
        "selected_for_scoring": scored.get("raw_count"),
        "freshly_scored_count": scored.get("freshly_scored_count"),
        "accepted_for_write": scored.get("accepted_for_write"),
        "cache_skipped": scored.get("cache_skipped"),
        "existing_skipped": scored.get("existing_skipped"),
        "decision_counts": scored.get("decision_counts") or {},
        "error_count": scored.get("error_count") or 0,
    }


def _startup_apply_artifact_metrics(path: Path | None) -> dict:
    payload = _load_artifact_json(path)
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    discovered = (
        counts.get("discovered_by_source")
        if isinstance(counts.get("discovered_by_source"), dict)
        else {}
    )
    new = (
        counts.get("new_by_source")
        if isinstance(counts.get("new_by_source"), dict)
        else {}
    )
    selected = (
        counts.get("selected_by_source")
        if isinstance(counts.get("selected_by_source"), dict)
        else {}
    )
    statuses = (
        counts.get("status_counts")
        if isinstance(counts.get("status_counts"), dict)
        else {}
    )
    decisions = (
        counts.get("decision_counts")
        if isinstance(counts.get("decision_counts"), dict)
        else {}
    )
    source_ids = sorted(set(discovered) | set(new) | set(selected))
    source_rows = {
        source_id: {
            "discovered": int(discovered.get(source_id) or 0),
            "new": int(new.get(source_id) or 0),
            "selected": int(selected.get(source_id) or 0),
        }
        for source_id in source_ids
    }
    return {
        "artifact": str(path) if path else "",
        "artifact_schema": payload.get("schema"),
        "artifact_version": payload.get("version"),
        "artifact_status": payload.get("status"),
        "discovered_count": int(counts.get("discovered") or 0),
        "new_count": int(counts.get("new") or 0),
        "freshly_scored_count": int(counts.get("scored") or 0),
        "accepted_for_write": int(statuses.get("queued") or 0),
        "review_count": int(statuses.get("review") or 0),
        "skipped_count": int(statuses.get("skipped") or 0),
        "written_count": int(counts.get("written") or 0),
        "source_counts": source_rows,
        "decision_counts": decisions,
        "error_count": int(counts.get("error_count") or 0),
    }


def _startup_report_metrics(path: Path | None) -> dict:
    payload = _load_json(path)
    startup_apply = payload.get("startup_apply") or {}
    relationship = payload.get("relationship_lane") or {}
    return {
        "artifact": str(path) if path else "",
        "startup_apply_status": startup_apply.get("status"),
        "startup_apply_mode": startup_apply.get("mode"),
        "startup_apply_run_artifact": startup_apply.get("run_artifact"),
        "startup_apply_discovered": startup_apply.get("discovered_counts") or {},
        "startup_apply_new": startup_apply.get("new_counts") or {},
        "startup_apply_verdicts": startup_apply.get("verdict_counts") or {},
        "startup_apply_source_verdicts": startup_apply.get("source_verdict_counts")
        or {},
        "relationship_status": relationship.get("status"),
        "relationship_mode": relationship.get("mode"),
        "relationship_error_count": relationship.get("error_count", 0),
        "relationship_artifacts": relationship.get("artifacts") or {},
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
        "decision_counts": metrics.get("decision_counts") or {},
        "accepted_per_minute": _accepted_per_minute(accepted, runtime),
        "details": metrics,
    }


def _load_artifact_json(path: Path | None) -> dict:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _linkedin_followup_draft_metrics(path: Path | None) -> dict:
    payload = _load_artifact_json(path)
    if not payload:
        return {}
    results = list(payload.get("results") or [])
    recommendations: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for draft in results:
        recommendation = str(draft.get("send_recommendation") or "unknown")
        kind = str(draft.get("draft_kind") or "unknown")
        recommendations[recommendation] = recommendations.get(recommendation, 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1
    summary = payload.get("summary") or payload.get("action_summary") or {}
    return {
        "artifact": str(path),
        "count": int(payload.get("count") or len(results)),
        "recommendations": recommendations,
        "kinds": kinds,
        "follow_up_candidates": summary.get("follow_up_candidates"),
        "reply_candidates": summary.get("reply_candidates"),
        "external_action_items": summary.get("external_action_items"),
        "action_items": summary.get("action_items") or [],
        "by_company": summary.get("by_company") or {},
    }


def _linkedin_followup_send_metrics(path: Path | None) -> dict:
    payload = _load_artifact_json(path)
    if not payload:
        return {}
    return {
        "artifact": str(path),
        "execute": payload.get("execute"),
        "total_drafts": payload.get("total_drafts", payload.get("count")),
        "eligible_count": payload.get("eligible_count", payload.get("count")),
        "sent_count": (payload.get("status_counts") or {}).get("sent", 0),
        "skipped_by_recommendation_count": payload.get("skipped_by_recommendation_count", 0),
        "status_counts": payload.get("status_counts") or {},
        "touchpoints_added": payload.get("touchpoints_added"),
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
    startup_apply = _startup_apply_artifact_metrics(
        artifacts.get("startup_apply_run")
    )
    startup_report = _startup_report_metrics(artifacts.get("startup_report"))
    action_queue = _action_queue_metrics(action_queue_path)
    linkedin_followup_drafts = _linkedin_followup_draft_metrics(artifacts.get("linkedin_followup_drafts"))
    linkedin_followup_sends = _linkedin_followup_send_metrics(artifacts.get("linkedin_followup_send_results"))
    relationship_stage = stage_metrics.get("relationship_discovery", {})

    sources = {
        "linkedin": _source_row(
            stage=stage_metrics.get("linkedin", {}), metrics=linkedin
        ),
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
            "error_count": startup_report.get("relationship_error_count", 0),
            "artifacts": startup_report.get("relationship_artifacts") or {},
        },
    }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": _manifest_run_id(getattr(args, "run_id", "")),
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
        "linkedin_followups": {
            "drafts": linkedin_followup_drafts,
            "sends": linkedin_followup_sends,
        },
    }

    SOURCE_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = SOURCE_VALIDATION_DIR / f"{stamp}-source-run-metrics.json"
    md_path = json_path.with_suffix(".md")
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
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
            "## LinkedIn Follow-Ups",
            "",
            f"- Drafts: {payload.get('linkedin_followups', {}).get('drafts', {})}",
            f"- Sends: {payload.get('linkedin_followups', {}).get('sends', {})}",
            "",
            "## Startup Split",
            "",
            f"- Startup apply status: {payload['startup_source_report']['startup_apply_status']}",
            f"- Startup apply mode: {payload['startup_source_report']['startup_apply_mode']}",
            f"- Startup apply exact run artifact: {payload['startup_source_report']['startup_apply_run_artifact']}",
            f"- Startup apply discovered: {payload['startup_source_report']['startup_apply_discovered']}",
            f"- Startup apply new: {payload['startup_source_report']['startup_apply_new']}",
            f"- Startup apply verdicts: {payload['startup_source_report']['startup_apply_verdicts']}",
            f"- Startup relationship status: {payload['startup_source_report']['relationship_status']}",
            f"- Startup relationship mode: {payload['startup_source_report']['relationship_mode']}",
            f"- Startup relationship errors: {payload['startup_source_report']['relationship_error_count']}",
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


def _claim_company(seen: set[str], company: str) -> bool:
    company = company.strip()
    key = _company_key(company)
    if not company or key in seen:
        return False
    seen.add(key)
    return True


def _outreach_target(item: dict[str, object], *, bucket: str) -> dict[str, str]:
    return {
        "company": str(item.get("company") or "").strip(),
        "target_role_title": str(
            item.get("role_title") or item.get("signal_title") or ""
        ).strip(),
        "source": str(item.get("source") or "").strip(),
        "queue_bucket": bucket,
    }


def selected_outreach_targets(
    action_queue_path: Path, *, app_limit: int, relationship_limit: int
) -> list[dict[str, str]]:
    payload = json.loads(action_queue_path.read_text(encoding="utf-8"))
    targets: list[dict[str, str]] = []
    seen: set[str] = set()

    if app_limit > 0:
        app_added = 0
        for item in payload.get("application_plus_outreach") or []:
            if not isinstance(item, dict):
                continue
            target = _outreach_target(item, bucket="application_plus_outreach")
            if _claim_company(seen, target["company"]):
                targets.append(target)
                app_added += 1
            if app_added >= app_limit:
                break

    relationship_added = 0
    if relationship_limit > 0:
        for item in payload.get("outreach_only_today") or []:
            if not isinstance(item, dict):
                continue
            target = _outreach_target(item, bucket="outreach_only_today")
            if _claim_company(seen, target["company"]):
                targets.append(target)
                relationship_added += 1
            if relationship_added >= relationship_limit:
                break
    return targets


def selected_outreach_companies(
    action_queue_path: Path, *, app_limit: int, relationship_limit: int
) -> list[str]:
    return [
        target["company"]
        for target in selected_outreach_targets(
            action_queue_path,
            app_limit=app_limit,
            relationship_limit=relationship_limit,
        )
    ]


def target_outreach_targets(
    action_queue_path: Path, *, company_limit: int
) -> list[dict[str, str]]:
    payload = json.loads(action_queue_path.read_text(encoding="utf-8"))
    targets: list[dict[str, str]] = []
    seen: set[str] = set()
    for bucket in (
        "application_plus_outreach",
        "outreach_only_today",
        "relationship_buffer",
    ):
        for item in payload.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            target = _outreach_target(item, bucket=bucket)
            if _claim_company(seen, target["company"]):
                targets.append(target)
            if len(targets) >= company_limit:
                return targets
    return targets


def target_outreach_companies(
    action_queue_path: Path, *, company_limit: int
) -> list[str]:
    return [
        target["company"]
        for target in target_outreach_targets(
            action_queue_path,
            company_limit=company_limit,
        )
    ]


def _artifact_from_output(output: str) -> Path | None:
    for line in output.splitlines():
        if line.startswith("Artifact: "):
            raw = line.split("Artifact: ", 1)[1].strip()
            path = Path(raw)
            return path if path.is_absolute() else OUTREACH_ROOT / path
    return None


def _candidate_mentions_company(company: str, candidate: dict) -> bool:
    """Require current-employer-shaped evidence, never a name/pass match."""

    company_tokens = re.findall(r"[a-z0-9]+", company.casefold())
    if not company_tokens:
        return False
    company_key = "".join(company_tokens)
    for field in ("current_company", "current_employer", "employer", "company"):
        value_key = "".join(
            re.findall(r"[a-z0-9]+", str(candidate.get(field) or "").casefold())
        )
        if value_key and value_key == company_key:
            return True
    if len(company_key) < 4:
        return False

    alias_pattern = r"\s+".join(re.escape(token) for token in company_tokens)
    end_boundary = r"(?=$|\s*(?:[|·,;()]|[-—]\s)|\.(?:\s|$))"
    patterns = (
        rf"(?:@\s*|\bat\s+){alias_pattern}{end_boundary}",
        rf"\b(?:founder|co-founder|ceo|cto|cpo|head\s+of\s+product|product)"
        rf"\s+(?:of\s+|at\s+|@\s*|[-—]\s*){alias_pattern}{end_boundary}",
        rf"\bcurrent:\s*[^|;]{{0,120}}?{alias_pattern}{end_boundary}",
    )
    for field in ("title", "headline", "snippet", "raw_text"):
        text = re.sub(
            r"\s+",
            " ",
            str(candidate.get(field) or "").casefold(),
        ).strip()
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match is None:
                continue
            segment_start = max(
                text.rfind("|", 0, match.start()),
                text.rfind("·", 0, match.start()),
                text.rfind(";", 0, match.start()),
                text.rfind(",", 0, match.start()),
            )
            prefix = text[segment_start + 1 : match.start()]
            if re.search(r"\b(?:ex|former|formerly|past|previously)\b", prefix):
                continue
            return True
    return False


def _company_filter_failed(payload: dict) -> bool:
    status = str(payload.get("company_filter_status") or "").strip().casefold()
    if status.startswith("failed"):
        return True
    if "Could not find an exact company suggestion for" in str(
        payload.get("company_filter_error") or ""
    ):
        return True
    for summary in payload.get("pass_summaries") or []:
        if not isinstance(summary, dict):
            continue
        alias_errors = " | ".join(
            str(item) for item in summary.get("alias_errors") or []
        )
        if (
            summary.get("pass_name") == "startup_company_coverage"
            and summary.get("fallback_used")
            and "Could not find an exact company suggestion for" in alias_errors
        ):
            return True
    return False


def _coverage_only(payload: dict, candidate: dict) -> bool:
    pool = payload.get("startup_pool")
    if isinstance(pool, dict) and bool(pool.get("coverage_only")):
        return True
    if "startup_company_coverage" in {
        str(item) for item in candidate.get("passes") or []
    }:
        return True
    return any(
        isinstance(summary, dict)
        and (
            summary.get("pass_name") == "startup_company_coverage"
            or bool(summary.get("coverage_only"))
        )
        for summary in payload.get("pass_summaries") or []
    )


def _candidate_score(candidate: dict) -> int:
    try:
        return int(candidate.get("score"))
    except (TypeError, ValueError):
        return -999


def _note_is_sendable(candidate: dict) -> bool:
    qc = candidate.get("polished_note_qc") or candidate.get("note_qc") or {}
    return qc.get("verdict") == "send"


def _normalized_company_identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _has_bound_target_company_evidence(company: str, candidate: dict) -> bool:
    """Require the Outreach discovery pass to bind the person to this company.

    A high score or second-degree connection is never a substitute for current-
    employer evidence.  This fail-closed gate also makes older artifacts that
    predate the binding fields ineligible for unattended sends.
    """

    expected = _normalized_company_identity(company)
    observed = _normalized_company_identity(
        candidate.get("target_company_evidence_company")
    )
    return bool(
        expected
        and candidate.get("target_company_match") is True
        and observed == expected
    )


def _safe_unattended_candidate(
    company: str,
    candidate: dict,
    *,
    min_score: int,
    source_payload: dict | None = None,
) -> bool:
    payload = source_payload or {}
    if _company_filter_failed(payload):
        return False
    if _coverage_only(payload, candidate) and not _candidate_mentions_company(
        company,
        candidate,
    ):
        return False
    if not candidate.get("linkedin_url") or candidate.get("existing_connection"):
        return False
    if not _note_is_sendable(candidate):
        return False
    score = _candidate_score(candidate)
    if score < min_score:
        return False
    return _has_bound_target_company_evidence(company, candidate)


def _bounded_command_error(result: subprocess.CompletedProcess, *, limit: int = 1200) -> str:
    raw = str(result.stderr or result.stdout or "")
    normalized = " ".join(raw.split())
    return normalized[-limit:]


def _filtered_send_artifact(
    source_artifact: Path, *, company: str, min_score: int, limit: int
) -> tuple[Path | None, int]:
    payload = json.loads(source_artifact.read_text(encoding="utf-8"))
    if _company_filter_failed(payload):
        return None, 0
    safe_results = [
        item
        for item in payload.get("results") or []
        if _safe_unattended_candidate(
            company,
            item,
            min_score=min_score,
            source_payload=payload,
        )
    ]
    if limit > 0:
        safe_results = safe_results[:limit]
    if not safe_results:
        return None, 0
    filtered_payload = {
        **payload,
        "results": safe_results,
        "target_send_filter": {
            "source_artifact": str(source_artifact),
            "min_score": min_score,
            "limit": limit,
            "safe_count": len(safe_results),
        },
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "company"
    out_path = OUTREACH_ROOT / "artifacts" / f"{stamp}-target-send-{slug}.json"
    out_path.write_text(
        json.dumps(filtered_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out_path, len(safe_results)


def _sent_count_from_batch(batch_artifact: Path | None) -> int:
    if not batch_artifact or not batch_artifact.exists():
        return 0
    payload = json.loads(batch_artifact.read_text(encoding="utf-8"))
    return sum(
        1
        for item in payload.get("results") or []
        if str(item.get("status") or "").lower() == "sent"
    )


def _status_counts_from_batch(batch_artifact: Path | None) -> dict[str, int]:
    if not batch_artifact or not batch_artifact.exists():
        return {}
    payload = json.loads(batch_artifact.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown").strip().casefold()
        counts[status] = counts.get(status, 0) + 1
    return counts


def run_targeted_outreach_from_action_queue(
    args: argparse.Namespace, action_queue_path: Path
) -> dict[str, object]:
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
    targets = target_outreach_targets(
        action_queue_path, company_limit=max(args.max_outreach_companies, 1)
    )
    companies = [target["company"] for target in targets]
    print(
        f"\nTargeted outreach companies selected from {action_queue_path.name}: {companies}"
    )
    target_sends = max(args.target_sends, 0)
    sent_total = 0
    failures: list[str] = []
    unresolved: list[str] = []
    skipped: list[str] = []
    company_runs: list[dict[str, object]] = []
    invite_send_artifacts: list[str] = []
    for target in targets:
        company = target["company"]
        if sent_total >= target_sends:
            break
        company_run: dict[str, object] = {
            "company": company,
            "target_role_title": target["target_role_title"],
            "source": target["source"],
            "queue_bucket": target["queue_bucket"],
            "status": "preparing",
            "prep_artifact": "",
            "filtered_send_artifact": "",
            "invite_send_artifact": "",
            "safe_candidate_count": 0,
            "sent_count": 0,
        }
        company_runs.append(company_run)
        prep_cmd: list[object] = [
            OUTREACH_PYTHON,
            "main.py",
            "run",
            "--company",
            company,
            "--company-mode",
            "startup",
        ]
        if target["target_role_title"]:
            prep_cmd.extend(["--target-role-title", target["target_role_title"]])
        prep = run_capture(
            prep_cmd,
            cwd=OUTREACH_ROOT,
            check=False,
            timeout=args.company_prep_timeout,
        )
        company_run["prep_returncode"] = prep.returncode
        if prep.returncode != 0:
            failures.append(company)
            company_run["status"] = "prep_failed"
            company_run["prep_error"] = _bounded_command_error(prep)
            print(
                f"[warn] Outreach artifact generation failed for {company}; continuing."
            )
            continue
        artifact = _artifact_from_output(prep.stdout)
        if not artifact or not artifact.exists():
            failures.append(company)
            company_run["status"] = "prep_artifact_missing"
            print(
                f"[warn] Could not resolve outreach artifact for {company}; continuing."
            )
            continue
        company_run["prep_artifact"] = str(artifact)
        remaining = target_sends - sent_total
        per_company_limit = args.send_limit or args.per_company_send_limit
        send_limit = (
            min(remaining, per_company_limit) if per_company_limit > 0 else remaining
        )
        filtered_artifact, safe_count = _filtered_send_artifact(
            artifact,
            company=company,
            min_score=args.send_min_score,
            limit=send_limit,
        )
        company_run["safe_candidate_count"] = safe_count
        if not filtered_artifact:
            skipped.append(company)
            company_run["status"] = "no_safe_candidates"
            print(
                f"[info] No safe unattended invite candidates for {company}; continuing."
            )
            continue
        company_run["filtered_send_artifact"] = str(filtered_artifact)
        print(
            f"[info] Sending up to {safe_count} safe candidates for {company}; target remaining={remaining}."
        )
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
        company_run["send_returncode"] = send.returncode
        if send.returncode != 0:
            failures.append(company)
            company_run["status"] = "send_failed"
            company_run["send_error"] = _bounded_command_error(send)
            print(f"[warn] Invite send failed for {company}; continuing.")
            continue
        batch_artifact = _artifact_from_output(send.stdout)
        if batch_artifact is None or not batch_artifact.is_file():
            failures.append(company)
            company_run["status"] = "send_artifact_missing"
            print(
                f"[warn] Invite send for {company} returned success without a readable batch artifact; continuing."
            )
            continue
        status_counts = _status_counts_from_batch(batch_artifact)
        sent_now = int(status_counts.get("sent") or 0) + int(
            status_counts.get("sent_without_note") or 0
        )
        unknown_now = int(status_counts.get("send_unknown_reserved") or 0)
        company_run["invite_send_artifact"] = str(batch_artifact)
        company_run["sent_count"] = sent_now
        company_run["status_counts"] = status_counts
        if unknown_now and sent_now:
            company_run["status"] = "partial_send_unknown_reserved"
            unresolved.append(company)
        elif unknown_now:
            company_run["status"] = "send_unknown_reserved"
            unresolved.append(company)
        else:
            company_run["status"] = "sent" if sent_now else "completed_no_sends"
        invite_send_artifacts.append(str(batch_artifact))
        sent_total += sent_now
        print(
            f"[info] {company}: sent_now={sent_now}; sent_total={sent_total}/{target_sends}."
        )
    print(f"\nTargeted outreach send total: {sent_total}/{target_sends}")
    if skipped:
        print(f"[info] Companies skipped with no safe unattended candidates: {skipped}")
    if failures:
        print(f"[warn] Outreach failures: {failures}")
    if unresolved:
        print(
            "[warn] Invite delivery requires signed-in reconciliation for: "
            f"{unresolved}"
        )
    return {
        "mode": "targeted_execute",
        "target_sends": target_sends,
        "sent_total": sent_total,
        "companies_selected": companies,
        "companies_attempted": len(company_runs),
        "company_runs": company_runs,
        "invite_send_artifacts": invite_send_artifacts,
        "skipped_companies": skipped,
        "failed_companies": failures,
        "unresolved_companies": unresolved,
    }


def run_outreach_from_action_queue(
    args: argparse.Namespace, action_queue_path: Path
) -> dict[str, object]:
    if args.execute_sends and args.target_sends > 0:
        return run_targeted_outreach_from_action_queue(args, action_queue_path)
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
    targets = selected_outreach_targets(
        action_queue_path,
        app_limit=max(args.app_outreach_limit, 0),
        relationship_limit=max(args.relationship_outreach_limit, 0),
    )
    companies = [target["company"] for target in targets]
    print(f"\nOutreach companies selected from {action_queue_path.name}: {companies}")
    failures: list[str] = []
    company_runs: list[dict[str, object]] = []
    for target in targets:
        company = target["company"]
        cmd: list[object] = [
            OUTREACH_PYTHON,
            "main.py",
            "run",
            "--company",
            company,
            "--company-mode",
            "startup",
        ]
        if target["target_role_title"]:
            cmd.extend(["--target-role-title", target["target_role_title"]])
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
        company_runs.append(
            {
                **target,
                "status": "prepared" if result.returncode == 0 else "prep_failed",
                "prep_returncode": result.returncode,
                "sent_count": 0,
            }
        )
        if result.returncode != 0:
            failures.append(company)
            print(
                f"[warn] Outreach artifact generation failed for {company}; continuing."
            )
    if failures:
        print(f"[warn] Outreach failures: {failures}")
    return {
        "mode": "prepare" if not args.execute_sends else "legacy_execute",
        "target_sends": max(args.target_sends, 0),
        "sent_total": 0,
        "companies_selected": companies,
        "companies_attempted": len(companies),
        "company_runs": company_runs,
        "invite_send_artifacts": [],
        "skipped_companies": [],
        "failed_companies": failures,
    }


def _outreach_artifact_from_text(value: str) -> Path | None:
    path = _readable_artifact_path(value, base_dir=OUTREACH_ROOT)
    return Path(path) if path else None


def run_linkedin_followup_pull(args: argparse.Namespace) -> ArtifactCommandResult:
    cmd: list[object] = [
        OUTREACH_PYTHON,
        "main.py",
        "pull-linkedin-followups",
        "--live",
        "--deep",
        "--apply-reconcile",
        "--update-offset",
        "--limit",
        args.linkedin_followup_limit,
        "--draft-limit",
        args.linkedin_followup_draft_limit,
    ]
    result = run_capture(
        cmd,
        cwd=OUTREACH_ROOT,
        check=False,
        timeout=args.linkedin_followup_timeout,
    )
    if result.returncode != 0:
        print(
            f"[warn] LinkedIn follow-up pull failed with {result.returncode}; continuing.",
            file=sys.stderr,
        )
        return ArtifactCommandResult("failed_command", int(result.returncode or 1))
    match = re.search(r"Draft artifact:\s*(.+)", result.stdout)
    if match:
        candidate = _outreach_artifact_from_text(match.group(1).strip())
        if candidate is not None:
            return ArtifactCommandResult("completed", 0, candidate)
    artifact = _artifact_from_output(result.stdout)
    if artifact and artifact.is_file():
        return ArtifactCommandResult("completed", 0, artifact.resolve())
    return ArtifactCommandResult("failed_missing_artifact", 1)


def run_linkedin_followup_send(
    args: argparse.Namespace,
    draft_artifact: Path,
) -> ArtifactCommandResult:
    cmd: list[object] = [
        OUTREACH_PYTHON,
        "main.py",
        "send-linkedin-followups",
        "--draft-artifact",
        draft_artifact,
        "--limit",
        args.linkedin_followup_send_limit,
    ]
    for recommendation in args.linkedin_followup_recommendation or ["safe_to_review"]:
        cmd.extend(["--recommendation", recommendation])
    if args.execute_linkedin_followups:
        cmd.append("--execute")
    result = run_capture(
        cmd,
        cwd=OUTREACH_ROOT,
        check=False,
        timeout=args.linkedin_followup_send_timeout,
    )
    if result.returncode != 0:
        print(
            f"[warn] LinkedIn follow-up send failed with {result.returncode}; continuing.",
            file=sys.stderr,
        )
        return ArtifactCommandResult("failed_command", int(result.returncode or 1))
    match = re.search(r"Artifact:\s*(.+)", result.stdout)
    if match:
        candidate = _outreach_artifact_from_text(match.group(1).strip())
        if candidate is not None:
            return ArtifactCommandResult("completed", 0, candidate)
    artifact = _artifact_from_output(result.stdout)
    if artifact and artifact.is_file():
        return ArtifactCommandResult("completed", 0, artifact.resolve())
    return ArtifactCommandResult("failed_missing_artifact", 1)


def score_partial_linkedin_raw(artifact_since: float) -> Path | None:
    partial_raw = latest_since("linkedin_live_raw_inflight_*.json", LOGS_DIR, artifact_since)
    if not partial_raw:
        return None
    print(f"[warn] Scoring partial LinkedIn raw artifact after timeout: {partial_raw}", file=sys.stderr)
    result = run(
        [PYTHON, "discovery/auto/linkedin_live.py", "--score-from-raw", partial_raw],
        check=False,
    )
    if result.returncode != 0:
        print(f"[warn] Partial LinkedIn scoring failed with {result.returncode}.", file=sys.stderr)
        return None
    return latest_since("linkedin_live_scored_*.json", LOGS_DIR, artifact_since)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Supervised daily application + outreach engine."
    )
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument("--skip-linkedin", action="store_true")
    parser.add_argument("--skip-handshake", action="store_true")
    parser.add_argument("--skip-jobspy", action="store_true")
    parser.add_argument("--skip-startup-apply", action="store_true")
    parser.add_argument("--skip-relationship-discovery", action="store_true")
    parser.add_argument(
        "--jobspy-results",
        type=int,
        default=0,
        help="Override JobSpy results per query/site. Default: 40 for 24h, 60 for 7d.",
    )
    parser.add_argument(
        "--jobspy-query-index",
        action="append",
        type=int,
        default=[],
        help="JobSpy query index to run; repeatable. Defaults: 24h uses PM/Product Ops/Growth/Strategy/APM/AI-PM; 7d adds focused MBA/AI strategy queries.",
    )
    parser.add_argument("--jobspy-score-limit", type=int, default=10)
    parser.add_argument(
        "--linkedin-discovery-timeout",
        type=int,
        default=1800,
        help="Timeout seconds for the LinkedIn discovery stage before scoring partial raw results.",
    )
    parser.add_argument(
        "--jobspy-fetch-timeout",
        type=int,
        default=0,
        help="Seconds before skipping the JobSpy breadth scrape. Default: 600 for 24h, 1800 for 7d.",
    )
    parser.add_argument("--startup-limit-companies", type=int, default=20)
    parser.add_argument("--startup-limit-jobs", type=int, default=50)
    parser.add_argument("--relationship-source-limit", type=int, default=25)
    parser.add_argument("--relationship-today", type=int, default=8)
    parser.add_argument("--run-generation", action="store_true")
    parser.add_argument("--resume-parallel", type=int, default=3)
    parser.add_argument("--prepare-outreach", action="store_true")
    parser.add_argument("--skip-linkedin-followups", action="store_true", help="Skip LinkedIn message reconcile/draft action list.")
    parser.add_argument("--linkedin-followup-limit", type=int, default=75, help="Maximum LinkedIn message threads to read for follow-up/reply actions.")
    parser.add_argument("--linkedin-followup-draft-limit", type=int, default=50, help="Maximum LinkedIn follow-up drafts to emit.")
    parser.add_argument("--linkedin-followup-timeout", type=int, default=180, help="Timeout seconds for LinkedIn follow-up reconcile/draft pull.")
    parser.add_argument("--execute-linkedin-followups", action="store_true", help="Actually send eligible LinkedIn follow-up drafts after reconcile.")
    parser.add_argument("--linkedin-followup-send-limit", type=int, default=10, help="Maximum eligible LinkedIn follow-up drafts to send.")
    parser.add_argument("--linkedin-followup-send-timeout", type=int, default=240, help="Timeout seconds for LinkedIn follow-up sends.")
    parser.add_argument(
        "--linkedin-followup-recommendation",
        action="append",
        default=[],
        help="Allowed send_recommendation for automatic follow-up sends; repeatable. Default: safe_to_review.",
    )
    parser.add_argument("--app-outreach-limit", type=int, default=3)
    parser.add_argument("--relationship-outreach-limit", type=int, default=2)
    parser.add_argument("--max-outreach-companies", type=int, default=24)
    parser.add_argument("--parallel-generation-outreach", action="store_true")
    parser.add_argument(
        "--execute-sends",
        action="store_true",
        help="Actually send LinkedIn invites after artifact generation.",
    )
    parser.add_argument(
        "--target-sends",
        type=int,
        default=25,
        help="Global send target for unattended --execute-sends runs.",
    )
    parser.add_argument(
        "--per-company-send-limit",
        type=int,
        default=15,
        help="Per-company cap while filling --target-sends.",
    )
    parser.add_argument("--send-limit", type=int, default=0)
    parser.add_argument("--send-min-score", type=int, default=20)
    parser.add_argument("--skip-linkedin-preflight", action="store_true")
    parser.add_argument("--company-prep-timeout", type=int, default=420)
    parser.add_argument("--send-timeout", type=int, default=420)
    parser.add_argument(
        "--run-id",
        default="",
        help="Stable identifier supplied by the nightly orchestrator; used for the exact run manifest filename.",
    )
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
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return path


def _build_source_breadth(jobspy_raw: Path, *, since_ts: float) -> Path | None:
    try:
        playwright_raw = latest("linkedin_live_raw_*.json", LOGS_DIR)
    except SystemExit as exc:
        print(
            f"[warn] Could not build source breadth without LinkedIn raw artifact: {exc}",
            file=sys.stderr,
        )
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
    return latest_since(
        "*source-breadth-filtered.json", SOURCE_VALIDATION_DIR, since_ts
    )


def _manifest_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned or datetime.now().strftime("%Y%m%d-%H%M%S")


def daily_engine_manifest_path(run_id: str) -> Path:
    return (
        SOURCE_VALIDATION_DIR
        / f"{_manifest_run_id(run_id)}-daily-engine-run-manifest.json"
    )


def startup_apply_run_artifact_path(run_id: str) -> Path:
    nonce = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return LOGS_DIR / f"startup_apply_run_{_manifest_run_id(run_id)}_{nonce}.json"


def handshake_run_artifact_path(run_id: str) -> Path:
    nonce = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return LOGS_DIR / f"handshake_import_{_manifest_run_id(run_id)}_{nonce}.json"


def startup_source_report_path(run_id: str) -> Path:
    nonce = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return (
        SOURCE_VALIDATION_DIR
        / f"{_manifest_run_id(run_id)}-{nonce}-startup-source-report.json"
    )


def _artifact_health_status(total_count: int, error_count: int) -> str:
    if total_count == 0 or error_count == 0:
        return "completed"
    if error_count >= total_count:
        return "failed"
    return "partial_failed"


def _validate_startup_apply_run_artifact(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"Exact startup run artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Exact startup run artifact is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Startup run artifact root must be an object")
    if payload.get("schema") != "resume_generator.startup_apply_run":
        raise ValueError(f"Unexpected startup run artifact schema: {payload.get('schema')!r}")
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported startup run artifact version: {payload.get('version')!r}")
    counts = payload.get("counts")
    candidates = payload.get("candidates")
    if not isinstance(counts, dict) or not isinstance(candidates, dict):
        raise ValueError("Startup run artifact is missing counts or candidates")
    selected = candidates.get("selected")
    scored = candidates.get("scored")
    if (
        not isinstance(selected, list)
        or not isinstance(scored, list)
        or any(not isinstance(item, dict) for item in [*selected, *scored])
    ):
        raise ValueError("Startup run artifact candidate lists are invalid")
    try:
        selected_count = int(counts.get("selected"))
        scored_count = int(counts.get("scored"))
        error_count = int(counts.get("error_count"))
        scoring_errors = int(counts.get("scoring_error_count"))
        processing_errors = int(counts.get("processing_error_count"))
        run_errors = int(counts.get("run_error_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Startup run artifact health counts are invalid") from exc
    if min(
        selected_count,
        scored_count,
        error_count,
        scoring_errors,
        processing_errors,
        run_errors,
    ) < 0:
        raise ValueError("Startup run artifact contains negative health counts")
    if selected_count != len(selected):
        raise ValueError(
            "Startup run artifact counts.selected does not match candidates.selected"
        )
    if scored_count != len(scored) or scored_count > selected_count:
        raise ValueError(
            "Startup run artifact counts.scored does not match candidates.scored"
        )
    actual_scoring_errors = sum(
        1
        for item in scored
        if isinstance(item, dict)
        and (
            str(item.get("decision") or "").strip().casefold() == "error"
            or str(item.get("status") or "").strip().casefold() == "error"
        )
    )
    if scoring_errors != actual_scoring_errors:
        raise ValueError("Startup run artifact scoring error count is inconsistent")
    if processing_errors != max(0, selected_count - scored_count):
        raise ValueError("Startup run artifact processing error count is inconsistent")
    if error_count != scoring_errors + processing_errors + run_errors:
        raise ValueError("Startup run artifact total error count is inconsistent")
    expected_status = (
        "failed"
        if run_errors
        else _artifact_health_status(selected_count, error_count)
    )
    if payload.get("status") != expected_status:
        raise ValueError(
            "Startup run artifact status does not match its scoring error counts"
        )
    return payload


def _validate_handshake_run_artifact(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"Exact Handshake run artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Exact Handshake run artifact is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Handshake run artifact root must be an object")
    if payload.get("schema") != "resume_generator.handshake_import_run":
        raise ValueError(f"Unexpected Handshake run artifact schema: {payload.get('schema')!r}")
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported Handshake run artifact version: {payload.get('version')!r}")
    counts = payload.get("counts")
    skipped = payload.get("skipped")
    fetch_failed_rows = payload.get("fetch_failed")
    scored_rows = payload.get("scored")
    if (
        not isinstance(counts, dict)
        or not isinstance(skipped, list)
        or not isinstance(fetch_failed_rows, list)
        or not isinstance(scored_rows, list)
        or any(
            not isinstance(item, dict)
            for item in [*skipped, *fetch_failed_rows, *scored_rows]
        )
    ):
        raise ValueError("Handshake run artifact contains invalid row lists")
    try:
        input_rows = int(counts.get("input_rows"))
        candidates = int(counts.get("deduped_candidates"))
        skipped_count = int(counts.get("skipped_duplicates"))
        error_count = int(counts.get("error_count"))
        fetch_ok = int(counts.get("fetch_ok"))
        fetch_failed_count = int(counts.get("fetch_failed"))
        fetch_errors = int(counts.get("fetch_error_count"))
        scored_count = int(counts.get("scored"))
        scoring_errors = int(counts.get("scoring_error_count"))
        processing_errors = int(counts.get("processing_error_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Handshake run artifact contains invalid counts") from exc
    if min(
        input_rows,
        candidates,
        skipped_count,
        error_count,
        fetch_ok,
        fetch_failed_count,
        fetch_errors,
        scored_count,
        scoring_errors,
        processing_errors,
    ) < 0:
        raise ValueError("Handshake run artifact contains negative counts")
    if skipped_count != len(skipped):
        raise ValueError(
            "Handshake skipped count does not match its run-scoped skipped rows"
        )
    if candidates + skipped_count > input_rows:
        raise ValueError("Handshake run artifact count ordering is impossible")
    if fetch_failed_count != fetch_errors:
        raise ValueError("Handshake fetch failure counts disagree")
    if fetch_ok + fetch_errors != candidates:
        raise ValueError("Handshake fetch counts do not match candidate count")
    if fetch_errors != len(fetch_failed_rows):
        raise ValueError("Handshake fetch error count does not match failed rows")
    if scored_count != len(scored_rows) or scored_count > fetch_ok:
        raise ValueError("Handshake scored count does not match scored rows")
    actual_scoring_errors = sum(
        1
        for item in scored_rows
        if str(item.get("decision") or "").strip().casefold() == "error"
        or str(item.get("status") or "").strip().casefold() == "error"
    )
    if scoring_errors != actual_scoring_errors:
        raise ValueError("Handshake scoring error count is inconsistent")
    if processing_errors != max(0, fetch_ok - scored_count):
        raise ValueError("Handshake processing error count is inconsistent")
    if error_count != fetch_errors + scoring_errors + processing_errors:
        raise ValueError("Handshake total error count is inconsistent")
    expected_status = _artifact_health_status(candidates, error_count)
    if payload.get("status") != expected_status:
        raise ValueError(
            "Handshake run artifact status does not match its processing error counts"
        )
    return payload


def _artifact_pointer_from_output(output: str, *, base_dir: Path) -> Path | None:
    for line in reversed((output or "").splitlines()):
        if not line.strip().startswith("Artifact:"):
            continue
        raw_path = line.split("Artifact:", 1)[1].strip()
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve(strict=False)
    return None


def _validate_relationship_discovery_artifact(
    path: Path,
    expected_source_id: str,
) -> tuple[dict[str, object], str]:
    if not path.is_file():
        raise ValueError(
            f"Exact relationship artifact is missing for {expected_source_id}: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Exact relationship artifact is invalid for {expected_source_id}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Relationship discovery artifact root must be an object")
    source = payload.get("source")
    actual_source_id = (
        str(source.get("source_id") or "").strip()
        if isinstance(source, dict)
        else ""
    )
    if actual_source_id != expected_source_id:
        raise ValueError(
            f"Relationship artifact source mismatch: expected {expected_source_id}, "
            f"found {actual_source_id or 'missing'}"
        )
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError(
            f"Relationship artifact results are invalid for {expected_source_id}"
        )
    try:
        kept_count = int(payload.get("count"))
        raw_count = int(payload.get("raw_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Relationship artifact counts are invalid for {expected_source_id}"
        ) from exc
    if kept_count != len(results) or kept_count < 0 or raw_count < kept_count:
        raise ValueError(
            f"Relationship artifact counts are inconsistent for {expected_source_id}"
        )
    status = str(payload.get("status") or "completed").strip().casefold()
    if status in {"ran", "success", "ok"}:
        status = "completed"
    return payload, status


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _readable_artifact_path(value: object, *, base_dir: Path) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    path = path.resolve(strict=False)
    return str(path) if path.is_file() else ""


def _artifact_path_list(value: object, *, base_dir: Path) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    paths: list[str] = []
    for item in values:
        path = _readable_artifact_path(item, base_dir=base_dir)
        if path and path not in paths:
            paths.append(path)
    return paths


def _reconcile_artifacts_from_drafts(draft_artifacts: list[str]) -> list[str]:
    paths: list[str] = []
    for raw_path in draft_artifacts:
        payload = _load_json(Path(raw_path))
        source = _readable_artifact_path(
            payload.get("source_artifact"),
            base_dir=OUTREACH_ROOT,
        )
        if source and source not in paths:
            paths.append(source)
    return paths


APP_INVITE_FAILED_STATUSES = {
    "prep_failed",
    "prep_artifact_missing",
    "send_failed",
    "send_artifact_missing",
}
APP_INVITE_UNRESOLVED_STATUSES = {
    "send_unknown_reserved",
    "partial_send_unknown_reserved",
}


def _app_invite_execution_status(outreach: dict[str, object]) -> str:
    rows = [
        row
        for row in list(outreach.get("company_runs") or [])
        if isinstance(row, dict)
    ]
    if not outreach:
        return "skipped"
    failed = [
        row
        for row in rows
        if str(row.get("status") or "").casefold() in APP_INVITE_FAILED_STATUSES
    ]
    unresolved = [
        row
        for row in rows
        if str(row.get("status") or "").casefold()
        in APP_INVITE_UNRESOLVED_STATUSES
    ]
    completed = [row for row in rows if row not in failed and row not in unresolved]
    if failed:
        return "partial_failed" if completed or unresolved else "failed"
    if unresolved:
        return (
            "partial_send_unknown_reserved"
            if completed
            else "send_unknown_reserved"
        )
    return "completed"


def _typed_manifest_pointers(manifest: dict[str, object]) -> dict[str, object]:
    artifacts = (
        manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    )
    outreach = (
        manifest.get("outreach_execution")
        if isinstance(manifest.get("outreach_execution"), dict)
        else {}
    )
    invite_send_artifacts = _artifact_path_list(
        outreach.get("invite_send_artifacts"),
        base_dir=OUTREACH_ROOT,
    )
    followup_drafts = _artifact_path_list(
        artifacts.get("linkedin_followup_drafts"),
        base_dir=OUTREACH_ROOT,
    )
    followup_sends = _artifact_path_list(
        artifacts.get("linkedin_followup_send_results"),
        base_dir=OUTREACH_ROOT,
    )
    reconcile_artifacts = _artifact_path_list(
        artifacts.get("linkedin_reconcile_artifacts"),
        base_dir=OUTREACH_ROOT,
    )
    startup_apply_run_artifact = _readable_artifact_path(
        artifacts.get("startup_apply_run"),
        base_dir=ROOT,
    )
    startup_source_report_artifact = _readable_artifact_path(
        artifacts.get("startup_report"),
        base_dir=ROOT,
    )
    handshake_run_artifact = _readable_artifact_path(
        artifacts.get("handshake_log"),
        base_dir=ROOT,
    )
    relationship_run = (
        artifacts.get("relationship_discovery")
        if isinstance(artifacts.get("relationship_discovery"), dict)
        else {}
    )
    relationship_paths = (
        relationship_run.get("artifacts")
        if isinstance(relationship_run.get("artifacts"), dict)
        else {}
    )
    relationship_discovery_artifacts = {
        str(source_id): path
        for source_id, raw_path in relationship_paths.items()
        if (
            path := _readable_artifact_path(raw_path, base_dir=OUTREACH_ROOT)
        )
    }
    for path in _reconcile_artifacts_from_drafts(followup_drafts):
        if path not in reconcile_artifacts:
            reconcile_artifacts.append(path)
    return {
        "manifest_schema": "resume_generator.daily_engine_run_manifest",
        "manifest_version": 1,
        "invite_send_artifacts": invite_send_artifacts,
        "linkedin_followup_draft_artifacts": followup_drafts,
        "linkedin_followup_send_artifacts": followup_sends,
        "linkedin_reconcile_artifacts": reconcile_artifacts,
        "startup_apply_run_artifact": startup_apply_run_artifact,
        "startup_source_report_artifact": startup_source_report_artifact,
        "handshake_run_artifact": handshake_run_artifact,
        "relationship_discovery_artifacts": relationship_discovery_artifacts,
        "source_metrics": str(manifest.get("source_metrics") or ""),
        "action_queue": str(manifest.get("action_queue") or ""),
        "app_invites": {
            "status": _app_invite_execution_status(outreach),
            "target": int(outreach.get("target_sends") or 0),
            "sent": int(outreach.get("sent_total") or 0),
            "companies_attempted": int(outreach.get("companies_attempted") or 0),
            "company_runs": list(outreach.get("company_runs") or []),
            "failed_companies": list(outreach.get("failed_companies") or []),
            "skipped_companies": list(outreach.get("skipped_companies") or []),
            "unresolved_companies": list(
                outreach.get("unresolved_companies") or []
            ),
        },
        "track_2_daily_run_artifacts": list(
            manifest.get("track_2_daily_run_artifacts") or []
        ),
        "track_2_phase_artifacts": list(manifest.get("track_2_phase_artifacts") or []),
        "track_2_phase_results": list(manifest.get("track_2_phase_results") or []),
        "track_2_email_draft_artifacts": list(
            manifest.get("track_2_email_draft_artifacts") or []
        ),
        "track_2_email_send_artifacts": list(
            manifest.get("track_2_email_send_artifacts") or []
        ),
        "email_channel": (
            manifest.get("email_channel")
            if isinstance(manifest.get("email_channel"), dict)
            else {
                "status": "skipped_track_2_not_run",
                "smtp_configured": False,
                "blockers": [
                    "Track 2 has not run yet; nightly email delivery also requires explicit human approval and SMTP configuration."
                ],
                "draft_artifacts": [],
                "send_artifacts": [],
                "draft_count": 0,
                "sent_count": 0,
                "approval_required": True,
            }
        ),
    }


def _manifest_count(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _source_families_for_manifest(manifest: dict[str, object]) -> dict[str, object]:
    source_metrics = _load_json(Path(str(manifest.get("source_metrics") or "")))
    sources = (
        source_metrics.get("sources")
        if isinstance(source_metrics.get("sources"), dict)
        else {}
    )
    stages = (
        manifest.get("stage_metrics")
        if isinstance(manifest.get("stage_metrics"), dict)
        else {}
    )

    def source_row(key: str) -> dict[str, object]:
        row = sources.get(key) if isinstance(sources.get(key), dict) else {}
        stage = stages.get(key) if isinstance(stages.get(key), dict) else {}
        return {
            "status": str(row.get("status") or stage.get("status") or "skipped"),
            "raw_count": _manifest_count(row.get("raw_count")),
            "kept_count": _manifest_count(row.get("accepted_for_write")),
            "details": row.get("details")
            if isinstance(row.get("details"), dict)
            else {},
        }

    startup_apply = source_row("startup_apply")
    startup_relationship = (
        sources.get("startup_relationship")
        if isinstance(sources.get("startup_relationship"), dict)
        else {}
    )
    relationship_stage = (
        stages.get("relationship_discovery")
        if isinstance(stages.get("relationship_discovery"), dict)
        else {}
    )
    startup_report_stage = (
        stages.get("startup_source_report")
        if isinstance(stages.get("startup_source_report"), dict)
        else {}
    )
    relationship_count = _manifest_count(
        startup_relationship.get("relationship_targets")
    )
    startup_lane_statuses = [
        str(startup_apply.get("status") or "skipped").casefold(),
        str(
            startup_relationship.get("status")
            or relationship_stage.get("status")
            or "skipped"
        ).casefold(),
    ]
    helper_status = str(
        startup_report_stage.get("status") or "skipped"
    ).casefold()

    def non_green(status: str) -> bool:
        return (
            "fail" in status
            or "timeout" in status
            or status in {"incomplete", "timed_out"}
        )

    lane_has_activity = any(
        status in {"ran", "completed", "partial"}
        for status in startup_lane_statuses
    )
    if any(non_green(status) for status in [*startup_lane_statuses, helper_status]):
        startup_status = "partial_failed" if lane_has_activity else "failed"
    elif all(status == "skipped" for status in startup_lane_statuses):
        # The helper report is bookkeeping; a successful helper cannot manufacture
        # source activity when both underlying startup lanes were intentionally skipped.
        startup_status = "skipped"
    elif all(status in {"ran", "completed"} for status in startup_lane_statuses):
        startup_status = "ran"
    else:
        startup_status = "partial"

    action_queue_path = Path(str(manifest.get("action_queue") or ""))
    action_queue = _load_json(action_queue_path)
    action_counts = (
        action_queue.get("counts")
        if isinstance(action_queue.get("counts"), dict)
        else {}
    )
    action_total = sum(_manifest_count(value) for value in action_counts.values())
    action_queue_stage = (
        stages.get("action_queue")
        if isinstance(stages.get("action_queue"), dict)
        else {}
    )
    outreach = (
        manifest.get("outreach_execution")
        if isinstance(manifest.get("outreach_execution"), dict)
        else {}
    )
    app_invite_status = _app_invite_execution_status(outreach)
    if action_queue_path.is_file():
        if app_invite_status in {"failed", "partial_failed"}:
            app_queue_status = "partial_failed"
        elif app_invite_status in APP_INVITE_UNRESOLVED_STATUSES:
            app_queue_status = "incomplete"
        else:
            app_queue_status = "ran"
    else:
        app_queue_status = str(action_queue_stage.get("status") or "skipped")
    return {
        "linkedin": source_row("linkedin"),
        "handshake": source_row("handshake"),
        "jobspy": source_row("jobspy"),
        "startup_sources": {
            "status": startup_status,
            "raw_count": _manifest_count(startup_apply.get("raw_count"))
            + relationship_count,
            "kept_count": _manifest_count(startup_apply.get("kept_count"))
            + relationship_count,
            "details": {
                "startup_apply": startup_apply,
                "startup_relationship": {
                    "status": str(
                        startup_relationship.get("status")
                        or relationship_stage.get("status")
                        or "skipped"
                    ),
                    "relationship_targets": relationship_count,
                    "source_counts": startup_relationship.get("source_counts") or {},
                    "error_count": _manifest_count(
                        startup_relationship.get("error_count")
                    ),
                    "artifacts": startup_relationship.get("artifacts") or {},
                },
            },
        },
        "resume_generator_app_queue": {
            "status": app_queue_status,
            "raw_count": action_total,
            "kept_count": _manifest_count(outreach.get("sent_total")),
            "details": {
                "action_queue_counts": action_counts,
                "app_invite_status": app_invite_status,
                "invite_target": _manifest_count(outreach.get("target_sends")),
                "invite_sent": _manifest_count(outreach.get("sent_total")),
                "companies_attempted": _manifest_count(
                    outreach.get("companies_attempted")
                ),
                "failed_companies": list(outreach.get("failed_companies") or []),
                "skipped_companies": list(outreach.get("skipped_companies") or []),
                "unresolved_companies": list(
                    outreach.get("unresolved_companies") or []
                ),
            },
        },
        "track_2": {
            "status": "skipped",
            "raw_count": 0,
            "kept_count": 0,
            "details": {
                "reason": "Track 2 runs in the nightly stage after the daily engine."
            },
        },
    }


def write_daily_engine_manifest(manifest: dict[str, object]) -> Path:
    manifest.update(_typed_manifest_pointers(manifest))
    if not isinstance(manifest.get("source_families"), dict):
        manifest["source_families"] = _source_families_for_manifest(manifest)
    path = daily_engine_manifest_path(str(manifest.get("run_id") or ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(manifest), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


def _run_daily_engine(args: argparse.Namespace, run_manifest: dict[str, object]) -> int:
    run_started_at = str(run_manifest["run_started_at"])
    stage_metrics: dict[str, dict] = {}
    artifacts: dict[str, object] = {}
    run_manifest["stage_metrics"] = stage_metrics
    run_manifest["artifacts"] = artifacts
    run_manifest["outreach_execution"] = {}
    direct_followup_failed = False
    if args.execute_sends and args.parallel_generation_outreach:
        raise SystemExit(
            "--execute-sends is intentionally not supported with --parallel-generation-outreach."
        )
    if args.execute_linkedin_followups and not args.prepare_outreach:
        raise SystemExit(
            "--execute-linkedin-followups requires --prepare-outreach so the "
            "standalone inbox lane cannot be silently skipped."
        )
    hours_old = window_to_hours(args.window)

    run_manifest["applied_pdf_sync"] = applied_pdf_status_report()

    needs_linkedin = (not args.skip_linkedin) or bool(args.prepare_outreach)
    if needs_linkedin and not args.skip_linkedin_preflight:
        if not ensure_linkedin_chrome_session("initial preflight failure"):
            raise SystemExit("LinkedIn Chrome preflight failed after one guarded reset.")

    if not args.skip_linkedin:
        stage_started = _start_stage(stage_metrics, "linkedin")
        artifact_since = time.time()
        result = run_capture(
            ["./discovery/scripts/run_linkedin_discovery.sh", args.window],
            check=False,
            timeout=args.linkedin_discovery_timeout,
        )
        if result.returncode == 0:
            scored_artifact = latest_since(
                "linkedin_live_scored_*.json", LOGS_DIR, artifact_since
            )
            artifacts["linkedin_scored"] = scored_artifact
            _finish_stage(
                stage_metrics,
                "linkedin",
                stage_started,
                status=_linkedin_scoring_stage_status(scored_artifact),
                returncode=result.returncode,
            )
        else:
            status = "timed_out" if result.returncode == 124 else "failed"
            _finish_stage(stage_metrics, "linkedin", stage_started, status=status, returncode=result.returncode)
            artifacts["linkedin_scored"] = score_partial_linkedin_raw(artifact_since)
            artifacts["linkedin_chrome_reset_after_failure"] = reset_linkedin_chrome_session(status)
    else:
        _skip_stage(stage_metrics, "linkedin")

    if not args.skip_handshake:
        stage_started = _start_stage(stage_metrics, "handshake")
        handshake_artifact = handshake_run_artifact_path(args.run_id)
        artifacts["handshake_log"] = handshake_artifact
        handshake_result = run(
            [
                "./discovery/scripts/run_handshake_discovery.sh",
                args.window,
                handshake_artifact,
            ],
            check=False,
        )
        if handshake_result.returncode != 0:
            _finish_stage(
                stage_metrics,
                "handshake",
                stage_started,
                status="failed",
                returncode=handshake_result.returncode,
            )
            raise SystemExit(
                f"Handshake discovery exited with {handshake_result.returncode}; "
                f"exact artifact: {handshake_artifact}"
            )
        try:
            handshake_payload = _validate_handshake_run_artifact(handshake_artifact)
        except ValueError as exc:
            _finish_stage(
                stage_metrics,
                "handshake",
                stage_started,
                status="failed",
                returncode=2,
            )
            raise SystemExit(str(exc)) from exc
        handshake_status = str(handshake_payload.get("status") or "failed")
        _finish_stage(
            stage_metrics,
            "handshake",
            stage_started,
            status="ran" if handshake_status == "completed" else handshake_status,
        )
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
        fetch_cmd: list[object] = [
            PYTHON,
            "discovery/scripts/fetch_jobspy_breadth.py",
            "--hours-old",
            hours_old,
        ]
        if jobspy_results:
            fetch_cmd.extend(["--results", jobspy_results])
        for query_index in jobspy_query_indices:
            fetch_cmd.extend(["--query-index", query_index])
        jobspy_fetch = run_capture(fetch_cmd, check=False, timeout=jobspy_timeout)
        if jobspy_fetch.returncode != 0:
            print(
                f"[warn] Skipping JobSpy validation/scoring because fetch exited with {jobspy_fetch.returncode}.",
                file=sys.stderr,
            )
            fallback_raw = _write_empty_jobspy_raw(
                hours_old,
                "timeout" if jobspy_fetch.returncode == 124 else "fetch_failed",
            )
            artifacts["jobspy_raw"] = fallback_raw
            artifacts["source_breadth"] = _build_source_breadth(
                fallback_raw, since_ts=artifact_since
            )
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
            artifacts["jobspy_scored"] = latest_since(
                "jobspy_filtered_scored_*.json", LOGS_DIR, artifact_since
            )
            _finish_stage(stage_metrics, "jobspy", stage_started)
    else:
        _skip_stage(stage_metrics, "jobspy")
        artifact_since = time.time()
        fallback_raw = _write_empty_jobspy_raw(hours_old, "skip_jobspy")
        artifacts["jobspy_raw"] = fallback_raw
        artifacts["source_breadth"] = _build_source_breadth(
            fallback_raw, since_ts=artifact_since
        )

    if not args.skip_startup_apply:
        stage_started = _start_stage(stage_metrics, "startup_apply")
        startup_apply_artifact = startup_apply_run_artifact_path(args.run_id)
        artifacts["startup_apply_run"] = startup_apply_artifact
        startup_result = run(
            [
                PYTHON,
                "discovery/auto/startup_apply_pipeline.py",
                "--limit-companies",
                args.startup_limit_companies,
                "--limit-jobs",
                args.startup_limit_jobs,
                "--run-artifact",
                startup_apply_artifact,
            ],
            check=False,
        )
        if startup_result.returncode != 0:
            _finish_stage(
                stage_metrics,
                "startup_apply",
                stage_started,
                status="failed",
                returncode=startup_result.returncode,
            )
            raise SystemExit(
                f"Startup apply exited with {startup_result.returncode}; exact artifact: "
                f"{startup_apply_artifact}"
            )
        try:
            startup_apply_payload = _validate_startup_apply_run_artifact(
                startup_apply_artifact
            )
        except ValueError as exc:
            _finish_stage(
                stage_metrics,
                "startup_apply",
                stage_started,
                status="failed",
                returncode=2,
            )
            raise SystemExit(str(exc)) from exc
        startup_outputs = startup_apply_payload.get("outputs")
        run_log = str(
            startup_outputs.get("run_log")
            if isinstance(startup_outputs, dict)
            else ""
        )
        if run_log and Path(run_log).is_file():
            artifacts["startup_apply_log"] = Path(run_log)
        startup_apply_status = str(
            startup_apply_payload.get("status") or "failed"
        )
        _finish_stage(
            stage_metrics,
            "startup_apply",
            stage_started,
            status=(
                "ran" if startup_apply_status == "completed" else startup_apply_status
            ),
        )
    else:
        _skip_stage(stage_metrics, "startup_apply")

    relationship_artifact_paths: dict[str, Path] = {}
    relationship_artifact_statuses: dict[str, str] = {}
    if not args.skip_relationship_discovery:
        stage_started = _start_stage(stage_metrics, "relationship_discovery")
        for source_id in RELATIONSHIP_SOURCES:
            result = run_capture(
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
                check=False,
            )
            output = "\n".join(
                part for part in [result.stdout, result.stderr] if part
            )
            pointer = _artifact_pointer_from_output(
                output,
                base_dir=OUTREACH_ROOT,
            )
            if pointer is None:
                relationship_artifact_statuses[source_id] = "failed"
                print(
                    f"[warn] No exact Artifact pointer returned for {source_id}.",
                    file=sys.stderr,
                )
                continue
            try:
                _, artifact_health = _validate_relationship_discovery_artifact(
                    pointer,
                    source_id,
                )
            except ValueError as exc:
                relationship_artifact_statuses[source_id] = "failed"
                print(f"[warn] {exc}", file=sys.stderr)
                continue
            relationship_artifact_paths[source_id] = pointer
            if result.returncode != 0:
                relationship_artifact_statuses[source_id] = "failed"
            else:
                relationship_artifact_statuses[source_id] = artifact_health

        green_relationship_sources = sum(
            status == "completed"
            for status in relationship_artifact_statuses.values()
        )
        relationship_errors = len(RELATIONSHIP_SOURCES) - green_relationship_sources
        if relationship_errors == 0:
            relationship_stage_status = "ran"
        elif green_relationship_sources:
            relationship_stage_status = "partial_failed"
        else:
            relationship_stage_status = "failed"
        artifacts["relationship_discovery"] = {
            "artifacts": relationship_artifact_paths,
            "statuses": relationship_artifact_statuses,
        }
        _finish_stage(
            stage_metrics,
            "relationship_discovery",
            stage_started,
            status=relationship_stage_status,
            returncode=0 if relationship_errors == 0 else 1,
        )
    else:
        _skip_stage(stage_metrics, "relationship_discovery")

    stage_started = _start_stage(stage_metrics, "startup_source_report")
    startup_report_cmd: list[object] = [
        PYTHON,
        "discovery/scripts/build_startup_source_report.py",
        "--limit-companies",
        args.startup_limit_companies,
        "--limit-jobs",
        args.startup_limit_jobs,
    ]
    if args.skip_startup_apply:
        startup_report_cmd.append("--no-startup-apply")
    else:
        startup_apply_artifact = artifacts.get("startup_apply_run")
        if not isinstance(startup_apply_artifact, Path):
            _finish_stage(
                stage_metrics,
                "startup_source_report",
                stage_started,
                status="failed",
                returncode=2,
            )
            raise SystemExit("Startup source report has no exact startup run pointer.")
        startup_report_cmd.extend(
            ["--startup-run-artifact", startup_apply_artifact]
        )
    if args.skip_relationship_discovery:
        startup_report_cmd.append("--no-relationship-artifacts")
    else:
        startup_report_cmd.append("--exact-relationship-artifacts")
        for source_id in RELATIONSHIP_SOURCES:
            startup_report_cmd.extend(
                ["--required-relationship-source", source_id]
            )
            startup_report_cmd.extend(
                [
                    "--relationship-artifact-status",
                    f"{source_id}={relationship_artifact_statuses.get(source_id, 'failed')}",
                ]
            )
            exact_artifact = relationship_artifact_paths.get(source_id)
            if exact_artifact is not None:
                startup_report_cmd.extend(
                    [
                        "--relationship-artifact",
                        f"{source_id}={exact_artifact}",
                    ]
                )
    startup_report_artifact = startup_source_report_path(args.run_id)
    artifacts["startup_report"] = startup_report_artifact
    startup_report_cmd.extend(["--output-json", startup_report_artifact])
    report_result = run(startup_report_cmd, check=False)
    if report_result.returncode != 0 or not startup_report_artifact.is_file():
        _finish_stage(
            stage_metrics,
            "startup_source_report",
            stage_started,
            status="failed",
            returncode=report_result.returncode or 2,
        )
        raise SystemExit(
            "Startup source report failed closed for exact startup run artifact "
            f"{artifacts.get('startup_apply_run')}."
        )
    _finish_stage(stage_metrics, "startup_source_report", stage_started)

    stage_started = _start_stage(stage_metrics, "action_queue")
    action_queue_path = build_action_queue(args)
    run_manifest["action_queue"] = str(action_queue_path)
    _finish_stage(stage_metrics, "action_queue", stage_started)
    print(f"\nFinal action queue: {action_queue_path}")
    print(f"Final action report: {action_queue_path.with_suffix('.html')}")

    if args.prepare_outreach and not args.skip_linkedin_followups:
        stage_started = _start_stage(stage_metrics, "linkedin_followups")
        pull_result = run_linkedin_followup_pull(args)
        artifacts["linkedin_followup_pull"] = pull_result.as_dict()
        followup_artifact = pull_result.artifact
        artifacts["linkedin_followup_drafts"] = followup_artifact
        _finish_stage(
            stage_metrics,
            "linkedin_followups",
            stage_started,
            status="ran" if pull_result.status == "completed" else pull_result.status,
            returncode=pull_result.returncode,
        )
        direct_followup_failed = pull_result.status != "completed"
        if args.execute_linkedin_followups and followup_artifact:
            stage_started = _start_stage(stage_metrics, "linkedin_followup_sends")
            chrome_ready = ensure_linkedin_chrome_session(
                "before LinkedIn follow-up sends"
            )
            send_result = (
                run_linkedin_followup_send(args, followup_artifact)
                if chrome_ready
                else ArtifactCommandResult("failed_chrome_unavailable", 1)
            )
            artifacts["linkedin_followup_send"] = send_result.as_dict()
            followup_send_artifact = send_result.artifact
            artifacts["linkedin_followup_send_results"] = followup_send_artifact
            _finish_stage(
                stage_metrics,
                "linkedin_followup_sends",
                stage_started,
                status=(
                    "ran" if send_result.status == "completed" else send_result.status
                ),
                returncode=send_result.returncode,
            )
            direct_followup_failed = (
                direct_followup_failed or send_result.status != "completed"
            )
        else:
            _skip_stage(stage_metrics, "linkedin_followup_sends")
    else:
        _skip_stage(stage_metrics, "linkedin_followups")
        _skip_stage(stage_metrics, "linkedin_followup_sends")

    source_metrics_path = write_source_run_metrics(
        args=args,
        run_started_at=run_started_at,
        stage_metrics=stage_metrics,
        artifacts=artifacts,
        action_queue_path=action_queue_path,
    )
    artifacts["source_metrics"] = source_metrics_path
    run_manifest["source_metrics"] = str(source_metrics_path)
    print(f"Final source metrics: {source_metrics_path}")

    generation_proc: subprocess.Popen | None = None
    if (
        args.run_generation
        and args.prepare_outreach
        and args.parallel_generation_outreach
    ):
        if not ensure_linkedin_chrome_session("before parallel outreach"):
            raise SystemExit("LinkedIn Chrome unavailable before parallel outreach.")
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
        targets = selected_outreach_targets(
            action_queue_path,
            app_limit=max(args.app_outreach_limit, 0),
            relationship_limit=max(args.relationship_outreach_limit, 0),
        )
        companies = [target["company"] for target in targets]
        print(
            f"\nOutreach companies selected from {action_queue_path.name}: {companies}"
        )
        failures: list[str] = []
        for target in targets:
            company = target["company"]
            cmd: list[object] = [
                OUTREACH_PYTHON,
                "main.py",
                "run",
                "--company",
                company,
                "--company-mode",
                "startup",
            ]
            if target["target_role_title"]:
                cmd.extend(["--target-role-title", target["target_role_title"]])
            result = run(
                cmd,
                cwd=OUTREACH_ROOT,
                check=False,
            )
            if result.returncode != 0:
                failures.append(company)
                print(
                    f"[warn] Outreach artifact generation failed for {company}; continuing."
                )
        if failures:
            print(f"[warn] Outreach failures: {failures}")
    else:
        if args.run_generation:
            run(
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
        if args.prepare_outreach:
            if not ensure_linkedin_chrome_session("before outreach"):
                raise SystemExit("LinkedIn Chrome unavailable before outreach.")
            run_manifest["outreach_execution"] = run_outreach_from_action_queue(
                args,
                action_queue_path,
            )

    if generation_proc is not None:
        return_code = generation_proc.wait()
        if return_code != 0:
            raise SystemExit(return_code)
    return 1 if direct_followup_failed else 0


def _exception_returncode(exc: BaseException) -> int:
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, SystemExit):
        return exc.code if isinstance(exc.code, int) and exc.code != 0 else 1
    if isinstance(exc, subprocess.CalledProcessError):
        return int(exc.returncode or 1)
    return 1


def main() -> int:
    args = parse_args()
    run_id = _manifest_run_id(args.run_id)
    run_manifest: dict[str, object] = {
        "manifest_version": 1,
        "run_id": run_id,
        "run_started_at": datetime.now().isoformat(timespec="seconds"),
        "status": "running",
        "argv": vars(args),
        "stage_metrics": {},
        "artifacts": {},
        "outreach_execution": {},
        "source_metrics": "",
        "action_queue": "",
    }
    returncode = 1
    try:
        returncode = _run_daily_engine(args, run_manifest)
        run_manifest["status"] = "completed" if returncode == 0 else "failed"
    except BaseException as exc:
        returncode = _exception_returncode(exc)
        run_manifest["status"] = "failed"
        run_manifest["failure"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "returncode": returncode,
        }
        print(
            f"[error] Daily engine failed: {type(exc).__name__}: {exc}", file=sys.stderr
        )
    finally:
        for stage in (run_manifest.get("stage_metrics") or {}).values():
            if isinstance(stage, dict) and stage.get("status") == "running":
                stage["status"] = "failed_interrupted"
        run_manifest["completed_at"] = datetime.now().isoformat(timespec="seconds")
        run_manifest["returncode"] = returncode
        manifest_path = write_daily_engine_manifest(run_manifest)
        print(f"Run manifest: {manifest_path}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
