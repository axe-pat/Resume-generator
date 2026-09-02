"""
scraper.py — Job Discovery via JobSpy
--------------------------------------
Queries LinkedIn + Indeed across explicit Lane A and Lane B role clusters every run.
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
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from jobspy import scrape_jobs

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.job_eligibility import (  # noqa: E402
    annotate_discovery_job,
)

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

LANE_A_QUERIES = [
    {
        "id":          "pm_intern",
        "search_term": "Product Manager Intern",
        "covers":      ["PM Intern", "MBA PM Intern", "Technical PM Intern",
                        "APM Intern", "Platform PM Intern"],
        "role_type":   "PM",
        "lane":        "A",
    },
    {
        "id":          "product_ops_intern",
        "search_term": "Product Operations Intern",
        "covers":      ["Product Ops Intern", "Product Operations"],
        "role_type":   "Ops",
        "lane":        "A",
    },
    {
        "id":          "growth_intern",
        "search_term": "Growth Product Intern",
        "covers":      ["Growth Product Intern", "Product Growth Intern"],
        "role_type":   "Ops",
        "lane":        "A",
    },
    {
        "id":          "strategy_intern",
        "search_term": "Strategy Intern MBA",
        "covers":      ["Strategy Intern", "Business Strategy Intern",
                        "MBA Strategy Intern"],
        "role_type":   "Strategy",
        "lane":        "A",
    },
    {
        "id":          "bizops_intern",
        "search_term": "Business Operations Intern",
        "covers":      ["BizOps Intern", "Business Operations Intern"],
        "role_type":   "Ops",
        "lane":        "A",
    },
    {
        "id":          "tpm_intern",
        "search_term": "Program Manager Intern",
        "covers":      ["TPM Intern", "Technical Program Manager Intern",
                        "Program Manager Intern"],
        "role_type":   "TPM",
        "lane":        "A",
    },
    {
        "id":          "product_owner_intern",
        "search_term": "Product Owner Intern",
        "covers":      ["Product Owner Intern", "Agile Product Owner Intern"],
        "role_type":   "PM",
        "lane":        "A",
    },
    {
        "id":          "apm_intern",
        "search_term": "Associate Product Manager Intern",
        "covers":      ["APM Intern", "Associate Product Manager Intern",
                        "Associate PM Intern"],
        "role_type":   "PM",
        "lane":        "A",
    },
    {
        "id":          "ai_pm_intern",
        "search_term": "AI Product Manager Intern",
        "covers":      ["AI PM Intern", "AI Product Intern", "ML Product Intern",
                        "Machine Learning PM Intern", "GenAI PM Intern"],
        "role_type":   "PM",
        "lane":        "A",
    },
    {
        "id":          "mba_ai_strategy_intern",
        "search_term": "MBA AI Strategy Intern",
        "covers":      ["MBA AI Strategy Intern", "AI Strategy MBA Intern"],
        "role_type":   "Strategy",
        "lane":        "A",
    },
    {
        "id":          "mba_product_strategy_intern",
        "search_term": "Product Strategy Intern",
        "covers":      ["Product Strategy Intern", "MBA Product Strategy Intern",
                        "Product Strategy MBA Intern", "Product Strategist Intern"],
        "role_type":   "Strategy",
        "lane":        "A",
    },
    {
        "id":          "ai_strategy_ops_intern",
        "search_term": "AI Strategy Operations Intern",
        "covers":      ["AI Strategy & Operations Intern", "AI Ops Strategy Intern"],
        "role_type":   "Strategy",
        "lane":        "A",
    },
    {
        "id":          "growth_strategy_intern",
        "search_term": "Growth Strategy Intern",
        "covers":      ["Growth Strategy Intern", "User Growth Strategy Intern",
                        "Growth Strategy & Operations Intern"],
        "role_type":   "Strategy",
        "lane":        "A",
    },
]

# Lane B deliberately includes regular versions of the forward-deployed family.
# The timing gate rejects immediate-start postings and exposes that dropped volume.
LANE_B_QUERIES = [
    {
        "id": "new_grad_pm",
        "search_term": "New Grad Product Manager",
        "covers": ["Product Manager New Grad", "2027 Product Manager"],
        "role_type": "PM",
        "lane": "B",
    },
    {
        "id": "apm_2027",
        "search_term": "APM 2027",
        "covers": ["Associate Product Manager 2027", "APM New Grad"],
        "role_type": "PM",
        "lane": "B",
    },
    {
        "id": "associate_pm_new_grad",
        "search_term": "Associate Product Manager New Grad",
        "covers": ["Associate Product Manager New Grad"],
        "role_type": "PM",
        "lane": "B",
    },
    {
        "id": "pm_university_grad",
        "search_term": "Product Manager University Graduate",
        "covers": ["Product Manager University Graduate"],
        "role_type": "PM",
        "lane": "B",
    },
    {
        "id": "technical_pm_new_grad",
        "search_term": "Technical Product Manager New Grad",
        "covers": ["Technical Product Manager New Grad"],
        "role_type": "PM",
        "lane": "B",
    },
    {
        "id": "product_ops_new_grad",
        "search_term": "Product Operations New Grad",
        "covers": ["Product Operations New Grad", "Product Ops Analyst New Grad"],
        "role_type": "Ops",
        "lane": "B",
    },
    {
        "id": "strategy_ops_new_grad",
        "search_term": "Strategy Operations New Grad",
        "covers": ["Strategy & Operations New Grad"],
        "role_type": "Strategy",
        "lane": "B",
    },
    {
        "id": "bizops_analyst_new_grad",
        "search_term": "Business Operations Analyst New Grad",
        "covers": ["Business Operations Analyst New Grad", "BizOps New Grad"],
        "role_type": "Ops",
        "lane": "B",
    },
    {
        "id": "corporate_strategy_new_grad",
        "search_term": "Corporate Strategy New Grad",
        "covers": ["Corporate Strategy Analyst New Grad"],
        "role_type": "Strategy",
        "lane": "B",
    },
    {
        "id": "tpm_new_grad",
        "search_term": "Technical Program Manager New Grad",
        "covers": ["Technical Program Manager New Grad", "TPM New Grad"],
        "role_type": "TPM",
        "lane": "B",
    },
    {
        "id": "program_manager_new_grad",
        "search_term": "Program Manager New Grad",
        "covers": ["Program Manager New Grad"],
        "role_type": "TPM",
        "lane": "B",
    },
    {
        "id": "mba_leadership_development",
        "search_term": "MBA Leadership Development Program",
        "covers": ["MBA Leadership Development Program"],
        "role_type": "Strategy",
        "lane": "B",
    },
    {
        "id": "rotational_program",
        "search_term": "Rotational Program",
        "covers": ["Rotational Program", "Graduate Rotational Program"],
        "role_type": "Strategy",
        "lane": "B",
    },
    {
        "id": "general_management_rotational",
        "search_term": "General Management Rotational Program",
        "covers": ["General Management Rotational Program"],
        "role_type": "Strategy",
        "lane": "B",
    },
    {
        "id": "forward_deployed_engineer",
        "search_term": "Forward Deployed Engineer",
        "covers": ["Forward Deployed Engineer"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "solutions_engineer",
        "search_term": "Solutions Engineer",
        "covers": ["Solutions Engineer"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "applied_ai_engineer",
        "search_term": "Applied AI Engineer",
        "covers": ["Applied AI Engineer"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "solutions_architect",
        "search_term": "Solutions Architect",
        "covers": ["Solutions Architect"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "deployment_engineer",
        "search_term": "Deployment Engineer",
        "covers": ["Deployment Engineer", "Forward Deployed Software Engineer"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "technical_solutions_consultant",
        "search_term": "Technical Solutions Consultant",
        "covers": ["Technical Solutions Consultant"],
        "role_type": "Solutions",
        "lane": "B",
    },
    {
        "id": "partner_engineer",
        "search_term": "Partner Engineer",
        "covers": ["Partner Engineer"],
        "role_type": "Solutions",
        "lane": "B",
    },
]

_EXPANDED_LANE_B_QUERY_SPECS = [
    ("product_analyst_new_grad", "Product Analyst New Grad", ["Product Analyst"], "PM"),
    ("business_program_manager_new_grad", "Business Program Manager New Grad", ["Business Program Manager"], "TPM"),
    ("business_planning_ops_new_grad", "Business Planning Operations New Grad", ["Business Planning & Operations", "BP&O"], "Ops"),
    ("corporate_development_new_grad", "Corporate Development New Grad", ["Corporate Development"], "Strategy"),
    ("revenue_operations_new_grad", "Revenue Operations New Grad", ["Revenue Operations", "RevOps"], "Ops"),
    ("gtm_strategy_ops_new_grad", "GTM Strategy Operations New Grad", ["GTM Strategy & Operations"], "Strategy"),
    ("special_projects_new_grad", "Special Projects New Grad", ["Special Projects"], "Strategy"),
    ("product_strategy_ops_new_grad", "Product Strategy Operations New Grad", ["Product Strategy", "Product Strategy & Operations"], "Strategy"),
    ("sales_engineer", "Sales Engineer", ["Sales Engineer", "Pre-Sales Engineer"], "Solutions"),
    ("customer_engineer", "Customer Engineer", ["Customer Engineer"], "Solutions"),
    ("partner_solutions_architect", "Partner Solutions Architect", ["Partner Solutions Architect"], "Solutions"),
    ("technical_account_manager", "Technical Account Manager", ["Technical Account Manager"], "Solutions"),
    ("implementation_engineer", "Implementation Engineer", ["Implementation Engineer"], "Solutions"),
    ("implementation_consultant", "Implementation Consultant", ["Implementation Consultant"], "Solutions"),
    ("deployment_strategist", "Deployment Strategist", ["Deployment Strategist"], "Solutions"),
    ("field_engineer", "Field Engineer", ["Field Engineer"], "Solutions"),
    ("value_engineer", "Value Engineer", ["Value Engineer"], "Solutions"),
    ("rotational_product_manager_2027", "Rotational Product Manager 2027", ["Rotational Product Manager", "Meta RPM"], "PM"),
    ("product_management_leadership", "Product Management Leadership Program", ["Product Management Leadership Program"], "PM"),
    ("business_leadership_mba", "Business Leadership Program MBA", ["Business Leadership Program"], "Strategy"),
    ("technology_leadership_mba", "Technology Leadership Program MBA", ["Technology Leadership Program"], "Strategy"),
    ("pathways_operations_mba", "Pathways Operations Manager MBA", ["Pathways Operations Manager"], "Ops"),
    ("strategic_product_lead", "Strategic Product Lead", ["Strategic Product Lead"], "PM"),
    ("strategic_partner_manager", "Strategic Partner Manager", ["Strategic Partner Manager"], "Strategy"),
    ("strategic_partnerships_lead", "Strategic Partnerships Lead", ["Strategic Partnerships Lead"], "Strategy"),
    ("data_platform_pm_new_grad", "Data Platform Product Manager New Grad", ["Data Product Manager", "Platform Product Manager", "Infrastructure Product Manager", "Developer Platform Product Manager"], "PM"),
]

LANE_B_QUERIES.extend(
    {
        "id": query_id,
        "search_term": search_term,
        "covers": covers,
        "role_type": role_type,
        "lane": "B",
    }
    for query_id, search_term, covers, role_type in _EXPANDED_LANE_B_QUERY_SPECS
)

QUERY_PACKS = {
    "A": LANE_A_QUERIES,
    "B": LANE_B_QUERIES,
}
QUERIES = [*LANE_A_QUERIES, *LANE_B_QUERIES]

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
DEFAULT_QUERY_TIMEOUT_SECONDS = 120
DEFAULT_RUN_TIMEOUT_SECONDS = 5400
CHECKPOINTS_DIR = Path(__file__).parent / "checkpoints"

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

    originating_site = _str(row.get("site", "unknown")) or "unknown"
    job = {
        "date_found":    datetime.today().strftime("%Y-%m-%d"),
        "date_posted":   date_found,   # YYYY-MM-DD the job was originally posted
        "company":       company,
        "role_title":    title,
        "role_type":     query["role_type"],
        "location":      _str(row.get("location")),
        "url":           canonical_url,
        "url_hash":      url_hash(canonical_url),
        "tc_hash":       title_company_hash(title, company),
        # JobSpy is a filtered discovery path. The originating board is
        # provenance, not the queue-routing source tag.
        "source":        "jobspy_filtered_v1",
        "jd_text":       jd_text,
        "fit_score":     None,
        "fit_rationale": None,
        "status":        "new",
        "date_applied":  None,
        "folder_path":   None,
        "notes":         f"originating_site={originating_site}",
        "lane":          query["lane"],
        "query_lane":    query["lane"],
        # JobSpy provenance for source tuning. These stay in raw artifacts and
        # are useful when auditing noisy queries.
        "jobspy_query_id": query["id"],
        "jobspy_search_term": query["search_term"],
        # Internal — used by older local scripts; keep for compatibility.
        "_query_id":     query["id"],
    }
    annotate_discovery_job(job, default_lane=query["lane"])
    timing = str(job.get("start_timing") or "")
    if timing in {
        "summer_2027_internship",
        "other_2027_internship",
        "fall_2026_internship",
        "internship_unspecified",
    }:
        job["lane"] = "A"
    elif timing in {
        "immediate_full_time",
        "mid_2027_or_later_full_time",
        "new_grad_eligible",
        "full_time_unspecified",
    }:
        job["lane"] = "B"
    annotate_discovery_job(job, default_lane=query["lane"])
    return job


def _raw_noise_reason(job: dict) -> str:
    title = str(job.get("role_title") or "")
    company = str(job.get("company") or "")
    jd_head = str(job.get("jd_text") or "")[:1200]
    company_match = RAW_NOISE_COMPANY_RE.search(company)
    if company_match:
        return f"Raw source reject — noisy recruiter/aggregator company: '{company_match.group(0)}'"
    title_match = RAW_NOISE_TITLE_RE.search(title)
    if title_match and str(job.get("role_family") or "") != "Technical GTM":
        return f"Raw source reject — out-of-scope title signal: '{title_match.group(0)}'"
    jd_match = RAW_NOISE_JD_HEAD_RE.search(jd_head)
    if jd_match:
        return f"Raw source reject — out-of-scope JD signal: '{jd_match.group(0)}'"
    return ""


def _is_raw_noise(job: dict) -> bool:
    return bool(_raw_noise_reason(job))


# ---------------------------------------------------------------------------
# Single query runner
# ---------------------------------------------------------------------------

def run_query(query: dict, hours_old: int = DEFAULT_HOURS_OLD,
              results_override: int | None = None,
              verbose: bool = True,
              raise_errors: bool = False) -> list[dict]:
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
                raw_noise_reason = _raw_noise_reason(job)
                if raw_noise_reason:
                    skipped_raw_noise += 1
                    job["discovery_disposition"] = "reject"
                    job["discovery_reason"] = raw_noise_reason
                    job["classification"] = "reject"
                    job["reject_reason"] = raw_noise_reason
                results.append(job)

        if verbose:
            suffix = f" ({skipped_raw_noise} obvious-noise rows retained as rejects)" if skipped_raw_noise else ""
            print(f"    → {len(results)} raw results{suffix}")

    except Exception as e:
        if raise_errors:
            raise
        print(f"    ✗ Query '{query['id']}' failed: {e}")
        if verbose:
            traceback.print_exc()

    return results


def _write_json_checkpoint(path: Path, payload: dict) -> None:
    """Atomically write a checkpoint so an interrupted parent never sees half JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _wait_process_wall_clock(process: subprocess.Popen, timeout_seconds: float) -> int:
    """Wait using epoch time so closed-lid sleep still counts toward the cap."""
    deadline_epoch = time.time() + max(timeout_seconds, 0.1)
    while True:
        remaining = deadline_epoch - time.time()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout_seconds)
        try:
            return process.wait(timeout=min(1.0, remaining))
        except subprocess.TimeoutExpired:
            continue


def _query_worker(query_index: int, hours_old: int,
                  results_override: int | None, output_path: Path) -> int:
    """Isolated JobSpy worker. The parent may terminate this process on timeout."""
    started = time.time()
    query = QUERIES[query_index]
    try:
        jobs = run_query(
            query,
            hours_old=hours_old,
            results_override=results_override,
            verbose=False,
            raise_errors=True,
        )
        payload = {
            "status": "completed",
            "query_index": query_index,
            "query_id": query["id"],
            "lane": query["lane"],
            "search_term": query["search_term"],
            "elapsed_seconds": round(time.time() - started, 3),
            "result_count": len(jobs),
            "jobs": jobs,
            "error": "",
        }
        exit_code = 0
    except BaseException as exc:
        payload = {
            "status": "failed",
            "query_index": query_index,
            "query_id": query["id"],
            "lane": query["lane"],
            "search_term": query["search_term"],
            "elapsed_seconds": round(time.time() - started, 3),
            "result_count": 0,
            "jobs": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
        exit_code = 1
    _write_json_checkpoint(output_path, payload)
    return exit_code


def _read_checkpoint(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "failed", "jobs": [], "error": f"Unreadable checkpoint: {exc}"}


def run_query_with_timeout(
    query_index: int,
    *,
    hours_old: int,
    results_override: int | None,
    timeout_seconds: float,
    checkpoint_path: Path,
    log_path: Path,
) -> dict:
    """Run one query in a killable subprocess and return its checkpoint payload."""
    query = QUERIES[query_index]
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-query-index",
        str(query_index),
        "--worker-output",
        str(checkpoint_path),
        "--hours-old",
        str(hours_old),
    ]
    if results_override is not None:
        command.extend(["--worker-results", str(results_override)])

    started = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as query_log:
        process = subprocess.Popen(
            command,
            stdout=query_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            exit_code = _wait_process_wall_clock(process, timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                _wait_process_wall_clock(process, 5)
            except subprocess.TimeoutExpired:
                process.kill()
                _wait_process_wall_clock(process, 5)
            payload = {
                "status": "timed_out",
                "query_index": query_index,
                "query_id": query["id"],
                "lane": query["lane"],
                "search_term": query["search_term"],
                "elapsed_seconds": round(time.time() - started, 3),
                "result_count": 0,
                "jobs": [],
                "error": f"Hard query timeout after {timeout_seconds:.1f}s",
            }
            _write_json_checkpoint(checkpoint_path, payload)
            exit_code = 124

    payload = _read_checkpoint(checkpoint_path)
    payload.setdefault("query_index", query_index)
    payload.setdefault("query_id", query["id"])
    payload.setdefault("lane", query["lane"])
    payload.setdefault("search_term", query["search_term"])
    payload.setdefault("elapsed_seconds", round(time.time() - started, 3))
    payload.setdefault("result_count", 0)
    payload.setdefault("jobs", [])
    payload.setdefault("error", "")
    if exit_code and payload.get("status") == "completed":
        payload["status"] = "failed"
        payload["error"] = f"Worker exited with code {exit_code}"

    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    payload["throttle_events"] = len(
        re.findall(r"\b(?:429|rate.?limit(?:ed)?|throttl(?:e|ed|ing))\b", log_text, re.I)
    )
    payload["checkpoint_file"] = str(checkpoint_path)
    payload["log_file"] = str(log_path)
    return payload


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
           verbose: bool = True,
           per_query_timeout_seconds: int = DEFAULT_QUERY_TIMEOUT_SECONDS,
           total_timeout_seconds: int = DEFAULT_RUN_TIMEOUT_SECONDS,
           checkpoint_dir: Path | None = None,
           run_report: dict | None = None) -> list[dict]:
    """
    Run all (or selected) queries and return deduplicated new jobs.

    Args:
        hours_old:        Lookback window in hours
        query_indices:    If set, only run these query indices (0-based)
        existing_hashes:  Set of url_hashes already in jobs.xlsx (for dedup)
        results_override: Override RESULTS_WANTED for all queries (e.g. 200 for validation)
        verbose:          Print progress
        per_query_timeout_seconds: Hard wall-clock cap for each isolated JobSpy query
        total_timeout_seconds: Wall-clock cap for the complete scrape stage
        checkpoint_dir:   Optional run checkpoint directory
        run_report:       Optional dict populated with query outcomes and runtime

    Returns:
        List of job dicts — deduplicated, ready for scoring + xlsx write
    """
    selected_indices = list(query_indices) if query_indices is not None else list(range(len(QUERIES)))
    queries_to_run = [QUERIES[i] for i in selected_indices]
    scrape_started = time.time()
    checkpoint_root = checkpoint_dir or (
        CHECKPOINTS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    )
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    manifest_path = checkpoint_root / "manifest.json"
    manifest = {
        "schema": "resume_generator.discovery_query_checkpoint",
        "version": 1,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "hours_old": hours_old,
        "results_per_site": results_override or get_results_wanted(hours_old),
        "per_query_timeout_seconds": per_query_timeout_seconds,
        "total_timeout_seconds": total_timeout_seconds,
        "requested_query_indices": selected_indices,
        "queries": [],
        "status": "running",
    }
    _write_json_checkpoint(manifest_path, manifest)

    n_display = results_override or get_results_wanted(hours_old)
    if verbose:
        print(f"\n{'='*60}")
        print(f"Scraper — {len(queries_to_run)} queries "
              f"({', '.join(SITES)}) | lookback: {hours_old}h | results/site: {n_display}")
        print(f"{'='*60}")

    all_jobs: list[dict] = []

    run_cap_hit = False
    for i, (query_index, query) in enumerate(zip(selected_indices, queries_to_run)):
        elapsed = time.time() - scrape_started
        remaining = total_timeout_seconds - elapsed
        if remaining <= 0:
            run_cap_hit = True
            break

        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", query["id"])
        checkpoint_path = checkpoint_root / f"query_{query_index:02d}_{safe_id}.json"
        query_log_path = checkpoint_root / f"query_{query_index:02d}_{safe_id}.log"
        effective_timeout = min(float(per_query_timeout_seconds), max(remaining, 0.1))

        if verbose:
            print(
                f"  [{query['id']}] Searching: \"{query['search_term']}\" "
                f"(past {hours_old}h, {n_display} results/site; timeout {effective_timeout:.0f}s)",
                flush=True,
            )

        outcome = run_query_with_timeout(
            query_index,
            hours_old=hours_old,
            results_override=results_override,
            timeout_seconds=effective_timeout,
            checkpoint_path=checkpoint_path,
            log_path=query_log_path,
        )
        batch = list(outcome.pop("jobs", []) or [])
        all_jobs.extend(batch)
        outcome["checkpoint_file"] = str(Path(outcome["checkpoint_file"]).relative_to(checkpoint_root))
        outcome["log_file"] = str(Path(outcome["log_file"]).relative_to(checkpoint_root))
        manifest["queries"].append(outcome)
        manifest["elapsed_seconds"] = round(time.time() - scrape_started, 3)
        _write_json_checkpoint(manifest_path, manifest)

        if verbose:
            status = outcome.get("status", "failed")
            if status == "completed":
                print(
                    f"    → {len(batch)} raw results in {outcome.get('elapsed_seconds', 0):.1f}s "
                    f"(checkpointed)",
                    flush=True,
                )
            else:
                print(
                    f"    ✗ {status}: {outcome.get('error', 'unknown error')} — skipped, checkpointed",
                    flush=True,
                )

        # Polite sleep between queries (skip after last one)
        if i < len(queries_to_run) - 1:
            remaining = total_timeout_seconds - (time.time() - scrape_started)
            if remaining <= 0:
                run_cap_hit = True
                break
            time.sleep(min(INTER_QUERY_SLEEP, max(remaining, 0)))

    completed_indices = {record["query_index"] for record in manifest["queries"]}
    if run_cap_hit:
        for query_index in selected_indices:
            if query_index in completed_indices:
                continue
            query = QUERIES[query_index]
            manifest["queries"].append(
                {
                    "status": "skipped_run_timeout",
                    "query_index": query_index,
                    "query_id": query["id"],
                    "lane": query["lane"],
                    "search_term": query["search_term"],
                    "elapsed_seconds": 0,
                    "result_count": 0,
                    "error": "Total scrape wall-clock cap reached before query start",
                    "throttle_events": 0,
                    "checkpoint_file": "",
                    "log_file": "",
                }
            )

    if verbose:
        print(f"\n  Raw total:    {len(all_jobs)}")

    unique_jobs = deduplicate(all_jobs, existing_hashes=existing_hashes)

    status_counts: dict[str, int] = {}
    for record in manifest["queries"]:
        status = str(record.get("status") or "failed")
        status_counts[status] = status_counts.get(status, 0) + 1
    manifest.update(
        {
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": round(time.time() - scrape_started, 3),
            "status": "partial" if run_cap_hit or status_counts.get("timed_out") or status_counts.get("failed") else "completed",
            "run_cap_hit": run_cap_hit,
            "query_status_counts": status_counts,
            "throttle_events": sum(int(record.get("throttle_events") or 0) for record in manifest["queries"]),
            "raw_result_count": len(all_jobs),
            "deduplicated_new_job_count": len(unique_jobs),
        }
    )
    _write_json_checkpoint(manifest_path, manifest)
    if run_report is not None:
        run_report.clear()
        run_report.update(manifest)
        run_report["checkpoint_dir"] = str(checkpoint_root)

    if verbose:
        print(f"  After dedup:  {len(unique_jobs)} new jobs")
        by_type = {}
        by_lane = {}
        for j in unique_jobs:
            rt = j["role_type"]
            by_type[rt] = by_type.get(rt, 0) + 1
            lane = j.get("lane", "?")
            by_lane[lane] = by_lane.get(lane, 0) + 1
        for lane, count in sorted(by_lane.items()):
            print(f"    Lane {lane}: {count}")
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
        help=f"Run only this query index (0–{len(QUERIES) - 1}). Omit for all queries."
    )
    parser.add_argument(
        "--show", type=int, default=10,
        help="Number of sample results to print (default: 10)"
    )
    parser.add_argument(
        "--query-timeout", type=int, default=DEFAULT_QUERY_TIMEOUT_SECONDS,
        help=f"Hard timeout per query in seconds (default: {DEFAULT_QUERY_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--run-timeout", type=int, default=DEFAULT_RUN_TIMEOUT_SECONDS,
        help=f"Total scrape timeout in seconds (default: {DEFAULT_RUN_TIMEOUT_SECONDS})",
    )
    parser.add_argument("--worker-query-index", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker-results", type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_query_index is not None:
        if args.worker_output is None:
            parser.error("--worker-output is required with --worker-query-index")
        raise SystemExit(
            _query_worker(
                args.worker_query_index,
                args.hours_old,
                args.worker_results,
                args.worker_output,
            )
        )

    query_indices = [args.query_index] if args.query_index is not None else None

    jobs = scrape(
        hours_old=args.hours_old,
        query_indices=query_indices,
        per_query_timeout_seconds=max(args.query_timeout, 1),
        total_timeout_seconds=max(args.run_timeout, 1),
        verbose=True,
    )

    _print_job_summary(jobs, n=args.show)

    print(f"\n{'='*60}")
    print(f"Total new jobs: {len(jobs)}")
    print(f"{'='*60}")
