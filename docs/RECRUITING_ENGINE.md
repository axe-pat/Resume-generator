# Recruiting Engine

The **Recruiting Engine** is the combined system for the last-mile internship push
and the longer-term relationship graph. The point is not just to find applications.
It is to turn every credible company signal into the right next action: apply,
reach out, follow up, or skip.

Use these names when referencing the flow:

- **Recruiting Engine**: the full end-to-end system across ResumeGenerator and Outreach.
- **Daily Engine**: the supervised wrapper at `discovery/scripts/run_daily_engine.py`.
- **Source Engine**: the discovery/classification layer across job feeds and startup signals.
- **Action Queue**: the final daily decision layer with application and relationship buckets.
- **Outreach Lane**: the Outreach repo's people discovery, note generation, and send tracking.

## Operating Model

```text
Source Engine
  LinkedIn Playwright / JobSpy / startup apply feeds / startup org discovery
        |
        v
Action Queue
  application_only / application_plus_outreach / outreach_only_today
  relationship_buffer / follow_up / skipped_internal
        |
        v
Execution
  ResumeGenerator generates resume + cover letter
  Outreach finds people, generates notes, sends/logs touchpoints
```

The design rule is simple: discovery is shared, execution stays specialized.
ResumeGenerator remains the application system of record. Outreach remains the
relationship system of record.

## Source Lanes

### LinkedIn Playwright

Trusted daily application lane because it scrapes the same logged-in LinkedIn
results the user is actually looking at.

```bash
./discovery/scripts/run_linkedin_discovery.sh 24h
```

The wrapper runs queue hygiene, extracts raw LinkedIn results first, scores from
the saved raw artifact, writes accepted rows to `jobs.xlsx`, then refreshes the
current apply queue. If scoring breaks, replay scoring from the raw file instead
of reopening LinkedIn.

### Handshake Saved Search

Trusted application lane for the saved Handshake filter. Handshake does not
expose a clean 24h filter in this flow, so the runner treats the newest-first
search page as an offset feed: it scans the top page, canonicalizes job IDs,
skips anything already in `jobs.xlsx` or prior Handshake write logs, and stops
after a streak of already-known jobs.

```bash
./discovery/scripts/run_handshake_discovery.sh 24h
```

This uses the same signed-in Chrome/CDP session as browser-backed JD extraction.
The default filter is the paid internship Handshake URL saved in
`discovery/auto/import_handshake_csv.py`; override it with
`HANDSHAKE_SEARCH_URL=...` after tweaking the portal filter. Rows are written
with `source=handshake_jobs_v1`. The standing floor is flow-aware:
`handshake_apply_flow=internal` uses `4.0`, `external` uses `5.5`, and
`unknown` uses `4.5`.

### JobSpy

Breadth radar for roles the focused LinkedIn searches may miss. It is useful, but
noisy, so it should go through hard filters before any paid scoring.

```bash
venv/bin/python discovery/scripts/fetch_jobspy_breadth.py --hours-old 24
venv/bin/python discovery/scripts/validate_source_breadth.py \
  --playwright-raw discovery/auto/logs/linkedin_live_raw_YYYY-MM-DD_HHMMSS.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json
venv/bin/python discovery/scripts/run_jobspy_scoring_lane.py \
  --source-breadth discovery/source_validation/YYYYMMDD-HHMMSS-source-breadth-filtered.json \
  --jobspy-raw discovery/auto/logs/jobspy_breadth_raw_24h_YYYY-MM-DD_HHMMSS.json
```

Default posture: score `app_score_now`, keep `outreach_signal` for relationship
work, and avoid spending tokens on obvious full-time/senior/general-PM noise.

### Startup Apply Sources

Startup job-board lane for roles that look apply-ready now. It writes through the
same `jobs.xlsx` application gates when run for real, and can also feed the source
report without writing.

```bash
venv/bin/python discovery/auto/startup_apply_pipeline.py
venv/bin/python discovery/scripts/build_startup_source_report.py \
  --limit-companies 12 --limit-jobs 30
```

### Outreach Org Discovery

Relationship-first startup discovery. These are not necessarily application
postings. They are companies with credible hiring or fit signals that can become
`outreach_only_today` or `relationship_buffer` targets.

Run this through the Outreach repo source commands, then let the Daily Engine pull
the latest artifacts into the Action Queue.

## Action Queue

The Action Queue is the user-facing decision layer. It is where the system should
be inspected, not the raw discovery outputs.

```bash
venv/bin/python discovery/scripts/build_daily_action_queue.py
```

Output:

```text
discovery/source_validation/*-daily-action-queue.json
discovery/source_validation/*-daily-action-queue.md
discovery/source_validation/*-daily-action-queue.html
```

Important buckets:

- `scored_application_selected`: scored roles accepted by the application write gate.
- `scored_application_not_selected`: scored roles rejected or dropped by the gates.
- `application_plus_outreach`: active application targets that also need contact work.
- `application_only`: active application targets that already have enough relationship coverage.
- `outreach_only_today`: relationship targets rationed for today's send budget.
- `relationship_buffer`: valid relationship targets held for later.
- `follow_up`: companies with existing touchpoints.
- `skipped_internal`: blocklisted, duplicate, terminal, or low-fit records.

Run the queue before scoring when you want intake visibility. Run it again after
scoring/writes/generation to get the final daily operating view.

## Daily Engine

Supervised end-to-end command:

```bash
venv/bin/python discovery/scripts/run_daily_engine.py \
  --window 24h \
  --run-generation \
  --prepare-outreach \
  --execute-sends
```

Useful controls:

```bash
--skip-handshake
--target-sends 25
--per-company-send-limit 15
--max-outreach-companies 24
--send-min-score 20
```

Handshake runs by default as part of the daily application sources. Real sends
are deliberately explicit. Generation can run in parallel with Outreach artifact
preparation, but workbook writes and LinkedIn sends stay serialized.

## Weekly Caveat

The weekly LinkedIn wrapper has worked before, and weekly card capture currently
works. The fragile piece is full 7-day JD-detail extraction: a run can capture
cards but still fail to produce scoreable JD text. Card-only/count-only artifacts
are useful for coverage inspection, but they are not valid inputs to the
application scoring/write lane.

Until the detail-page fetcher is hardened:

- trust `./discovery/scripts/run_linkedin_discovery.sh 24h` as the application default
- use 7-day card/count runs for coverage review only
- do not score/write card-only raw files
- if a weekly scrape stalls, preserve the raw/inflight artifact and avoid writing
  incomplete rows to `jobs.xlsx`

## Safety Rules

- Keep staged extraction: capture raw first, then score from raw.
- Use the signed-in Chrome profile on port `9222`; verify CDP before LinkedIn automation.
- Do not let generated reports, run artifacts, or Outreach workbook CSV churn hide durable code changes.
- Keep `jobs.xlsx` as the application source of truth and the Outreach workbook as the relationship source of truth.
- Prefer loud failures over silent queue mutations.
