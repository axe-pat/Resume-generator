# Batch B — Gojek and Hevo variant audit

**Scope:** `G-SUPPLY`, `G-PRICING`, `G-LATENCY`, and `H-BATCHSHIFT` across the
live PM prompt, live NONPM prompt, canonical V4 overrides, approved gold, and
canonical story evidence.

**Mode:** local reasoning only. No external model/API was called. No live prompt,
variant, registry, or selector was edited.

## Decision standard

- Reconstruct the claim spine from story evidence before judging wording.
- Keep the incumbent on an exact material tie.
- Replace automatically only when the challenger Pareto-improves the material
  dimensions and loses none.
- `hold` means a claim/value inconsistency still needs a user decision; the user has
  now resolved every hold in this batch.
- `retire` means the wording is dominated or fails the connected-spine test even if
  its facts are later confirmed.
- Page fit remains assembly context, not a variant-level veto.

## HIGH-IMPACT claim/value decisions — resolved

The user confirmed every on-file value is defensible and delegated one canonical
representation per collision. Selection therefore follows material strength, causal
attribution, and outsider legibility rather than provenance conservatism:

1. **G-SUPPLY:** use **1.5 minutes**; retire 2 minutes and do not present `$110M+`
   marketplace scale as project impact.
2. **G-PRICING:** use **20+ interviews, explicit A/B proof, 9% conversion, and
   $3.2M incremental revenue**. The canonical challenger combines the strongest
   parts of the former diagnosis and experimentation variants. Retire 30+ / $15M+.
3. **G-LATENCY:** use **~28K recovered monthly rides**, not `$5M+`. This is the
   direct product outcome and avoids repeating G-PRICING's revenue currency.
4. **H-BATCHSHIFT:** use **8 enterprise customers in 90 days**, not 12. Eight is
   directly connected to the execution-model decision; the 12-customer copy grafts
   monitoring requirements onto the batch-shift path.

The exact defaults and locked literals live in
`CANONICAL_STORY_DECISIONS_2026-09-03.json`; the Markdown companion explains each
choice. Role-specific alternates may vary emphasis but may not revive a retired
metric or move it between stories.

**Resolved during this audit: inventory extraction.** The parser previously reduced
`pm/g-pricing/funnel-synthesis` to `Synthesized [data→insight]` in the snapshot even
though the live prompt contained a complete sentence. The parser is now fixed and the
inventory snapshot refreshed. This is no longer an open claim or variant issue.

---

## G-SUPPLY

### Re-derived claim spines

1. **Product ownership spine:** fragmented bespoke fleet integrations → a reusable
   platform/operating-model decision → standardized API and partner validation →
   +18% supply and −1.5-minute ETA across Singapore and Bali.
2. **Technical contract spine:** commercial fleets could not scale through ad hoc
   partner builds → define the shared contract and validation workflow → remove
   custom integration work → the same supply/ETA outcome.
3. **Operations spine:** external fleet capacity needed one repeatable launch model →
   build the multi-partner operating model across two markets → supply/ETA outcome.

The `$110M+` marketplace context and metro/bus/private taxonomy are supporting scale
and specificity. Neither is the causal result. The recommended bullets therefore do
not spend their lead or close on those atoms.

### Recommended slate, in broad-default / use-case order

**1. General product / platform ownership — canonical default**

> Led Gojek's fleet integration platform and partner operating model; replaced bespoke builds with a standardized API and validation workflow, enabling 18% supply growth and cutting pickup ETAs by 1.5 minutes across Singapore and Bali.

Why first: the whole spine is visible, ownership is direct, and the operating model
plus API makes this useful across PM and enterprise-leadership routes.

**2. Technical platform / API contract — new challenger**

> Defined the standardized API contract and partner validation workflow that replaced bespoke fleet integrations across Singapore and Bali, growing supply 18% and cutting pickup ETAs by 1.5 minutes.

Why it survives: it proves technical product-contract ownership without claiming the
whole platform and costs less than the general-product sibling. It is not just an
opener paraphrase; the slot question changes from end-to-end ownership to contract
design.

**3. Operations / execution — new challenger**

> Built Gojek's multi-partner operating model across Singapore and Bali, standardizing API requirements and validation for commercial fleets; grew supply 18% and cut pickup ETAs by 1.5 minutes.

Why it survives: it makes the repeatable operating mechanism the scarce atom for
operations and general-management roles. It avoids `$110M+` scale and the unsupported
2-minute outcome.

**4. Partner ecosystem specificity — retain live PM incumbent**

> Defined API specs and onboarding workflows for metro, bus, and private fleet partners on Gojek's platform; scaled to Singapore and Bali, grew supply 18% and reduced pickup ETAs by 1.5 minutes.

Why it survives: metro, bus, and private fleets are a genuinely distinct taxonomy
signal for partner-platform roles. The user's fact instruction removes the prior reason
to hold it; no other recommended sibling carries those partner types.

### Incumbent disposition map

| Incumbent ID | Decision | Destination / material reason |
|---|---|---|
| `pm/g-supply/supply-diagnosis` | **retire** | Grammar failure (`that enabling`) and generic “integration requirements”; dominated by slate 2. |
| `pm/g-supply/api-launch` | **replace** | Slate 2 makes the reusable contract, not onboarding activity, the subject. |
| `pm/g-supply/problem-diagnosis` | **replace** | “Platform extensibility gap” is abstract; slate 1 carries the same result with outside-legible before-state and ownership. |
| `pm/g-supply/ecosystem-gtm` | **retire** | `$110M+` is context, “driver recruitment couldn't fix” is not needed, and the sentence is denser without adding a distinct criterion. |
| `pm/g-supply/partner-taxonomy` | **retain, priority 4** | Distinct partner-taxonomy proof for ecosystem and partner-platform roles. |
| `pm/g-supply/platform-led` | **replace** | Slate 1 Pareto-adds the operating model and explicit bespoke-build before-state while preserving ownership and outcomes. |
| `canonical-v4/g-supply/ecosystem-GTM` | **retire** | Same dominated `$110M+`/driver-recruitment spine as the live sibling. |
| `canonical-v4/g-supply/API-launch` | **replace** | Slate 2 is the same contract claim with less activity framing and stronger before-state. |
| `canonical-v4/g-supply/platform-led` | **replace** | Slate 1 adds the partner operating model and the displaced bespoke builds. |
| `nonpm/g-supply/cluster-a-workstream-hypothesis` | **replace** | Slate 3 removes hypothesis narration and non-causal marketplace revenue while retaining operating ownership. |
| `nonpm/g-supply/cluster-a-diagnostic-market` | **replace** | Priority 4 preserves the full partner taxonomy while adding concrete API/onboarding work and the 1.5-minute outcome; `$110M+` is non-causal context. |
| `nonpm/g-supply/cluster-b-impact-operating-model` | **replace** | Priority 4 preserves the partner types and adds the specific interface/onboarding mechanism plus ETA outcome. |
| `nonpm/g-supply/support-only-route-secondary` | **replace** | Slate 3 adds validation and ETA; use the incumbent only if page assembly cannot fund the extra line. |
| `nonpm/g-supply/cluster-b-delivery-led` | **retire** | Uses 2 minutes rather than the 1.5-minute incumbent fact and adds `$110M+` context. |
| `G-SUPPLY-amazon-operating-model` | **replace** | Canonical default strengthens the opener with the playbook's “Led” verb and fixes platform-level attribution from “growing” to “enabling.” |

---

## G-PRICING

### Re-derived claim spines

1. **Problem-separation spine:** abandonment contained price and latency causes →
   separate the price-sensitive segment → launch the lower-cost tier → +9%
   conversion and $3.2M incremental revenue.
2. **Closed evidence-loop spine:** lower-cost willingness-to-pay hypothesis → funnel
   analysis + 20+ interviews → A/B confirmation → launch and the same outcome.

The two spines genuinely prove different criteria, but they no longer require two
defaults. The canonical challenger carries the cause-separation insight and closes
the evidence loop with A/B proof in one connected argument.

### Recommended slate, in broad-default / use-case order

**1. Default product / strategy / research — canonical default**

> Separated price-sensitive abandonment from quote-latency drop-off through funnel analysis and 20+ rider interviews; validated a lower-cost ride tier through A/B tests, lifting conversion 9% and generating $3.2M in incremental revenue.

**2. General product / segmentation — retained alternate**

> Separated price-sensitive abandonment from quote-latency drop-off using funnel analysis, elasticity modelling and 20+ rider interviews; launched a cost-tiered ride product which lifted conversion 9% and generated $3.2M in incremental revenue.

**3. Research / experimentation — retained alternate**

> Validated willingness-to-pay for a lower-cost ride tier through funnel analysis and 20+ customer interviews; confirmed via A/B pricing experiments and launched a cost-tiered model lifting conversion 9% and generating $3.2M.

### Incumbent disposition map

| Incumbent ID | Decision | Destination / material reason |
|---|---|---|
| `pm/g-pricing/pricing-strategy` | **replace** | Canonical default adds cause separation and retains A/B closure. |
| `pm/g-pricing/elasticity-analysis` | **replace** | Canonical default resolves the prior tradeoff by preserving cause separation, customer research, A/B proof, and realized impact together. |
| `pm/g-pricing/funnel-synthesis` | **replace** | Canonical default leads the insight rather than an inventory of methods and adds A/B closure. |
| `pm/g-pricing/wtp-research` | **retain, priority 3** | Exact text match to `G-PRICING-studyfetch-wtp-experiment`; use only as a shorter research-led alternate. |
| `pm/g-pricing/revenue-lift` | **retire** | Same WTP claim with process repeated after an impact opener; no distinct proof and higher load. |
| `nonpm/g-pricing/cluster-a-segmentation-diagnostic` | **replace** | Canonical default is the selected scale/impact representation and preserves the stronger realized outcome. |
| `nonpm/g-pricing/cluster-a-commercial-thesis` | **replace** | Canonical default removes adjacent competitor/unit-economics claims and retains one closed product path. |
| `nonpm/g-pricing/cluster-a-target-segment-thesis` | **replace** | “Highest-conversion segment” is a different claim; canonical default uses the supported price-versus-latency separation. |
| `nonpm/g-pricing/cluster-b-business-case-anchor` | **replace** | Canonical default preserves A/B proof with the selected 20+ / 9% / $3.2M fact set. |
| `nonpm/g-pricing/cluster-b-thesis-validation` | **replace** | Same canonical replacement. |
| `G-PRICING-amazon-cause-separated` | **retain, priority 2** | Diagnosis-led alternate using the canonical fact set. |
| `G-PRICING-studyfetch-wtp-experiment` | **retain, priority 3** | Research-led alternate using the canonical fact set. |

---

## G-LATENCY

### Re-derived claim spines

1. **Technical tradeoff spine:** live recalculation slowed quotes → choose cached
   pricing for 12 high-demand corridors → hold variance within 4% → −70% latency
   and ~28K recovered monthly rides.
2. **Distribution diagnosis spine:** a healthy 1.3-second average hid a 3.8-second
   p95 and 40% drop-off → target the tail with the same bounded caching mechanism →
   the same latency/rides outcome.
3. **Competitive-strategy spine:** Singapore/peak abandonment implied app switching
   → prioritize quote speed as a competitive lever → outcome.

### Recommended slate, in broad-default / use-case order

**1. Broad / technical product — retain approved StudyFetch gold**

> Traded live fare recalculation for sub-second quotes by pre-caching pricing across 12 high-demand corridors; held fare variance within 4%, cut latency 70%, and recovered ~28K monthly rides.

**2. Analytics / diagnosis — new challenger**

> Diagnosed a fare-quote bottleneck where a 3.8s p95 hid behind a 1.3s average and drove 40% drop-off; pre-cached 12 high-demand corridors, holding fare variance within 4% while cutting latency 70% and recovering ~28K monthly rides.

Why both survive: slate 1 proves a conscious technical tradeoff at low reading cost;
slate 2 proves distribution-level diagnosis. They share a result but fund different
hiring questions and should never appear together on one page.

**3. Competitive strategy / executive communication — retain live PM incumbent**

> Linked 40% higher abandonment in Singapore and 2-3x higher peak-hour drop-offs to competitive app-switching triggered by quote delays; drove a cross-functional roadmap to cut quote times 70% and enable ~28K additional monthly rides.

Why it survives: it is the only sibling that makes market behavior and the resulting
cross-functional roadmap the proof. The user's fact instruction removes the old-label
hold; it remains a targeted strategy variant rather than the general default.

### Incumbent disposition map

| Incumbent ID | Decision | Destination / material reason |
|---|---|---|
| `pm/g-latency/strategic-exec` | **retain, priority 3** | Distinct competitive-strategy and executive-roadmap proof. |
| `pm/g-latency/revenue-case` | **replace** | Slate 2 adds the actual bounded-caching mechanism and keeps the diagnosis/outcome. |
| `pm/g-latency/throughput-engineering` | **replace** | Slate 1 makes the sacrificed live recalculation legible and preserves the 4% bound. |
| `pm/g-latency/cross-functional-drive` | **replace** | Generic “alignment/modernize workflows” is weaker than the actual caching decision in slate 2. |
| `pm/g-latency/profiling-analysis` | **replace** | Slate 2 preserves p95-versus-average diagnosis but names the concrete mechanism and tradeoff. |
| `canonical-v4/g-latency/throughput-engineering` | **replace** | “Improved scalability” is outcome-first vagueness; slate 1 states the decision and sacrifice. |
| `nonpm/g-latency/cluster-a-funnel-diagnostic` | **replace** | Canonical default uses the directly measured ~28K rides and names the caching tradeoff. |
| `nonpm/g-latency/cluster-a-workflow-diagnostic` | **replace** | Canonical default removes the annual-value conversion and replaces “slowest step” with the concrete caching decision. |
| `nonpm/g-latency/cluster-b-conversion-recovery` | **replace** | Canonical default preserves the realized ride outcome without a second Gojek dollar currency. |
| `nonpm/g-latency/cluster-b-pricing-flow-fix` | **replace** | Canonical default exposes the technical decision hidden by “removing lag.” |
| `G-LATENCY-amazon-accuracy-tradeoff` | **replace** | Explicit registry hold already records that slate 1 is more outsider-legible. |
| `G-LATENCY-studyfetch-readable-tradeoff` | **retain, priority 1** | Current broad-reader champion. |

---

## H-BATCHSHIFT

### Re-derived claim spines

1. **Enterprise-trial trigger spine:** Fortune 500 trials stalled on auditability →
   choose batch-first transactional execution over streaming speed → explicit failure
   boundaries/correctness → +45% stability and eight enterprise customers in 90 days.
2. **Platform tradeoff spine:** low-latency streaming could not provide verifiable
   correctness → make the execution-model tradeoff explicit → same outcome.

The “logging and monitoring requirements” variants are not a third H-BATCHSHIFT
spine. They are a neighboring observability story joined to the enterprise-customer
outcome.

### Recommended slate, in broad-default / use-case order

**1. Enterprise-trial trigger — canonical default**

> Drove Hevo 2.0's batch-first shift after Fortune 500 trials stalled on auditability; traded streaming speed for verifiable correctness and clear failure boundaries, improving stability 45% and onboarding 8 enterprise customers in 90 days.

**2. Short rendering of the same execution-model claim — retain StudyFetch gold and live exact match**

> Drove Hevo 2.0's shift to a batch-first transactional model, trading streaming speed for verifiable correctness and clear failure boundaries; improved platform stability 45% and enabled onboarding of 8 enterprise customers within 90 days.

These siblings share the same material claim; they are reviewed long/short renderings,
not distinct criterion proof. Keep two only because the first preserves the buyer/trial
trigger while the second is materially cheaper for platform-heavy pages.

### Incumbent disposition map

| Incumbent ID | Decision | Destination / material reason |
|---|---|---|
| `pm/h-batchshift/business-model-pivot` | **replace** | Slate 1 adds the trial trigger, explicit speed/correctness tradeoff, and failure boundaries. |
| `pm/h-batchshift/enterprise-trial` | **replace** | Slate 1 names the actual execution-model decision rather than “shifted priorities.” |
| `pm/h-batchshift/strategic-bet` | **retain, priority 2** | Exact text match to `H-BATCHSHIFT-studyfetch-verifiable-correctness`. |
| `pm/h-batchshift/segment-shift` | **replace** | Slate 2 removes the extra 120K scale currency and preserves the cleaner execution-model claim. |
| `pm/h-batchshift/reliability-outcome` | **retire** | No trigger, thin decision language, and two scale currencies; dominated by both recommended siblings. |
| `nonpm/h-batchshift/cluster-a-enterprise-deal-blocker` | **retire** | Monitoring-requirements mechanism is from the adjacent story; 12-customer claim also conflicts. |
| `nonpm/h-batchshift/cluster-a-buyer-signoff-blocker` | **retire** | Same story graft and 12-customer conflict. |
| `nonpm/h-batchshift/cluster-a-trust-infrastructure` | **retire** | Same story graft and 12-customer conflict; longest sibling without a new signal. |
| `nonpm/h-batchshift/cluster-a-objection-to-proof-surface` | **retire** | Same story graft and 12-customer conflict; “trust” is less precise than auditability. |
| `nonpm/h-batchshift/cluster-b-enterprise-readiness-shift` | **replace** | Slate 1 names the execution-model decision and consequence while keeping the 8-customer outcome. |
| `nonpm/h-batchshift/cluster-b-trust-surface-reset` | **retire** | Thin activity statement with no concrete mechanism; dominated by slate 1. |
| `H-BATCHSHIFT-amazon-trial-trigger` | **replace** | Canonical default preserves the same trigger, tradeoff, and result at lower reading cost. |
| `H-BATCHSHIFT-studyfetch-verifiable-correctness` | **retain, priority 2** | Current platform/execution champion. |

---

## Net slate

| Family | Recommended surviving variants | New exact challengers | Held claim families |
|---|---:|---:|---|
| G-SUPPLY | 4 | 3 | None; 1.5 minutes is locked |
| G-PRICING | 3 | 1 | None; 20+ / 9% / $3.2M is locked |
| G-LATENCY | 3 | 1 | None; ~28K rides is locked |
| H-BATCHSHIFT | 2 | 1 | None; 8 customers is locked |

All four former human decisions are resolved. The numbered slate order is a
broad-default/use-case routing order, not a universal quality rank. Canonical defaults
are explicit machine-readable fields; alternates cannot change the locked metric set.
