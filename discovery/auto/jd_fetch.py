"""
jd_fetch.py — JD Fetcher / Retry Tool
---------------------------------------
Fetches missing job descriptions for rows in jobs.xlsx that have no jd_text.
Designed for screenshot-sourced jobs where the initial score_screenshots.py run
couldn't find the JD within its original 168h JobSpy window.

Three fetch paths, tried in order per job:
  Path A — JobSpy (no time limit): searches LinkedIn + Indeed by title + location.
            No hours_old constraint = finds postings regardless of age.
  Path B — Direct URL fetch: if a URL is present, try fetching it as a plain HTML
            page and extracting body text. Works for Greenhouse, Lever, Workday, etc.
            Skips LinkedIn URLs (auth-gated).
  Path C — Manual paste: writes a helper .txt file to discovery/manual/jd_paste/
            and prints instructions. User pastes the JD, then re-runs with --rescore.

After fetching, jobs are re-scored via scorer.py and jobs.xlsx is updated.

Usage:
    # Retry all screenshot rows with no JD (default)
    python discovery/auto/jd_fetch.py

    # Retry specific row IDs from jobs.xlsx
    python discovery/auto/jd_fetch.py --id 1540,1541,1543

    # Dry run — show what would be fetched, don't write xlsx
    python discovery/auto/jd_fetch.py --dry-run

    # After manually pasting JDs, re-score the paste files
    python discovery/auto/jd_fetch.py --rescore-pastes

    # Skip JobSpy (only try Path B + C) — faster if you know JobSpy won't help
    python discovery/auto/jd_fetch.py --no-jobspy

Run from ResumeGenerator v1/ root.
⚠  Run from Mac terminal — Anthropic API calls fail from the Cowork VM.
"""

import argparse
import hashlib
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

_HERE     = Path(__file__).parent          # discovery/auto/
_ROOT     = _HERE.parent                   # discovery/
_PROJ     = _ROOT.parent                   # ResumeGenerator v1/
JOBS_XLSX = _ROOT / "jobs.xlsx"
PASTE_DIR = _ROOT / "manual" / "jd_paste"
LOGS_DIR  = _HERE / "logs"

sys.path.insert(0, str(_HERE))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not found. pip install pandas")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not found. pip install anthropic")
    sys.exit(1)

try:
    import requests
    from requests.exceptions import RequestException
    _HAVE_REQUESTS = True
except ImportError:
    _HAVE_REQUESTS = False

try:
    from jobspy import scrape_jobs
    _HAVE_JOBSPY = True
except ImportError:
    _HAVE_JOBSPY = False

from pipeline import load_jobs, save_jobs, COLUMNS
from scorer  import score_batch, _load_api_key, DEFAULT_MODEL

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JD_RESULTS_WANTED = 15
JD_FETCH_SLEEP    = 5    # seconds between JobSpy calls
URL_FETCH_TIMEOUT = 15   # seconds for direct HTTP fetch
COMPANY_MATCH_THRESHOLD = 0.5  # slightly more lenient than score_screenshots.py

# ATS domains that are publicly fetchable (no auth needed)
_ATS_FETCHABLE = [
    "greenhouse.io", "boards.greenhouse.io",
    "lever.co", "jobs.lever.co",
    "myworkdayjobs.com",
    "careers.smartrecruiters.com",
    "jobs.jobvite.com",
    "apply.workable.com",
    "recruiting.ultipro.com",
    "icims.com",
    "taleo.net",
    "bamboohr.com",
    "bytedance.com",  # TikTok/ByteDance careers
]

_ATS_SKIP = ["linkedin.com", "indeed.com"]  # auth-gated or rate-limited


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company_similarity(a: str, b: str) -> float:
    a_tok = set(re.sub(r"[^\w]", " ", a.lower()).split())
    b_tok = set(re.sub(r"[^\w]", " ", b.lower()).split())
    noise = {"inc", "llc", "corp", "ltd", "co", "the", "and", "&",
             "technologies", "technology", "solutions", "services",
             "group", "global", "company"}
    a_tok -= noise
    b_tok -= noise
    if not a_tok or not b_tok:
        return 0.0
    return len(a_tok & b_tok) / min(len(a_tok), len(b_tok))


def _url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode()).hexdigest() if url else ""


def _tc_hash(company: str, title: str) -> str:
    return hashlib.md5(f"{company.strip().lower()}|{title.strip().lower()}".encode()).hexdigest()


def _extract_text_from_html(html: str) -> str:
    """Very basic HTML → text: strip tags, collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>",  " ", text,  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;",  "&", text)
    text = re.sub(r"&lt;",   "<", text)
    text = re.sub(r"&gt;",   ">", text)
    text = re.sub(r"\s+",    " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Path A — JobSpy (no time limit)
# ---------------------------------------------------------------------------

def fetch_via_jobspy(company: str, title: str, location: str) -> dict | None:
    """
    Search LinkedIn + Indeed with no time constraint.
    Returns best-matching job dict or None.
    """
    if not _HAVE_JOBSPY:
        return None

    loc = location if location and location.lower() not in ("unknown", "nan", "") else "United States"
    try:
        results = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term=title,
            location=loc,
            results_wanted=JD_RESULTS_WANTED,
            linkedin_fetch_description=True,
            # No hours_old — find the posting regardless of age
        )
    except Exception as e:
        print(f"      ⚠  JobSpy error: {e}")
        return None

    if results is None or results.empty:
        return None

    best_row, best_sim = None, 0.0
    for _, row in results.iterrows():
        sim = _company_similarity(company, str(row.get("company") or ""))
        if sim > best_sim:
            best_sim = sim
            best_row = row

    if best_row is None or best_sim < COMPANY_MATCH_THRESHOLD:
        return None

    jd_text = str(best_row.get("description") or "").strip()
    if not jd_text:
        return None

    return {
        "company":    str(best_row.get("company") or company),
        "role_title": str(best_row.get("title")   or title),
        "location":   str(best_row.get("location") or location),
        "url":        str(best_row.get("job_url")  or ""),
        "source":     str(best_row.get("site")     or "unknown"),
        "jd_text":    jd_text,
        "_path":      "A-jobspy",
    }


# ---------------------------------------------------------------------------
# Path B — Direct URL fetch
# ---------------------------------------------------------------------------

def fetch_via_url(url: str) -> str | None:
    """
    Fetch a publicly accessible ATS URL and extract text.
    Returns JD text or None.
    """
    if not _HAVE_REQUESTS or not url or url.lower() in ("nan", "none", ""):
        return None

    # Skip auth-gated sites
    for skip in _ATS_SKIP:
        if skip in url:
            return None

    # Only attempt known-fetchable ATS domains
    fetchable = any(ats in url for ats in _ATS_FETCHABLE)
    if not fetchable:
        print(f"      ⚠  URL not in known-fetchable ATS list: {url[:60]}")
        return None

    try:
        resp = requests.get(
            url,
            timeout=URL_FETCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JDFetcher/1.0)"},
        )
        resp.raise_for_status()
        text = _extract_text_from_html(resp.text)
        if len(text) > 200:
            return text[:8000]  # cap to save tokens
        return None
    except RequestException as e:
        print(f"      ⚠  URL fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Path C — Manual paste
# ---------------------------------------------------------------------------

def prepare_paste_file(row_id: int, company: str, title: str) -> Path:
    """
    Write a placeholder .txt to PASTE_DIR for manual JD entry.
    Returns the paste file path.
    """
    PASTE_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w]", "_", f"{company}_{title}")[:60]
    paste_path = PASTE_DIR / f"{row_id}_{slug}.txt"
    if not paste_path.exists():
        paste_path.write_text(
            f"# Row ID: {row_id}\n"
            f"# Company: {company}\n"
            f"# Title: {title}\n"
            f"# Instructions: Paste the full job description below this line, then save.\n"
            f"# Run: python discovery/auto/jd_fetch.py --rescore-pastes\n\n"
        )
    return paste_path


def load_paste_files() -> dict[int, str]:
    """
    Load all paste files that have content below the header lines.
    Returns {row_id: jd_text}.
    """
    if not PASTE_DIR.exists():
        return {}

    results = {}
    for f in PASTE_DIR.glob("*.txt"):
        try:
            row_id = int(f.stem.split("_")[0])
        except ValueError:
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        content_lines = [l for l in lines if not l.startswith("#") and l.strip()]
        text = "\n".join(content_lines).strip()
        if text:
            results[row_id] = text
    return results


# ---------------------------------------------------------------------------
# Scoring helper
# ---------------------------------------------------------------------------

def rescore_row(row: pd.Series, jd_text: str, client, model: str) -> dict:
    """Score a single job dict with the given JD text. Returns score result dict."""
    job = {
        "company":    str(row.get("company") or ""),
        "role_title": str(row.get("role_title") or ""),
        "location":   str(row.get("location") or ""),
        "source":     str(row.get("source") or "screenshot"),
        "jd_text":    jd_text,
    }
    scored = score_batch([job], client=client, model=model, verbose=True)
    return scored[0] if scored else {}


# ---------------------------------------------------------------------------
# Main fetch loop
# ---------------------------------------------------------------------------

def run_fetch(args):
    df = load_jobs()

    # Select target rows
    if args.id:
        ids = [int(i.strip()) for i in args.id.split(",")]
        mask = df["id"].isin(ids)
    else:
        # Default: screenshot rows with no JD text
        mask = (
            (df["source"] == "screenshot") &
            (df["jd_text"].fillna("").str.strip() == "")
        )

    targets = df[mask].copy()
    if targets.empty:
        print("No rows match. Nothing to do.")
        return

    print(f"\n{'='*60}")
    print(f"JD Fetcher  —  {len(targets)} target rows")
    print(f"{'='*60}")

    api_key = _load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)
    model   = args.model or DEFAULT_MODEL

    fetched    = []
    paste_needed = []

    _UNKNOWN_VALS = {"unknown", "", "nan", "none", "(job title not visible)"}

    for _, row in targets.iterrows():
        row_id  = int(row["id"]) if pd.notna(row.get("id")) else "?"
        company = str(row.get("company") or "Unknown")
        title   = str(row.get("role_title") or "Unknown")
        location = str(row.get("location") or "Unknown")
        url     = str(row.get("url") or "")

        print(f"\n  [{row_id}] {company} — {title[:60]}")

        # Skip if company or title is unusable — nothing to search for
        if company.strip().lower() in _UNKNOWN_VALS or title.strip().lower() in _UNKNOWN_VALS:
            print(f"    ✗ Skipping — unknown company or title (nothing to search)")
            continue

        jd_text  = None
        path_used = None

        # ── Path A: JobSpy (no time limit) ──────────────────────────────────
        if not args.no_jobspy and company != "Unknown" and title != "Unknown":
            print(f"    Path A: JobSpy search (no time limit)…")
            result = fetch_via_jobspy(company, title, location)
            if result and result.get("jd_text"):
                jd_text   = result["jd_text"]
                path_used = "A-jobspy"
                url       = result.get("url") or url
                print(f"      ✓ Found ({len(jd_text)} chars) via {result.get('source')}")
            else:
                print(f"      ✗ Not found")
            time.sleep(JD_FETCH_SLEEP)

        # ── Path B: Direct URL fetch ─────────────────────────────────────────
        if jd_text is None and url and url not in ("nan", "None", ""):
            print(f"    Path B: Direct URL fetch…")
            fetched_text = fetch_via_url(url)
            if fetched_text:
                jd_text   = fetched_text
                path_used = "B-url"
                print(f"      ✓ Fetched from URL ({len(jd_text)} chars)")
            else:
                print(f"      ✗ Not fetchable")

        # ── Path C: Manual paste ─────────────────────────────────────────────
        if jd_text is None:
            paste_path = prepare_paste_file(row_id, company, title)
            paste_needed.append((row_id, company, title, paste_path))
            print(f"    Path C: Manual paste needed → {paste_path.relative_to(_PROJ)}")
            continue

        # ── Score the fetched JD ─────────────────────────────────────────────
        print(f"    Scoring via {path_used}…")
        score_result = rescore_row(row, jd_text, client, model)

        fetched.append({
            "row_id":      row_id,
            "company":     company,
            "title":       title,
            "jd_text":     jd_text,
            "url":         url,
            "path":        path_used,
            "score_result": score_result,
        })

    # ── Write results back to xlsx ─────────────────────────────────────────
    if fetched and not args.dry_run:
        df = load_jobs()  # reload fresh
        for item in fetched:
            sr = item["score_result"]
            idx = df[df["id"] == item["row_id"]].index
            if idx.empty:
                print(f"  ⚠  Row ID {item['row_id']} not found in xlsx — skipping write")
                continue
            i = idx[0]
            df.at[i, "jd_text"]       = item["jd_text"]
            df.at[i, "url"]           = item["url"] or df.at[i, "url"]
            df.at[i, "url_hash"]      = _url_hash(item["url"]) if item["url"] else df.at[i, "url_hash"]
            df.at[i, "fit_score"]     = sr.get("fit_score")
            df.at[i, "fit_rationale"] = sr.get("fit_rationale")
            df.at[i, "role_type"]     = sr.get("role_type") or df.at[i, "role_type"]
            df.at[i, "status"]        = "queued" if sr.get("decision") == "Proceed" else "skipped"
            df.at[i, "notes"]         = (
                f"JD fetched via {item['path']} on {datetime.now().date()} "
                f"(originally: {df.at[i, 'notes'] or 'no JD'})"
            )

        save_jobs(df, dry_run=False)
        print(f"\n  ✓ Updated {len(fetched)} rows in jobs.xlsx")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Fetched + scored: {len(fetched)}")
    print(f"  Need manual paste: {len(paste_needed)}")

    if fetched:
        proceed = [f for f in fetched if f["score_result"].get("decision") == "Proceed"]
        print(f"  Queued (proceed): {len(proceed)}")
        for f in sorted(proceed, key=lambda x: x["score_result"].get("fit_score") or 0, reverse=True):
            score = f["score_result"].get("fit_score")
            print(f"    [{score}/10]  {f['company']} — {f['title']}")

    if paste_needed:
        print(f"\n  Manual paste instructions:")
        print(f"  1. Open each file below and paste the full JD text after the header")
        print(f"  2. Save the file")
        print(f"  3. Run:  python discovery/auto/jd_fetch.py --rescore-pastes")
        for row_id, company, title, paste_path in paste_needed:
            print(f"     → [{row_id}] {company} — {title[:50]}")
            print(f"        {paste_path.relative_to(_PROJ)}")

    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Rescore pastes
# ---------------------------------------------------------------------------

def run_rescore_pastes(args):
    """Re-score any paste files that now have content."""
    paste_files = load_paste_files()
    if not paste_files:
        print(f"No paste files with content found in {PASTE_DIR.relative_to(_PROJ)}")
        return

    print(f"\n{'='*60}")
    print(f"Rescoring {len(paste_files)} paste file(s)")
    print(f"{'='*60}")

    df      = load_jobs()
    api_key = _load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)
    model   = args.model or DEFAULT_MODEL

    updated = 0
    for row_id, jd_text in paste_files.items():
        idx = df[df["id"] == row_id].index
        if idx.empty:
            print(f"  ⚠  Row ID {row_id} not found in xlsx")
            continue

        i       = idx[0]
        company = str(df.at[i, "company"] or "")
        title   = str(df.at[i, "role_title"] or "")
        print(f"\n  [{row_id}] {company} — {title[:60]}")

        row          = df.iloc[i]
        score_result = rescore_row(row, jd_text, client, model)

        if not args.dry_run:
            df.at[i, "jd_text"]       = jd_text
            df.at[i, "fit_score"]     = score_result.get("fit_score")
            df.at[i, "fit_rationale"] = score_result.get("fit_rationale")
            df.at[i, "role_type"]     = score_result.get("role_type") or df.at[i, "role_type"]
            df.at[i, "status"]        = "queued" if score_result.get("decision") == "Proceed" else "skipped"
            df.at[i, "notes"]         = f"JD from manual paste on {datetime.now().date()}"
            updated += 1

    if updated and not args.dry_run:
        save_jobs(df, dry_run=False)
        print(f"\n  ✓ Updated {updated} rows in jobs.xlsx")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch missing JDs and re-score")
    parser.add_argument("--id",       type=str, default=None,
                        help="Comma-separated row IDs to retry (default: all screenshot rows with no JD)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Fetch and score but don't write to xlsx")
    parser.add_argument("--no-jobspy", action="store_true",
                        help="Skip Path A (JobSpy) — only try direct URL + paste")
    parser.add_argument("--rescore-pastes", action="store_true",
                        help="Re-score paste files that now have content")
    parser.add_argument("--model",    type=str, default=None,
                        help=f"Scoring model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if args.rescore_pastes:
        run_rescore_pastes(args)
    else:
        run_fetch(args)


if __name__ == "__main__":
    main()
