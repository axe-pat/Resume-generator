#!/usr/bin/env python3
"""Record and validate the exact tested commits allowed to run nightly."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
OUTREACH_ROOT = ROOT.parent / "Outreach"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "ResumeGenerator"
DEFAULT_ATTESTATION_PATH = APP_SUPPORT / "production_release.json"

RESUME_CODE_PATHS = (
    "discovery/scripts",
    "discovery/auto",
    "apply_assist",
    "jobs.py",
    "pyproject.toml",
    "requirements.txt",
)
OUTREACH_CODE_PATHS = (
    "main.py",
    "src",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
)


class ProductionReleaseError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}"
        )
        raise ProductionReleaseError(f"git {' '.join(args)} failed in {repo}: {detail}")
    return result.stdout.strip()


def _repo_release_state(repo: Path, code_paths: tuple[str, ...]) -> dict[str, object]:
    if not repo.is_dir():
        raise ProductionReleaseError(f"repository is missing: {repo}")
    branch = _git(repo, "branch", "--show-current")
    head = _git(repo, "rev-parse", "HEAD")
    dirty_output = _git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *code_paths,
    )
    return {
        "root": str(repo.resolve()),
        "branch": branch,
        "head": head,
        "code_paths": list(code_paths),
        "dirty_code": [line for line in dirty_output.splitlines() if line.strip()],
    }


def _require_releasable(name: str, state: dict[str, object]) -> None:
    if state.get("branch") != "main":
        raise ProductionReleaseError(
            f"{name} must be on main for production; found {state.get('branch') or 'detached HEAD'}"
        )
    dirty = list(state.get("dirty_code") or [])
    if dirty:
        raise ProductionReleaseError(
            f"{name} production code paths are dirty: {'; '.join(str(item) for item in dirty)}"
        )


def record_attestation(
    *,
    path: Path,
    resume_root: Path = ROOT,
    outreach_root: Path = OUTREACH_ROOT,
    test_evidence: list[str],
) -> dict[str, object]:
    if not test_evidence:
        raise ProductionReleaseError("at least one --test-evidence entry is required")
    resume = _repo_release_state(resume_root, RESUME_CODE_PATHS)
    outreach = _repo_release_state(outreach_root, OUTREACH_CODE_PATHS)
    _require_releasable("ResumeGenerator", resume)
    _require_releasable("Outreach", outreach)
    payload: dict[str, object] = {
        "version": 1,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tests": {
            "status": "passed",
            "evidence": test_evidence,
        },
        "repositories": {
            "resume_generator": resume,
            "outreach": outreach,
        },
    }
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
    return payload


def validate_attestation(
    *,
    path: Path,
    resume_root: Path = ROOT,
    outreach_root: Path = OUTREACH_ROOT,
) -> dict[str, object]:
    path = path.expanduser()
    if not path.is_file():
        raise ProductionReleaseError(
            f"production attestation is missing: {path}; record one after both repos pass release tests"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionReleaseError(
            f"production attestation is unreadable: {path}: {exc}"
        ) from exc
    if payload.get("version") != 1:
        raise ProductionReleaseError("production attestation version is not supported")
    tests = payload.get("tests") if isinstance(payload.get("tests"), dict) else {}
    if tests.get("status") != "passed" or not list(tests.get("evidence") or []):
        raise ProductionReleaseError(
            "production attestation has no passed test evidence"
        )

    recorded_repositories = (
        payload.get("repositories")
        if isinstance(payload.get("repositories"), dict)
        else {}
    )
    current = {
        "resume_generator": _repo_release_state(resume_root, RESUME_CODE_PATHS),
        "outreach": _repo_release_state(outreach_root, OUTREACH_CODE_PATHS),
    }
    for key, label in (
        ("resume_generator", "ResumeGenerator"),
        ("outreach", "Outreach"),
    ):
        state = current[key]
        _require_releasable(label, state)
        recorded = (
            recorded_repositories.get(key)
            if isinstance(recorded_repositories.get(key), dict)
            else {}
        )
        expected_head = str(recorded.get("head") or "")
        if not expected_head:
            raise ProductionReleaseError(
                f"{label} tested SHA is missing from attestation"
            )
        if state.get("head") != expected_head:
            raise ProductionReleaseError(
                f"{label} HEAD {state.get('head')} does not match tested SHA {expected_head}"
            )
    return {
        "status": "valid",
        "attestation": str(path),
        "recorded_at": payload.get("recorded_at"),
        "repositories": current,
        "test_evidence": list(tests.get("evidence") or []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--attestation",
        default=os.environ.get(
            "RESUMEGEN_PRODUCTION_ATTESTATION", str(DEFAULT_ATTESTATION_PATH)
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser(
        "record", help="Record the clean main SHAs after release tests pass."
    )
    record.add_argument(
        "--test-evidence",
        action="append",
        default=[],
        help="Passed test command/result; repeat for each repo or suite.",
    )
    subparsers.add_parser(
        "check", help="Validate current clean main SHAs against the attestation."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "record":
            result = record_attestation(
                path=Path(args.attestation),
                test_evidence=list(args.test_evidence),
            )
        else:
            result = validate_attestation(path=Path(args.attestation))
    except ProductionReleaseError as exc:
        print(f"Production release check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
