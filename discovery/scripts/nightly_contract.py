#!/usr/bin/env python3
"""Single source of truth for the unattended production nightly contract."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence


PRODUCTION_NIGHTLY_ARGS: tuple[str, ...] = (
    "--cycle-config",
    "offcycle_light",
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
    "--track-2-send-linkedin",
    "--track-2-total-actions",
    "auto",
    "--track-2-companies",
    "auto",
    "--track-2-linkedin-invites",
    "auto",
    "--track-2-linkedin-followups",
    "auto",
    "--track-2-company-mapping",
    "auto",
    "--track-2-email-research",
    "auto",
    "--track-2-context-enrichment",
    "8",
    "--track-2-email-drafts",
    "auto",
)

REQUIRED_LIVE_FLAGS = frozenset(
    {
        "--generate",
        "--prepare-outreach",
        "--execute-sends",
        "--execute-track-2-daily-plan",
        "--track-2-send-linkedin",
    }
)
REQUIRED_BOUNDED_OPTIONS = {
    "--cycle-config": "offcycle_light",
    "--target-sends": "auto",
    "--per-company-send-limit": "5",
    "--send-min-score": "20",
    "--track-2-total-actions": "auto",
    "--track-2-companies": "auto",
    "--track-2-linkedin-invites": "auto",
    "--track-2-linkedin-followups": "auto",
    "--track-2-company-mapping": "auto",
    "--track-2-email-research": "auto",
    "--track-2-context-enrichment": "8",
    "--track-2-email-drafts": "auto",
}


def production_nightly_args_text() -> str:
    return shlex.join(PRODUCTION_NIGHTLY_ARGS)


def _option_value(argv: Sequence[str], option: str) -> str | None:
    for index, token in enumerate(argv):
        if token == option:
            return argv[index + 1] if index + 1 < len(argv) else None
        prefix = f"{option}="
        if token.startswith(prefix):
            return token[len(prefix) :]
    return None


def validate_production_nightly_args(argv: Sequence[str]) -> list[str]:
    """Return contract violations for an unattended production install."""

    tokens = list(argv)
    present = set(tokens)
    errors = [
        f"missing required live-delivery flag {flag}"
        for flag in sorted(REQUIRED_LIVE_FLAGS - present)
    ]
    for option, expected in REQUIRED_BOUNDED_OPTIONS.items():
        actual = _option_value(tokens, option)
        if actual != expected:
            errors.append(f"{option} must be {expected}, got {actual or 'missing'}")
    if "--execute-linkedin-followups" in present:
        errors.append(
            "--execute-linkedin-followups is forbidden: Track 2 is the sole "
            "scheduled follow-up owner"
        )
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["print"]:
        print(production_nightly_args_text())
        return 0
    if len(args) == 2 and args[0] == "validate":
        try:
            candidate = shlex.split(args[1])
        except ValueError as exc:
            print(f"Invalid RESUMEGEN_NIGHTLY_ARGS: {exc}", file=sys.stderr)
            return 2
        errors = validate_production_nightly_args(candidate)
        if errors:
            print("Unsafe unattended nightly contract:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 2
        return 0
    print("Usage: nightly_contract.py print | validate '<pipeline args>'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
