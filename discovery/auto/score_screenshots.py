"""
score_screenshots.py — LinkedIn Screenshot → Score Flow
---------------------------------------------------------
Closes the personalization gap: LinkedIn's "In my network" + "Under 10
applicants" filters surface jobs that unauthenticated JobSpy can never
replicate. This script lets you drop LinkedIn search screenshots (as PDFs
or images) into manual_inputs/ and run them through the same scoring
pipeline.

Workflow:
  1. Read every PDF/PNG/JPG from discovery/manual/ (or --dir path)
  2. Use Claude Haiku vision to extract job listings (company, title, location)
  3. For each extracted job, search LinkedIn + Indeed via JobSpy to find the
     full JD (matched by title + location, filtered by company name)
  4. Score through scorer.py (same Claude model + prompt as cron runs)
  5. Dedup against existing jobs.xlsx entries (url_hash + company+title)
  6. Append new, scored jobs to jobs.xlsx
  7. Print a delta report: what this run found that cron missed

Usage:
    python discovery/auto/score_screenshots.py               # reads discovery/manual/
    python discovery/auto/score_screenshots.py --dir path/to/screenshots
    python discovery/auto/score_screenshots.py --dry-run     # score but don't write xlsx
    python discovery/auto/score_screenshots.py --hours-old 168  # widen JD search to 7 days
    python discovery/auto/score_screenshots.py --no-jd-fetch    # skip JobSpy, score title-only

Run from ResumeGenerator v1/ root.
"""

import argparse
import base64
import hashlib
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE         = Path(__file__).parent            # discovery/auto/
_ROOT         = _HERE.parent                    # discovery/
JOBS_XLSX     = _ROOT / "jobs.xlsx"
MANUAL_DIR    = _ROOT / "manual"
LOGS_DIR      = _HERE / "logs"
sys.path.insert(0, str(_HERE))

# ---------------------------------------------------------------------------
# Dependency imports
# ---------------------------------------------------------------------------

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not found. pip install anthropic")
    sys.exit(1)

try:
    import fitz  # PyMuPDF — for PDF→image conversion
except ImportError:
    print("ERROR: PyMuPDF not found. pip install pymupdf")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not found. pip install pandas")
    sys.exit(1)

try:
    from jobspy import scrape_jobs
except ImportError:
    print("ERROR: jobspy not found. pip install jobspy")
    sys.exit(1)

from scorer import score_batch, _load_api_key, _load_file, PROFILE, SCORER

# Re-use pipeline.py's xlsx helpers directly
from pipeline import (
    load_jobs, save_jobs, jobs_to_rows, get_existing_hashes, COLUMNS, _url_hash,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VISION_MODEL     = "claude-haiku-4-5-20251001"   # cheap vision model for extraction
VISION_MAX_TOKENS = 1500
JD_FETCH_HOURS   = None    # no time filter by default — targeted single-job lookups may be older than any rolling window
JD_RESULTS_WANTED = 15     # results to pull per company+title search (short list to match)
JD_FETCH_SLEEP   = 4       # seconds between JobSpy calls (rate limit courtesy)
COMPANY_MATCH_THRESHOLD = 0.6  # minimum fuzzy match ratio for company name

EXTRACTION_PROMPT = """You are extracting job listings from a LinkedIn job search screenshot.

List every job visible in the image. For each one output EXACTLY this format, one job per line:
COMPANY: <company name> | TITLE: <full job title> | LOCATION: <city, state or Remote>

Rules:
- Include ALL jobs you can see, even partially visible ones
- Use the company name exactly as shown (not the posting aggregator)
- Include the full job title as shown (do NOT truncate)
- If location is not visible, write: LOCATION: Unknown
- Do NOT include any other text, headers, or explanations

Output only the COMPANY/TITLE/LOCATION lines, nothing else."""


# ---------------------------------------------------------------------------
# PDF / image → base64 helper
# ---------------------------------------------------------------------------

def pdf_pages_to_b64(pdf_path: Path, dpi: int = 150) -> list[str]:
    """
    Convert each page of a PDF to a PNG and return as base64 strings.
    dpi=150 is enough for LinkedIn job cards — higher wastes tokens.
    """
    doc = fitz.open(str(pdf_path))
    pages_b64 = []
    for page in doc:
        pix    = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
        pages_b64.append(base64.standard_b64encode(png_bytes).decode("utf-8"))
    doc.close()
    return pages_b64


def image_to_b64(img_path: Path) -> str:
    """Return a PNG/JPG as base64."""
    return base64.standard_b64encode(img_path.read_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# Vision extraction
# ---------------------------------------------------------------------------

def extract_jobs_from_image(client: anthropic.Anthropic,
                             img_b64: str,
                             media_type: str = "image/png") -> list[dict]:
    """
    Send one screenshot image to Claude Haiku and extract job listings.
    Returns list of dicts: {company, role_title, location}.
    """
    try:
        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=VISION_MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type":   "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       img_b64,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
    except Exception as e:
        print(f"  ⚠  Vision API error: {e}")
        return []

    raw = response.content[0].text.strip()
    jobs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("COMPANY:"):
            continue
        # Parse: COMPANY: X | TITLE: Y | LOCATION: Z
        parts = {p.split(":", 1)[0].strip(): p.split(":", 1)[1].strip()
                 for p in line.split("|") if ":" in p}
        company = parts.get("COMPANY", "").strip()
        title   = parts.get("TITLE", "").strip()
        loc     = parts.get("LOCATION", "Unknown").strip()
        if company and title:
            jobs.append({"company": company, "role_title": title, "location": loc})

    return jobs


def extract_from_file(client: anthropic.Anthropic,
                      file_path: Path) -> list[dict]:
    """
    Extract job listings from a PDF, PNG, or JPEG file.
    Returns deduplicated list of job dicts.
    """
    suffix = file_path.suffix.lower()
    print(f"  📄 Extracting from: {file_path.name}")
    all_jobs = []

    if suffix == ".pdf":
        pages_b64 = pdf_pages_to_b64(file_path)
        for i, page_b64 in enumerate(pages_b64):
            jobs = extract_jobs_from_image(client, page_b64, "image/png")
            print(f"     Page {i+1}: extracted {len(jobs)} listings")
            all_jobs.extend(jobs)
    elif suffix in (".png", ".jpg", ".jpeg", ".webp"):
        media_map = {".png": "image/png", ".jpg": "image/jpeg",
                     ".jpeg": "image/jpeg", ".webp": "image/webp"}
        img_b64 = image_to_b64(file_path)
        all_jobs = extract_jobs_from_image(client, img_b64, media_map[suffix])
        print(f"     Extracted {len(all_jobs)} listings")
    else:
        print(f"     Skipping unsupported file type: {suffix}")

    # Dedup within this file (same company+title may appear on multiple pages)
    seen  = set()
    dedup = []
    for j in all_jobs:
        key = (j["company"].lower().strip(), j["role_title"].lower().strip())
        if key not in seen:
            seen.add(key)
            dedup.append(j)

    return dedup


# ---------------------------------------------------------------------------
# JD fetching via JobSpy
# ---------------------------------------------------------------------------

def _company_similarity(a: str, b: str) -> float:
    """Very simple token overlap similarity for company name matching."""
    a_tokens = set(re.sub(r"[^\w]", " ", a.lower()).split())
    b_tokens = set(re.sub(r"[^\w]", " ", b.lower()).split())
    # Remove common noise words
    noise = {"inc", "llc", "corp", "ltd", "co", "the", "and", "&", "technologies",
             "technology", "solutions", "services", "group", "global", "company"}
    a_tokens -= noise
    b_tokens -= noise
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / min(len(a_tokens), len(b_tokens))


def fetch_jd(company: str, title: str, location: str,
             hours_old: int | None = None) -> dict | None:
    """
    Search LinkedIn + Indeed for a specific job by title+location,
    then filter results by company name match.
    Returns the best-matching job dict from JobSpy, or None if not found.

    hours_old: None (default) = no time filter — correct for targeted single-job
               lookups where the posting may be older than the rolling scrape window.
               Pass an int only if you specifically want to limit recency.
    """
    loc = location if location and location.lower() != "unknown" else "United States"
    kwargs = dict(
        site_name=["linkedin", "indeed"],
        search_term=title,
        location=loc,
        results_wanted=JD_RESULTS_WANTED,
        linkedin_fetch_description=True,
    )
    if hours_old is not None:
        kwargs["hours_old"] = hours_old
    try:
        results = scrape_jobs(**kwargs)
    except Exception as e:
        print(f"    ⚠  JobSpy error for '{company} — {title}': {e}")
        return None

    if results is None or results.empty:
        return None

    # Find best company match
    best_row  = None
    best_score = 0.0
    for _, row in results.iterrows():
        sim = _company_similarity(company, str(row.get("company") or ""))
        if sim > best_score:
            best_score = sim
            best_row   = row

    if best_row is None or best_score < COMPANY_MATCH_THRESHOLD:
        return None

    # Convert pandas row to dict matching scraper schema
    row = best_row
    return {
        "company":     str(row.get("company") or company),
        "role_title":  str(row.get("title") or title),
        "location":    str(row.get("location") or location),
        "url":         str(row.get("job_url") or ""),
        "source":      "screenshot",                          # always screenshot — JobSpy is just the JD fetch mechanism
        "jd_text":     str(row.get("description") or ""),
        "date_found":  str(datetime.now().date()),
        "date_posted": str(row.get("date_posted") or ""),     # from JobSpy payload if available
    }


# ---------------------------------------------------------------------------
# Title+company hash for dedup (mirrors pipeline.py logic)
# ---------------------------------------------------------------------------

def _tc_hash(company: str, title: str) -> str:
    key = f"{company.strip().lower()}|{title.strip().lower()}"
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Delta report
# ---------------------------------------------------------------------------

def write_run_log(new_scored: list[dict], run_start: datetime,
                  input_dir: str, dry_run: bool) -> Path:
    """
    Write a structured log file for this screenshot run to discovery/auto/logs/.
    Mirrors the format used by pipeline.py run logs.
    Returns the log file path.
    """
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = run_start.strftime("%Y-%m-%d_%H%M")
    log_path  = LOGS_DIR / f"screenshots_{timestamp}.txt"
    elapsed   = (datetime.now() - run_start).seconds

    proceed  = [j for j in new_scored if j.get("decision") == "Proceed"]
    skipped  = [j for j in new_scored if j.get("decision") in ("Reject", "Deprioritize")]
    errors   = [j for j in new_scored if j.get("decision") in ("Error", None)]
    high     = sorted([j for j in proceed if j.get("category") == "High Priority"],
                      key=lambda j: j.get("fit_score") or 0, reverse=True)
    mid      = [j for j in proceed if j.get("category") == "Medium Priority"]
    no_jd    = [j for j in new_scored if not (j.get("jd_text") or "").strip()]

    lines = [
        f"Screenshot Run Log",
        f"{'='*60}",
        f"Run time:    {run_start.strftime('%Y-%m-%d %H:%M')}",
        f"Elapsed:     {elapsed}s",
        f"Source dir:  {input_dir}",
        f"Dry run:     {dry_run}",
        f"",
        f"── Summary ──────────────────────────────────────────────",
        f"New jobs extracted:  {len(new_scored)}",
        f"Queued (proceed):    {len(proceed)}  "
            f"[High: {len(high)}  Mid: {len(mid)}]",
        f"Rejected/skipped:    {len(skipped)}",
        f"No JD found:         {len(no_jd)}  (scored on title/company only)",
        f"Scoring errors:      {len(errors)}",
        f"",
    ]

    if high:
        lines += ["── High Priority (cron missed) ───────────────────────────"]
        for j in high:
            jd_flag = "" if (j.get("jd_text") or "").strip() else "  [no JD]"
            lines += [
                f"  [{j.get('fit_score')}/10]  {j.get('company')} — {j.get('role_title')}{jd_flag}",
                f"           {j.get('location')} | {j.get('source', 'screenshot')}",
                f"           {j.get('fit_rationale', '')}",
                f"",
            ]

    if mid:
        lines += ["── Medium Priority ───────────────────────────────────────"]
        for j in mid:
            jd_flag = "" if (j.get("jd_text") or "").strip() else "  [no JD]"
            lines += [
                f"  [{j.get('fit_score')}/10]  {j.get('company')} — {j.get('role_title')}{jd_flag}",
            ]
        lines += [""]

    if skipped:
        lines += ["── Rejected / Skipped ────────────────────────────────────"]
        for j in skipped:
            lines += [
                f"  ✗  {j.get('company')} — {j.get('role_title')}",
                f"     {j.get('fit_rationale', '')}",
            ]
        lines += [""]

    if no_jd:
        lines += ["── No JD Found (title-only scoring) ──────────────────────"]
        for j in no_jd:
            lines += [f"  ?  {j.get('company')} — {j.get('role_title')}"]
        lines += [""]

    lines += [f"{'='*60}", f"End of log"]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def print_delta_report(new_scored: list[dict], run_start: datetime) -> None:
    """
    Show what the screenshot run found that wasn't already in jobs.xlsx.
    Labelled 'delta' because the main purpose is catching cron-missed jobs.
    """
    elapsed = (datetime.now() - run_start).seconds
    proceed = [j for j in new_scored if j.get("decision") == "Proceed"]
    skipped = [j for j in new_scored if j.get("decision") in ("Reject", "Deprioritize")]
    errors  = [j for j in new_scored if j.get("decision") in ("Error", None)]
    high    = [j for j in proceed if j.get("category") == "High Priority"]
    mid     = [j for j in proceed if j.get("category") == "Medium Priority"]
    no_jd   = [j for j in new_scored if not (j.get("jd_text") or "").strip()]

    print(f"\n{'═'*60}")
    print(f"  Screenshot run complete  ({elapsed}s)")
    print(f"{'═'*60}")
    print(f"  New jobs extracted:  {len(new_scored)}")
    print(f"  Queued (proceed):    {len(proceed)}  "
          f"[High: {len(high)}  Mid: {len(mid)}]")
    print(f"  Rejected/skipped:    {len(skipped)}")
    print(f"  No JD found:         {len(no_jd)}  "
          f"(scored on title/company only — lower confidence)")
    print(f"  Scoring errors:      {len(errors)}")

    if high:
        print(f"\n  ★  New High Priority finds (cron missed these):")
        top = sorted(high, key=lambda j: j.get("fit_score") or 0, reverse=True)
        for j in top[:10]:
            score = j.get("fit_score") or "?"
            jd_flag = "" if (j.get("jd_text") or "").strip() else "  [no JD]"
            print(f"     [{score}/10]  {j.get('company')} — {j.get('role_title')}{jd_flag}")
            print(f"             {j.get('location')} | {j.get('source', 'screenshot')}")

    if mid:
        print(f"\n  ◆  Medium Priority:")
        for j in mid:
            score   = j.get("fit_score") or "?"
            jd_flag = "" if (j.get("jd_text") or "").strip() else "  [no JD]"
            print(f"     [{score}/10]  {j.get('company')} — {j.get('role_title')}{jd_flag}")

    if no_jd and len(no_jd) > len(errors):
        print(f"\n  ℹ  Tip: For jobs marked [no JD], paste the JD text into")
        print(f"      manual_inputs/<company>_<title>.txt and re-run for better scoring.")
    print(f"{'═'*60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Score LinkedIn screenshots manually")
    parser.add_argument("--dir",        type=str, default=str(MANUAL_DIR),
                        help="Directory containing screenshot PDFs/images")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Score but do not write to jobs.xlsx")
    parser.add_argument("--hours-old",  type=int, default=JD_FETCH_HOURS,
                        help="Lookback hours for JobSpy JD search (default: None = no time filter)")
    parser.add_argument("--no-jd-fetch", action="store_true",
                        help="Skip JobSpy; score on title+company only (fast, lower confidence)")
    parser.add_argument("--model",      type=str, default=None,
                        help="Override scoring model")
    args = parser.parse_args()

    run_start = datetime.now()
    input_dir = Path(args.dir)

    if not input_dir.exists():
        print(f"ERROR: {input_dir} does not exist. Create it and drop screenshots inside.")
        sys.exit(1)

    # Collect files
    supported = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    files = sorted(
        [f for f in input_dir.iterdir()
         if f.is_file() and f.suffix.lower() in supported],
        key=lambda f: f.stat().st_mtime,
    )
    if not files:
        print(f"No PDF/image files found in {input_dir}")
        print(f"Drop LinkedIn job search screenshots (PDF or PNG) into: {input_dir}")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"Screenshot Scorer  —  {len(files)} file(s)  —  {run_start.strftime('%H:%M')}")
    print(f"{'='*60}")

    # Load API key + client
    api_key = _load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)

    # Load existing xlsx to dedup against
    existing_df     = load_jobs()
    existing_hashes = get_existing_hashes(existing_df)  # url_hash set
    existing_tc     = set()  # title+company hash set
    for _, row in existing_df.iterrows():
        co = str(row.get("company") or "")
        ti = str(row.get("role_title") or "")
        if co and ti:
            existing_tc.add(_tc_hash(co, ti))

    # ── Step 1: Extract all jobs from screenshots ──────────────────────────
    print(f"\n── Extracting jobs from screenshots ──────────────────────────")
    all_extracted: list[dict] = []
    for f in files:
        jobs = extract_from_file(client, f)
        all_extracted.extend(jobs)

    # Dedup extracted jobs across all files
    seen_tc:  set[str] = set()
    unique_extracted: list[dict] = []
    for j in all_extracted:
        tc = _tc_hash(j["company"], j["role_title"])
        if tc not in seen_tc:
            seen_tc.add(tc)
            unique_extracted.append(j)

    print(f"\n  Extracted: {len(all_extracted)} total  →  {len(unique_extracted)} unique")

    # Drop rows with no usable company or title — vision couldn't read them, nothing to search for
    _UNKNOWN_VALS = {"unknown", "", "nan", "(job title not visible)", "n/a"}
    usable = []
    skipped_unknown = 0
    for j in unique_extracted:
        co = j.get("company", "").strip().lower()
        ti = j.get("role_title", "").strip().lower()
        if co in _UNKNOWN_VALS or ti in _UNKNOWN_VALS:
            skipped_unknown += 1
            print(f"  ⚠  Skipping (no usable company/title): {j.get('company')} — {j.get('role_title')}")
        else:
            usable.append(j)
    unique_extracted = usable
    if skipped_unknown:
        print(f"  Dropped {skipped_unknown} rows with unknown company or title")

    # Filter out already-in-xlsx jobs
    new_jobs = []
    already  = 0
    for j in unique_extracted:
        tc = _tc_hash(j["company"], j["role_title"])
        if tc in existing_tc:
            already += 1
        else:
            new_jobs.append(j)

    print(f"  Already in jobs.xlsx: {already}  →  {len(new_jobs)} new to process")

    if not new_jobs:
        print(f"\nAll extracted jobs already exist in jobs.xlsx. Nothing to do.")
        return

    # ── Step 2: Fetch JDs via JobSpy ──────────────────────────────────────
    if not args.no_jd_fetch:
        lookback_label = f"{args.hours_old}h lookback" if args.hours_old is not None else "no time filter"
        print(f"\n── Fetching JDs via JobSpy ({lookback_label}) ──────────────")
        fetched   = 0
        not_found = 0
        for j in new_jobs:
            print(f"  🔍 {j['company']} — {j['role_title'][:60]}")
            result = fetch_jd(j["company"], j["role_title"], j["location"],
                              hours_old=args.hours_old)
            if result and result.get("jd_text", "").strip():
                # Merge fetched fields into job dict (keep extracted company/title as fallback)
                # source stays "screenshot" — JobSpy site (linkedin/indeed) is just the JD fetch mechanism
                jd_site = result.get("source", "")   # only used for the print label
                j.update({
                    "url":         result.get("url", ""),
                    "source":      "screenshot",
                    "jd_text":     result["jd_text"],
                    "date_found":  result.get("date_found", str(datetime.now().date())),
                    "date_posted": result.get("date_posted", ""),
                    "url_hash":    _url_hash(result.get("url", "")) if result.get("url") else "",
                })
                print(f"     ✓ JD found ({len(result['jd_text'])} chars) via {jd_site}")
                fetched += 1
            else:
                j.setdefault("url", "")
                j.setdefault("source", "screenshot")
                j.setdefault("jd_text", "")
                j.setdefault("date_found", str(datetime.now().date()))
                j["url_hash"] = ""
                print(f"     ✗ JD not found — will score on title+company only")
                not_found += 1
            time.sleep(JD_FETCH_SLEEP)

        print(f"\n  JD fetch: {fetched} found, {not_found} not found")
    else:
        print(f"\n  --no-jd-fetch set — skipping JD search")
        for j in new_jobs:
            j.setdefault("url", "")
            j.setdefault("source", "screenshot")
            j.setdefault("jd_text", "")
            j.setdefault("date_found", str(datetime.now().date()))
            j["url_hash"] = ""

    # ── Step 3: Score all new jobs ─────────────────────────────────────────
    print(f"\n── Scoring {len(new_jobs)} jobs ─────────────────────────────────────")
    from scorer import DEFAULT_MODEL
    model = args.model or DEFAULT_MODEL

    scored = score_batch(new_jobs, client=client, model=model, verbose=True)

    # ── Step 4: Write to xlsx ─────────────────────────────────────────────
    # Dedup against url_hash before writing (in case JD fetch matched an existing URL)
    to_write = []
    for j in scored:
        uh = j.get("url_hash") or ""
        if uh and uh in existing_hashes:
            print(f"  ⚠  Skipping (url_hash already in xlsx): {j.get('company')} — {j.get('role_title')}")
            continue
        to_write.append(j)

    if to_write:
        start_id = int(existing_df["id"].dropna().astype(float).max() + 1) \
                   if not existing_df.empty and existing_df["id"].notna().any() else 1
        new_rows = jobs_to_rows(to_write, start_id=start_id)
        new_df   = pd.DataFrame(new_rows, columns=COLUMNS)
        combined = pd.concat([existing_df, new_df], ignore_index=True)

        # Mark source as screenshot where no URL was found
        combined.loc[combined["source"] == "screenshot", "notes"] = (
            "Added via score_screenshots.py — JD from JobSpy"
        )
        combined.loc[
            (combined["source"] == "screenshot") & (combined["jd_text"].fillna("") == ""),
            "notes"
        ] = "Added via score_screenshots.py — NO JD FETCHED (scored on title only)"

        save_jobs(combined, dry_run=args.dry_run)
        print(f"\n  ✓ Written {len(to_write)} new rows to jobs.xlsx")
    else:
        print(f"\n  All scored jobs already existed in xlsx after hash check.")

    # ── Step 5: Delta report + log ────────────────────────────────────────
    print_delta_report(scored, run_start)
    if not args.dry_run:
        log_path = write_run_log(scored, run_start, args.dir, args.dry_run)
        print(f"  Run log → {log_path}")


if __name__ == "__main__":
    main()
