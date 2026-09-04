"""Report exhaustive ownership coverage for documented resume-variant rules.

This is an inert audit command.  It neither edits prompts nor changes live
generation.  A zero exit code means every cataloged rule has exactly one owner
and every structured-critic rule is assigned to one required review dimension.
It does not pretend that known missing or conflicted rules are already solved.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Sequence

from shared.variant_rule_catalog import (
    RULE_CATALOG,
    STRUCTURED_CHALLENGER_DIMENSIONS,
    CoverageStatus,
    validate_rule_catalog,
)


def coverage_payload() -> dict[str, object]:
    errors = validate_rule_catalog()
    owner_counts = Counter(rule.owner.value for rule in RULE_CATALOG)
    status_counts = Counter(rule.status.value for rule in RULE_CATALOG)
    unresolved = [
        {
            "rule_id": rule.rule_id,
            "source": rule.source,
            "name": rule.name,
            "owner": rule.owner.value,
            "status": rule.status.value,
            "implementation": rule.implementation,
            "note": rule.note,
        }
        for rule in RULE_CATALOG
        if rule.status in {CoverageStatus.MISSING, CoverageStatus.CONFLICT}
    ]
    return {
        "cataloged_rules": len(RULE_CATALOG),
        "mapped_rules": len(RULE_CATALOG) if not errors else 0,
        "structured_review_dimensions": sorted(STRUCTURED_CHALLENGER_DIMENSIONS),
        "owner_counts": dict(sorted(owner_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "unresolved_rules": unresolved,
        "catalog_errors": errors,
        "coverage_gate_passed": not errors,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = coverage_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"Rule ownership coverage: {payload['mapped_rules']}/"
            f"{payload['cataloged_rules']} mapped"
        )
        print(f"Owner counts: {payload['owner_counts']}")
        print(f"Status counts: {payload['status_counts']}")
        print(
            "Structured review dimensions: "
            + ", ".join(payload["structured_review_dimensions"])
        )
        unresolved = payload["unresolved_rules"]
        if unresolved:
            print("Known gaps/conflicts (visible, not waived):")
            for rule in unresolved:
                print(
                    f"- {rule['rule_id']} [{rule['status']}] "
                    f"{rule['name']}: {rule['note']}"
                )
        for error in payload["catalog_errors"]:
            print(f"ERROR: {error}")
    return 0 if payload["coverage_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
