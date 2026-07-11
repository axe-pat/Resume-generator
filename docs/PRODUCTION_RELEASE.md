# Recruiting Engine Production Release

The nightly recruiting engine runs only released code. New sources, messaging
rules, browser selectors, and report features are developed and exercised in a
branch or isolated worktree. They enter the 1:00am pipeline only after their
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
   check.
5. Record the exact tested HEADs with `production_release.py record`, including
   concise test evidence.
6. Run `production_release.py check`, then install/reload the LaunchAgent.
7. Run `nightly_prompt.py --production-check-only` from the intended execution
   context—or use a separate `RESUMEGEN_NIGHTLY_MODE=check` LaunchAgent label—to
   prove Desktop/TCC access without touching scheduler state or live actions.
8. Verify the next run by its nightly summary, exact daily-engine manifest,
   Track 2 run artifact, and HTML report. A missing pointer is a production
   failure; do not infer success from a browser window or a loose artifact.

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

The scheduled guard exits before the pipeline when either repo is not on `main`,
a protected code path is dirty, an attestation is missing, or HEAD differs from
the recorded tested SHA. This is deliberate: a new feature cannot become
production merely because it exists in the shared checkout.

## Operational files

- Release attestation:
  `~/Library/Application Support/ResumeGenerator/production_release.json`
- Scheduler state:
  `~/Library/Application Support/ResumeGenerator/nightly_scheduler_state.json`
- Shared cockpit mutation lock:
  `~/Library/Application Support/ResumeGenerator/operator_mutation.lock`
- Timestamped logs: `~/Library/Logs/ResumeGenerator/`
- Nightly summaries: `discovery/source_validation/*-nightly-pipeline-summary.json`
- Daily manifests: `discovery/source_validation/*-daily-engine-run-manifest.json`
- Final HTML report:
  `../Outreach/workspace/reports/daily_html/daily_run_report.html`

The pipeline owns `nightly_pipeline.lock` first and then holds the shared
cockpit mutation lock for the whole run. A guarded cockpit write that already
owns the shared lock finishes before nightly proceeds; a new cockpit write
fails closed once the pipeline lock is busy.

Legacy terminal summaries whose successful report was named by completion time
can be rebound without rerunning report logic or touching mutable latest
mirrors:

```bash
venv/bin/python discovery/scripts/repair_outreach_report_binding.py \
  --summary discovery/source_validation/<run-id>-nightly-pipeline-summary.json
# Review the preview, then repeat with --apply.
```
