# Recruiting Engine Production Release

The nightly recruiting engine runs only released code. New sources, messaging
rules, browser selectors, and report features are developed and exercised in a
branch or isolated worktree. They enter the 20:00/01:00 Asia/Kolkata schedule only after their
focused tests pass, the combined smoke suite passes, and both repos are merged
to clean `main` commits.

## Release contract

1. Run focused tests for the changed ResumeGenerator and Outreach surfaces.
2. Run the non-live combined pipeline tests. Tests must use temporary artifact
   and workspace directories; they must never write to production `artifacts/`
   or perform LinkedIn/SMTP actions.
3. Merge the verified changes to each repo's `main` branch.
4. Confirm the production code paths are clean. Runtime data under workspace,
   reports, and ignored artifacts is not part of the source-code cleanliness
   check. ResumeGenerator's protected paths include `apply_assist/`, so the
   fill-to-review runner cannot become production through an unattested edit.
5. Record the exact tested HEADs with `production_release.py record`, including
   concise test evidence.
6. Run `production_release.py check`, then install/reload both LaunchAgent slots.
7. Run `nightly_prompt.py --production-check-only` from the intended execution
   context—or use a separate `RESUMEGEN_NIGHTLY_MODE=check` LaunchAgent label—to
   prove Desktop/TCC access without touching scheduler state or live actions.
8. Verify the next run by its nightly summary, exact daily-engine manifest,
   Track 2 run artifact, and HTML report. A missing pointer is a production
   failure; do not infer success from a browser window or a loose artifact.

If a same-day live proof has already sent invitations or messages, do not rerun
the live pipeline merely to obtain a green report. Fix and validate code with
fixture/no-send end-to-end tests, attest and reload the release, then treat the
next scheduled run as the first live candidate. Reconciliation must precede any
forced retry so daily limits and recipient safety remain authoritative.

Report acceptance also checks semantics, not just files: every run-scoped
report is named by and contains the nightly run ID; required source failures
remain non-green; feed captures need stable post permalinks; exact-run review
rows are separate from workspace carryover; and per-company mapping reports
attempted/completed/failed rather than presenting a phase budget as completed.

## Failure behavior

The pipeline is fail-reporting, not fail-silent. It attempts summary and report
finalization after subprocess exceptions. The scheduler records the attempt
before any live action, so it will not automatically replay a partially failed
run the same day. Reconcile the summary's exact invite/follow-up artifacts before
using `nightly_prompt.py --force`.

The complete Track 2 subprocess has a four-hour (`14400` second) outer deadline.
If it expires, the orchestrator terminates the isolated process group, records
return code `124` and `status: timed_out` with an explicit failure message, and
still finalizes the nightly summary, exact manifest, and report. Use
`--track-2-timeout-seconds 0` only for an explicitly supervised diagnostic run;
never blindly retry a timed-out live run before reconciling partial artifacts.

`--execute-track-2-daily-plan` runs live refresh, planning, enrichment, and
draft creation but does not deliver LinkedIn messages by itself. Delivery
requires the separate `--track-2-send-linkedin` flag. The canonical unattended
schedule has two reviewed contracts. The 20:00 `evening_delivery` slot is the
only Track 2 delivery/draft owner. The 01:00 `overnight_maintenance` slot still
runs reconciliation and maintenance but forbids LinkedIn delivery and sets
invite, follow-up, and email-draft limits to `0`. Both slots may claim the same
discovery lane only when its shared 48-hour attempt cadence is due; that lane
includes `--execute-sends --target-sends auto` for the app queue. The source of
truth is `discovery/scripts/nightly_contract.py`; inspect exact vectors with:

```bash
venv/bin/python discovery/scripts/nightly_contract.py print-slot evening_delivery maintenance
venv/bin/python discovery/scripts/nightly_contract.py print-slot overnight_maintenance maintenance
venv/bin/python discovery/scripts/nightly_contract.py print-slot evening_delivery discovery
```

The installer and due-time scheduler both validate the exact selected contract;
custom `RESUMEGEN_NIGHTLY_ARGS` vectors are rejected. Discovery, generation,
and app-queue sending remain one Daily Engine lane, so they all run at the
48-hour discovery cadence. Track 2 maintenance remains twice daily, but only
the evening slot can send or produce the reviewed draft batches.

Track 2's process return code is not sufficient evidence of success. The
orchestrator reads every exact-run `phase_results` row; `partial_failed`,
`failed*`, `timed_out`, or `incomplete*` in a required phase propagates to the
daily manifest, source breakdown, nightly summary, scheduler exit code, and
macOS failure notification.
Delivery uncertainty is equally non-green: `send_unknown_reserved`,
`partial_send_unknown_reserved`, literal `unknown`, nested run/status-count
evidence, and `planned`/`queued`/`prepared` after execution or delivery was
requested all fail the run. Mode is explicit: those pending statuses remain
valid for a pure preview, and invite `prepared` remains valid when execution was
requested with LinkedIn delivery deliberately disabled.

The production nightly, Daily Engine, and current-queue refresh paths never run
`sync_applied_pdfs.py`. Each reports that legacy lane as
`skipped_deprecated`; the presence of `Resume.pdf` is not submission evidence
and cannot mutate application status.

The scheduled guard exits before the pipeline when either repo is not on `main`,
a protected code path is dirty, an attestation is missing, or HEAD differs from
the recorded tested SHA. This is deliberate: a new feature cannot become
production merely because it exists in the shared checkout.

## Operational files

- Release attestation:
  `~/Library/Application Support/ResumeGenerator/production_release.json`
- Evening scheduler state:
  `~/Library/Application Support/ResumeGenerator/nightly_scheduler_state.evening.json`
- Overnight scheduler state:
  `~/Library/Application Support/ResumeGenerator/nightly_scheduler_state.overnight.json`
- Shared discovery-attempt state:
  `~/Library/Application Support/ResumeGenerator/nightly_discovery_cadence.json`
- Shared scheduler overlap lock:
  `~/Library/Application Support/ResumeGenerator/nightly_scheduler.lock`
- Shared cockpit mutation lock:
  `~/Library/Application Support/ResumeGenerator/operator_mutation.lock`
- Timestamped logs: `~/Library/Logs/ResumeGenerator/`
- Nightly summaries: `discovery/source_validation/*-nightly-pipeline-summary.json`
- Daily manifests: `discovery/source_validation/*-daily-engine-run-manifest.json`
- Final HTML report:
  `../Outreach/workspace/reports/daily_html/daily_run_report.html`

Both scheduler slots first serialize through `nightly_scheduler.lock`, which is
held for the complete selected run. The pipeline then owns
`nightly_pipeline.lock` and holds the shared
cockpit mutation lock for the whole run. A guarded cockpit write that already
owns the shared lock finishes before nightly proceeds; a new cockpit write
fails closed once the pipeline lock is busy.

The pipeline also gives any dedicated LinkedIn Chrome it launches an opaque,
per-run owner marker. Terminal cleanup closes only Chrome carrying that exact
marker and debug port. Normal Chrome and a pre-existing/user-owned CDP session
are never terminal-cleanup targets. If an unrelated debug session is unhealthy,
the automated reset refuses to kill it and the run fails visibly instead. A
nightly run never silently attaches to an unowned CDP listener: the listener
must carry the current run token. A stale token is replaced only when the
process is explicitly ResumeGenerator-owned and its Chrome binary, debug port,
and approved user-data directory all match; otherwise the run fails closed.

Legacy terminal summaries whose successful report was named by completion time
can be rebound without rerunning report logic or touching mutable latest
mirrors:

```bash
venv/bin/python discovery/scripts/repair_outreach_report_binding.py \
  --summary discovery/source_validation/<run-id>-nightly-pipeline-summary.json
# Review the preview, then repeat with --apply.
```
