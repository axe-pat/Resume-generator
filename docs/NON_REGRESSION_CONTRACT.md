# Non-regression contract

Standing rule for the resume generator rebuild. Applies to every change already made,
in progress, or proposed.

---

## The rule

**No change ships that would have made the Amazon resume worse, or that cannot be
turned off in one line.**

Everything below is machinery for enforcing that honestly rather than by assertion.

---

## The problem: right now we cannot detect regression at all

Every rule built so far is calibrated against **one document**. That is not a test set,
it is an anecdote. A rule that is correct for a Lane B product resume can be wrong for a
Lane C campus resume or a Philips operations application, and nothing would tell us.

This is not hypothetical. It already happened once today: promoting
`FIGURE_REPEATED_ACROSS_COMPANIES` to a blocker would have **rejected the gold resume**,
because `70%` appears at both FlairX and Gojek. That was caught by manually checking the
fixture, not by any process. Next time it will not be caught.

**Nothing else should be built until there is a fixture set.**

### The fixture set — build this first, roughly 30 minutes

| Fixture | Source | Status |
|---|---|---|
| Amazon PMT | `Akshat_Pathak_Amazon_Resume.pdf` | Exists. Verified one page, submitted. ~9.0 |
| Amazon ALA, Aug 20 | `resume_2026-08-20_final.docx` | Exists. Known-good, one page. 8.5 |
| Lane C Viterbi | Aug-20 commit, **with the fabricated credential removed** | Exists |
| One NONPM | — | **Does not exist.** 12 of the 47 route here and nothing validates it |
| One Lane A internship | — | Does not exist |

**Every rule change re-runs against all fixtures. If a fixture newly fails, the rule is
wrong until proven otherwise.** The NONPM gap is the sharpest one: a quarter of the queue
routes through a template with zero validated output.

---

## The four-part test for any change

A change ships only if all four hold.

1. **No fixture newly fails.** Mechanical, non-negotiable.
2. **It would have caught a defect that actually occurred.** Not a defect we can imagine.
   Every blocker must name the real document it would have saved. This is the
   anti-speculation gate and it is the one most likely to be skipped.
3. **It is reversible in one line.** Feature flag or config constant. If turning it off
   requires unpicking a refactor, it is too entangled to ship unattended.
4. **It can be described in one sentence without reference to the implementation.** If it
   cannot, it will not be debuggable at resume 34 at 3am.

---

## Honest audit: where we have already drifted

Six things, listed because a contract that only points forward is worthless.

**1. The taxonomy grew after we agreed not to grow it.** We started at three templates and
an explicit warning against unnecessary taxonomy. We now have six identity headings and
seven nonpm routes. The pool-funding justification is real and I verified it. But it is
more routing surface than we agreed, on a queue where 12 resumes will hit routes that have
never produced a validated document.

**2. Nothing has been measured.** 61 focused tests and 254 repository tests all verify that
code does what the code says. **Zero evidence exists that output quality moved.** The only
real quality datapoint in this whole exercise remains 8.4 (old generator) versus ~9.0–9.2
(hand-built). The new architecture has produced no resumes.

**3. I proposed a rule that would have rejected the gold.** Exact-string provenance
matching. Caught because it was objected to, not because a fixture failed. That is a
process failure, and it is precisely what the fixture set exists to prevent.

**4. Scope has grown without a re-baseline.** The plan was three days, then compressed to
one or two hours, and is now two committed steps with more queued. That is fine, but it
should be acknowledged rather than drifted through — the original constraint was real.

**5. Warnings are accumulating with no consumer.** Twelve warning categories, no aggregator,
no threshold. Across 47 documents that is hundreds of signals nobody will read. Unread
warnings are worse than no warnings: they create the feeling of coverage without it.

**6. The largest one — we have been improving the gate, not the generator.** Steps 1 and 2
are both about *rejecting* bad output. Neither touches bullet quality, variant selection,
or the pool.

The 0.8-point gap between 8.4 and 9.2 came almost entirely from **content**: insight-first
openers instead of method-first, naming the before-state, the tradeoff framing, the Intuit
story swap, the summary rebuild. **None of that is in Step 1 or Step 2.**

Wire up everything committed so far and run 47 resumes, and the honest expected outcome is:
**the same 8.4-grade content, correctly assembled and reliably one page.** Safer, not
better. That is worth having — it removes the failure modes that lose an application
outright — but it is not the thing that was being aimed at, and it would be easy to finish
the rebuild believing the quality problem had been solved.

---

## Risk tiers for everything done and planned

**Safe — pure addition, no output change, trivially reversible**
Page-count assertion · section integrity · rendered-content verification · contact-block
integrity · dead-letter queue · warning digest · fixture set

**Low risk — deterministic, no legitimate false positive**
Duplicate bullet detection · same-company figure reuse · opener repetition ≥3 · date and
punctuation consistency

**Medium risk — changes output shape, thin validation**
Allocation contract (10/11/9) · six-heading taxonomy · Fluo placement policy · archetype
bounds per route
*Mitigation: these all need NONPM and Lane A fixtures before live wiring.*

**High risk — flagged**

- **Step 3's "automated repair" is the single most dangerous item on the roadmap.** An LLM
  rewriting bullets unattended to satisfy lint, across 47 documents, with no fixture set,
  is the textbook path to output that passes every rule and reads like nothing. Bullets
  were rewritten roughly fifteen times today and **you rejected or amended most of those
  rewrites** — including several of mine that were technically compliant and worse.
  Recommendation: repair proposes, it does not apply. Diffs go to a review file. If it must
  apply automatically, restrict it to a whitelist of mechanical fixes (punctuation, date
  format, an opener verb swap from a fixed list) and never to rewriting a bullet's content.

- **Goodhart risk on the gate itself.** Once lint exists, "passes lint" becomes the
  definition of done. Lint measures the *absence of defects*, not the *presence of quality*.
  A resume can clear every blocker and be a 7. Keep a quality score reported alongside the
  gate result and never let a green gate stand in for a score.

- **Complexity outrunning debuggability.** Profile registry, allocation contract, seven
  routes, six headings, twenty-odd blockers, twelve warnings, an admission gate. If this
  breaks at resume 30, the question is whether it can be reasoned about. A simpler system
  that is slightly weaker but fully understood is worth more than a stronger one that is
  opaque.

---

## Rollback

Before Step 3 wires anything into live generation: **tag the current working state**, and
keep the existing generator path runnable behind a flag. If the new pipeline produces worse
output on the fixtures, the old path must still be one command away. There is currently no
stated rollback and Step 3 is the step that changes live behaviour.

---

## What I will do with this

Applied to every subsequent proposal, mine or anyone's. Any change that fails the four-part
test gets flagged before it is built, not after. If I propose something that would reject a
fixture, that is a process failure on my side and worth saying so plainly.
