#!/usr/bin/env python3
"""Browser-backed USC Marshall 12twenty discovery.

The portal is authenticated and JavaScript-rendered, so discovery attaches to
the repository's signed-in Chrome/CDP session.  It deliberately extracts the
full job detail before applying deterministic eligibility rules: 12twenty's
keyword search frequently matches body copy that is unrelated to the title.

Default behavior is extract/classify only.  Pass ``--score`` to score the
deterministic survivors and ``--write`` to append accepted rows to jobs.xlsx.
``--write`` requires ``--score`` so unreviewed rows never enter the apply queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

try:
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - environment failure is reported by CLI
    print("ERROR: playwright is not installed in this Python environment.")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
DISCOVERY_DIR = HERE.parent
ROOT = DISCOVERY_DIR.parent
LOGS_DIR = HERE / "logs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402
from discovery.auto.scorer import DEFAULT_MODEL, score_batch  # noqa: E402
from shared.discovery_sources import min_apply_queue_score_for_row  # noqa: E402
from shared.discovery_search_policy import discovery_priority, internship_title_rejection  # noqa: E402
from shared.job_eligibility import (  # noqa: E402
    LANE_A,
    LANE_B,
    LANE_C,
    classify_discovery_job_offline,
    classify_start_timing,
)

SOURCE_TAG = "twelvetwenty_jobs_v1"
RUN_SCHEMA = "resume_generator.twelvetwenty_import_run"
RUN_VERSION = 1
DEFAULT_URL = "https://marshall-usc.12twenty.com/jobPostings#/jobPostings/index?tab=all"

TIME_FILTER_LABELS = {
    "24h": "Today",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
}

# Searches are intentionally redundant. Portal metadata is inconsistent, and
# some target roles are found only because the phrase appears in the JD body.
SEARCH_TERMS = (
    "new grad",
    "associate product manager",
    "junior product manager",
    "product manager",
    "product operations",
    "technical program manager",
    "program manager",
    "leadership development program",
    "rotational program",
    "graduate program",
    "young professional",
    "product analyst",
    "business operations",
    "strategy operations",
    "forward deployed",
    "solutions engineer",
    "sales engineer",
    "technical account manager",
    "2027",
    "product manager intern Spring 2027",
)

_PART_TIME_RE = re.compile(
    r"\b(?:part[- ]time|student worker|research assistant|teaching assistant|on[- ]campus)\b",
    re.I,
)


@dataclass(frozen=True)
class SearchCard:
    title: str
    company: str
    location: str
    role_type: str
    listed_at: str
    deadline_label: str
    url: str
    queries: tuple[str, ...]


def canonical_url(url: str) -> str:
    """Collapse featured/recommended variants of the same portal posting."""
    parts = urlsplit(str(url or "").strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment.split("?", 1)[0]))


def url_hash(url: str) -> str:
    return hashlib.md5(canonical_url(url).casefold().encode()).hexdigest()


def title_company_hash(company: str, title: str) -> str:
    return hashlib.md5(f"{company.strip().casefold()}||{title.strip().casefold()}".encode()).hexdigest()


def infer_lane(title: str, jd_text: str, role_type: str = "") -> str:
    timing = classify_start_timing(title, jd_text)
    if timing in {
        "fall_2026_internship",
        "spring_2027_internship",
        "summer_2027_internship",
        "summer_internship_unspecified_year",
        "other_2027_internship",
        "internship_unspecified",
    } or "intern" in str(role_type or "").casefold():
        return LANE_A
    if _PART_TIME_RE.search(f"{title}\n{jd_text[:2400]}"):
        return LANE_C
    return LANE_B


def _clean_heading(value: str) -> str:
    return re.sub(r"\s+(?:School Network\s+)?unfavorited\s*$", "", value or "", flags=re.I).strip()


def _term_map(page: Page) -> dict[str, list[str]]:
    pairs = page.locator("main dt").evaluate_all(
        """els => els.map(el => ({
          key: (el.innerText || el.textContent || '').trim(),
          value: ((el.nextElementSibling && (el.nextElementSibling.innerText ||
                  el.nextElementSibling.textContent)) || '').trim()
        }))"""
    )
    out: dict[str, list[str]] = {}
    for pair in pairs:
        key = re.sub(r"\s+", " ", str(pair.get("key") or "")).strip().rstrip(":")
        value = re.sub(r"\s+", " ", str(pair.get("value") or "")).strip()
        if key and value:
            out.setdefault(key, []).append(value)
    return out


def _first_term(terms: dict[str, list[str]], *names: str) -> str:
    for name in names:
        values = terms.get(name) or []
        if values:
            return values[0]
    return ""


def _parse_search_row(text: str) -> tuple[str, str, str, str, str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and line not in {"--", "APPLICATION OPEN", "Not Applied"}]
    company = lines[1] if len(lines) > 1 else ""
    joined = " | ".join(lines)
    role_type = "Internship" if re.search(r"\bInternship\b", joined, re.I) else "Job"
    listed_match = re.search(r"\b(?:\d+\s+(?:hours?|days?|weeks?|months?)|1\s+month) ago\b", joined, re.I)
    listed = listed_match.group(0) if listed_match else ""
    deadline_match = re.search(r"Apply By:\s*\d{1,2}/\d{1,2}/\d{4},?\s*[^|]*", joined, re.I)
    deadline = deadline_match.group(0).strip() if deadline_match else ""
    location = ""
    if len(lines) > 2:
        location = re.sub(r"\s+(?:Job|Internship)$", "", lines[2]).strip()
    return company, location, role_type, listed, deadline


def _collect_cards(page: Page, terms: tuple[str, ...], *, delay_ms: int, max_per_query: int) -> list[SearchCard]:
    box = page.get_by_role("textbox", name="Employer, Job Title, or Keyword")
    found: dict[str, dict[str, Any]] = {}
    for query in terms:
        table = page.locator("tbody")
        before = table.inner_text() if table.count() else ""
        box.fill(query)
        box.press("Enter")
        try:
            page.wait_for_function(
                """before => {
                  const table = document.querySelector('tbody');
                  return !table || (table.innerText || '') !== before;
                }""",
                arg=before,
                timeout=max(2500, delay_ms * 3),
            )
        except PlaywrightTimeoutError:
            # Legitimate different queries can return the same set. The bounded
            # wait prevents a stale result without turning that case fatal.
            pass
        page.wait_for_timeout(delay_ms)
        for _ in range(5):
            load_more = page.get_by_role("button", name=re.compile(r"Load more results", re.I))
            if load_more.count() == 0 or not load_more.first.is_visible():
                break
            load_more.first.click()
            page.wait_for_timeout(delay_ms)
        rows = page.locator("tbody tr").evaluate_all(
            """els => els.map(el => {
              const a = el.querySelector('a[href*="/jobPostings/"]');
              return a ? {title: (a.innerText || a.textContent || '').trim(),
                          url: a.href, row: (el.innerText || '').trim()} : null;
            }).filter(Boolean)"""
        )
        unique_in_query = 0
        for row in rows:
            key = canonical_url(str(row.get("url") or ""))
            if not key:
                continue
            record = found.setdefault(
                key,
                {"title": str(row.get("title") or "").strip(), "row": str(row.get("row") or ""), "queries": []},
            )
            if query not in record["queries"]:
                record["queries"].append(query)
            unique_in_query += 1
            if unique_in_query >= max_per_query:
                break

    cards: list[SearchCard] = []
    for url, raw in found.items():
        company, location, role_type, listed, deadline = _parse_search_row(raw["row"])
        cards.append(
            SearchCard(
                title=raw["title"],
                company=company,
                location=location,
                role_type=role_type,
                listed_at=listed,
                deadline_label=deadline,
                url=url,
                queries=tuple(raw["queries"]),
            )
        )
    return cards


def _extract_detail(page: Page, card: SearchCard, *, delay_ms: int) -> dict[str, Any]:
    page.goto(card.url, wait_until="domcontentloaded", timeout=45_000)
    page.get_by_role("heading", level=1).wait_for(state="visible", timeout=20_000)
    page.locator("body").press("End")
    page.wait_for_timeout(max(200, delay_ms // 3))
    main = page.locator("main")
    text = main.inner_text(timeout=20_000)
    terms = _term_map(page)
    title = _clean_heading(page.get_by_role("heading", level=1).inner_text()) or card.title
    company_links = main.locator('a[href*="/Companies"]')
    company = company_links.first.inner_text().strip() if company_links.count() else card.company
    location = _first_term(terms, "Location") or card.location
    role_type = _first_term(terms, "Type of Job") or card.role_type
    deadline = _first_term(terms, "Application Deadline")
    start_date = _first_term(terms, "Anticipated Job Start Date")
    work_auth = _first_term(terms, "Work Authorization")
    salary = _first_term(terms, "Salary")
    return {
        "company": company,
        "role_title": title,
        "location": location,
        "role_type": role_type,
        "url": card.url,
        "date_posted": card.listed_at,
        "deadline": "" if deadline == "--" else deadline,
        "deadline_source": "12twenty_portal" if deadline and deadline != "--" else "rolling",
        "anticipated_start_date": "" if start_date == "--" else start_date,
        "work_authorization": work_auth,
        "pay_text": "" if salary == "--" else salary,
        "jd_text": text,
        "queries": list(card.queries),
    }


def _candidate(detail: dict[str, Any]) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    title = str(detail.get("role_title") or "")
    jd_text = str(detail.get("jd_text") or "")
    lane = infer_lane(title, jd_text, str(detail.get("role_type") or ""))
    row = {
        "id": "",
        "date_found": today,
        "date_posted": detail.get("date_posted", ""),
        "company": detail.get("company", ""),
        "role_title": title,
        "role_type": detail.get("role_type", ""),
        "location": detail.get("location", ""),
        "url": detail.get("url", ""),
        "url_hash": url_hash(str(detail.get("url") or "")),
        "source": SOURCE_TAG,
        "fit_score": "",
        "fit_rationale": "",
        "status": "new",
        "date_applied": "",
        "folder_path": "",
        "resume_run": "",
        "jd_text": jd_text,
        "notes": "12twenty portal; queries=" + ",".join(detail.get("queries") or []),
        "lane": lane,
        "deadline": detail.get("deadline", ""),
        "deadline_source": detail.get("deadline_source", ""),
        "everify_status": "",
        "sponsorship_flag": "",
        "classification": "",
        "reject_reason": "",
        "pay_text": detail.get("pay_text", ""),
        "anticipated_start_date": detail.get("anticipated_start_date", ""),
        "work_authorization": detail.get("work_authorization", ""),
    }
    # Portal metadata is part of the evidence. Keeping it in JD text ensures the
    # shared immigration and timing rules see it even when body copy omits it.
    row["jd_text"] = (
        f"{row['jd_text']}\n\n12twenty structured fields\n"
        f"Anticipated Job Start Date: {row['anticipated_start_date']}\n"
        f"Work Authorization: {row['work_authorization']}\n"
        f"Salary: {row['pay_text']}"
    )
    return classify_discovery_job_offline(row, default_lane=lane)


def _existing_keys(df: pd.DataFrame) -> tuple[set[str], set[str]]:
    urls = {url_hash(value) for value in df.get("url", pd.Series(dtype=str)).fillna("").astype(str) if value.strip()}
    pairs = {
        title_company_hash(str(row.get("company") or ""), str(row.get("role_title") or ""))
        for _, row in df.iterrows()
    }
    return urls, pairs


def _assign_ids(df: pd.DataFrame, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric = pd.to_numeric(df.get("id", pd.Series(dtype=str)), errors="coerce")
    next_id = int(numeric.max()) + 1 if numeric.notna().any() else 1
    for row in rows:
        row["id"] = str(next_id)
        next_id += 1
    return rows


def _write_artifact(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def run(args: argparse.Namespace) -> int:
    if args.write and not args.score:
        raise SystemExit("--write requires --score; unreviewed 12twenty rows cannot enter the queue")
    endpoint = f"http://127.0.0.1:{args.debug_port}"
    cards: list[SearchCard] = []
    details: list[dict[str, Any]] = []
    fetch_failed: list[dict[str, str]] = []
    title_skipped: list[dict[str, str]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(endpoint, timeout=60_000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            search_page = context.new_page()
            detail_page = context.new_page()
            try:
                search_page.goto(args.search_url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    search_page.get_by_role("textbox", name="Employer, Job Title, or Keyword").wait_for(
                        state="visible", timeout=45_000
                    )
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        "12twenty search is unavailable in the configured profile; "
                        f"landed at {search_page.url.split('?')[0]} "
                        f"(page title: {search_page.title()}). "
                        "Check portal sign-in before retrying."
                    ) from exc
                body = search_page.locator("body").inner_text()
                if "Akshat Pathak" not in body or "Account Settings" not in body:
                    raise RuntimeError("12twenty session is not signed in in the configured Chrome profile")

                date_button = search_page.get_by_role("button", name=re.compile(r"Job Posting Submit Date"))
                if date_button.count() and date_button.get_attribute("aria-expanded") != "true":
                    date_button.first.click()
                relative = search_page.get_by_role("radio", name="Relative Range")
                if relative.count() and not relative.is_checked():
                    relative.check()
                search_page.get_by_role("combobox", name="Job Posting Submit Date").select_option(
                    label=TIME_FILTER_LABELS[args.window]
                )
                search_page.wait_for_timeout(args.delay_ms)

                cards = _collect_cards(
                    search_page,
                    tuple(args.search or SEARCH_TERMS),
                    delay_ms=args.delay_ms,
                    max_per_query=args.max_per_query,
                )
                cards.sort(key=lambda card: discovery_priority(card.title, card.role_type))
                for card in cards:
                    reason = internship_title_rejection(card.title)
                    if reason:
                        title_skipped.append({"company": card.company, "role_title": card.title,
                                              "url": card.url, "reason": reason})
                        continue
                    try:
                        details.append(_extract_detail(detail_page, card, delay_ms=args.delay_ms))
                    except Exception as exc:  # one stale network listing must not kill the pull
                        fetch_failed.append({"url": card.url, "title": card.title, "error": str(exc)[:300]})
            finally:
                search_page.close()
                detail_page.close()
    except Exception as exc:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        artifact = Path(args.run_artifact) if args.run_artifact else LOGS_DIR / f"twelvetwenty_import_{stamp}.json"
        failure = {
            "schema": RUN_SCHEMA,
            "version": RUN_VERSION,
            "status": "failed",
            "generated_at": datetime.now().astimezone().isoformat(),
            "window": args.window,
            "time_filter": TIME_FILTER_LABELS[args.window],
            "source": SOURCE_TAG,
            "counts": {
                "queries": len(args.search or SEARCH_TERMS),
                "search_cards": len(cards), "fetch_ok": len(details), "fetch_failed": 1,
                "new_after_dedupe": 0, "deterministic_survivors": 0, "scored": 0,
                "accepted": 0, "rejected": 0, "skipped_duplicates": 0, "error_count": 1,
            },
            "cards": [asdict(card) for card in cards],
            "details": details, "classified": [], "survivors": [], "accepted": [],
            "rejected": [], "skipped": [],
            "fetch_failed": [{"url": args.search_url, "title": "12twenty preflight", "error": str(exc)[:500]}],
        }
        _write_artifact(artifact, failure)
        print(f"12twenty discovery failed: {exc}", file=sys.stderr)
        print(f"Artifact: {artifact}")
        return 1

    existing = jobs.load_jobs()
    existing_urls, existing_pairs = _existing_keys(existing)
    classified: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for detail in details:
        row = _candidate(detail)
        pair = title_company_hash(str(row.get("company") or ""), str(row.get("role_title") or ""))
        if row["url_hash"] in existing_urls:
            skipped.append({"company": row["company"], "role_title": row["role_title"], "reason": "duplicate_url"})
        elif pair in existing_pairs:
            skipped.append({"company": row["company"], "role_title": row["role_title"], "reason": "duplicate_company_title"})
        else:
            classified.append(row)

    survivors = [row for row in classified if str(row.get("classification") or "").casefold() in {"keep", "unsure"}]
    scored = score_batch(survivors, model=args.model, verbose=not args.quiet, max_workers=args.max_workers) if args.score and survivors else survivors
    accepted = [
        row for row in scored
        if str(row.get("status") or "").casefold() == "queued"
        and pd.to_numeric(row.get("fit_score"), errors="coerce")
        >= min_apply_queue_score_for_row(str(row.get("source") or ""), str(row.get("notes") or ""), args.min_score)
    ]
    rejected = [row for row in classified if row not in survivors] + [row for row in scored if row not in accepted]

    counts = {
        "queries": len(args.search or SEARCH_TERMS),
        "search_cards": len(cards),
        "fetch_ok": len(details),
        "fetch_failed": len(fetch_failed),
        "new_after_dedupe": len(classified),
        "deterministic_survivors": len(survivors),
        "scored": len(scored) if args.score else 0,
        "accepted": len(accepted) if args.score else 0,
        "rejected": len(rejected),
        "skipped_duplicates": len(skipped),
        "title_prefilter_skipped": len(title_skipped),
        "error_count": len(fetch_failed),
    }
    status = "completed" if not fetch_failed else ("partial_failed" if details else "failed")
    payload = {
        "schema": RUN_SCHEMA,
        "version": RUN_VERSION,
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(),
        "window": args.window,
        "time_filter": TIME_FILTER_LABELS[args.window],
        "source": SOURCE_TAG,
        "counts": counts,
        "cards": [asdict(card) for card in cards],
        "details": details,
        "classified": classified,
        "survivors": survivors,
        "accepted": accepted,
        "rejected": rejected,
        "skipped": skipped,
        "title_prefilter_skipped": title_skipped,
        "fetch_failed": fetch_failed,
    }
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifact = Path(args.run_artifact) if args.run_artifact else LOGS_DIR / f"twelvetwenty_import_{stamp}.json"
    _write_artifact(artifact, payload)

    print(f"12twenty {args.window}: {len(cards)} unique search cards; {len(details)} full JDs fetched")
    print(f"New after dedupe: {len(classified)}; deterministic survivors: {len(survivors)}")
    print(f"Projected scoring calls: {len(survivors)}")
    print(f"Artifact: {artifact}")
    if rejected:
        reason_counts = pd.Series([str(row.get("reject_reason") or row.get("fit_rationale") or "not accepted") for row in rejected]).value_counts()
        print("Reject reasons:")
        for reason, count in reason_counts.items():
            print(f"  {count:>3}  {reason}")

    if args.write and accepted:
        accepted = _assign_ids(existing, accepted)
        frame = pd.DataFrame(accepted, columns=jobs.COLUMNS)
        jobs.save_jobs(pd.concat([existing[jobs.COLUMNS], frame], ignore_index=True))
        from discovery.scripts.refresh_current_apply_queue import main as refresh_queue

        refresh_queue()
        print(f"Wrote {len(accepted)} accepted role(s) and refreshed the apply queue.")
    elif args.write:
        print("No accepted roles to write.")
    return 0 if status != "failed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="USC Marshall 12twenty discovery")
    parser.add_argument("--window", choices=tuple(TIME_FILTER_LABELS), default="24h")
    parser.add_argument("--search-url", default=DEFAULT_URL)
    parser.add_argument("--search", action="append", default=[])
    parser.add_argument("--debug-port", type=int, default=9222)
    parser.add_argument("--delay-ms", type=int, default=900)
    parser.add_argument("--max-per-query", type=int, default=100)
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=5.9)
    parser.add_argument("--run-artifact", default="")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
