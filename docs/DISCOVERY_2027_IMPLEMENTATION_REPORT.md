# Discovery 2027 implementation report

Date: 2026-08-18
Pipeline run: `2026-08-18 09:14`
Scope: ResumeGenerator discovery only; Outreach was read/tested but not modified.

## Outcome

The discovery system now has explicit Lane A (Fall 2026 internship), Lane B
(mid-2027/new-grad full-time), and Lane C (Handshake income-now) treatment.
The canonical profile and scorer use the same Lane B role families. Summer 2027
internships reject. Discovery metadata is stored in seven real workbook columns,
and JobSpy searches are isolated behind per-query checkpoints and timeouts.

The one authorized live run was partial under the unchanged source volume: all
60 queries were registered, 45 were attempted, 15 completed, 30 timed out, and
15 were skipped when the total scrape cap was reached. No query was retried.

## Workbook and Outreach compatibility

- Existing 18 columns were not reordered.
- Appended columns: `lane`, `deadline`, `deadline_source`, `everify_status`,
  `sponsorship_flag`, `classification`, `reject_reason`.
- `notes` remains human-readable. Legacy discovery metadata tokens remaining: 0.
- Workbook after the run: 2,638 Jobs rows, 25 columns.
- Deadline values present: 24; manual-lookup flags: 31.
- Lane B E-Verify status: 1,116 `unknown`; sponsorship soft flags: 18.
- Outreach's real `load_resume_jobs` imported 2,633 rows after the live write.
- Outreach bridge tests: 7 passed. No Outreach file was changed.

## Offline replay over the original 1,218 rows

| Lane | Keep | Reject | Unsure | Total |
|---|---:|---:|---:|---:|
| A | 175 | 755 | 218 | 1,148 |
| B | 8 | 52 | 10 | 70 |
| C | 0 | 0 | 0 | 0 |
| **Total** | **183** | **807** | **228** | **1,218** |

Largest reject reasons:

- 427 — Lane A result is not a Fall 2026 internship.
- 233 — no known role family in title and no target signal in the JD.
- 62 — 2027 internship is outside the Fall 2026 lane.
- 40 — Lane B has no explicit new-grad eligibility or mid-2027-or-later start.
- 7 — Summer 2027 internship begins after the May 2027 graduation.

Required row checks:

- Salesforce — Summer 2027 Intern, APM: both copies reject with the Summer 2027
  timing reason.
- Amazon — 2027 MBA Leadership Development Program Intern: rejects as a 2027
  internship outside Lane A.

The complete reason table, all 228 unsure rows, and all 1,218 row-level outcomes
are in `discovery/source_validation/20260818-090708-discovery-2027-existing-replay.{md,json}`.

## One live pipeline run

### Source execution

- Requested queries: 60 (13 Lane A, 47 Lane B).
- Attempted: 45.
- Completed: 15.
- Timed out and skipped: 30.
- Not started because the scrape cap was reached: 15.
- Source runtime: 5,368.0 seconds (1:29:28).
- Raw results: 2,408.
- New after deduplication: 1,420.
- Source throttle/429 events: 0.
- Scoring throttle/429 events: 0.
- Query 42 reproduced the previous JobSpy stall but was killed at 120 seconds;
  the run advanced and retained the first 41 outcomes.

The end-to-end process elapsed 6,914 seconds (1:55:14). The extra 1,546 seconds
were in-flight scoring threads draining after the scoring deadline. Post-run,
API requests and retry sleeps were bound to the same epoch deadline and the
supervisor/query waits were made sleep-safe. This correction was regression-tested;
the scrape was not rerun.

### Classification/scoring volume by lane

| Lane | Found | Proceed | Reject | Unsure | Unscored at cap |
|---|---:|---:|---:|---:|---:|
| A | 374 | 3 | 287 | 12 | 72 |
| B | 1,046 | 1 | 71 | 2 | 972 |
| C | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1,420** | **4** | **358** | **14** | **1,044** |

Largest live reject reasons:

- 163 — Lane A result is not a Fall 2026 internship.
- 69 — Lane B has no explicit new-grad eligibility or mid-2027-or-later start.
- 44 — no known role family in title and no target signal in the JD.
- 34 — 2027 internship is outside the Fall 2026 lane.
- 20 — Summer 2027 internship begins after May 2027 graduation.

The complete 27-reason count table is in the run log.

### Proceed rows

- TikTok — Product-Led-Growth Product Manager Project Intern, 2026 Start — 8.6.
- NETGEAR — Associate Product Manager — 8.2.
- TikTok — Product Manager Graduate, Content and Service Ads, 2027 Start — 8.2.
- TikTok — Data Product Manager Project Intern, 2026 Start — 8.2.

### Unsure review list

1. U.S. Customs and Border Protection — Audiovisual Production Specialist.
2. U.S. Customs and Border Protection — Mission Support Specialist.
3. Republic Services — MBA Intern.
4. Cintas — Management Trainee.
5. Pali - AI Relationship Coach — Growth Marketer.
6. TraceRoot.AI (YC S25) — GTM Engineer Intern.
7. Amcor — Intern - AI Innovation Engineer.
8. Brunswick — Industrial Design Intern - BBGTC.
9. Keytronic — Finance Intern (AR).
10. WindBorne Systems — GTM Lead.
11. TikTok — Category Management Project Intern (TikTok Shop - Operations), 2026 Start.
12. TikTok — Category Management Project Intern (TikTok Shop - Operation Center), 2026 Start.
13. OneMain Financial — Loan Sales Specialist.
14. Shield AI — Engineering Manager, Air Vehicle Mechanical Systems.

### Google APM / Meta RPM watch

- Exact Google APM listings: 0.
- Exact Meta RPM listings: 0.
- The completed `APM 2027` query returned 62 raw rows but no Google APM.
- Generic Google Product Manager and Meta Product Manager rows did surface, so
  the sources reach both companies but did not reach the named programmes.
- The dedicated `Rotational Product Manager 2027` query was one of the 15
  run-cap-skipped queries, so Meta RPM coverage was not fully tested.

This supports a separate deadline/watch mechanism for Google APM. Meta RPM also
needs a watch or a completed direct-query test; this run alone cannot distinguish
absence from the skipped targeted query.

## Unchanged by design

- No prioritisation, score threshold, per-query result cap, or budget changed.
- The standard 24-hour run still requested 100 results per site/query.
- `WEEKLY_JOBSPY_RESULTS` remains 60.
- The 13-to-60 query expansion is still approximately 4.6x source load.
- Consulting job-board queries remain excluded.
- Outreach was not modified.

## Follow-up source strategy (2026-08-20)

The 47 Lane B JobSpy query definitions remain available for explicit breadth
tests, but they are no longer scheduled in the daily or weekly write path. The
active JobSpy pack is deliberately demoted to the 13 Lane A queries; Lane B is
owned by the materially higher-yield LinkedIn browser path. Result caps,
prioritisation, scoring thresholds, and budgets remain unchanged.

## Verification

- Discovery 2027 focused tests: 17 passed.
- Broader non-nightly regression set: 107 passed.
- Outreach bridge tests: 7 passed.
- Workbook formula-error scan: 0 matches; Jobs, Archive, and ReviewCache rendered
  and visually inspected after the pipeline write.
- Six unrelated nightly/Chrome fixture tests remain failing in the current
  worktree/environment; they do not exercise these discovery changes.
