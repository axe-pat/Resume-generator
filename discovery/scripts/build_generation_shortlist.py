#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
CURRENT_APPLY_QUEUE_DIR = ROOT / "apps" / "Apply queues" / "current_apply_queue"
CURRENT_APPLY_QUEUE_JSON = CURRENT_APPLY_QUEUE_DIR / "priority_order.json"
CURRENT_SHORTLIST_JSON = CURRENT_APPLY_QUEUE_DIR / "generation_shortlist.json"
CURRENT_SHORTLIST_MD = CURRENT_APPLY_QUEUE_DIR / "generation_shortlist.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


DEFAULT_NON_HANDSHAKE_MIN = 7.0
DEFAULT_HANDSHAKE_INTERNAL_MIN = 6.0
DEFAULT_HANDSHAKE_EXTERNAL_MIN = 6.5
DEFAULT_HANDSHAKE_UNKNOWN_MIN = 6.5


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _note_value(notes: str, key: str) -> str:
    prefix = f"{key}="
    for token in str(notes or "").split():
        if token.startswith(prefix):
            return token[len(prefix) :].strip().lower()
    return ""


def _has_resume_artifact(folder_path: str) -> bool:
    if not folder_path:
        return False
    path = Path(folder_path)
    if not path.exists() or not path.is_dir():
        return False
    return bool(list(path.glob("resume_*.txt")) or list(path.glob("resume_*.docx")))


def _generation_floor(row: dict[str, Any], args: argparse.Namespace) -> tuple[float, str]:
    source = _clean(row.get("source")).lower()
    notes = _clean(row.get("notes"))
    if source == "handshake_jobs_v1":
        flow = _note_value(notes, "handshake_apply_flow") or "unknown"
        if flow == "internal":
            return args.handshake_internal_min, "handshake_internal"
        if flow == "external":
            return args.handshake_external_min, "handshake_external"
        return args.handshake_unknown_min, "handshake_unknown"
    return args.non_handshake_min, "non_handshake"


def _load_tracker_rows() -> dict[str, dict[str, Any]]:
    df = jobs.load_jobs().fillna("")
    return {str(row.get("id") or "").strip(): row.to_dict() for _, row in df.iterrows()}


def _load_queue_entries(queue_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"Queue file must contain a JSON list: {queue_path}")
    return [entry for entry in payload if isinstance(entry, dict)]


def build_shortlist(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queue_entries = _load_queue_entries(Path(args.queue_path))
    tracker_by_id = _load_tracker_rows()
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for entry in queue_entries:
        row_id = _clean(entry.get("id"))
        tracker_row = tracker_by_id.get(row_id, {})
        combined = {**entry, **tracker_row}
        fit_score = _safe_float(combined.get("fit_score"))
        floor, policy = _generation_floor(combined, args)
        status = _clean(combined.get("status")).lower()
        folder_path = _clean(entry.get("folder_path") or combined.get("folder_path"))
        reason = ""

        if status in {"generated", "applied", "closed", "parked", "rejected", "skip", "skipped"}:
            reason = f"status_{status or 'unknown'}"
        elif _has_resume_artifact(folder_path) and not args.include_existing:
            reason = "resume_already_exists"
        elif fit_score < floor:
            reason = f"below_generation_floor_{floor:g}"

        out_entry = {
            **entry,
            "source": _clean(combined.get("source")),
            "notes": _clean(combined.get("notes")),
            "generation_policy": policy,
            "generation_min_score": floor,
            "generation_reason": reason or "selected",
        }
        if reason:
            skipped.append(out_entry)
            continue
        selected.append(out_entry)
        if len(selected) >= args.cap:
            break

    return selected, skipped


def _write_markdown(path: Path, selected: list[dict[str, Any]], skipped: list[dict[str, Any]], args: argparse.Namespace) -> None:
    lines = [
        "# Nightly Generation Shortlist",
        "",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        f"Cap: {args.cap}",
        "",
        "## Policy",
        "",
        f"- Non-Handshake: `fit_score >= {args.non_handshake_min:g}`",
        f"- Handshake internal apply: `fit_score >= {args.handshake_internal_min:g}`",
        f"- Handshake external apply: `fit_score >= {args.handshake_external_min:g}`",
        f"- Handshake unknown flow: `fit_score >= {args.handshake_unknown_min:g}`",
        "",
        f"## Selected ({len(selected)})",
        "",
    ]
    if selected:
        for idx, item in enumerate(selected, start=1):
            lines.append(
                f"{idx}. {item.get('company')} | {item.get('role_title')} | "
                f"score={item.get('fit_score')} | policy={item.get('generation_policy')} | "
                f"min={item.get('generation_min_score')}"
            )
    else:
        lines.append("_No jobs selected._")

    lines.extend(["", f"## Skipped Preview ({min(len(skipped), args.skipped_preview)}/{len(skipped)})", ""])
    for item in skipped[: args.skipped_preview]:
        lines.append(
            f"- {item.get('company')} | {item.get('role_title')} | "
            f"score={item.get('fit_score')} | reason={item.get('generation_reason')}"
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_outputs(selected: list[dict[str, Any]], skipped: list[dict[str, Any]], args: argparse.Namespace) -> tuple[Path, Path]:
    SOURCE_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = SOURCE_VALIDATION_DIR / f"{stamp}-generation-shortlist.json"
    md_path = SOURCE_VALIDATION_DIR / f"{stamp}-generation-shortlist.md"

    json_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    _write_markdown(md_path, selected, skipped, args)

    if args.write_current:
        CURRENT_APPLY_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        CURRENT_SHORTLIST_JSON.write_text(json.dumps(selected, indent=2), encoding="utf-8")
        _write_markdown(CURRENT_SHORTLIST_MD, selected, skipped, args)

    metadata_path = json_path.with_name(json_path.name.replace(".json", "-metadata.json"))
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "queue_path": str(Path(args.queue_path)),
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "cap": args.cap,
        "policy": {
            "non_handshake_min": args.non_handshake_min,
            "handshake_internal_min": args.handshake_internal_min,
            "handshake_external_min": args.handshake_external_min,
            "handshake_unknown_min": args.handshake_unknown_min,
        },
        "shortlist_json": str(json_path),
        "shortlist_markdown": str(md_path),
        "current_shortlist_json": str(CURRENT_SHORTLIST_JSON) if args.write_current else "",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cost-gated generation shortlist from current_apply_queue.")
    parser.add_argument("--queue-path", default=str(CURRENT_APPLY_QUEUE_JSON))
    parser.add_argument("--cap", type=int, default=10)
    parser.add_argument("--non-handshake-min", type=float, default=DEFAULT_NON_HANDSHAKE_MIN)
    parser.add_argument("--handshake-internal-min", type=float, default=DEFAULT_HANDSHAKE_INTERNAL_MIN)
    parser.add_argument("--handshake-external-min", type=float, default=DEFAULT_HANDSHAKE_EXTERNAL_MIN)
    parser.add_argument("--handshake-unknown-min", type=float, default=DEFAULT_HANDSHAKE_UNKNOWN_MIN)
    parser.add_argument("--include-existing", action="store_true", help="Include jobs that already have resume artifacts.")
    parser.add_argument("--write-current", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skipped-preview", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected, skipped = build_shortlist(args)
    json_path, md_path = write_outputs(selected, skipped, args)
    print(f"Selected for generation: {len(selected)}")
    for idx, item in enumerate(selected, start=1):
        print(
            f"  {idx}. {item.get('company')} | {item.get('role_title')} | "
            f"score={item.get('fit_score')} | min={item.get('generation_min_score')}"
        )
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    if args.write_current:
        print(f"Current queue shortlist: {CURRENT_SHORTLIST_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
