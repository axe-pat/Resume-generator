# Variant Finals v2 — Approved & Corrected
Last updated: 2026-03-29

Philosophy: keep what was strong in the old variants, add ONE specific earned detail,
keep it clean. No jargon salad. Prefer 2-liners. Don't abandon strong signals.

---

## H-MONITORING-AI — Both Variants

Old variants failed because "anomaly detection" and "GenAI-based incident summarization"
are product categories, not specific design decisions.
Fix: Name the specific mechanism (GenAI synthesizer + 20+ failure taxonomy).
Keep: "AI-powered monitoring surface/platform" — powerful, memorable.

**[AI-monitoring-product]** ← BEST for AI product or AI infrastructure roles
"Designed an AI-powered monitoring surface to replace manual alert triage; used a GenAI synthesizer and a 20+ failure taxonomy to consolidate alert storms into single incident cards, cutting MTTR 40% across 120K+ pipelines."

**[AI-reliability-product]** ← for AI + observability or reliability-heavy roles
"Shipped an AI monitoring surface as the primary observability layer for 120K+ enterprise pipelines; a GenAI synthesizer trained on a 20+ failure taxonomy replaced alert storms with structured incident cards, cutting MTTR 40%."

Notes:
- [AI-monitoring-product] is user-approved verbatim — use exactly as written
- No parentheses anywhere; no per-connector / SLA language; no "silent failure" explanation
- "20+ failure taxonomy" = the earned detail that makes it non-fakeable

---

## G-SUPPLY — Replacement Variants

Old [API-launch] and [ecosystem-GTM] failed WRONG_ARCHETYPE because they had
no diagnostic opener — just "Defined integration specs" with no PM discovery signal.
Fix: add a light one-line diagnostic. Keep all strong signals: $110M, "Defined integration
requirements", "multi-partner fleet platform", 18% supply, 1.5-min ETA.

**[ecosystem-GTM]** ← ★ TOP PICK — when scale/marketplace context strengthens story
"Diagnosed that Gojek's $110M+ marketplace had untapped fleet supply capacity; defined integration requirements and onboarding workflow for a multi-partner fleet platform, scaled to Singapore and Bali, growing supply 18% and cutting ETAs 1.5 minutes."

**[API-launch]** ← technical PM / developer-platform roles
"Diagnosed that Gojek's marketplace model excluded commercial fleet operators; defined integration specs and partner onboarding workflow for a multi-partner fleet API, enabling 18% supply growth across Singapore and Bali and reducing pickup ETAs 1.5 minutes."

**[partner-taxonomy]** ← cross-partner coordination / supply ecosystem roles (ALREADY GOOD — no change)
"Defined API specs and onboarding workflows for metro, bus, and private fleet partners on Gojek's platform; scaled to Singapore and Bali, grew supply 18% and reduced pickup ETAs by 1.5 minutes."

Notes:
- Keep [supply-diagnosis] and [problem-diagnosis] as-is — those are fine
- The only change to [ecosystem-GTM] and [API-launch] is adding a brief diagnostic opener
- "enabling 18% supply growth" vs "growing active supply 18%" — "enabling" softens attribution correctly

---

## I-BILLING — Replacement Variants

Old [roadmap-pivot] failed WEAK_MECHANISM — "drove a roadmap pivot" with no HOW.
Old [financial-case] failed GENERIC — "built the financial case" is activity, not mechanism.
Fix: name the specific mechanism (cross-org data join, LTV math, sequencing argument).
Keep: 80K+ businesses, reconciliation framework, roadmap pivot framing.

**[roadmap-pivot]** replacement ← ★ TOP PICK — data-driven / retention / monetization roles
"Identified billing errors as the root of silent SMB cancellations — surfaced through a first-ever cross-org billing and subscription data join; reframed the fix as a revenue protection play and won a one-quarter feature hold."

**[financial-case]** replacement ← PM judgment / risk-aware / roadmap trade-off roles
"Modeled that a planned subscription tier on a 15% billing mismatch would generate $1.8M in overbilling risk; reframed the roadmap as a sequencing decision — fix first, launch second — and redirected engineering one quarter without blocking the feature."

Notes:
- Keep [churn-renewal], [trust-reliability], [exec-presentation] as-is — those are solid
- [roadmap-pivot] replacement: cross-org data join is the specific PM signal; "revenue protection" is the reframe that moved leadership
- LTV 40% above median DROPPED — too complicated, adds length without proportional signal
- "fix first, launch second" — clean two-beat reframe, no jargon

---

## O-PROVIDER — Replacement Variants

Old [GTM-execution] failed GENERIC_MECHANISM — "drove go-live" is vague.
Old [platform-scale] failed ATTRIBUTION — $20M attributed as Akshat's direct output.
Fix: name the specific mechanism (reusable template, 80% common logic).
Fix: frame $20M correctly as "claims revenue previously routing out-of-network."
Keep: legacy XML / REST schema mismatch, custom transformation layer, 6 months → 10 weeks.

**[GTM-execution]** replacement ← ★ TOP PICK — technical PM / integration / platform roles
"Defined integration specs for a stalled provider partnership; built a reusable schema transformation template — 80% common logic, typed slots for provider-specific mappings — cutting onboarding from 6 months to 10 weeks."

**[platform-scale]** replacement ← when scale and revenue context strengthens story
"Integrated a new provider into Optum's 50M-member care network, enabling $20M+ in claims revenue previously routing out-of-network; diagnosed a schema mismatch between legacy XML and REST APIs and delivered a custom transformation layer, cutting onboarding from 6 months to 10 weeks."

Notes:
- Keep [schema-mechanism], [integration-diagnosis], [cross-functional-exec] as-is — those are solid
- "80% common logic, typed slots for the 20%" = the earned detail (non-fakeable, specific PM design decision)
- $20M is now framed as claims revenue previously going to OON providers — accurate, not overclaimed

---

## O-AFFORDABILITY — Replacement Variant

Old [business-case-AI] failed GENERIC_MECHANISM — "building the product requirements
and stakeholder case" is activity description, not specific mechanism.
Fix: name the exact design element (90-day auto bail-out criterion) that won approval.
Keep: hackathon → pilot arc, "first member-facing AI affordability tool" positioning.

**[business-case-AI]** replacement ← ★ TOP PICK — responsible AI / clinical / regulated roles
"Identified that clinical leadership's approval blocker was exit risk, not model accuracy; designed a 90-day automatic bail-out criterion with auto-termination, winning approval as Optum's first member-facing AI affordability tool."

**[tiered-intervention]** ← new variant for AI product design / ML-heavy roles
"Reframed Optum's affordability outreach from reactive to predictive; designed a risk model on prescription fill rate, ER frequency, and deductible utilization with a three-tier intervention playbook, piloted as Optum's first AI affordability tool."

Notes:
- Keep [hackathon-impact] as-is — impact-first, self-credentialing, works well
- Keep [ML-product-design], [innovation-to-pilot], [responsible-AI] as-is
- [business-case-AI] fix: the 90-day bail-out criterion is the earned detail — specific, surprising, memorable
- [tiered-intervention]: three named indicators = earned detail; "reactive to predictive" = the diagnostic reframe

---

## WHAT TO SHIP TO freeform_master_v2.txt

### Direct replacements (swap old text with new):
- H-MONITORING-AI [AI-monitoring-product] — full replacement
- H-MONITORING-AI [AI-reliability-product] — full replacement
- G-SUPPLY [ecosystem-GTM] — add diagnostic opener only
- G-SUPPLY [API-launch] — add diagnostic opener only
- I-BILLING [roadmap-pivot] — full replacement
- I-BILLING [financial-case] — full replacement
- O-PROVIDER [GTM-execution] — full replacement
- O-PROVIDER [platform-scale] — full replacement
- O-AFFORDABILITY [business-case-AI] — full replacement
- O-AFFORDABILITY [tiered-intervention] — new variant (add after [business-case-AI])

### G-LATENCY (approved last session — ship these too):
- [strategic-exec], [revenue-case], [cross-functional-drive], [throughput-engineering], [profiling-analysis]
  → all 5 replacements from VARIANT_FINALS_v2.md / VARIANT_RULES_AND_FINALS.md
