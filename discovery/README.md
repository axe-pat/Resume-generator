# Discovery Layer

Populates `jobs.xlsx` with scored job listings from LinkedIn and Indeed.
Two input paths: automated keyword scraping (every 3h) and manual LinkedIn screenshot scoring (on demand).

---

## Files

```
discovery/
├── jobs.xlsx                   Master tracker (source of truth for the whole pipeline)
├── blocklist.txt               Companies excluded from promotion (fnmatch wildcards, one per line)
├── auto/
│   ├── pipeline.py             Orchestrator: scrape → score → sort → fully format xlsx
│   ├── scraper.py              JobSpy wrapper — 9 query clusters
│   ├── scorer.py               Claude Haiku fit scorer (pre-filters + 0–10 rubric)
│   ├── scorer_prompt.md        Scoring rubric and profile context
│   ├── score_screenshots.py    LinkedIn screenshot PDF → vision extract → JD fetch → score
│   ├── jd_fetch.py             Retry tool: fetches JDs for xlsx rows that have none
│   ├── seed_from_csv.py        One-time import of LinkedIn CSV exports
│   └── logs/                   Per-run digest files (run_YYYY-MM-DD_HHMM.txt,
│                                                      screenshots_YYYY-MM-DD_HHMM.txt)
└── manual/
    ├── <screenshots>.pdf       LinkedIn screenshot PDFs for score_screenshots.py
    └── jd_paste/               Manual JD paste files created by jd_fetch.py Path C
```

---

## Running manually

### Automated pipeline

```bash
# Standard run (scrape last 24h, score, write xlsx)
python discovery/auto/pipeline.py

# Widen scrape window (e.g. after a gap in cron)
python discovery/auto/pipeline.py --hours-old 48

# Re-score existing unscored rows (status=new, no fit_score)
# Use this to recover from a partial run or rate-limit outage
python discovery/auto/pipeline.py --skip-scrape

# Dry run — scrape and score but don't write xlsx
python discovery/auto/pipeline.py --dry-run

# Override results per query per site
python discovery/auto/pipeline.py --results 200

# Use a different model (default: claude-haiku-4-5-20251001)
python discovery/auto/pipeline.py --model claude-sonnet-4-6

# Suppress verbose per-job output
python discovery/auto/pipeline.py --quiet
```

### Screenshot scoring (LinkedIn PDF screenshots)

**Run from your Mac terminal, not the Cowork VM** — the VM has SSL issues that break the Anthropic API.

```bash
# Score all PDFs in discovery/manual/ (default)
python discovery/auto/score_screenshots.py

# Specify a different directory
python discovery/auto/score_screenshots.py --dir path/to/screenshots

# Dry run
python discovery/auto/score_screenshots.py --dry-run

# Widen JD search window (default: 168h = 7 days)
python discovery/auto/score_screenshots.py --hours-old 336

# Skip JobSpy JD fetch — score on title+company only (fast, lower confidence)
python discovery/auto/score_screenshots.py --no-jd-fetch
```

### Logged-in LinkedIn live discovery

Uses your real logged-in LinkedIn Jobs session in Chrome to run targeted searches,
open visible jobs, capture JD text from the right-hand detail pane, score them,
and append new rows into `jobs.xlsx`.

```bash
# Standard run using the built-in searches:
# - Product Manager Intern (past 24h)
# - Product Manager Intern (past week)
# - MBA Intern (past 24h)
# - MBA Intern (past week)
python discovery/auto/linkedin_live.py

# Dry run — scrape + score, don't write xlsx
python discovery/auto/linkedin_live.py --dry-run

# Go deeper per search
python discovery/auto/linkedin_live.py --limit-per-search 15 --pages 2

# Custom search set
python discovery/auto/linkedin_live.py \
  --search "Product Manager Intern" --time r86400 \
  --search "MBA Intern" --time r604800
```

Pre-reqs:
- Run Chrome with remote debugging enabled on port `9222`
- Keep LinkedIn logged in in that Chrome profile
- Ensure Playwright is installed in the Python env that runs the script

### JD fetch / retry

For xlsx rows with no JD text (typically screenshot-sourced jobs that couldn't be found within the original 168h window):

```bash
# Retry all screenshot rows with no JD (Path A: JobSpy no time limit, Path B: direct URL)
python discovery/auto/jd_fetch.py

# Retry specific row IDs only
python discovery/auto/jd_fetch.py --id 1540,1541,1543

# Dry run — fetch and score but don't write xlsx
python discovery/auto/jd_fetch.py --dry-run

# After manually pasting JDs into discovery/manual/jd_paste/*.txt
python discovery/auto/jd_fetch.py --rescore-pastes
```

For jobs the fetcher still can't find (LinkedIn-auth-only, private ATS): the script writes a helper `.txt` file to `discovery/manual/jd_paste/` with instructions. Paste the JD there, then run `--rescore-pastes`.

⚠️  Run from Mac terminal — scoring uses the Anthropic API.

### Standalone component testing

```bash
# Test scraper — run all 9 queries, print sample results
python discovery/auto/scraper.py

# Test scraper — single query index (0-based)
python discovery/auto/scraper.py --query-index 0

# Test scorer — score 3 built-in mock JDs
python discovery/auto/scorer.py --test

# Test scorer — score a single JD file
python discovery/auto/scorer.py --jd path/to/jd.txt
```

---

## Two input paths: automated vs screenshot

### Automated pipeline (every 3h)
Keyword-based scraping across 9 query clusters on LinkedIn + Indeed. Covers ~838 companies posting via standard channels. Misses companies that don't surface through keyword queries (top-tier brands with high traffic, unconventionally titled roles, network-gated postings).

### Screenshot scoring (manual)
LinkedIn's "In My Network" and "Under 10 Applicants" filters surface jobs that unauthenticated JobSpy can never replicate. Workflow: take LinkedIn screenshots → save as PDFs to `discovery/manual/` → run score_screenshots.py.

The two sources are complementary, not redundant. In a 79-job March 2026 validation run, only ~30% of manually-found companies also appeared in the automated results.

---

## Deduplication

Two-level dedup prevents the same job appearing twice across both sources:

1. **URL hash** — MD5 of canonical URL. Primary key, stored in `url_hash` column.
2. **Title+company hash** — catches cross-posts with different URLs (internal only, not stored).

Both are checked on every run. Existing hashes are loaded from xlsx before any processing starts.

---

## Scoring

Claude Haiku scores each job on a 25-point rubric normalised to 0–10:
- PM Fit (role match, scope, autonomy)
- Technical Match (stack, domain)
- Visa/Sponsorship (hard filter first)
- Growth / Compensation signals

Decision outcomes:
- `Proceed` → `status = queued` (eligible for jobs.py promotion)
- `Reject` / `Deprioritize` → `status = skipped`

After every run, `pipeline.py` sorts the full dataset by status rank and writes the xlsx with complete formatting: status-cell colours, score traffic lights (green ≥8.5 / amber 7–8.4 / red <7), thick section dividers between status groups, and grey strikethrough for blocklisted companies. The view is always fresh after a cron run — no manual `jobs.py sort` needed.

### Pre-filters (no API call)

Three checks run before any Claude call, in this order:

**1. Role-type mismatch** (title only — not full JD, to avoid false positives):
Rejects pharmacy, clinical/medical, non-PM engineering (electrical, mechanical, firmware, civil, etc.), architecture/construction, trades, accounting, legal, logistics/warehouse, HR. Grey areas pass through — "Supply Chain PM", "Solutions Architect" are not filtered.

**2. Immigration hard reject** (JD text):
Catches: US citizen only, security clearance required, explicit CPT/OPT rejection.
Does NOT reject: "No visa sponsorship" alone (means no future H-1B, not an internship blocker).

**3. Full-time level mismatch** (JD text):
Rejects if: no internship signal in title or JD opening, AND 4+ years experience required.

### Rate limiting

- 2 parallel scoring workers (safe under 50K tokens/minute org limit)
- Exponential backoff on 429 errors: 60s → 120s → 240s → 480s
- 5 retry attempts per job before marking as Error
- Cost estimate printed before each batch (Haiku: ~$0.00176/job)

---

## Source taxonomy

The `date_posted` column is set from JobSpy's `date_posted` field and reflects when the job was originally listed by the employer. It is distinct from `date_found` (when the row was added to jobs.xlsx). Useful for filtering stale postings and gauging how fresh a role is. Blank for `seeded` and `manual` rows.

| source       | meaning                                                              |
|--------------|----------------------------------------------------------------------|
| `linkedin`   | Automated pipeline (LinkedIn)                                        |
| `indeed`     | Automated pipeline (Indeed)                                          |
| `screenshot` | Extracted from LinkedIn screenshot PDF via score_screenshots.py      |
| `seeded`     | Pre-seeded historical jobs (applied before this system was built)    |
| `manual`     | Manually added rows directly in xlsx                                 |

---

## Scraper query clusters

9 clusters. Each runs on LinkedIn + Indeed. Results per query scale with lookback window: 50 (≤6h), 100 (≤30h), 150 (>30h).

| id                   | search_term                          | role_type |
|----------------------|--------------------------------------|-----------|
| pm_intern            | Product Manager Intern               | PM        |
| product_ops_intern   | Product Operations Intern            | Ops       |
| growth_intern        | Growth Product Intern                | Ops       |
| strategy_intern      | Strategy Intern MBA                  | Strategy  |
| bizops_intern        | Business Operations Intern           | Ops       |
| tpm_intern           | Program Manager Intern               | TPM       |
| product_owner_intern | Product Owner Intern                 | PM        |
| apm_intern           | Associate Product Manager Intern     | PM        |
| ai_pm_intern         | AI Product Manager Intern            | PM        |

### Known coverage gaps
- High-traffic companies (Adobe, Apple, TikTok) can flood query results, pushing other roles past the results cap. TikTok is a notable example — a dedicated query is the planned fix.
- Companies that only post jobs internally or via direct ATS (no LinkedIn/Indeed syndication) are not captured by either input path.

---

## Adding jobs manually

For jobs found outside both automated paths (referrals, direct company site, cold outreach):

1. Open `jobs.xlsx`
2. Add a row with at minimum: `company`, `role_title`, `url`, `jd_text`, `status=queued`, `fit_score`, `source=manual`
3. The pipeline will pick it up on the next `jobs.py pipeline` run

Or use the seed script for bulk CSV imports:
```bash
python discovery/auto/seed_from_csv.py path/to/linkedin_export.csv
```

---

## Log files

Every run writes a structured log to `discovery/auto/logs/`:

- `run_YYYY-MM-DD_HHMM.txt` — pipeline.py runs
- `screenshots_YYYY-MM-DD_HHMM.txt` — score_screenshots.py runs

Each log contains: summary counts, all High Priority and Medium Priority jobs with scores + rationale + URL, rejected jobs, and any scoring errors.

---

## Skip-scrape behavior note

`--skip-scrape` targets rows where `status == "new"` AND `fit_score` is empty. The fit_score check uses `.fillna("")` because xlsx NaN values read back as float NaN, not empty string — a plain `== ""` check would return 0 rows.
