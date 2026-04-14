# Resume Layer

Generates tailored, paste-ready resume experience sections from a job description. Uses a freeform variant-selection system where the model picks the right story framing and ordering for each JD.

---

## Files

```
resume/
└── freeform/
    ├── freeform_runner.py      Main pipeline (Pass 0–4 + QC + optional docx)
    ├── jds/                    JD text files for batch runs
    ├── runs/                   Output files (one per company run)
    │   └── freeform/
    │       └── YYYY-MM-DD_<company>.txt
    └── prompts/
        ├── freeform_master_v2.txt      Pass 1: signal extraction + variant selection
        ├── freeform_voice_rewrite.txt  Pass 2: voice + style rewrite
        ├── freeform_scorer.txt         Pass 3: per-bullet scoring + holistic score
        └── freeform_targeted_swap.txt  Pass 4: targeted fix loop — takes scorer output
                                        (failure_mode + note per weak bullet) and rewrites
                                        only bullets scoring below 8.0; all others verbatim
```

---

## How the system works

Five API passes produce a polished 11-bullet experience section (3/3/3/2 across four companies). Here's what happens inside:

**Pass 0 — Signal extraction**
Reads the JD and identifies the 3 strongest hiring signals (e.g. "pricing strategy", "cross-functional execution", "AI/ML product thinking"). These drive all downstream decisions.

**Pass 1 — Variant + story selection**
For each of the 11 story slots the model picks one of 4–5 labeled variants (e.g. `[pricing-strategy]`, `[churn-renewal]`, `[AI-monitoring-product]`). Three story slots are flexible — H3 (Hevo: Regression / Query Engine / H-MONITORING-AI), I2 (Intuit: Prioritization Framework / Roadmap Ownership), and Optum ordering — and the model picks the story whose domain best matches the JD signals. Pass 1 also selects a **Professional Summary variant** (Section 0) from a pool of JD-tailored positioning statements; on the PM track, it may add one tightly controlled JD-aware qualifier to the opening identity frame (Zone 1) or, if needed, the closing USC Marshall transition line (Zone 3). Injection into the factual proof chain (Zone 2) is explicitly forbidden. Section 0 is now post-processed in code too, so forbidden em dashes are normalized before save/docx even if the model leaks one. On the non-PM track, Pass 1 can now also emit an optional **Projects & Consulting** section (Section 3B) when founder-advisory / L'Oréal / USC proof materially improves non-engineering identity.

**Pass 2 — Voice rewrite** (skippable with `--no-rewrite`)
Rewrites bullets for voice using a four-archetype framework: Diagnostic (insight-first), Action-first (execution-first), Context-first (scope/goal-first), or Impact-first (credentialing outcome leads). Each bullet gets one "earned detail" — a phrase only the person who did the work would write (hidden constraint, decision trade-off, process artifact, or corrected assumption). Contrast phrases ("not X but Y", "rather than") are capped at one across the entire 11-bullet section. Em dashes are forbidden in all output; they are **auto-stripped** in code after Pass 2 (replaced with `: `). A **regression guard** runs immediately after Pass 2: any bullet that contains 2+ colons (double-colon syntactic error), **crosses the 2-liner→3-liner boundary** (P1 ≤199 chars AND P2 ≥230 chars), or grows more than 80 chars vs Pass 1 (extreme bloat fallback) is automatically reverted to the Pass 1 version, with the reason logged. The old flat +60-char threshold was replaced 2026-03-26 with this semantic rule — it catches the common case where a 155-char P1 2-liner becomes a 215-char P2 3-liner, which the old threshold missed. If QC-03 fails (Intuit incident bullet dropped), Pass 2 is retried once with a hard constraint. A **trailing-reasoning truncation** step runs after extraction: the parser finds the last `•` bullet line and discards anything after it, preventing pre-submit reasoning the model appends from being captured as section content. (Prompt version: 2.1)

**Pass 3 — Self-scoring** (skippable with `--no-score`)
Scores each bullet on three dimensions: (1) archetype correctness (was the right opener type chosen?), (2) craft execution (earned detail passing detection + removal tests, mechanism visibility, metric placement, register), (3) readability (no "and...and" chains, parallel clauses, late-arriving subjects). Holistic score also evaluates JD fit — whether the section foregrounds the role's top signals from the Pass 0 strategy. Per-bullet output includes archetype_used and failure_mode fields. Pass 3 now uses a tighter `max_tokens=4096` budget to reduce pathological slow scorer calls without changing the rubric. (Prompt version: 2.0)

**Pass 4 — Targeted fix loop** (skippable with `--no-fix`)
After Pass 3, any bullet scoring below 8.0 is sent to `freeform_targeted_swap.txt` for surgical repair, unless the holistic resume score is already `>= 8.0` — in that case Pass 4 is skipped entirely because historical runs showed high-score passes rarely improve and often regress. When Pass 4 does run, the prompt receives: (1) the full experience section, (2) the weak bullets with their `failure_mode` and `note` from the scorer, (3) the strategy block, (4) the JD. The model fixes only the flagged bullets — all others are reproduced verbatim. After Pass 4, em dashes are stripped again and the section is **re-scored** so the final file reflects post-fix accuracy. The fix log (ORIGINAL / FIXED / FAILURE / FIX per bullet) is saved to the output `.txt` file. `MAX_FIX_ATTEMPTS = 1` — a second attempt almost never helps for `WEAK_MECHANISM`/`VAGUE_OUTCOME` failures caused by missing source metrics, and halves the cost of this pass. Two regression guards run after re-score: (1) **Holistic guard** — if the re-scored holistic drops below pre-fix holistic, revert the entire section (existing); (2) **Per-bullet guard** — even when the holistic holds, individual bullets can regress; any bullet whose post-fix score is lower than its pre-fix score is reverted to the pre-Pass-4 text, with the regression logged. Per-bullet guard fires only when the holistic guard did not revert.

**Runtime logging**
Each AI call now prints an elapsed time line in the terminal/log (for example `Pass 3: Score complete (84.2s)`), making it easier to diagnose unusually slow runs without inferring timing from file timestamps alone.

**Validation — action-first constraints (run_app.py)**
After the resume is generated, a post-hoc validator runs on the final bullet list and checks three hard rules:
- **Min 4 action/impact-first bullets** across all 11 (baseline; may adjust ±1 by JD type)
- **No ≥3 consecutive diagnostic openers** per company section (prevents template monotony like "Identified → Surfaced → Identified")
- **At least one strong ownership verb** present somewhere (Led, Owned, Built, Established, Unblocked, Shipped, Drove)

Output includes per-company categorization of bullet openers and flags any violations in the terminal. All 11 bullets are categorized as diagnostic (insight-first), action (execution-first), or impact-first (metrics-lead). Diagnostic streak per company shows the longest run of consecutive insight openers.

**QC — 13 automated checks**
- QC-01: All 4 company headers present verbatim
- QC-02: Bullet counts exactly 3/3/3/2 = 11
- QC-03: Intuit incident story (1,500+ businesses) present — protected, never dropped; auto-retries Pass 2 with a hard constraint if missing
- QC-04: No forbidden words — checks full list: leveraged, utilized, spearheaded, synergies, actionable, successfully, effectively, streamlined, holistic, various, multiple
- QC-05: No opening verb repeated 3+ times
- QC-06: Section 3 successfully extracted
- QC-07: Skills section present and contains required rows — **track-dependent**: PM track checks `Product Focus:`, `Tools:`, `Interests:`, `Community:`; NonPM track checks `Interests:` + one of `Domain Expertise:`, `Operating Focus:`, `Commercial Focus:`, `Research Focus:`, `Workflow & AI Systems:`, `Implementation Focus:`, or `Core Competencies:`; also errors if `Product Focus:` appears in a nonpm run
- QC-08: No bullets over 300 chars (3+ wrapped lines)
- QC-09: No orphan last lines — uses actual word-wrap simulation (Times New Roman 10pt, 7.0" continuation width ≈ 100 chars/line); flags any bullet whose final wrapped line is ≤ 3 words, showing the exact stranded text
- QC-10: No forbidden opener patterns — checks full Pass 2 list including "Led the", "Managed", "Supported", "Drove X by aligning stakeholders"
- QC-11: No em dashes (—) anywhere in output (note: these are now also auto-stripped in code after Pass 2)
- QC-12: Contrast phrase cap — "not X but Y" used at most once across all 11 bullets; FAIL if > 1 detected
- QC-13: Long-bullet check — two thresholds:
  - `_THREE_LINE_CHARS = 200` (detection): bullets ≥200 chars flagged as likely 3-liners. **Informational only** for bullets in the 200–259 char range — warns but does not auto-trim.
  - `_AUTO_TRIM_CHARS = 260` (auto-trim): fires only when >2 bullets exceed 260 chars (4-liner territory). Calls `run_length_trim()` and re-scores. Regular 3-liners (200–259 chars) are never auto-trimmed.

---

## Usage

```bash
# Standard run — PM track (default)
python resume/freeform/freeform_runner.py Stripe

# Non-PM track (Strategy / Consulting / S&O / PgM / RevOps / Ops)
python resume/freeform/freeform_runner.py McKinsey --track nonpm

# Also generate a formatted .docx
python resume/freeform/freeform_runner.py Stripe --docx

# Batch — all JDs in resume/freeform/jds/
python resume/freeform/freeform_runner.py --batch

# Override model (default: claude-sonnet-4-6)
python resume/freeform/freeform_runner.py Rubrik --model claude-sonnet-4-6

# Skip rewrite (faster, ~$0.04 cheaper/job)
python resume/freeform/freeform_runner.py Stripe --no-rewrite

# Skip scoring
python resume/freeform/freeform_runner.py Stripe --no-score

# Skip Pass 4 targeted fix (faster, ~$0.04 cheaper/job)
python resume/freeform/freeform_runner.py Stripe --no-fix
```

**Important:** the `.txt` output file is a cumulative ledger — it appends each run's full output. The docx generator reads `sections` from the in-memory Claude response during a run, not from the `.txt` file, so re-runs always produce a clean single-version docx.

In practice, `freeform_runner.py` is usually called through `run_app.py`, not directly:

```bash
python run_app.py Stripe                        # full pipeline (strategy + resume + CL)
python run_app.py Stripe --resume-only          # resume only
python run_app.py McKinsey --track nonpm        # non-PM resume track
python run_app.py Stripe --no-rewrite           # skip Pass 2
python run_app.py Stripe --docx                 # also produce formatted .docx
```

The `.docx` is written to `apps/<Company>/resume_YYYY-MM-DD_r<score>.docx` (same dir as the `.txt`), where `<score>` is the final holistic resume score (e.g. `r8.3`). If scoring is skipped (`--no-score`), the score tag is omitted.

Output is saved to: `resume/freeform/runs/freeform/YYYY-MM-DD_<company>.txt`
Each file contains: JD signals → variant selection notes → paste-ready bullets → QC log

---

## Page fitting (docx)

The docx generator uses a 4-tier layout system (T0–T3) to fit 11 bullets onto one page. Before generating, it estimates total DXA height of all content and picks the tightest tier that still fits:

| Tier | Line spacing | Section gap | Result |
|------|-------------|-------------|--------|
| T0   | 220         | 120/80      | Comfortable, most runs land here |
| T1   | 215         | 100/70      | Slightly tighter |
| T2   | 210         | 80/60       | Tight |
| T3   | 200         | 60/40       | Tightest — very long bullets or skills |

If T3 still overflows, the docx is still generated at T3 (the content will run slightly onto a second page). A warning is printed with the fill percentage so you can spot this and trim bullets manually.

The node package (`resume/node_modules/docx`) is installed locally and works across all Cowork sessions — no reinstall needed.

**Node PATH note:** When running from inside a Python venv on macOS, `node` may not be on PATH. The pipeline now uses `shutil.which("node")` and falls back to `/opt/homebrew/bin/node` (Apple Silicon) and `/usr/local/bin/node` (Intel) automatically. If docx generation still fails with `node not found`, verify with `which node` and ensure it's in one of those locations.

## Prompt update log

**2026-04-10 (nonPM route evidence-mix enforcement)** — non-PM route behavior now explicitly controls which stories are allowed to dominate the resume, not just the diction used to describe them.
- **Route evidence-mix policy** (`freeform_master_nonpm.txt`): added route-specific anchor-family checks so Strategy/Consulting, BizOps, Commercial/GTM, Research/Intelligence, AI-Automation, Client-Implementation, and Ops/PgM each have a clearer expected story mix. The prompt now distinguishes anchor slots from concise supporting slots and defines an `engineering-surface anchor` guard for routes that should not read SWE-first.
- **Selection-log enforcement** (`freeform_master_nonpm.txt`): Section 2 now requires explicit logging of selected anchor slots, supporting slots intentionally kept concise, engineering-surface anchor count, and a final route evidence-mix check. This forces the route choice to show up in story selection, not just in summary/voice.
- **Scorer + rewrite route preservation** (`freeform_runner.py`): the non-PM scorer preamble now checks whether the strongest bullets match the route's expected anchor family, and the non-PM rewrite preamble now preserves Pass 1 anchor hierarchy instead of flattening every bullet into generic strategy wording.
- **Anchor-variant rewrite pass** (`freeform_master_nonpm.txt`): tightened the main non-PM anchor stories (`G2`, `G3`, `H1`, `H2`, `H3`, `I1`, `I2`, `O1`, `O2`) so commercial, strategy, governance, and workflow routes now lead with business diagnosis, operating decisions, or workflow logic instead of engineering-first phrasing.
- **Upstream proof recommendation** (`step0_strategy.txt`, `shared/strategy.py`): Step 0 can now explicitly recommend whether non-engineering proof should be omitted or surfaced via founder / L'Oréal / Grab in Section 3B, and that recommendation is exposed in the formatted strategy block that Pass 1 reads.

**2026-04-09 (nonPM route expansion + first-class proof scaffolding)** — non-PM identity work moved upstream from rewrite-only behavior into Step 0, Pass 1 structure, parser, and docx rendering.
- **Step 0 candidate framing made track-neutral** (`shared/prompts/step0_strategy.txt`): candidate context no longer frames Akshat only as a PM candidate. It now explicitly covers product, strategy, bizops, ops, and AI-automation targets, plus founder-advisory context.
- **Richer non-PM subtype taxonomy** (`shared/prompts/step0_strategy.txt`, `freeform_runner.py`): `nonpm_subtype` expanded to `strategy-consulting`, `bizops-sando`, `commercial-gtm`, `research-intelligence`, `ai-automation`, `client-implementation`, and `ops-pgm` (with legacy aliases still accepted in the non-PM master). Non-PM scorer/rewrite preambles were updated to understand the new route families.
- **Optional Section 3B — Projects & Consulting** (`freeform_master_nonpm.txt`, `freeform_runner.py`, `resume_docx.js`, `run_app.py`): non-PM resumes can now carry first-class founder-advisory / L'Oréal / USC proof in an additive section between Experience and Skills. Parser extraction, save-output, docx payload, local docx regeneration, and page-fit estimation all now preserve this section.
- **Non-PM skills labels widened** (`freeform_master_nonpm.txt`, `freeform_runner.py`): Route labels now support `Operating Focus:`, `Commercial Focus:`, and `Workflow & AI Systems:` in addition to the prior non-PM labels, and QC-07 recognizes them.
- **Non-PM master prompt upgraded** (`freeform_master_nonpm.txt`): route system expanded from 4 broad buckets to 7 calibrated families: Strategy/Consulting, BizOps/S&O, Commercial/GTM, Research/Intelligence, AI-Automation, Client-Implementation, and Ops/PgM. The prompt now also defines when to use first-class non-engineering proof versus a compact Strategy Project row.

**2026-04-09 (NonPM pass hardening — archetype ceilings, H-SUPPORT-OPS guard, scorer preamble)** — Three fixes from analysis of April 9 NonPM batch (5/12 failing, 8/12 MONOTONY flags, D=7 in most failures).
- **freeform_master_nonpm.txt HARD RULES**: Added HARD CEILINGS block after the distribution table — D must stay within route ceiling (max 5 Strategy, max 4 BizOps/Commercial/AI-Auto/Client/Ops, max 6 Research); C=0 is a structural error; I=0 is a structural error. Exceeding the upper bound is now explicitly penalized equally to falling below the lower bound. Added D_EXCESS, C_MISSING, I_MISSING penalty definitions (-0.3 each).
- **freeform_master_nonpm.txt ARCHETYPE TALLY**: Updated output format to require explicit D_EXCESS check and C/I floor check per run, surfacing ceiling violations at generation time.
- **freeform_master_nonpm.txt H-SUPPORT-OPS cluster-a variant**: Added REWRITE GUARD — the operating-model-reframe variant has no metric; Pass 2 must not introduce "cut", "reduced by", or percentage claims. If a numbered metric is needed, select a cluster-b variant instead.
- **freeform_runner.py NONPM_SCORER_PREAMBLE**: Added D_EXCESS, C_MISSING, I_MISSING as explicit penalties to apply at the section level during Pass 3 scoring, mirroring the generation-level constraints.
- **Note**: NONPM_REWRITE_PREAMBLE (contrast phrase cap + H-BATCHSHIFT guard) was added in a prior session and was live before this batch. April 9 runs were generated before the preamble was updated — future runs should see contrast phrase violations resolved.

**2026-04-01 (pipeline fix — 3 prompt-level issues exposed by test runs)** — Three fixes to Pass 1 / Pass 2 / Pass 3 prompts after reviewing 2026-04-01 test runs (DwyerOmega, Equip, Gartner, Aeolus).
- **Voice rewrite `"Conducted behavioral analysis"` leak** (`freeform_voice_rewrite.txt`): Pass 2 was generating a non-approved generic mechanism-first opener when Diagnostic Saturation Rule fired (≥3 diagnostic). Root cause: the existing guard ("do not use generic mechanism") wasn't specific enough. Fix: (1) added `"Conducted behavioral analysis..."`, `"Performed behavioral analysis..."`, and `"Conducted [X] analysis to..."` to FORBIDDEN OPENER PATTERNS with explicit GENERIC_MECHANISM label; (2) strengthened Diagnostic Saturation Rule to say: only use mechanism-first if the Pass 1 input already names a specific credentialing method — otherwise prefer action-first rather than inventing a mechanism.
- **PRE-GENERATION CHECKLIST not enforced** (`freeform_master_v2.txt`): action-first count step in checklist wasn't being followed reliably (DwyerOmega 2/11, Equip 3/11 action/impact-first). Fix: SECTION 2 output format now requires the model to log opener type (ACTION / DIAGNOSTIC / IMPACT-FIRST) for every slot, compute the action/impact-first tally explicitly, and show the count with a ✓ or a named swap plan before generating Section 3. This forces the count to be visible in the reasoning, not silently skipped.
- **Scorer MONOTONY blind spot** (`freeform_scorer.txt`): DwyerOmega scored 8.2 with a DDDDDADDDDI pattern (9 consecutive diagnostic across Gojek+Hevo — 5 in Gojek alone). Scorer had no per-company-block penalty. Fix: (1) added MONOTONY to failure mode taxonomy (≥3 consecutive diagnostic openers in one company block); (2) added MONOTONY section-level penalty = -0.5; (3) added ACTION_COUNT_LOW section-level penalty = -0.3 if total action+impact-first < 4 across all 11 bullets.

**2026-04-01 (full variant audit — 22 fixes across 10 story groups)** — Systematic audit of all PM track variants against VARIANT_FINALS_v4.md rulebook. Fixed construction violations, missing outcomes, em dashes, and archetype labeling errors.
- **Weak construction fixes** (6 variants): eliminated "Improved/Restored/Accelerated X by doing Y" pattern in H-BATCHSHIFT [reliability-outcome], H-MONITORING [reliability-product], I-BILLING [exec-presentation], I-PRIORITIZATION [cross-functional-align], I-STRATEGIC-NO [capacity-decision], G-LATENCY [throughput-engineering] — all flipped to lead with the action or result directly.
- **Results-first conversion** (1 variant): I-BILLING [trust-reliability] → "Restored accurate billing for 80K+ Intuit businesses; diagnosed silent SMB cancellations as a billing accuracy failure…" — clean results-first structure (metric stands alone as credential).
- **New G-PRICING [revenue-lift] variant**: replaces [throughput-systems]; clean results-first ("Generated $3.2M in incremental revenue and a 9% conversion lift…") for monetization/growth PM roles. Carries ⚠ scorer caveat.
- **Missing outcome fix** (1 variant): H-BATCHSHIFT [strategic-bet] now includes "improved platform stability 45% and enabled onboarding of 8 enterprise customers within 90 days."
- **Generic mechanism fixes** (2 variants): H-MONITORING [feature-ownership] ("drove X as Y" → "shaped X into Y"), H-MONITORING [reliability-product] ("driving observability features" → specific outcome chain).
- **Vague outcome fixes** (3 variants): H-MONITORING [customer-trust], I-INCIDENT [churn-defense], I-INCIDENT [stakeholder-coord] — all now end with concrete containment language instead of "limiting damage."
- **Em dash fixes** (5 variants): H-QUERY [analytics-tools], I-INCIDENT [crisis-management], I-RECONCILIATION [hidden-aggregate], I-ROADMAP [roadmap-ownership], O-AFFORDABILITY [ML-product-design] — replaced with semicolons or restructured.
- **Archetype label fix** (1 variant): G-LATENCY [revenue-case] was mislabeled IMPACT-FIRST; opener is "Diagnosed" (DIAGNOSTIC) — label corrected to prevent action-first miscounting.
- **Attribution fixes** (2 variants): G-SUPPLY [supply-diagnosis] and [platform-led] — "increased/growing active supply 18%" → "enabling 18% supply growth" per attribution rules.
- **Pre-generation checklist** (`freeform_master_v2.txt`): added explicit action-first count verification step — model must tally action/impact openers and confirm ≥4 before generating; swap rule added for below-threshold cases.

**2026-04-03 (four-archetype system — scorer, master, voice rewrite, variants)** — Major architectural update formalizing Context-first as the fourth distinct opener archetype and introducing archetype-specific scoring criteria. No archetype has an imposed ceiling; ceiling depends on the story's earned-detail potential, not the archetype type.
- **VARIANT_FINALS_v4.md (Section 11)**: Added FOUR-ARCHETYPE PHILOSOPHY section with full archetype definitions, target distribution table (Diagnostic 4–5 / Action-first 2–3 / Context-first 1–2 / Impact-first 2 at baseline), archetype-specific 10/9/8 criteria, and rationale for why Diagnostic is the plurality archetype for PM roles.
- **freeform_scorer.txt**: Replaced shared rubric header with archetype-specific 10/9/8 criteria for all four archetypes. Added ARCHETYPE CORRECTNESS CHECKS clarifying Context-first is not wrong just because it lacks a corrected assumption — WRONG_ARCHETYPE must not fire on valid Context-first bullets.
- **freeform_master_v2.txt HARD RULES**: Replaced ACTION/IMPACT-FIRST COUNT block with full FOUR-ARCHETYPE SYSTEM table including verb lists, distribution table, and PENALTIES block (ACTION_COUNT_LOW and MONOTONY definitions). Added "Caught = DIAGNOSTIC" note to verb list.
- **freeform_voice_rewrite.txt Section 1**: Restructured from three archetypes to four. Split old ARCHETYPE 2 (CONTEXT/MECHANISM-FIRST) into separate ARCHETYPE 2: ACTION-FIRST and ARCHETYPE 3: CONTEXT-FIRST. Updated DECISION CHAIN to 4 steps. Updated Example 2 (G-LATENCY) from "Mechanism-first" to "Action-first" — the AFTER was using "Conducted behavioral analysis..." which is a FORBIDDEN OPENER; corrected to lead with quantification action instead.
- **G-SUPPLY [API-launch] + [platform-led]**: Upgraded mechanism clause from "defined integration specs" / "defined partner integration requirements and onboarding workflows" → "designed a standardized API contract and partner validation workflow" (concrete deliverable pair). Openers preserved — both correctly remain Context-first.
- **I-BILLING [exec-presentation]**: Flipped from action-first ("Designed a scalable reconciliation framework...") to diagnostic-first ("Diagnosed that SMB cancellations traced to billing accuracy failures, not product gaps...") — corrected assumption is the real value in this story.

**2026-03-31 (Pass 4 skip threshold)** — conservative runtime/cost optimization based on historical run review.
- **High-score skip rule** (`freeform_runner.py`): Pass 4 is now skipped when the initial holistic resume score is already `>= 8.0`, even if a few individual bullets remain below the per-bullet threshold.
- **Rationale**: historical logs showed Pass 4 helped sub-8.0 runs often enough to keep, but in reviewed `>= 8.0` runs it produced 0 observed improvements and frequent regressions while still paying the full Pass 4 + re-score cost.
- **Terminal visibility** (`freeform_runner.py`): the runner now prints `Pass 4 skipped — holistic score already ...` so the reason is explicit in the log.

**2026-03-31 (PM title guard + scorer budget)** — two fixes after AXS review.
- **PM title override for auto-switch** (`freeform_runner.py`): roles whose title explicitly contains `Product Manager`, `Product Management`, `Product Intern`, `Product Management Intern`, `APM`, or `PM Intern` no longer auto-switch to the non-PM track just because Step 0 emitted `ops-execution` or another non-PM role family.
- **PM-adjacent Product Development guard** (`freeform_runner.py`, `step0_strategy.txt`): `Product Development` titles now stay on the PM track when the JD clearly centers roadmap input, launches, consumer research, competitive analysis, SKU ownership, or product-definition work. This catches SharkNinja-style product-development roles that were previously over-routed into the ops track.
- **Strategy prompt title rule** (`step0_strategy.txt`): Step 0 now explicitly prefers `role_family = "pm"` for coordination-heavy Product team intern roles whose title is clearly PM or clearly PM-adjacent product development, reducing future AXS/SharkNinja-style misclassification at the source.
- **Scorer token cap** (`freeform_runner.py`): Pass 3 now uses `max_tokens=4096` instead of the generic 8192 default to reduce pathological long-latency scorer calls.

**2026-03-31 (Section 0 sanitization + recovery-path summary preservation)** — summary handling hardened.
- **Professional summary sanitization** (`freeform_runner.py`): Section 0 now runs through a dedicated sanitizer that strips forbidden em dashes and normalizes punctuation before the final text and docx are written.
- **Recovery paths keep Section 0** (`run_app.py`): `--score-only` and `--docx-only` now both re-extract and preserve the saved summary section instead of treating Section 0 as optional during docx regeneration.

**2026-03-31 (runtime timing instrumentation)** — Added per-call elapsed timing to slow-run diagnostics.
- **Resume API timing** (`freeform_runner.py`): every Pass 1/2/3/4 and QC-triggered API call now logs a completion line with elapsed seconds, e.g. `Pass 4: Fix complete (71.3s)`.
- **Shared strategy timing** (`shared/strategy.py`): Step 0 now prints `Strategy API complete (...)` so strategy latency is visible in `run_app.py`, `freeform_runner.py`, and `cl_pipeline.py` logs.

**2026-03-31 (PM summary injection guardrails)** — PM Section 0 now supports minimal JD-aware tailoring without opening up full summary rewrites.
- **Controlled qualifier injection** (`freeform_master_v2.txt`): PM summary generation still starts from one of the 5 base variants, but may now add at most one short qualifier derived from `top_signals` / positioning strategy.
- **Zone priority defined** (`freeform_master_v2.txt`): Zone 1 (opening identity frame) is the default insertion point; Zone 3 (USC Marshall transition line) is fallback-only when Zone 1 becomes awkward or too long.
- **Zone 2 banned** (`freeform_master_v2.txt`): the factual proof chain containing company evidence, metrics, and phrases like `customer discovery` / `product roadmap` cannot be edited for keyword injection.
- **Compression rule added** (`freeform_master_v2.txt`): JD language must be compressed into summary-safe phrases such as `analytics-led enterprise workflows` rather than copied as raw JD jargon or stuffed keyword lists.

**2026-03-31 (action-first audit + verb optimization + per-section monotony rules)** — Major action-first variant audit and optimization pass; introduced per-section monotony constraint to eliminate template feeling; added 1 new "Led" ownership variant and 6 verb upgrades.
- **Verb optimization** (7 edits): `[execution-velocity]` "Reduced" → "Cut" (match [platform-quality] energy); `[analytics-tools]` "Designed" → "Shipped" (PM-native production-delivery signal); `[influence-without-authority]` "Influenced" → "Unified" (action + result clarity); `[trial-conversion]` "Improved… by shaping" → "Reshaped" (weak passive opener replaced with transformation narrative); `[innovation-to-pilot]` "Designed ML-based" → "Converted hackathon win to pilot" (journey framing over mechanism); `[responsible-AI]` "Designed and prototyped" → "Prototyped" (reduced repetition in O-AFFORDABILITY variant set).
- **New `[platform-led]` variant** (G-SUPPLY): "Led Gojek's fleet integration platform from product definition to launch; defined partner integration requirements and onboarding workflows for commercial fleet operators…" — ownership-focused action opener for product ownership or platform PM roles. Fills gap for pure "Led" bullet (previously none existed).
- **Per-section monotony constraint** (new rules added to file header): no company block may have ≥3 consecutive diagnostic openers. If a section has 2 diagnostic bullets, the 3rd must use action or impact-first opener. Prevents "Identified → Surfaced → Identified" monotony at Gojek and forces variety within company blocks.
- **Action-first count baseline** (new rule): minimum 4 action/impact-first bullets across all 11 (previously untracked). Baseline 4; adjusts ±1 by JD type (Technical PM: +1 toward execution; Strategy PM: +1 toward insight).
- **Ownership language rule** (new rule): at least one strong ownership verb ("Led", "Owned", "Built", "Established", "Unblocked", "Shipped", "Drove") must appear across all 11 bullets. Ensures leadership signal is visible.

**2026-03-31 (story bank quality pass — 6 variant areas upgraded)** — Major variant rewrite across G-LATENCY, H-MONITORING-AI, G-SUPPLY, I-BILLING, O-PROVIDER, O-AFFORDABILITY. Rulebook codified in `VARIANT_FINALS_v4.md`.
- **G-LATENCY** (all 5 replaced): added orientation anchor ("bottleneck" up front before p95 numbers); [strategic-exec] now uses competitive app-switching + 2-3x abandonment data; [revenue-case] and [profiling-analysis] use "where X hid behind Y" construction; [throughput-engineering] changed "accepting" → "trading" ±4% fare variance; [cross-functional-drive] marked as ★ DEFAULT for general PM roles.
- **H-MONITORING-AI** (both replaced): replaced generic "anomaly detection / GenAI-based summarization" with "GenAI synthesizer + 20+ failure taxonomy → single incident cards"; [AI-monitoring-product] uses triage time 45→5 min (more visceral than MTTR 40%); [AI-reliability-product] keeps MTTR 40% as observability-layer framing.
- **G-SUPPLY** ([ecosystem-GTM] + [API-launch] replaced): added gap-first opener; [ecosystem-GTM] uses "built X by defining Y" construction; [API-launch] uses action opener without forced diagnosis; $110M and multi-partner language preserved.
- **I-BILLING** ([roadmap-pivot] + [financial-case] replaced): [roadmap-pivot] now names cross-org data join as specific mechanism + "refocusing engineering toward accuracy over feature delivery"; [financial-case] now names reconciliation framework artifact + "securing a roadmap pivot" as org outcome.
- **O-PROVIDER** ([GTM-execution] + [platform-scale] replaced): real story is provisioning Kafka event pipelines, consumers, and microservices — not schema mismatch. Both variants updated with Kafka architecture detail.
- **O-AFFORDABILITY** ([business-case-AI] replaced + [tiered-intervention] added): [business-case-AI] now uses predictive reframe (post-claim outreach missed intervention window) + tiered playbook from in-app prompts to social worker referrals; [tiered-intervention] is a new 6th variant for ML-heavy roles using named risk indicators.

**2026-03-26 (regression guard + partner taxonomy pass)** — Regression guard tightened; new G-SUPPLY variant added:
- **Regression guard** (`freeform_runner.py`): replaced flat "+60 chars" bloat rule with semantic 2-liner→3-liner detection. New rule: revert if (P1 ≤199 AND P2 ≥230) — catches bullets crossing the 2-liner boundary — OR if growth >80 chars (extreme bloat on any bullet). Old rule missed the common case P1=155→P2=215 (+60 chars exactly, 2-liner→3-liner). New rule catches it.
- **G-SUPPLY `[partner-taxonomy]` variant** (`freeform_master_v2.txt`): fifth variant added using Bullet Bank earned detail ("metro, bus, and private fleet partners" + "standardized API specs and onboarding workflows"). Use when cross-partner coordination or supply ecosystem specificity is valued. ~192 chars (clean 2-liner).

**2026-03-26 (story bank metrics pass)** — Real metrics added to variants; attribution guard language clarified:
- **G-SUPPLY `[ecosystem-GTM]`**: updated to include "$110M+" as scale context ("Gojek's $110M+ ride marketplace"). $110M is real platform revenue; guard still blocks Pass 2 from hallucinating it — it only flows through when `[ecosystem-GTM]` is selected by Pass 1.
- **O-PROVIDER `[platform-scale]`**: updated to include "$20M+ in incremental annual revenue" alongside existing "50M-member" context. This variant is now the go-to when scale/revenue context strengthens the story.
- **Attribution guard (Pass 1 + Pass 2)**: removed the confusing "org-level outcomes Akshat did not produce" sentence (which contradicted having these numbers in variants). Guard now reads: "NEVER add unless present verbatim in the specific variant you selected / the Pass 1 input." Behavior is unchanged — hallucination from strategy context is still blocked.

**2026-03-26 (quality pass)** — Attribution guard, Diagnostic saturation rule, story priority routing, expansion threshold:
- **Attribution guard (Pass 1 + Pass 2)**: added hard constraint to `freeform_master_v2.txt` and `freeform_voice_rewrite.txt` blocking `$110M`, `$20M`, `50M members` from being added to bullets unless verbatim in the source variant. These figures caused ATTRIBUTION_MISMATCH (7.0 bullets) on G-SUPPLY and O-PROVIDER in ~50% of runs.
- **Diagnostic saturation rule (Pass 2)**: added rule to `freeform_voice_rewrite.txt` — when ≥3 bullets already use a Diagnostic opener, switch to Mechanism-first unless the insight is genuinely non-obvious. Prevents REPETITIVE_FRAMING section-level penalty (-0.2 holistic).
- **Story priority routing (strategy.py)**: `_format_strategy_block()` now includes `story_recommendations` (mapped to story pool IDs) and `story_reasoning` from the strategy JSON. Pass 1 receives explicit story prioritization instead of inferring from framing axis alone.
- **Expansion pass threshold**: lowered from 85% → 80% fill, and minimum spare_lines raised from 0 → 2. Eliminates spurious expansion API calls (~$0.04/run) when fill is marginally below 85%.

**2026-03-26 (maintenance pass)** — Parse robustness + runtime fixes across `freeform_runner.py`, `freeform_master_v2.txt`, `freeform_voice_rewrite.txt`:
- **Trailing-reasoning truncation**: all 4 parse sites (Pass 2, run_length_trim, run_targeted_fixes, run_expansion_pass) now find the last `•` bullet line and truncate there, preventing model pre-submit reasoning from being captured as section content.
- **Three-pattern cascade**: all parse sites use P1 (specific separator chars `[─═\-=]{3,}`), P2 (any single non-newline line), P3 (no separator) with `≥5 bullet` validation, plus a company-header fallback.
- **`BULLET LENGTH RULE` rewritten** in both Pass 1 and Pass 2 prompts: removed the mandatory "count characters / trim inline" instruction (was causing ~260-line reasoning blobs and 872s runs). Now a calibration guide only — pipeline QC enforces limits automatically.
- **Pass 2 pre-submit checklist** reformatted from 30+ `[ ]` checkbox items to compact imperative constraints to prevent inline checklist-reporting in model output.
- **`MAX_FIX_ATTEMPTS = 1`** (reduced from 2) — second attempt never helps for metric-free stories.
- **QC-13 thresholds split**: `_THREE_LINE_CHARS=200` (detection/warning) vs. `_AUTO_TRIM_CHARS=260` (auto-trim trigger). 3-liners in 200–259 char range are now informational only.

**2026-03-29 (nonpm parser + summary pool fix)** — fixed `freeform_master_nonpm.txt` OUTPUT FORMAT and summary generation:
- **Company headers**: changed from archive-style `Gojek (description) – Location · Dates` to PM pipe format `GOJEK | Senior Software Engineer | Jan 2025 – Jul 2025 | Gurgaon, India`. The `extract_sections()` regex anchors on `GOJEK | Senior Software Engineer` — archive format never matched.
- **Skills bullet char**: changed from `•` (U+2022) to `●` (U+25CF) to match the skills parser regex (`SKILLS & INTERESTS\s*\n\s*●`).
- **Section order enforcement**: added `CRITICAL` note and explicit "Do not reorder" instruction after first run output sections as 1→3→4→0 instead of the expected 0→1→3→4.
- **Professional Summary pool enforcement** (`freeform_master_nonpm.txt`, lines 492–504): added CRITICAL VERBATIM requirement to all 5 variants (`[nonpm-default]`, `[nonpm-consulting]`, `[nonpm-gtm]`, `[nonpm-technical]`, `[nonpm-ops]`). First run showed model generating custom summary instead of picking pool variant verbatim. Now includes explicit "Output the chosen variant exactly as written. Do NOT paraphrase, merge, or reword." on line 494 and `CRITICAL:` on line 504, matching PM master pattern.
- **O1 cluster-a variants fixed**: both variants contained "supported" as secondary verb that Pass 2 rewrites as forbidden opener. Replaced with "analyzed" + specific mechanism: (1) network-gap-diagnostic: "analyzed coverage needs... and sized the integration opportunity"; (2) growth-constraint-analysis: "analyzed market coverage gaps and built the business case for the integration initiative".

**2026-03-28 (non-PM track — full implementation)** — initial `--track nonpm` launch; later expanded on 2026-04-09:
- **`--track` flag** (`freeform_runner.py`, `run_app.py`): `--track pm` (default) or `--track nonpm`. Controls which master prompt is loaded, which QC-07 Skills label set is enforced, and what docx summary header is generated. Auto-validates against `VALID_TRACKS = ("pm", "nonpm")`.
- **`freeform_master_nonpm.txt`**: initial version covered four non-PM routes; as of 2026-04-09 it covers seven calibrated route families and an optional `PROJECTS & CONSULTING` section while preserving the same 11-slot experience spine.
- **QC-07 track-aware** (`freeform_runner.py`): PM track checks `Product Focus:`, `Tools:`, `Interests:`, `Community:`. NonPM track now checks `Interests:` plus one of `Domain Expertise:`, `Operating Focus:`, `Commercial Focus:`, `Research Focus:`, `Workflow & AI Systems:`, `Implementation Focus:`, or `Core Competencies:`. Also flags `Product Focus:` as a wrong-label error in nonpm runs.
- **Scorer preamble** (`freeform_runner.py`): nonpm track prepends an 8-line context block to the scorer prompt so `reframed`, `diagnosed`, `synthesized`, `owned a workstream` are not flagged as `WRONG_ARCHETYPE`.
- **Docx summary header** (`resume_docx.js`): reads `data.summary_section_header` from payload. PM → `PRODUCT MANAGEMENT`, nonpm → `PROFILE`. Backward-compatible: defaults to `PRODUCT MANAGEMENT` if field absent.
- **`role_family` field** (`step0_strategy.txt`, `shared/strategy.py`): strategy prompt now emits `role_family: "pm" | "strategy-consulting" | "ops-execution"`. Included in formatted strategy block.
- **Track auto-detection** (`freeform_runner.py`): after Pass 0, if `track == "pm"` (default) but `strategy_dict["role_family"]` is non-PM, runner auto-switches to `"nonpm"` master + scorer preamble and prints a `[i]` note. Means `jobs.py pipeline` will route consulting/ops jobs to the nonpm track without any extra flag.

**2026-03-28 (professional summary final + docx header)** — 5-variant summary overhaul shipped:
- **Professional Summary pool replaced** (`freeform_master_v2.txt`): Old 6-variant pool (PM-enterprise, PM-marketplace, PM-AI, PM-fintech, PM-technical, PM-analytics) replaced with 5 new variants with a consistent formula: [PM identity/lens] + [decision proof with tradeoff signal] + [power shift: "Now at USC Marshall to move from X to Y"]. New variants: `[PM-default]` (general PM, $3.2M Gojek + 80K Intuit), `[PM-standout]` (reliability/technical PM, 120K+ pipelines + 80K businesses), `[PM-ai]` (AI/GenAI roles, Hevo pipelines + Optum risk models + L'Oréal GenAI), `[PM-growth]` (marketplace/supply, $3.2M ride tier + 18% supply expansion), `[PM-fintech]` (fintech/billing, $1.2M overbilling risk + "where financial accuracy is the product"). Selection rules updated to a–e (5 rules). No em dashes; comma/colon structure throughout.
- **Docx section header updated** (`resume_docx.js`): Section header changed from `'PROFESSIONAL SUMMARY'` to `'PRODUCT MANAGEMENT'` for ATS compatibility (signals PM identity without relying on job title).

**2026-03-27 (regression guard + H3 fix + summary rewrite)** — Three fixes after AXS run analysis:
- **H3 hard constraint** (`freeform_master_v2.txt`): Added `ORDERING RULE — HARD CONSTRAINT` block directly in the Hevo story pool header: H-FLEX ★ MUST always be H3; H-BATCHSHIFT and H-MONITORING must occupy H1 and H2. Root cause of previous 7.0: model placed H-BATCHSHIFT as H3, triggering ATTRIBUTION_MISMATCH because `[reliability-outcome]` cites both "120K+ data pipelines" and "8 enterprise customers" — scorer flags combined attribution. Constraint includes the failure reason so the model understands why.
- **Per-bullet regression guard** (`freeform_runner.py`): Pass 4 previously had only a holistic regression guard (revert entire section if holistic score drops). New per-bullet guard: before Pass 4, snapshot all 11 bullet texts and Pass 3 scores; after re-score, for each bullet compare new score to pre-fix score — if `new_score < pre_fix_score`, revert that specific bullet's text to the pre-Pass-4 version. Uses `_revert_regressed_bullets()` helper (walks lines by company + bullet index, selectively replaces regressions). Only fires when holistic guard did not revert the entire section. Logs each reverted bullet with before/after scores.
- **Professional summary variants rewritten** (`freeform_master_v2.txt`): All 6 variants replaced with punchy, metric-specific positioning statements. Old variants were generic ("5 years building enterprise data and platform systems... completing USC Marshall MBA to lead roadmaps"). New variants include concrete outcomes: `[PM-enterprise]` = "Technical PM in everything but job title for 5 years: drove Hevo's SMB-to-Fortune-500 pivot, fixed billing for 80K+ Intuit businesses, diagnosed supply constraints at Gojek." `[PM-marketplace]` includes "$3.2M ride-tier launch, 18% supply growth, 120K+ pipelines." `[PM-fintech]` includes "$1.2M overbilling risk, 80K+ businesses." `[PM-analytics]` calls out the observability + reconciliation systems specifically.

**2026-03-27 (content + summary pass)** — Major story bank + pipeline upgrades:
- **H-QUERY upgraded** (`freeform_master_v2.txt`): both variants now include `50% query latency reduction` (confirmed in Bullet Bank / story bank) and `adopted across all Hevo 2.0 dashboards` scope. Old variants mentioned "reusable filtering framework" only, with no latency metric. H-QUERY is now A-tier for analytics/data-platform JDs.
- **H-GENAI retired; H-MONITORING-AI added** (`freeform_master_v2.txt`): H-GENAI (7.0 ceiling, VAGUE_OUTCOME) replaced with H-MONITORING-AI — the real AI-assisted monitoring platform (anomaly detection + GenAI-based failure summarization, ~40% MTTR reduction across 120K+ enterprise pipelines). Confirmed by user as real work done at Hevo. H-FLEX decision rules updated: AI JDs → H-MONITORING-AI (not H-GENAI), analytics JDs → H-QUERY, execution JDs → H-REGRESSION.
- **Professional Summary pool added** (`freeform_master_v2.txt`): 6 JD-tailored variants (PM-enterprise, PM-marketplace, PM-AI, PM-fintech, PM-technical, PM-analytics). Output now includes Section 0 before Section 3. `freeform_runner.py` extracts `summary_section` key. `resume_docx.js` renders "PROFESSIONAL SUMMARY" section between contact line and EDUCATION. Fill estimator (`_estimate_height`) updated to account for summary DXA overhead.
- **Strategy Project as 6th Skills row** (`freeform_master_v2.txt`): L'Oréal consulting variant ("mapped GenAI use cases across 2 business units, 3 workflow recommendations for executive review") and Cloud Startup variant added. For AI JDs: use L'Oréal variant and skip `[ai-automation]` row (max 6 rows maintained). For all other JDs: use Cloud Startup variant. Row count rule added to Section 4 output format.

**2026-03-26** — Updated all story pools (GOJEK, HEVO, INTUIT, OPTUM) in `freeform_master_v2.txt` (Pass 1):
- **G-SUPPLY:** Simplified to 4 focused variants; removed revenue-attribution bullets; added NOTE on $110M platform revenue as org-level context only
- **G-PRICING:** Added NOTE on Diagnostic-first archetype requirement (scorer flags Impact-first as WRONG_ARCHETYPE); reorganized variants
- **H-BATCHSHIFT:** Streamlined to 5 variants with cleaner business-model-pivot opener
- **H-MONITORING:** Added CONSTRAINT on contrast-phrase ban; updated [debugging-reframe] to enforce no-contrast rule; 4 variants total
- **H-FLEX:** Simplified GenAI option (H-GENAI) with scorer note on delivery verbs
- **I-BILLING:** Added NOTE on platform-level renewal lift (context only, not outcome); reorganized to 5 variants
- **I-FLEX:** Clarified I-PRIORITIZATION vs. I-STRATEGIC-NO trade-off guidance; updated I-RECONCILIATION framing
- **O-PROVIDER:** Simplified to 5 clear variants with explicit attribution note (what's Akshat's work vs. org-level context)
- **O-AFFORDABILITY:** Reordered with [hackathon-impact] as impact-first lead; updated [business-case-AI] positioning

## Known limitations and ceilings

**H3 slot** — upgraded 2026-03-27. Now has three strong options: H-REGRESSION (execution, ~8), H-QUERY (analytics/data, ~8-8.5 with 50% latency metric), H-MONITORING-AI (AI roles, ~8-8.5 with concrete mechanism + metric). All are B+/A- tier. True A-tier would require a Hevo business-outcome story with retention/monetization impact.

**PLG gap** — the story bank has zero PLG-native stories (viral loops, self-serve activation, product-qualified leads). For PLG-focused JDs (Typeface, Zoom, etc.), the system foregrounds what it has but the underlying material is marketplace/enterprise, not PLG.

**Intuit I1 ordering** — for non-monetization JDs, the model sometimes leads Intuit with the incident response story rather than the billing/financial story. The billing story's "identified churn driver → shifted roadmap" arc is usually a stronger PM-thinking opener. A prompt rule fix is planned.

**What gets you from 8.5 to 9.5** — it's the raw material, not the system. Adding: (1) a monetization story from Hevo, (2) a PLG/activation story, (3) a sharper Hevo H3 story with business outcomes.

---

## Cost reference

| Pass               | Model  | Cost/job |
|--------------------|--------|----------|
| Pass 0+1           | Sonnet | ~$0.06   |
| Pass 2 rewrite     | Sonnet | ~$0.04   |
| Pass 3 score       | Sonnet | ~$0.02   |
| Pass 4 targeted fix| Sonnet | ~$0.04   |
| Pass 4 re-score    | Sonnet | ~$0.02   |
| **Resume total**   |        | **~$0.18** |
