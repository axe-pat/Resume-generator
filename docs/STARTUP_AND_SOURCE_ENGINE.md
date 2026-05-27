# Startup And Source Engine

Status: v0 validation in progress

## Goal

Build a recruiting source engine that finds high-quality application and relationship targets without breaking the existing ResumeGenerator and Outreach execution paths.

The engine should support two outcomes:

- Applications: roles that should enter the ResumeGenerator scoring, queue, resume, and cover-letter flow.
- Relationships: startups and people worth contacting even when there is no clean internship posting.

This matters because the June push is not only summer-internship search. It is also founder, PM, and operator relationship building for full-time recruiting.

## Current Source Lanes

### Trusted LinkedIn Application Lane

Command:

```bash
./discovery/scripts/run_linkedin_discovery.sh 24h
```

Purpose:

- Daily trusted LinkedIn capture.
- Uses the logged-in Playwright browser flow.
- Extracts first into a raw artifact, then scores from the saved raw artifact.
- Best default for roles that should go into the application queue.

Why it stays:

- It captures the LinkedIn surface the user can visually inspect.
- It is narrower but more trustworthy than broad scraping.

### JobSpy Breadth Lane

Current validation command:

```bash
venv/bin/python discovery/scripts/validate_source_breadth.py \
  --playwright-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json \
  --jobspy-raw discovery/auto/logs/jobspy_linkedin_equiv_raw_24h_YYYY-MM-DD_HHMMSS.json
```

Purpose:

- Test what JobSpy finds that Playwright misses.
- Apply hard relevance filters before any Claude scoring or tracker writes.
- Separate application scoring candidates from startup/company relationship signals.

Rule:

- JobSpy should not become an unfiltered write path.
- If used daily, it must be filtered before scoring and before writing to `jobs.xlsx`.

Initial 24h validation on 2026-05-27:

- Playwright extract-only: 32 jobs.
- JobSpy LinkedIn-equivalent raw: 106 jobs.
- Overlap: 8.
- Playwright-only after stricter filters: 8 `app_score_now`, 12 `app_review`, 1 `skip_noise`.
- JobSpy-only after stricter filters: 2 `app_score_now`, 2 `app_review`, 16 `outreach_signal`, 78 `skip_noise`.
- Overlap after stricter filters: 6 `app_score_now`, 2 `app_review`.

Interpretation:

- Hybrid is likely valuable.
- Playwright remains the trusted baseline.
- JobSpy can add breadth, but most incremental jobs are not application candidates.
- `app_score_now` is intentionally high precision: the title itself must carry both a target-role signal and an early-career signal.
- `app_review` is for early-career or internship-ish roles that need cheap/manual triage before normal scoring.
- `outreach_signal` is for full-time/non-internship roles at high-signal companies or domains that may be valuable for relationship building, not immediate application scoring.

### Startup Apply Lane

Command:

```bash
venv/bin/python discovery/auto/startup_apply_pipeline.py \
  --dry-run --skip-score --limit-companies 12 --limit-jobs 30
```

Purpose:

- Find actual startup roles with apply URLs and JD text.
- Existing sources include YC, Built In, and a16z.
- This is application-first, not relationship-first.

Current finding:

- The lane works, but app-ready supply is thin.
- On 2026-05-27 it found 2 review candidates and 0 queued candidates in dry-run mode.

### Outreach Organization Discovery Lane

Commands:

```bash
cd ../Outreach
./.venv/bin/python main.py discover-source --source-id yc_sf_bay_hiring --limit 25 --no-write-workbook
./.venv/bin/python main.py discover-source --source-id yc_los_angeles --limit 25 --no-write-workbook
./.venv/bin/python main.py discover-source --source-id builtin_la_companies --limit 25 --no-write-workbook
```

Purpose:

- Build the relationship-first startup universe.
- Finds companies, descriptions, websites, founders or contacts when available, and source metadata.
- Does not require a clean posted internship.

Current finding:

- Org discovery has healthy supply.
- On 2026-05-27: YC SF hiring returned 25 orgs, YC LA returned 25 orgs, Built In LA returned 20 orgs.

## Target Daily Architecture

```text
Daily source intake
  Playwright LinkedIn 24h
  Filtered JobSpy LinkedIn 24h
  Startup apply sources
  Startup relationship signal sources
        ↓
Application / relationship classifier
        ↓
application_only
application_plus_outreach
outreach_only
follow_up
skip
        ↓
Execution
  ResumeGenerator: resumes, cover letters, apply queue
  Outreach: contacts, messages, touchpoints, follow-ups
```

## Startup Signal Ranking

For relationship-first startups, rank companies by:

- Hiring signal: active jobs page, hiring tag, recent job postings, or public role openings.
- Funding/quality signal: YC, a16z, Techstars, Contrary, recent funding, accelerator-backed, or credible portfolio inclusion.
- Geography: LA, SF Bay Area, remote, or otherwise practical for summer/fall conversations.
- Domain fit: AI, data, developer tools, marketplaces, productivity, robotics, healthtech, fintech, infrastructure, or business/product operator relevance.
- Team size: small enough that founder/operator outreach can matter.
- Contactability: identifiable founder, Head of Product, PM, operator, chief of staff, recruiter, or warm alumni/contact path.
- Application adjacency: whether there is a real role, a jobs page, or a plausible project/internship angle.

## Source Roadmap

Keep or strengthen:

- LinkedIn Playwright: trusted daily baseline.
- JobSpy: filtered breadth radar.
- YC Jobs and YC company directories.
- Built In job lists and company pages.
- a16z portfolio jobs.

Add next:

- Wellfound jobs and company pages.
- Techstars portfolio jobs.
- Contrary portfolio/jobs if accessible.
- Founder-post signal capture from X/LinkedIn posts.
- A general external-source adapter that can ingest a search result page, job board export, or source-specific API result into the same normalized candidate model.

## Daily Run Policy

Recommended daily policy once the source engine is wired:

- Always run Playwright 24h as the trusted application baseline.
- Run JobSpy 24h as a filtered breadth add-on.
- Automatically score JobSpy `app_score_now`.
- Either cap JobSpy `app_review` scoring, or run it through a cheaper triage-only prompt before normal scoring.
- Send JobSpy `outreach_signal` to the relationship lane instead of the resume/cover-letter lane.
- Run startup apply sources in the application lane, because those produce actual apply URLs and JDs.
- Run startup relationship sources in the relationship lane, because those produce company/person targets even without a posted internship.

## Safety Rules

- Do not write to `jobs.xlsx` from new source experiments until source validation reports look sane.
- Do not mutate `apps/Apply queues/current_apply_queue` from validation scripts.
- Keep raw artifacts for every extraction.
- Score only `app_score_now` by default.
- Keep `app_review` as a bounded manual or cheap-review queue.
- Keep `outreach_signal` out of the normal application scoring path.
- Never spend Claude calls on `skip_noise`.
