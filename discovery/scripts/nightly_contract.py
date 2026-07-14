#!/usr/bin/env python3
"""Single source of truth for the unattended two-slot production contract."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence


EVENING_DELIVERY_SLOT = "evening_delivery"
OVERNIGHT_MAINTENANCE_SLOT = "overnight_maintenance"
PRODUCTION_SLOTS = (EVENING_DELIVERY_SLOT, OVERNIGHT_MAINTENANCE_SLOT)
PRODUCTION_SLOT_TIMES = {
    EVENING_DELIVERY_SLOT: "20:00",
    OVERNIGHT_MAINTENANCE_SLOT: "01:00",
}

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


def production_nightly_args_text() -> str:
    return shlex.join(PRODUCTION_NIGHTLY_ARGS)


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
    """Validate the backwards-compatible discovery-enabled evening vector."""

    return validate_production_slot_args(
        argv,
        slot=EVENING_DELIVERY_SLOT,
        include_discovery=True,
    )


def _parse_candidate(value: str) -> tuple[list[str] | None, str | None]:
    try:
        return shlex.split(value), None
    except ValueError as exc:
        return None, f"Invalid pipeline arguments: {exc}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["print"]:
        print(production_nightly_args_text())
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
