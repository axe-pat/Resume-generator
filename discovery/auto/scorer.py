"""
scorer.py — Claude Fit Scorer
-------------------------------
Takes a list of job dicts (from scraper.py) and scores each one against
Akshat's profile using Claude.

For each job it returns:
  fit_score      float  0.0–10.0  (normalised from 25-pt rubric)
  fit_rationale  str    one-sentence rationale from Claude
  role_type      str    PM / Strategy / Ops / TPM / Solutions / Other
  decision       str    Proceed / Reject / Deprioritize
  category       str    High Priority / Medium Priority / Low Priority / N/A
  breakdown      str    raw dimension breakdown string e.g. "PM Fit: 4 | Tech: 3 | ..."

Fast pre-filter (no API call):
  Catches obvious hard rejects from immigration keywords in the JD text
  before spending tokens. Claude still handles the nuanced cases.

Usage (standalone test):
    python scorer.py --test            # score 3 built-in mock JDs
    python scorer.py --jd path/to.txt  # score a single JD file

Called by pipeline.py for each batch of new jobs.
"""

import argparse
import os
import re
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import pandas as pd

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not found. Run: pip install anthropic")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE    = Path(__file__).parent            # discovery/auto/
_ROOT    = _HERE.parent                    # discovery/
PROFILE  = _ROOT.parent / "profile" / "profile.md"
SCORER   = _HERE / "scorer_prompt.md"
sys.path.insert(0, str(_ROOT.parent))
from shared.job_eligibility import (  # noqa: E402
    LANE_C,
    annotate_discovery_job,
    classify_role_surface,
    evaluate_lane_c,
    normalize_discovery_lane,
    pre_filter_discovery_scope,
    pre_filter_discovery_timing,
    pre_filter_full_time_level,
    pre_filter_immigration,
    pre_filter_role_type,
)

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------

# Haiku: fast + cheap (~$0.001/job). Fine for structured scoring.
# Swap to "claude-sonnet-4-6" if you want more nuanced scores.
DEFAULT_MODEL  = "claude-haiku-4-5-20251001"
MAX_TOKENS     = 400   # output is short — 6 structured lines
JD_CHAR_LIMIT  = 6000  # truncate very long JDs to save tokens
RETRY_ATTEMPTS = 5   # more attempts for rate-limit resilience (most will be 429 waits)
JD_CHROME_MARKERS = (
    "looking for talent?",
    "post a job",
    "linkedin corporation ©",
    "select language",
    "visit our help center",
    "manage your account and privacy",
    "recommendation transparency",
)
JD_SECTION_MARKERS = (
    "about the job",
    "responsibilities",
    "qualifications",
    "minimum qualifications",
    "preferred qualifications",
    "what you'll do",
    "job description",
)

# Thread-safe printing — used by score_job when called from ThreadPoolExecutor
_print_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _load_file(path: Path, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found at {path}. "
            f"Run from the ResumeGenerator v1/ root or check file paths."
        )
    return path.read_text(encoding="utf-8").strip()


def _as_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def _job_text(job: dict, key: str, default: str = "") -> str:
    value = _as_text(job.get(key, default))
    return value if value else default


def build_prompt(job: dict, profile_text: str, scorer_text: str) -> str:
    """
    Assemble the full prompt: scorer instructions + profile + JD.
    """
    jd_raw  = _job_text(job, "jd_text")
    jd_text = jd_raw[:JD_CHAR_LIMIT] + (" [truncated]" if len(jd_raw) > JD_CHAR_LIMIT else "")

    return f"""{scorer_text}

---

## Candidate Profile

{profile_text}

---

## Job Description to Evaluate

Company:    {_job_text(job, 'company', 'Unknown')}
Role Title: {_job_text(job, 'role_title', 'Unknown')}
Location:   {_job_text(job, 'location', 'Unknown')}
Source:     {_job_text(job, 'source', 'unknown')}
Lane:       {_job_text(job, 'lane', 'A')}
Start:      {_job_text(job, 'start_timing', 'unknown')}
Deadline:   {_job_text(job, 'application_deadline', 'not stated')}
E-Verify:   {_job_text(job, 'e_verify_status', 'not applicable/unknown')}

{jd_text}
"""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _extract(pattern: str, text: str, fallback: str = "") -> str:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else fallback


def parse_response(text: str) -> dict:
    """
    Parse Claude's structured output into a dict.

    Expected format (from scorer_prompt.md):
        Decision: Proceed
        Category: High Priority
        fit_score: 8.4
        Breakdown: PM Fit: 5 | Tech: 4 | Brand: 5 | Quality: 4 | Conversion: 3 | Total: 21/25
        Rationale: One sentence here.
        role_type: PM
    """
    decision  = _extract(r"^Decision:\s*(.+)$",   text, "Unknown")
    category  = _extract(r"^Category:\s*(.+)$",   text, "Unknown")
    breakdown = _extract(r"^Breakdown:\s*(.+)$",  text, "")
    rationale = _extract(r"^Rationale:\s*(.+)$",  text, "No rationale returned.")
    role_type = _extract(r"^role_type:\s*(.+)$",  text, "Other")

    # fit_score — extract float, clamp to [0, 10]
    raw_score = _extract(r"^fit_score:\s*([\d.]+)", text, "0.0")
    try:
        score = round(min(max(float(raw_score), 0.0), 10.0), 1)
    except ValueError:
        score = 0.0

    # Normalise decision/category casing
    decision  = decision.strip().title().replace("_", " ")
    role_type = role_type.strip()
    if role_type not in ("PM", "Strategy", "Ops", "TPM", "Solutions", "Other"):
        role_type = "Other"

    classification = "reject" if decision in {"Reject", "Deprioritize"} else "keep"
    if decision == "Unsure":
        classification = "unsure"
    return {
        "decision":  decision,
        "category":  category,
        "fit_score": score,
        "breakdown": breakdown,
        "fit_rationale": f"[{decision} | {category}] {rationale}",
        "role_type": role_type,
        "classification": classification,
        "reject_reason": rationale if classification in {"reject", "unsure"} else "",
        "_raw_response": text,
    }


def _rejected_result(reason: str) -> dict:
    return {
        "decision":      "Reject",
        "category":      "N/A",
        "fit_score":     0.0,
        "breakdown":     "PM Fit: 0 | Tech: 0 | Brand: 0 | Quality: 0 | Conversion: 0 | Total: 0/25",
        "fit_rationale": f"[Reject | N/A] {reason}",
        "role_type":     "Other",
        "_raw_response": f"Pre-filter: {reason}",
        "rejection_reason": reason,
        "classification": "reject",
        "reject_reason": reason,
    }


def _lane_c_result(
    eligible: bool,
    reason: str,
    hourly_low: float | None,
    hourly_high: float | None,
) -> dict:
    if not eligible:
        return _rejected_result(reason)
    rate = (
        f"${hourly_low:g}-${hourly_high:g}/hour"
        if hourly_low is not None and hourly_high is not None and hourly_high != hourly_low
        else f"${hourly_low:g}/hour"
    )
    return {
        "decision": "Proceed",
        "category": "Income Now",
        "fit_score": None,
        "breakdown": "Lane C: pay floor + shift compatibility",
        "fit_rationale": f"[Proceed | Income Now] {reason}; {rate}.",
        "role_type": "Other",
        "classification": "keep",
        "reject_reason": "",
        "_raw_response": f"Lane C deterministic filter: {reason}",
    }


def _unsure_result(reason: str, role_type: str = "Other") -> dict:
    return {
        "decision": "Unsure",
        "category": "Review",
        "fit_score": None,
        "breakdown": "Unscored: title/body review gate",
        "fit_rationale": f"[Unsure | Review] {reason}",
        "role_type": role_type if role_type in ("PM", "Strategy", "Ops", "TPM", "Solutions") else "Other",
        "classification": "unsure",
        "reject_reason": reason,
        "_raw_response": f"Discovery review gate: {reason}",
    }


def _error_result(error: str) -> dict:
    return {
        "decision":      "Error",
        "category":      "Unknown",
        "fit_score":     None,
        "breakdown":     "",
        "fit_rationale": f"[Scoring error] {error}",
        "role_type":     "Other",
        "_raw_response": f"Error: {error}",
    }


def _jd_quality_issue(jd_text: str) -> str:
    raw = _as_text(jd_text).strip()
    if not raw:
        return "empty"
    lower = raw.lower()
    chrome_hits = sum(marker in lower for marker in JD_CHROME_MARKERS)
    section_hits = sum(marker in lower for marker in JD_SECTION_MARKERS)
    if raw.startswith("Looking for talent?"):
        return "linkedin_chrome"
    if "linkedin corporation ©" in lower and section_hits == 0:
        return "linkedin_chrome"
    if chrome_hits >= 3 and section_hits == 0:
        return "linkedin_chrome"
    if chrome_hits >= 2 and len(raw) < 2200 and section_hits == 0:
        return "linkedin_chrome"
    return ""


# ---------------------------------------------------------------------------
# Core score function
# ---------------------------------------------------------------------------

def score_job(job: dict, client: anthropic.Anthropic | None,
              profile_text: str, scorer_text: str,
              model: str = DEFAULT_MODEL,
              verbose: bool = True,
              deadline_epoch: float | None = None) -> dict:
    """
    Score a single job dict. Returns a result dict with fit_score etc.
    Merges result back into the job dict and returns the enriched job.
    """
    company = _job_text(job, "company", "?")
    title   = _job_text(job, "role_title", "?")
    annotate_discovery_job(job)
    lane = normalize_discovery_lane(job.get("lane"))

    with _print_lock:
        if verbose:
            print(f"  Scoring: {company} — {title}")

    jd_text = _job_text(job, "jd_text")

    # ── Lane C: income-now gate; never pass through PM fit filters/scoring ───
    if lane == LANE_C:
        immigration_reject, immigration_reason = pre_filter_immigration(jd_text)
        if immigration_reject:
            result = _rejected_result(immigration_reason)
            job.update(result)
            job["status"] = "skipped"
            return job
        eligible, reason, hourly_low, hourly_high = evaluate_lane_c(
            title,
            jd_text,
            _job_text(job, "pay_text") or _job_text(job, "pay"),
        )
        result = _lane_c_result(eligible, reason, hourly_low, hourly_high)
        job.update(result)
        job["status"] = "review" if eligible else "skipped"
        with _print_lock:
            if verbose:
                symbol = "→" if eligible else "✗"
                print(f"    {symbol} Lane C deterministic gate: {reason}")
        return job

    # ── Pre-filter: lane timing and scope (no API call) ─────────────────────
    is_reject, reason = pre_filter_discovery_timing(title, jd_text, lane)
    if is_reject:
        result = _rejected_result(reason)
        job.update(result)
        job["status"] = "skipped"
        with _print_lock:
            if verbose:
                print(f"    ✗ Timing reject: {reason}")
        return job

    is_reject, reason = pre_filter_discovery_scope(title, lane)
    if is_reject:
        result = _rejected_result(reason)
        job.update(result)
        job["status"] = "skipped"
        with _print_lock:
            if verbose:
                print(f"    ✗ Scope reject: {reason}")
        return job

    # ── Pre-filter: role-type mismatch (title check — no API call) ───────────
    is_role_reject, role_reason = pre_filter_role_type(title)
    if is_role_reject:
        result = _rejected_result(role_reason)
        with _print_lock:
            if verbose:
                print(f"    ✗ Role-type reject: {role_reason}")
        job.update(result)
        job["status"] = "skipped"
        return job

    # ── Pre-filter: immigration ───────────────────────────────────────────────
    is_reject, reason = pre_filter_immigration(jd_text)
    if is_reject:
        result = _rejected_result(reason)
        with _print_lock:
            if verbose:
                print(f"    ✗ Pre-filter reject: {reason[:80]}")
        job.update(result)
        job["status"] = "skipped"
        return job

    # ── Pre-filter: full-time hire (not an internship) ────────────────────────
    # Module-level _INTERN_SIGNAL / _YEARS_REQUIRED are used (compiled once).
    is_reject, reason = pre_filter_full_time_level(title, jd_text)
    if is_reject:
        result = _rejected_result(reason)
        with _print_lock:
            if verbose:
                print(f"    ✗ Pre-filter reject: {reason}")
        job.update(result)
        job["status"] = "skipped"
        return job

    # ── Three-way discovery failure mode: keep / reject / unsure ─────────────
    disposition = str(job.get("discovery_disposition") or "keep").strip().lower()
    disposition_reason = str(job.get("discovery_reason") or "").strip()
    if disposition == "reject":
        reason = disposition_reason or "Discovery reject — no target role or JD-body signal"
        result = _rejected_result(reason)
        job.update(result)
        job["status"] = "skipped"
        with _print_lock:
            if verbose:
                print(f"    ✗ Discovery reject: {reason}")
        return job
    if disposition == "unsure":
        result = _unsure_result(
            disposition_reason or "Unknown title with target signals in the JD body",
            _job_text(job, "role_type", "Other"),
        )
        job.update(result)
        job["status"] = "review"
        with _print_lock:
            if verbose:
                print(f"    ? Unsure — review: {result['fit_rationale']}")
        return job

    # ── No JD text — can't score meaningfully ─────────────────────────────────
    if not jd_text.strip():
        result = _error_result("No JD text available — cannot score")
        with _print_lock:
            if verbose:
                print(f"    ⚠  No JD text — {company} / {title}")
        job.update(result)
        return job

    jd_issue = _jd_quality_issue(jd_text)
    if jd_issue == "linkedin_chrome":
        result = _error_result("Invalid JD capture — extracted LinkedIn shell/footer text")
        with _print_lock:
            if verbose:
                print(f"    ⚠  Bad JD capture — {company} / {title}")
        job.update(result)
        return job

    # ── Claude call (with retry) ───────────────────────────────────────────────
    if client is None:
        result = _error_result("Scoring client unavailable for Lane A/B role")
        job.update(result)
        return job

    prompt = build_prompt(job, profile_text, scorer_text)
    last_error = ""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        remaining = None if deadline_epoch is None else deadline_epoch - time.time()
        if remaining is not None and remaining <= 0:
            result = _error_result("Total pipeline wall-clock cap reached before API scoring completed")
            job.update(result)
            job["_run_timeout_unscored"] = True
            return job
        try:
            request_timeout = None if remaining is None else max(min(remaining, 60.0), 0.1)
            request_kwargs = {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            }
            if request_timeout is not None:
                request_kwargs["timeout"] = request_timeout
            response = client.messages.create(
                **request_kwargs,
            )
            raw = response.content[0].text.strip()
            result = parse_response(raw)
            surface_disposition, _, surface_family = classify_role_surface(title, jd_text)

            # The model occasionally turns generic "no visa sponsorship" boilerplate
            # into a hard F-1 rejection even though OPT itself needs no employer
            # sponsorship. Deterministic hard-reject checks already ran above, so keep
            # such contradictions visible for review instead of silently discarding them.
            invalid_sponsorship_reject = (
                lane == "B"
                and str(result.get("decision") or "").strip().lower() == "reject"
                and not pre_filter_immigration(jd_text)[0]
                and (
                    "sponsor" in jd_text.lower()
                    or "employment authorization" in jd_text.lower()
                )
                and (
                    "sponsor" in str(result.get("fit_rationale") or "").lower()
                    or "authorization" in str(result.get("fit_rationale") or "").lower()
                )
            )
            if invalid_sponsorship_reject:
                correction_prompt = (
                    prompt
                    + "\n\nCRITICAL CORRECTION: The JD does not explicitly exclude F-1, OPT, or CPT, "
                    "and the deterministic hard-immigration filter has passed it. Generic no-sponsorship "
                    "or no-new-employment-authorization-sponsorship language is a soft flag for Lane B. "
                    "You MUST score the role normally and may not reject it on immigration grounds."
                )
                correction_kwargs = dict(request_kwargs)
                correction_kwargs["messages"] = [
                    {"role": "user", "content": correction_prompt}
                ]
                corrected_response = client.messages.create(**correction_kwargs)
                corrected_raw = corrected_response.content[0].text.strip()
                corrected = parse_response(corrected_raw)
                corrected_still_invalid = (
                    str(corrected.get("decision") or "").strip().lower() == "reject"
                    and (
                        "sponsor" in str(corrected.get("fit_rationale") or "").lower()
                        or "authorization" in str(corrected.get("fit_rationale") or "").lower()
                    )
                )
                if corrected_still_invalid:
                    result = _unsure_result(
                        "Lane B sponsorship review — JD has generic no-sponsorship language "
                        "but does not explicitly exclude F-1, OPT, or CPT",
                        _job_text(job, "role_type", "Other"),
                    )
                    result["_raw_response"] = f"{raw}\n\nCORRECTION ATTEMPT:\n{corrected_raw}"
                else:
                    result = corrected
                    result["_raw_response"] = corrected_raw

            rationale_lower = str(result.get("fit_rationale") or "").lower()
            invalid_technical_gtm_reject = (
                lane == "B"
                and surface_disposition == "keep"
                and surface_family == "Technical GTM"
                and str(result.get("decision") or "").strip().lower() == "reject"
                and any(
                    phrase in rationale_lower
                    for phrase in (
                        "role type mismatch",
                        "outside",
                        "target scope",
                        "product ownership",
                        "sales execution",
                    )
                )
            )
            if invalid_technical_gtm_reject:
                correction_prompt = (
                    prompt
                    + "\n\nCRITICAL CORRECTION: This title is in the canonical Lane B Technical GTM "
                    "primary family. Sales Engineer and Technical Sales Engineer are explicit targets. "
                    "Technical GTM roles are not required to own a product roadmap; customer discovery, "
                    "technical solution design, demos, and hands-on enablement are the relevant ownership "
                    "signals. You MUST score the role normally and may not reject it merely as sales, "
                    "implementation, or for lacking product ownership."
                )
                correction_kwargs = dict(request_kwargs)
                correction_kwargs["messages"] = [
                    {"role": "user", "content": correction_prompt}
                ]
                corrected_response = client.messages.create(**correction_kwargs)
                corrected_raw = corrected_response.content[0].text.strip()
                corrected = parse_response(corrected_raw)
                corrected_rationale = str(corrected.get("fit_rationale") or "").lower()
                corrected_still_invalid = (
                    str(corrected.get("decision") or "").strip().lower() == "reject"
                    and any(
                        phrase in corrected_rationale
                        for phrase in (
                            "role type mismatch",
                            "outside",
                            "target scope",
                            "product ownership",
                            "sales execution",
                        )
                    )
                )
                if corrected_still_invalid:
                    result = _unsure_result(
                        "Technical GTM role-type review — canonical Lane B target was still rejected "
                        "by the model after correction",
                        "Solutions",
                    )
                    result["_raw_response"] = f"{raw}\n\nCORRECTION ATTEMPT:\n{corrected_raw}"
                else:
                    result = corrected
                    result["_raw_response"] = corrected_raw

            # A role-type correction can expose a second model error: turning
            # generic no-sponsorship boilerplate into an F-1/OPT hard reject.
            # The deterministic immigration gate above is authoritative.
            post_correction_sponsorship_reject = (
                lane == "B"
                and str(result.get("decision") or "").strip().lower() == "reject"
                and not pre_filter_immigration(jd_text)[0]
                and (
                    "sponsor" in str(result.get("fit_rationale") or "").lower()
                    or "authorization" in str(result.get("fit_rationale") or "").lower()
                    or "f-1" in str(result.get("fit_rationale") or "").lower()
                    or "opt" in str(result.get("fit_rationale") or "").lower()
                )
            )
            if post_correction_sponsorship_reject:
                previous_raw = str(result.get("_raw_response") or raw)
                result = _unsure_result(
                    "Lane B sponsorship review — JD has generic no-sponsorship language "
                    "but does not explicitly exclude F-1, OPT, or CPT",
                    "Solutions" if surface_family == "Technical GTM" else _job_text(job, "role_type", "Other"),
                )
                result["_raw_response"] = previous_raw

            with _print_lock:
                if verbose:
                    score_str = f"{result['fit_score']}/10" if result['fit_score'] is not None else "err"
                    print(f"    → {result['decision']} | {result['category']} | "
                          f"score={score_str} | {company} — {title}")
                    print(f"       {result['fit_rationale']}")

            job.update(result)

            # Auto-set status based on decision
            if result["decision"] == "Reject":
                job["status"] = "skipped"
            elif result["decision"] == "Unsure":
                job["status"] = "review"
            elif result["fit_score"] is not None and result["fit_score"] >= 0:
                job["status"] = "queued"

            return job

        except Exception as e:
            last_error = str(e)
            err_str    = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
            if is_rate_limit:
                job["_scoring_rate_limit_events"] = int(
                    job.get("_scoring_rate_limit_events") or 0
                ) + 1

            with _print_lock:
                if verbose:
                    tag = "rate-limit" if is_rate_limit else "error"
                    print(f"    ⚠  Attempt {attempt}/{RETRY_ATTEMPTS} [{tag}] ({company}): "
                          f"{err_str[:120]}")

            if attempt < RETRY_ATTEMPTS:
                if is_rate_limit:
                    # Exponential backoff: 60s → 120s → 240s → 480s
                    # 50K TPM limit + ~1800 tokens/job → need ~2.2s per job to stay under.
                    # After a burst trip, wait long enough for the bucket to meaningfully refill.
                    wait = min(60 * (2 ** (attempt - 1)), 480)
                    with _print_lock:
                        if verbose:
                            print(f"       Rate limit hit — waiting {wait}s before retry…")
                    if deadline_epoch is not None:
                        wait = min(wait, max(deadline_epoch - time.time(), 0))
                    if wait > 0:
                        time.sleep(wait)
                else:
                    wait = 3
                    if deadline_epoch is not None:
                        wait = min(wait, max(deadline_epoch - time.time(), 0))
                    if wait > 0:
                        time.sleep(wait)   # non-rate-limit errors: short wait then retry

    result = _error_result(f"All {RETRY_ATTEMPTS} attempts failed: {last_error}")
    job.update(result)
    return job


# ---------------------------------------------------------------------------
# Batch scorer (called by pipeline.py)
# ---------------------------------------------------------------------------

def score_batch(jobs: list[dict],
                client: anthropic.Anthropic | None = None,
                model: str = DEFAULT_MODEL,
                verbose: bool = True,
                max_workers: int = 2,
                deadline_epoch: float | None = None) -> list[dict]:
    """
    Score a list of job dicts. Returns the same list with scoring fields filled in.
    Uses ThreadPoolExecutor for parallel API calls.

    Args:
        jobs:        List of job dicts from scraper.py
        client:      Anthropic client (created from env if not provided)
        model:       Claude model string
        verbose:     Print per-job progress
        max_workers: Parallel API workers. Default 2 — keeps burst traffic below the
                     50K tokens/minute org rate limit (~1800 tokens/job → max ~27 jobs/min).
                     5 workers caused 321 rate-limit failures in the 168h run (2026-03-19).

    Returns:
        Same list with fit_score, fit_rationale, role_type, decision, category added,
        in the same order as input.
    """
    if not jobs:
        return []

    has_api_scoring_jobs = any(
        normalize_discovery_lane(job.get("lane")) != LANE_C for job in jobs
    )
    if client is None and has_api_scoring_jobs:
        api_key = _load_api_key()
        client  = anthropic.Anthropic(api_key=api_key)

    profile_text = _load_file(PROFILE, "profile.md")
    scorer_text  = _load_file(SCORER,  "scorer_prompt.md")

    if verbose:
        print(f"\n{'='*60}")
        print(f"Scorer — {len(jobs)} jobs | model: {model} | workers: {max_workers}")
        print(f"{'='*60}")

    # Pre-allocate output list to preserve input order
    scored: list[dict | None] = [None] * len(jobs)

    def _score_one(idx_job: tuple[int, dict]) -> tuple[int, dict]:
        idx, job = idx_job
        result = score_job(
            dict(job), client, profile_text, scorer_text,
            model=model, verbose=verbose, deadline_epoch=deadline_epoch,
        )
        return idx, result

    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = {
        executor.submit(_score_one, (i, job)): i
        for i, job in enumerate(jobs)
    }
    pending = set(futures)
    deadline_hit = False
    try:
        while pending:
            timeout = None
            if deadline_epoch is not None:
                timeout = max(0.0, deadline_epoch - time.time())
                if timeout <= 0:
                    deadline_hit = True
                    break
            done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
            if not done:
                deadline_hit = True
                break
            for future in done:
                try:
                    idx, result = future.result()
                    scored[idx] = result
                except Exception as exc:
                    # Shouldn't happen — score_job catches its own errors,
                    # but guard against unexpected executor failures.
                    orig_idx = futures[future]
                    scored[orig_idx] = dict(jobs[orig_idx])
                    scored[orig_idx].update(_error_result(f"Executor error: {exc}"))
                    with _print_lock:
                        print(f"  ✗ Executor error at index {orig_idx}: {exc}")
    finally:
        if deadline_hit:
            for future in pending:
                future.cancel()
            # Running API calls receive the same epoch deadline as their request
            # timeout, so they can be reaped without leaving non-daemon executor
            # threads alive after the pipeline has written its final report.
            executor.shutdown(wait=True, cancel_futures=True)
        else:
            executor.shutdown(wait=True)

    if deadline_hit:
        for idx, value in enumerate(scored):
            if value is None:
                timed_out = dict(jobs[idx])
                timed_out.update(_error_result("Total pipeline wall-clock cap reached before scoring completed"))
                timed_out["_run_timeout_unscored"] = True
                scored[idx] = timed_out
        if verbose:
            print("  ⚠  Total pipeline wall-clock cap reached during scoring; remaining rows marked Error")

    # Filter out any None slots (shouldn't occur, but be safe)
    scored = [j for j in scored if j is not None]

    # Summary
    if verbose:
        proceeds = [j for j in scored if j.get("decision") == "Proceed"]
        rejects  = [j for j in scored if j.get("decision") == "Reject"]
        unsure   = [j for j in scored if j.get("decision") == "Unsure"]
        errors   = [j for j in scored if j.get("decision") == "Error"]
        high     = [j for j in proceeds if j.get("category") == "High Priority"]
        mid      = [j for j in proceeds if j.get("category") == "Medium Priority"]
        income   = [j for j in proceeds if j.get("category") == "Income Now"]

        print(f"\n{'─'*60}")
        print(f"  Scored:      {len(scored)}")
        print(f"  Proceed:     {len(proceeds)}  "
              f"(High: {len(high)}  Mid: {len(mid)}  "
              f"Low: {len(proceeds) - len(high) - len(mid) - len(income)}"
              f"  Income Now: {len(income)})")
        print(f"  Rejected:    {len(rejects)}")
        print(f"  Unsure:      {len(unsure)}")
        print(f"  Errors:      {len(errors)}")
        if high:
            print(f"\n  Top picks:")
            top = sorted(high, key=lambda j: j.get("fit_score") or 0, reverse=True)
            for j in top[:5]:
                print(f"    [{j['fit_score']}/10] {j['company']} — {j['role_title']}")

    return scored


# ---------------------------------------------------------------------------
# API key loader (mirrors freeform_runner.py pattern)
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = _ROOT.parent / ".env"  # .env lives at ResumeGenerator v1/ root
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    print("ERROR: ANTHROPIC_API_KEY not found. Set it in .env or as env var.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI — standalone test
# ---------------------------------------------------------------------------

_MOCK_JDS = [
    {
        # Should score HIGH — clear PM role, top company, technical leverage
        "company": "Stripe", "role_title": "MBA Product Manager Intern",
        "location": "San Francisco, CA", "source": "linkedin",
        "jd_text": """
Stripe is looking for an MBA Product Manager Intern to join our Payments Platform team
for Summer 2026. You will own the roadmap for a core API surface used by millions of
developers, partner with engineering and design, and drive measurable improvements to
developer experience and transaction success rates. You'll define requirements, write
PRDs, run experiments, and present findings to senior leadership.

Requirements: MBA candidate (graduating 2026 or 2027), 3+ years prior experience in
software engineering, product, or strategy. Strong analytical skills. Experience with
APIs or developer-facing products a plus. We welcome applications from international
students on CPT/OPT.
        """,
    },
    {
        # Should score MEDIUM — adjacent role, decent company
        "company": "Rippling", "role_title": "Business Operations Intern (MBA)",
        "location": "New York, NY", "source": "indeed",
        "jd_text": """
Rippling is hiring a Business Operations Intern for our GTM Strategy team. You'll work
directly with the COO's office on special projects spanning market entry analysis,
pricing strategy, and cross-functional process design. This role requires strong
structured thinking and comfort with ambiguity. MBA candidates preferred.

Rippling is growing rapidly and this role offers high exposure to senior leadership.
No visa sponsorship available at this time.
        """,
    },
    {
        # Should REJECT — immigration hard reject
        "company": "Lockheed Martin", "role_title": "Product Manager Intern",
        "location": "Washington, DC", "source": "linkedin",
        "jd_text": """
Lockheed Martin is seeking a Product Manager Intern for our Defense Systems division.
You will support program managers on key defense contracts.

Requirements: Must be a US Citizen. Top Secret/SCI clearance required or ability to
obtain. Currently enrolled in accredited MBA program.
        """,
    },
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scorer — standalone test")
    parser.add_argument(
        "--test", action="store_true",
        help="Score 3 built-in mock JDs to validate output"
    )
    parser.add_argument(
        "--jd", type=str, default=None,
        help="Path to a .txt JD file to score"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})"
    )
    args = parser.parse_args()

    if args.jd:
        jd_path = Path(args.jd)
        if not jd_path.exists():
            print(f"ERROR: {jd_path} not found")
            sys.exit(1)
        jobs = [{
            "company":    jd_path.stem,
            "role_title": jd_path.stem,
            "location":   "Unknown",
            "source":     "manual",
            "jd_text":    jd_path.read_text(encoding="utf-8"),
        }]
    elif args.test:
        jobs = _MOCK_JDS
    else:
        parser.print_help()
        sys.exit(0)

    api_key = _load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)

    score_batch(jobs, client=client, model=args.model, verbose=True)
