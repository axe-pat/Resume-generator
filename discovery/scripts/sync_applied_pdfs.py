#!/usr/bin/env python3
"""Deprecated, report-only scanner for legacy Resume.pdf markers.

PDF presence is not evidence of submission. This command intentionally never
moves files or writes jobs.xlsx; reviewed outcomes must use
transition_application.py with one numeric job ID and an exact confirmation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"


def _find_resume_pdf_dirs() -> list[Path]:
    dirs: list[Path] = []
    for pdf_path in APPS_DIR.rglob("Resume.pdf"):
        if pdf_path.is_symlink() or not pdf_path.is_file():
            continue
        if "archive" in pdf_path.parts:
            continue
        if ".current_apply_queue_prev" in pdf_path.parts:
            continue
        if "forgotten_queue" in pdf_path.parts:
            continue
        dirs.append(pdf_path.parent.resolve())
    return sorted(set(dirs))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit one JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = _find_resume_pdf_dirs()
    payload = {
        "status": "skipped_deprecated",
        "mutated": False,
        "candidate_count": len(candidates),
        "reason": (
            "Resume.pdf presence is not proof of submission; use the reviewed "
            "archive-first lifecycle command"
        ),
        "candidate_paths": [
            str(path.relative_to(ROOT.resolve()))
            for path in candidates
            if path == ROOT.resolve() or ROOT.resolve() in path.parents
        ],
    }
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("Applied-PDF sync: skipped_deprecated (no mutation)")
        print(f"Legacy Resume.pdf candidates requiring review: {len(candidates)}")
        print(
            "Use discovery/scripts/transition_application.py with one reviewed "
            "numeric job ID."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
