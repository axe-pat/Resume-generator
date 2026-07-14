#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from production_release import (  # noqa: E402
    DEFAULT_ATTESTATION_PATH,
    ProductionReleaseError,
    validate_attestation,
)
from nightly_contract import (  # noqa: E402
    PRODUCTION_SLOT_TIMES,
    PRODUCTION_SLOTS,
    production_slot_args,
    validate_production_nightly_args,
    validate_production_slot_args,
)

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "venv" / "bin" / "python"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "ResumeGenerator"
STATE_PATH = APP_SUPPORT / "nightly_scheduler_state.json"
DISCOVERY_STATE_PATH = APP_SUPPORT / "nightly_discovery_cadence.json"
LOCK_PATH = APP_SUPPORT / "nightly_scheduler.lock"
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_DISCOVERY_CADENCE_HOURS = 48.0
LOG_DIR = Path(
    os.environ.get(
        "RESUMEGEN_NIGHTLY_LOG_DIR",
        Path.home() / "Library" / "Logs" / "ResumeGenerator",
    )
).expanduser()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError as exc:  # pragma: no cover - macOS ships tzdata
        raise RuntimeError(f"Required timezone is unavailable: {DEFAULT_TIMEZONE}") from exc


def _now() -> datetime:
    return datetime.now(_timezone())


def _today_key(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d")


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(0)
        yield


def _parse_hhmm(value: str) -> time:
    try:
        hour_s, minute_s = value.strip().split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    except Exception as exc:
        raise ValueError("Use HH:MM, for example 21:30") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Use a 24-hour time from 00:00 to 23:59")
    return time(hour=hour, minute=minute)


def _scheduled_at(today: datetime, scheduled_time: str) -> datetime:
    scheduled = _parse_hhmm(scheduled_time)
    return today.replace(
        hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0
    )


def _parse_iso(value: str, *, reference: datetime | None = None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if reference is not None and reference.tzinfo is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=reference.tzinfo)
    return parsed


def _discovery_due(
    state: dict,
    *,
    now: datetime,
    cadence_hours: float = DEFAULT_DISCOVERY_CADENCE_HOURS,
) -> tuple[bool, str]:
    """Gate discovery by attempt time, not success, to avoid unsafe replay."""

    last_attempt = _parse_iso(str(state.get("last_attempt_at") or ""), reference=now)
    if last_attempt is None:
        return True, "no_previous_discovery_attempt"
    elapsed = now - last_attempt
    if elapsed < timedelta(0):
        return False, "clock_before_last_discovery_attempt"
    remaining = timedelta(hours=max(cadence_hours, 0)) - elapsed
    if remaining <= timedelta(0):
        return True, "discovery_cadence_elapsed"
    seconds = max(0, int(remaining.total_seconds()))
    return False, f"discovery_due_in_{seconds}s"


def _due(state: dict, args: argparse.Namespace) -> tuple[bool, str]:
    if args.force:
        return True, "forced"
    now = _now()
    today = _today_key(now)
    if state.get("last_attempt_date") == today or state.get("last_run_date") == today:
        return False, "already_ran_today"
    if state.get("last_skip_date") == today:
        return False, "skipped_today"
    snooze_until = _parse_iso(
        str(state.get("snooze_until") or ""), reference=now
    )
    if snooze_until and now < snooze_until:
        return False, f"snoozed_until_{snooze_until.isoformat(timespec='minutes')}"
    if now >= _scheduled_at(now, args.scheduled_time):
        return True, "scheduled_or_catchup"
    return False, "before_scheduled_time"


def _osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], text=True, capture_output=True)


def _prompt_choice(args: argparse.Namespace, reason: str) -> str:
    try:
        pipeline_args = shlex.join(_pipeline_args(args))
    except ValueError as exc:
        pipeline_args = f"invalid: {exc}"
    message = (
        "ResumeGenerator nightly pipeline is due.\\n\\n"
        f"Reason: {reason}\\n"
        f"Scheduled time: {args.scheduled_time}\\n"
        f"Pipeline args: {pipeline_args}"
    )
    script = (
        f"display dialog {json.dumps(message)} "
        'buttons {"Skip Today", "Snooze", "Run Now"} '
        'default button "Run Now" cancel button "Skip Today"'
    )
    result = _osascript(script)
    if result.returncode != 0:
        return "Skip Today"
    output = result.stdout.strip()
    if "button returned:Snooze" in output:
        return "Snooze"
    if "button returned:Run Now" in output:
        return "Run Now"
    return "Skip Today"


def _prompt_snooze_time(default_time: str) -> datetime | None:
    script = (
        'display dialog "Snooze nightly pipeline until what local time? Use HH:MM." '
        f"default answer {json.dumps(default_time)} "
        'buttons {"Cancel", "OK"} default button "OK" cancel button "Cancel"'
    )
    result = _osascript(script)
    if result.returncode != 0:
        return None
    match = result.stdout.strip().split("text returned:", 1)
    if len(match) != 2:
        return None
    try:
        target_time = _parse_hhmm(match[1].strip())
    except ValueError as exc:
        _osascript(f"display alert {json.dumps(str(exc))}")
        return None
    now = _now()
    target = now.replace(
        hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=1)
    return target


def _pipeline_command(args: argparse.Namespace) -> list[str]:
    extra_args = _pipeline_args(args)
    return [str(PYTHON), "discovery/scripts/run_nightly_pipeline.py", *extra_args]


def _pipeline_args(args: argparse.Namespace) -> list[str]:
    production_slot = str(getattr(args, "production_slot", "") or "")
    if production_slot:
        explicit = str(getattr(args, "pipeline_args", "") or "").strip()
        inherited = os.environ.get("RESUMEGEN_NIGHTLY_ARGS", "").strip()
        if explicit or inherited:
            raise ValueError(
                "production slots use the reviewed dynamic contract; "
                "RESUMEGEN_NIGHTLY_ARGS/--pipeline-args overrides are forbidden"
            )
        return list(
            production_slot_args(
                production_slot,
                include_discovery=bool(
                    getattr(args, "include_discovery", False)
                ),
            )
        )
    return shlex.split(
        getattr(args, "pipeline_args", "")
        or os.environ.get("RESUMEGEN_NIGHTLY_ARGS", "--generate")
    )


def _pipeline_outcome(
    log_path: Path, subprocess_returncode: int
) -> tuple[int, str, Path | None]:
    """Bind scheduler success to the exact terminal nightly summary."""

    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    summary_path: Path | None = None
    prefix = "Nightly summary:"
    for line in reversed(lines):
        if line.startswith(prefix):
            candidate = Path(line.removeprefix(prefix).strip()).expanduser()
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            summary_path = candidate
            break
    summary = (
        _load_state(summary_path)
        if summary_path and summary_path.is_file()
        else {}
    )
    summary_status = str(summary.get("status") or "").strip().casefold()
    if subprocess_returncode != 0:
        return subprocess_returncode, "failed_or_incomplete", summary_path
    if not summary:
        return 1, "failed_missing_summary", summary_path
    if summary_status != "completed":
        return 1, "failed_or_incomplete", summary_path
    return 0, "completed", summary_path


def _run_pipeline(args: argparse.Namespace) -> tuple[int, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"nightly_pipeline_{stamp}.log"
    cmd = _pipeline_command(args)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(shlex.quote(part) for part in cmd)}\n\n")
        log.write(f"TZ={DEFAULT_TIMEZONE}\n\n")
        log.flush()
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "TZ": DEFAULT_TIMEZONE},
        )
    returncode, status, summary_path = _pipeline_outcome(log_path, result.returncode)
    if returncode == 0:
        notification = "Nightly recruiting run completed successfully."
    else:
        notification = (
            f"Nightly recruiting run failed or was incomplete (exit {returncode}). "
            f"Review {log_path.name}."
        )
    _osascript(
        "display notification "
        f"{json.dumps(notification)} "
        'with title "ResumeGenerator"'
    )
    if summary_path:
        print(f"Nightly scheduler outcome: {status}; summary: {summary_path}")
    else:
        print(f"Nightly scheduler outcome: {status}; summary missing")
    return returncode, log_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unattended scheduler for the local nightly pipeline."
    )
    parser.add_argument(
        "--scheduled-time", default="01:00", help="Local HH:MM time to run each day."
    )
    parser.add_argument("--state-path", default=str(STATE_PATH))
    parser.add_argument(
        "--production-slot",
        choices=PRODUCTION_SLOTS,
        default="",
        help="Select one reviewed two-slot production contract.",
    )
    parser.add_argument(
        "--timezone",
        choices=(DEFAULT_TIMEZONE,),
        default=DEFAULT_TIMEZONE,
        help="IANA timezone used for due dates and daily slot idempotency.",
    )
    parser.add_argument(
        "--discovery-state-path", default=str(DISCOVERY_STATE_PATH)
    )
    parser.add_argument(
        "--discovery-cadence-hours",
        type=float,
        default=DEFAULT_DISCOVERY_CADENCE_HOURS,
    )
    parser.add_argument("--lock-path", default=str(LOCK_PATH))
    parser.add_argument(
        "--pipeline-args", default="", help="Arguments for run_nightly_pipeline.py."
    )
    parser.add_argument("--force", action="store_true", help="Run even if not due.")
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Ask Run/Snooze/Skip before running. Off by default.",
    )
    parser.add_argument(
        "--require-production-attestation",
        action="store_true",
        help="Require clean main branches at the exact tested SHAs recorded in the release attestation.",
    )
    parser.add_argument(
        "--require-live-delivery-contract",
        action="store_true",
        help=(
            "Fail closed unless the configured unattended pipeline includes both "
            "bounded app-queue and Track 2 LinkedIn delivery gates."
        ),
    )
    parser.add_argument(
        "--require-production-slot-contract",
        action="store_true",
        help="Fail closed unless the selected slot/mode matches its reviewed contract.",
    )
    parser.add_argument(
        "--production-attestation",
        default=os.environ.get(
            "RESUMEGEN_PRODUCTION_ATTESTATION", str(DEFAULT_ATTESTATION_PATH)
        ),
    )
    parser.add_argument(
        "--production-check-only",
        action="store_true",
        default=_env_flag("RESUMEGEN_PRODUCTION_CHECK_ONLY"),
        help="Validate Desktop repo access and the production attestation, print JSON, and exit without scheduler-state changes.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print due state without running or prompting.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.production_check_only:
        try:
            result = validate_attestation(path=Path(args.production_attestation))
        except ProductionReleaseError as exc:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "check": "production_release_and_desktop_access",
                        "error": str(exc),
                    },
                    indent=2,
                )
            )
            return 78
        print(
            json.dumps(
                {
                    "status": "valid",
                    "check": "production_release_and_desktop_access",
                    **result,
                },
                indent=2,
            )
        )
        return 0
    state_path = Path(args.state_path).expanduser()
    lock_path = Path(getattr(args, "lock_path", LOCK_PATH)).expanduser()
    with _lock(lock_path):
        state = _load_state(state_path)
        is_due, reason = _due(state, args)
        production_slot = str(getattr(args, "production_slot", "") or "")
        discovery_state_path = Path(
            getattr(args, "discovery_state_path", DISCOVERY_STATE_PATH)
        ).expanduser()
        discovery_state = _load_state(discovery_state_path) if production_slot else {}
        if production_slot:
            include_discovery, discovery_reason = _discovery_due(
                discovery_state,
                now=_now(),
                cadence_hours=float(
                    getattr(
                        args,
                        "discovery_cadence_hours",
                        DEFAULT_DISCOVERY_CADENCE_HOURS,
                    )
                ),
            )
        else:
            include_discovery, discovery_reason = False, "legacy_single_slot"
        args.include_discovery = include_discovery
        if args.check_only:
            print(
                json.dumps(
                    {
                        "due": is_due,
                        "reason": reason,
                        "timezone": getattr(args, "timezone", DEFAULT_TIMEZONE),
                        "production_slot": production_slot,
                        "discovery_due": include_discovery,
                        "discovery_reason": discovery_reason,
                        "state": state,
                        "discovery_state": discovery_state,
                    },
                    indent=2,
                )
            )
            return 0
        if not is_due:
            if args.verbose:
                print(f"Not due: {reason}")
            return 0

        if getattr(args, "require_production_slot_contract", False):
            if not production_slot:
                contract_errors = ["--production-slot is required"]
            else:
                contract_errors = []
                expected_time = PRODUCTION_SLOT_TIMES[production_slot]
                if args.scheduled_time != expected_time:
                    contract_errors.append(
                        f"{production_slot} must run at {expected_time} {DEFAULT_TIMEZONE}"
                    )
                cadence_hours = float(
                    getattr(
                        args,
                        "discovery_cadence_hours",
                        DEFAULT_DISCOVERY_CADENCE_HOURS,
                    )
                )
                if cadence_hours != DEFAULT_DISCOVERY_CADENCE_HOURS:
                    contract_errors.append(
                        "production discovery cadence must be exactly 48 hours"
                    )
                try:
                    pipeline_args = _pipeline_args(args)
                except ValueError as exc:
                    contract_errors.append(str(exc))
                else:
                    contract_errors.extend(
                        validate_production_slot_args(
                            pipeline_args,
                            slot=production_slot,
                            include_discovery=include_discovery,
                        )
                    )
            if contract_errors:
                message = "; ".join(contract_errors)
                state["last_guard_failure_at"] = _now().isoformat(timespec="seconds")
                state["last_guard_failure"] = (
                    f"unsafe production slot contract: {message}"
                )
                _save_state(state_path, state)
                print(state["last_guard_failure"], file=sys.stderr)
                return 78
        elif getattr(args, "require_live_delivery_contract", False):
            try:
                pipeline_args = _pipeline_args(args)
            except ValueError as exc:
                contract_errors = [f"invalid pipeline argument quoting: {exc}"]
            else:
                contract_errors = validate_production_nightly_args(pipeline_args)
            if contract_errors:
                message = "; ".join(contract_errors)
                state["last_guard_failure_at"] = _now().isoformat(timespec="seconds")
                state["last_guard_failure"] = f"unsafe live delivery contract: {message}"
                _save_state(state_path, state)
                print(state["last_guard_failure"], file=sys.stderr)
                return 78

        if args.require_production_attestation:
            try:
                attestation = validate_attestation(
                    path=Path(args.production_attestation)
                )
            except ProductionReleaseError as exc:
                state["last_guard_failure_at"] = _now().isoformat(timespec="seconds")
                state["last_guard_failure"] = str(exc)
                _save_state(state_path, state)
                print(f"Production release check failed: {exc}", file=sys.stderr)
                return 78
            state["last_production_attestation"] = attestation

        choice = _prompt_choice(args, reason) if args.prompt else "Run Now"
        today = _today_key()
        if choice == "Skip Today":
            state["last_skip_date"] = today
            state["last_decision_at"] = _now().isoformat(timespec="seconds")
            _save_state(state_path, state)
            return 0
        if choice == "Snooze":
            default_time = (_now() + timedelta(hours=1)).strftime("%H:%M")
            snooze_until = _prompt_snooze_time(default_time)
            if snooze_until:
                state["snooze_until"] = snooze_until.isoformat(timespec="minutes")
                state["last_decision_at"] = _now().isoformat(timespec="seconds")
                _save_state(state_path, state)
            return 0

        state["snooze_until"] = ""
        state["production_slot"] = production_slot
        state["timezone"] = getattr(args, "timezone", DEFAULT_TIMEZONE)
        state["discovery_requested"] = include_discovery
        state["discovery_reason"] = discovery_reason
        state["last_decision_at"] = _now().isoformat(timespec="seconds")
        state["last_attempt_date"] = today
        state["last_attempt_started_at"] = _now().isoformat(timespec="seconds")
        _save_state(state_path, state)
        discovery_attempt_at = ""
        if include_discovery:
            discovery_attempt_at = _now().isoformat(timespec="seconds")
            discovery_state.update(
                {
                    "timezone": getattr(args, "timezone", DEFAULT_TIMEZONE),
                    "cadence_hours": float(
                        getattr(
                            args,
                            "discovery_cadence_hours",
                            DEFAULT_DISCOVERY_CADENCE_HOURS,
                        )
                    ),
                    "last_attempt_at": discovery_attempt_at,
                    "last_attempt_slot": production_slot,
                    "last_attempt_status": "running",
                }
            )
            _save_state(discovery_state_path, discovery_state)
        return_code, log_path = _run_pipeline(args)
        return_code, run_status, summary_path = _pipeline_outcome(
            log_path, return_code
        )
        state = _load_state(state_path)
        state["last_run_date"] = today
        state["last_run_completed_at"] = _now().isoformat(timespec="seconds")
        state["last_run_exit_code"] = return_code
        state["last_run_status"] = run_status
        state["last_run_was_actual_pipeline"] = True
        state["last_run_log"] = str(log_path)
        state["last_run_summary"] = str(summary_path or "")
        _save_state(state_path, state)
        if include_discovery:
            discovery_state = _load_state(discovery_state_path)
            if discovery_state.get("last_attempt_at") == discovery_attempt_at:
                discovery_state["last_attempt_status"] = run_status
                discovery_state["last_attempt_exit_code"] = return_code
                discovery_state["last_attempt_completed_at"] = _now().isoformat(
                    timespec="seconds"
                )
                discovery_state["last_attempt_summary"] = str(summary_path or "")
                _save_state(discovery_state_path, discovery_state)
        return return_code


if __name__ == "__main__":
    raise SystemExit(main())
