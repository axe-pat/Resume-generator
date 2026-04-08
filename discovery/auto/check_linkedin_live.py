from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from linkedin_live import _ensure_logs_dir, _looks_logged_in, _open_linkedin_browser_session


def _write_artifact(payload: dict) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = _ensure_logs_dir() / f"linkedin_live_session_check_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _body_preview(page) -> str:
    try:
        text = page.locator("body").inner_text(timeout=2000)
    except PlaywrightError:
        return ""
    return " ".join(text.split())[:400]


def _is_authwall(page) -> bool:
    current_url = page.url.lower()
    if "linkedin.com/authwall" in current_url or "linkedin.com/login" in current_url:
        return True
    preview = _body_preview(page).lower()
    return any(
        token in preview
        for token in (
            "join linkedin",
            "sign in",
            "agree & join",
            "new to linkedin",
            "already on linkedin?",
        )
    )


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
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(15000)

                artifact_payload["steps"].append(f"Attached to Chrome on port {args.debug_port}")
                artifact_payload["steps"].append(f"Initial page URL: {page.url}")

                page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                cookies = context.cookies(["https://www.linkedin.com"])
                has_li_at = any(cookie.get("name") == "li_at" for cookie in cookies)
                logged_in = _looks_logged_in(page)
                authwall = _is_authwall(page)

                artifact_payload.update(
                    {
                        "ok": logged_in and not authwall,
                        "current_url": page.url,
                        "title": page.title(),
                        "logged_in_heuristic": logged_in,
                        "authwall_or_login": authwall,
                        "has_li_at_cookie": has_li_at,
                        "cookie_names": sorted(cookie.get("name", "") for cookie in cookies),
                        "body_preview": _body_preview(page),
                    }
                )
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
