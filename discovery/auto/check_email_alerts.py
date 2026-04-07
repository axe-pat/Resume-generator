"""
check_email_alerts.py — Gmail LinkedIn Alert → Score Flow
----------------------------------------------------------
Reads unread LinkedIn job alert emails from Gmail, extracts job listings,
fetches JDs via JobSpy, scores through the same pipeline, and writes to
jobs.xlsx. This is the automation path that captures LinkedIn's profile-
based relevance ranking — closer to "authenticated" results without a login.

LinkedIn alert emails (from jobs-noreply@linkedin.com) contain:
  - Job title, company, location
  - Direct LinkedIn job URL (linkedin.com/jobs/view/JOBID)

This script processes those emails, fetches the full JDs, and scores them.

Setup (one-time):
  1. Gmail → Settings → See all settings → Forwarding and POP/IMAP
     → Enable IMAP
  2. Google Account → Security → 2-Step Verification → App passwords
     → Create one for "Mail" / "Other" → copy the 16-char password
  3. Add to .env (ResumeGenerator v1/ root):
         GMAIL_ADDRESS=your@gmail.com
         GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (with or without spaces)
  4. On LinkedIn: Jobs → Job alerts → make sure you have an alert for
     "Product Manager Intern" or similar (weekly/daily digest)

Usage:
    python discovery/auto/check_email_alerts.py                # process new alerts
    python discovery/auto/check_email_alerts.py --dry-run      # don't write xlsx
    python discovery/auto/check_email_alerts.py --days 7       # look back 7 days of emails
    python discovery/auto/check_email_alerts.py --no-mark-read # leave emails unread
    python discovery/auto/check_email_alerts.py --verbose      # extra debug output

Run from ResumeGenerator v1/ root.
"""

import argparse
import email
import hashlib
import imaplib
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE    = Path(__file__).parent
_ROOT    = _HERE.parent
JOBS_XLSX = _ROOT / "jobs.xlsx"
LOGS_DIR  = _HERE / "logs"
sys.path.insert(0, str(_HERE))

# ---------------------------------------------------------------------------
# Dependency imports
# ---------------------------------------------------------------------------

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not found. pip install beautifulsoup4")
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

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not found. pip install anthropic")
    sys.exit(1)

from scorer import score_batch, _load_api_key
from pipeline import load_jobs, save_jobs, jobs_to_rows, get_existing_hashes, COLUMNS, _url_hash

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GMAIL_IMAP_HOST    = "imap.gmail.com"
GMAIL_IMAP_PORT    = 993
LINKEDIN_SENDER    = "jobs-noreply@linkedin.com"
DEFAULT_LOOKBACK_DAYS = 3        # how many days of email to scan per run
JD_FETCH_HOURS     = 168         # JobSpy lookback for JD fetching (7 days)
JD_RESULTS_WANTED  = 10          # results to compare when matching JD
JD_FETCH_SLEEP     = 4           # seconds between JobSpy calls
COMPANY_MATCH_THRESHOLD = 0.5    # fuzzy company match threshold


# ---------------------------------------------------------------------------
# Credential loader
# ---------------------------------------------------------------------------

def _load_credentials() -> tuple[str, str]:
    """
    Load Gmail address and app password from env or .env file.
    Returns (gmail_address, app_password).
    """
    def _from_env_file():
        env_path = _ROOT.parent / ".env"  # .env lives at ResumeGenerator v1/ root
        result = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip().strip('"').strip("'")
        return result

    env_vars = _from_env_file()

    address  = os.environ.get("GMAIL_ADDRESS") or env_vars.get("GMAIL_ADDRESS", "")
    password = os.environ.get("GMAIL_APP_PASSWORD") or env_vars.get("GMAIL_APP_PASSWORD", "")

    # Normalise app password — remove spaces (Google shows it as "xxxx xxxx xxxx xxxx")
    password = password.replace(" ", "")

    if not address or not password:
        print("\nERROR: Gmail credentials not found.")
        print("Add these to ResumeGenerator v1/.env:")
        print("   GMAIL_ADDRESS=your@gmail.com")
        print("   GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx")
        print("\nTo get an App Password:")
        print("   Gmail → Settings → IMAP → Enable")
        print("   Google Account → Security → 2-Step Verification → App passwords")
        sys.exit(1)

    return address, password


# ---------------------------------------------------------------------------
# Gmail IMAP helpers
# ---------------------------------------------------------------------------

def connect_gmail(address: str, password: str) -> imaplib.IMAP4_SSL:
    """Open an IMAP connection to Gmail. Returns the connection object."""
    try:
        conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        conn.login(address, password)
        return conn
    except imaplib.IMAP4.error as e:
        print(f"\nERROR: Gmail login failed: {e}")
        print("Check your App Password and that IMAP is enabled in Gmail settings.")
        sys.exit(1)


def fetch_linkedin_alert_emails(conn: imaplib.IMAP4_SSL,
                                 days_back: int = DEFAULT_LOOKBACK_DAYS,
                                 verbose: bool = False) -> list[email.message.Message]:
    """
    Fetch unread LinkedIn job alert emails from the past N days.
    Returns list of parsed email.message.Message objects.
    """
    conn.select("INBOX")

    # Search: unread + from LinkedIn jobs sender + recent
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
    search_criteria = f'(UNSEEN FROM "{LINKEDIN_SENDER}" SINCE {since_date})'

    _, msg_nums_raw = conn.search(None, search_criteria)
    msg_nums = msg_nums_raw[0].split()

    if verbose:
        print(f"  Found {len(msg_nums)} unread LinkedIn alert email(s) in past {days_back} days")

    messages = []
    for num in msg_nums:
        _, msg_data = conn.fetch(num, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        messages.append((num, msg))

    return messages


def mark_as_read(conn: imaplib.IMAP4_SSL, msg_num: bytes) -> None:
    """Mark a specific email as read (remove \\Unseen flag)."""
    conn.store(msg_num, "+FLAGS", "\\Seen")


# ---------------------------------------------------------------------------
# Email HTML parser — extract job listings from LinkedIn alert email body
# ---------------------------------------------------------------------------

# LinkedIn job URLs in emails: href="https://www.linkedin.com/jobs/view/JOBID..."
_LINKEDIN_JOB_URL_PAT = re.compile(
    r'https://www\.linkedin\.com/jobs/view/(\d+)[^"]*',
    re.IGNORECASE,
)

# After clicking "View job", LinkedIn uses tracking URLs that redirect.
# We extract the raw job view URL directly from the href.
_LI_JOB_PATH_PAT = re.compile(r'/jobs/view/(\d+)')


def _decode_str(s: str | bytes) -> str:
    """Decode email header values."""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    return s


def get_email_html(msg: email.message.Message) -> str | None:
    """Extract HTML body from a multipart email."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
    elif msg.get_content_type() == "text/html":
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")
    return None


def parse_linkedin_email(msg: email.message.Message,
                          verbose: bool = False) -> list[dict]:
    """
    Parse a LinkedIn job alert email and extract job listings.

    LinkedIn alert emails contain job cards structured as:
      <a href="...linkedin.com/jobs/view/JOBID...">Job Title</a>
      <span>Company Name</span>
      <span>Location</span>

    Returns list of dicts: {company, role_title, location, url, linkedin_job_id}
    """
    html = get_email_html(msg)
    if not html:
        if verbose:
            print("    ⚠  No HTML body found in email")
        return []

    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen_ids = set()

    # Strategy 1: Find all LinkedIn job view links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        url_match = _LINKEDIN_JOB_URL_PAT.search(href)
        if not url_match:
            continue

        job_id = url_match.group(1)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        clean_url = f"https://www.linkedin.com/jobs/view/{job_id}"

        # The job title is usually the anchor text, or in a nearby element
        title_text = a_tag.get_text(strip=True)

        # Company and location: look in surrounding context
        company = ""
        location = ""

        # Try parent container
        parent = a_tag.find_parent(["td", "div", "tr", "li"])
        if parent:
            all_text = [t.get_text(strip=True) for t in parent.find_all(["span", "p", "div"])
                        if t.get_text(strip=True) and len(t.get_text(strip=True)) < 80]
            # First non-empty non-title text tends to be company, then location
            candidates = [t for t in all_text if t and t != title_text]
            if candidates:
                company = candidates[0] if len(candidates) > 0 else ""
                location = candidates[1] if len(candidates) > 1 else ""

        if not title_text or len(title_text) < 5:
            continue

        jobs.append({
            "company":        company or "Unknown",
            "role_title":     title_text,
            "location":       location or "Unknown",
            "url":            clean_url,
            "linkedin_job_id": job_id,
            "source":         "email_alert",
            "date_found":     str(datetime.now().date()),
        })

    if verbose and not jobs:
        # Fallback debug: show what links were in the email
        all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        li_links = [l for l in all_links if "linkedin.com" in l]
        print(f"    LinkedIn links found: {len(li_links)}")

    return jobs


# ---------------------------------------------------------------------------
# JD fetching via JobSpy (by title + location, matching company)
# ---------------------------------------------------------------------------

def _company_similarity(a: str, b: str) -> float:
    a_tokens = set(re.sub(r"[^\w]", " ", a.lower()).split())
    b_tokens = set(re.sub(r"[^\w]", " ", b.lower()).split())
    noise = {"inc", "llc", "corp", "ltd", "co", "the", "and", "&",
             "technologies", "technology", "solutions", "services", "group"}
    a_tokens -= noise
    b_tokens -= noise
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / min(len(a_tokens), len(b_tokens))


def fetch_jd_for_job(job: dict,
                     hours_old: int = JD_FETCH_HOURS,
                     verbose: bool = False) -> str:
    """
    Search LinkedIn for the job's title + location to find the full JD.
    Returns JD text string (empty string if not found).
    """
    title   = job.get("role_title", "")
    company = job.get("company", "")
    loc     = job.get("location", "")
    if not loc or loc.lower() == "unknown":
        loc = "United States"

    try:
        results = scrape_jobs(
            site_name=["linkedin"],
            search_term=title,
            location=loc,
            results_wanted=JD_RESULTS_WANTED,
            hours_old=hours_old,
            linkedin_fetch_description=True,
            verbose=0,
        )
    except Exception as e:
        if verbose:
            print(f"    ⚠  JobSpy error: {e}")
        return ""

    if results is None or results.empty:
        return ""

    # Find best company match
    best_jd    = ""
    best_score = 0.0
    for _, row in results.iterrows():
        sim = _company_similarity(company, str(row.get("company") or ""))
        jd  = str(row.get("description") or "")
        if sim > best_score and jd.strip():
            best_score = sim
            best_jd    = jd
            # Also update the URL if we found a better match
            if row.get("job_url"):
                job["url"]      = str(row["job_url"])
                job["url_hash"] = _url_hash(str(row["job_url"]))

    if best_score >= COMPANY_MATCH_THRESHOLD:
        if verbose:
            print(f"    ✓ JD fetched ({len(best_jd)} chars, match={best_score:.2f})")
        return best_jd
    else:
        if verbose:
            print(f"    ✗ No JD match found (best company sim={best_score:.2f})")
        return ""


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def _tc_hash(company: str, title: str) -> str:
    key = f"{company.strip().lower()}|{title.strip().lower()}"
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Log writer
# ---------------------------------------------------------------------------

def write_email_log(processed_jobs: list[dict], emails_scanned: int,
                    run_start: datetime) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    ts       = run_start.strftime("%Y-%m-%d_%H%M")
    log_path = LOGS_DIR / f"email_run_{ts}.txt"
    elapsed  = (datetime.now() - run_start).seconds

    proceed = [j for j in processed_jobs if j.get("decision") == "Proceed"]
    high    = sorted([j for j in proceed if j.get("category") == "High Priority"],
                     key=lambda j: j.get("fit_score") or 0, reverse=True)
    mid     = [j for j in proceed if j.get("category") == "Medium Priority"]

    lines = [
        "Email Alert Run Log",
        "=" * 60,
        f"Run time:      {run_start.strftime('%Y-%m-%d %H:%M')}",
        f"Elapsed:       {elapsed}s",
        f"Emails scanned:{emails_scanned}",
        f"Jobs extracted:{len(processed_jobs)}",
        "",
        "── Summary ──────────────────────────────────────────────",
        f"Queued (proceed): {len(proceed)}  "
            f"[High: {len(high)}  Mid: {len(mid)}]",
        f"Rejected/skipped: {len([j for j in processed_jobs if j.get('decision') == 'Reject'])}",
        "",
    ]
    if high:
        lines.append("── High Priority ─────────────────────────────────────────")
        for j in high:
            lines += [
                f"  [{j['fit_score']}/10]  {j['company']} — {j['role_title']}",
                f"           {j.get('location', '')}",
                f"           {j.get('fit_rationale', '')}",
                f"           {j.get('url', '')}",
                "",
            ]

    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Log written: {log_path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Process LinkedIn job alert emails and score new jobs"
    )
    parser.add_argument("--dry-run",       action="store_true",
                        help="Score but don't write to jobs.xlsx")
    parser.add_argument("--days",          type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help=f"Days of email history to scan (default: {DEFAULT_LOOKBACK_DAYS})")
    parser.add_argument("--no-mark-read",  action="store_true",
                        help="Leave emails as unread after processing")
    parser.add_argument("--verbose",       action="store_true",
                        help="Extra debug output")
    parser.add_argument("--model",         type=str, default=None,
                        help="Override scoring model")
    args = parser.parse_args()

    run_start = datetime.now()

    print(f"\n{'='*60}")
    print(f"Email Alert Checker  —  {run_start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # Load credentials
    gmail_address, gmail_password = _load_credentials()

    # Load existing xlsx for dedup
    existing_df     = load_jobs()
    existing_hashes = get_existing_hashes(existing_df)
    existing_tc: set[str] = set()
    for _, row in existing_df.iterrows():
        co = str(row.get("company") or "")
        ti = str(row.get("role_title") or "")
        if co and ti:
            existing_tc.add(_tc_hash(co, ti))

    # Connect to Gmail
    print(f"\n  Connecting to Gmail ({gmail_address})...")
    conn = connect_gmail(gmail_address, gmail_password)
    print(f"  ✓ Connected")

    # Fetch LinkedIn alert emails
    print(f"\n── Scanning emails (past {args.days} days) ──────────────────")
    email_data = fetch_linkedin_alert_emails(conn, days_back=args.days,
                                              verbose=True)

    if not email_data:
        print(f"  No new LinkedIn alert emails found. Nothing to process.")
        conn.logout()
        return

    # Parse all emails → extract job listings
    all_extracted: list[dict] = []
    processed_msg_nums = []

    for msg_num, msg in email_data:
        subject_raw = msg.get("Subject", "No subject")
        subject     = _decode_str(decode_header(subject_raw)[0][0])
        print(f"\n  📧 {subject[:70]}")

        jobs = parse_linkedin_email(msg, verbose=args.verbose)
        print(f"     Extracted {len(jobs)} job listing(s)")

        if jobs:
            all_extracted.extend(jobs)
            processed_msg_nums.append(msg_num)

    # Dedup extracted jobs
    seen_tc:  set[str]  = set()
    unique_jobs: list[dict] = []
    for j in all_extracted:
        tc = _tc_hash(j["company"], j["role_title"])
        if tc not in seen_tc:
            seen_tc.add(tc)
            unique_jobs.append(j)

    print(f"\n  Extracted: {len(all_extracted)} total → {len(unique_jobs)} unique")

    # Filter already-in-xlsx
    new_jobs = [j for j in unique_jobs if _tc_hash(j["company"], j["role_title"])
                not in existing_tc]
    already  = len(unique_jobs) - len(new_jobs)
    print(f"  Already in xlsx: {already}  →  {len(new_jobs)} new")

    if not new_jobs:
        print(f"\n  All jobs already in jobs.xlsx.")
        if not args.no_mark_read:
            for num in processed_msg_nums:
                mark_as_read(conn, num)
        conn.logout()
        return

    # Fetch JDs via JobSpy
    print(f"\n── Fetching JDs ({len(new_jobs)} jobs) ────────────────────────")
    fetched = 0
    for j in new_jobs:
        print(f"  🔍 {j['company']} — {j['role_title'][:60]}")
        jd = fetch_jd_for_job(j, hours_old=JD_FETCH_HOURS, verbose=args.verbose)
        j["jd_text"] = jd
        if jd:
            fetched += 1
        else:
            print(f"    ✗ JD not found")
        time.sleep(JD_FETCH_SLEEP)

    print(f"\n  JD fetch: {fetched}/{len(new_jobs)} found")

    # Score
    print(f"\n── Scoring {len(new_jobs)} jobs ─────────────────────────────────────")
    api_key = _load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)

    from scorer import DEFAULT_MODEL
    model = args.model or DEFAULT_MODEL

    scored = score_batch(new_jobs, client=client, model=model, verbose=True)

    # Write to xlsx
    to_write = [j for j in scored
                if not (j.get("url_hash") and j["url_hash"] in existing_hashes)]

    if to_write and not args.dry_run:
        start_id = int(existing_df["id"].dropna().astype(float).max() + 1) \
                   if not existing_df.empty and existing_df["id"].notna().any() else 1
        new_rows = jobs_to_rows(to_write, start_id=start_id)
        new_df   = pd.DataFrame(new_rows, columns=COLUMNS)
        combined = pd.concat([existing_df, new_df], ignore_index=True)

        # Tag email-sourced jobs in notes column
        combined.loc[combined["source"] == "email_alert", "notes"] = \
            "Sourced from LinkedIn job alert email"

        save_jobs(combined, dry_run=False)
        print(f"\n  ✓ Written {len(to_write)} new rows to jobs.xlsx")
    elif args.dry_run:
        print(f"\n  [dry-run] Would write {len(to_write)} rows — skipped")

    # Mark emails as read
    if not args.no_mark_read and processed_msg_nums:
        for num in processed_msg_nums:
            mark_as_read(conn, num)
        print(f"  ✓ Marked {len(processed_msg_nums)} email(s) as read")

    conn.logout()

    # Log + summary
    write_email_log(scored, emails_scanned=len(email_data), run_start=run_start)

    # Print summary
    proceed = [j for j in scored if j.get("decision") == "Proceed"]
    high    = [j for j in proceed if j.get("category") == "High Priority"]
    mid     = [j for j in proceed if j.get("category") == "Medium Priority"]

    print(f"\n{'═'*60}")
    print(f"  Email run complete  ({(datetime.now()-run_start).seconds}s)")
    print(f"  Jobs extracted:  {len(scored)}")
    print(f"  Queued:          {len(proceed)}  [High: {len(high)}  Mid: {len(mid)}]")
    if high:
        print(f"\n  ★  New finds from alerts:")
        for j in sorted(high, key=lambda j: j.get("fit_score") or 0, reverse=True):
            print(f"     [{j['fit_score']}/10]  {j['company']} — {j['role_title']}")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
