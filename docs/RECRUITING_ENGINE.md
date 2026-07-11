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

Before opening each JD, the importer skips obvious non-fit titles such as
camp/admin, HR/recruiting, channel-management, generic sales/business
development, and social-media roles. The import log records
`title_prefilter_skipped` so an over-aggressive filter is visible in the run
artifact.

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
The 24h daily lane runs the focused PM/product-ops/growth/strategy/APM/AI-PM
set plus MBA/AI strategy queries, uses about 40 results per site, and gives the
scrape a 10-minute default timeout. Weekly runs use the same focused query set
at about 60 results per site with a 30-minute timeout. The old all-query broad
sweep is manual/opt-in for source audits.

### Startup Apply Sources

Startup job-board lane for roles that look apply-ready now. It writes through the
same `jobs.xlsx` application gates when run for real, and can also feed the source
report without writing. This is distinct from relationship discovery: startup
apply needs a real role/JD/apply URL, while relationship discovery can act on a
credible company-level hiring signal.

```bash
venv/bin/python discovery/auto/startup_apply_pipeline.py
venv/bin/python discovery/scripts/build_startup_source_report.py \
  --limit-companies 20 --limit-jobs 50
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
discovery/source_validation/*-source-run-metrics.json
discovery/source_validation/*-source-run-metrics.md
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
--jobspy-results 40
--jobspy-query-index 0 --jobspy-query-index 8
--startup-limit-companies 20
--startup-limit-jobs 50
--target-sends 25
--per-company-send-limit 15
--max-outreach-companies 24
--send-min-score 20
```

Handshake runs by default as part of the daily application sources. Real sends
are deliberately explicit. Generation can run in parallel with Outreach artifact
preparation, but workbook writes and LinkedIn sends stay serialized.

## Nightly Production Automation

Nightly automation is the production entrypoint for discovery, the app-outreach
lane, shortlist/generation, Outreach Track 2, and the final run-scoped report.
The LaunchAgent runs unattended at 1:00am by default. Prompt/Snooze/Skip mode is
still available, but it is an explicit opt-in and is not the production default.

```bash
venv/bin/python discovery/scripts/run_nightly_pipeline.py
```

Generated-but-unapplied jobs remain in the active apply queue by default. They
should only leave the current queue when marked applied/closed or when the
forgotten-queue age-out rule moves them out. The old generated-archive behavior
is now opt-in via `--archive-generated-before-run`.

Generation is opt-in:

```bash
venv/bin/python discovery/scripts/run_nightly_pipeline.py --generate
```

The generation shortlist is queue-compatible and capped at 10 by default:

```bash
venv/bin/python discovery/scripts/build_generation_shortlist.py
python jobs.py --no-color generate \
  --queue \
  --queue-path "apps/Apply queues/current_apply_queue/generation_shortlist.json" \
  --resume-only \
  --budget-mode
```

Generation policy:

- Non-Handshake roles: `fit_score >= 7.0`
- Handshake internal apply: `fit_score >= 6.0`
- Handshake external apply: `fit_score >= 6.5`
- Handshake unknown flow: `fit_score >= 6.5`
- Daily generation cap: `10`

Every daily-engine invocation writes one exact manifest named
`<run-id>-daily-engine-run-manifest.json`. The nightly summary records it as
`daily_engine_manifest`; it is the authoritative pointer for:

- `invite_send_artifacts`, with actual per-company and total app-invite sends
- `linkedin_followup_draft_artifacts`
- `linkedin_followup_send_artifacts`
- `linkedin_reconcile_artifacts`
- the exact `source_metrics` and `action_queue`
- `source_families`, with explicit status and zero counts for LinkedIn,
  Handshake, JobSpy, startup sources, ResumeGenerator/app queue, and Track 2

Track 2 remains separately bound through
`outreach_maintenance.track_2_daily_run_artifact`. The orchestrator recognizes
the command's final `Run artifact:` line instead of accidentally taking an
earlier nested artifact. Before report generation it also augments the daily
manifest with `track_2_daily_run_artifacts`, full phase results, phase artifact
pointers, and planned-versus-actual phase counts. Email is explicit too:
`track_2_email_draft_artifacts` and `track_2_email_send_artifacts` are always
present, while `email_channel` records draft/sent counts, SMTP readiness, and
concrete blockers. The nightly path does not silently enable SMTP delivery;
review-bound approval and the separate live email command remain required.

The nightly finalizer always writes the JSON/Markdown summary and attempts the
Outreach daily report, even when an earlier subprocess raises. A failed stage
therefore produces a failed reportable run, not a missing run. Timestamped
launcher and full pipeline logs live under
`~/Library/Logs/ResumeGenerator/` by default.

### Release and install

Scheduled production runs are guarded by a release attestation. Both repos must
be on `main`, the production code paths must be clean, and each HEAD must equal
the tested SHA recorded in the attestation. Development and feature testing
should happen on a branch/worktree; do not point the LaunchAgent at that working
tree.

After both repos have passed their release suites and the tested commits are on
clean `main` branches, record the release:

```bash
venv/bin/python discovery/scripts/production_release.py record \
  --test-evidence "ResumeGenerator focused/full tests passed" \
  --test-evidence "Outreach focused/full tests passed"

venv/bin/python discovery/scripts/production_release.py check
```

Then install the unattended 1:00am LaunchAgent:

```bash
RESUMEGEN_NIGHTLY_ARGS="--cycle-config offcycle_light --generate ..." \
RESUMEGEN_NIGHTLY_LOAD=1 \
./discovery/scripts/install_nightly_launch_agent.sh 01:00
```

Before trusting the schedule, verify the same launchd context can read both
Desktop repos and validate the recorded SHAs without triggering any pipeline
action. Install a separate, temporary check-only label:

```bash
RESUMEGEN_NIGHTLY_LABEL=com.akshat.resumegenerator.nightly.preflight \
RESUMEGEN_NIGHTLY_MODE=check \
RESUMEGEN_NIGHTLY_LOAD=1 \
./discovery/scripts/install_nightly_launch_agent.sh 01:00

launchctl kickstart -k \
  "gui/$(id -u)/com.akshat.resumegenerator.nightly.preflight"
launchctl print \
  "gui/$(id -u)/com.akshat.resumegenerator.nightly.preflight"
```

Exit code `0` plus a JSON `status: valid` record in
`~/Library/Logs/ResumeGenerator/nightly_launchd.out.log` proves the launchd
process could read the Desktop repos and match the attestation. The check-only
path does not read or mutate scheduler state and cannot invoke the pipeline.
Boot out the temporary preflight label after verification. A nonzero result
must be fixed before enabling the production label; it commonly means a missing
attestation, dirty/changed HEAD, or macOS Desktop/TCC denial.

The installer only writes the plist unless `RESUMEGEN_NIGHTLY_LOAD=1` is set.
It checks every five minutes for catch-up after wake, but the scheduler records
the day's attempt before execution so a partial LinkedIn send cannot be replayed
blindly. Inspect the failed summary/report and explicitly force a retry only
after reconciling partial actions.

To use the old prompt flow for a non-production/manual setup:

```bash
RESUMEGEN_NIGHTLY_MODE=prompt ./discovery/scripts/install_nightly_launch_agent.sh 01:00
```

Nightly summaries link the per-run source metrics artifact and still include the
temporary JobSpy block. The source metrics report shows raw/discovered counts,
selected/new counts, fresh scoring, errors, accepted writes, outreach signals,
runtime, and accepted-per-minute by source. Use it for source trend audits before
changing filters again.

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
