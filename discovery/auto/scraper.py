"""
scraper.py — Job Discovery via JobSpy
--------------------------------------
Queries LinkedIn + Indeed across configured role clusters every run.
Returns a list of deduplicated job dicts ready for the pipeline.

Deduplication:
  - Primary:   MD5 hash of the canonical job URL
  - Secondary: MD5 hash of (company_lower + title_lower) — catches cross-posts
                with different URLs

Usage (standalone test):
    python scraper.py                     # run all queries, print summary
    python scraper.py --query-index 0     # run only query 0 (PM Intern)
    python scraper.py --hours-old 72      # widen lookback window

Called by pipeline.py for each scheduled run.
"""

import argparse
import hashlib
import re
import time
import traceback
from datetime import datetime

import pandas as pd
from jobspy import scrape_jobs

# ---------------------------------------------------------------------------
# Aggregator detection + real-company extraction
# ---------------------------------------------------------------------------

# Job aggregators that post listings on behalf of the real employer.
# When the scraped company matches one of these, we try to extract the actual
# company from the job description text.
AGGREGATOR_NAMES: set[str] = {
    "lensa", "the ladders", "ladders", "ziprecruiter", "zip recruiter",
    "handshake", "built in", "builtinnyc", "builtinsf", "built in nyc",
    "careerbuilder", "career builder", "monster", "simplyhired",
    "simply hired", "talent.com", "zippia", "jobscore", "otta",
    "wellfound", "angellist", "levels.fyi careers",
}

# Ordered patterns to find the real employer in JD text.
# Each pattern must have exactly one capture group — the company name.
_COMPANY_EXTRACT_PATS = [
    # "About Coinbase" as a section header (line-start or after newline)
    re.compile(r"(?:^|\n)\s*About\s+([A-Z][A-Za-z0-9 &.',()\-]{2,50})\s*(?:\n|$)", re.M),
    # "Join Coinbase as ..." / "Joining Coinbase's ..."
    re.compile(r"\bJoin(?:ing)?\s+([A-Z][A-Za-z0-9 &.',()\-]{2,40})\b"),
    # "At Coinbase, ..." / "At Coinbase we ..."
    re.compile(r"\bAt\s+([A-Z][A-Za-z0-9 &.',()\-]{2,40})[, ]"),
    # "Coinbase is looking / hiring / seeking ..."
    re.compile(r"\b([A-Z][A-Za-z0-9 &.',()\-]{2,40})\s+is\s+(?:looking for|hiring|seeking)\b"),
    # "Coinbase is a / an leading / top ..."
    re.compile(r"\b([A-Z][A-Za-z0-9 &.',()\-]{2,40})\s+is\s+(?:a |an )\w"),
    # "Working at / with Coinbase"
    re.compile(r"\bWorking\s+(?:at|with)\s+([A-Z][A-Za-z0-9 &.',()\-]{2,40})\b"),
    # "the team at Coinbase"
    re.compile(r"\bteam\s+at\s+([A-Z][A-Za-z0-9 &.',()\-]{2,40})\b"),
]

# Words that would make a false positive — don't return these as company names
_STOPWORDS = {
    "the", "a", "an", "this", "our", "we", "you", "your", "us", "here",
    "and", "or", "that", "it", "its", "with", "for", "from", "in", "on",
    "by", "as", "is", "are", "be", "to", "of", "at", "not", "but", "so",
}


def extract_company_from_jd(jd_text: str) -> str | None:
    """
    Attempt to extract the real employer name from aggregator JD text.
    Returns a cleaned company name string, or None if nothing convincing found.
    """
    if not jd_text:
        return None

    snippet = jd_text[:3000]   # only scan the opening section

    for pat in _COMPANY_EXTRACT_PATS:
        m = pat.search(snippet)
        if m:
            candidate = m.group(1).strip().rstrip(".,;:'\"")
            # Reject if it looks like a stopword or is very short/long
            if (len(candidate) < 2 or len(candidate) > 60
                    or candidate.lower() in _STOPWORDS
                    or candidate.lower() in AGGREGATOR_NAMES):
                continue
            return candidate

    return None

# ---------------------------------------------------------------------------
# Query configuration
# ---------------------------------------------------------------------------

# Query clusters covering the target role types from profile.md.
# Each cluster has a primary search term + the role types it covers.
# LinkedIn + Indeed run for every query. Glassdoor is skipped by default
# (slower, lower marginal yield for PM roles).

QUERIES = [
    {
        "id":          "pm_intern",
        "search_term": "Product Manager Intern",
        "covers":      ["PM Intern", "MBA PM Intern", "Technical PM Intern",
                        "APM Intern", "Platform PM Intern"],
        "role_type":   "PM",
    },
    {
        "id":          "product_ops_intern",
        "search_term": "Product Operations Intern",
        "covers":      ["Product Ops Intern", "Product Operations"],
        "role_type":   "Ops",
    },
    {
        "id":          "growth_intern",
        "search_term": "Growth Product Intern",
        "covers":      ["Growth Product Intern", "Product Growth Intern"],
        "role_type":   "Ops",
    },
    {
        "id":          "strategy_intern",
        "search_term": "Strategy Intern MBA",
        "covers":      ["Strategy Intern", "Business Strategy Intern",
                        "MBA Strategy Intern"],
        "role_type":   "Strategy",
    },
    {
        "id":          "bizops_intern",
        "search_term": "Business Operations Intern",
        "covers":      ["BizOps Intern", "Business Operations Intern"],
        "role_type":   "Ops",
    },
    {
        "id":          "tpm_intern",
        "search_term": "Program Manager Intern",
        "covers":      ["TPM Intern", "Technical Program Manager Intern",
                        "Program Manager Intern"],
        "role_type":   "TPM",
    },
    {
        "id":          "product_owner_intern",
        "search_term": "Product Owner Intern",
        "covers":      ["Product Owner Intern", "Agile Product Owner Intern"],
        "role_type":   "PM",
    },
    {
        "id":          "apm_intern",
        "search_term": "Associate Product Manager Intern",
        "covers":      ["APM Intern", "Associate Product Manager Intern",
                        "Associate PM Intern"],
        "role_type":   "PM",
    },
    {
        "id":          "ai_pm_intern",
        "search_term": "AI Product Manager Intern",
        "covers":      ["AI PM Intern", "AI Product Intern", "ML Product Intern",
                        "Machine Learning PM Intern", "GenAI PM Intern"],
        "role_type":   "PM",
    },
    {
        "id":          "mba_ai_strategy_intern",
        "search_term": "MBA AI Strategy Intern",
        "covers":      ["MBA AI Strategy Intern", "AI Strategy MBA Intern"],
        "role_type":   "Strategy",
    },
    {
        "id":          "mba_product_strategy_intern",
        "search_term": "Product Strategy Intern",
        "covers":      ["Product Strategy Intern", "MBA Product Strategy Intern",
                        "Product Strategy MBA Intern", "Product Strategist Intern"],
        "role_type":   "Strategy",
    },
    {
        "id":          "ai_strategy_ops_intern",
        "search_term": "AI Strategy Operations Intern",
        "covers":      ["AI Strategy & Operations Intern", "AI Ops Strategy Intern"],
        "role_type":   "Strategy",
    },
    {
        "id":          "growth_strategy_intern",
        "search_term": "Growth Strategy Intern",
        "covers":      ["Growth Strategy Intern", "User Growth Strategy Intern",
                        "Growth Strategy & Operations Intern"],
        "role_type":   "Strategy",
    },
]

# Sites to query per run
SITES = ["linkedin", "indeed"]

# Default lookback window in hours. 24h is safe for 3h run cadence
# (overlapping is fine — dedup handles it).
DEFAULT_HOURS_OLD = 24

# Results per query per site — scales with lookback window.
# LinkedIn relevance degrades sharply beyond ~150 results (rate limits + noise).
# 3h run:  few new jobs, 50 is plenty
# 24h run: 100 covers the bulk of the relevant universe
# 72h run: 150 worth going deeper since pool is 3x larger
# Override with get_results_wanted(hours_old) at call time.
RESULTS_WANTED = 100   # default for 24h runs

def get_results_wanted(hours_old: int) -> int:
    """Return appropriate RESULTS_WANTED for the given lookback window."""
    if hours_old <= 6:
        return 50
    elif hours_old <= 30:
        return 100
    else:
        return 150   # 48h, 72h — deeper scrape is worth it

# Seconds to sleep between queries to avoid hammering
INTER_QUERY_SLEEP = 8

# Cheap rejects applied before a JobSpy row enters the raw breadth artifact.
# This keeps the weekly lane from spending downstream validation/scoring time on
# categories that repeatedly dominate broad JobSpy results.
RAW_NOISE_TITLE_RE = re.compile(
    r"\b("
    r"pharmacy|pharmacist|pharmcst|pharm|"
    r"software (?:engineer|developer)|developer intern|security engineer|"
    r"data scientist|machine learning engineer|systems engineer|"
    r"human resources|hr intern|recruiter|talent acquisition|"
    r"account executive|sales representative|sales intern|social media|"
    r"marketing intern|product marketing manager|customer success|"
    r"facility|facilities|administrative|receptionist|summer camp"
    r")\b",
    re.I,
)

RAW_NOISE_COMPANY_RE = re.compile(
    r"\b("
    r"walgreens|cvs|dillons|kroger|jobright(?:\.ai)?|lensa|talentify|"
    r"robert half|randstad|insight global|teksystems"
    r")\b",
    re.I,
)

RAW_NOISE_JD_HEAD_RE = re.compile(
    r"\b("
    r"licensed pharmacist|pharmacy manager|dispense prescribed medications|"
    r"retail sales|cold call|commission|cash register|front desk"
    r")\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def _hash(text: str) -> str:
    """MD5 hash of a string — used for dedup."""
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def url_hash(url: str) -> str:
    return _hash(url)


def title_company_hash(title: str, company: str) -> str:
    return _hash(f"{title}||{company}")


# ---------------------------------------------------------------------------
# Row normalisation
# ---------------------------------------------------------------------------

def _normalise_row(row: pd.Series, query: dict) -> dict:
    """
    Convert a JobSpy DataFrame row into a clean dict matching jobs.xlsx schema.
    Handles missing / NaN fields gracefully.
    """
    def _str(val, fallback=""):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return fallback
        return str(val).strip()

    title   = _str(row.get("title"))
    company = _str(row.get("company"))
    jd_text = _str(row.get("description"))
    url     = _str(row.get("job_url"))

    # If the company is a known job aggregator, try to extract the real employer
    # from the job description so we store "Coinbase" not "Lensa".
    if company.lower().strip() in AGGREGATOR_NAMES:
        real_co = extract_company_from_jd(jd_text)
        if real_co:
            company = real_co

    # Prefer direct ATS URL if available (not a LinkedIn redirect)
    direct_url = _str(row.get("job_url_direct"))
    canonical_url = direct_url if direct_url and direct_url != url else url

    # Date posted — normalise to YYYY-MM-DD string
    raw_date = row.get("date_posted")
    if isinstance(raw_date, (datetime, pd.Timestamp)):
        date_found = raw_date.strftime("%Y-%m-%d")
    else:
        date_found = _str(raw_date) or datetime.today().strftime("%Y-%m-%d")

    return {
        "date_found":    datetime.today().strftime("%Y-%m-%d"),
        "date_posted":   date_found,   # YYYY-MM-DD the job was originally posted
        "company":       company,
        "role_title":    title,
        "role_type":     query["role_type"],
        "location":      _str(row.get("location")),
        "url":           canonical_url,
        "url_hash":      url_hash(canonical_url),
        "tc_hash":       title_company_hash(title, company),
        "source":        _str(row.get("site", "unknown")),
        "jd_text":       jd_text,
        "fit_score":     None,
        "fit_rationale": None,
        "status":        "new",
        "date_applied":  None,
        "folder_path":   None,
        "notes":         None,
        # JobSpy provenance for source tuning. These stay in raw artifacts and
        # are useful when auditing noisy queries.
        "jobspy_query_id": query["id"],
        "jobspy_search_term": query["search_term"],
        # Internal — used by older local scripts; keep for compatibility.
        "_query_id":     query["id"],
    }


def _is_raw_noise(job: dict) -> bool:
    title = str(job.get("role_title") or "")
    company = str(job.get("company") or "")
    jd_head = str(job.get("jd_text") or "")[:1200]
    return bool(
        RAW_NOISE_TITLE_RE.search(title)
        or RAW_NOISE_COMPANY_RE.search(company)
        or RAW_NOISE_JD_HEAD_RE.search(jd_head)
    )


# ---------------------------------------------------------------------------
# Single query runner
# ---------------------------------------------------------------------------

def run_query(query: dict, hours_old: int = DEFAULT_HOURS_OLD,
              results_override: int | None = None,
              verbose: bool = True) -> list[dict]:
    """
    Run one search query across SITES.
    Returns a list of normalised job dicts.
    Catches and logs errors per site so one failure doesn't kill the run.

    Args:
        results_override: If set, use this instead of get_results_wanted(hours_old).
                          Useful for one-off validation runs.
    """
    results = []

    n_results = results_override if results_override else get_results_wanted(hours_old)

    if verbose:
        print(f"  [{query['id']}] Searching: \"{query['search_term']}\" "
              f"(past {hours_old}h, {n_results} results/site)")

    try:
        df = scrape_jobs(
            site_name=SITES,
            search_term=query["search_term"],
            location="United States",
            results_wanted=n_results,
            hours_old=hours_old,
            country_indeed="USA",
            linkedin_fetch_description=True,   # fetch full LI description
            verbose=0,
        )

        if df is None or df.empty:
            if verbose:
                print("    → 0 results")
            return []

        skipped_raw_noise = 0
        for _, row in df.iterrows():
            job = _normalise_row(row, query)
            # Skip rows with no title, company, or URL — unusable
            if job["role_title"] and job["company"] and job["url"]:
                if _is_raw_noise(job):
                    skipped_raw_noise += 1
                    continue
                results.append(job)

        if verbose:
            suffix = f" ({skipped_raw_noise} obvious-noise skipped)" if skipped_raw_noise else ""
            print(f"    → {len(results)} raw results{suffix}")

    except Exception as e:
        print(f"    ✗ Query '{query['id']}' failed: {e}")
        if verbose:
            traceback.print_exc()

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(jobs: list[dict],
                existing_hashes: set[str] | None = None) -> list[dict]:
    """
    Remove duplicates from a list of job dicts.

    Two passes:
      1. Within-batch dedup (url_hash + tc_hash)
      2. Against existing_hashes (url_hashes already in jobs.xlsx)

    Returns deduplicated list, preserving first occurrence.
    """
    seen_url_hashes: set[str] = set(existing_hashes or [])
    seen_tc_hashes:  set[str] = set()
    unique = []

    for job in jobs:
        uh = job["url_hash"]
        th = job["tc_hash"]

        if uh in seen_url_hashes:
            continue
        if th in seen_tc_hashes:
            continue

        seen_url_hashes.add(uh)
        seen_tc_hashes.add(th)
        unique.append(job)

    return unique


# ---------------------------------------------------------------------------
# Main scrape function (called by pipeline.py)
# ---------------------------------------------------------------------------

def scrape(hours_old: int = DEFAULT_HOURS_OLD,
           query_indices: list[int] | None = None,
           existing_hashes: set[str] | None = None,
           results_override: int | None = None,
           verbose: bool = True) -> list[dict]:
    """
    Run all (or selected) queries and return deduplicated new jobs.

    Args:
        hours_old:        Lookback window in hours
        query_indices:    If set, only run these query indices (0-based)
        existing_hashes:  Set of url_hashes already in jobs.xlsx (for dedup)
        results_override: Override RESULTS_WANTED for all queries (e.g. 200 for validation)
        verbose:          Print progress

    Returns:
        List of job dicts — deduplicated, ready for scoring + xlsx write
    """
    queries_to_run = (
        [QUERIES[i] for i in query_indices]
        if query_indices is not None
        else QUERIES
    )

    n_display = results_override or get_results_wanted(hours_old)
    if verbose:
        print(f"\n{'='*60}")
        print(f"Scraper — {len(queries_to_run)} queries "
              f"({', '.join(SITES)}) | lookback: {hours_old}h | results/site: {n_display}")
        print(f"{'='*60}")

    all_jobs: list[dict] = []

    for i, query in enumerate(queries_to_run):
        batch = run_query(query, hours_old=hours_old,
                          results_override=results_override, verbose=verbose)
        all_jobs.extend(batch)

        # Polite sleep between queries (skip after last one)
        if i < len(queries_to_run) - 1:
            time.sleep(INTER_QUERY_SLEEP)

    if verbose:
        print(f"\n  Raw total:    {len(all_jobs)}")

    unique_jobs = deduplicate(all_jobs, existing_hashes=existing_hashes)

    if verbose:
        print(f"  After dedup:  {len(unique_jobs)} new jobs")
        by_type = {}
        for j in unique_jobs:
            rt = j["role_type"]
            by_type[rt] = by_type.get(rt, 0) + 1
        for rt, count in sorted(by_type.items()):
            print(f"    {rt}: {count}")

    return unique_jobs


# ---------------------------------------------------------------------------
# CLI (standalone testing)
# ---------------------------------------------------------------------------

def _print_job_summary(jobs: list[dict], n: int = 10) -> None:
    print(f"\n{'─'*60}")
    print(f"Sample results (first {min(n, len(jobs))}):")
    print(f"{'─'*60}")
    for job in jobs[:n]:
        jd_preview = (job["jd_text"][:80] + "…") if job["jd_text"] else "—"
        print(f"  [{job['role_type']}] {job['company']} — {job['role_title']}")
        print(f"         {job['location']} | {job['source']} | {job['url'][:60]}")
        print(f"         JD: {jd_preview}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper — standalone test")
    parser.add_argument(
        "--hours-old", type=int, default=DEFAULT_HOURS_OLD,
        help=f"Lookback window in hours (default: {DEFAULT_HOURS_OLD})"
    )
    parser.add_argument(
        "--query-index", type=int, default=None,
        help="Run only this query index (0–5). Omit for all queries."
    )
    parser.add_argument(
        "--show", type=int, default=10,
        help="Number of sample results to print (default: 10)"
    )
    args = parser.parse_args()

    query_indices = [args.query_index] if args.query_index is not None else None

    jobs = scrape(
        hours_old=args.hours_old,
        query_indices=query_indices,
        verbose=True,
    )

    _print_job_summary(jobs, n=args.show)

    print(f"\n{'='*60}")
    print(f"Total new jobs: {len(jobs)}")
    print(f"{'='*60}")
