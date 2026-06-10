#!/usr/bin/env python3
"""
Import a manually exported Handshake CSV into the application tracker.

This is intentionally browser-backed: direct HTTP fetches to Handshake are
Cloudflare/auth gated, so JD extraction requires a signed-in Chrome session with
remote debugging enabled.

Default behavior is dry-run. Pass --write to append accepted rows to jobs.xlsx
and refresh the current apply queue.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
DISCOVERY_DIR = HERE.parent
ROOT = DISCOVERY_DIR.parent
LOGS_DIR = HERE / "logs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import jobs  # noqa: E402
from scorer import DEFAULT_MODEL, score_batch  # noqa: E402

SOURCE_TAG = "handshake_jobs_v1"
DEFAULT_CSV = Path("/Users/akshat/Downloads/-JobTitle-Company-Industry-Pay-Deadline-Status-URL.csv")


@dataclass
class CsvJob:
    row_number: str
    company: str
    role_title: str
    industry: str
    pay: str
    deadline: str
    urgency: str
    url: str


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode()).hexdigest() if url else ""


def _tc_hash(company: str, title: str) -> str:
    return hashlib.md5(f"{company.strip().lower()}|{title.strip().lower()}".encode()).hexdigest()


def _load_csv(path: Path) -> list[CsvJob]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"#", "Job Title", "Company", "Industry", "Pay", "Deadline", "Status", "URL"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            url = _clean(row.get("URL"))
            company = _clean(row.get("Company"))
            title = _clean(row.get("Job Title"))
            if not url or not company or not title:
                continue
            rows.append(
                CsvJob(
                    row_number=_clean(row.get("#")),
                    company=company,
                    role_title=title,
                    industry=_clean(row.get("Industry")),
                    pay=_clean(row.get("Pay")),
                    deadline=_clean(row.get("Deadline")),
                    urgency=_clean(row.get("Status")),
                    url=url,
                )
            )
    return rows


def _existing_keys(df: pd.DataFrame) -> tuple[set[str], set[str]]:
    url_hashes = set(df.get("url_hash", pd.Series(dtype=str)).fillna("").astype(str))
    title_company = {
        _tc_hash(str(row.get("company") or ""), str(row.get("role_title") or ""))
        for _, row in df.iterrows()
    }
    return url_hashes, title_company


def _csv_notes(job: CsvJob) -> str:
    parts = [
        "handshake_csv_import=true",
        f"csv_row={job.row_number}" if job.row_number else "",
        f"industry={job.industry}" if job.industry else "",
        f"pay={job.pay}" if job.pay else "",
        f"deadline={job.deadline}" if job.deadline else "",
        f"urgency={job.urgency}" if job.urgency else "",
    ]
    return " ".join(part for part in parts if part)


def _candidate_dict(job: CsvJob, jd_text: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "id": "",
        "date_found": today,
        "date_posted": "",
        "company": job.company,
        "role_title": job.role_title,
        "role_type": "",
        "location": "",
        "url": job.url,
        "url_hash": _url_hash(job.url),
        "source": SOURCE_TAG,
        "fit_score": "",
        "fit_rationale": "",
        "status": "new",
        "date_applied": "",
        "folder_path": "",
        "resume_run": "",
        "jd_text": jd_text,
        "notes": _csv_notes(job),
    }


def _looks_like_blocker(text: str, title: str) -> str:
    lower = text.lower()
    if not text.strip():
        return "empty page text"
    if "just a moment" in lower and "cloudflare" in lower:
        return "Cloudflare challenge"
    if "sign in" in lower and "handshake" in lower and len(text) < 2500:
        return "Handshake login wall"
    if "enable javascript" in lower and len(text) < 2500:
        return "JavaScript/browser challenge"
    if len(text) < 500:
        return f"too little page text ({len(text)} chars)"
    if title and title.lower() not in lower and len(text) < 1800:
        return "job title not visible in extracted text"
    return ""


async def _expand_handshake_page(page: Any) -> None:
    selectors = [
        "button:has-text('More')",
        "button:has-text('Show more')",
        "[role=button]:has-text('More')",
        "[role=button]:has-text('Show more')",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(await locator.count(), 6)
        except Exception:
            continue
        for idx in range(count):
            try:
                item = locator.nth(idx)
                if await item.is_visible(timeout=1000):
                    await item.click(timeout=2000)
                    await page.wait_for_timeout(350)
            except Exception:
                continue


def _trim_jd_text(text: str, company: str, title: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    lower = text.lower()
    start = 0
    title_idx = lower.find(title.lower()) if title else -1
    company_idx = lower.find(company.lower()) if company else -1
    if title_idx != -1 and company_idx != -1 and 0 <= title_idx - company_idx <= 600:
        start = company_idx
    elif title_idx != -1:
        start = max(0, title_idx - 80)
    else:
        for anchor in ("job description", "about the role", "about the job", "responsibilities", "what you'll do"):
            idx = lower.find(anchor)
            if idx != -1:
                start = max(0, idx - 120)
                break

    trimmed = text[start:]
    if company and company.lower() not in trimmed.lower():
        trimmed = f"{company}\n{title}\n\n{trimmed}"
    return trimmed[:12000]


async def _fetch_with_cdp(candidates: list[CsvJob], cdp_url: str, delay_ms: int) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is not installed in this venv.") from exc

    fetched: list[dict[str, Any]] = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            raise SystemExit(
                f"Could not attach to Chrome at {cdp_url}. "
                "Launch a signed-in Handshake browser with remote debugging first."
            ) from exc

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        for idx, job in enumerate(candidates, start=1):
            result: dict[str, Any] = {
                "company": job.company,
                "role_title": job.role_title,
                "url": job.url,
                "ok": False,
                "jd_text": "",
                "error": "",
            }
            try:
                print(f"Fetching [{idx}/{len(candidates)}]: {job.company} | {job.role_title}")
                await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(delay_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                await _expand_handshake_page(page)

                page_title = await page.title()
                body_text = await page.locator("body").inner_text(timeout=10000)
                blocker = _looks_like_blocker(body_text, job.role_title)
                if blocker:
                    result["error"] = f"{blocker}; page_title={page_title!r}"
                else:
                    result["ok"] = True
                    result["jd_text"] = _trim_jd_text(body_text, job.company, job.role_title)
                    result["page_title"] = page_title
            except Exception as exc:
                result["error"] = str(exc)
            fetched.append(result)

        await page.close()
        await browser.close()

    return fetched


def _assign_ids(existing: pd.DataFrame, new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric_ids = pd.to_numeric(existing.get("id", pd.Series(dtype=str)), errors="coerce").dropna()
    next_id = int(numeric_ids.max()) + 1 if not numeric_ids.empty else 1
    for row in new_rows:
        row["id"] = str(next_id)
        next_id += 1
    return new_rows


def _write_raw_log(payload: dict[str, Any]) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = LOGS_DIR / f"handshake_import_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _refresh_queue() -> None:
    from discovery.scripts.refresh_current_apply_queue import main as refresh_main

    refresh_main()


def run(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv).expanduser()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    csv_jobs = _load_csv(csv_path)
    df_existing = jobs.load_jobs()
    existing_urls, existing_tc = _existing_keys(df_existing)

    seen_urls: set[str] = set()
    candidates: list[CsvJob] = []
    skipped: list[dict[str, str]] = []
    for item in csv_jobs:
        url_key = _url_hash(item.url)
        title_key = _tc_hash(item.company, item.role_title)
        if url_key in existing_urls:
            skipped.append({"url": item.url, "company": item.company, "role_title": item.role_title, "reason": "duplicate_url"})
            continue
        if title_key in existing_tc:
            skipped.append({"url": item.url, "company": item.company, "role_title": item.role_title, "reason": "duplicate_company_title"})
            continue
        if url_key in seen_urls:
            skipped.append({"url": item.url, "company": item.company, "role_title": item.role_title, "reason": "duplicate_in_csv"})
            continue
        seen_urls.add(url_key)
        candidates.append(item)

    if args.limit:
        candidates = candidates[: args.limit]

    print(f"CSV rows: {len(csv_jobs)}")
    print(f"New candidates after dedupe: {len(candidates)}")
    print(f"Skipped duplicates: {len(skipped)}")
    if not candidates:
        return 0

    fetched: list[dict[str, Any]]
    if args.no_fetch:
        fetched = [
            {
                "company": item.company,
                "role_title": item.role_title,
                "url": item.url,
                "ok": True,
                "jd_text": f"{item.company}\n{item.role_title}\n\n{_csv_notes(item)}",
                "warning": "no_fetch placeholder; not scoreable as a real JD",
            }
            for item in candidates
        ]
    else:
        import asyncio

        fetched = asyncio.run(_fetch_with_cdp(candidates, args.cdp_url, args.delay_ms))

    fetched_by_url = {str(item.get("url") or ""): item for item in fetched}
    fetch_ok = [item for item in candidates if fetched_by_url.get(item.url, {}).get("ok")]
    fetch_failed = [fetched_by_url.get(item.url, {}) for item in candidates if not fetched_by_url.get(item.url, {}).get("ok")]

    rows_to_score = [
        _candidate_dict(item, str(fetched_by_url[item.url].get("jd_text") or ""))
        for item in fetch_ok
    ]

    scored: list[dict[str, Any]] = []
    if rows_to_score and not args.skip_score:
        scored = score_batch(rows_to_score, model=args.model, verbose=not args.quiet, max_workers=args.max_workers)
    else:
        scored = rows_to_score

    allowed_decisions = {"proceed"}
    if args.include_deprioritized:
        allowed_decisions.add("deprioritize")
    accepted = [
        row for row in scored
        if str(row.get("status") or "").lower() == "queued"
        and str(row.get("decision") or "").lower() in allowed_decisions
        and pd.to_numeric(row.get("fit_score"), errors="coerce") >= args.min_score
    ]
    rejected = [row for row in scored if row not in accepted]

    log_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "csv": str(csv_path),
        "source": SOURCE_TAG,
        "write": bool(args.write),
        "counts": {
            "csv_rows": len(csv_jobs),
            "deduped_candidates": len(candidates),
            "skipped_duplicates": len(skipped),
            "fetch_ok": len(fetch_ok),
            "fetch_failed": len(fetch_failed),
            "scored": len(scored),
            "accepted_min_score": len(accepted),
            "rejected_or_below_min": len(rejected),
        },
        "skipped": skipped,
        "fetch_failed": fetch_failed,
        "scored": [
            {
                "company": row.get("company"),
                "role_title": row.get("role_title"),
                "fit_score": row.get("fit_score"),
                "status": row.get("status"),
                "decision": row.get("decision"),
                "category": row.get("category"),
                "url": row.get("url"),
                "fit_rationale": row.get("fit_rationale"),
            }
            for row in scored
        ],
        "accepted": [
            {
                "company": row.get("company"),
                "role_title": row.get("role_title"),
                "fit_score": row.get("fit_score"),
                "url": row.get("url"),
                "fit_rationale": row.get("fit_rationale"),
            }
            for row in accepted
        ],
    }
    log_path = _write_raw_log(log_payload)

    print(f"Fetched JDs: {len(fetch_ok)} ok, {len(fetch_failed)} failed")
    if fetch_failed:
        print("Fetch failures:")
        for item in fetch_failed[:8]:
            print(f"  - {item.get('company')} | {item.get('role_title')}: {item.get('error')}")

    if scored:
        print(f"Scored: {len(scored)}")
        print(f"Accepted at min_score {args.min_score}: {len(accepted)}")
        print("Top scored:")
        for row in sorted(scored, key=lambda r: float(r.get("fit_score") or 0), reverse=True)[:8]:
            print(
                f"  [{row.get('fit_score')}] {row.get('company')} | {row.get('role_title')} | "
                f"{row.get('decision')} / {row.get('category')}"
            )
        for row in sorted(accepted, key=lambda r: float(r.get("fit_score") or 0), reverse=True):
            print(f"  [{row.get('fit_score')}] {row.get('company')} | {row.get('role_title')}")

    print(f"Log: {log_path.relative_to(ROOT)}")

    if not args.write:
        print("Dry run only. Re-run with --write to append accepted rows and refresh the queue.")
        return 0

    if not accepted:
        print("No accepted rows to write.")
        return 0

    accepted = _assign_ids(df_existing, accepted)
    df_new = pd.DataFrame(accepted, columns=jobs.COLUMNS)
    df_all = pd.concat([df_existing[jobs.COLUMNS], df_new], ignore_index=True)
    jobs.save_jobs(df_all)
    print(f"Wrote {len(accepted)} row(s) to discovery/jobs.xlsx")

    if not args.no_refresh_queue:
        _refresh_queue()
        print("Refreshed apps/Apply queues/current_apply_queue")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Handshake CSV jobs into ResumeGenerator.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Handshake CSV export path.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="Chrome DevTools endpoint.")
    parser.add_argument("--limit", type=int, default=0, help="Limit candidates for smoke tests.")
    parser.add_argument("--delay-ms", type=int, default=2500, help="Wait after page load before extracting text.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Scoring model.")
    parser.add_argument("--max-workers", type=int, default=1, help="Scoring workers.")
    parser.add_argument("--min-score", type=float, default=5.9, help="Minimum score to write to queue lane.")
    parser.add_argument(
        "--include-deprioritized",
        action="store_true",
        help="Allow Deprioritize rows above --min-score; Reject rows still stay out.",
    )
    parser.add_argument("--skip-score", action="store_true", help="Fetch JDs but do not call the scorer.")
    parser.add_argument("--no-fetch", action="store_true", help="Parse/dedupe only with placeholder text.")
    parser.add_argument("--write", action="store_true", help="Append accepted rows to jobs.xlsx and refresh queue.")
    parser.add_argument("--no-refresh-queue", action="store_true", help="Do not refresh current_apply_queue after writing.")
    parser.add_argument("--quiet", action="store_true", help="Reduce scorer output.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
