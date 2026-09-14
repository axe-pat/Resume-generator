# FlairX professional-resume port — implementation record

**Status:** routing/allocation, summary, and profile-eligibility code implemented;
resumes have not yet been regenerated.

## 1. Allocation contract — critical

The PM architecture is being reused, not replaced:

- 10 Experience bullets by default.
- 9 only to protect admitted quality or repair a dense page.
- 11 only when one additional admitted story adds a distinct signal and the page fits.
- FlairX is `minimum 2 / target 2 / maximum 3` on every professional resume.
- A third FlairX bullet must come from a third story family and either displace a
  lower-marginal bullet at 10 or earn the gated eleventh slot. Four is barred.

Default centers:

| Profile | FlairX | Gojek | Hevo | Intuit | Optum |
|---|---:|---:|---:|---:|---:|
| Product general / AI | 2 | 3 | 2 | 2 | 1 |
| Product data platform | 2 | 2 | 3 | 2 | 1 |
| Enterprise / business leadership | 2 | 2 | 2 | 2 | 2 |
| Operations / program leadership | 2 | 2 | 3 | 2 | 1 |
| Commercial / GTM | 2 | 3 | 2 | 2 | 1 |
| Customer-technical client value | 2 | 2 | 2 | 2 | 2 |
| Customer-technical deployed systems | 2 | 2 | 3 | 2 | 1 |

The automatic 2-to-3 FlairX comparison remains bounded by the same rule: a third bullet
is selected only when it materially beats the marginal non-FlairX proof on criterion fit
and page value, with no critical loss in stakes, ownership, outcome closure, or outsider
legibility. An exact tie keeps the two-bullet default.

## 2. Route decisions for the 11 affected resumes — critical

| Role | Resolved profile | Why |
|---|---|---|
| Adobe Corporate Strategy | Enterprise / business leadership | Recommendation quality and executive strategy are the output. |
| Hartford Product Analytics LDP | Product general | The rotations explicitly lead into Product Development and Product Management. |
| onsemi AI & Data Analytics | Customer-technical deployed systems | The deliverable is a working AI tool, data model, controls, and operational handoff. |
| Momentum MBA S&O | Enterprise / business leadership | Operating models, business cases, and transformation choices. |
| Barclays Operations Analyst | Operations / program leadership | Operational control, reconciliation, risk, and process improvement. |
| Vanguard MBA General Management | Enterprise / business leadership | Executive-facing rotational strategy and initiative ownership. |
| Momentum Launch S&O | Enterprise / business leadership | Workflow diagnosis and portfolio-level operating choices. |
| Retell Forward Deployed Engineer | Customer-technical deployed systems | Customer discovery plus production code and integrations. |
| SCE MBA LDP | Enterprise / business leadership | Cross-functional strategy across finance, regulation, procurement, and operations. |
| Nuvo Forward Deployed Engineer | Customer-technical deployed systems | Custom technical solutions, integrations, and field-to-product feedback. |
| Fora Wolf Program | Operations / program leadership | Product operations, automation, internal tools, launches, and advisor operations. |

## 3. New non-PM summary challengers — approved and shipping-selectable

These are alternatives inside the closed selector slate. Existing corporate-led
summaries remain available; FlairX is not forced into every summary. Each challenger is
eligible only for its named profile and only when its required FlairX story family is
selected on-page.

### A. Enterprise / strategy

> Strategy and operations professional with five years turning ambiguous operating evidence into consequential business choices. Reframed an enterprise hiring-policy objection as a product gap at a growing AI hiring platform, then led a two-week launch that unblocked $1.2M in pilots.

Requires the selected `F-ENTERPRISE` proof. Best for corporate strategy, transformation,
and general-management roles where the current U.S. role should prove judgment and delivery.

### B. Operations / program

> Operations and program leader with five years building the mechanisms that turn cross-functional ambiguity into reliable execution. Converted founder-held account context into shared Product and GTM workflows at an AI hiring startup, removing the CEO as the routing point for routine decisions.

Requires the selected `F-OPS` organizational-leverage proof. Best for Product Ops, BizOps,
program, and operating-model roles.

### C. Technical solutions — customer integration

> Customer-facing technologist with five years turning ambiguous workflows into deployed data and AI systems. Re-scoped a blocked ATS integration into a pull-first product at an enterprise AI hiring platform, removing roughly 80% of duplicate recruiter entry and retaining its highest-volume account.

Requires the selected `F-CEIPAL` account-retention proof. Best for forward-deployed,
solutions, integration, and customer-engineering roles.

### D. Technical solutions — AI workflow

> Technical solutions leader with five years translating workflow constraints into deployable data and AI systems. Turned an enterprise hiring-policy objection into privacy-safe scheduling and transcript-grounded scoring at an AI-native hiring platform, shipping the workflow in two weeks.

Requires the selected `F-ENTERPRISE` proof. Best for AI-tool, technical-delivery, and
workflow-automation roles where the Ceipal integration is not the best anchor.

## Verification already complete

- All 11 dry prompts resolve without contract errors.
- Dry prompts expose only profile-eligible FlairX variants: 14 enterprise, 10
  operations, 12 commercial, 18 client-value, and 14 deployed-systems variants.
- Focused architecture, prompt, and live-bridge suite: **103 passed**.

Next: complete the gated same-budget third-FlairX comparison, run the broader regression
suite, then regenerate the 11 resumes through one v2 batch command.

## Post-smoke allocation correction

The first live Adobe v2 smoke test exposed a general allocation regression: the
enterprise-leadership center forced two Optum bullets even when the second, oldest-role
proof was materially weaker than a third recent Gojek proof. Professional defaults now
retain Optum once for five-year career continuity. Enterprise leadership uses
`2 FlairX / 3 Gojek / 2 Hevo / 2 Intuit / 1 Optum`; customer-technical client value uses
`2 FlairX / 2 Gojek / 3 Hevo / 2 Intuit / 1 Optum`. Canonical per-story framings are also
marked as quality incumbents so a keyword-matched alternative cannot displace them by
regressing mechanism, outsider clarity, stakes, ownership, or outcome closure.

After a prompt-only preference still selected three weaker, keyword-shaped siblings in
the Adobe smoke test, this was tightened deterministically: when a reviewed family has a
`canonical_default_id`, only that exact variant is exposed to live v2 generation. The
other reviewed framings remain in the inert batch files for future human reconsideration;
the model still chooses among distinct story families, but it no longer re-litigates an
already-settled wording decision on every JD.
