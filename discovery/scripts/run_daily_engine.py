#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
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
    parser.add_argument("--jobspy-results", type=int, default=None)
    parser.add_argument("--jobspy-score-limit", type=int, default=10)
    parser.add_argument("--jobspy-fetch-timeout", type=int, default=1800, help="Seconds before skipping the JobSpy breadth scrape for this run.")
    parser.add_argument("--startup-limit-companies", type=int, default=12)
    parser.add_argument("--startup-limit-jobs", type=int, default=30)
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


def main() -> int:
    args = parse_args()
    if args.execute_sends and args.parallel_generation_outreach:
        raise SystemExit("--execute-sends is intentionally not supported with --parallel-generation-outreach.")
    hours_old = window_to_hours(args.window)

    needs_linkedin = (not args.skip_linkedin) or bool(args.prepare_outreach)
    if needs_linkedin and not args.skip_linkedin_preflight:
        run(["./discovery/scripts/ensure_chrome_9222.sh"])

    if not args.skip_linkedin:
        run(["./discovery/scripts/run_linkedin_discovery.sh", args.window])

    if not args.skip_handshake:
        run(["./discovery/scripts/run_handshake_discovery.sh", args.window])

    if not args.skip_jobspy:
        fetch_cmd: list[object] = [PYTHON, "discovery/scripts/fetch_jobspy_breadth.py", "--hours-old", hours_old]
        if args.jobspy_results:
            fetch_cmd.extend(["--results", args.jobspy_results])
        jobspy_fetch = run_capture(fetch_cmd, check=False, timeout=args.jobspy_fetch_timeout)
        if jobspy_fetch.returncode != 0:
            print(f"[warn] Skipping JobSpy validation/scoring because fetch exited with {jobspy_fetch.returncode}.", file=sys.stderr)
        else:
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
