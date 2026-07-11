#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "venv" / "bin" / "python"
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"
CURRENT_SHORTLIST_JSON = (
    ROOT / "apps" / "Apply queues" / "current_apply_queue" / "generation_shortlist.json"
)
OUTREACH_ROOT = ROOT.parent / "Outreach"
OUTREACH_PYTHON = OUTREACH_ROOT / ".venv" / "bin" / "python"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "ResumeGenerator"
LOCK_PATH = APP_SUPPORT / "nightly_pipeline.lock"

APP_QUEUE_SEND_TARGET_BY_CYCLE = {
    "offcycle_light": "5",
    "normal": "25",
}
TRACK_2_INVITE_TARGET_BY_CYCLE = {
    "offcycle_light": "25",
    "normal": "25",
}
TRACK_2_FOLLOWUP_TARGET_BY_CYCLE = {
    "offcycle_light": "25",
    "normal": "25",
}
TRACK_2_MAPPING_TARGET_BY_CYCLE = {
    "offcycle_light": "15",
    "normal": "15",
}
TRACK_2_EMAIL_RESEARCH_TARGET_BY_CYCLE = {
    "offcycle_light": "10",
    "normal": "10",
}
TRACK_2_EMAIL_DRAFT_TARGET_BY_CYCLE = {
    "offcycle_light": "5",
    "normal": "5",
}
TRACK_2_TOTAL_ACTIONS_BY_CYCLE = {
    "offcycle_light": "80",
    "normal": "80",
}
TRACK_2_COMPANIES_BY_CYCLE = {
    "offcycle_light": "55",
    "normal": "55",
}


def _cmd_text(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(cmd: list[object], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n$ {_cmd_text(cmd)}", flush=True)
    return subprocess.run([str(part) for part in cmd], cwd=ROOT, check=check)


def latest(pattern: str) -> Path | None:
    matches = sorted(
        SOURCE_VALIDATION_DIR.glob(pattern), key=lambda path: path.stat().st_mtime
    )
    return matches[-1] if matches else None


def latest_since(pattern: str, started_at_epoch: float) -> Path | None:
    """Return only an artifact written by this pipeline invocation."""
    candidate = latest(pattern)
    if candidate is None or candidate.stat().st_mtime < started_at_epoch:
        return None
    return candidate


@contextmanager
def _pipeline_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"Nightly pipeline already running; lock held at {path}", flush=True)
            raise SystemExit(75)
        yield


def _daily_engine_cmd(args: argparse.Namespace, *, run_id: str = "") -> list[object]:
    cmd: list[object] = [
        PYTHON,
        "discovery/scripts/run_daily_engine.py",
        "--window",
        args.window,
    ]
    if run_id:
        cmd.extend(["--run-id", run_id])
    # Scheduled nightly execution has one canonical inbox/follow-up owner:
    # Track 2. The direct daily-engine lane remains available when that script
    # is run standalone, but must not rescan or resend inside this wrapper.
    cmd.append("--skip-linkedin-followups")
    for flag_name, cli_flag in (
        ("skip_linkedin", "--skip-linkedin"),
        ("skip_handshake", "--skip-handshake"),
        ("skip_jobspy", "--skip-jobspy"),
        ("skip_startup_apply", "--skip-startup-apply"),
        ("skip_relationship_discovery", "--skip-relationship-discovery"),
        ("skip_linkedin_preflight", "--skip-linkedin-preflight"),
    ):
        if getattr(args, flag_name):
            cmd.append(cli_flag)
    cmd.extend(["--relationship-today", args.relationship_today])
    cmd.extend(["--startup-limit-companies", args.startup_limit_companies])
    cmd.extend(["--startup-limit-jobs", args.startup_limit_jobs])
    cmd.extend(["--jobspy-fetch-timeout", args.jobspy_fetch_timeout])
    cmd.extend(["--jobspy-results", args.jobspy_results])
    cmd.extend(["--linkedin-discovery-timeout", args.linkedin_discovery_timeout])
    for query_index in args.jobspy_query_index:
        cmd.extend(["--jobspy-query-index", query_index])
    if args.prepare_outreach:
        cmd.append("--prepare-outreach")
    if args.execute_sends:
        cmd.append("--execute-sends")
        cmd.extend(["--target-sends", _app_queue_target_sends(args)])
        cmd.extend(["--per-company-send-limit", args.per_company_send_limit])
        cmd.extend(["--send-min-score", args.send_min_score])
    return cmd


def _clear_generated_queue_cmd() -> list[object]:
    return [PYTHON, "discovery/scripts/archive_current_generated_queue.py"]


def _sync_applied_pdfs_cmd() -> list[object]:
    return [PYTHON, "discovery/scripts/sync_applied_pdfs.py"]


def _shortlist_cmd(args: argparse.Namespace) -> list[object]:
    return [
        PYTHON,
        "discovery/scripts/build_generation_shortlist.py",
        "--cap",
        args.generation_cap,
        "--non-handshake-min",
        args.non_handshake_generation_min,
        "--handshake-internal-min",
        args.handshake_internal_generation_min,
        "--handshake-external-min",
        args.handshake_external_generation_min,
        "--handshake-unknown-min",
        args.handshake_unknown_generation_min,
    ]


def _generate_cmd(args: argparse.Namespace, shortlist_path: Path) -> list[object]:
    cmd: list[object] = [
        PYTHON,
        "jobs.py",
        "--no-color",
        "generate",
        "--queue",
        "--queue-path",
        shortlist_path,
        "--limit",
        args.generation_cap,
        "--parallel",
        args.resume_parallel,
        "--resume-only",
        "--budget-mode",
    ]
    if args.generation_dry_run:
        cmd.append("--dry-run")
    return cmd


def _outreach_cmd(*parts: object) -> list[object]:
    return [OUTREACH_PYTHON, "main.py", *parts]


def _app_queue_target_sends(args: argparse.Namespace) -> str:
    if args.target_sends != "auto":
        return args.target_sends
    return APP_QUEUE_SEND_TARGET_BY_CYCLE.get(
        args.cycle_config, APP_QUEUE_SEND_TARGET_BY_CYCLE["offcycle_light"]
    )


def _track_2_invite_target(args: argparse.Namespace) -> str:
    if args.track_2_linkedin_invites != "auto":
        return args.track_2_linkedin_invites
    return TRACK_2_INVITE_TARGET_BY_CYCLE.get(
        args.cycle_config, TRACK_2_INVITE_TARGET_BY_CYCLE["offcycle_light"]
    )


def _track_2_followup_target(args: argparse.Namespace) -> str:
    if args.track_2_linkedin_followups != "auto":
        return args.track_2_linkedin_followups
    return TRACK_2_FOLLOWUP_TARGET_BY_CYCLE.get(
        args.cycle_config, TRACK_2_FOLLOWUP_TARGET_BY_CYCLE["offcycle_light"]
    )


def _track_2_mapping_target(args: argparse.Namespace) -> str:
    if args.track_2_company_mapping != "auto":
        return args.track_2_company_mapping
    return TRACK_2_MAPPING_TARGET_BY_CYCLE.get(
        args.cycle_config, TRACK_2_MAPPING_TARGET_BY_CYCLE["offcycle_light"]
    )


def _track_2_email_research_target(args: argparse.Namespace) -> str:
    if args.track_2_email_research != "auto":
        return args.track_2_email_research
    return TRACK_2_EMAIL_RESEARCH_TARGET_BY_CYCLE.get(
        args.cycle_config,
        TRACK_2_EMAIL_RESEARCH_TARGET_BY_CYCLE["offcycle_light"],
    )


def _track_2_email_draft_target(args: argparse.Namespace) -> str:
    if args.track_2_email_drafts != "auto":
        return args.track_2_email_drafts
    return TRACK_2_EMAIL_DRAFT_TARGET_BY_CYCLE.get(
        args.cycle_config,
        TRACK_2_EMAIL_DRAFT_TARGET_BY_CYCLE["offcycle_light"],
    )


def _track_2_total_actions(args: argparse.Namespace) -> str:
    if args.track_2_total_actions != "auto":
        return args.track_2_total_actions
    return TRACK_2_TOTAL_ACTIONS_BY_CYCLE.get(
        args.cycle_config, TRACK_2_TOTAL_ACTIONS_BY_CYCLE["offcycle_light"]
    )


def _track_2_companies(args: argparse.Namespace) -> str:
    if args.track_2_companies != "auto":
        return args.track_2_companies
    return TRACK_2_COMPANIES_BY_CYCLE.get(
        args.cycle_config, TRACK_2_COMPANIES_BY_CYCLE["offcycle_light"]
    )


def _signal_process_group(process: subprocess.Popen, sig: signal.Signals) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return
    except (AttributeError, PermissionError):
        if sig == signal.SIGKILL:
            process.kill()
        else:
            process.terminate()


def _terminate_process_group(
    process: subprocess.Popen,
    *,
    grace_seconds: float = 10,
) -> tuple[str, str]:
    _signal_process_group(process, signal.SIGTERM)
    try:
        return process.communicate(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _signal_process_group(process, signal.SIGKILL)
        return process.communicate()


def _run_capture_print(
    cmd: list[object],
    *,
    cwd: Path,
    timeout_seconds: int | float | None = None,
) -> subprocess.CompletedProcess:
    print(f"\n$ {_cmd_text(cmd)}", flush=True)
    normalized = [str(part) for part in cmd]
    process = subprocess.Popen(
        normalized,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timeout = timeout_seconds if timeout_seconds and timeout_seconds > 0 else None
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        returncode = int(process.returncode or 0)
    except subprocess.TimeoutExpired:
        timed_out = True
        print(
            f"[warn] Command timed out after {timeout_seconds}s; terminating process group: {_cmd_text(cmd)}",
            file=sys.stderr,
            flush=True,
        )
        stdout, stderr = _terminate_process_group(process)
        returncode = 124
    result = subprocess.CompletedProcess(normalized, returncode, stdout, stderr)
    setattr(result, "timed_out", timed_out)
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    return result


def _artifact_from_output(output: str) -> str:
    lines = output.splitlines()
    # Track 2 emits many nested `Artifact:` lines before the authoritative
    # top-level `Run artifact:` pointer. Prefer the exact run pointer first.
    for label in ("Run artifact", "Artifact", "Output"):
        prefix = f"{label}:"
        for line in lines:
            if line.strip().startswith(prefix):
                return line.strip().split(prefix, 1)[1].strip()
    return ""


def _run_id(created_at: str) -> str:
    parsed = datetime.fromisoformat(created_at)
    return parsed.strftime("%Y%m%d-%H%M%S")


def daily_engine_manifest_path(run_id: str) -> Path:
    return SOURCE_VALIDATION_DIR / f"{run_id}-daily-engine-run-manifest.json"


def _resolve_outreach_artifact(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = OUTREACH_ROOT / path
    return path.resolve(strict=False)


def _labeled_path_from_output(output: str, label: str) -> str:
    prefix = f"{label}:"
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _run_shared_discovery_queue(action_queue: Path) -> dict[str, object]:
    """Build the cross-repo queue from one exact current-run action artifact."""

    result = _run_capture_print(
        [
            OUTREACH_PYTHON,
            "-m",
            "outreach.shared_discovery",
            "--action-queue",
            action_queue,
            "--workspace",
            "workspace",
            "--output-dir",
            "workspace/shared_discovery",
            "--limit",
            "50",
        ],
        cwd=OUTREACH_ROOT,
    )
    json_path = _resolve_outreach_artifact(
        _labeled_path_from_output(result.stdout, "JSON")
    )
    csv_path = _resolve_outreach_artifact(
        _labeled_path_from_output(result.stdout, "CSV")
    )
    if result.returncode != 0:
        status = "failed_command"
    elif json_path is None or csv_path is None:
        status = "failed_missing_artifact_paths"
    elif not json_path.is_file() or not csv_path.is_file():
        status = "failed_missing_artifacts"
    else:
        status = "completed"
    return {
        "returncode": result.returncode,
        "status": status,
        "json": str(json_path or ""),
        "csv": str(csv_path or ""),
    }


def _run_outreach_maintenance(
    args: argparse.Namespace,
    *,
    source_metrics: Path | None = None,
    run_id: str = "",
) -> dict[str, object]:
    """Maintain Track 2 account data and emit executable campaign artifacts."""
    summary: dict[str, object] = {
        "ran": True,
        "cycle_config": args.cycle_config,
        "strategic_accounts_artifact": "",
        "account_universe_import": "",
        "website_resolution_artifact": "",
        "context_enrichment_artifact": "",
        "account_tracker": "",
        "campaign_plan_artifact": "",
        "track_2_daily_run_artifact": "",
        "linkedin_intelligence_artifact": "",
        "company_news_artifact": "",
        "company_discovery_artifact": "",
        "role_surface_artifact": "",
        "cadence_report_artifact": "",
        "outcome_learning_artifact": "",
    }

    result = _run_capture_print(
        _outreach_cmd(
            "import-strategic-accounts",
            "--workspace",
            "workspace",
            "--execute",
        ),
        cwd=OUTREACH_ROOT,
    )
    summary["strategic_accounts_returncode"] = result.returncode
    summary["strategic_accounts_artifact"] = _artifact_from_output(result.stdout)

    result = _run_capture_print(
        _outreach_cmd(
            "import-resume-jobs",
            "--jobs-xlsx",
            "../ResumeGenerator v1/discovery/jobs.xlsx",
            "--account-universe",
        ),
        cwd=OUTREACH_ROOT,
    )
    summary["account_universe_import_returncode"] = result.returncode
    summary["account_universe_import"] = _artifact_from_output(result.stdout)

    if not args.skip_linkedin:
        result = _run_capture_print(
            _outreach_cmd(
                "capture-linkedin-intelligence",
                "--workspace",
                "workspace",
                "--profile-viewers-every-days",
                "7",
            ),
            cwd=OUTREACH_ROOT,
        )
        summary["linkedin_intelligence_returncode"] = result.returncode
        linkedin_intelligence_path = _resolve_outreach_artifact(
            _artifact_from_output(result.stdout)
        )
        summary["linkedin_intelligence_artifact"] = str(
            linkedin_intelligence_path or ""
        )
        if result.returncode != 0:
            summary["linkedin_intelligence_status"] = "failed_command"
            summary["linkedin_intelligence_validation_returncode"] = None
        elif linkedin_intelligence_path is None:
            summary["linkedin_intelligence_status"] = "failed_missing_artifact_path"
            summary["linkedin_intelligence_validation_returncode"] = 1
        elif not linkedin_intelligence_path.is_file():
            summary["linkedin_intelligence_status"] = "failed_missing_artifact"
            summary["linkedin_intelligence_validation_returncode"] = 1
        else:
            summary["linkedin_intelligence_status"] = "completed"
            summary["linkedin_intelligence_validation_returncode"] = 0
    else:
        summary["linkedin_intelligence_returncode"] = None
        summary["linkedin_intelligence_validation_returncode"] = None
        summary["linkedin_intelligence_status"] = "skipped"

    if not getattr(args, "skip_company_news", False):
        result = _run_capture_print(
            _outreach_cmd(
                "capture-company-news",
                "--workspace",
                "workspace",
                "--run-id",
                run_id or "nightly",
            ),
            cwd=OUTREACH_ROOT,
        )
        summary["company_news_returncode"] = result.returncode
        company_news_path = _resolve_outreach_artifact(
            _artifact_from_output(result.stdout)
        )
        summary["company_news_artifact"] = str(company_news_path or "")
        if result.returncode != 0:
            summary["company_news_status"] = "failed_command"
            summary["company_news_validation_returncode"] = None
        elif company_news_path is None:
            summary["company_news_status"] = "failed_missing_artifact_path"
            summary["company_news_validation_returncode"] = 1
        elif not company_news_path.is_file():
            summary["company_news_status"] = "failed_missing_artifact"
            summary["company_news_validation_returncode"] = 1
        else:
            summary["company_news_status"] = "completed"
            summary["company_news_validation_returncode"] = 0
    else:
        summary["company_news_returncode"] = None
        summary["company_news_validation_returncode"] = None
        summary["company_news_status"] = "skipped"

    linkedin_capture_artifact = (
        str(summary.get("linkedin_intelligence_artifact") or "")
        if summary.get("linkedin_intelligence_status") == "completed"
        else ""
    )
    company_news_artifact = (
        str(summary.get("company_news_artifact") or "")
        if summary.get("company_news_status") == "completed"
        else ""
    )
    if linkedin_capture_artifact or company_news_artifact or source_metrics:
        company_discovery_cmd = _outreach_cmd(
            "build-company-discovery-review",
            "--workspace",
            "workspace",
            "--run-id",
            run_id or "nightly",
        )
        if linkedin_capture_artifact:
            company_discovery_cmd.extend(
                ["--capture-artifact", linkedin_capture_artifact]
            )
        if source_metrics:
            company_discovery_cmd.extend(["--source-metrics", source_metrics])
        if company_news_artifact:
            company_discovery_cmd.extend(
                ["--news-capture-artifact", company_news_artifact]
            )
        result = _run_capture_print(
            company_discovery_cmd,
            cwd=OUTREACH_ROOT,
        )
        summary["company_discovery_returncode"] = result.returncode
        company_discovery_path = _resolve_outreach_artifact(
            _artifact_from_output(result.stdout)
        )
        summary["company_discovery_artifact"] = str(company_discovery_path or "")
        if result.returncode != 0:
            summary["company_discovery_status"] = "failed_command"
            summary["company_discovery_validation_returncode"] = None
        elif company_discovery_path is None:
            summary["company_discovery_status"] = "failed_missing_artifact_path"
            summary["company_discovery_validation_returncode"] = 1
        elif not company_discovery_path.is_file():
            summary["company_discovery_status"] = "failed_missing_artifact"
            summary["company_discovery_validation_returncode"] = 1
        else:
            summary["company_discovery_status"] = "completed"
            summary["company_discovery_validation_returncode"] = 0
    else:
        summary["company_discovery_returncode"] = None
        summary["company_discovery_validation_returncode"] = None
        summary["company_discovery_status"] = "skipped_no_current_capture"

    if source_metrics:
        result = _run_capture_print(
            _outreach_cmd(
                "build-role-surface-report",
                "--source-metrics",
                source_metrics,
                "--workspace",
                "workspace",
                "--run-id",
                run_id or source_metrics.stem,
            ),
            cwd=OUTREACH_ROOT,
        )
        summary["role_surface_returncode"] = result.returncode
        summary["role_surface_artifact"] = _artifact_from_output(result.stdout)
    else:
        summary["role_surface_returncode"] = None
        summary["role_surface_status"] = "skipped"

    if args.outreach_resolve_limit > 0:
        result = _run_capture_print(
            _outreach_cmd(
                "resolve-company-websites",
                "--workspace",
                "workspace",
                "--limit",
                args.outreach_resolve_limit,
                "--execute",
                "--max-search-results",
                args.outreach_max_search_results,
                "--timeout-seconds",
                args.outreach_timeout_seconds,
            ),
            cwd=OUTREACH_ROOT,
        )
        summary["website_resolution_returncode"] = result.returncode
        summary["website_resolution_artifact"] = _artifact_from_output(result.stdout)

    if args.outreach_enrich_limit > 0:
        enrich_cmd = _outreach_cmd(
            "enrich-company-context",
            "--workspace",
            "workspace",
            "--limit",
            args.outreach_enrich_limit,
            "--verify-all",
            "--execute",
            "--require-direct-url",
            "--no-job-fallback",
            "--timeout-seconds",
            args.outreach_timeout_seconds,
        )
        if args.outreach_no_web_search:
            enrich_cmd.append("--no-web-search")
        result = _run_capture_print(enrich_cmd, cwd=OUTREACH_ROOT)
        summary["context_enrichment_returncode"] = result.returncode
        summary["context_enrichment_artifact"] = _artifact_from_output(result.stdout)

    result = _run_capture_print(
        _outreach_cmd(
            "account-tracker",
            "--workspace",
            "workspace",
            "--output",
            "workspace/account_tracker.xlsx",
        ),
        cwd=OUTREACH_ROOT,
    )
    summary["account_tracker_returncode"] = result.returncode
    summary["account_tracker"] = _artifact_from_output(result.stdout)

    result = _run_capture_print(
        _outreach_cmd(
            "build-account-campaign-plan",
            "--workspace",
            "workspace",
            "--limit",
            args.outreach_campaign_limit,
        ),
        cwd=OUTREACH_ROOT,
    )
    summary["campaign_plan_returncode"] = result.returncode
    summary["campaign_plan_artifact"] = _artifact_from_output(result.stdout)

    track_2_timeout = max(int(getattr(args, "track_2_timeout_seconds", 14400)), 0)
    if args.execute_track_2_daily_plan:
        track_2_cmd = _outreach_cmd(
            "run-track-2-daily-plan",
            "--workspace",
            "workspace",
            "--execute",
            "--live-linkedin",
            "--refresh-linkedin",
            "--send-linkedin",
            "--max-total-actions",
            _track_2_total_actions(args),
            "--max-companies",
            _track_2_companies(args),
            "--max-linkedin-invites",
            _track_2_invite_target(args),
            "--max-linkedin-followups",
            _track_2_followup_target(args),
            "--max-company-mapping",
            _track_2_mapping_target(args),
            "--max-email-research",
            _track_2_email_research_target(args),
            "--max-context-enrichment",
            args.track_2_context_enrichment,
            "--max-email-drafts",
            _track_2_email_draft_target(args),
        )
        if args.track_2_no_network_enrichment:
            track_2_cmd.append("--no-network-enrichment")
        result = _run_capture_print(
            track_2_cmd,
            cwd=OUTREACH_ROOT,
            timeout_seconds=track_2_timeout or None,
        )
        summary["track_2_daily_run_returncode"] = result.returncode
        summary["track_2_timeout_seconds"] = track_2_timeout
        summary["track_2_daily_run_artifact"] = _artifact_from_output(result.stdout)
        track_2_artifact = _resolve_outreach_artifact(
            summary["track_2_daily_run_artifact"]
        )
        artifact_is_readable = (
            track_2_artifact is not None and track_2_artifact.is_file()
        )
        summary["track_2_artifact_validation_returncode"] = (
            0 if artifact_is_readable else 1
        )
        if getattr(result, "timed_out", False):
            summary["track_2_daily_run_status"] = "timed_out"
            summary["track_2_daily_run_failure"] = (
                f"Track 2 exceeded its {track_2_timeout}-second outer timeout; "
                "the subprocess group was terminated and partial progress must be reconciled from its artifacts."
            )
        elif result.returncode != 0:
            summary["track_2_daily_run_status"] = "failed"
            summary["track_2_daily_run_failure"] = (
                f"Track 2 exited with return code {result.returncode}."
            )
        elif not artifact_is_readable:
            summary["track_2_daily_run_status"] = "failed_missing_artifact"
            summary["track_2_daily_run_failure"] = (
                "Track 2 exited successfully but did not emit a readable "
                "authoritative run artifact."
            )
        else:
            summary["track_2_daily_run_status"] = "completed"
            summary["track_2_daily_run_failure"] = ""
    else:
        summary["track_2_daily_run_returncode"] = None
        summary["track_2_daily_run_status"] = "skipped"
        summary["track_2_timeout_seconds"] = track_2_timeout
        summary["track_2_daily_run_failure"] = ""
        summary["track_2_artifact_validation_returncode"] = None

    result = _run_capture_print(
        _outreach_cmd("build-outreach-cadence-report", "--workspace", "workspace"),
        cwd=OUTREACH_ROOT,
    )
    summary["cadence_report_returncode"] = result.returncode
    summary["cadence_report_artifact"] = _artifact_from_output(result.stdout)

    result = _run_capture_print(
        _outreach_cmd("build-outcome-learning-report", "--workspace", "workspace"),
        cwd=OUTREACH_ROOT,
    )
    summary["outcome_learning_returncode"] = result.returncode
    summary["outcome_learning_artifact"] = _artifact_from_output(result.stdout)
    return summary


def _selected_count(shortlist_path: Path) -> int:
    try:
        payload = json.loads(shortlist_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _write_summary(summary: dict, path: Path | None = None) -> Path:
    SOURCE_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    if path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = SOURCE_VALIDATION_DIR / f"{stamp}-nightly-pipeline-summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        "# Nightly Pipeline Summary",
        "",
        f"Created: {summary['created_at']}",
        f"Status: {summary.get('status', '')}",
        f"Daily engine ran: {summary['daily_engine_ran']}",
        f"Daily engine manifest: {summary.get('daily_engine_manifest') or ''}",
        f"Source metrics: {summary.get('source_metrics') or ''}",
        f"Action queue: {summary.get('action_queue') or ''}",
        f"Generation shortlist: {summary.get('generation_shortlist') or ''}",
        f"Selected for generation: {summary.get('generation_selected_count')}",
        f"Generation ran: {summary.get('generation_ran')}",
        f"Generation dry run: {summary.get('generation_dry_run')}",
        f"LinkedIn follow-up owner: {summary.get('linkedin_followup_owner') or ''}",
        f"Failures: {', '.join(summary.get('failures') or []) or 'none'}",
    ]
    outreach = summary.get("outreach_maintenance") or {}
    if outreach:
        lines.extend(
            [
                "",
                "## Outreach Track 2 Maintenance",
                "",
                f"- Ran: {outreach.get('ran')}",
                f"- Strategic account import: {outreach.get('strategic_accounts_artifact') or ''}",
                f"- Account universe import return code: {outreach.get('account_universe_import_returncode', '')}",
                f"- Website resolution: {outreach.get('website_resolution_artifact') or ''}",
                f"- Context enrichment: {outreach.get('context_enrichment_artifact') or ''}",
                f"- Account tracker: {outreach.get('account_tracker') or ''}",
                f"- Campaign plan: {outreach.get('campaign_plan_artifact') or ''}",
                f"- Track 2 daily run: {outreach.get('track_2_daily_run_artifact') or ''}",
                f"- LinkedIn feed/profile signals: {outreach.get('linkedin_intelligence_artifact') or outreach.get('linkedin_intelligence_status') or ''}",
                f"- Company/news signals: {outreach.get('company_news_artifact') or outreach.get('company_news_status') or ''}",
                f"- Company discovery review: {outreach.get('company_discovery_artifact') or ''}",
                f"- Role-surface report: {outreach.get('role_surface_artifact') or outreach.get('role_surface_status') or ''}",
                f"- Cadence report: {outreach.get('cadence_report_artifact') or ''}",
                f"- Outcome learning: {outreach.get('outcome_learning_artifact') or ''}",
            ]
        )
    shared_queue = summary.get("shared_discovery_queue") or {}
    if shared_queue:
        lines.extend(
            [
                "",
                "## Shared Discovery Queue",
                "",
                f"- Status: {shared_queue.get('status') or ('completed' if shared_queue.get('returncode') == 0 else 'failed')}",
                f"- JSON: {shared_queue.get('json') or ''}",
                f"- CSV: {shared_queue.get('csv') or ''}",
            ]
        )
    outreach_report = summary.get("outreach_daily_report") or {}
    if outreach_report:
        lines.extend(
            [
                "",
                "## Outreach Daily Report",
                "",
                f"- Return code: {outreach_report.get('returncode', '')}",
                f"- HTML report: {outreach_report.get('html_report') or ''}",
                f"- Markdown report: {outreach_report.get('daily_report') or ''}",
                f"- Report artifact: {outreach_report.get('summary_artifact') or ''}",
            ]
        )
    jobspy_metrics = summary.get("jobspy_metrics") or {}
    if jobspy_metrics:
        lines.extend(
            [
                "",
                "## JobSpy Metrics",
                "",
                f"- Raw jobs: {jobspy_metrics.get('raw_jobs', '')}",
                f"- JobSpy-only: {jobspy_metrics.get('jobspy_only', '')}",
                f"- Score-now candidates: {jobspy_metrics.get('jobspy_app_score_now', '')}",
                f"- Review candidates: {jobspy_metrics.get('jobspy_app_review', '')}",
                f"- Outreach signals: {jobspy_metrics.get('jobspy_outreach_signal', '')}",
                f"- Selected/extracted for scoring: {jobspy_metrics.get('selected_for_scoring', '')}",
                f"- Freshly scored: {jobspy_metrics.get('freshly_scored', '')}",
                f"- Existing skipped: {jobspy_metrics.get('existing_skipped', '')}",
                f"- Cache skipped: {jobspy_metrics.get('cache_skipped', '')}",
                f"- Accepted for write: {jobspy_metrics.get('accepted_for_write', '')}",
            ]
        )
    md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def _value_from_output(output: str, label: str) -> str:
    needle = f"{label}:"
    for line in output.splitlines():
        if needle in line:
            return line.split(needle, 1)[1].strip()
    return ""


def _write_outreach_daily_report(summary_path: Path, since: str) -> dict[str, object]:
    result = _run_capture_print(
        _outreach_cmd(
            "write-daily-run-report",
            "--workspace",
            "workspace",
            "--since",
            since,
            "--nightly-summary",
            summary_path,
        ),
        cwd=OUTREACH_ROOT,
    )
    return {
        "returncode": result.returncode,
        "summary_artifact": _value_from_output(result.stdout, "Summary artifact"),
        "daily_report": _value_from_output(result.stdout, "Daily report"),
        "html_report_artifact": _value_from_output(
            result.stdout, "HTML report artifact"
        ),
        "html_report": _value_from_output(result.stdout, "HTML report"),
    }


def _latest_in(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    return matches[-1] if matches else None


def _load_json(path: Path | None) -> dict:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _jobspy_metrics(source_metrics_path: Path | None) -> dict:
    """Return JobSpy metrics recorded by this daily-engine run, never "latest" data."""
    source_metrics = _load_json(source_metrics_path)
    jobspy = (source_metrics.get("sources") or {}).get("jobspy") or {}
    details = jobspy.get("details") or {}
    return {
        "status": jobspy.get("status") or "skipped",
        "raw_jobs": jobspy.get("raw_count"),
        "jobspy_only": details.get("jobspy_only"),
        "jobspy_app_score_now": details.get("app_score_now"),
        "jobspy_app_review": details.get("app_review"),
        "jobspy_outreach_signal": details.get("outreach_signal"),
        "selected_for_scoring": details.get("selected_for_scoring"),
        "freshly_scored": jobspy.get("freshly_scored_count"),
        "existing_skipped": details.get("existing_skipped"),
        "cache_skipped": details.get("cache_skipped"),
        "accepted_for_write": jobspy.get("accepted_for_write"),
        "new_after_dedup": details.get("new_after_dedup"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nightly discovery + cost-gated generation wrapper."
    )
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument(
        "--skip-daily-engine",
        action="store_true",
        help="Only rebuild generation shortlist from current queue.",
    )
    parser.add_argument(
        "--archive-generated-before-run",
        action="store_true",
        help="Archive generated jobs from the active queue before discovery. Off by default so generated-but-unapplied jobs stay active.",
    )
    parser.add_argument(
        "--skip-clear-generated-queue",
        action="store_true",
        help="Deprecated no-op kept for old launch commands.",
    )
    parser.add_argument("--skip-linkedin", action="store_true")
    parser.add_argument("--skip-company-news", action="store_true")
    parser.add_argument("--skip-handshake", action="store_true")
    parser.add_argument("--skip-jobspy", action="store_true")
    parser.add_argument("--skip-startup-apply", action="store_true")
    parser.add_argument("--skip-relationship-discovery", action="store_true")
    parser.add_argument("--skip-linkedin-preflight", action="store_true")
    parser.add_argument("--relationship-today", type=str, default="8")
    parser.add_argument("--jobspy-fetch-timeout", type=str, default="0")
    parser.add_argument("--jobspy-results", type=str, default="0")
    parser.add_argument("--linkedin-discovery-timeout", type=str, default="900")
    parser.add_argument("--jobspy-query-index", action="append", default=[])
    parser.add_argument("--startup-limit-companies", type=str, default="20")
    parser.add_argument("--startup-limit-jobs", type=str, default="50")
    parser.add_argument("--prepare-outreach", action="store_true")
    parser.add_argument("--execute-sends", action="store_true")
    parser.add_argument(
        "--cycle-config", choices=("offcycle_light", "normal"), default="offcycle_light"
    )
    parser.add_argument("--target-sends", type=str, default="auto")
    parser.add_argument("--per-company-send-limit", type=str, default="15")
    parser.add_argument("--send-min-score", type=str, default="20")
    parser.add_argument(
        "--execute-linkedin-followups",
        action="store_true",
        help=(
            "Deprecated nightly compatibility flag. Track 2 is the canonical "
            "scheduled LinkedIn inbox/follow-up lane; run_daily_engine.py "
            "directly for the standalone lane."
        ),
    )
    parser.add_argument("--linkedin-followup-send-limit", type=str, default="10")
    parser.add_argument("--linkedin-followup-send-timeout", type=str, default="240")
    parser.add_argument(
        "--linkedin-followup-recommendation", action="append", default=[]
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate resumes from the gated shortlist.",
    )
    parser.add_argument("--generation-dry-run", action="store_true")
    parser.add_argument("--generation-cap", type=str, default="10")
    parser.add_argument("--resume-parallel", type=str, default="3")
    parser.add_argument("--non-handshake-generation-min", type=str, default="7.0")
    parser.add_argument("--handshake-internal-generation-min", type=str, default="6.0")
    parser.add_argument("--handshake-external-generation-min", type=str, default="6.5")
    parser.add_argument("--handshake-unknown-generation-min", type=str, default="6.5")
    parser.add_argument(
        "--skip-outreach-maintenance",
        action="store_true",
        help="Skip Track 2 account tracker/campaign maintenance.",
    )
    parser.add_argument(
        "--skip-shared-discovery",
        action="store_true",
        help="Skip the merged cross-repo discovery queue.",
    )
    parser.add_argument(
        "--outreach-resolve-limit",
        type=int,
        default=15,
        help="Websites to resolve for unverified Outreach companies.",
    )
    parser.add_argument(
        "--outreach-enrich-limit",
        type=int,
        default=15,
        help="Companies to externally enrich after website resolution.",
    )
    parser.add_argument(
        "--outreach-campaign-limit",
        type=int,
        default=30,
        help="Track 2 campaign actions to print/save.",
    )
    parser.add_argument(
        "--outreach-timeout-seconds",
        type=int,
        default=4,
        help="Per-page Outreach enrichment timeout.",
    )
    parser.add_argument(
        "--outreach-max-search-results",
        type=int,
        default=3,
        help="Search results to validate per website resolution candidate.",
    )
    parser.add_argument(
        "--outreach-no-web-search",
        action="store_true",
        help="Only use known/direct Outreach URLs during context enrichment.",
    )
    parser.add_argument(
        "--execute-track-2-daily-plan",
        action="store_true",
        help="Execute the bounded Outreach Track 2 daily plan after rebuilding the tracker.",
    )
    parser.add_argument("--track-2-total-actions", type=str, default="auto")
    parser.add_argument("--track-2-companies", type=str, default="auto")
    parser.add_argument("--track-2-linkedin-invites", type=str, default="auto")
    parser.add_argument("--track-2-linkedin-followups", type=str, default="auto")
    parser.add_argument("--track-2-company-mapping", type=str, default="auto")
    parser.add_argument("--track-2-email-research", type=str, default="auto")
    parser.add_argument("--track-2-context-enrichment", type=str, default="8")
    parser.add_argument("--track-2-email-drafts", type=str, default="auto")
    parser.add_argument(
        "--track-2-timeout-seconds",
        type=int,
        default=14400,
        help="Outer timeout for the complete Track 2 subprocess. Default 14400 (4 hours); 0 disables.",
    )
    parser.add_argument("--track-2-no-network-enrichment", action="store_true")
    return parser.parse_args()


def _initial_summary(
    args: argparse.Namespace, *, created_at: str, run_id: str
) -> dict[str, object]:
    return {
        "created_at": created_at,
        "run_id": run_id,
        "status": "running",
        "daily_engine_ran": not args.skip_daily_engine,
        "daily_engine_returncode": None,
        "daily_engine_manifest": "",
        "daily_engine_manifest_status": "skipped"
        if args.skip_daily_engine
        else "not_started",
        "source_metrics": "",
        "source_metrics_status": "skipped" if args.skip_daily_engine else "not_started",
        "action_queue": "",
        "action_queue_status": "skipped" if args.skip_daily_engine else "not_started",
        "applied_pdfs_synced": False,
        "generated_queue_cleared": False,
        "generated_queue_archived": False,
        "generation_ran": False,
        "generation_dry_run": bool(args.generation_dry_run),
        "generation_selected_count": 0,
        "outreach_maintenance": {"ran": False},
        "shared_discovery_queue": {"status": "not_started"},
        "linkedin_followup_owner": "track_2",
        "direct_daily_linkedin_followups": "disabled_in_scheduled_nightly",
        "outreach_daily_report": {},
        "cycle_config": args.cycle_config,
        "app_queue_target_sends": _app_queue_target_sends(args),
        "failures": [],
    }


def _path_from_manifest(manifest: dict, key: str) -> Path | None:
    value = str(manifest.get(key) or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path if path.is_file() else None


def _outreach_maintenance_failures(maintenance: dict[str, object]) -> list[str]:
    failures = [
        f"{key}:{value}"
        for key, value in maintenance.items()
        if key.endswith("_returncode") and value not in (0, None)
    ]
    if maintenance.get("track_2_daily_run_status") == "timed_out":
        failures.append(
            "track_2_daily_run:timed_out:"
            f"{maintenance.get('track_2_timeout_seconds', 0)}s"
        )
    return failures


# Backwards-compatible name retained for existing callers and focused tests.
_nonzero_returncode_failures = _outreach_maintenance_failures


def _run_pipeline_body(
    args: argparse.Namespace,
    *,
    summary: dict[str, object],
    failures: list[str],
) -> None:
    source_metrics: Path | None = None
    action_queue: Path | None = None
    run_id = str(summary["run_id"])

    if args.execute_linkedin_followups:
        raise SystemExit(
            "--execute-linkedin-followups is not valid in scheduled nightly mode: "
            "Track 2 owns inbox reconciliation and follow-up sends. Run "
            "run_daily_engine.py standalone for the direct lane."
        )

    run(_sync_applied_pdfs_cmd())
    summary["applied_pdfs_synced"] = True

    if args.archive_generated_before_run and not args.skip_clear_generated_queue:
        run(_clear_generated_queue_cmd())
        summary["generated_queue_cleared"] = True
        summary["generated_queue_archived"] = True

    if not args.skip_daily_engine:
        manifest_path = daily_engine_manifest_path(run_id)
        daily_result = run(_daily_engine_cmd(args, run_id=run_id), check=False)
        summary["daily_engine_returncode"] = daily_result.returncode
        if daily_result.returncode != 0:
            failures.append(f"daily_engine:{daily_result.returncode}")
        if manifest_path.is_file():
            summary["daily_engine_manifest"] = str(manifest_path)
            summary["daily_engine_manifest_status"] = "current_run"
            daily_manifest = _load_json(manifest_path)
            source_metrics = _path_from_manifest(daily_manifest, "source_metrics")
            action_queue = _path_from_manifest(daily_manifest, "action_queue")
        else:
            summary["daily_engine_manifest_status"] = "missing_current_run"
            failures.append("daily_engine_manifest:missing_current_run")
            daily_manifest = {}
            action_queue = None

        if source_metrics:
            summary["source_metrics"] = str(source_metrics)
            summary["source_metrics_status"] = "current_run"
        else:
            summary["source_metrics_status"] = "missing_current_run"
            if daily_result.returncode == 0:
                failures.append("source_metrics:missing_current_run")
        if action_queue:
            summary["action_queue"] = str(action_queue)
            summary["action_queue_status"] = "current_run"
        else:
            summary["action_queue_status"] = "missing_current_run"

    summary["jobspy_metrics"] = _jobspy_metrics(source_metrics)

    run(_shortlist_cmd(args))
    shortlist_path = (
        CURRENT_SHORTLIST_JSON
        if CURRENT_SHORTLIST_JSON.exists()
        else latest("*generation-shortlist.json")
    )
    if not shortlist_path:
        raise SystemExit("Generation shortlist was not created.")
    selected_count = _selected_count(shortlist_path)
    summary["generation_shortlist"] = str(shortlist_path)
    summary["generation_selected_count"] = selected_count

    if args.generate and selected_count > 0:
        run(_generate_cmd(args, shortlist_path))
        summary["generation_ran"] = True
    elif args.generate:
        print(
            "\nNo jobs selected for generation; skipping jobs.py generate.", flush=True
        )

    if not args.skip_outreach_maintenance:
        summary["outreach_maintenance"] = _run_outreach_maintenance(
            args,
            source_metrics=source_metrics,
            run_id=run_id,
        )
        failures.extend(_outreach_maintenance_failures(summary["outreach_maintenance"]))

    # Older programmatic callers do not know this newer stage; preserve their
    # prior behavior while the CLI parser opts in explicitly with False.
    skip_shared_discovery = getattr(args, "skip_shared_discovery", True)
    if action_queue and not skip_shared_discovery:
        shared_queue = _run_shared_discovery_queue(action_queue)
        summary["shared_discovery_queue"] = shared_queue
        if shared_queue.get("status") != "completed":
            failures.append(
                "shared_discovery_queue:"
                f"{shared_queue.get('status') or shared_queue.get('returncode')}"
            )
    elif skip_shared_discovery:
        summary["shared_discovery_queue"] = {"status": "skipped"}
    else:
        summary["shared_discovery_queue"] = {
            "status": "skipped_missing_current_action_queue"
        }


def _exception_returncode(exc: BaseException) -> int:
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, SystemExit):
        return exc.code if isinstance(exc.code, int) and exc.code != 0 else 1
    if isinstance(exc, subprocess.CalledProcessError):
        return int(exc.returncode or 1)
    return 1


def _artifact_pointers(value: object, *, key: str = "") -> list[str]:
    pointers: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            pointers.extend(_artifact_pointers(child, key=str(child_key)))
    elif isinstance(value, list):
        for child in value:
            pointers.extend(_artifact_pointers(child, key=key))
    elif "artifact" in key.casefold():
        path = _resolve_outreach_artifact(value)
        if path is not None and path.is_file():
            pointers.append(str(path))
    return list(dict.fromkeys(pointers))


def _smtp_configured() -> bool:
    configured = {
        "SMTP_HOST": bool(os.environ.get("SMTP_HOST", "").strip()),
        "SMTP_FROM_EMAIL": bool(os.environ.get("SMTP_FROM_EMAIL", "").strip()),
    }
    env_path = OUTREACH_ROOT / ".env"
    if env_path.is_file() and not all(configured.values()):
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            clean = line.strip()
            if not clean or clean.startswith("#") or "=" not in clean:
                continue
            if clean.startswith("export "):
                clean = clean.removeprefix("export ").lstrip()
            key, value = clean.split("=", 1)
            key = key.strip()
            if key in configured and value.strip().strip("'\""):
                configured[key] = True
    return all(configured.values())


def _track_2_phase_counts(phase_results: list[dict]) -> list[dict[str, object]]:
    counts: list[dict[str, object]] = []
    for phase in phase_results:
        status_counts = (
            phase.get("send_status_counts")
            if isinstance(phase.get("send_status_counts"), dict)
            else {}
        )
        run_sent = 0
        for run_row in list(phase.get("runs") or []):
            if not isinstance(run_row, dict):
                continue
            run_statuses = (
                run_row.get("status_counts")
                if isinstance(run_row.get("status_counts"), dict)
                else {}
            )
            run_sent += int(run_statuses.get("sent") or 0)
        actual = max(
            int(status_counts.get("sent") or 0),
            run_sent,
            int(phase.get("touchpoints_added") or 0),
            int(phase.get("updated") or 0),
            int(phase.get("inspected_count") or 0),
            int(phase.get("draft_count") or 0),
            int(phase.get("count") or 0)
            if str(phase.get("status") or "") in {"ran", "inspected", "drafted"}
            else 0,
            len(list(phase.get("runs") or []))
            if str(phase.get("status") or "") == "ran"
            else 0,
        )
        counts.append(
            {
                "phase": str(phase.get("phase") or ""),
                "status": str(phase.get("status") or "skipped"),
                "planned_count": int(phase.get("budget") or phase.get("count") or 0),
                "actual_count": actual,
            }
        )
    return counts


def _augment_daily_engine_manifest(summary: dict[str, object]) -> None:
    manifest_value = str(summary.get("daily_engine_manifest") or "").strip()
    if not manifest_value:
        return
    manifest_path = Path(manifest_value)
    if not manifest_path.is_file():
        return
    manifest = _load_json(manifest_path)
    if not manifest:
        return
    maintenance = (
        summary.get("outreach_maintenance")
        if isinstance(summary.get("outreach_maintenance"), dict)
        else {}
    )
    returncode = maintenance.get("track_2_daily_run_returncode")
    track_path = _resolve_outreach_artifact(
        maintenance.get("track_2_daily_run_artifact")
    )
    track_payload = (
        _load_json(track_path) if track_path and track_path.is_file() else {}
    )
    if returncode is None:
        status = "skipped"
    elif maintenance.get("track_2_daily_run_status") == "timed_out":
        status = "timed_out"
    elif returncode != 0:
        status = "failed"
    elif not track_payload:
        status = "failed_missing_artifact"
    else:
        status = "ran"
    phase_results = [
        item
        for item in list(track_payload.get("phase_results") or [])
        if isinstance(item, dict)
    ]
    phase_counts = _track_2_phase_counts(phase_results)
    phase_artifacts = _artifact_pointers(phase_results)
    email_draft_phases = [
        phase
        for phase in phase_results
        if "email" in str(phase.get("phase") or "").casefold()
        and (
            "draft" in str(phase.get("phase") or "").casefold()
            or str(phase.get("status") or "").casefold() == "drafted"
        )
    ]
    email_send_phases = [
        phase
        for phase in phase_results
        if "email" in str(phase.get("phase") or "").casefold()
        and str(phase.get("status") or "").casefold()
        in {"sent", "partial_sent", "delivered"}
    ]
    email_draft_artifacts = _artifact_pointers(email_draft_phases)
    email_send_artifacts = _artifact_pointers(email_send_phases)
    email_draft_count = sum(
        int(phase.get("draft_count") or phase.get("count") or 0)
        for phase in email_draft_phases
    )
    email_sent_count = sum(
        max(
            int(phase.get("sent_count") or 0),
            int(
                (phase.get("send_status_counts") or {}).get("sent")
                if isinstance(phase.get("send_status_counts"), dict)
                else 0
            ),
        )
        for phase in email_send_phases
    )
    smtp_configured = _smtp_configured()
    email_blockers: list[str] = []
    if email_send_artifacts and email_sent_count:
        email_status = "sent"
    elif email_draft_artifacts:
        email_status = "drafted_review_needed"
        email_blockers.append(
            "Explicit human approval bound to the reviewed recipient, subject, and body is required before SMTP delivery."
        )
        if not smtp_configured:
            email_blockers.append(
                "SMTP_HOST and SMTP_FROM_EMAIL are not configured for the Outreach runtime."
            )
    elif status != "ran":
        email_status = (
            "skipped_track_2_failed"
            if status.startswith("failed") or status == "timed_out"
            else "skipped_track_2_not_run"
        )
        email_blockers.append(
            "Track 2 did not complete an email-draft lane in this run."
        )
    elif not smtp_configured:
        email_status = "skipped_missing_credentials"
        email_blockers.append(
            "SMTP_HOST and SMTP_FROM_EMAIL are not configured for the Outreach runtime."
        )
    else:
        email_status = "skipped_no_due_drafts"
        email_blockers.append(
            "No due, verified, review-ready email draft was selected in this run."
        )
    email_channel = {
        "status": email_status,
        "smtp_configured": smtp_configured,
        "blockers": email_blockers,
        "draft_artifacts": email_draft_artifacts,
        "send_artifacts": email_send_artifacts,
        "draft_count": email_draft_count,
        "sent_count": email_sent_count,
        "approval_required": True,
        "nightly_delivery_enabled": False,
    }
    run_artifacts = [str(track_path)] if track_path and track_path.is_file() else []
    used = (
        track_payload.get("used") if isinstance(track_payload.get("used"), dict) else {}
    )
    planned_count = int(used.get("total_actions") or 0)
    actual_count = sum(int(row.get("actual_count") or 0) for row in phase_counts)
    track_2 = {
        "status": status,
        "returncode": returncode,
        "timeout_seconds": int(maintenance.get("track_2_timeout_seconds") or 0),
        "failure": str(maintenance.get("track_2_daily_run_failure") or ""),
        "run_artifact": str(track_path or ""),
        "artifacts": list(dict.fromkeys([*run_artifacts, *phase_artifacts])),
        "planned_action_count": planned_count,
        "actual_action_count": actual_count,
        "used": used,
        "summary": track_payload.get("summary") or {},
        "phase_summary": track_payload.get("phase_summary") or {},
        "phase_counts": phase_counts,
        "phase_results": phase_results,
    }
    manifest["track_2_daily_run_artifacts"] = run_artifacts
    manifest["track_2_phase_artifacts"] = phase_artifacts
    manifest["track_2_phase_results"] = phase_results
    manifest["track_2_email_draft_artifacts"] = email_draft_artifacts
    manifest["track_2_email_send_artifacts"] = email_send_artifacts
    manifest["email_channel"] = email_channel
    manifest["track_2"] = track_2
    source_families = (
        manifest.get("source_families")
        if isinstance(manifest.get("source_families"), dict)
        else {}
    )
    source_families["track_2"] = {
        "status": status,
        "raw_count": planned_count,
        "kept_count": actual_count,
        "details": track_2,
    }
    manifest["source_families"] = source_families
    shared_queue = (
        summary.get("shared_discovery_queue")
        if isinstance(summary.get("shared_discovery_queue"), dict)
        else {}
    )

    def existing_artifact(value: object) -> str:
        path = _resolve_outreach_artifact(value)
        return str(path) if path is not None and path.is_file() else ""

    company_news_artifact = existing_artifact(
        maintenance.get("company_news_artifact")
    )
    company_discovery_artifact = existing_artifact(
        maintenance.get("company_discovery_artifact")
    )
    shared_json = existing_artifact(shared_queue.get("json"))
    shared_csv = existing_artifact(shared_queue.get("csv"))
    manifest["nightly_extensions"] = {
        "schema": "resume_generator.nightly_extensions",
        "version": 1,
        "run_id": str(summary.get("run_id") or ""),
        "linkedin_followup_owner": "track_2",
        "direct_daily_linkedin_followups": "disabled_in_scheduled_nightly",
        "company_news": {
            "status": str(maintenance.get("company_news_status") or "skipped"),
            "returncode": maintenance.get("company_news_returncode"),
            "artifacts": [company_news_artifact] if company_news_artifact else [],
        },
        "company_discovery": {
            "status": (
                "completed"
                if company_discovery_artifact
                else str(maintenance.get("company_discovery_status") or "skipped")
            ),
            "returncode": maintenance.get("company_discovery_returncode"),
            "artifacts": (
                [company_discovery_artifact] if company_discovery_artifact else []
            ),
        },
        "shared_discovery": {
            "status": str(shared_queue.get("status") or "skipped"),
            "returncode": shared_queue.get("returncode"),
            "artifacts": [path for path in (shared_json, shared_csv) if path],
            "action_queue": str(manifest.get("action_queue") or ""),
        },
    }
    manifest["company_news_artifacts"] = (
        [company_news_artifact] if company_news_artifact else []
    )
    manifest["company_discovery_artifacts"] = (
        [company_discovery_artifact] if company_discovery_artifact else []
    )
    manifest["shared_discovery_artifacts"] = [
        path for path in (shared_json, shared_csv) if path
    ]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _finalize_summary_and_report(
    *,
    summary: dict[str, object],
    failures: list[str],
    summary_path: Path,
) -> None:
    summary["failures"] = failures
    summary["status"] = "failed" if failures else "completed"
    summary["completed_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        _augment_daily_engine_manifest(summary)
    except Exception as exc:
        failure = f"daily_engine_manifest_augmentation:{type(exc).__name__}"
        if failure not in failures:
            failures.append(failure)
        summary["daily_engine_manifest_augmentation_error"] = str(exc)
        summary["failures"] = failures
        summary["status"] = "failed"
    _write_summary(summary, path=summary_path)
    try:
        report_summary = _write_outreach_daily_report(
            summary_path,
            str(summary["created_at"]),
        )
    except BaseException as exc:
        report_summary = {
            "returncode": _exception_returncode(exc),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    summary["outreach_daily_report"] = report_summary
    if report_summary.get("returncode") not in (0, None):
        failure = f"outreach_daily_report:{report_summary.get('returncode')}"
        if failure not in failures:
            failures.append(failure)
        summary["failures"] = failures
        summary["status"] = "failed"
    _write_summary(summary, path=summary_path)
    print(f"\nNightly summary: {summary_path}", flush=True)


def main() -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = _run_id(created_at)
    summary_path = SOURCE_VALIDATION_DIR / f"{run_id}-nightly-pipeline-summary.json"
    try:
        args = parse_args()
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        returncode = _exception_returncode(exc)
        fallback_args = argparse.Namespace(
            skip_daily_engine=True,
            generation_dry_run=False,
            cycle_config="",
            target_sends="auto",
        )
        summary = _initial_summary(
            fallback_args,
            created_at=created_at,
            run_id=run_id,
        )
        summary["argument_parse_failure"] = {
            "returncode": returncode,
            "argv": sys.argv[1:],
        }
        _finalize_summary_and_report(
            summary=summary,
            failures=[f"argument_parse:{returncode}"],
            summary_path=summary_path,
        )
        return returncode
    with _pipeline_lock(LOCK_PATH):
        failures: list[str] = []
        summary = _initial_summary(args, created_at=created_at, run_id=run_id)
        exception_returncode = 0
        try:
            _run_pipeline_body(args, summary=summary, failures=failures)
        except BaseException as exc:
            exception_returncode = _exception_returncode(exc)
            failure = f"pipeline_exception:{type(exc).__name__}:{exception_returncode}"
            failures.append(failure)
            summary["pipeline_exception"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "returncode": exception_returncode,
                "traceback": traceback.format_exc(limit=12),
            }
            print(
                f"[error] Nightly pipeline failed before normal completion: {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
        finally:
            _finalize_summary_and_report(
                summary=summary,
                failures=failures,
                summary_path=summary_path,
            )
        if exception_returncode:
            return exception_returncode
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
