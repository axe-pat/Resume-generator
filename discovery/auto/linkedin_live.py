"""
linkedin_live.py — Logged-in LinkedIn job discovery
---------------------------------------------------
Uses a real logged-in Chrome session via Playwright CDP to search LinkedIn Jobs,
extract visible job cards, open each card, capture JD text, score the results,
and append them into discovery/jobs.xlsx.

This is intentionally separate from Outreach. We borrow the same browser/session
pattern, but keep discovery logic native to this repo.

Usage:
    python discovery/auto/linkedin_live.py --dry-run
    python discovery/auto/linkedin_live.py --limit-per-search 12
    python discovery/auto/linkedin_live.py --pages 2
    python discovery/auto/linkedin_live.py --search "Product Manager Intern" --time r86400

Pre-reqs:
  1. Chrome must already be running with remote debugging enabled.
  2. The logged-in LinkedIn session must be active in that Chrome profile.
  3. Playwright must be installed in the Python env running this script.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from urllib.parse import urlencode

import pandas as pd

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    print("ERROR: playwright is not installed in this Python environment.")
    print('Install it with: pip install playwright && playwright install chromium')
    sys.exit(1)

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from pipeline import COLUMNS, JOBS_XLSX, LOGS_DIR, SHEET_NAME, load_jobs, save_jobs  # noqa: E402
from scorer import DEFAULT_MODEL, score_batch  # noqa: E402


DEFAULT_DEBUG_PORT = 9222
DEFAULT_LIMIT_PER_SEARCH: int | None = None
DEFAULT_PAGES: int | None = None
SOURCE_TAG = "linkedin_live_jobs_v1"
SEARCH_RESULTS_MIN_POOL_BEFORE_FALLBACK = 2
CHROME_APP_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_PROFILE_ROOT = Path.home() / "Library/Application Support/Google/Chrome"
TEMP_DEBUG_PROFILE_ROOT = Path(tempfile.gettempdir()) / "codex-chrome-debug-profile"
DEFAULT_SEARCHES = [
    ("Product Manager Intern", "r86400"),
    ("Product Manager Intern", "r604800"),
    ("MBA Intern", "r86400"),
    ("MBA Intern", "r604800"),
]

TIME_LABELS = {
    "r86400": "past_24h",
    "r604800": "past_week",
}


@dataclass
class LinkedInJobCard:
    search_term: str
    time_filter: str
    title: str
    company: str
    location: str
    url: str
    listed_at: str
    insight: str
    jd_text: str


def _hash(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def url_hash(url: str) -> str:
    return _hash(url)


def title_company_hash(title: str, company: str) -> str:
    return _hash(f"{title}||{company}")


def _human_pause(page: Page, low_ms: int = 900, high_ms: int = 1700) -> None:
    page.wait_for_timeout(low_ms + int((high_ms - low_ms) * 0.5))


def _jobs_search_url(search_term: str, time_filter: str) -> str:
    return (
        "https://www.linkedin.com/jobs/search-results/"
        f"?keywords={quote_plus(search_term)}"
        f"&f_TPR={time_filter}"
        "&origin=SEMANTIC_SEARCH_JOB_ALERT_IN_APP_NOTIFICATION"
    )


def _jobs_search_fallback_url(search_term: str, time_filter: str) -> str:
    return (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(search_term)}"
        "&distance=25"
        "&geoId=103644278"
        "&sortBy=DD"
        f"&f_TPR={time_filter}"
        "&origin=JOB_SEARCH_PAGE_JOB_FILTER"
        "&refresh=true"
    )


def _with_start_param(url: str, start: int) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}start={start}"


def _ensure_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def _write_run_artifact(name: str, payload: dict) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = _ensure_logs_dir() / f"{name}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _prepare_debug_profile_copy(profile_dir: str = "Default") -> Path:
    source_profile = CHROME_PROFILE_ROOT / profile_dir
    if not source_profile.exists():
        raise FileNotFoundError(f"Chrome profile not found: {source_profile}")

    shutil.rmtree(TEMP_DEBUG_PROFILE_ROOT, ignore_errors=True)
    TEMP_DEBUG_PROFILE_ROOT.mkdir(parents=True, exist_ok=True)

    local_state = CHROME_PROFILE_ROOT / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, TEMP_DEBUG_PROFILE_ROOT / "Local State")

    shutil.copytree(source_profile, TEMP_DEBUG_PROFILE_ROOT / profile_dir, dirs_exist_ok=True)
    return TEMP_DEBUG_PROFILE_ROOT


def _open_linkedin_browser_session(playwright, debug_port: int):
    endpoint = f"http://127.0.0.1:{debug_port}"
    try:
        browser = playwright.chromium.connect_over_cdp(endpoint)
        if browser.contexts:
            return {
                "mode": "cdp",
                "context": browser.contexts[0],
                "cleanup": lambda: None,
            }
    except PlaywrightError:
        pass

    if not CHROME_APP_PATH.exists():
        raise RuntimeError(
            f"Chrome app not found at {CHROME_APP_PATH} and CDP attach failed."
        )

    debug_root = _prepare_debug_profile_copy("Default")
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(debug_root),
        executable_path=str(CHROME_APP_PATH),
        headless=False,
        args=["--no-first-run", "--no-default-browser-check"],
    )
    return {
        "mode": "persistent",
        "context": context,
        "cleanup": context.close,
    }


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value or "run"


def _parse_relative_date(text: str) -> str:
    raw = (text or "").strip().lower()
    now = datetime.now()
    if not raw:
        return now.strftime("%Y-%m-%d")

    patterns: list[tuple[str, timedelta]] = [
        (r"(\d+)\s*hour", timedelta(hours=1)),
        (r"(\d+)\s*day", timedelta(days=1)),
        (r"(\d+)\s*week", timedelta(days=7)),
        (r"(\d+)\s*month", timedelta(days=30)),
    ]
    for pattern, unit in patterns:
        match = re.search(pattern, raw)
        if match:
            count = int(match.group(1))
            return (now - (unit * count)).strftime("%Y-%m-%d")
    if "today" in raw or "just now" in raw:
        return now.strftime("%Y-%m-%d")
    if "yesterday" in raw:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def _clean_title(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if not value:
        return value

    parts = value.split(" ")
    if len(parts) % 2 == 0:
        half = len(parts) // 2
        if parts[:half] == parts[half:]:
            return " ".join(parts[:half])

    repeated = re.match(r"^(.+?)\s+\1(?:\s+with verification)?$", value, flags=re.I)
    if repeated:
        return repeated.group(1).strip()

    return value


def _scroll_results_list(page: Page) -> int:
    """
    Scroll the jobs results container itself. LinkedIn virtualizes cards inside
    the list, so page-level mouse wheel misses rows on the search-results view.
    Returns the current number of visible job roots after scrolling.
    """
    script = r"""
    () => {
      const selectors = [
        'ul.semantic-search-results-list',
        'ul[class*="semantic-search-results-list"]',
        '.jobs-search-results-list',
        '.scaffold-layout__list ul',
      ];
      const container =
        selectors.map(sel => document.querySelector(sel)).find(Boolean) ||
        document.querySelector('ul:has([data-job-id])');
      if (!container) {
        window.scrollBy(0, 2200);
        return document.querySelectorAll('[data-job-id]').length;
      }
      container.scrollTop = container.scrollHeight;
      return document.querySelectorAll('[data-job-id]').length;
    }
    """
    try:
        visible = page.evaluate(script)
    except PlaywrightError:
        page.mouse.wheel(0, 2200)
        visible = page.locator("[data-job-id]").count()
    _human_pause(page, 700, 1200)
    return int(visible or 0)


def _extract_about_job_text(page: Page) -> str:
    candidates = [
        page.locator("main").first,
        page.locator("body").first,
    ]
    for locator in candidates:
        try:
            if locator.count() == 0:
                continue
            text = locator.inner_text(timeout=3000).strip()
            if not text:
                continue
            normalized = re.sub(r"\n{3,}", "\n\n", text)
            match = re.search(
                r"About the job\s+(.*?)(?:\n(?:Seniority level|Employment type|Job function|Industries|Referrals increase your chances|Set alert for similar jobs|People you can reach out to)\b|$)",
                normalized,
                flags=re.S | re.I,
            )
            if match:
                return match.group(1).strip()
            return normalized
        except PlaywrightError:
            continue
    return ""


def _safe_goto(page: Page, url: str, timeout_ms: int = 30000) -> bool:
    def _looks_loaded() -> bool:
        try:
            if "linkedin.com/jobs" not in page.url:
                return False
            page.wait_for_timeout(1200)
            if page.locator("[data-job-id]").count() > 0:
                return True
            body_text = page.locator("body").inner_text(timeout=1500)
            return "results" in body_text.lower() or "jobs" in body_text.lower()
        except PlaywrightError:
            return False

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        return _looks_loaded()
    except PlaywrightTimeoutError:
        try:
            page.goto(url, wait_until="commit", timeout=min(timeout_ms, 12000))
            return _looks_loaded()
        except PlaywrightError:
            return False
    except PlaywrightError:
        return False


def _semantic_fuzzy_count(page: Page) -> int | None:
    code_nodes = page.locator("code")
    total = min(code_nodes.count(), 120)
    for idx in range(total):
        try:
            text = code_nodes.nth(idx).inner_text(timeout=500)
        except PlaywrightError:
            continue
        if "jobsDashJobCardsBySemanticSearch" not in text or "fuzzyCount" not in text:
            continue
        match = re.search(r'"fuzzyCount":\{.*?"text":"(\d+)\s+results"', text)
        if match:
            return int(match.group(1))
    return None


def _job_score_value(job: dict) -> float:
    try:
        return float(job.get("fit_score"))
    except (TypeError, ValueError):
        return -1.0


def _render_report_markdown(
    *,
    run_label: str,
    searches: list[tuple[str, str]],
    scored_jobs: list[dict],
    accepted_for_write: list[dict],
    fresh_after_dedup: list[dict],
) -> str:
    captured = len(scored_jobs)
    decisions: dict[str, int] = {}
    for job in scored_jobs:
        key = str(job.get("decision") or "Unknown")
        decisions[key] = decisions.get(key, 0) + 1

    top_jobs = sorted(
        [job for job in scored_jobs if _job_score_value(job) >= 0],
        key=_job_score_value,
        reverse=True,
    )[:10]

    lines = [
        f"# LinkedIn Discovery Batch Report: {run_label}",
        "",
        "## Summary",
        f"- Searches: {', '.join(f'{term} ({TIME_LABELS.get(window, window)})' for term, window in searches)}",
        f"- Jobs extracted: {captured}",
        f"- Jobs accepted for write gate: {len(accepted_for_write)}",
        f"- Jobs written after dedup: {len(fresh_after_dedup)}",
        f"- Decisions: {', '.join(f'{k}={v}' for k, v in sorted(decisions.items())) or 'none'}",
        "",
        "## Top Rated",
    ]

    if top_jobs:
        lines.extend([
            "| Score | Decision | Company | Role | Search | Window |",
            "|---|---|---|---|---|---|",
        ])
        for job in top_jobs:
            lines.append(
                f"| {job.get('fit_score', '')} | {job.get('decision', '')} | "
                f"{job.get('company', '')} | {job.get('role_title', '')} | "
                f"{re.search(r'search=([^ ]+.*?)(?: window=| insight=|$)', str(job.get('notes', ''))).group(1) if re.search(r'search=([^ ]+.*?)(?: window=| insight=|$)', str(job.get('notes', ''))) else ''} | "
                f"{re.search(r'window=([^ ]+)', str(job.get('notes', ''))).group(1) if re.search(r'window=([^ ]+)', str(job.get('notes', ''))) else ''} |"
            )
    else:
        lines.append("No scored jobs available.")

    lines.extend(["", "## All Reviewed Jobs", "| Score | Decision | Write Gate | Company | Role | Source Search |", "|---|---|---|---|---|---|"])
    accepted_urls = {job.get("url") for job in accepted_for_write}
    for job in sorted(scored_jobs, key=_job_score_value, reverse=True):
        notes = str(job.get("notes", ""))
        search_match = re.search(r"search=(.*?)(?: window=| insight=|$)", notes)
        source_search = search_match.group(1) if search_match else ""
        lines.append(
            f"| {job.get('fit_score', '') if job.get('fit_score') is not None else ''} | "
            f"{job.get('decision', '')} | "
            f"{'accepted' if job.get('url') in accepted_urls else 'dropped'} | "
            f"{job.get('company', '')} | {job.get('role_title', '')} | {source_search} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_report_html(
    *,
    run_label: str,
    searches: list[tuple[str, str]],
    scored_jobs: list[dict],
    accepted_for_write: list[dict],
    fresh_after_dedup: list[dict],
) -> str:
    captured = len(scored_jobs)
    decisions: dict[str, int] = {}
    for job in scored_jobs:
        key = str(job.get("decision") or "Unknown")
        decisions[key] = decisions.get(key, 0) + 1

    top_jobs = sorted(
        [job for job in scored_jobs if _job_score_value(job) >= 0],
        key=_job_score_value,
        reverse=True,
    )[:10]
    accepted_urls = {job.get("url") for job in accepted_for_write}

    def search_of(job: dict) -> str:
        notes = str(job.get("notes", ""))
        match = re.search(r"search=(.*?)(?: window=| insight=|$)", notes)
        return match.group(1) if match else ""

    def rows_html(rows: list[dict], include_gate: bool) -> str:
        out = []
        for job in rows:
            cells = [
                html.escape("" if job.get("fit_score") is None else str(job.get("fit_score"))),
                html.escape(str(job.get("decision", ""))),
            ]
            if include_gate:
                cells.append("accepted" if job.get("url") in accepted_urls else "dropped")
            cells.extend([
                html.escape(str(job.get("company", ""))),
                html.escape(str(job.get("role_title", ""))),
                html.escape(search_of(job)),
            ])
            out.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
        return "\n".join(out)

    summary_items = [
        f"Searches: {', '.join(f'{term} ({TIME_LABELS.get(window, window)})' for term, window in searches)}",
        f"Jobs extracted: {captured}",
        f"Jobs accepted for write gate: {len(accepted_for_write)}",
        f"Jobs written after dedup: {len(fresh_after_dedup)}",
        f"Decisions: {', '.join(f'{k}={v}' for k, v in sorted(decisions.items())) or 'none'}",
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(f"LinkedIn Discovery Batch Report: {run_label}")}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 980px;
      margin: 32px auto;
      padding: 0 20px 40px;
      color: #1f2937;
      background: #f8fafc;
      line-height: 1.5;
    }}
    h1, h2 {{ color: #0f172a; }}
    .card {{ background: white; padding: 16px 18px; border-radius: 14px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }}
    ul {{ margin: 0; padding-left: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }}
    th {{ background: #eff6ff; color: #1d4ed8; position: sticky; top: 0; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <h1>LinkedIn Discovery Batch Report: {html.escape(run_label)}</h1>
  <div class="card">
    <h2>Summary</h2>
    <ul>
      {''.join(f'<li>{html.escape(item)}</li>' for item in summary_items)}
    </ul>
  </div>
  <div class="card">
    <h2>Top Rated</h2>
    <table>
      <thead>
        <tr><th>Score</th><th>Decision</th><th>Company</th><th>Role</th><th>Search</th></tr>
      </thead>
      <tbody>
        {rows_html(top_jobs, include_gate=False) if top_jobs else '<tr><td colspan="5" class="muted">No scored jobs available.</td></tr>'}
      </tbody>
    </table>
  </div>
  <div class="card">
    <h2>All Reviewed Jobs</h2>
    <table>
      <thead>
        <tr><th>Score</th><th>Decision</th><th>Write Gate</th><th>Company</th><th>Role</th><th>Search</th></tr>
      </thead>
      <tbody>
        {rows_html(sorted(scored_jobs, key=_job_score_value, reverse=True), include_gate=True)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def _write_batch_report(
    *,
    run_label: str,
    searches: list[tuple[str, str]],
    scored_jobs: list[dict],
    accepted_for_write: list[dict],
    fresh_after_dedup: list[dict],
) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = f"linkedin_live_report_{stamp}_{_slug(run_label)}"
    md_path = _ensure_logs_dir() / f"{base}.md"
    html_path = _ensure_logs_dir() / f"{base}.html"
    md = _render_report_markdown(
        run_label=run_label,
        searches=searches,
        scored_jobs=scored_jobs,
        accepted_for_write=accepted_for_write,
        fresh_after_dedup=fresh_after_dedup,
    )
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(
        _render_report_html(
            run_label=run_label,
            searches=searches,
            scored_jobs=scored_jobs,
            accepted_for_write=accepted_for_write,
            fresh_after_dedup=fresh_after_dedup,
        ),
        encoding="utf-8",
    )
    return md_path, html_path


def _looks_logged_in(page: Page) -> bool:
    if page.is_closed():
        return False
    try:
        checks = [
            ("feed", "linkedin.com/feed" in page.url),
            ("jobs", "linkedin.com/jobs" in page.url),
            ("me icon", page.locator('[data-control-name="nav.settings"]').count() > 0),
            ("global nav", page.locator("nav.global-nav").count() > 0),
        ]
    except PlaywrightError:
        return False
    return any(ok for _, ok in checks)


def _extract_visible_cards(page: Page) -> list[dict]:
    script = """
    () => {
      const normalize = (value) => value ? value.replace(/\\s+/g, ' ').trim() : '';
      const cleanRepeated = (value) => {
        const normalized = normalize(value);
        if (!normalized || normalized.length % 2 !== 0) return normalized;
        const half = normalized.length / 2;
        const first = normalized.slice(0, half);
        const second = normalized.slice(half);
        return first === second ? first : normalized;
      };
      const seen = new Set();
      const cards = [];
      const cardNodes = Array.from(document.querySelectorAll('[data-job-id]'));
      for (const node of cardNodes) {
        const jobId = node.getAttribute('data-job-id');
        const url = jobId ? `https://www.linkedin.com/jobs/view/${jobId}/` : '';
        if (!url || seen.has(url)) continue;
        seen.add(url);

        const titleNode =
          node.querySelector('.job-card-job-posting-card-wrapper__title strong') ||
          node.querySelector('.job-card-job-posting-card-wrapper__title') ||
          node.querySelector('.job-card-list__title') ||
          node.querySelector('.job-card-container__link');
        const companyNode =
          node.querySelector('.artdeco-entity-lockup__subtitle') ||
          node.querySelector('.job-card-container__company-name') ||
          node.querySelector('.artdeco-entity-lockup__primary-subtitle');
        const metaTexts = Array.from(node.querySelectorAll(
          '.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-card-container__footer-item, .artdeco-entity-lockup__metadata, time'
        )).map(el => normalize(el.textContent)).filter(Boolean);
        const location = metaTexts.find(text =>
          text &&
          !/(ago|applicant|applicants|clicked apply|viewed|easy apply|promoted|response|benefit|school alum|company alumni|connections? work here)/i.test(text)
        ) || '';
        const listedAt = metaTexts.find(text =>
          /(ago|today|yesterday|viewed|reposted|within the past)/i.test(text)
        ) || '';

        cards.push({
          title: cleanRepeated(titleNode ? titleNode.textContent : ''),
          company: normalize(companyNode ? companyNode.textContent : ''),
          location,
          listed_at: listedAt,
          url,
        });
      }
      return cards;
    }
    """
    data = page.evaluate(script)
    return [row for row in data if row.get("title") and row.get("company") and row.get("url")]


def _open_job_details(page: Page, job_url: str, detail_page: Page | None = None) -> tuple[str, str]:
    owns_page = detail_page is None
    detail_page = detail_page or page.context.new_page()
    detail_page.set_default_timeout(5000)
    try:
        detail_page.goto(job_url, wait_until="domcontentloaded", timeout=8000)
        detail_page.wait_for_timeout(900)

        extracted = detail_page.evaluate(
            """
            () => {
              const pickText = (selectors) => {
                for (const selector of selectors) {
                  const node = document.querySelector(selector);
                  if (!node) continue;
                  const text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                  if (text) return text;
                }
                return '';
              };

              let jdText = pickText([
                '.jobs-search__job-details--wrapper',
                '.jobs-box__html-content',
                '#job-details',
                '.jobs-description',
                '.jobs-description-content__text',
                '.show-more-less-html__markup',
              ]);

              let insightText = pickText([
                '.jobs-unified-top-card__job-insight',
                '.job-details-jobs-unified-top-card__primary-description-container',
                '.jobs-unified-top-card__primary-description-container',
                '.jobs-unified-top-card__subtitle-primary-grouping',
              ]);

              if (!insightText) {
                const main = document.querySelector('main');
                const mainText = (main?.innerText || '').replace(/\\s+/g, ' ').trim();
                if (mainText) {
                  const aboutIdx = mainText.indexOf('About the job');
                  insightText = aboutIdx > 0 ? mainText.slice(0, aboutIdx).trim() : mainText.slice(0, 400).trim();
                }
              }

              return { jdText, insightText };
            }
            """
        )

        jd_text = (extracted or {}).get("jdText", "").strip()
        if not jd_text:
            jd_text = _extract_about_job_text(detail_page)
        insight_text = (extracted or {}).get("insightText", "").strip()

        return jd_text, insight_text
    except PlaywrightError:
        return "", ""
    finally:
        if owns_page:
            detail_page.close()


def _goto_next_page(page: Page) -> bool:
    candidates = [
        page.get_by_role("button", name=re.compile("next", re.I)),
        page.locator("button[aria-label*='next' i]"),
        page.locator("button.jobs-search-pagination__indicator-button--next"),
        page.locator(".artdeco-pagination__button--next"),
    ]
    for locator in candidates:
        try:
            if locator.count() == 0:
                continue
            button = locator.first
            if button.is_disabled():
                return False
            button.click(timeout=5000)
            _human_pause(page, 1400, 2400)
            return True
        except PlaywrightError:
            try:
                handle = button.element_handle(timeout=2000)
                if handle is None:
                    continue
                page.evaluate("(el) => el.click()", handle)
                _human_pause(page, 1400, 2400)
                return True
            except PlaywrightError:
                continue
    return False


def scrape_search(
    page: Page,
    search_term: str,
    time_filter: str,
    limit_per_search: int | None,
    pages: int | None,
    extract_only: bool = False,
    detail_page: Page | None = None,
) -> list[LinkedInJobCard]:
    def _run_single_url(url: str) -> list[LinkedInJobCard]:
        cards: list[LinkedInJobCard] = []
        seen_urls: set[str] = set()

        use_offset_paging = "linkedin.com/jobs/search-results/" in url
        if use_offset_paging:
            if not _safe_goto(page, url):
                return cards
            _human_pause(page, 1600, 2400)
            if not _looks_logged_in(page):
                raise RuntimeError(
                    "LinkedIn does not appear logged in in the connected Chrome session. "
                    "Open your logged-in LinkedIn jobs page in the debug-enabled Chrome window first."
                )
            page.wait_for_timeout(1500)
            page_size: int | None = None
            page_signatures: set[tuple[str, ...]] = set()
            start = 0
            page_index = 0
            while True:
                if pages is not None and page_index >= max(pages, 1):
                    break
                target_url = _with_start_param(url, start) if start else url
                if not _safe_goto(page, target_url):
                    break
                _human_pause(page, 1600, 2400)

                if not _looks_logged_in(page):
                    raise RuntimeError(
                        "LinkedIn does not appear logged in in the connected Chrome session. "
                        "Open your logged-in LinkedIn jobs page in the debug-enabled Chrome window first."
                    )

                page.wait_for_timeout(2000)
                initial_visible = _extract_visible_cards(page)
                if not initial_visible:
                    break
                signature = tuple(card["url"] for card in initial_visible[:10])
                if signature in page_signatures:
                    break
                page_signatures.add(signature)
                if page_size is None:
                    page_size = max(len(initial_visible), 1)

                stagnant_scrolls = 0
                for _ in range(20):
                    before_count = len(seen_urls)
                    visible = _extract_visible_cards(page)
                    for summary in visible:
                        job_url = summary["url"]
                        if job_url in seen_urls:
                            continue
                        if extract_only:
                            jd_text, insight_text = "", ""
                        else:
                            try:
                                jd_text, insight_text = _open_job_details(page, job_url, detail_page=detail_page)
                            except PlaywrightError:
                                jd_text, insight_text = "", ""

                        seen_urls.add(job_url)
                        cards.append(
                            LinkedInJobCard(
                                search_term=search_term,
                                time_filter=time_filter,
                                title=_clean_title(summary["title"]),
                                company=summary["company"],
                                location=summary["location"],
                                url=job_url,
                                listed_at=summary["listed_at"],
                                insight=insight_text,
                                jd_text=jd_text,
                            )
                        )
                        if limit_per_search is not None and len(cards) >= limit_per_search:
                            return cards

                    if len(seen_urls) == before_count:
                        stagnant_scrolls += 1
                    else:
                        stagnant_scrolls = 0
                    if stagnant_scrolls >= 2:
                        break
                    _scroll_results_list(page)

                if len(initial_visible) < page_size:
                    break
                start += page_size
                page_index += 1
            return cards

        page_index = 0
        while True:
            if not _safe_goto(page, url):
                break
            _human_pause(page, 1600, 2400)

            if not _looks_logged_in(page):
                raise RuntimeError(
                    "LinkedIn does not appear logged in in the connected Chrome session. "
                    "Open your logged-in LinkedIn jobs page in the debug-enabled Chrome window first."
                )

            page.wait_for_timeout(2000)
            stagnant_scrolls = 0
            for _ in range(20):
                before_count = len(seen_urls)
                visible = _extract_visible_cards(page)
                for summary in visible:
                    job_url = summary["url"]
                    if job_url in seen_urls:
                        continue
                    if extract_only:
                        jd_text, insight_text = "", ""
                    else:
                        try:
                            jd_text, insight_text = _open_job_details(page, job_url, detail_page=detail_page)
                        except PlaywrightError:
                            jd_text, insight_text = "", ""

                    seen_urls.add(job_url)
                    cards.append(
                        LinkedInJobCard(
                            search_term=search_term,
                            time_filter=time_filter,
                            title=_clean_title(summary["title"]),
                            company=summary["company"],
                            location=summary["location"],
                            url=job_url,
                            listed_at=summary["listed_at"],
                            insight=insight_text,
                            jd_text=jd_text,
                        )
                    )
                    if limit_per_search is not None and len(cards) >= limit_per_search:
                        return cards

                if len(seen_urls) == before_count:
                    stagnant_scrolls += 1
                else:
                    stagnant_scrolls = 0
                if stagnant_scrolls >= 2:
                    break
                _scroll_results_list(page)

            if pages is not None and page_index + 1 >= max(pages, 1):
                break
            if limit_per_search is not None and len(cards) >= limit_per_search:
                break
            moved = _goto_next_page(page)
            if not moved:
                break
            page_index += 1
        return cards

    primary_cards = _run_single_url(_jobs_search_url(search_term, time_filter))
    fallback_threshold = SEARCH_RESULTS_MIN_POOL_BEFORE_FALLBACK
    if limit_per_search is not None:
        fallback_threshold = min(limit_per_search, SEARCH_RESULTS_MIN_POOL_BEFORE_FALLBACK)
    if len(primary_cards) >= fallback_threshold:
        return primary_cards

    fallback_cards = _run_single_url(_jobs_search_fallback_url(search_term, time_filter))
    combined: list[LinkedInJobCard] = []
    seen: set[str] = set()
    for card in [*primary_cards, *fallback_cards]:
        if card.url in seen:
            continue
        seen.add(card.url)
        combined.append(card)
        if limit_per_search is not None and len(combined) >= limit_per_search:
            break
    return combined


def cards_to_jobs(cards: Iterable[LinkedInJobCard]) -> list[dict]:
    jobs: list[dict] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for card in cards:
        jobs.append(
            {
                "id": None,
                "date_found": today,
                "date_posted": _parse_relative_date(card.listed_at),
                "company": card.company,
                "role_title": card.title,
                "role_type": "Other",
                "location": card.location,
                "url": card.url,
                "url_hash": url_hash(card.url),
                "source": SOURCE_TAG,
                "fit_score": None,
                "fit_rationale": None,
                "status": "new",
                "date_applied": None,
                "folder_path": None,
                "jd_text": card.jd_text,
                "notes": (
                    f"tag={SOURCE_TAG} "
                    f"search={card.search_term} "
                    f"window={TIME_LABELS.get(card.time_filter, card.time_filter)} "
                    f"insight={card.insight}"
                ).strip(),
                "tc_hash": title_company_hash(card.title, card.company),
            }
        )
    return jobs


def append_new_jobs(df_existing: pd.DataFrame, jobs: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    existing_url_hashes = {
        str(v).strip()
        for v in df_existing.get("url_hash", pd.Series(dtype=str)).fillna("").tolist()
        if str(v).strip()
    }
    existing_tc_hashes = {
        title_company_hash(str(row.get("role_title") or ""), str(row.get("company") or ""))
        for _, row in df_existing.iterrows()
    }

    fresh: list[dict] = []
    seen_new_urls: set[str] = set()
    seen_new_tcs: set[str] = set()
    for job in jobs:
        if job["url_hash"] in existing_url_hashes or job["url_hash"] in seen_new_urls:
            continue
        if job["tc_hash"] in existing_tc_hashes or job["tc_hash"] in seen_new_tcs:
            continue
        fresh.append(job)
        seen_new_urls.add(job["url_hash"])
        seen_new_tcs.add(job["tc_hash"])

    if not fresh:
        return df_existing, []

    start_id = 1
    if not df_existing.empty and "id" in df_existing.columns:
        numeric_ids = pd.to_numeric(df_existing["id"], errors="coerce").dropna()
        if not numeric_ids.empty:
            start_id = int(numeric_ids.max()) + 1

    rows_for_df = []
    for idx, job in enumerate(fresh, start=start_id):
        job["id"] = str(idx)
        rows_for_df.append({col: job.get(col) for col in COLUMNS})

    df_new = pd.DataFrame(rows_for_df, columns=COLUMNS)
    if df_existing.empty:
        return df_new, fresh
    return pd.concat([df_existing[COLUMNS], df_new], ignore_index=True), fresh


def filter_jobs_for_write(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Keep only jobs we would actually want in the tracker.
    We do not persist:
    - rows with no JD text
    - scorer errors
    - hard rejects
    - deprioritized jobs
    """
    accepted: list[dict] = []
    dropped: list[dict] = []
    for job in jobs:
        has_jd = bool((job.get("jd_text") or "").strip())
        decision = str(job.get("decision") or "").strip().lower()
        if not has_jd or decision not in {"proceed"}:
            dropped.append(job)
            continue
        accepted.append(job)
    return accepted, dropped


def run_live_discovery(
    searches: list[tuple[str, str]],
    debug_port: int,
    limit_per_search: int | None,
    pages: int | None,
    dry_run: bool,
    model: str,
    quiet: bool,
    extract_only: bool = False,
    max_workers: int = 2,
) -> int:
    windows = sorted({TIME_LABELS.get(window, window) for _, window in searches})
    run_label = windows[0] if len(windows) == 1 else "mixed"
    with sync_playwright() as playwright:
        session = _open_linkedin_browser_session(playwright, debug_port)
        try:
            context = session["context"]
            page = context.new_page()
            detail_page = context.new_page()
            page.set_default_timeout(15000)
            detail_page.set_default_timeout(15000)

            scraped_cards: list[LinkedInJobCard] = []
            for search_term, time_filter in searches:
                if not quiet:
                    print(f"\nSearching LinkedIn Jobs: {search_term} | {TIME_LABELS.get(time_filter, time_filter)}")
                cards = scrape_search(
                    page=page,
                    search_term=search_term,
                    time_filter=time_filter,
                    limit_per_search=limit_per_search,
                    pages=pages,
                    extract_only=extract_only,
                    detail_page=detail_page,
                )
                scraped_cards.extend(cards)
                if not quiet:
                    print(f"  Captured {len(cards)} cards")
            detail_page.close()
            page.close()
        finally:
            try:
                session["cleanup"]()
            except Exception:
                pass

    jobs = cards_to_jobs(scraped_cards)
    artifact = _write_run_artifact(
        "linkedin_live_raw",
        {
            "count": len(scraped_cards),
            "searches": [{"search_term": s, "time_filter": t} for s, t in searches],
            "cards": [asdict(card) for card in scraped_cards],
        },
    )

    if not quiet:
        print(f"\nRaw artifact: {artifact}")
        print(f"Raw cards captured: {len(scraped_cards)}")

    if not jobs:
        print("No jobs were captured from LinkedIn live search.")
        return 0

    if extract_only:
        md_report, html_report = _write_batch_report(
            run_label=f"{run_label}_extract_only",
            searches=searches,
            scored_jobs=jobs,
            accepted_for_write=[],
            fresh_after_dedup=[],
        )
        print(f"Extract-only count complete: {len(jobs)} jobs")
        print(f"Batch report (Markdown): {md_report}")
        print(f"Batch report (HTML): {html_report}")
        return len(jobs)

    scored = score_batch(jobs, model=model, verbose=not quiet, max_workers=max_workers)
    accepted_for_write, dropped_before_write = filter_jobs_for_write(scored)
    df_existing = load_jobs()
    merged_df, fresh = append_new_jobs(df_existing, accepted_for_write)

    score_artifact = _write_run_artifact(
        "linkedin_live_scored",
        {
            "captured": len(scraped_cards),
            "scored": len(scored),
            "accepted_for_write": len(accepted_for_write),
            "dropped_before_write": len(dropped_before_write),
            "new_after_dedup": len(fresh),
            "jobs": scored,
        },
    )
    if not quiet:
        print(f"Scored artifact: {score_artifact}")
        print(f"Accepted for write after gating: {len(accepted_for_write)}")
        print(f"Dropped before write: {len(dropped_before_write)}")
        print(f"New jobs after dedup: {len(fresh)}")

    md_report, html_report = _write_batch_report(
        run_label=run_label,
        searches=searches,
        scored_jobs=scored,
        accepted_for_write=accepted_for_write,
        fresh_after_dedup=fresh,
    )
    if not quiet:
        print(f"Batch report (Markdown): {md_report}")
        print(f"Batch report (HTML): {html_report}")

    if fresh:
        save_jobs(merged_df, dry_run=dry_run)
        if dry_run:
            print(f"[dry-run] Would append {len(fresh)} LinkedIn-live jobs to {JOBS_XLSX}")
        else:
            print(f"Appended {len(fresh)} LinkedIn-live jobs to {JOBS_XLSX}")
    else:
        print("All captured jobs were duplicates of existing rows.")

    return len(fresh)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Logged-in LinkedIn live discovery")
    parser.add_argument("--debug-port", type=int, default=DEFAULT_DEBUG_PORT, help="Chrome remote debugging port")
    parser.add_argument(
        "--limit-per-search",
        type=int,
        default=DEFAULT_LIMIT_PER_SEARCH,
        help="Max jobs to inspect per search. Omit for no cap. Use 0 for no cap.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGES,
        help="LinkedIn result pages to scan per search. Omit for all pages. Use 0 for all pages.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Score jobs but skip writing jobs.xlsx")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Scoring model (default: {DEFAULT_MODEL})")
    parser.add_argument("--extract-only", action="store_true", help="Only extract/count jobs. Skip JD scoring and jobs.xlsx writes.")
    parser.add_argument("--max-workers", type=int, default=2, help="Parallel scoring workers for the full scored run.")
    parser.add_argument("--quiet", action="store_true", help="Reduce terminal output")
    parser.add_argument("--search", action="append", default=[], help="Override search term. Repeat for multiple values.")
    parser.add_argument(
        "--time",
        action="append",
        default=[],
        help="Override LinkedIn recency filter(s), e.g. r86400 or r604800. Must align with --search count if provided.",
    )
    return parser.parse_args()


def _resolve_searches(args: argparse.Namespace) -> list[tuple[str, str]]:
    if not args.search and not args.time:
        return list(DEFAULT_SEARCHES)
    if len(args.search) != len(args.time):
        raise SystemExit("When overriding searches, provide matching counts for --search and --time.")
    return list(zip(args.search, args.time))


if __name__ == "__main__":
    args = _parse_args()
    searches = _resolve_searches(args)
    limit_per_search = None if args.limit_per_search in (None, 0) else args.limit_per_search
    pages = None if args.pages in (None, 0) else args.pages
    run_live_discovery(
        searches=searches,
        debug_port=args.debug_port,
        limit_per_search=limit_per_search,
        pages=pages,
        dry_run=args.dry_run,
        model=args.model,
        quiet=args.quiet,
        extract_only=args.extract_only,
        max_workers=args.max_workers,
    )
