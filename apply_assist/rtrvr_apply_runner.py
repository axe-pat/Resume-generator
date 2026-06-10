#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "apply_assist" / "results"
DEFAULT_MCP_ENDPOINT = "https://mcp.rtrvr.ai"
DEFAULT_AGENT_ENDPOINT = "https://api.rtrvr.ai/agent"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_project_env() -> dict[str, str]:
    path = ROOT / ".env"
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(name: str, env_file: dict[str, str]) -> str:
    return _clean(os.environ.get(name) or env_file.get(name) or "")


def _load_answers(task: dict[str, Any]) -> dict[str, Any]:
    path_text = _clean(task.get("answers_profile_path"))
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {"_missing_answer_bank": str(path)}
    return _load_json(path)


def _compact_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True)


def _task_has_file_url(task: dict[str, Any]) -> bool:
    return bool(_clean((task.get("resume") or {}).get("file_url")))


def _resume_required_for_upload(task: dict[str, Any]) -> bool:
    return bool((task.get("resume") or {}).get("required_for_upload"))


def _build_instruction(task: dict[str, Any], answers: dict[str, Any], *, allow_missing_file_url: bool) -> str:
    resume = task.get("resume") or {}
    note = task.get("note") or {}
    guardrails = task.get("guardrails") or {}
    local_resume = _clean(resume.get("local_path"))
    file_url = _clean(resume.get("file_url"))

    file_guidance = (
        f"Use the attached/fetchable resume file named {resume.get('display_name', 'resume')}."
        if file_url
        else "No fetchable resume file URL is attached."
    )
    if local_resume and allow_missing_file_url:
        file_guidance += (
            f" A local resume path is recorded for the human operator: {local_resume}. "
            "Use it only if your browser-side file picker/tool can actually access local files."
        )

    return f"""
You are running a supervised job-application assist task for Akshat.

Hard rules:
- Stop before the final submit/apply action. Do not submit the application.
- First verify the page is for this exact company and role.
- If company or role do not match, stop and report the mismatch.
- Fill only from the task packet and answer bank below.
- Do not invent answers.
- If an unexpected required question appears, stop and report the exact question text.
- If auth, CAPTCHA, payment, EEO, disability, veteran-status, sponsorship, or work-authorization uncertainty appears and the answer is not explicitly provided, stop.
- If a field is optional and not answerable, leave it blank rather than guessing.

Target:
- Source: {task.get('source', '')}
- Company: {task.get('company', '')}
- Role: {task.get('role_title', '')}
- URL: {task.get('application_url', '')}
- Fit score: {task.get('fit_score', '')}

Resume instructions:
- Strategy: {resume.get('strategy', '')}
- Required for upload: {resume.get('required_for_upload', False)}
- {file_guidance}

Note / message instructions:
- Note required: {note.get('required', False)}
- Note text:
{_clean(note.get('text')) or '[no note provided]'}

Guardrails:
{_compact_json(guardrails)}

Answer bank:
{_compact_json(answers)}

When finished, leave the browser on the final review screen and return a concise status:
- ready_for_human_submit
- needs_human_answer
- blocked_auth_or_captcha
- company_role_mismatch
- failed

Include any unanswered required question verbatim.
""".strip()


def _build_mcp_payload(
    task: dict[str, Any],
    instruction: str,
    *,
    device_id: str,
    max_steps: int,
    recording_id: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "user_input": instruction,
        "tab_urls": [_clean(task.get("application_url"))],
        "max_steps": max_steps,
    }
    if device_id:
        params["device_id"] = device_id
    if recording_id:
        params["recording_id"] = recording_id
    file_url = _clean((task.get("resume") or {}).get("file_url"))
    if file_url:
        params["file_urls"] = [file_url]
    return {"tool": "planner", "params": params}


def _build_agent_payload(
    task: dict[str, Any],
    instruction: str,
    *,
    enable_vnc: bool,
    trajectory_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "input": instruction,
        "urls": [_clean(task.get("application_url"))],
        "response": {"verbosity": "final"},
    }
    if trajectory_id:
        payload["trajectoryId"] = trajectory_id
    file_url = _clean((task.get("resume") or {}).get("file_url"))
    if file_url:
        resume = task.get("resume") or {}
        payload["files"] = [
            {
                "displayName": _clean(resume.get("display_name")) or "resume.pdf",
                "uri": file_url,
                "mimeType": _clean(resume.get("mime_type")) or "application/pdf",
            }
        ]
    if enable_vnc:
        payload["options"] = {"ui": {"enableVnc": True, "vncScope": "root"}}
    return payload


def _post_json(endpoint: str, payload: dict[str, Any], api_key: str, timeout_seconds: int) -> tuple[int, dict[str, Any] | str]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except URLError as exc:
        return 0, {"error": str(exc)}


def _write_result(
    task: dict[str, Any],
    mode: str,
    kind: str,
    payload: dict[str, Any],
    *,
    results_dir: Path,
    response: Any | None = None,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = _clean(task.get("task_id")) or "manual-task"
    path = results_dir / f"{stamp}-{task_id}-{mode}-{kind}.json"
    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "task_id": task_id,
        "mode": mode,
        "kind": kind,
        "payload": payload,
        "response": response,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or dry-run an rtrvr apply-assist task.")
    parser.add_argument("task_json", type=Path)
    parser.add_argument("--live", action="store_true", help="Actually call rtrvr. Default is dry-run only.")
    parser.add_argument("--mode", choices=["mcp", "agent"], default="mcp")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--recording-id", default="")
    parser.add_argument("--trajectory-id", default="")
    parser.add_argument("--enable-vnc", action="store_true", help="Only applies to --mode agent.")
    parser.add_argument("--allow-missing-file-url", action="store_true")
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task = _load_json(args.task_json)
    answers = _load_answers(task)

    if _resume_required_for_upload(task) and not _task_has_file_url(task) and not args.allow_missing_file_url:
        print(
            "ERROR: this task requires resume upload but resume.file_url is empty.\n"
            "Add --resume-file-url when building the task, edit the task JSON, or run with "
            "--allow-missing-file-url for a prompt-only experiment.",
            file=sys.stderr,
        )
        return 2

    instruction = _build_instruction(task, answers, allow_missing_file_url=args.allow_missing_file_url)
    env_file = _read_project_env()
    device_id = _env_value("RTRVR_DEVICE_ID", env_file)

    if args.mode == "mcp":
        payload = _build_mcp_payload(
            task,
            instruction,
            device_id=device_id,
            max_steps=args.max_steps,
            recording_id=args.recording_id,
        )
        endpoint = args.endpoint or _env_value("RTRVR_MCP_ENDPOINT", env_file) or DEFAULT_MCP_ENDPOINT
    else:
        payload = _build_agent_payload(
            task,
            instruction,
            enable_vnc=args.enable_vnc,
            trajectory_id=args.trajectory_id,
        )
        endpoint = args.endpoint or _env_value("RTRVR_AGENT_ENDPOINT", env_file) or DEFAULT_AGENT_ENDPOINT

    if not args.live:
        path = _write_result(task, args.mode, "dry-run", payload, results_dir=args.results_dir)
        print(f"Dry-run payload written: {path}")
        print("No rtrvr call was made. Re-run with --live to execute.")
        return 0

    api_key = _env_value("RTRVR_API_KEY", env_file)
    if not api_key:
        print("ERROR: RTRVR_API_KEY is not set in the environment or project .env.", file=sys.stderr)
        return 2

    status, response = _post_json(endpoint, payload, api_key, args.timeout_seconds)
    path = _write_result(task, args.mode, f"live-{status}", payload, results_dir=args.results_dir, response=response)
    print(f"rtrvr status: {status}")
    print(f"Result written: {path}")
    if status < 200 or status >= 300:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
