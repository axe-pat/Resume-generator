# Resume generator v2 — architecture review and upgrade path

Written 2026-08-28, after the Amazon PMT exercise produced a 9.2 manual resume against
the stock generator's 8.4 on the same JD.

---

## Part 1 — What actually created the 0.8-point gap

I catalogued every correction made during the Amazon session and sorted it by what would
have been needed to catch it automatically. This is the whole basis for the plan below.

### Group A — deterministic. No AI required. Currently uncaught. (9 of 20)

| What was caught | Rule that catches it |
|---|---|
| `$1.2M` appearing at both FlairX and Intuit | Same figure in ≥2 bullets |
| `Unblocked` opening three bullets | Duplicate opening verb across section |
| `roadmap pivot` ending two consecutive Intuit bullets | Duplicate outcome phrase, n-gram overlap |
| `80K+` in two consecutive Intuit bullets | Duplicate scale figure in same company block |
| Skills rows: 3 without terminal periods, 2 with | Terminal punctuation consistency per block |
| `August 2020` in Education vs `Jul 2020` in Experience | Date format consistency across document |
| F2 predicted to spill to 3 lines at 216 chars | Char→line prediction (calibration exists: 185=2 lines, 216=3) |
| "Marshall Leadership Fellow" — a credential that exists nowhere | Every proper noun and figure must resolve to a source variant |
| Generator's own output rendering at 3 pages | Read the rendered PDF page count before declaring success |

**This is the single biggest cheap win in the system.** Nine of twenty corrections, all
mechanical, none currently checked, and two of them (the invented credential, the 3-page
render) are catastrophic rather than cosmetic.

### Group B — needs a critic with an explicit rubric. Automatable. (6 of 20)

| What was caught | Axis that catches it |
|---|---|
| `When a migration script…` — subordinate-conjunction opener | Opener form: verb-first required |
| `: conversion up 9%, $3.2M` — fragment list reads casual | Register: outcomes tied by verb, not appended |
| "Reads like I caught a bug" | Identity: does the bullet's subject read as product or execution |
| `onboarded without custom engineering` repeating `replacing bespoke builds` | Intra-bullet redundancy |
| `$3,000` sitting next to `$3.2M` | Scale coherence across figures on the page |
| p95-vs-average presented as a hard-won finding | Insight difficulty: would a competent peer have found this in five minutes |

The current scorer covers craft, archetype, and readability well. It does not cover any of
these six. They are all expressible as rubric dimensions.

### Group C — genuinely required you. (5 of 20)

- FlairX location: San Francisco or Remote
- Is "8-team incident response" the real figure
- Is `$2M` the real projection or an adjustment
- Title risk appetite (bare `Product Owner` vs the doubled form)
- Whether `unblocked` is the honest verb on the $1.2M

**All five are ground truth or risk tolerance. None is a judgment about writing.** That is
the finding that sets the ceiling: the irreducible human input is a facts ledger and a
handful of risk calls, not a day of line editing.

---

## Part 2 — What is actually wrong with the generator

Read against that catalogue, the gaps are specific.

**1. The architecture is hard-coded and cannot produce the winning shape.**
`freeform_master_v2.txt` fixes 11 bullets at FlairX 3 / Gojek 3 / Hevo 3 / Intuit 2, with no
Optum block and no Fluo block in Experience. The resume that won was **10 bullets across five
companies at 2/3/2/2/1**. The generator could not have produced it at any temperature. This is
the largest structural limiter in the system and it is not a model problem.

**2. The scorer reports a mean, and means hide failures.**
Four dimensions, averaged into one holistic number. A bullet that scores 9 on craft and 3 on
identity lands at a passing 6 and never reaches Pass 4. Every failure in Group B above is
exactly this shape: well-written, wrong on one axis.

**3. Nothing evaluates the page.** The scorer takes `{{EXPERIENCE_SECTION}}` and scores
bullets. It never sees the title lines, the summary, the skills block, the education block, or
the interaction between them. Every Group A duplication is a page-level property, invisible by
construction.

**4. No provenance chain.** Nothing verifies that a figure in the output existed in the source
variant. This is how a fabricated credential reached a rendered, apply-ready .docx.

**5. No render verification.** The 3-page failure this week was a parsing bug: the run output
contained multiple `SECTION 0` blocks and `extract_sections` took the first, which was the
reasoning block. Nothing downstream looked at the artifact, so an 8.4 score was reported on a
document that was unusable.

**6. Story pools are embedded, not loaded.** `FLUO_STORY_POOL_V1.md` exists and is good. The
generator does not read it; it uses older inline variants. Every pool improvement requires a
prompt edit, so pools and generator drift apart by default.

**7. No eligibility gate.** The Databricks degree-language problem and the Appian sponsorship
line were both caught by a human reading the posting. Tailoring effort is currently spent
before anyone checks whether the role is applicable.

**8. Nothing accumulates.** Twenty judgments were made this session. None of them are captured
anywhere the generator will see. Application 41 will make the same mistakes as application 1.

---

## Part 3 — The upgrade path, in build order

Ordered by value per hour of work, not by ambition.

### T0 · Fix the breakage — hours

- `extract_sections`: select the **last** `SECTION 0` block, or reject output containing more
  than one. This is the 3-page bug.
- Load `FLUO_STORY_POOL_V1.md` and the FlairX pool from disk at runtime instead of inlining.
- Render the PDF and assert page count == 1 before any run is reported as successful.

Nothing here is clever. All of it is currently costing you finished documents.

### T1 · Deterministic lint — one day, largest single return

A `lint.py` that runs on the assembled document, pre-render, and **blocks**:

```
duplicate_figure          same numeric token in ≥2 bullets
duplicate_opening_verb    same first word across bullets
duplicate_phrase          ≥3-word overlap between any two bullets
scale_coherence           smallest and largest $ figures within ~2 orders of magnitude
provenance                every figure and proper noun resolves to a source variant
punctuation_consistency   terminal periods uniform within each block
date_format               one month format across the whole document
line_prediction           char count → predicted lines, flag spills
page_count                rendered PDF is one page
```

Calibrate `line_prediction` from documents you have already rendered: 185 chars renders 2
lines, 216 renders 3, in the current layout.

**Expected effect: 8.4 → roughly 8.8, and the elimination of every catastrophic failure mode
observed so far.** No model calls.

### T2 · Unfreeze the architecture — one to two days

Move company count and bullet allocation out of the prompt and into Pass 0's strategy output:

```json
{ "blocks": [
  {"key":"flairx","bullets":2}, {"key":"gojek","bullets":3},
  {"key":"hevo","bullets":2},   {"key":"intuit","bullets":2},
  {"key":"optum","bullets":1} ],
  "fluo_placement": "skills" }
```

Add Optum and Fluo as selectable blocks with their own pools. Total bullets become a page
budget the strategy pass allocates, not a constant. Without this the generator cannot reach
the shape that won, so every later improvement is capped.

### T3 · Multi-axis scorecard — two days

Replace the single holistic number with a per-bullet vector, and **report the minimum, not
the mean**:

`identity · leadership-principle · jd-language · scale-legibility · opener-form ·
architecture-distinctness · technical-depth · human-presence · non-duplication · defensibility`

Pass 4 then targets the lowest axis rather than the lowest average. Add two page-level
coverage checks: a JD-keyword matrix, and for Amazon-family reqs a leadership-principle
coverage map (target 8+ distinct principles, none carrying more than 4 bullets).

The current scorer's craft rubric is good and should be kept as one axis, not replaced.

### T4 · Adversarial selection — three days, use selectively

This is the mechanism that reproduces what actually happened in the Amazon session:

```
for each slot:
    generate 3 candidates
    critic argues against each, given JD + rubric + rejection ledger
    judge selects, and must state what it beat and why
```

The "what it beat and why" requirement matters — it forces an explicit comparison rather than
a vague preference, which is where the quality showed up in this session. Costs roughly 3–4×
tokens. Reserve for tier-1 applications.

### T5 · Rejection ledger — ongoing, and this is the answer to "can it develop gut feel"

A file of `(before, after, why)` triples from every session, injected into the generator and
critic prompts as negative few-shot examples. This session alone produces about twenty, and
they are specific and reusable: no `When` openers, no fragment-list outcomes, no small dollar
figures beside large ones, no repeated outcome phrases within a block.

This is not self-improving weights and it should not be sold as such. It is a growing corpus
of your judgments that makes application 41 cheaper than application 1. It is also the only
component here that compounds.

### T6 · Facts ledger — the only part that needs you

One file of confirmed ground truth with provenance and status per claim
(`designed / prototyped / shipped / presented / proposed`). The lint provenance check reads
from it. New experiences get added once and are then reusable forever.

This is Group C from Part 1, and it is the entire irreducible human input to the system.

### T7 · Eligibility gate — half a day

Before any tailoring: degree language, sponsorship language, start-date compatibility, work
authorization. The other agent added this to its workflow and it correctly flagged Databricks
and Appian. It belongs in the pipeline, ahead of generation, not in a person's head.

---

## Part 4 — Is it the model or the architecture

**The architecture, with specific evidence.**

The generator scored 8.4 while producing an unusable three-page document, from a shape that
structurally could not match the winner, judged by a scorer that cannot see the page. None of
those three facts is a model limitation. A better model inside the same harness produces a
better-written three-page document with the same duplications.

The honest ceiling estimate:

| Configuration | Expected |
|---|---|
| Today | 8.4, unreliable |
| T0 + T1 | ~8.8, reliable |
| + T2 + T3 | ~9.0 |
| + T4 + T5, tier-1 only | ~9.2, matching this session |
| Human in the loop on top | ~9.4 |

That last row is the finding worth keeping. **The human-in-the-loop version beat the solo-AI
version by 0.8 points on the same source material.** So the target is not full automation. It
is making your twenty minutes worth as much as today's full day.

---

## Part 5 — Scaling to forty applications

**Most of this session was not Amazon-specific.** What transfers: the bullet set itself, the
titles, the summary structure, the Fluo line, every lint rule, and the rejection ledger. What
was Amazon-only: the leadership-principle map and the shared-resume-across-four-reqs
constraint. Roughly 80% of the day is now permanent asset.

**Tier the queue.** Forty applications do not all deserve 9.2.

| Tier | Volume | Treatment | Your time |
|---|---|---|---|
| 1 — top targets | 5–8 | Full T4 adversarial + your review | 20 min each |
| 2 — real but not critical | ~15 | Generator + lint + spot-check the scorecard | 5 min each |
| 3 — volume | rest | Generator + lint, no review | 0 |

Tier 3 does not need to reach 9.2. It needs to reach a reliable 8.5 and never ship a
three-page document or an invented credential. T0 and T1 alone deliver that.

---

## Recommended first sprint

1. T0 — the three bug fixes
2. T1 — `lint.py` with the nine checks
3. T6 — seed the facts ledger from the Amazon resume, which is now verified
4. T5 — seed the rejection ledger with this session's twenty
5. Make the Amazon resume the regression fixture: any generator change must reproduce it or
   explain why not

That is roughly two days and it moves tier-3 volume from unreliable to safe, which is what is
actually blocking the other thirty-nine applications.
