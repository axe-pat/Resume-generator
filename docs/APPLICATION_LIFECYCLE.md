# Application Lifecycle Transitions

`applied` and `closed` are artifact-moving lifecycle outcomes, not ordinary
tracker labels. Use the fixed one-job transition command instead of
`jobs.py mark`:

```bash
# Preview: validates the tracker row, current-queue indexes, artifact tree,
# destination, and all locks without changing files.
venv/bin/python discovery/scripts/transition_application.py \
  --id 1949 --status applied --dry-run --json

# After the user confirms that the application was submitted:
venv/bin/python discovery/scripts/transition_application.py \
  --id 1949 --status applied --confirm "APPLY 1949" --json

# After the user confirms that the role should be closed/not applied:
venv/bin/python discovery/scripts/transition_application.py \
  --id 1949 --status not-applied --confirm "CLOSE 1949" --json
```

`not-applied` is stored as tracker status `closed`. The complete role directory
is moved to `apps/archive/applied/<date>/...` or
`apps/archive/closed/<date>/...` before `jobs.xlsx` is changed. The command
also removes the job from the current queue's JSON/text indexes, invalidates
the old generation shortlist, records `application_transition.json` beside the
archived artifacts, and sets `date_applied` only for an applied transition.

## Safety contract

- Exactly one positive numeric job ID and one current-queue artifact directory
  must resolve. Duplicate tracker rows, duplicate folders, missing metadata,
  symlinks, stale queue indexes, pre-existing destinations, and conflicting
  terminal statuses fail closed.
- The nightly, shared operator, current-queue, and workbook advisory locks are
  held or proven before mutation. Lock contention exits with code `75` without
  waiting behind or racing another producer.
- A persistent transaction journal snapshots `jobs.xlsx`, its backup, and all
  mutable queue indexes. Any exception restores the workbook and indexes and
  moves the complete artifact tree back. A later invocation first rolls back
  an interrupted uncommitted journal.
- Repeating an already-completed transition is idempotent only when the tracker,
  durable archive, transition audit, and absent queue entry all agree.
- `jobs.py mark --status applied|closed` is rejected because it cannot satisfy
  this archive-first contract.
- Tracker-only `parked/rejected/skip/skipped` remains available for rows proven
  absent from the live queue. It fails closed when the row ID, metadata, or
  folder path is live, or when the queue indexes cannot be validated.
- Nightly, Daily Engine, and current-queue refresh never invoke the deprecated
  `sync_applied_pdfs.py` helper. The helper itself is report-only, and all
  callers report the lane as `skipped_deprecated`; PDF presence is never
  submission evidence.
- Every existing lexical ancestor of the computed archive target is checked
  for symlinks before preview or mutation, including `archive/<status>` and
  deeper preserved queue-path descendants.

The private operator companion may add the hidden
`--external-operator-lock` flag only while it retains the shared operator lock
for the child process. The command verifies that an external owner really holds
that lock; direct callers must omit the flag and let the command acquire it.
