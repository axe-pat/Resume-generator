# Variant bank inventory — 2026-09-03

## Bottom line

The current freeform generator exposes **152 selectable prompt records across 27
semantic groups/surfaces**. It has **no exact duplicate selectable text**, but it
does have concentrated near-duplicate families. The newer gold overlay contains
**22 machine-admitted variants** (21 `promote-now`, 1 wording hold), but it is
deliberately isolated and is not yet used by `freeform_runner.py`.

This means the bank currently has two different meanings of “approved”:

- the master prompts are prose-approved by `VARIANT_FINALS_v4.md`, which says the
  master version is approved unless separately listed;
- the gold overlay is record-by-record approved against the new admission schema.

The live selector reads the first class directly from prompt text. It does not call
`shared.variant_admission` or `shared.gold_variant_registry`. Therefore **0 of the
152 live prompt records is machine-gated in its live selection path**, even though
3 selectable prompt texts exactly match an admitted gold record.

## Strict live inventory

“Selectable” below means the prompt tells the model it may choose the text. It does
not include PM summary variants currently marked reference-only, the PM legacy
Intuit/Optum blocks marked `DO NOT SELECT`, examples, output placeholders, or story
documents that are not loaded by the runner.

| Surface | Semantic groups | Selectable records |
|---|---:|---:|
| FlairX experience, PM only | 5 | 25 |
| Gojek experience, PM + NONPM wording banks | 3 | 30 |
| Hevo experience, PM + NONPM wording banks | 6 | 32 |
| Intuit experience, PM + NONPM wording banks | 4 | 25 |
| Optum experience, NONPM | 2 | 12 |
| Fluo inline venture row, PM | 1 | 4 |
| NONPM project proof: founder / L'Oréal / Grab | 3 | 7 |
| NONPM summary pool | 1 | 9 |
| PM analytics and community skill rows | 2 | 8 |
| **Total** | **27** | **152** |

Track totals:

- **PM: 78 selectable** = 66 experience + 4 Fluo + 8 skills/community.
  The 5 PM summaries are retained but explicitly unavailable under the current
  `Section 0 = NONE` prompt rule.
- **NONPM: 74 selectable** = 58 experience + 7 project-proof + 9 summary.
- The PM prompt also exposes **21 prohibited reference bullets** to the model:
  10 legacy Intuit and 11 Optum. Instructions prohibit selection, but physical
  prompt exposure remains a leakage surface.

The 20 unique live experience story families are:

- FlairX: `F-ENTERPRISE`, `F-AVATAR`, `F-OPS`, `F-CEIPAL`, `F-SOURCING`.
- Gojek: `G-SUPPLY`, `G-PRICING`, `G-LATENCY`.
- Hevo: `H-BATCHSHIFT`, `H-MONITORING`, `H-REGRESSION`, `H-QUERY`,
  `H-MONITORING-AI`, `H-SUPPORT-OPS`.
- Intuit: `I-BILLING`, `I-RECONCILIATION`, `I-GOVERNANCE`, `I-INCIDENT`.
- Optum: `O-PROVIDER`, `O-AFFORDABILITY`.

## Duplicates and redundancy

Method: collapse whitespace, case, and punctuation for exact matching. For near
duplicates, compare normalized character sequences and flag pairs at similarity
`>= 0.85`. This is triage, not an automatic deletion rule.

- **Exact selectable duplicates: 0.**
- **High-similarity experience pairs: 8.** All occur inside one NONPM story
  family; none crosses tracks or story families.
- Six of the eight pairs come from four `O-AFFORDABILITY` variants:
  `ai-workflow-design`, `pilot-decision-workflow`, `decision-workflow`, and
  `ai-solution-delivery` (similarity 0.872–0.984).
- One pair is NONPM `O-PROVIDER` market-entry vs segment-prioritization (0.869).
- One pair is NONPM `G-PRICING` business-case vs thesis-validation (0.856).
- At a looser 0.75 threshold there are 13 experience pairs, still all within the
  same story family. The problem is sibling differentiation, not corpus-wide copy.

Gold-overlay overlap is small: 3 of 22 gold records exactly match a currently
selectable prompt variant (`G-PRICING` StudyFetch, `H-MONITORING-AI` StudyFetch,
and `H-BATCHSHIFT` StudyFetch). Two more exact gold texts sit only in the PM
Optum reference block and are prohibited on that track. The other 17 gold records
are not exact prompt text.

## Canonical, review, and story-source status

These sources should not be added together as if they were independent variants:
most are successive versions or richer evidence for the same story.

| Source class | Inventory | Actual status |
|---|---:|---|
| Gold overlay | 22 records / 16 story IDs | Machine-admitted; 21 promote, 1 hold; not live-wired |
| Canonical story files | 17 files (16 `_GOLD_REFERENCE_` + `hevo_ai_monitoring`) | Evidence sources; several contain explicit confirmation notes |
| FlairX V2 review | 10 candidate bullets | Earlier conservative candidate set; overlaps current 25 |
| FlairX V3 review | 25 named story variants plus slate copies | Superseded by V4; do not review independently |
| FlairX V4 review | 27 named variants | Proposed replacement pool, never copied into the live prompt |
| Fluo fact-base drafts | 14 drafts | 10 no-blank drafts + 4 explicitly incomplete templates |
| Fluo V1 bank | 15 named bank variants across 8 story families, plus top/second-entry alternatives | Candidate bank; only selected finals belong in shipping overlay |
| Profile-maxing lab | 12 story files | Counterfactual design targets; quarantine from fact sourcing |

### Fact/source decisions, not wording reviews

Only conflicts or explicit gaps should come to the user. The highest-priority ones are:

1. **FlairX V4 conflicts with the gold overlay and the user's later fact decision.**
   V4 labels `$1.2M`, `94%`, zero-downtime, and several other outcomes as invented
   or amplified, while the gold overlay marks its admitted records `fact_status =
   approved`. The user has said the old fabrication tags were misplaced. This is a
   source-state reconciliation task: update one canonical fact state later, then let
   every affected variant inherit it. Do not ask for separate approval of every
   wording that repeats the same atom.
2. **Hevo AI monitoring:** the story source itself says to confirm the `120K+`
   figure even though current prompt/gold text uses it.
3. **Optum affordability:** the story source says pilot outcome numbers are soft.
   The admitted prototype/pilot-approval wording is safer than any realized impact.
4. **Intuit recovery:** the story source flags soft outcome metrics. Keep incident
   role and affected-customer facts separate from unconfirmed recovery rates.
5. **Recruiting engine:** three offers are user-reported but not linked in the
   outcome ledger. Current admitted bullets correctly use applications, contacts,
   acceptances, and replies instead.
6. **Fluo:** four fact-base templates still contain blanks; the V1 metric canon also
   distinguishes live outcomes from estimates, plans, and open partnership mechanics.
   Those records remain non-selectable until their shared atoms clear.

### Wording/quality challenges

After fact atoms clear, these deserve pairwise wording review rather than new fact work:

- the eight high-similarity NONPM pairs above;
- `F-OPS`, where multiple variants describe system construction but compete on a
  weak or indirect downstream outcome;
- `F-CEIPAL`, where ecosystem, adoption, technical-integration, and sync-hardening
  variants need a clean value-signal distinction;
- PM `H-FLEX`, because three different story families compete for one slot and must
  be ranked by profile, not globally;
- summaries, which should be reviewed as identity claims and not mixed into bullet
  quality scoring.

## What “apply the quality formula to all variants” should mean

It should **not** mean asking the user to rate 152 bullets, and it should not mean
computing one average that can hide a failed dimension.

### 1. Machine inventory and lineage

Parse every live record into a stable ID: `track / story / variant`. Attach normalized
text, fact atoms, source references, role tags, line cost, and eligible profiles.
Quarantine reference-only and counterfactual sources before any model sees the bank.

### 2. Fact-atom gate, once per shared claim

Resolve a metric or claim once, then propagate its status to every sibling variant.
Only `approved` atoms may enter a shipping candidate. `pending`, contradictory, or
missing-source atoms create a compact user decision list grouped by fact, not by bullet.

### 3. Variant veto gate, once per wording

Use the existing admission contract as independent vetoes:

- one argument;
- mechanism supports the opener's claim;
- outcome closes the same claim;
- outsider-legible;
- strongest attributable outcome available;
- stakes >= 3, difficulty >= 2, defensibility >= 3, distinctiveness >= 2;
- line cost 1–4.

Decision quality, human presence, and metric salience remain warning/ranking fields.
An otherwise elegant bullet that fails one hard dimension does not survive on its mean.

### 4. Sibling dominance and deduplication

Within each story/profile pair, compare candidates head-to-head. Auto-retire an exact
duplicate. Flag near duplicates. Keep a sibling only if it buys a genuinely different
value signal, archetype, outcome currency, or materially lower line cost. “Same proof,
different opener” is not enough.

### 5. Profile selection, per JD

Only after admission should the model rank by JD fit, profile priorities, identity mix,
non-duplication, and marginal page value. Assembly lint remains document-level and
must not be pushed back into the variant gate.

## Review batches that do not waste the user's time

The machine processes all 152 records. Human review sees only unresolved facts and
champion-versus-challenger decisions. Cap each checkpoint at **10–12 exact bullets and
3–5 decisions**.

| Batch | Scope | What the user actually reviews |
|---|---|---|
| 0 — source conflicts | Shared fact atoms across all profiles | Only the 5–8 contradictory or missing claims; no prose polishing |
| 1 — product general | Amazon gold spine + best FlairX/Fluo alternatives | One champion per funded signal and only challengers that could displace it |
| 2 — AI / zero-to-one delta | FlairX AI, H-MONITORING-AI, Optum AI, Recruiting Engine | Variants not already cleared in Batch 1 |
| 3 — data/platform delta | F-AVATAR, G-SUPPLY/LATENCY, H-BATCHSHIFT/QUERY/REGRESSION, O-PROVIDER | Trade-off, platform, and customer-deployment challengers only |
| 4 — enterprise + operations | NONPM G/H/I anchors for enterprise, BizOps, Ops/PgM | Route champions plus the few support variants needed for a different archetype/line cost |
| 5 — commercial + research | G-PRICING/LATENCY, I-RECONCILIATION, O-PROVIDER, Fluo GTM | Commercial/research champions; retire same-proof paraphrases |
| 6 — customer technical | Client implementation and deployed-systems deltas | Only variants that differ from cleared product/data champions |
| 7 — campus | Lane C student-service, analytics, communications proof | Fluo, Niveda, and campus-specific rows; not the corporate bank again |
| 8 — summaries/skills | Identity headings, summary champions, compact support rows | Page-level identity choices after bullet bank is stable |

Because batches are deltas, a bullet cleared for Product General is not shown again for
AI, data, or customer-technical unless the profile changes the claim materially. The
expected human surface is roughly **40–60 finalist/challenger texts plus the compact
fact-conflict list**, not 152 prompt records and not every draft in the story engine.

## Recommended next move

Build a read-only inventory artifact first, then run Batch 0 and Batch 1. Do not edit
the two live prompts during triage. Once a batch is approved, add only its surviving
finalists to the isolated registry, validate them, and compare the incumbent prompt
against a registry-backed shadow run. Promotion happens only after the challenger wins;
the source prompts remain the rollback path.

## Verification performed

- Parsed both live master prompts by section and variant label.
- Normalized all selectable text for exact duplicate detection.
- Compared all experience pairs at 0.85 near-duplicate similarity.
- Compared all 22 gold records against the prompt bank.
- Ran registry/admission architecture tests: **67 passed, 1 skipped** with
  `PYTHONPATH=.`.
