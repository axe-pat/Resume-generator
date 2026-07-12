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
  ResumeGenerator nightly generates tailored resumes; cover letters stay on demand
  Outreach finds people, generates notes, sends/logs touchpoints
```

The design rule is simple: discovery is shared, execution stays specialized.
ResumeGenerator remains the application system of record. Outreach remains the
relationship system of record. The production nightly generation command uses
`--resume-only --budget-mode`; generate a cover letter separately only when an
ATS or application path actually requires one.

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

The importer emits a versioned run artifact even when all observed links are
duplicates and zero candidates remain. In production, the Daily Engine passes
an exact artifact path through the Handshake wrapper, validates it, and uses its
run-scoped `input_rows`, skips, candidates, fetches, scores, and accepted count
for Source Breakdown. It never falls back to a stale `latest` Handshake log;
missing or invalid output keeps the stage non-green.
Zero candidates after dedupe is a valid completed run. All JD fetch/processing
failures mark it failed; mixed successes and errors mark it partial-failed, and
the error count is carried into the manifest/source family.

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
  --rediscover-startup-apply \
  --rediscover-relationship-artifacts \
  --limit-companies 20 --limit-jobs 50
```

The first command emits a versioned structured artifact on every execution,
including zero-new and best-effort failure cases. The second command is an
explicit standalone re-fetch for source-health work. In the production Daily
Engine, the report receives the exact startup-run artifact and exact report
output path; it never re-fetches or chooses a `latest` startup artifact. A
missing, malformed, or non-green pointer fails closed and keeps the run
non-green.

Startup scoring health preserves `decision=Error`: all-error scoring is
`failed`, mixed success/errors is `partial_failed`, and zero-new remains a green
`completed` result. The artifact, source metrics, and top-level source family all
carry the error count.

The production relationship lane captures the exact `Artifact:` path from every
configured Outreach `discover-source` command, validates that each artifact
belongs to that source, and passes the exact mapping into the report. Missing or
non-green members produce failed/partial-failed health; mtime-based selection is
only available in explicit standalone rediscovery mode.

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

Execution preserves more than the company name. For every selected company the
Daily Engine carries the exact `role_title`, source, and queue bucket into the
company-run manifest. When a concrete role exists it invokes Outreach with
`--target-role-title`; role-family messaging therefore follows the application
evidence before any company-level tracker context or Product fallback. A
duplicate company in a later relationship bucket cannot overwrite the earlier
`application_plus_outreach` role/source provenance.

The nightly wrapper now passes this exact current-run action queue into Outreach's
shared discovery builder. The resulting
`../Outreach/workspace/shared_discovery/shared_daily_queue.{json,csv}` merges
application roles with YC/Built In company targets, approved company-watchlist
entries, and warm Outreach contacts. It validates exact pointers, dedupes companies,
preserves source provenance, and labels every row ready, human-review-required, or
buffered. It does not write back into `jobs.xlsx` or authorize a send.

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

The Daily Engine also retains a standalone, supervised LinkedIn inbox lane. It
can reconcile messages, emit a reusable draft artifact, and optionally send the
approved recommendation classes. Its offset pull remains resumable (previously
seen threads are still eligible for reconciliation), and a successful command
without a readable result artifact is recorded as a failure. This lane is not
used by the scheduled nightly wrapper.

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

Scheduled LinkedIn inbox/follow-up ownership is deliberately singular: Track 2
owns refresh, reconciliation, cadence selection, and optional sends. The nightly
wrapper always passes `--skip-linkedin-followups` to the Daily Engine, then
invokes the bounded Track 2 plan with `--refresh-linkedin` and the cycle's
follow-up limit.
It adds `--send-linkedin` only when the separate nightly
`--track-2-send-linkedin` flag is present. This lets a supervised/manual command
run the full live preparation/draft flow without delivery. Production unattended
automation is intentionally live: its canonical contract includes both
`--execute-sends --target-sends auto` and
`--execute-track-2-daily-plan --track-2-send-linkedin`. The deprecated nightly
`--execute-linkedin-followups` flag is
rejected before pipeline side effects begin. Use `run_daily_engine.py` directly
only when intentionally operating the standalone supervised lane; never run both
lanes for the same scheduled run.

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

The same augmentation writes `nightly_extensions` for the normalized run ID,
canonical LinkedIn owner, company-news capture, reviewed company discovery, and
the shared discovery queue. Only readable files are emitted into the typed
`company_news_artifacts`, `company_discovery_artifacts`, and
`shared_discovery_artifacts` lists; missing files remain explicit failed/skipped
statuses rather than inheriting an older workspace artifact.

The nightly finalizer always writes the JSON/Markdown summary and attempts the
Outreach daily report, even when an earlier subprocess raises. A failed stage
therefore produces a failed reportable run, not a missing run. Timestamped
launcher and full pipeline logs live under
`~/Library/Logs/ResumeGenerator/` by default.

LinkedIn job discovery has a 30-minute (`1800` second) wall-clock bound. The
extractor still checkpoints partial raw results and scores them after a timeout,
but `source_families.linkedin.status=timed_out` keeps both the nightly summary
and daily report non-green. This longer bound accommodates normal multi-page
LinkedIn latency while preserving deterministic process-group cleanup.

Track 2 has a four-hour (`14400` second) outer deadline by default. Override it
with `--track-2-timeout-seconds`; `0` disables the deadline for an explicitly
supervised diagnostic run. On timeout, the orchestrator terminates Track 2's
isolated subprocess group, records return code `124`, `status: timed_out`, the
configured deadline, and an explicit reconciliation warning in the exact
summary/manifest, then still runs report finalization. Do not force a retry
until the partial Track 2 artifacts have been reconciled against LinkedIn.
Even when the Track 2 command exits `0`, a nested required phase with
`partial_failed`, `failed*`, `timed_out`, or `incomplete*` makes the complete
nightly non-green. That status reaches the exact manifest, source breakdown,
summary, scheduler state/exit, and notification.
The same applies to delivery-uncertain evidence such as
`send_unknown_reserved`, `partial_send_unknown_reserved`, literal `unknown`, or
unknown reservation counts hidden under a nominally sent phase. When
`execute=true`/`send_linkedin=true`, terminal `planned`, `queued`, or `prepared`
work is incomplete. Those statuses remain valid in a pure preview, and prepared
invite candidates remain valid in an explicitly no-send execution.

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
RESUMEGEN_NIGHTLY_LOAD=1 \
./discovery/scripts/install_nightly_launch_agent.sh 01:00
```

With no `RESUMEGEN_NIGHTLY_ARGS` override, the installer obtains the exact live
argument vector from `discovery/scripts/nightly_contract.py`. In unattended mode
it refuses a custom vector that omits app delivery, Track 2 delivery, selects
zero app sends, or changes the reviewed bounded cycle values. For a supervised
enrichment-only diagnostic, invoke `run_nightly_pipeline.py` directly or use
prompt mode; do not weaken the production label.

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
Its `ProgramArguments` call the configured `PYTHON_BIN` and
`nightly_prompt.py` directly, so launchd uses the same audited interpreter that
was selected during installation.
It checks every five minutes for catch-up after wake, but these `StartInterval`
due checks are not recruiting runs: they do not launch the pipeline, show a run
notification, touch the actual-run fields in scheduler state, or own a browser
when the day is already handled/not due. The scheduler records the day's actual
attempt before execution so a partial LinkedIn send cannot be replayed blindly.
Inspect the failed summary/report and explicitly force a retry only after
reconciling partial actions.

To use the old prompt flow for a non-production/manual setup:

```bash
RESUMEGEN_NIGHTLY_MODE=prompt ./discovery/scripts/install_nightly_launch_agent.sh 01:00
```

The LaunchAgent `last exit code` is not the source of truth because the 5-minute
prompt checker can later exit cleanly with "not due" and overwrite it. For run
debugging, inspect:

- timestamped pipeline logs in `~/Library/Logs/ResumeGenerator/nightly_pipeline_*.log`
- scheduler state in `~/Library/Application Support/ResumeGenerator/nightly_scheduler_state.json`
- summary artifacts in `discovery/source_validation/*nightly-pipeline-summary.{json,md}`

The scheduler state also records `last_run_was_actual_pipeline`,
`last_run_status`, and the exact `last_run_summary`. Product surfaces should use
those fields rather than presenting a clean five-minute due-check exit as a new
successful run.

Any dedicated LinkedIn Chrome launched during the nightly receives a unique
per-run owner marker. Finalization closes only the Chrome root carrying that
exact marker and port, including after pipeline exceptions. Normal Chrome and an
unrelated user-owned debug session are preserved. An automated reset likewise
refuses to terminate an unowned CDP session. While a nightly token is active,
preflight also refuses to reuse an unowned listener. It may replace an older
ResumeGenerator token only after exact Chrome, port, and approved-profile
validation; ambiguous listeners fail closed.

LinkedIn/Chrome preflight retries the live-session check before failing. If the
daily engine still fails, the nightly wrapper records `daily_engine_returncode`,
continues non-LinkedIn maintenance where possible, rebuilds Outreach Track 2
account artifacts, writes a failure summary, and exits nonzero so the failure is
visible without making the whole run look like it did nothing.

Nightly summaries link the per-run source metrics artifact and still include the
temporary JobSpy block. The source metrics report shows raw/discovered counts,
selected/new counts, fresh scoring, errors, accepted writes, outreach signals,
runtime, and accepted-per-minute by source. Use it for source trend audits before
changing filters again.

The same nightly maintenance pass also captures the configured public company/news
feeds into Outreach's reviewed watchlist contract. Source status and counts are
recorded from the exact capture artifact; the cumulative candidate ledger is never
presented as current-run source activity. Use `--skip-company-news` or
`--skip-shared-discovery` only for an intentional degraded run.

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
