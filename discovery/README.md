# Discovery Layer

Populates `jobs.xlsx` with scored job listings from LinkedIn, Indeed, and Handshake.
Discovery is explicitly lane-tagged: Fall 2026 internships (A), 2027 new-grad/full-time (B), and Handshake income-now work (C).

For the combined application + relationship workflow, use
[`docs/RECRUITING_ENGINE.md`](../docs/RECRUITING_ENGINE.md) as the higher-level
operating guide. This file stays focused on discovery commands and mechanics.

---

## Files

```
discovery/
├── jobs.xlsx                   Master tracker (source of truth for the whole pipeline)
├── blocklist.txt               Companies excluded from promotion (fnmatch wildcards, one per line)
├── auto/
│   ├── pipeline.py             Orchestrator: scrape → score → sort → fully format xlsx
│   ├── scraper.py              JobSpy wrapper — 60 Lane A/B query clusters
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

# Standard run + startup apply lane in one command
python discovery/auto/pipeline.py --with-startup-apply

# Widen scrape window (e.g. after a gap in cron)
python discovery/auto/pipeline.py --hours-old 48

# Re-score existing unscored rows (status=new, no fit_score)
# Use this to recover from a partial run or rate-limit outage
python discovery/auto/pipeline.py --skip-scrape

# Dry run — scrape and score but don't write xlsx
python discovery/auto/pipeline.py --dry-run

# Override results per query per site
python discovery/auto/pipeline.py --results 200

# Override safety caps (defaults: 120s/query, 5400s total)
python discovery/auto/pipeline.py --query-timeout 120 --run-timeout 5400

# Use a different model (default: claude-haiku-4-5-20251001)
python discovery/auto/pipeline.py --model claude-sonnet-4-6

# Suppress verbose per-job output
python discovery/auto/pipeline.py --quiet
```

Each JobSpy query runs in its own killable process. Its results and status are
checkpointed under `discovery/auto/checkpoints/` before the next query starts;
a timed-out query is logged and skipped. The pipeline also has a total
wall-clock cap (including time spent asleep/closed-lid), and in-flight scoring
requests share that deadline, so completed query checkpoints survive a stalled
or terminated run without background scoring threads extending it.

To validate discovery classification against the current workbook without any
network calls:

```bash
venv/bin/python discovery/scripts/replay_discovery_eligibility.py
```

### Startup apply pipeline

Separate startup-focused lane for roles you can apply to now. Writes into the same
`jobs.xlsx`, but uses startup-specific `source` tags and can surface `review` rows
for borderline roles that should stay out of the live apply queue until checked.

```bash
# Dry-run discovery smoke test without Anthropic scoring
python discovery/auto/startup_apply_pipeline.py --dry-run --skip-score

# Standard run
python discovery/auto/startup_apply_pipeline.py

# Narrow to specific sources while tuning
python discovery/auto/startup_apply_pipeline.py \
  --source yc_sf_bay_hiring \
  --source builtin_sf_job_lists \
  --source a16z_job_board

# Go lighter or broader on discovery breadth
python discovery/auto/startup_apply_pipeline.py --limit-companies 8 --limit-jobs 20

# Analyze the current startup sources without deduping against jobs.xlsx
python discovery/auto/startup_apply_pipeline.py --dry-run --ignore-existing
```

Every execution writes a versioned `startup_apply_run_*.json` artifact, including
successful zero-new runs and best-effort failure artifacts. The artifact records
the exact discovered/new counts by source plus the selected/scored candidate
data used downstream. The Daily Engine supplies an exact artifact path and binds
all startup reporting to it.

Artifact health distinguishes absence from failure: zero new roles is
`completed`; all scoring results with `decision=Error` is `failed`; a mix of
successful and errored scoring is `partial_failed`. Error decisions and counts
remain visible in source metrics and are not rewritten as ordinary skips.

### Startup source report

No-write daily/validation report that puts startup apply candidates and Outreach
organization artifacts into the same source-engine vocabulary.

```bash
venv/bin/python discovery/scripts/build_startup_source_report.py \
  --rediscover-startup-apply \
  --rediscover-relationship-artifacts \
  --limit-companies 12 --limit-jobs 30

# Source-health mode: ignore existing jobs.xlsx dedupe
venv/bin/python discovery/scripts/build_startup_source_report.py \
  --rediscover-startup-apply \
  --rediscover-relationship-artifacts \
  --limit-companies 12 --limit-jobs 30 --ignore-existing
```

`--rediscover-startup-apply` is deliberately a standalone/manual source-health
mode. It performs a fresh network fetch and must not be presented as the report
for an earlier startup run. Production uses `--startup-run-artifact <exact.json>`;
the Daily Engine wires that pointer automatically, never selects `latest`, and
fails closed if the artifact is missing, malformed, or non-green.

Production relationship discovery is exact-pointer bound too: each configured
Outreach `discover-source` command must return its exact `Artifact:` path. The
Daily Engine validates source identity and health and passes that source-to-path
mapping to the report. Directory/mtime selection exists only in explicit
`--rediscover-relationship-artifacts` manual mode.

Output goes to `discovery/source_validation/` with:

- startup apply items classified as `app_score_now`, `app_review`, `outreach_signal`, or `skip_noise`
- relationship org targets ranked from exact run artifacts in production, or
  directory-selected artifacts only in explicit manual rediscovery mode

### Daily source dashboard

Internal no-write source-health dashboard that combines the latest LinkedIn/JobSpy
breadth validation and startup source report before the central gates run.

```bash
venv/bin/python discovery/scripts/build_daily_source_dashboard.py
```

Use explicit artifacts when you want a reproducible dashboard from a specific run:

```bash
venv/bin/python discovery/scripts/build_daily_source_dashboard.py \
  --source-breadth discovery/source_validation/20260527-142449-source-breadth-filtered.json \
  --startup-source-report discovery/source_validation/20260527-150343-startup-source-report.json
```

### Daily action queue

User-facing no-write queue that runs after the source-health layer. This is the
thing to inspect before doing applications or relationship outreach.

```bash
venv/bin/python discovery/scripts/build_daily_action_queue.py
```

What it gates against:

- `discovery/blocklist.txt` through the same blocklist helper used by `jobs.py`
- existing rows in `discovery/jobs.xlsx`
- terminal `Reject` / `Deprioritize` entries in the `ReviewCache` sheet
- the live queue at `apps/Apply queues/current_apply_queue/priority_order.json`
- existing Outreach organizations, contacts, and touchpoints

Output goes to `discovery/source_validation/*-daily-action-queue.{json,md,html}` with:

- `scored_application_selected`: scored roles accepted by the application write gate and still usable after blocklist/status checks
- `scored_application_not_selected`: scored roles rejected, deprioritized, blocklisted, or otherwise dropped
- `unscored_coverage_candidates`: filtered candidates still needing an application scoring lane
- `application_plus_outreach`: active application targets that also need contact work
- `application_only`: active application targets that already have enough relationship coverage
- `outreach_only_today`: the rationed relationship batch for today
- `relationship_buffer`: valid relationship targets held for later days
- `follow_up`: companies with existing touchpoints
- `skipped_internal`: blocklisted, duplicate, terminal, or low-fit records

The execution bridge keeps each selected target's company, exact role title,
source, and bucket together. Concrete application roles are passed to Outreach
as `--target-role-title` and copied into `outreach_execution.company_runs`; a
company-level relationship row cannot silently replace that role context.

Run it before scoring as a pre-score intake view. Run it again after the
application scoring/write lanes refresh `current_apply_queue`; that second HTML
is the final daily operating queue.

### Nightly generation shortlist

Cost-gated queue-compatible shortlist for unattended resume generation.

```bash
venv/bin/python discovery/scripts/build_generation_shortlist.py
venv/bin/python discovery/scripts/run_nightly_pipeline.py --generate
```

Defaults:
- non-Handshake generation floor: `7.0`
- Handshake internal apply generation floor: `6.0`
- Handshake external/unknown generation floor: `6.5`
- daily cap: `10`
- resume-only + budget mode when generation is enabled

Outputs:
- `discovery/source_validation/*-generation-shortlist.json`
- `discovery/source_validation/*-generation-shortlist.md`
- `apps/Apply queues/current_apply_queue/generation_shortlist.json`
- `apps/Apply queues/current_apply_queue/generation_shortlist.md`

Two-slot prompt/snooze setup (20:00 and 01:00 Asia/Kolkata):

```bash
RESUMEGEN_NIGHTLY_MODE=prompt \
./discovery/scripts/install_nightly_launch_agent.sh
```

The installer writes an evening delivery plist and an overnight maintenance
plist, but does not load either unless `RESUMEGEN_NIGHTLY_LOAD=1` is set. Each
slot has its own daily idempotency state; both share one overlap lock and one
48-hour discovery-attempt state. The prompt runner does not require Codex to
stay open.

### Filtered JobSpy scoring lane

JobSpy is a breadth radar, not a direct write path. Fetch raw results, validate
against the trusted LinkedIn raw artifact, then score only filtered survivors.

```bash
venv/bin/python discovery/scripts/fetch_jobspy_breadth.py --hours-old 24

venv/bin/python discovery/scripts/validate_source_breadth.py \
  --playwright-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json

venv/bin/python discovery/scripts/run_jobspy_scoring_lane.py \
  --source-breadth discovery/source_validation/YYYYMMDD-HHMMSS-source-breadth-filtered.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json
```

The scoring lane skips blocklisted companies before spending tokens and reuses
the normal application scorer, write gate, `jobs.xlsx` dedupe, and `ReviewCache`.
Daily automation runs a narrower JobSpy breadth policy by default: PM/product
ops/growth/strategy/APM/AI-PM query indices, about 40 results per site, and a
10-minute fetch timeout. Weekly automation also uses a curated profile instead
of the full broad sweep: the daily set plus focused MBA/AI strategy queries,
about 60 results per site, and a 30-minute timeout. The old broad sweep is now
manual/opt-in via explicit `--jobspy-query-index` and `--jobspy-results` flags.

### Supervised daily engine

The first unified wrapper deliberately keeps sends off unless explicitly enabled.

```bash
venv/bin/python discovery/scripts/run_daily_engine.py \
  --window 24h \
  --run-generation \
  --prepare-outreach \
  --app-outreach-limit 3 \
  --relationship-outreach-limit 2
```

Use `--parallel-generation-outreach` to run resume/CL generation while Outreach
builds LinkedIn artifacts. Shared writes still run serially; real sends require
the explicit `--execute-sends` flag and stay separate from the parallel mode.

For an unattended real-send run, keep `--parallel-generation-outreach` off and
use the global send target. The default target is 25 sends; the engine keeps
moving through application-plus-outreach, relationship-today, and relationship
buffer companies until it hits that target or runs out of safe candidates.

```bash
venv/bin/python discovery/scripts/run_daily_engine.py \
  --window 24h \
  --run-generation \
  --prepare-outreach \
  --execute-sends
```

Useful controls:

```bash
--jobspy-results 40
--jobspy-query-index 0 --jobspy-query-index 8
--startup-limit-companies 20
--startup-limit-jobs 50
--target-sends 25
--per-company-send-limit 15
--max-outreach-companies 24
--send-min-score 20
```

Each daily engine run writes a per-run source scorecard:

```text
discovery/source_validation/*-source-run-metrics.json
discovery/source_validation/*-source-run-metrics.md
```

Use that artifact to compare raw/discovered counts, selected/new counts, fresh
scoring, errors, accepted writes, outreach signals, runtime, and
accepted-per-minute across LinkedIn, Handshake, JobSpy, startup apply, and the
startup relationship lane.

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

Semantic URLs include **geo + distance** (default: US + 25 mi) so the results list is not empty;
override with `LINKEDIN_JOBS_GEO_ID` and `LINKEDIN_JOBS_DISTANCE` in `.env` or the shell if needed.

```bash
# Standard run using the built-in searches:
# - Product Manager Intern (past 24h)
# - Product Manager Intern (past week)
# - MBA Intern (past 24h)
# - MBA Intern (past week)
python discovery/auto/linkedin_live.py

# Same, but start Chrome via launch_linkedin_browser.sh when CDP port is closed
# (set LINKEDIN_CHROME_USER_DATA_DIR in the environment or in project root .env)
python discovery/auto/linkedin_live.py --launch-chrome

# Recommended one-command wrappers
./discovery/scripts/run_linkedin_discovery.sh 24h
./discovery/scripts/run_linkedin_discovery.sh 7d

# Dry run — scrape + score, don't write xlsx
python discovery/auto/linkedin_live.py --dry-run

# Go deeper per search
python discovery/auto/linkedin_live.py --limit-per-search 15 --pages 2

# Optional: explicitly allow fallback to the noisier /jobs/search/ route when semantic coverage is low
python discovery/auto/linkedin_live.py --allow-jobs-search-fallback

# Custom search set
python discovery/auto/linkedin_live.py \
  --search "Product Manager Intern" --time r86400 \
  --search "MBA Intern" --time r604800
```

Pre-reqs:
- Run Chrome with remote debugging enabled on port `9222` (or pass `--launch-chrome` once `LINKEDIN_CHROME_USER_DATA_DIR` is set)
- Keep LinkedIn logged in in that Chrome profile
- Ensure Playwright is installed in the Python env that runs the script
- See `../docs/LINKEDIN_BROWSER_PLAYBOOK.md` for the canonical shared Chrome-session rules used by both discovery and Outreach

`linkedin_live.py` already runs a LinkedIn **preflight** after attaching to CDP (login / authwall), so `./discovery/scripts/check_linkedin_live.sh` is optional — use it when you want a quick health check without starting a full scrape.

Recommended live-session flow:

```bash
# 1. Point the launcher at an explicitly approved signed-in Chrome profile
#    (or add the same line to ResumeGenerator v1/.env — no export needed)
export LINKEDIN_CHROME_USER_DATA_DIR="/absolute/path/to/your/signed-in/chrome-data"

# 2. Launch that profile on port 9222 (skip if Chrome is already listening on 9222)
./discovery/scripts/launch_linkedin_browser.sh

# 3. (Optional) Verify CDP owner + LinkedIn session before a long run
./discovery/scripts/check_linkedin_live.sh

# 4. Run a focused extract-only probe before the full batch
python discovery/auto/linkedin_live.py \
  --search "Product Manager Intern" --time r86400 \
  --extract-only

# 5. Score/write later from the saved raw artifact(s) without reopening LinkedIn
python discovery/auto/linkedin_live.py \
  --score-from-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json
```

For normal day-to-day use, prefer the wrapper:

```bash
./discovery/scripts/run_linkedin_discovery.sh 24h
./discovery/scripts/run_linkedin_discovery.sh 7d
```

Current weekly caveat: the 7-day card/count path is useful for coverage checks,
but full 7-day JD-detail extraction can stall or produce card-only raw artifacts.
Do not score/write card-only weekly raw files; use the 24h wrapper as the trusted
daily application lane until weekly detail extraction is hardened.

It does:
- applied-PDF sync
- queue refresh
- LinkedIn extract-only run
- scoring from the saved raw artifact
- queue refresh again

This is the most reliable path when LinkedIn browser extraction is healthy but live scoring is occasionally flaky.

What the live runner now does automatically:
- Skips scoring jobs already present in `jobs.xlsx`
- Skips rescoring jobs previously marked `Reject` or `Deprioritize` in the hidden `ReviewCache` sheet inside `jobs.xlsx`
- Writes batch reports to `discovery/auto/logs/`
- Appends accepted (`Proceed`) rows to `discovery/jobs.xlsx` with **`status=queued`** so they match `jobs.py` / apply-queue flows
- After new rows are written, runs **`discovery/scripts/refresh_current_apply_queue.py`** (best-effort) so `apps/Apply queues/current_apply_queue/` is rebuilt with `priority_order.json` for `jobs.py generate --queue`
- Still exports a dated **read-only** run bundle to `apps/runs/<timestamp>_<window>/` with:
  - `report.md`
  - `report.html`
  - `manifest.json`
  - `accepted/<Company>/<Role>/jd.txt`
  - `accepted/<Company>/<Role>/intel.txt`
  - `accepted/<Company>/<Role>/metadata.json`

Recommended staged pattern for reliability:
- Run extraction first with `--extract-only`
- Keep the `linkedin_live_raw_*.json` artifact as the source of truth
- Replay scoring later with `--score-from-raw ...`
- If scoring fails, rerun scoring from the raw artifact instead of redoing LinkedIn extraction

### Handshake saved-search discovery

Uses your real logged-in Handshake session in Chrome to read the saved Handshake
search filter, open newly discovered job pages, extract JD text, score, write
accepted rows to `jobs.xlsx`, and refresh `current_apply_queue`.

```bash
# Daily lane: newest-first search page, dedupe against jobs.xlsx, stop after known jobs
./discovery/scripts/run_handshake_discovery.sh 24h

# Wider audit lane
./discovery/scripts/run_handshake_discovery.sh 7d

# Override the saved filter after tuning Handshake
HANDSHAKE_SEARCH_URL="https://app.joinhandshake.com/job-search/..." \
  ./discovery/scripts/run_handshake_discovery.sh 24h

# Lane C income-now search (saved Handshake on-campus/part-time URL required)
HANDSHAKE_LANE=C \
HANDSHAKE_SEARCH_URL="https://app.joinhandshake.com/job-search/..." \
  ./discovery/scripts/run_handshake_discovery.sh 24h
```

Handshake search does not offer the same reliable 24h/weekly URL filter as
LinkedIn. The runner therefore uses a bounded offset-style rule: the 24h wrapper
looks at the newest page, canonicalizes `/job-search/<id>` URLs, skips existing
rows plus jobs already scored in prior Handshake write logs, and stops after 8
consecutive known jobs by default. Tune with `HANDSHAKE_MAX_PAGES`,
`HANDSHAKE_MAX_RESULTS`, and
`HANDSHAKE_STOP_AFTER_EXISTING` when the portal filter changes.

Every Handshake execution writes a versioned `handshake_import_*.json` artifact,
including runs where every observed link is already known. The artifact keeps
the full observed-link count, duplicate/prefilter skips, candidates, fetches,
scores, and accepted rows. The Daily Engine supplies the exact output path and
reads only that pointer; it never substitutes an older `latest` import log. A
missing, malformed, or non-green exact artifact fails the Handshake stage.
Zero post-dedupe candidates is still a valid `completed` run. All JD fetch or
processing failures produce `failed`; mixed success/errors produce
`partial_failed`, with error counts propagated into Source Breakdown.

The queue floor is application-effort aware:
- `handshake_apply_flow=internal` uses `4.0`
- `handshake_apply_flow=external` uses `5.5`
- `handshake_apply_flow=unknown` uses `4.5`

The underlying importer also still supports manual CSV exports:

```bash
python discovery/auto/import_handshake_csv.py \
  --csv /Users/akshat/Downloads/-JobTitle-Company-Industry-Pay-Deadline-Status-URL.csv \
  --min-score 4.5 \
  --include-deprioritized \
  --write
```

Pre-reqs:
- Run Chrome with remote debugging enabled on port `9222`
- Keep Handshake logged in in that Chrome profile
- Ensure Playwright is installed in the Python env that runs the script

### Source breadth validation

Use this before promoting JobSpy or startup-source experiments into the daily write path.
It compares a trusted Playwright raw artifact against a JobSpy raw artifact and applies
hard relevance filters before any Claude scoring or `jobs.xlsx` writes.

```bash
venv/bin/python discovery/scripts/validate_source_breadth.py \
  --playwright-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json \
  --jobspy-raw discovery/auto/logs/jobspy_linkedin_equiv_raw_24h_YYYY-MM-DD_HHMMSS.json
```

Output goes to `discovery/source_validation/` with `app_score_now`, `app_review`,
`unsure`, `outreach_signal`, and `skip_noise` buckets. `unsure` is the explicit
human-review list for unknown titles whose JD bodies contain target signals; it
must not be silently dropped. Only `app_score_now` should be
considered for automatic application scoring by default; `outreach_signal` belongs
in the relationship lane.

For the broader source-engine plan, see `docs/STARTUP_AND_SOURCE_ENGINE.md`.

### Queue / apply surfaces

Current steady-state structure:
- `apps/Apply queues/current_apply_queue/` = live apply inbox (`jobs.py generate --queue`)
- `apps/runs/forgotten_queue/` = older manual leftovers and future aged-out items
- `apps/archive/discovery_runs/` = immutable discovery history
- `apps/archive/applied/` = jobs treated as applied

Useful maintenance commands:

```bash
# Deprecated report-only scanner; never moves files or changes tracker status
python discovery/scripts/sync_applied_pdfs.py

# Safely preview one reviewed applied/closed outcome before committing it
python discovery/scripts/transition_application.py --id 1949 --status applied --dry-run --json

# Rebuild the single live apply inbox from jobs.xlsx
python discovery/scripts/refresh_current_apply_queue.py

# Move leftover manual dirs and 10-day-old queue items into forgotten_queue
python discovery/scripts/refresh_forgotten_queue.py

# One-time cleanup helper to archive redundant old surfaces
python discovery/scripts/consolidate_apply_surfaces.py
```

Recommended post-apply rhythm:

```bash
python discovery/scripts/transition_application.py --id 1949 --status applied --confirm "APPLY 1949"
python discovery/scripts/refresh_forgotten_queue.py
```

The transition command already updates the current-queue indexes. It archives
the complete application directory before changing `jobs.xlsx`, keeps a
rollback journal, and rejects ambiguous or concurrent mutations. See
`docs/APPLICATION_LIFECYCLE.md`.

Nightly, Daily Engine, and queue refresh all report legacy PDF sync as
`skipped_deprecated`. A local `Resume.pdf` proves only that a file exists; it is
never treated as evidence that the user submitted the application.

Recommended post-discovery rhythm:

```bash
python discovery/scripts/refresh_current_apply_queue.py
python discovery/scripts/refresh_forgotten_queue.py
```

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
| `handshake_jobs_v1` | Browser-backed Handshake saved-search/CSV application lane     |
| `yc_startup_jobs` | Startup-apply pipeline from YC startup sources                  |
| `builtin_startup_jobs` | Startup-apply pipeline from Built In startup job-list sources |
| `a16z_startup_jobs` | Startup-apply pipeline from a16z portfolio jobs board         |
| `screenshot` | Extracted from LinkedIn screenshot PDF via score_screenshots.py      |
| `seeded`     | Pre-seeded historical jobs (applied before this system was built)    |
| `manual`     | Manually added rows directly in xlsx                                 |

---

## Scraper query clusters

12 clusters. Each runs on LinkedIn + Indeed. Results per query scale with
lookback window inside the standalone scraper, but the daily/weekly engine
overrides those defaults with curated profiles.

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
| mba_ai_strategy_intern | MBA AI Strategy Intern              | Strategy  |
| mba_product_strategy_intern | MBA Product Strategy Intern    | Strategy  |
| ai_strategy_ops_intern | AI Strategy Operations Intern       | Strategy  |

Default engine profiles:

- 24h: `pm_intern`, `product_ops_intern`, `growth_intern`,
  `strategy_intern`, `apm_intern`, `ai_pm_intern`,
  `mba_ai_strategy_intern`, `mba_product_strategy_intern`, and
  `ai_strategy_ops_intern`; 40 results/site.
- 7d: the same focused query set; 60 results/site.
- Broad validation sweep: opt in manually by passing all desired
  `--jobspy-query-index` values and a larger `--jobspy-results` cap.

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

### Queue generation defaults

`apps/Apply queues/current_apply_queue/generate_command.sh` is rebuilt by the
queue refresh scripts. It now defaults to:

```bash
python jobs.py generate --queue --resume-only --budget-mode
```

That keeps resume generation as the default artifact and defers cover letters
until an ATS actually asks for one. Use `--with-cl` on `jobs.py generate`, or
run `python run_app.py <Company> --cl-only`, when a cover letter is needed.

---

## Log files

Every run writes a structured log to `discovery/auto/logs/`:

- `run_YYYY-MM-DD_HHMM.txt` — pipeline.py runs
- `screenshots_YYYY-MM-DD_HHMM.txt` — score_screenshots.py runs

Each log contains: summary counts, all High Priority and Medium Priority jobs with scores + rationale + URL, rejected jobs, and any scoring errors.

---

## Skip-scrape behavior note

`--skip-scrape` targets rows where `status == "new"` AND `fit_score` is empty. The fit_score check uses `.fillna("")` because xlsx NaN values read back as float NaN, not empty string — a plain `== ""` check would return 0 rows.
