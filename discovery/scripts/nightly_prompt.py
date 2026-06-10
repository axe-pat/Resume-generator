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

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "venv" / "bin" / "python"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "ResumeGenerator"
STATE_PATH = APP_SUPPORT / "nightly_scheduler_state.json"
LOCK_PATH = APP_SUPPORT / "nightly_scheduler.lock"
LOG_DIR = ROOT / "logs"


def _now() -> datetime:
    return datetime.now()


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
    return today.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _due(state: dict, args: argparse.Namespace) -> tuple[bool, str]:
    if args.force:
        return True, "forced"
    now = _now()
    today = _today_key(now)
    if state.get("last_run_date") == today:
        return False, "already_ran_today"
    if state.get("last_skip_date") == today:
        return False, "skipped_today"
    snooze_until = _parse_iso(str(state.get("snooze_until") or ""))
    if snooze_until and now < snooze_until:
        return False, f"snoozed_until_{snooze_until.isoformat(timespec='minutes')}"
    if now >= _scheduled_at(now, args.scheduled_time):
        return True, "scheduled_or_catchup"
    return False, "before_scheduled_time"


def _osascript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], text=True, capture_output=True)


def _prompt_choice(args: argparse.Namespace, reason: str) -> str:
    message = (
        "ResumeGenerator nightly pipeline is due.\\n\\n"
        f"Reason: {reason}\\n"
        f"Scheduled time: {args.scheduled_time}\\n"
        f"Pipeline args: {args.pipeline_args or '(default)'}"
    )
    script = (
        f'display dialog {json.dumps(message)} '
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
        f'default answer {json.dumps(default_time)} '
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
        _osascript(f'display alert {json.dumps(str(exc))}')
        return None
    now = _now()
    target = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _pipeline_command(args: argparse.Namespace) -> list[str]:
    extra_args = shlex.split(args.pipeline_args or os.environ.get("RESUMEGEN_NIGHTLY_ARGS", "--generate"))
    return [str(PYTHON), "discovery/scripts/run_nightly_pipeline.py", *extra_args]


def _run_pipeline(args: argparse.Namespace) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"nightly_pipeline_{stamp}.log"
    cmd = _pipeline_command(args)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(shlex.quote(part) for part in cmd)}\n\n")
        log.flush()
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    _osascript(
        'display notification '
        f'{json.dumps(f"Nightly pipeline finished with exit code {result.returncode}.")} '
        'with title "ResumeGenerator"'
    )
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prompt/snooze gate for the local nightly pipeline.")
    parser.add_argument("--scheduled-time", default="20:00", help="Local HH:MM time to prompt each day.")
    parser.add_argument("--state-path", default=str(STATE_PATH))
    parser.add_argument("--pipeline-args", default="", help="Arguments for run_nightly_pipeline.py.")
    parser.add_argument("--force", action="store_true", help="Prompt even if not due.")
    parser.add_argument("--check-only", action="store_true", help="Print due state without prompting.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_path).expanduser()
    with _lock(LOCK_PATH):
        state = _load_state(state_path)
        is_due, reason = _due(state, args)
        if args.check_only:
            print(json.dumps({"due": is_due, "reason": reason, "state": state}, indent=2))
            return 0
        if not is_due:
            if args.verbose:
                print(f"Not due: {reason}")
            return 0

        choice = _prompt_choice(args, reason)
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
        state["last_decision_at"] = _now().isoformat(timespec="seconds")
        state["last_run_date"] = today
        _save_state(state_path, state)
        return_code = _run_pipeline(args)
        state = _load_state(state_path)
        state["last_run_completed_at"] = _now().isoformat(timespec="seconds")
        state["last_run_exit_code"] = return_code
        _save_state(state_path, state)
        return return_code


if __name__ == "__main__":
    raise SystemExit(main())
