#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "apps" / "Apply queues" / "current_apply_queue" / "priority_order.json"
DEFAULT_ANSWER_BANK = ROOT / "apply_assist" / "profile_answers.local.json"
TASKS_DIR = ROOT / "apply_assist" / "tasks"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _slug(value: str, max_len: int = 72) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return cleaned[:max_len].strip("-") or "task"


def _parse_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Queue JSON not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list in queue JSON: {path}")
    return payload


def _select_queue_item(queue: list[dict[str, Any]], *, rank: int | None, job_id: str | None) -> dict[str, Any]:
    if job_id:
        for item in queue:
            if _clean(item.get("id")) == str(job_id):
                return item
        raise ValueError(f"No queue item found with id={job_id}")
    if rank is None:
        rank = 1
    if rank < 1 or rank > len(queue):
        raise ValueError(f"Rank {rank} is outside queue length {len(queue)}")
    return queue[rank - 1]


def _infer_source(url: str) -> str:
    text = url.lower()
    if "wellfound.com" in text or "angel.co" in text:
        return "wellfound"
    if "joinhandshake.com" in text or "handshake.com" in text:
        return "handshake"
    if "greenhouse.io" in text:
        return "greenhouse"
    if "lever.co" in text:
        return "lever"
    if "myworkdayjobs.com" in text or "workday" in text:
        return "workday"
    if "linkedin.com" in text:
        return "linkedin"
    return "generic"


def _guess_resume_strategy(source: str, fit_score: float | None, local_resume_path: Path | None) -> str:
    if source == "wellfound":
        return "profile_existing"
    if local_resume_path is not None:
        return "tailored"
    if fit_score is not None and fit_score >= 8.0:
        return "tailored"
    if fit_score is not None and fit_score >= 6.5:
        return "role_family"
    return "default"


def _latest_file(folder: Path, patterns: tuple[str, ...]) -> Path | None:
    if not folder.is_dir():
        return None
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(folder.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_note_text(note_text: str, note_path: Path | None) -> tuple[str, str]:
    if note_text:
        return note_text.strip(), ""
    if note_path:
        return note_path.read_text(encoding="utf-8").strip(), str(note_path)
    return "", ""


def _build_task(args: argparse.Namespace) -> dict[str, Any]:
    queue = _load_queue(args.queue_json)
    item = _select_queue_item(queue, rank=args.rank, job_id=args.job_id)

    company = _clean(item.get("company"))
    role_title = _clean(item.get("role_title"))
    url = _clean(args.url_override or item.get("url"))
    source = _clean(args.source) or _infer_source(url)
    fit_score = _parse_float(item.get("fit_score"))
    folder_path = Path(_clean(item.get("folder_path"))) if _clean(item.get("folder_path")) else None

    local_resume = Path(args.resume_local_path).expanduser().resolve() if args.resume_local_path else None
    if local_resume is None and folder_path is not None:
        local_resume = _latest_file(folder_path, ("resume_*.pdf", "resume_*.docx"))

    note_text, note_file = _read_note_text(args.note_text, args.note_path)
    resume_strategy = args.resume_strategy or _guess_resume_strategy(source, fit_score, local_resume)
    resume_required_for_upload = source not in {"wellfound"} and resume_strategy != "profile_existing"

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = f"{stamp}-{_clean(item.get('id')) or 'manual'}-{_slug(company)}-{_slug(role_title, 36)}"

    return {
        "schema_version": "apply_assist_task_v0",
        "task_id": task_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "company": company,
        "role_title": role_title,
        "application_url": url,
        "fit_score": item.get("fit_score", ""),
        "resume": {
            "strategy": resume_strategy,
            "local_path": str(local_resume) if local_resume else "",
            "file_url": _clean(args.resume_file_url),
            "display_name": _clean(args.resume_display_name) or (local_resume.name if local_resume else "resume.pdf"),
            "mime_type": _clean(args.resume_mime_type) or _guess_mime_type(local_resume),
            "required_for_upload": resume_required_for_upload,
        },
        "note": {
            "text": note_text,
            "path": note_file,
            "required": source == "wellfound",
        },
        "answers_profile_path": str(args.answers_profile),
        "screening_answers": {},
        "guardrails": {
            "stop_before_submit": True,
            "verify_company_and_role": True,
            "do_not_invent_answers": True,
            "stop_on_unanswered_required_question": True,
            "stop_on_auth_captcha_or_payment": True,
        },
        "metadata": {
            "queue_rank": item.get("priority_rank", args.rank or ""),
            "queue_job_id": item.get("id", ""),
            "queue_status": item.get("status", ""),
            "folder_path": str(folder_path) if folder_path else "",
            "source_queue": str(args.queue_json),
        },
    }


def _guess_mime_type(path: Path | None) -> str:
    if path is None:
        return "application/pdf"
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an rtrvr apply-assist task packet.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--rank", type=int, default=1, help="1-based priority rank from current_apply_queue.")
    selector.add_argument("--job-id", default="", help="Queue job id from priority_order.json.")
    parser.add_argument("--queue-json", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--source", default="", help="Override source, e.g. wellfound, handshake, greenhouse.")
    parser.add_argument("--url-override", default="", help="Use a direct apply URL instead of the queue URL.")
    parser.add_argument("--resume-local-path", default="", help="Local resume path for review/reference.")
    parser.add_argument("--resume-file-url", default="", help="Public/fetchable resume URL for rtrvr file upload.")
    parser.add_argument("--resume-display-name", default="")
    parser.add_argument("--resume-mime-type", default="")
    parser.add_argument("--resume-strategy", choices=["tailored", "role_family", "default", "profile_existing"], default="")
    parser.add_argument("--note-text", default="", help="Inline note text, useful for Wellfound.")
    parser.add_argument("--note-path", type=Path, default=None)
    parser.add_argument("--answers-profile", type=Path, default=DEFAULT_ANSWER_BANK)
    parser.add_argument("--out-dir", type=Path, default=TASKS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task = _build_task(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{task['task_id']}.json"
    out_path.write_text(json.dumps(task, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote task: {out_path}")
    print(f"Source: {task['source']} | Company: {task['company']} | Role: {task['role_title']}")
    if task["resume"]["required_for_upload"] and not task["resume"]["file_url"]:
        print("Note: live upload will need resume.file_url or --allow-missing-file-url.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
