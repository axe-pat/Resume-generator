#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _cmd_text(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(cmd: list[object], *, cwd: Path = ROOT) -> None:
    print(f"\n$ {_cmd_text(cmd)}")
    subprocess.run([str(part) for part in cmd], cwd=cwd, check=True)


def start(cmd: list[object], *, cwd: Path = ROOT) -> subprocess.Popen:
    print(f"\n$ {_cmd_text(cmd)}")
    return subprocess.Popen([str(part) for part in cmd], cwd=cwd)


def latest(pattern: str, directory: Path) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {directory / pattern}")
    return matches[-1]


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


def selected_outreach_companies(action_queue_path: Path, *, app_limit: int, relationship_limit: int) -> list[str]:
    payload = json.loads(action_queue_path.read_text(encoding="utf-8"))
    companies: list[str] = []
    seen: set[str] = set()

    for item in payload.get("application_plus_outreach") or []:
        company = str(item.get("company") or "").strip()
        if company and company.lower() not in seen:
            companies.append(company)
            seen.add(company.lower())
        if len(companies) >= app_limit:
            break

    relationship_added = 0
    for item in payload.get("outreach_only_today") or []:
        company = str(item.get("company") or "").strip()
        if company and company.lower() not in seen:
            companies.append(company)
            seen.add(company.lower())
            relationship_added += 1
        if relationship_added >= relationship_limit:
            break
    return companies


def run_outreach_from_action_queue(args: argparse.Namespace, action_queue_path: Path) -> None:
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
        run(cmd, cwd=OUTREACH_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supervised daily application + outreach engine.")
    parser.add_argument("--window", choices=("24h", "7d"), default="24h")
    parser.add_argument("--skip-linkedin", action="store_true")
    parser.add_argument("--skip-jobspy", action="store_true")
    parser.add_argument("--skip-startup-apply", action="store_true")
    parser.add_argument("--skip-relationship-discovery", action="store_true")
    parser.add_argument("--jobspy-results", type=int, default=None)
    parser.add_argument("--jobspy-score-limit", type=int, default=10)
    parser.add_argument("--startup-limit-companies", type=int, default=12)
    parser.add_argument("--startup-limit-jobs", type=int, default=30)
    parser.add_argument("--relationship-source-limit", type=int, default=25)
    parser.add_argument("--relationship-today", type=int, default=8)
    parser.add_argument("--run-generation", action="store_true")
    parser.add_argument("--resume-parallel", type=int, default=3)
    parser.add_argument("--prepare-outreach", action="store_true")
    parser.add_argument("--app-outreach-limit", type=int, default=3)
    parser.add_argument("--relationship-outreach-limit", type=int, default=2)
    parser.add_argument("--parallel-generation-outreach", action="store_true")
    parser.add_argument("--execute-sends", action="store_true", help="Actually send LinkedIn invites after artifact generation.")
    parser.add_argument("--send-limit", type=int, default=0)
    parser.add_argument("--send-min-score", type=int, default=35)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute_sends and args.parallel_generation_outreach:
        raise SystemExit("--execute-sends is intentionally not supported with --parallel-generation-outreach.")
    hours_old = window_to_hours(args.window)

    if not args.skip_linkedin:
        run(["./discovery/scripts/run_linkedin_discovery.sh", args.window])

    if not args.skip_jobspy:
        fetch_cmd: list[object] = [PYTHON, "discovery/scripts/fetch_jobspy_breadth.py", "--hours-old", hours_old]
        if args.jobspy_results:
            fetch_cmd.extend(["--results", args.jobspy_results])
        run(fetch_cmd)
        jobspy_raw = latest(f"jobspy_breadth_raw_{hours_old}h_*.json", LOGS_DIR)
        playwright_raw = latest("linkedin_live_raw_*.json", LOGS_DIR)
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
        source_breadth = latest("*source-breadth-filtered.json", SOURCE_VALIDATION_DIR)
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

    if not args.skip_startup_apply:
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

    if not args.skip_relationship_discovery:
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
    action_queue_path = build_action_queue(args)
    print(f"\nFinal action queue: {action_queue_path}")
    print(f"Final action report: {action_queue_path.with_suffix('.html')}")

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
        for company in companies:
            run([OUTREACH_PYTHON, "main.py", "run", "--company", company, "--company-mode", "startup"], cwd=OUTREACH_ROOT)
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
