# Step 1 review checkpoint — durable content and release contract

## Outcome

Step 1 is implemented but **not live**. The legacy generator remains the default,
no reviewed variant has been newly exposed to selection, and no queue resume was
generated or replaced.

This step makes the Amazon and StudyFetch gains durable in three layers:

1. **Variant quality:** 22 exact final-resume variants are captured with one-time
   admission metadata; 21 are proposed for promotion and one is held.
2. **Assembly quality:** Experience and Projects now share one evidence budget;
   the normal 10-bullet professional spine and the StudyFetch-style project
   exception are both explicitly bounded.
3. **Artifact safety:** a run cannot report success unless its final PDF is one
   page, contains the complete expected text, and preserves the prior released
   artifact if validation fails.

Only 5 of the 22 exact final-resume variants currently appear in the live PM or
NONPM prompt. Approval therefore adds 16 genuinely new winning variants rather
than relabeling the existing pool.

## Your four decisions

### 1. Exact variants — **CRITICAL**

- [ ] Approve the 21 `PROMOTE NOW` candidates in the
  [full exact-text review](GOLD_VARIANT_DURABILITY_REVIEW_2026-09-02.md).
- [ ] Mark any candidate `HOLD` and add a short reason beside it.

The review file puts **HIGH-IMPACT** on the variants to read first. Exact bullet
text and source fixture are evidence; archetype, scores, outcome tier, and line
cost are review judgments.

### 2. Gojek latency wording — **CRITICAL**

- [ ] Use the clearer StudyFetch variant for future selection:

  > Traded live fare recalculation for sub-second quotes by pre-caching pricing across 12 high-demand corridors; held fare variance within 4%, cut latency 70%, and recovered ~28K monthly rides.

Recommended. Keep the submitted Amazon wording only in its historical fixture;
do not expose both near-duplicates to the selector.

### 3. One-time variant admission rules — **CRITICAL**

- [ ] Approve all five gates below, or annotate changes in
  [the canonical playbook](../variants/VARIANT_FINALS_v4.md).

Every selectable variant must:

1. make one argument;
2. use a mechanism that supports that argument;
3. end in an outcome that closes that argument;
4. be understandable without company-internal context; and
5. use the strongest attributable outcome available for that story.

These augment, rather than replace, the existing playbook and the prior
stakes/difficulty/defensibility/distinctiveness gates.

### 4. Page-wide proof modes — **CRITICAL**

- [ ] Approve both bounded modes.

**Inline is the default:** 10 Experience bullets, with 9 allowed for quality or
page fit and 11 allowed only for a distinct additional signal. All five career
blocks remain visible; FlairX has at least two bullets on product resumes and
Optum at least one.

**Project replacement is the exception:** use it only when independent work is
the strongest proof of a top JD screen. Add 2–3 admitted Project bullets, remove
1–2 lower-marginal Experience bullets, retain all five career blocks, and keep
10–11 total proof units. This reproduces StudyFetch's 8 Experience + 3 Projects
without turning that one resume into the general default.

## Implemented safety checks

- Explicit Lane C metadata cannot fall into PM/NONPM generation. It currently
  blocks until the dedicated Lane C adapter is connected.
- Missing, truncated, role-mismatched, and suspiciously duplicated JDs are
  surfaced before generation.
- Multiple generated content sections, QC blockers, multi-page PDFs, and missing
  rendered text block release.
- PDF publication is atomic and preserves the incumbent artifact on failure.
- Score-only revisions update their source TXT atomically only after release
  validation succeeds.

## Verification

- Focused rebuild suite: **138 passed, 1 skipped**.
- Full repository suite: **346 passed, 1 skipped, 7 failed**. The seven failures
  are existing Chrome/nightly scheduler sandbox tests outside the resume rebuild;
  none are in the focused resume, routing, preflight, or artifact-release suite.
- No commit has been created yet because this checkpoint contains human-owned
  content and policy decisions. Existing unrelated worktree changes are untouched.

## After approval

Step 2 will promote only approved variants, connect the assembly resolver in
shadow mode, finish the dedicated Lane C adapter, and produce the first comparison
batch without replacing legacy outputs. The broad legacy pool will then be
machine-triaged in profile-sized waves, with only promote/hold/quarantine edge
cases sent for human review.
