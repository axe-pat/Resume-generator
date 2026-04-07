# Non-PM Resume Architecture Plan

**Status:** ✅ Built — 2026-03-28
**Date drafted:** 2026-03-28
**Goal:** Extend the freeform resume system to generate top-tier resumes for non-PM roles, using the same infrastructure and story facts but with role-appropriate framing.

---

## Target role families

- Strategy & Operations (S&O)
- Management Consulting (MBB, boutique, in-house)
- Corporate Strategy
- Program Manager (PgM, Technical PgM)
- GTM / Revenue Operations / Business Operations
- Operations roles (general)

Not: SWE roles (these use a different resume entirely).

---

## Architectural decision: 2-prompt system

**Do NOT build a separate master prompt per role.** Instead:

```
freeform_master_v2.txt       ← existing PM prompt (unchanged)
freeform_master_nonpm.txt    ← new, covers ALL non-PM role families
```

Within `freeform_master_nonpm.txt`, an internal `role_family` signal (detected from the JD in Step 0) branches between two clusters:

**Cluster A — Strategy/Consulting**
Target: MBB, corporate strategy, in-house strategy, BD
Language: "diagnosed X as Y (not Z)", "reframed", "operating model", "future-state architecture", "hypothesis-driven", "market assessment", "synthesized primary research"

**Cluster B — Ops/Execution**
Target: S&O, PgM, RevOps, GTM, Biz Ops, technical PgM
Language: "governance model", "portfolio triage", "throughput", "cross-functional alignment", "delivered against milestones", "standup", "workstream", "OKR"

These two clusters are more similar to each other than either is to PM — one master handles both with internal branching (same mechanism as H-FLEX/I-FLEX in the PM master).

---

## Runner changes needed

Add `--track` flag to `freeform_runner.py`:

```
--track pm       (default, uses freeform_master_v2.txt)
--track nonpm    (uses freeform_master_nonpm.txt)
```

Also update the strategy step (`shared/strategy.py`) to emit a `role_family` field in the strategy JSON:
```json
"role_family": "strategy-consulting" | "ops-execution" | "pm"
```

Runner auto-detects track from `role_family` if `--track` is not explicitly passed.

---

## What's different in the non-PM master vs PM master

### Framing axes
PM master primary axes: product-sense, enterprise-GTM, technical-depth, cross-functional-execution
Non-PM primary axes: **analytical-rigor**, **operational-impact**, **executive-influence**, **cross-functional-delivery**

### Verb palette
| PM | Strategy/Consulting | Ops/Execution |
|----|--------------------|----|
| Drove | Diagnosed | Generated |
| Identified | Reframed | Accelerated |
| Shaped | Synthesized | Transformed |
| Owned the roadmap | Defined future-state | Delivered against |
| Built | Recommended | Established governance |

### Skills section
PM master: `Product Focus:`, `Tools:`, `Interests:`
Non-PM: needs different labels — TBD based on archive review. Probably:
Strategy cluster: `Domain Expertise:`, `Analytics & Strategy Tools:`, `Interests:`
Ops cluster: `Core Competencies:`, `Tools & Platforms:`, `Interests:`

### Professional summary variants
Need a separate summary pool for non-PM (not the PM-default / PM-standout etc.). These don't exist yet — write them after studying the archive.

---

## Stories already proven in the non-PM archive

The archive resumes (read 2026-03-28) confirm the core facts are the same — only framing changes. These variants already exist as hand-written bullets in the archive and need to be codified into story bank format.

### GOJEK stories (non-PM framing, confirmed)

**G-SUPPLY (Strategy/Consulting frame):**
"Unlocked ~$110M+ in annual value and 18% higher peak-hour supply by owning the supply-expansion workstream; tested the hypothesis that fragmented public-transport integrations were limiting scalability and designed the future-state multi-partner operating model to integrate metro, bus, and private fleets across Singapore and Bali."

**G-PRICING (Strategy/Consulting frame):**
"Led a market diagnostic to evaluate rider willingness-to-pay; combined primary research (30+ stakeholder interviews) with funnel analysis to recommend a segmented monetization strategy, driving a 9% booking lift and $15M+ in value."

**G-LATENCY (Strategy/Consulting frame):**
"Identified revenue leakage as a pricing-process bottleneck, rather than demand; analyzed latency data to isolate conversion barriers and recommended a redesigned pricing workflow, delivering ~$5M+ in impact through 70% faster fare-quote generation."

### HEVO DATA stories (non-PM framing, confirmed)

**H-BATCHSHIFT (Strategy/Consulting frame):**
"Owned a core workstream in Hevo's enterprise-readiness transformation; diagnosed churn risk as a reliability and observability problem (not feature gaps) and defined the future-state architecture, enabling onboarding of 12 enterprise clients within 90 days."

**H-MONITORING (Strategy/Consulting frame):**
"Identified slow incident resolution as a decision-visibility issue, not an engineering-capacity constraint; modernized the monitoring framework to surface actionable signals, reducing time-to-insight ~40% and improving SLA performance by 30%."

**H-SUPPORT-OPS (NEW — does not exist in PM master):**
"Reframed recurring escalations as an operating-model gap between Support and Engineering; designed a cross-team incident intake and prioritization model, accelerating resolution and improving reliability for enterprise customers."
Best for: S&O, PgM, Operations roles. Has no PM equivalent.

### INTUIT stories (non-PM framing, confirmed)

**I-RECONCILIATION (Strategy/Consulting frame):**
"Owned a data-integrity workstream to address billing discrepancies impacting SMB renewals; identified cross-system misalignment as the root cause and designed a standardized reconciliation model across five platforms, restoring accuracy for 80K+ businesses and driving a 10% renewal lift."

**I-INCIDENT (Strategy/Consulting frame):**
"Led cross-functional problem solving during a critical billing incident impacting 1,500+ businesses; synthesized technical diagnostics and customer-impact data to guide remediation and refunds, containing value at risk and restoring trust."

**I-GOVERNANCE (NEW — does not exist in PM master):**
"Reframed delivery inefficiency as a governance problem, not capacity; analyzed a 20K+ issue backlog across eight teams and implemented a portfolio triage model, improving throughput by 25% by prioritizing highest-risk work."
Best for: S&O, PgM, Consulting (operational improvement). Has no PM equivalent.

### OPTUM stories (non-PM framing, confirmed)

**O-AFFORDABILITY (Strategy/Consulting frame):**
"Owned an innovation workstream on member affordability; reframed cost management as prediction and proposed an AI model to flag high out-of-pocket risk and recommend lower-cost care, winning Optum's global hackathon and advancing to pilot."

**O-PROVIDER (Strategy/Consulting frame):**
"Diagnosed growth constraints as network-access gaps, not demand; supported provider-network integration after analyzing coverage needs, unlocking access for 50M users and ~$20M+ in incremental revenue."

---

## New story slots (not in PM master)

The non-PM master has **13 story slots** to draw from vs 11 in PM:

| Slot | PM equivalent | Non-PM story |
|------|--------------|-------------|
| G1 | G-SUPPLY | G-SUPPLY |
| G2 | G-PRICING | G-PRICING |
| G3 | G-LATENCY | G-LATENCY |
| H1 | H-BATCHSHIFT | H-BATCHSHIFT |
| H2 | H-MONITORING | H-MONITORING |
| H3 | H-FLEX (Regression/Query/AI) | H-SUPPORT-OPS *or* H-REGRESSION |
| I1 | I-RECONCILIATION | I-RECONCILIATION |
| I2 | I-INCIDENT | I-INCIDENT |
| I3 | I-FLEX (Prioritization/Roadmap) | I-GOVERNANCE |
| O1 | O-PROVIDER | O-PROVIDER |
| O2 | O-AFFORDABILITY | O-AFFORDABILITY |

Note: H-QUERY and H-MONITORING-AI (PM H-FLEX options) probably don't belong in the non-PM master — they're product-framed. H-SUPPORT-OPS and H-REGRESSION (reframed as "release governance") are more appropriate.

---

## Files to read first (before building)

The following archive files were only partially read on 2026-03-28. Read all of them before writing the master prompt:

```
resume_archive/Non-PM/Akshat Pathak_StrategyOps.pdf       ← READ ✓
resume_archive/Non-PM/Akshat Pathak GTM_RevOps.pdf         ← READ ✓
resume_archive/Non-PM/Consulting/Akshat Pathak's MBB resume.pdf  ← READ ✓
resume_archive/Non-PM/Consulting/Akshat Pathak consulting base.docx  ← NOT READ (docx)
resume_archive/Non-PM/Consulting/Akshat Pathak PwC resume -2.pdf   ← NOT READ
resume_archive/Non-PM/Consulting/Akshat Pathak Pwc resume.pdf      ← NOT READ
```

Also read the non-Consulting archive (Tanium, Epicor, NetApp, PTC, Box, etc.) — these may have PgM/S&O variants worth codifying.

---

## Build sequence

1. ✅ **Read remaining archive files** (docx + PwC PDFs above)
2. ✅ **Extract all non-PM bullet variants** — organized by story slot and role cluster
3. ✅ **Write `freeform_master_nonpm.txt`** with:
   - WHO AKSHAT IS block (same core, different emphasis)
   - Story pool with Cluster A + Cluster B variants per story
   - New story slots: H-SUPPORT-OPS, I-GOVERNANCE
   - Role-family selection rules (same mechanic as H-FLEX)
   - Non-PM professional summary pool (5 variants)
   - Output format (same 4-section structure as PM master)
4. ✅ **Add `--track` flag** to `freeform_runner.py` + auto-detect from role_family post-Pass-0
5. ✅ **Update strategy step** to emit `role_family`
6. ⬜ **Test run** against a known S&O JD and a known consulting JD (requires Mac terminal)
7. ✅ **Update READMEs**

---

## Key constraint: maintain quality parity

The PM pipeline produces 8.5-9.2 holistic scores. The non-PM pipeline should match this. Do not ship until test runs score 8.0+ on the non-PM scorer (same scoring prompt, role-adjusted framing expectations).

The non-PM master should use the SAME scorer (`freeform_scorer.txt`) since the scoring principles (mechanism visibility, attribution accuracy, earned detail, metric placement) apply regardless of role type. The scorer will need a brief note on role-appropriate language so it doesn't flag "reframed" or "diagnosed" as non-PM verbs.

---

## What NOT to build

- Do not create separate masters per role (no `freeform_master_consulting.txt`, `freeform_master_pgm.txt` etc.)
- Do not fork the runner — add a flag, not a separate script
- Do not touch the PM master for this project
- Do not change the docx generator — non-PM resumes use the same layout

---

## Open questions (resolve before building)

1. Should the non-PM master have its own professional summary pool, or share with PM? (Probably separate — the positioning narrative is different.)
2. Does the skills section need different row labels? (Probably yes — "Product Focus:" doesn't fit a consulting resume.)
3. For PgM roles: 3/3/3/2 bullet structure still right? Or do PgM resumes traditionally show more "delivery artifacts" (milestones, teams managed)?
4. Attribution guards: the $110M+ and $15M+ figures appear in the StrategyOps archive but not PM master (PM master uses $110M only in G-SUPPLY ecosystem-GTM). Should these flow through in non-PM variants?
