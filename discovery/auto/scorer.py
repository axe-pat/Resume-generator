"""
scorer.py — Claude Fit Scorer
-------------------------------
Takes a list of job dicts (from scraper.py) and scores each one against
Akshat's profile using Claude.

For each job it returns:
  fit_score      float  0.0–10.0  (normalised from 25-pt rubric)
  fit_rationale  str    one-sentence rationale from Claude
  role_type      str    PM / Strategy / Ops / TPM / Other
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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


def build_prompt(job: dict, profile_text: str, scorer_text: str) -> str:
    """
    Assemble the full prompt: scorer instructions + profile + JD.
    """
    jd_raw  = job.get("jd_text") or ""
    jd_text = jd_raw[:JD_CHAR_LIMIT] + (" [truncated]" if len(jd_raw) > JD_CHAR_LIMIT else "")

    return f"""{scorer_text}

---

## Candidate Profile

{profile_text}

---

## Job Description to Evaluate

Company:    {job.get('company', 'Unknown')}
Role Title: {job.get('role_title', 'Unknown')}
Location:   {job.get('location', 'Unknown')}
Source:     {job.get('source', 'unknown')}

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
    if role_type not in ("PM", "Strategy", "Ops", "TPM", "Other"):
        role_type = "Other"

    return {
        "decision":  decision,
        "category":  category,
        "fit_score": score,
        "breakdown": breakdown,
        "fit_rationale": f"[{decision} | {category}] {rationale}",
        "role_type": role_type,
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


# ---------------------------------------------------------------------------
# Core score function
# ---------------------------------------------------------------------------

def score_job(job: dict, client: anthropic.Anthropic,
              profile_text: str, scorer_text: str,
              model: str = DEFAULT_MODEL,
              verbose: bool = True) -> dict:
    """
    Score a single job dict. Returns a result dict with fit_score etc.
    Merges result back into the job dict and returns the enriched job.
    """
    company = job.get("company", "?")
    title   = job.get("role_title", "?")

    with _print_lock:
        if verbose:
            print(f"  Scoring: {company} — {title}")

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
    is_reject, reason = pre_filter_immigration(job.get("jd_text") or "")
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
    is_reject, reason = pre_filter_full_time_level(title, job.get("jd_text") or "")
    if is_reject:
        result = _rejected_result(reason)
        with _print_lock:
            if verbose:
                print(f"    ✗ Pre-filter reject: {reason}")
        job.update(result)
        job["status"] = "skipped"
        return job

    # ── No JD text — can't score meaningfully ─────────────────────────────────
    if not (job.get("jd_text") or "").strip():
        result = _error_result("No JD text available — cannot score")
        with _print_lock:
            if verbose:
                print(f"    ⚠  No JD text — {company} / {title}")
        job.update(result)
        return job

    # ── Claude call (with retry) ───────────────────────────────────────────────
    prompt = build_prompt(job, profile_text, scorer_text)
    last_error = ""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            result = parse_response(raw)

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
            elif result["fit_score"] is not None and result["fit_score"] >= 0:
                job["status"] = "queued"

            return job

        except Exception as e:
            last_error = str(e)
            err_str    = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()

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
                    time.sleep(wait)
                else:
                    time.sleep(3)   # non-rate-limit errors: short wait then retry

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
                max_workers: int = 2) -> list[dict]:
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

    if client is None:
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
            job, client, profile_text, scorer_text,
            model=model, verbose=verbose,
        )
        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_score_one, (i, job)): i
            for i, job in enumerate(jobs)
        }
        for future in as_completed(futures):
            try:
                idx, result = future.result()
                scored[idx] = result
            except Exception as exc:
                # Shouldn't happen — score_job catches its own errors,
                # but guard against unexpected executor failures.
                orig_idx = futures[future]
                scored[orig_idx] = jobs[orig_idx]
                with _print_lock:
                    print(f"  ✗ Executor error at index {orig_idx}: {exc}")

    # Filter out any None slots (shouldn't occur, but be safe)
    scored = [j for j in scored if j is not None]

    # Summary
    if verbose:
        proceeds = [j for j in scored if j.get("decision") == "Proceed"]
        rejects  = [j for j in scored if j.get("decision") == "Reject"]
        errors   = [j for j in scored if j.get("decision") == "Error"]
        high     = [j for j in proceeds if j.get("category") == "High Priority"]
        mid      = [j for j in proceeds if j.get("category") == "Medium Priority"]

        print(f"\n{'─'*60}")
        print(f"  Scored:      {len(scored)}")
        print(f"  Proceed:     {len(proceeds)}  "
              f"(High: {len(high)}  Mid: {len(mid)}  "
              f"Low: {len(proceeds) - len(high) - len(mid)})")
        print(f"  Rejected:    {len(rejects)}")
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
