from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright

from linkedin_live import _ensure_logs_dir, _open_linkedin_browser_session, _session_preflight


def _write_artifact(payload: dict) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = _ensure_logs_dir() / f"linkedin_live_session_check_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify LinkedIn live Chrome session via CDP")
    parser.add_argument("--debug-port", type=int, default=9222, help="Chrome remote debugging port")
    parser.add_argument(
        "--url",
        default="https://www.linkedin.com/feed/",
        help="LinkedIn URL to open for the live-session check",
    )
    args = parser.parse_args()

    artifact_payload: dict = {
        "ok": False,
        "debug_port": args.debug_port,
        "target_url": args.url,
        "steps": [],
    }

    try:
        with sync_playwright() as playwright:
            session = _open_linkedin_browser_session(playwright, args.debug_port)
            try:
                context = session["context"]
                artifact_payload["steps"].append(f"Attached to Chrome on port {args.debug_port}")
                artifact_payload.update(_session_preflight(context, target_url=args.url))
            finally:
                try:
                    session["cleanup"]()
                except Exception:
                    pass
    except Exception as exc:
        artifact_payload["error"] = str(exc)

    artifact = _write_artifact(artifact_payload)
    print(f"Artifact: {artifact}")

    if artifact_payload.get("ok"):
        print("LinkedIn live session check passed.")
        print(f"URL: {artifact_payload.get('current_url', '')}")
        print(f"Title: {artifact_payload.get('title', '')}")
        return 0

    print("LinkedIn live session check failed.")
    if artifact_payload.get("error"):
        print(f"Error: {artifact_payload['error']}")
    else:
        print(f"URL: {artifact_payload.get('current_url', '')}")
        print(f"Title: {artifact_payload.get('title', '')}")
        print(f"logged_in_heuristic={artifact_payload.get('logged_in_heuristic')}")
        print(f"authwall_or_login={artifact_payload.get('authwall_or_login')}")
        print(f"has_li_at_cookie={artifact_payload.get('has_li_at_cookie')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
