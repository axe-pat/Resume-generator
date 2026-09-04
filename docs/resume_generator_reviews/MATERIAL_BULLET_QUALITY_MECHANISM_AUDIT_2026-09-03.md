# Material bullet-quality mechanism audit

**Scope:** reverse-engineer the content decisions that improved the Amazon shared resume
and the StudyFetch Product Intern resume. This is a review artifact only. It does not edit
or wire any live prompt, pool, profile, or variant.

## Bottom line

The winning mechanism was not “write more polished bullets.” It was:

> **Choose the one connected story path that best proves the page's highest-value hiring
> question; lead with the scarcest causal atom; name one decision or artifact; finish on
> that path's best attributable consequence; remove every fact that belongs to another
> path.**

The current playbook already describes most sentence-level quality gates. What it does not
yet operationalize is **how to choose the right claim before writing**, **how to preserve
causal edges when compressing a rich story**, and **how to compare a challenger against the
incumbent without letting style gains hide a material loss**.

That distinction explains the observed pattern:

- FlairX V4 could report 27/27 compliance across a large checklist while still losing to
  simpler final bullets. Its own audit emphasizes formal compliance and 203–256-character
  density (`FLAIRX_BULLET_REVIEW_V4.md:8-38`).
- The StudyFetch revisions improved most when a system inventory became an end-to-end user
  path and a prototype/booth description became an interview → behavioral data → diagnosis
  → next-test loop.
- The Amazon revisions improved when adjacent facts and weak currencies were removed, and
  when the decision or tradeoff became the subject of the sentence.

## What is already covered

Do not add duplicate rules for these. They already have a canonical owner.

| Existing mechanism | Where it already lives | Status |
|---|---|---|
| Opener + mechanism + outcome; opener archetypes | `docs/variants/VARIANT_FINALS_v4.md:24-68` | Keep |
| Why-now, causal connector, earned detail, removal test, Mom Test | `docs/variants/VARIANT_FINALS_v4.md:71-85` | Keep |
| One argument; mechanism fit; outcome closure | `docs/variants/VARIANT_FINALS_v4.md:86-93` | Keep; these are critical vetoes |
| Best attributable outcome over activity/build scale | `docs/variants/VARIANT_FINALS_v4.md:94-96` | Keep |
| Outsider legibility, closed discovery loop, low cognitive load | `docs/variants/VARIANT_FINALS_v4.md:97-106` | Keep |
| Stakes, difficulty, defensibility, distinctiveness, line cost | `shared/variant_admission.py:46-85` | Keep at one-time admission |
| Outcome-tier vocabulary | `shared/variant_admission.py:35-44` | Keep, but do not treat it as a score |
| JD routing, identity mix, marginal value, non-duplicate value signals | `docs/resume_generator_reviews/RULE_OWNERSHIP_MAP.md:8-16` | Keep per JD / assembly |

The live PM prompt already selects approved-looking variants verbatim rather than freely
rewriting them (`resume/freeform/prompts/freeform_master_v2.txt:119-126`). That is helpful,
but its embedded pool is stale and some variants still encode the losing mechanism. For
example, the older FlairX sourcing variant combines product construction, a corrected vendor
estimate, and distribution in one bullet (`freeform_master_v2.txt:255-274`).

## What the Amazon and StudyFetch work added

These are the genuinely new or still-non-operational mechanisms.

### 1. Select a claim spine before selecting wording

A story file is an evidence graph, not a bullet. Construct candidate paths of:

`trigger or observation → judgment → decision/artifact → attributable consequence`

One bullet may take **one connected path**. Shared topic is not sufficient. This turns the
existing “one argument” rule into a selection procedure rather than a post-hoc lint check.

Why it matters: the FlairX reviews moved from mechanism-only V2 to maximum-consequence V3.
V3 correctly diagnosed that mechanism-only bullets weakened the top role
(`FLAIRX_BULLET_REVIEW_V3.md:9-24`), but “every bullet lands on a consequence” plus distinct
outcome currencies (`FLAIRX_BULLET_REVIEW_V3.md:26-40`) encouraged strong adjacent facts to
be packed together. The final winners kept the consequence requirement but restored one
causal path.

### 2. Lead with the scarce causal atom

Do not mechanically prefer insight-first or action-first. Ask which atom in the chosen path
is hardest for another candidate to reproduce:

- non-obvious diagnosis → lead the diagnosis;
- consequential tradeoff → lead the trade;
- distinctive shipped artifact / ownership → lead the artifact;
- direct, self-explanatory result → impact-first is allowed.

The Fluo pool discovered the general principle by ranking stories on **stakes plus
non-replicability**, not merely “was this clever” (`FLUO_STORY_POOL_V1.md:40-58`). The
important extension is that the scarce atom can be the decision or shipped artifact, not
always the insight.

### 3. Optimize for criterion proof, not generic JD similarity

Before comparing variants, state the single hiring question the slot must answer. Examples:

- Amazon FlairX: “Can this person turn enterprise constraints into material product and
  business outcomes?”
- StudyFetch FlairX: “Has this person personally wireframed, built, and shipped?”
- StudyFetch Fluo: “Can this person combine interviews with usage behavior and design the
  next test?”

This is stricter than tags or keyword fit. A variant may be topically relevant but fail to
prove the criterion. The StudyFetch fixture makes independent building first-class proof in
the summary and Projects and deliberately replaces two corporate bullets
(`tests/fixtures/resume_gold/studyfetch_builder_discovery_2026-09-01.json:21-35,159-177`).

### 4. Prefer counterfactual ownership over impressive system description

Ask: **what decision, artifact, or changed outcome would probably not exist without the
candidate?** That is stronger than describing the size or sophistication of a system.

This is why “four repos,” module counts, and roles scored were weak Recruiting Engine leads.
The approved story instead says what the system decides and the operated path it created;
its source also separates the user's product/ship decisions from agent implementation
(`_GOLD_REFERENCE_recruiting_decision_engine.md:7-18,31-38`).

### 5. Use page-relative marginal value

A bullet does not earn space because it is good in isolation. It must add a value signal not
already better supplied elsewhere on the page. This is why StudyFetch could replace two
corporate bullets with three project bullets while retaining the five-company spine
(`studyfetch_builder_discovery_2026-09-01.json:58-130,159-177`). Amazon instead kept ten
corporate bullets and one compact Fluo proof because its shared product/leadership reader
needed a different portfolio (`amazon_product_operator_2026-08-27.json:58-118,143-160`).

### 6. Compress by information role, not word count

When a draft is dense, remove in this order:

1. adjacent-story facts and second outcomes;
2. architecture inventory and implementation nouns that do not prove ownership;
3. internal product names and unexplained local shorthand;
4. secondary currencies that make the result look smaller or split attention;
5. process steps already implied by the decision.

Protect: the scarce atom, one earned detail, one mechanism, and the best causally matched
outcome. This is how the final FlairX provider bullet beat V4 variants carrying more vendor,
timeline, fee, and procurement detail.

## Compact durable formula

Use this at variant creation and per-JD selection.

### A. Build candidate spines

For each story, enumerate no more than three connected spines:

`reader problem → candidate judgment/ownership → decision or artifact → consequence`

Record which tempting atoms were excluded because they belong to another spine.

### B. Apply critical admission vetoes

A spine cannot ship if any answer is no:

1. Is the work material enough to deserve page space?
2. Are all four causal edges supported by the same story?
3. Is candidate ownership legible?
4. Does the mechanism answer the opener?
5. Does the outcome close the opener's claim?
6. Can an outsider understand the object and consequence in one read?

These are vetoes, not dimensions to average.

### C. Require material Pareto non-regression, then rank

Compare these material dimensions in order, but do not average them:

1. **Criterion proof:** directly answers the slot's highest-value hiring question.
2. **Marginal page value:** adds a signal the page does not already prove better.
3. **Stakes × non-replicability:** consequence matters and evidence is hard to copy.
4. **Counterfactual ownership:** a decision/outcome exists because of the candidate.
5. **Outcome quality:** attributable user/business or observed behavior, then a real
   decision/organizational change, then quality/efficiency, then activity/build scale.
An automatic replacement requires at least one improvement across 1–5 and no regression
across any of them. If one rises while another falls, retain the incumbent as the shipping
default and request human review. **Line cost** may break an exact material tie only when the
two renderings carry the same claim. Rhythm, archetype, and keywords never independently
justify replacement.

This ordering prevents a highly polished, archetype-balancing bullet from beating a more
material proof. The incumbent wins an exact tie.

### D. Render the winner

`[scarce causal atom] + [one decision/artifact with one earned detail] + [best matched consequence]`

Read once and ask the reader to state: **what changed, what the candidate did, and why that
result follows.** If they cannot, the bullet is not done even if it passes every micro-rule.

## Pairwise incumbent-versus-challenger protocol

The critic should not assign a mean score. It should emit this decision card:

```yaml
slot_question: "the one hiring question this slot must prove"
incumbent_spine: "trigger -> judgment -> mechanism -> result"
challenger_spine: "trigger -> judgment -> mechanism -> result"
critical_vetoes:
  same_story_edge_integrity: pass|fail
  materiality: pass|fail
  criterion_proof: pass|fail
  ownership: pass|fail
  outcome_closure: pass|fail
  outsider_legibility: pass|fail
page_effect:
  new_signal: "what the challenger adds"
  displaced_signal: "what disappears"
  redundancy_or_line_cost: "net page effect"
  page_can_fund_both: true|false
material_win: "one concrete improvement, or none"
verdict: keep_incumbent|accept_challenger|keep_both|human_review
```

Rules:

1. Any challenger critical failure means `keep_incumbent`.
2. A challenger must create at least one material win, not just cleaner phrasing.
3. A critical or material loss cannot be offset by any number of stylistic wins. A material
   tradeoff routes to human review with the incumbent still the shipping default.
4. Compare page fit in assembly context, including the summary and neighboring bullets;
   page fit is not a variant-level critical veto.
5. If the challenger changes the story spine rather than the rendering, label it as a
   **selection change**, not a rewrite.
6. If evidence is ambiguous, retain the incumbent and request human review. Do not auto-merge.
7. `keep_both` requires available page budget and criterion sets with at least one unique,
   funded proof on each side; topical variety alone is insufficient.

## Representative test against known winners

The protocol was applied to eight real incumbent/challenger pairs. “Winner” means the version
that survived into the relevant final gold, or the explicitly preferred future sibling where
both artifacts are preserved.

| Company / slot | Incumbent | Challenger | Material decision | Expected | Formula |
|---|---|---|---|---|---|
| FlairX provider | Generator: vendor cap → diligence/pricing → multi-provider routing | Shared gold: vendor cap ended long rounds → swappable providers/usage pricing → 70% lower cost/minute | Challenger closes the same dependency claim with one outcome and drops secondary currencies | Challenger | **Challenger** |
| FlairX enterprise, StudyFetch | Generator: client-run suite → team shipped M365/scoring in 2 weeks | StudyFetch: same spine, but wireframed privacy-safe scheduling and scoring flows before leading delivery | Directly proves StudyFetch's prototype/design criterion without losing enterprise stakes | Challenger | **Challenger** |
| Gojek pricing, Amazon | Generator: “validated willingness-to-pay” → methods → launch | Amazon: separated price abandonment from latency abandonment → cost tier → 9% / $3.2M | The diagnostic insight becomes the scarce atom; methods support rather than lead | Challenger | **Challenger** |
| Gojek pricing, StudyFetch | Amazon diagnosis variant | StudyFetch WTP variant: interviews → A/B confirmation → launch | StudyFetch asks for interview/data/prototype loops; the experimental closure is higher marginal proof | Challenger | **Challenger** |
| Gojek latency, future general use | Amazon: “Traded ±4% fare-quote accuracy...” | StudyFetch: “Traded live fare recalculation...” and then bounds variance at 4% | Challenger preserves tradeoff but makes the sacrificed object legible to an outsider | Challenger | **Challenger** |
| Hevo monitoring, StudyFetch | Initial: internal “Job Monitoring” reframe → audit surface → failure-ID speed | Final: manual alert triage → GenAI taxonomy/incident cards → 45-to-under-5-minute triage at scale | Final answers the AI-build/data-curiosity criterion with one visible user problem and causal outcome | Challenger | **Challenger** |
| Intuit incident, Amazon | Generator: “Caught a billing failure...” → coordinated functions → faster resolution | Amazon: coordinated an 8-team response after lifecycle mismatch → parallel fix/validation → days to hours | Challenger makes leadership the subject and names the operating mechanism; no “caught a bug” identity | Challenger | **Challenger** |
| Recruiting Engine, StudyFetch | V2: roles/organizations + decision-ledger architecture | V3/V4: full role-to-application-to-person path → 190+ applications/1,100+ contacts → 300+ accepts/100+ replies | User job and external outcomes replace architecture/build scale; direct top-criterion proof | Challenger | **Challenger** |
| Fluo, StudyFetch | V2: 35-step prototype + live booth + downloads | V3/V4: 60 interviews → 3/20 usage corroboration → awareness/demand diagnosis → receipt retest | Closed discovery/data/next-test loop exactly matches the JD; no mixed prototype/event spine | Challenger | **Challenger** |

**Result: 9/9 expected choices.** More importantly, the protocol explains why the same Gojek
pricing story legitimately chooses different siblings for Amazon and StudyFetch. It does not
collapse “best variant” into one universal sentence.

Exact final shape authority:

- Amazon summary, allocation, and selected variant IDs:
  `tests/fixtures/resume_gold/amazon_product_operator_2026-08-27.json:32-35,58-118,143-160`.
- StudyFetch summary, 8 Experience + 3 Projects shape, and selected variant IDs:
  `tests/fixtures/resume_gold/studyfetch_builder_discovery_2026-09-01.json:32-35,58-130,159-177`.
- Exact approved final bullet text: `resume/variants/approved_gold_variants.jsonl`.
- Exact StudyFetch before states:
  `apps/Apply queues/current_apply_queue/jobs/29_08-26_CARRY_92_StudyFetch/Product_Intern/`
  (`Akshat_Pathak_StudyFetch_Resume.docx`, `..._2026-09-01.docx`, `..._v3.docx`, `..._v4.docx`).
- Exact Amazon generator incumbent and submitted gold:
  `apps/archive/applied/2026-08-28/Apply queues/current_apply_queue/jobs/06_08-24_CARRY_94_Amazon/Product_Manager_Technical_PMT_-_2027/`.

## Failure modes the durable layer must catch

1. **Checklist saturation:** every micro-rule passes, but the sentence has no dominant claim.
2. **Metric grafting:** a large result from an adjacent story is attached to a different
   opener or mechanism.
3. **Inventory masquerading as mechanism:** a list of features, tools, repos, or workflow
   stages replaces the one decision that matters.
4. **Internal-name tax:** the reader must know the company's product vocabulary before the
   opener makes sense.
5. **Proxy-outcome inflation:** activity count, system size, or build complexity displaces
   user/business behavior.
6. **Consequence maximalism:** forcing every bullet to end on the biggest number creates
   causal mismatch or weak attribution.
7. **Archetype Goodharting:** a lower-value story wins only to balance opener types.
8. **Local improvement, global regression:** a stronger isolated bullet duplicates a signal
   or removes a scarce identity proof elsewhere on the page.
9. **Drill-down optimization:** a technically rich bullet would survive an interview but is
   too dense or low-stakes to earn one.
10. **Universal-winner fallacy:** one sibling is promoted globally when different JDs ask
    different questions of the same story.

## Smallest persistent mechanism worth building

Do not add another long prose prompt. Add three compact artifacts around the existing
admission and fixture system:

1. **Claim-spine metadata on each admitted sibling**
   - `claim_id`: shared only by renderings of the same material claim;
   - `claim_spine`: four short connected atoms;
   - `scarce_atom`: insight | tradeoff | artifact | impact;
   - `criterion_tags`: hiring questions it directly proves;
   - `counterfactual_ownership`: one sentence;
   - `decision_rationale`: required when the judgment atom is intentionally implicit;
   - `excluded_adjacent_atoms`: facts intentionally not used in this sibling.

2. **Pairwise decision cards per run**
   - one card only when a challenger would replace an incumbent;
   - machine-readable critical vetoes and page effect;
   - retain both siblings when the winner is JD-conditional.

3. **Golden pair fixtures**
   - preserve the losing and winning exact text plus the target criterion and expected
     verdict;
   - run these before changing selection or rewrite behavior;
   - use Amazon and StudyFetch pairs above as the first nine cases.

This complements rather than replaces the existing registry. The current registry can tell
that a bullet is admissible; this layer explains **which admissible sibling should win here**
and prevents the generator from recombining their atoms.

## Recommended next review decision

Approve the formula and the nine pairwise expected outcomes before any live wiring. Then add
the five claim-spine fields and golden-pair fixtures as inert data first. Only after those
fixtures pass should the selector or voice-rewrite prompt consume them.

That sequence protects the current generator while making the material improvement testable.
