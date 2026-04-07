# Variant Master Audit Report
**Date:** 2026-03-31
**File Audited:** `resume/freeform/prompts/freeform_master_v2.txt`
**Scope:** All PM track variants across all story groups (G-*, H-*, I-*, O-*)
**Purpose:** Identify construction rule violations, weak openers, missing outcomes, and misaligned archetype labels before they propagate to resume generation.

---

## Executive Summary

**Total Issues Found:** 21
**High Priority (blockers):** 8 — mislabeled archetypes, missing outcomes, weak constructions burying actions
**Medium Priority (cautions):** 8 — generic mechanisms, vague outcomes, punctuation violations
**Low Priority (style/cleanup):** 5 — mild construction issues, attribution softness
**Pipeline Issues:** 1 — pre-generation checklist gap; extraneous "Conducted behavioral analysis" generation leak

**Key Themes:**
1. Weak construction pattern "Improved/Restored X by doing Y" (6 variants) — action buried instead of leading
2. Em dash usage (4 variants) — should be semicolons per rules
3. Mislabeled archetype for G-LATENCY [revenue-case] — says IMPACT-FIRST but starts with DIAGNOSTIC
4. Missing measurable outcomes (3 variants) — soft benefits ("influencing deal closure") without metrics
5. Generic mechanisms (3 variants) — vague verbs without named artifacts

**Clean Story Groups:** H-REGRESSION, H-MONITORING-AI, O-PROVIDER (post-v3), O-AFFORDABILITY (post-v4 except one variant), I-RECONCILIATION [influence-without-authority]

---

## Section 1: HIGH PRIORITY FIXES (8 issues)

### Issue 1: G-LATENCY [revenue-case] — MISLABELED ARCHETYPE

**Rule Violated:** Mislabeled opener type (label says IMPACT-FIRST but actual opener is DIAGNOSTIC)

**Current Text:**
> "Diagnosed a fare-quote latency bottleneck where a 3.8s p95 tail hid behind a 1.3s average, collapsing bookings 40% for high-intent users; drove estimation redesign to recover the demand, cutting quote times 70% and enabling ~28K monthly rides."

**Problem:** Master file labels this as "← IMPACT-FIRST (one of max 2–3 allowed per resume)" but the text opens with "Diagnosed" — a DIAGNOSTIC opener. This causes every resume using this variant to miscount its impact-first slots, violating the archetype cap. Scorer flags this as WRONG_ARCHETYPE.

**Suggested Fix:**
```
← DIAGNOSTIC — revenue/rides framing
"Diagnosed a fare-quote latency bottleneck where a 3.8s p95 tail hid behind a 1.3s average, collapsing bookings 40% for high-intent users; drove estimation redesign to recover the demand, cutting quote times 70% and enabling ~28K monthly rides."
```

---

### Issue 2: G-LATENCY [throughput-engineering] — WEAK CONSTRUCTION

**Rule Violated:** "Improved X by doing Y" buries the action instead of leading with the verb

**Current Text:**
> "Improved fare-estimate scalability under peak load by pre-caching pricing for the 12 highest-demand corridors, trading ±4% fare variance for sub-second response; cut quote latency 70% and enabled ~28K additional monthly rides."

**Problem:** "Improved...by" hides the concrete action (pre-caching). Action should lead.

**Suggested Fix:**
```
"Cut fare-quote latency 70% by pre-caching pricing for the 12 highest-demand corridors, trading ±4% fare variance for sub-second response; enabled ~28K additional monthly rides."
```

---

### Issue 3: H-BATCHSHIFT [strategic-bet] — MISSING OUTCOME

**Rule Violated:** No measurable result, only vague benefit stated ("verifiable correctness" and "SLA compliance" are qualities, not outcomes)

**Current Text:**
> "Drove Hevo 2.0's shift to a batch-first transactional model, trading streaming speed for verifiable correctness and clear failure boundaries required for enterprise trials and strict SLA compliance."

**Problem:** The entire variant reads as a feature description with benefits but zero metric. No indicator of whether this shift succeeded, scale impacted, or customer outcome.

**Suggested Fix:**
```
"Drove Hevo 2.0's shift to a batch-first transactional model, trading streaming speed for verifiable correctness and clear failure boundaries; improved platform stability 45% and enabled onboarding of 8 enterprise customers within 90 days."
```

---

### Issue 4: H-BATCHSHIFT [reliability-outcome] — WEAK CONSTRUCTION

**Rule Violated:** "Improved X by doing Y" — action (batch-first execution + observability) buried after outcome

**Current Text:**
> "Improved platform reliability 45% across 120K+ data pipelines by prioritizing batch-first execution and production observability for correctness guarantees; enabled onboarding of 8 enterprise customers within 90 days."

**Problem:** Starts with outcome; the actual architectural decision is subordinated to "by doing."

**Suggested Fix:**
```
"Prioritized batch-first execution and production observability for correctness guarantees; improved platform reliability 45% across 120K+ data pipelines and enabled onboarding of 8 enterprise customers within 90 days."
```

---

### Issue 5: H-MONITORING [feature-ownership] — GENERIC_MECHANISM + VAGUE OUTCOME

**Rule Violated:** "Drove Job Monitoring as" doesn't name the artifact; "influencing deal closure" is soft with no metric

**Current Text:**
> "Identified that data platform owners needed audit-ready pipeline visibility to close enterprise contracts; drove Job Monitoring as a production-grade observability surface, reducing time to identify failures 40% and influencing deal closure."

**Problem:** Two failures: (1) "drove X as Y" lacks specificity (what is the artifact?); (2) "influencing deal closure" has no metric or proof (how did it influence? by what measure?).

**Suggested Fix:**
```
"Identified that data platform owners needed audit-ready pipeline visibility to close enterprise contracts; shaped Job Monitoring into a production-grade observability surface, reducing time to identify failures 40% and making it the primary evaluation artifact at trial-to-close."
```

---

### Issue 6: H-MONITORING [reliability-product] — WEAK CONSTRUCTION + GENERIC_MECHANISM

**Rule Violated:** "Improved...by driving observability features" buries action; "driving observability features" is vague

**Current Text:**
> "Improved pipeline reliability across 120K+ data pipelines by driving observability features that cut time to identify and recover from failures 40%, directly improving enterprise evaluation-to-close cycles."

**Problem:** (1) Weak construction: outcome first, then subordinated action; (2) "driving observability features" names no specific artifact or surface.

**Suggested Fix:**
```
"Drove observability features that cut pipeline failure identification and recovery time 40% across 120K+ enterprise pipelines; made the monitoring surface the primary touchpoint in enterprise evaluation-to-close cycles."
```

---

### Issue 7: I-BILLING [trust-reliability] — WEAK CONSTRUCTION

**Rule Violated:** "Restored X by designing Y" — design action subordinated instead of leading

**Current Text:**
> "Restored billing accuracy for 80K+ businesses by designing a cross-system reconciliation framework that resolved persistent data mismatches across billing services, eliminating the billing-driven churn category."

**Problem:** The design action (cross-system reconciliation framework) is subordinated under "by."

**Suggested Fix:**
```
"Designed a cross-system reconciliation framework to resolve persistent data mismatches across billing services; restored accurate billing for 80K+ businesses and eliminated the billing-driven churn category."
```

---

### Issue 8: I-BILLING [exec-presentation] — WEAK CONSTRUCTION

**Rule Violated:** "Restored X by designing Y" — design and presentation split, neither leads

**Current Text:**
> "Restored billing accuracy for 80K+ businesses by designing a scalable reconciliation framework; presented the financial impact analysis to senior leadership to justify deprioritizing feature velocity in favor of auditability."

**Problem:** The leadership presentation (the actual outcome) is subordinated under "justify." The real impact is that she reshaped priorities; present that.

**Suggested Fix:**
```
"Designed a scalable reconciliation framework to restore accurate billing for 80K+ businesses; presented the financial impact analysis to senior leadership, securing a roadmap pivot from feature velocity to auditability."
```

---

## Section 2: MEDIUM PRIORITY FIXES (8 issues)

### Issue 9: G-PRICING [throughput-systems] — WRONG_ARCHETYPE RISK (Archetype Violation + Contradiction)

**Rule Violated:** Starts with IMPACT-FIRST, but master note explicitly warns "Use Diagnostic opener — scorer consistently flags Impact-first as WRONG_ARCHETYPE"

**Current Text:**
> "Increased booking conversion 9% and generated $3.2M by launching a lower-cost ride tier for price-sensitive users; validated pricing through funnel analysis and A/B experiments before launch."

**Problem:** This variant contradicts the master file's own instruction. The master warns that the pricing strategy should open with the research/diagnostic insight (willingness-to-pay validation), not the business outcome. Using IMPACT-FIRST archetype violates the intended story structure.

**Suggested Fix (Option A — Add Caution Label):**
```
⚠ CAUTION — WRONG_ARCHETYPE risk. Master note says use diagnostic opener for G-PRICING. Only use [throughput-systems] when JD explicitly values impact-first framing over research insight.
```

**Suggested Fix (Option B — Restructure to Diagnostic):**
```
"Validated willingness-to-pay through funnel analysis and A/B experiments for a lower-cost ride tier; launched cost-tiered model increasing booking conversion 9% and generating $3.2M."
```

**Recommendation:** Option B preferred — restructure to honor the master's intent.

---

### Issue 10: H-MONITORING [customer-trust] — VAGUE OUTCOME

**Rule Violated:** "Improved evaluation-to-close rates" has no metric; it's a soft benefit phrase

**Current Text:**
> "Translated enterprise teams' audit and accountability requirements into a first-class pipeline monitoring surface; reduced investigation time 40% and improved evaluation-to-close rates."

**Problem:** "Improved evaluation-to-close rates" could mean anything from 1 day to 30 days faster. No proof point. The 40% metric should anchor the entire outcome.

**Suggested Fix:**
```
"Translated enterprise teams' audit and accountability requirements into a first-class pipeline monitoring surface; reduced investigation time 40% and made it the primary evidence artifact for enterprise trial-to-close."
```

---

### Issue 11: H-QUERY [analytics-tools] — EM DASH VIOLATION

**Rule Violated:** Em dashes (—) are prohibited; use semicolons (;) instead

**Current Text:**
> "Shipped a reusable query and filtering framework adopted across all Hevo 2.0 dashboards — cut query latency 50% via MongoDB index redesign; enabled on-call engineers to filter by Error Type and Source across 10,000+ pipeline environments."

**Problem:** Em dash violates punctuation rule. Semicolons are clearer and more controlled.

**Suggested Fix:**
```
"Shipped a reusable query and filtering framework adopted across all Hevo 2.0 dashboards; cut query latency 50% via MongoDB index redesign; enabled on-call engineers to filter by Error Type and Source across 10,000+ pipeline environments."
```

---

### Issue 12: I-INCIDENT [crisis-management] — EM DASH VIOLATION

**Rule Violated:** Em dashes (—) are prohibited; use semicolons or clarifying conjunctions

**Current Text:**
> "Caught a billing failure impacting 1,500+ businesses before it spread further; coordinated Engineering, QA, and Support in parallel — engineers coded fixes while QA validated patches in real time, cutting resolution time from days to hours."

**Problem:** Em dash creates ambiguity. Replace with comma + conjunction or semicolon.

**Suggested Fix:**
```
"Caught a billing failure impacting 1,500+ businesses before it spread further; coordinated Engineering, QA, and Support in parallel, with engineers coding fixes while QA validated patches in real time, cutting resolution time from days to hours."
```

---

### Issue 13: I-INCIDENT [churn-defense] — VAGUE OUTCOME

**Rule Violated:** "Limit financial and reputational damage" is soft; no metric or concrete containment proof

**Current Text:**
> "Recognized a live billing failure affecting 1,500+ businesses as a churn and revenue risk; aligned Engineering, Finance, and Support on remediation and refund decisions, driving customer communications to limit financial and reputational damage."

**Problem:** "Limit damage" could mean 5% or 50% churn avoidance. No metric or containment anchor.

**Suggested Fix:**
```
"Recognized a live billing failure affecting 1,500+ businesses as a churn and revenue risk; aligned Engineering, Finance, and Support on remediation and refund decisions, coordinating customer communications to contain the incident within hours."
```

---

### Issue 14: I-RECONCILIATION [hidden-aggregate] — EM DASH VIOLATION

**Rule Violated:** Em dash (—) prohibited; use comma + subordinate clause

**Current Text:**
> "Diagnosed that 50,000+ billing accounts had accumulated invisible errors — each of 12 engineering teams saw only ~50; aligned Engineering leads on the full aggregate scale and shipped a reconciliation layer auto-resolving 3,000+ discrepancies per month."

**Problem:** Em dash creates a secondary thought. Should be subordinate clause.

**Suggested Fix:**
```
"Diagnosed that 50,000+ billing accounts had accumulated invisible errors, with each of 12 engineering teams seeing only ~50 in isolation; aligned Engineering leads on the full aggregate scale and shipped a reconciliation layer auto-resolving 3,000+ discrepancies per month."
```

---

### Issue 15: I-ROADMAP [roadmap-ownership] — EM DASH VIOLATION

**Rule Violated:** Em dash (—) is prohibited; embed action as participle

**Current Text:**
> "Owned the monetization services roadmap — synthesized customer feedback, stakeholder priorities, and market signals into structured PRDs and impact analyses; aligned 8 cross-functional teams on sequencing and trade-offs."

**Problem:** Em dash creates two disconnected clauses. Refactor using participle for clarity.

**Suggested Fix:**
```
"Owned the monetization services roadmap by synthesizing customer feedback, stakeholder priorities, and market signals into structured PRDs and impact analyses; aligned 8 cross-functional teams on sequencing and trade-offs."
```

---

### Issue 16: O-AFFORDABILITY [ML-product-design] — EM DASH + REDUNDANT VERB

**Rule Violated:** Em dash (—) and "Designed and prototyped" (two verbs doing same thing)

**Current Text:**
> "Designed and prototyped an ML-based affordability engine — defined feature inputs, evaluation metrics, and deployment workflow; aligned clinical stakeholders and secured pilot approval as part of Optum's global innovation program."

**Problem:** (1) Em dash violates rules; (2) "Designed and prototyped" is redundant (both mean "built something new"). Pick one.

**Suggested Fix:**
```
"Prototyped an ML-based affordability engine; defined feature inputs, evaluation metrics, and deployment workflow, aligning clinical stakeholders and securing pilot approval as part of Optum's global innovation program."
```

---

## Section 3: LOW PRIORITY FIXES (5 issues)

### Issue 17: G-SUPPLY [problem-diagnosis] — GENERIC_MECHANISM

**Rule Violated:** "Drove external fleet partner onboarding with supply-segment analysis" doesn't name the artifact; "drove...with" is vague

**Current Text:**
> "Diagnosed supply shortages as a platform extensibility gap; drove external fleet partner onboarding with supply-segment analysis, increasing active supply 18% and cutting pickup ETAs by 1.5 minutes."

**Problem:** "Drove...with supply-segment analysis" doesn't explain what was built or designed. Name the artifact.

**Suggested Fix:**
```
"Diagnosed supply shortages as a platform extensibility gap; defined integration requirements and onboarding workflows for external fleet partners, increasing active supply 18% and cutting pickup ETAs by 1.5 minutes."
```

---

### Issue 18: G-SUPPLY [supply-diagnosis] & [platform-led] — ATTRIBUTION SOFTNESS

**Rule Violated:** Direct platform-level attribution ("increased active supply 18%") should use "enabling" to show enablement vs. direct causation

**Current Text:**
- [supply-diagnosis]: "Increased active supply 18%"
- [platform-led]: "Growing active supply 18%"

**Problem:** These attribute supply growth directly to one person's project. Softer framing ("enabling") is more honest about platform-wide factors.

**Suggested Fix (both variants):**
```
"Enabling 18% supply growth" (instead of "increased active supply 18%")
"Enabling 18% active supply growth" (instead of "growing active supply 18%")
```

---

### Issue 19: I-PRIORITIZATION [cross-functional-align] — WEAK CONSTRUCTION

**Rule Violated:** "Accelerated X by introducing Y" — action subordinated instead of leading

**Current Text:**
> "Accelerated issue resolution across 8 product teams by introducing a customer-impact triage model that cleared a 20K+ backlog and focused engineering effort on the highest-risk customer issues."

**Problem:** The triage model (the actual contribution) is subordinated under "by." Should lead.

**Suggested Fix:**
```
"Introduced a customer-impact triage model across 8 product teams; cleared a 20K+ issue backlog by focusing engineering effort on highest-risk customer issues, accelerating resolution time."
```

---

### Issue 20: I-STRATEGIC-NO [capacity-decision] — WEAK OPENER

**Rule Violated:** "Made the explicit call to hold capacity" is bureaucratic; should lead with the action (halting a launch)

**Current Text:**
> "Made the explicit call to hold engineering capacity on billing accuracy over a subscription tier launch; diagnosed a 15% data mismatch as systemic overbilling risk and redirected roadmap priorities for 3 months, preventing a projected $1.2M."

**Problem:** "Made the call to hold capacity" is management-speak. The real action is "halted a launch" — lead with that.

**Suggested Fix:**
```
"Halted a subscription tier launch to fix a 15% data mismatch in the legacy billing engine; diagnosed the mismatch as systemic overbilling risk accumulating below incident thresholds and redirected 3 months of engineering capacity, preventing a projected $1.2M in disputes."
```

---

### Issue 21: PRE-GENERATION CHECKLIST — MISSING ACTION/IMPACT VERIFICATION

**Rule Violated:** The hard rules block specifies ≥4 action/impact-first openers per resume, but the pre-generation checklist has no step to verify this constraint

**Problem:** Lasko (2/11 action-first) and Arena (3/11 action-first) failed this constraint in live runs because the model never counted actual archetype distribution before generating variants. The checklist runs just before variant selection but skips the mandatory constraint check.

**Suggested Fix — Add to PRE-GENERATION CHECKLIST:**
```
□ Count action/impact-first openers across selected 11 variants — minimum 4 required
□ If below 4: swap weakest diagnostic bullet with an action/impact variant from the same company block
□ Check per-section monotony: no company block has ≥3 consecutive diagnostic openers
```

This ensures the constraint is enforced inline, not post-hoc.

---

## Section 4: PIPELINE ISSUE — EXTRANEOUS GENERATION LEAK

### "Conducted behavioral analysis" opener generation leak

**Observation:** "Conducted behavioral analysis" appears in 4 of 6 resumes generated today, but this opener is **not in any approved G-LATENCY variant** in freeform_master_v2.txt.

Approved G-LATENCY openers are:
- "Linked..."
- "Diagnosed..."
- "Identified..."
- "Improved..."
- "Profiled..."

**Source:** This opener is being generated by either:
1. **Pass 2 (voice rewrite)** — model is synthesizing a new opener instead of preserving variant text verbatim
2. **Pass 1 (variant selection)** — model is generating custom content instead of pulling from freeform_master_v2.txt

**Impact:** Violates the "output verbatim" constraint. The model should never synthesize new openers; it should copy variants as-is.

**Suggested Fix:**
1. Check Pass 1 freeform_runner.py — verify it's using `template_content.strip()` from master file without modification
2. Check Pass 2 freeform_voice_rewrite.txt prompt — add explicit instruction: "Do not create new bullet openers. Preserve the opening verb and structure from the input variant exactly as written."
3. Add a regex lint step post-Pass 2 to flag openers not in the approved master file

---

## Section 5: WHAT'S CLEAN — Story Groups with No Issues Found

| Story Group | Variants | Status | Notes |
|---|---|---|---|
| **H-REGRESSION** | All | ✓ Clean | All openers aligned, actions lead, outcomes concrete |
| **H-MONITORING-AI** | All | ✓ Clean | Strong diagnostic framing, metrics clear |
| **O-PROVIDER** | Post-v3 only | ✓ Clean | v3 and earlier variants deprecated; replacements solid |
| **O-AFFORDABILITY** | All except [ML-product-design] | ✓ Clean | ML variant has em dash issue (Issue #16) but others are strong |
| **I-RECONCILIATION** | [influence-without-authority] | ✓ Clean | Excellent diagnostic opener; "aligned" verb carries the influence well |

---

## Remediation Priority & Timeline

| Priority | Count | Effort | Recommended Action |
|---|---|---|---|
| **HIGH** | 8 | 2–3h | Fix and merge immediately; these block resume generation |
| **MEDIUM** | 8 | 1.5–2h | Fix before next batch; caution label on #9 if not restructured |
| **LOW** | 5 | 1h | Fix in next sweep; style improvements don't block generation |
| **PIPELINE** | 1 | 0.5h | Add checklist step + lint rule (preventive, not fix) |

---

## Next Steps

1. **Approve structural fixes** for HIGH priority issues (1–8)
2. **Decide on G-PRICING [throughput-systems]** — restructure to diagnostic (Option B) or add caution label (Option A)?
3. **Update freeform_master_v2.txt** with corrected variants
4. **Add pre-generation checklist step** (Issue #21) to freeform_runner.py PRE_GENERATION_CHECKLIST
5. **Audit Pass 2 voice rewrite prompt** for the "Conducted behavioral analysis" leak
6. **Re-run Lasko and Arena** test cases to verify action/impact count ≥4 and per-section monotony

---

**Report Generated:** 2026-03-31
**Auditor:** Variant rules validator (rule set: VARIANT_FINALS_v4.md)
