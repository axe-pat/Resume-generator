# Plan for generating 47 resumes without per-resume review

The design goal changes when you stop reviewing. It is no longer *maximise peak quality*. It is
**raise the floor and make catastrophic output impossible**. A reliable 8.6 across 47 beats a
9.3 average that ships one fabricated credential to Databricks.

Ordered by that priority throughout.

---

## Part 1 — Decisions to lock now, not leave to the model

### Allocation: fixed shape, chosen by lane. Not dynamic.

You asked fixed or dynamic. Neither: **fixed within a lane, and the only model decision is which
lane.** That converts a continuous generation choice into a discrete classification, which is
what you want running unattended — a router picking one of three validated shapes has far fewer
failure modes than a model allocating bullets per JD.

| Template | Roles | Shape | Fluo | Summary |
|---|---|---|---|---|
| **PM** | Lane A + Lane B product/technical (~29) | FlairX 2 · Gojek 3 · Hevo 2 · Intuit 2 · Optum 1 = **10** | Skills row | `PRODUCT MANAGEMENT` |
| **NONPM** | Ops leadership, supplier quality, strategy/ops (~12: Philips OLDP, Stellantis GPSQ, Amazon Pathways, Celonis, Momentum…) | same 10, non-PM variant pool | `PROJECTS & CONSULTING` | `PROFESSIONAL EXPERIENCE` |
| **LANE-C** | USC campus roles (6) | PROFILE · EDUCATION · CAMPUS & STUDENT-FACING · PROFESSIONAL EXPERIENCE · SKILLS+Languages | **top experience block**, framed on international students | `PROFILE` |

PM and NONPM deliberately share a shape. They differ in variant selection and section headers,
not architecture — one less thing to validate.

**LANE-C already exists** as `resume/lane_c_docx.py` from the Aug-20 commit. It was the best
thing in that commit and it should not be rebuilt.

**Fluo placement is locked per template and is never a per-JD decision.** The Amazon reasoning
generalises: two unknown two-month companies at the top of a PM resume costs more than the
currency signal gains. On Lane C the calculus inverts — a USC office reading about international
students wants Fluo first.

### The Amazon ten become the canonical pool

Eight of the bullets improved materially this session. **They currently exist only in the Amazon
folder.** Promote them into the story pools as the new default variants, or 47 resumes get
generated from the older, weaker text.

---

## Part 2 — Hard gates. Any failure blocks the run.

These are not scoring dimensions. They abort.

| Gate | Why |
|---|---|
| **Provenance** — every figure and proper noun resolves to the facts ledger | "Marshall Leadership Fellow" reached a rendered, apply-ready document once in ~5 attempts. At 47 unattended, assume it happens several times. This is the single most important gate in the system. |
| **Page count == 1** from the rendered PDF | Three lines of code. Catches the whole class, not just the SECTION 0 bug. |
| **Section integrity** — required sections present, exactly one SECTION 0, no reasoning text in output | The observed failure mode. |
| **Eligibility** — degree language, sponsorship, start date, work authorisation, checked *before* generation | Caught Databricks' degree wording and Appian's sponsorship line. Tailoring effort currently gets spent before anyone checks applicability. |
| **Duplicate figure / opening verb / ≥3-word phrase** | `$1.2M` twice, `Unblocked` ×3, `roadmap pivot` ×2, `80K+` ×2 — all shipped past the current scorer. |
| **Scale coherence** — smallest and largest dollar figures within ~2 orders of magnitude | `$3,000` beside `$3.2M`. |
| **Format consistency** — one date format, uniform terminal punctuation per block | Visible on the rendered page. |

Ten of the twenty corrections this session are on this list, and all ten are deterministic. No
model calls. This is the largest return per hour available.

---

## Part 3 — Pool hygiene is now the whole game

**This is the part I would spend the most time on, and it is easy to skip.**

Without per-resume review, the generator only *selects*; it does not create. Output quality is
therefore bounded almost entirely by the pool. If every variant is a 9, the worst possible
resume is a poorly-selected set of 9s. If the pool contains 7s, some of your 47 ship 7s, and you
will not see them.

**Audit every variant in every pool once, against the four variant-level gates:**

- **Stakes** — is the underlying task significant? Not "does it read well." The generalised form
  of the bug-catch problem: is the bullet's subject a decision or a consequence, rather than a
  detection or a task completed?
- **Difficulty** — would a competent peer have reached this in five minutes? The p95-vs-average
  bullet failed here while passing every craft check.
- **Defensibility** — survives twenty minutes of drilling.
- **Provenance** — resolves to a source.

Delete or fix anything that fails. A variant that fails Stakes cannot be rescued downstream by
any amount of generation, which is exactly why this belongs at pool admission and not in the
per-run scorer.

**Two specific cleanups while you are in there:**

1. **`FLAIRX_BULLET_REVIEW_V3.md` vs `V4` contradict each other.** V3 flags `$1.2M`, `42%` and
   `55%→80%` as invented, then resolves them two paragraphs later. V4 then bans deal-closure
   claims. Both files are live inputs. Reconcile them into one file with one verdict per figure,
   or the pool will keep emitting claims that another file says are retracted.
2. **`profile/handcrafted_resumes/Akshat_Pathak_McKinsey_FT_Associate.docx` is being used as a
   quality benchmark** (the Fluo pool scores against it) while containing `$110M`, which
   `freeform_master_v2.txt`'s attribution guard bans by name. Either clear those figures or stop
   benchmarking against that file.

---

## Part 4 — Selection quality, since you are not reviewing

**Multi-axis scorecard, reporting the minimum.** Replace the single holistic number. Score each
bullet across identity · JD language · scale legibility · opener form · architecture
distinctness · human presence · non-duplication, and **fail on the lowest axis, not the mean**.
Every failure this session was well-written-but-wrong-on-one-axis, which a mean hides.

**Best-of-N with a critic, on the top ten roles only.** Generate three candidate sets, a critic
argues against each given the JD and rubric, a judge picks and must state what it beat and why.
That forced comparison is where the quality actually came from in this session. It costs 3–4×
tokens on ten resumes, which is nothing against your time, and it is the closest available
substitute for you being in the loop.

**Seed the rejection ledger with this session's twenty** as negative few-shot examples. No
subordinate-conjunction openers. No fragment-list outcomes. No small dollar figures beside large
ones. No repeated outcome phrase inside a company block. These are specific, reusable, and they
are the only component that compounds across the 47 and everything after.

---

## Part 5 — Sequence

| | Work | Time | Effect |
|---|---|---|---|
| 1 | Section-integrity fix; render-and-assert-one-page; load story pools from disk | 2–3 h | Removes the observed catastrophic failure |
| 2 | `lint.py` — the seven gates in Part 2 | 1 day | Removes the rest of the catastrophic class |
| 3 | Facts ledger seeded from the verified Amazon resume; provenance gate reads it | 3–4 h | Makes fabrication structurally impossible |
| 4 | **Pool audit against the four variant gates** | 1 day | Raises the floor across all 47. Highest quality return. |
| 5 | Promote the Amazon ten into the pools | 2 h | Otherwise 47 resumes use older text |
| 6 | Three templates wired to a lane router | 1 day | Lane C stops getting a PM resume |
| 7 | Eligibility gate ahead of generation | 4 h | Stops wasted tailoring; catches sponsorship traps |
| 8 | Multi-axis scorecard, min-not-mean | 1–2 days | Raises the ceiling |
| 9 | Best-of-N + critic, top ten roles | 2–3 days | Approaches this session's quality unattended |
| 10 | Rejection ledger | ongoing | Compounds |

**Steps 1–5 are roughly three days and they are what makes an unattended run safe.** Do not start
the 47 before step 3 is done. Steps 8–9 are quality; steps 1–5 are the difference between
"unreviewed" and "unsafe."

---

## Part 6 — Two things that are still true

**Amazon has four reqs and one resume.** Check the queue for other multi-req employers before
generating; a per-req resume is wasted effort where the portal only accepts one.

**There is still no outcome data.** 179 applied rows, zero response/stage/rejection-type
recorded. Everything in this plan is judged by a model against a rubric. Add those columns before
the 47 go out and in three months you can tell which of these changes mattered. Skip it and the
next architecture review is another argument from first principles.
