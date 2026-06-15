#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "venv" / "bin" / "python"
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"
CURRENT_SHORTLIST_JSON = ROOT / "apps" / "Apply queues" / "current_apply_queue" / "generation_shortlist.json"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "ResumeGenerator"
LOCK_PATH = APP_SUPPORT / "nightly_pipeline.lock"


def _cmd_text(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(cmd: list[object], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n$ {_cmd_text(cmd)}", flush=True)
    return subprocess.run([str(part) for part in cmd], cwd=ROOT, check=check)


def latest(pattern: str) -> Path | None:
    matches = sorted(SOURCE_VALIDATION_DIR.glob(pattern), key=lambda path: path.stat().st_mtime)
    return matches[-1] if matches else None


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


def _daily_engine_cmd(args: argparse.Namespace) -> list[object]:
    cmd: list[object] = [
        PYTHON,
        "discovery/scripts/run_daily_engine.py",
        "--window",
        args.window,
    ]
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
    if args.prepare_outreach:
        cmd.append("--prepare-outreach")
    if args.execute_sends:
        cmd.append("--execute-sends")
        cmd.extend(["--target-sends", args.target_sends])
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


def _selected_count(shortlist_path: Path) -> int:
    try:
        payload = json.loads(shortlist_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _write_summary(summary: dict) -> Path:
    SOURCE_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SOURCE_VALIDATION_DIR / f"{stamp}-nightly-pipeline-summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        "# Nightly Pipeline Summary",
        "",
        f"Created: {summary['created_at']}",
        f"Daily engine ran: {summary['daily_engine_ran']}",
        f"Action queue: {summary.get('action_queue') or ''}",
        f"Generation shortlist: {summary.get('generation_shortlist') or ''}",
        f"Selected for generation: {summary.get('generation_selected_count')}",
        f"Generation ran: {summary.get('generation_ran')}",
        f"Generation dry run: {summary.get('generation_dry_run')}",
    ]
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


def _jobspy_metrics() -> dict:
    raw = _load_json(_latest_in(LOGS_DIR, "jobspy_breadth_raw_*h_*.json"))
    breadth = _load_json(_latest_in(SOURCE_VALIDATION_DIR, "*source-breadth-filtered.json"))
    scored = _load_json(_latest_in(LOGS_DIR, "jobspy_filtered_scored_*.json"))
    jobspy_bucket = (breadth.get("classified") or {}).get("jobspy_only") or {}
    return {
        "raw_jobs": raw.get("count") or len(raw.get("jobs") or []),
        "jobspy_only": (breadth.get("raw_counts") or {}).get("jobspy_only"),
        "jobspy_app_score_now": len(jobspy_bucket.get("app_score_now") or []),
        "jobspy_app_review": len(jobspy_bucket.get("app_review") or []),
        "jobspy_outreach_signal": len(jobspy_bucket.get("outreach_signal") or []),
        "selected_for_scoring": scored.get("extracted"),
        "freshly_scored": scored.get("scored"),
        "existing_skipped": scored.get("existing_skipped"),
        "cache_skipped": scored.get("cache_skipped"),
        "accepted_for_write": scored.get("accepted_for_write"),
        "new_after_dedup": scored.get("new_after_dedup"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nightly discovery + cost-gated generation wrapper.")
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument("--skip-daily-engine", action="store_true", help="Only rebuild generation shortlist from current queue.")
    parser.add_argument("--archive-generated-before-run", action="store_true", help="Archive generated jobs from the active queue before discovery. Off by default so generated-but-unapplied jobs stay active.")
    parser.add_argument("--skip-clear-generated-queue", action="store_true", help="Deprecated no-op kept for old launch commands.")
    parser.add_argument("--skip-linkedin", action="store_true")
    parser.add_argument("--skip-handshake", action="store_true")
    parser.add_argument("--skip-jobspy", action="store_true")
    parser.add_argument("--skip-startup-apply", action="store_true")
    parser.add_argument("--skip-relationship-discovery", action="store_true")
    parser.add_argument("--skip-linkedin-preflight", action="store_true")
    parser.add_argument("--relationship-today", type=str, default="8")
    parser.add_argument("--jobspy-fetch-timeout", type=str, default="1800")
    parser.add_argument("--startup-limit-companies", type=str, default="12")
    parser.add_argument("--startup-limit-jobs", type=str, default="30")
    parser.add_argument("--prepare-outreach", action="store_true")
    parser.add_argument("--execute-sends", action="store_true")
    parser.add_argument("--target-sends", type=str, default="25")
    parser.add_argument("--per-company-send-limit", type=str, default="15")
    parser.add_argument("--send-min-score", type=str, default="20")
    parser.add_argument("--generate", action="store_true", help="Generate resumes from the gated shortlist.")
    parser.add_argument("--generation-dry-run", action="store_true")
    parser.add_argument("--generation-cap", type=str, default="10")
    parser.add_argument("--resume-parallel", type=str, default="3")
    parser.add_argument("--non-handshake-generation-min", type=str, default="7.0")
    parser.add_argument("--handshake-internal-generation-min", type=str, default="6.0")
    parser.add_argument("--handshake-external-generation-min", type=str, default="6.5")
    parser.add_argument("--handshake-unknown-generation-min", type=str, default="6.5")
    return parser.parse_args()


def main() -> int:
    with _pipeline_lock(LOCK_PATH):
        args = parse_args()
        summary = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "daily_engine_ran": not args.skip_daily_engine,
            "applied_pdfs_synced": False,
            "generated_queue_cleared": False,
            "generated_queue_archived": False,
            "generation_ran": False,
            "generation_dry_run": bool(args.generation_dry_run),
        }

        run(_sync_applied_pdfs_cmd())
        summary["applied_pdfs_synced"] = True

        if args.archive_generated_before_run and not args.skip_clear_generated_queue:
            run(_clear_generated_queue_cmd())
            summary["generated_queue_cleared"] = True
            summary["generated_queue_archived"] = True

        if not args.skip_daily_engine:
            run(_daily_engine_cmd(args))
        action_queue = latest("*daily-action-queue.json")
        if action_queue:
            summary["action_queue"] = str(action_queue)
        summary["jobspy_metrics"] = _jobspy_metrics()

        run(_shortlist_cmd(args))
        shortlist_path = CURRENT_SHORTLIST_JSON if CURRENT_SHORTLIST_JSON.exists() else latest("*generation-shortlist.json")
        if not shortlist_path:
            raise SystemExit("Generation shortlist was not created.")
        selected_count = _selected_count(shortlist_path)
        summary["generation_shortlist"] = str(shortlist_path)
        summary["generation_selected_count"] = selected_count

        if args.generate and selected_count > 0:
            run(_generate_cmd(args, shortlist_path))
            summary["generation_ran"] = True
        elif args.generate:
            print("\nNo jobs selected for generation; skipping jobs.py generate.", flush=True)

        summary_path = _write_summary(summary)
        print(f"\nNightly summary: {summary_path}", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
