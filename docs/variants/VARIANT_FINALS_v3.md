# Variant Finals v3 — Rules + All Approved Bullets
Last updated: 2026-03-29

---

## UPDATED T2P RULES (v3)

### Core Formula
[Diagnostic/Need Opener] + [Strategic Mechanism] + [Business Outcome]

"Diagnostic" is not always a data discovery — sometimes it's a stated business need.
The opener just needs to establish WHY this work happened before the mechanism runs.

---

### Marshall-Grade Vetting Checklist (v3)

- [ ] **Why Now?** Does the opener explain why this work was a priority? (data discovery, business need, or clear gap)
- [ ] **Causality Bridge** Strong linkers: "by," "surfaced through," "reframed as," "enabling," "triggering"
- [ ] **Earned Detail** ONE specific non-fakeable detail that grounds the mechanism. Must pass the removal test: if you remove it, does the bullet become generic? If yes, keep it. If the detail makes the bullet harder to follow in one read → drop it.
- [ ] **Length** 130–215 chars preferred (2-liner). 216–260 acceptable (3-liner). Keep 3-liners to ≤3 on the whole resume.
- [ ] **No Markdown** No bold, no asterisks
- [ ] **Mom Test** Non-technical recruiter can follow the thought in one read without pausing

---

### Key Rules Added / Updated vs v1

**1. Don't force earned detail.** If a specific detail makes the bullet harder to follow, abstract it or drop it. The detail must earn its place. "90-day automatic bail-out criterion with auto-termination" fails this — the jargon overloads before you know what the bullet is about.

**2. No em dashes anywhere in bullets.** Use commas or semicolons. Em dashes add noise, signal parenthetical thinking, and break two-beat rhythm.

**3. No parentheses anywhere in bullets.** Use "including X and Y" or restructure.

**4. Vary openers.** Don't start 5 bullets with "Diagnosed." Use: Identified, Surfaced, Linked, Recognized, Profiled, Expanded, Brought, Secured, Designed, Shipped, Drove.

**5. Start from the old variant when upgrading.** Old variants have battle-tested signal. The fix is usually ONE addition (diagnostic opener) or ONE swap (vague verb → specific mechanism). Not a full rebuild using only the story bank.

**6. Diagnosis isn't always needed.** If the business need is obvious (Gojek needed more supply), a business need opener or action opener is cleaner than forcing a discovery framing.

**7. Platform-level outcomes.** When the metric is platform-level (e.g., 18% supply growth is from all fleet integrations, not Akshat alone), prefer "enabling" or "contributing to" over "growing" or "generating."

**8. Impact-first: max 2–3 per resume.** Currently: [revenue-case] G-LATENCY + [hackathon-impact] O-AFFORDABILITY = 2. Within limit.

---

## G-LATENCY — All 5 Variants (APPROVED)

**Default PM variant: [cross-functional-drive]** — use for mixed/general PM roles.
[strategic-exec] is for strategy/exec-presenting roles, not the default.

**[strategic-exec]** ← strategy / exec-presentation roles
"Linked 40% higher abandonment in Singapore and 2.3x higher peak-hour drop-offs to competitive app-switching triggered by quote delays; drove a cross-functional roadmap to cut quote times 70% and enable ~28K additional monthly rides."
Note: 2.3x = ratio not em dash. No em dash version needed here.

**[revenue-case]** ← revenue/rides framing (IMPACT-FIRST, one of max 2–3 allowed)
"Diagnosed a 3.8s p95 latency tail hiding behind a 1.3s average, collapsing conversion 40% for high-intent users at booking; drove estimation redesign to recover the lost demand, cutting quote times 70% and enabling ~28K monthly rides."
Note on "too technical": p95 vs average IS PM signal — knowing to look at percentiles not averages is the diagnostic insight. Keep as-is.

**[cross-functional-drive]** ← ★ DEFAULT — broad PM / cross-functional roles
"Identified that a 1.3s average latency masked a 3.8s p95 tail triggering 40% drop-offs for high-intent users. Drove Product and Marketplace alignment to modernize estimation workflows, cutting quote times 70% and enabling ~28K additional monthly rides."

**[throughput-engineering]** ← platform / engineering PM roles
"Improved fare-estimate scalability under peak load by pre-caching pricing for the 12 highest-demand corridors, accepting ±4% fare variance for sub-second response; cut quote latency 70% and enabled ~28K additional monthly rides."

**[profiling-analysis]** ← technical PM / engineering-heavy roles
"Profiled fare-quote API performance under peak load and diagnosed a 3.8s p95 tail hiding behind a healthy 1.3s average; redesigned the estimation stack to close the gap, cutting quote latency 70% and enabling ~28K additional monthly rides."

---

## H-MONITORING-AI — Both Variants (APPROVED)

Fix from old: "anomaly detection" and "GenAI-based incident summarization" are categories, not mechanisms.
Fix: name "GenAI synthesizer" (specific product function) + "20+ failure taxonomy" (earned detail).
Keep: "AI-powered monitoring surface/platform" — powerful, memorable.
"GenAI synthesizer" is the right term — specific (not "AI model"), PM-level, memorable.

**[AI-monitoring-product]** ← BEST for AI product / AI infrastructure roles (user-approved verbatim)
"Designed an AI-powered monitoring surface to replace manual alert triage; used a GenAI synthesizer and a 20+ failure taxonomy to consolidate alert storms into single incident cards, cutting MTTR 40% across 120K+ pipelines."

**[AI-reliability-product]** ← AI + observability / reliability-heavy roles
"Shipped an AI monitoring surface as the primary observability layer for 120K+ enterprise pipelines; a GenAI synthesizer trained on a 20+ failure taxonomy replaced alert storms with structured incident cards, cutting MTTR 40%."

No: per-connector language, SLA thresholds, silent failure explanations, parentheses.

---

## G-SUPPLY — Updated Variants

Old [ecosystem-GTM] and [API-launch]: no diagnostic opener → WRONG_ARCHETYPE.
Fix: add ONE light opener showing why external fleet integration was needed.
Keep: $110M, "Defined integration requirements/specs," "onboarding workflow," "multi-partner fleet platform," 18% supply, 1.5-min ETA.
Not a dramatic diagnosis — a business need framing is fine.

**[ecosystem-GTM]** ← ★ when scale / marketplace context strengthens story
"Identified commercial fleet operators as an untapped supply source on Gojek's $110M+ marketplace; defined integration requirements and onboarding workflow for a multi-partner fleet platform, growing supply 18% across Singapore and Bali and cutting ETAs 1.5 minutes."

**[API-launch]** ← technical PM / developer-platform roles
"Expanded Gojek's marketplace supply by onboarding commercial fleet operators; defined integration specs and partner onboarding workflow for a multi-partner fleet API, enabling 18% supply growth across Singapore and Bali and reducing pickup ETAs 1.5 minutes."
Note: no forced diagnosis here — business need is self-evident. Action opener is cleaner.

Keep [supply-diagnosis], [problem-diagnosis], [partner-taxonomy] as-is — those are fine.

---

## I-BILLING — Updated Variants

Old [roadmap-pivot]: "drove a roadmap pivot from feature velocity to correctness" — WEAK_MECHANISM (no HOW).
Old [financial-case]: "built the financial case" — GENERIC.
Fix: name the specific mechanism (cross-org data join, reconciliation framework, sequencing argument).

**[roadmap-pivot]** replacement ← data-driven / retention / monetization roles
"Identified billing errors as the root of silent SMB cancellations, surfaced through a first-ever cross-org billing and subscription data join; reframed billing accuracy as a revenue protection play, redirecting engineering from feature delivery for one quarter."
Note: em dash removed (now comma); "won a one-quarter feature hold" → "redirecting engineering from feature delivery for one quarter" (clearer tradeoff).

**[financial-case]** replacement ← exec-presentation / roadmap pivot roles
"Surfaced billing inaccuracies as a churn risk for 80K+ businesses; designed a cross-system reconciliation framework to eliminate root-cause data mismatches and presented the business impact case to senior leadership, securing a roadmap pivot."
Note: "business impact case" (not "financial case" — more PM); "securing a roadmap pivot" = clear outcome; dropped $1.8M / LTV complexity — too convoluted.

Keep [churn-renewal], [trust-reliability], [exec-presentation] as-is.

---

## O-PROVIDER — Updated Variants

Old [GTM-execution]: "drove go-live" — GENERIC_MECHANISM.
Old [platform-scale]: $20M attributed directly to Akshat — ATTRIBUTION.
Fix: "drove go-live" → name specific mechanism. $20M → "claims revenue previously routing out-of-network."

**[GTM-execution]** replacement ← technical PM / integration / platform roles
"Defined integration requirements for a new provider partnership; resolved a schema mismatch between legacy XML and REST APIs through a custom transformation layer, cutting onboarding from 6 months to 10 weeks."
Note: "drove go-live" dropped — clean mechanism does the work. "by diagnosing" structure lives in [platform-scale].

**[platform-scale]** replacement ← when scale and revenue context strengthens story
"Brought a new provider into Optum's 50M-member care network by diagnosing a schema mismatch between legacy XML and REST APIs and delivering a custom transformation layer; cut onboarding from 6 months to 10 weeks and enabled $20M+ in claims revenue previously routing out-of-network."
Note: "by diagnosing" as the mechanism; $20M framed as claims revenue previously OON — accurate, not overclaimed.

Keep [schema-mechanism], [integration-diagnosis], [cross-functional-exec] as-is.

---

## O-AFFORDABILITY — Updated Variant

Old [business-case-AI]: "building the product requirements and stakeholder case" — GENERIC.
Fix: replace GENERIC with the specific framing shift (clinical risk safeguards, not business case).
Don't force jargon (90-day bail-out criterion) — it overloads before the bullet lands.
Take old as base, make ONE specific swap.

**[business-case-AI]** replacement ← responsible AI / clinical / regulated roles
"Secured pilot approval from hackathon prototype by reframing the stakeholder pitch around clinical risk safeguards rather than a business case; launched as Optum's first member-facing AI affordability tool."
Note: "clinical risk safeguards rather than a business case" = the specific mechanism (not generic "stakeholder case"). "rather than" contrast is fine in Optum section (no section contrast cap there).

**[tiered-intervention]** ← new variant for AI product design / ML-heavy roles
"Reframed Optum's affordability outreach from reactive to predictive; designed a risk model on prescription fill rate, ER frequency, and deductible utilization with a three-tier intervention playbook, piloted as Optum's first AI affordability tool."
Note: three named indicators = earned detail. "Reactive to predictive" = the diagnostic reframe.

Keep [hackathon-impact], [ML-product-design], [innovation-to-pilot], [responsible-AI] as-is.

---

## WHAT TO SHIP TO freeform_master_v2.txt (full list)

### G-LATENCY (all 5 replacements):
- [strategic-exec] — new version with 2.3x and competitive app-switching
- [revenue-case] — new version with p95 tail + conversion cliff
- [cross-functional-drive] — new version with p95 masked insight; NOTE as DEFAULT
- [throughput-engineering] — new version with 12 corridors + variance tradeoff
- [profiling-analysis] — new version with p95 tail diagnosis

### H-MONITORING-AI (both replacements):
- [AI-monitoring-product] — GenAI synthesizer + 20+ failure taxonomy
- [AI-reliability-product] — observability layer framing

### G-SUPPLY (2 replacements; keep 3 others as-is):
- [ecosystem-GTM] — add "Identified commercial fleet operators as untapped supply source" opener
- [API-launch] — replace with "Expanded Gojek's marketplace supply by onboarding..." opener

### I-BILLING (2 replacements; keep 3 others as-is):
- [roadmap-pivot] — cross-org join + revenue protection play + redirecting engineering
- [financial-case] — reconciliation framework + business impact case + roadmap pivot

### O-PROVIDER (2 replacements; keep 3 others as-is):
- [GTM-execution] — remove "drove go-live"; clean mechanism
- [platform-scale] — "by diagnosing" pattern; $20M as OON claims revenue

### O-AFFORDABILITY (1 replacement + 1 new):
- [business-case-AI] — clinical risk safeguards vs business case
- [tiered-intervention] — NEW variant (add after [business-case-AI])
