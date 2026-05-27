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

Raw fetch and validation commands:

```bash
venv/bin/python discovery/scripts/fetch_jobspy_breadth.py --hours-old 24
```

```bash
venv/bin/python discovery/scripts/validate_source_breadth.py \
  --playwright-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json
```

Filtered scoring command:

```bash
venv/bin/python discovery/scripts/run_jobspy_scoring_lane.py \
  --source-breadth discovery/source_validation/YYYYMMDD-HHMMSS-source-breadth-filtered.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json
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

Scoring-lane check on 2026-05-27:

- Blocklist preflight skipped the TikTok survivor before any Claude call.
- Jobright.ai was the only non-blocklisted JobSpy-only `app_score_now` survivor.
- The normal application scorer rejected Jobright.ai as a full-time/level mismatch, wrote no app row, and added the terminal decision to `ReviewCache`.
- Net result: JobSpy added useful validation coverage but no new application package in that 24h sample.

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
- The no-write startup source report now reclassifies those candidates with the shared verdicts:
  2 `app_score_now`, 0 `app_review`, 0 `skip_noise` on the 2026-05-27 12-company smoke run.

Current report command:

```bash
venv/bin/python discovery/scripts/build_startup_source_report.py \
  --limit-companies 12 --limit-jobs 30
```

Use `--ignore-existing` when checking source health instead of only net-new tracker additions.

### Daily Source Dashboard

Command:

```bash
venv/bin/python discovery/scripts/build_daily_source_dashboard.py
```

Purpose:

- Combines the latest LinkedIn/JobSpy source breadth validation with the latest startup source report.
- Shows an internal no-write source-health dashboard for `app_score_now`, `app_review`, relationship targets, and skipped noise.
- Runs before blocklist, `jobs.xlsx`, live apply queue, and Outreach-history gates, so it is not the operator-facing queue.
- Keeps execution separate: ResumeGenerator still owns resume/cover-letter generation, Outreach still owns contact enrichment and messaging.

### Daily Action Queue

Command:

```bash
venv/bin/python discovery/scripts/build_daily_action_queue.py
```

Purpose:

- Builds the operator-facing daily queue after central gates.
- Reuses `jobs.py` blocklist behavior instead of copying a second blocklist implementation.
- Cross-pollinates active application targets into Outreach via `application_plus_outreach`.
- Rations relationship-only work into `outreach_only_today` and keeps the rest in `relationship_buffer`.
- Penalizes enterprise-sized Built In results and separately scores JobSpy-only role signals as relationship targets.

Outputs:

- `scored_application_selected`: scored roles accepted by the application write gate and still usable after blocklist/status checks.
- `scored_application_not_selected`: scored roles rejected, deprioritized, blocklisted, or otherwise dropped.
- `unscored_coverage_candidates`: filtered candidates still needing an application scoring lane.
- `application_plus_outreach`: generate/apply normally, but also run Outreach for the company.
- `application_only`: application execution is enough for now.
- `outreach_only_today`: run the LinkedIn company/contact pipeline today.
- `relationship_buffer`: keep valid targets for later batches.
- `follow_up`: existing-touchpoint companies.
- `skipped_internal`: blocklisted, terminal, duplicate, or low-fit internal rows.

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
- On 2026-05-27: YC SF hiring returned 25 orgs, YC LA returned 25 orgs, Built In LA returned 20 orgs, Built In SF returned 20 orgs.
- The startup source report reads the latest no-write Outreach artifacts and ranks relationship targets by source quality, active hiring, geography, domain fit, and team-size/contactability signals.

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

## Supervised Orchestrator

Command:

```bash
venv/bin/python discovery/scripts/run_daily_engine.py \
  --window 24h \
  --run-generation \
  --prepare-outreach \
  --app-outreach-limit 3 \
  --relationship-outreach-limit 2
```

Behavior:

- Runs the trusted LinkedIn lane, filtered JobSpy lane, startup apply lane, relationship source discovery, startup source report, and final daily action queue.
- Reads the final post-score action queue JSON to pick application-plus-outreach and outreach-only companies.
- Keeps `jobs.xlsx`, queue refreshes, and Outreach workbook writes serial.
- Allows `--parallel-generation-outreach` so resume/CL generation can run while Outreach builds LinkedIn artifacts.
- Does not send invites unless `--execute-sends` is explicitly passed.

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

- Wellfound jobs and company pages. Quick probe on 2026-05-27 showed public pages are indexed and high-value, but direct HTTP plus headed/headless Playwright receive a DataDome/Cloudflare 403 challenge. Treat this as a browser/session-backed or external-API source, not a quick static scraper.
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
