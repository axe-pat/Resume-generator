#!/usr/bin/env python3
"""Single source of truth for the unattended two-slot production contract."""

from __future__ import annotations

import json
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path


EVENING_DELIVERY_SLOT = "evening_delivery"
OVERNIGHT_MAINTENANCE_SLOT = "overnight_maintenance"
PRODUCTION_SLOTS = (EVENING_DELIVERY_SLOT, OVERNIGHT_MAINTENANCE_SLOT)
PRODUCTION_SLOT_TIMES = {
    EVENING_DELIVERY_SLOT: "20:00",
    OVERNIGHT_MAINTENANCE_SLOT: "01:00",
}

# Operator-triggered runs include the discovery lane once every N runs; the
# other runs are delivery-only maintenance. The counter lives in the shared
# discovery cadence state and is updated by the scheduler at run time.
DISCOVERY_RUN_INTERVAL = 3
DISCOVERY_CADENCE_STATE_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "ResumeGenerator"
    / "nightly_discovery_cadence.json"
)

_DISCOVERY_ARGS: tuple[str, ...] = (
    "--generate",
    "--prepare-outreach",
    "--execute-sends",
    "--target-sends",
    "auto",
    "--per-company-send-limit",
    "5",
    "--send-min-score",
    "20",
    "--linkedin-discovery-timeout",
    "1800",
)

_MAINTENANCE_ONLY_ARGS: tuple[str, ...] = (
    "--skip-daily-engine",
    "--skip-shared-discovery",
)

_COMMON_TRACK_2_ARGS: tuple[str, ...] = (
    "--cycle-config",
    "offcycle_light",
    "--outreach-resolve-limit",
    "20",
    "--outreach-enrich-limit",
    "20",
    "--outreach-campaign-limit",
    "30",
    "--outreach-timeout-seconds",
    "4",
    "--outreach-max-search-results",
    "3",
    "--execute-track-2-daily-plan",
    "--track-2-total-actions",
    "auto",
    "--track-2-companies",
    "auto",
    "--track-2-company-mapping",
    "auto",
    "--track-2-email-research",
    "auto",
    "--track-2-context-enrichment",
    "8",
)

_EVENING_DELIVERY_ARGS: tuple[str, ...] = (
    "--track-2-send-linkedin",
    "--track-2-linkedin-invites",
    "auto",
    "--track-2-linkedin-followups",
    "auto",
    "--track-2-email-drafts",
    "auto",
)

# The 01:00 slot still runs refresh, reconciliation, account maintenance,
# mapping, research, and enrichment. Delivery and both draft-producing lanes
# are hard-zeroed so running the second slot cannot double the reviewed daily
# send caps or create a second batch of LinkedIn/email drafts.
_OVERNIGHT_MAINTENANCE_ARGS: tuple[str, ...] = (
    "--track-2-linkedin-invites",
    "0",
    "--track-2-linkedin-followups",
    "0",
    "--track-2-email-drafts",
    "0",
)


def production_slot_args(
    slot: str, *, include_discovery: bool
) -> tuple[str, ...]:
    if slot not in PRODUCTION_SLOTS:
        raise ValueError(f"Unknown production slot: {slot}")
    lane_args = _DISCOVERY_ARGS if include_discovery else _MAINTENANCE_ONLY_ARGS
    slot_args = (
        _EVENING_DELIVERY_ARGS
        if slot == EVENING_DELIVERY_SLOT
        else _OVERNIGHT_MAINTENANCE_ARGS
    )
    return (*lane_args, *_COMMON_TRACK_2_ARGS, *slot_args)


# Backwards-compatible name for callers that need the old single-vector view.
# It is the discovery-enabled evening contract, not a vector to run twice.
PRODUCTION_NIGHTLY_ARGS: tuple[str, ...] = production_slot_args(
    EVENING_DELIVERY_SLOT, include_discovery=True
)

# The delivery-only counterpart used by operator runs between discovery runs.
MAINTENANCE_NIGHTLY_ARGS: tuple[str, ...] = production_slot_args(
    EVENING_DELIVERY_SLOT, include_discovery=False
)


def discovery_due_by_run_count(
    state_path: Path | None = None,
    *,
    interval: int = DISCOVERY_RUN_INTERVAL,
) -> tuple[bool, str]:
    """Read-only 1-in-N gate for operator-triggered runs.

    The scheduler owns the counter writes; this only decides whether the next
    run should include the discovery lane. A missing or unreadable state fails
    open to discovery so a fresh install starts with a full run.
    """

    if state_path is None:
        state_path = DISCOVERY_CADENCE_STATE_PATH
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return True, "no_discovery_cadence_state"
    raw = state.get("runs_since_discovery")
    if not isinstance(raw, int) or raw < 0:
        return True, "invalid_runs_since_discovery"
    if raw >= max(interval, 1) - 1:
        return True, f"runs_since_discovery_{raw}_of_{interval}"
    return False, f"runs_since_discovery_{raw}_of_{interval}"


def production_nightly_args_text() -> str:
    return shlex.join(PRODUCTION_NIGHTLY_ARGS)


def current_operator_nightly_args() -> tuple[tuple[str, ...], bool, str]:
    """The exact evening vector the next operator-triggered run must use."""

    include_discovery, reason = discovery_due_by_run_count()
    vector = (
        PRODUCTION_NIGHTLY_ARGS if include_discovery else MAINTENANCE_NIGHTLY_ARGS
    )
    return vector, include_discovery, reason


def production_slot_args_text(slot: str, *, include_discovery: bool) -> str:
    return shlex.join(
        production_slot_args(slot, include_discovery=include_discovery)
    )


def _option_value(argv: Sequence[str], option: str) -> str | None:
    for index, token in enumerate(argv):
        if token == option:
            return argv[index + 1] if index + 1 < len(argv) else None
        prefix = f"{option}="
        if token.startswith(prefix):
            return token[len(prefix) :]
    return None


def validate_production_slot_args(
    argv: Sequence[str], *, slot: str, include_discovery: bool
) -> list[str]:
    """Return violations for one canonical slot/mode combination."""

    if slot not in PRODUCTION_SLOTS:
        return [f"unknown production slot {slot}"]
    tokens = list(argv)
    expected = list(production_slot_args(slot, include_discovery=include_discovery))
    if tokens != expected:
        present = set(tokens)
        errors: list[str] = []
        if include_discovery:
            for flag in ("--generate", "--prepare-outreach", "--execute-sends"):
                if flag not in present:
                    errors.append(f"missing required discovery flag {flag}")
            if _option_value(tokens, "--target-sends") != "auto":
                errors.append("--target-sends must be auto in a discovery run")
        if slot == EVENING_DELIVERY_SLOT:
            if "--track-2-send-linkedin" not in present:
                errors.append(
                    "evening delivery slot must include --track-2-send-linkedin"
                )
        else:
            if "--track-2-send-linkedin" in present:
                errors.append(
                    "overnight maintenance slot cannot send LinkedIn messages"
                )
            for option in (
                "--track-2-linkedin-invites",
                "--track-2-linkedin-followups",
                "--track-2-email-drafts",
            ):
                if _option_value(tokens, option) != "0":
                    errors.append(
                        f"overnight maintenance slot requires {option} 0"
                    )
        errors.append(
            "pipeline arguments must exactly match the reviewed "
            f"{slot} {'discovery' if include_discovery else 'maintenance'} contract"
        )
        return errors

    present = set(tokens)
    if include_discovery:
        for flag in ("--generate", "--prepare-outreach", "--execute-sends"):
            if flag not in present:
                return [f"missing required discovery flag {flag}"]
        if _option_value(tokens, "--target-sends") != "auto":
            return ["--target-sends must be auto in a discovery run"]
        if "--skip-daily-engine" in present or "--skip-shared-discovery" in present:
            return ["discovery mode cannot skip the daily/shared discovery lanes"]
    else:
        for flag in ("--skip-daily-engine", "--skip-shared-discovery"):
            if flag not in present:
                return [f"maintenance mode must include {flag}"]
        for flag in ("--generate", "--prepare-outreach", "--execute-sends"):
            if flag in present:
                return [f"maintenance mode cannot include {flag}"]

    if slot == EVENING_DELIVERY_SLOT:
        if "--track-2-send-linkedin" not in present:
            return ["evening delivery slot must include --track-2-send-linkedin"]
    else:
        if "--track-2-send-linkedin" in present:
            return ["overnight maintenance slot cannot send LinkedIn messages"]
        for option in (
            "--track-2-linkedin-invites",
            "--track-2-linkedin-followups",
            "--track-2-email-drafts",
        ):
            if _option_value(tokens, option) != "0":
                return [f"overnight maintenance slot requires {option} 0"]
    if "--execute-linkedin-followups" in present:
        return [
            "--execute-linkedin-followups is forbidden: Track 2 is the sole "
            "scheduled follow-up owner"
        ]
    return []


def validate_production_nightly_args(argv: Sequence[str]) -> list[str]:
    """Validate an operator-run evening vector (discovery or maintenance).

    Both reviewed shapes deliver: discovery adds the Daily Engine lane once
    per DISCOVERY_RUN_INTERVAL runs, maintenance skips it explicitly. Any
    other vector is rejected with the discovery-shape violations.
    """

    tokens = list(argv)
    discovery_errors = validate_production_slot_args(
        tokens,
        slot=EVENING_DELIVERY_SLOT,
        include_discovery=True,
    )
    if not discovery_errors:
        return []
    maintenance_errors = validate_production_slot_args(
        tokens,
        slot=EVENING_DELIVERY_SLOT,
        include_discovery=False,
    )
    if not maintenance_errors:
        return []
    return discovery_errors


def _parse_candidate(value: str) -> tuple[list[str] | None, str | None]:
    try:
        return shlex.split(value), None
    except ValueError as exc:
        return None, f"Invalid pipeline arguments: {exc}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["print"]:
        vector, _, _ = current_operator_nightly_args()
        print(shlex.join(vector))
        return 0
    if args == ["print-cadence"]:
        include_discovery, reason = discovery_due_by_run_count()
        print(
            json.dumps(
                {
                    "include_discovery": include_discovery,
                    "reason": reason,
                    "interval_runs": DISCOVERY_RUN_INTERVAL,
                    "state_path": str(DISCOVERY_CADENCE_STATE_PATH),
                }
            )
        )
        return 0
    if len(args) == 3 and args[0] == "print-slot":
        slot, mode = args[1:]
        if mode not in {"discovery", "maintenance"}:
            print("Mode must be discovery or maintenance", file=sys.stderr)
            return 2
        try:
            print(
                production_slot_args_text(
                    slot, include_discovery=mode == "discovery"
                )
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    if len(args) == 2 and args[0] == "validate":
        candidate, parse_error = _parse_candidate(args[1])
        errors = (
            [parse_error]
            if parse_error
            else validate_production_nightly_args(candidate or [])
        )
    elif len(args) == 4 and args[0] == "validate-slot":
        slot, mode, raw_candidate = args[1:]
        if mode not in {"discovery", "maintenance"}:
            errors = ["mode must be discovery or maintenance"]
        else:
            candidate, parse_error = _parse_candidate(raw_candidate)
            errors = (
                [parse_error]
                if parse_error
                else validate_production_slot_args(
                    candidate or [],
                    slot=slot,
                    include_discovery=mode == "discovery",
                )
            )
    else:
        print(
            "Usage: nightly_contract.py print | print-slot <slot> "
            "<discovery|maintenance> | validate '<args>' | validate-slot "
            "<slot> <discovery|maintenance> '<args>'",
            file=sys.stderr,
        )
        return 2
    if errors:
        print("Unsafe unattended nightly contract:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
