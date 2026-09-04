# Batch C — Hevo Monitoring, Intuit, and Optum variant audit

**Mode:** local reasoning only; no API calls; no live prompt/registry edits.
**Decision rule:** compare only within a hiring question. The incumbent wins a
tie. `replace` means a challenger creates a material causal/value gain with no
material loss; wording cleanup alone never qualifies. Slate order is a default
use-case ranking, not a claim that one variant is universally best across roles or
page budgets.

**Canonical collision decisions:** the eight cross-variant metric/scope choices
are now resolved in
[`CANONICAL_STORY_DECISIONS_2026-09-03.md`](CANONICAL_STORY_DECISIONS_2026-09-03.md).
This remains review-only; no live prompt or registry has been changed.

## Sources and boundary

Reviewed all 50 live selectable incumbents in
`resume/variants/live_prompt_variants.jsonl`, the six relevant records in
`resume/variants/approved_gold_variants.jsonl`, the PM reference-only siblings,
and:

- `docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_hevo_incident_intelligence.md`
- `docs/career_workbench/story_engine/stories/hevo_ai_monitoring.md`
- `docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_intuit_recovery_control_plane.md`
- `docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_optum_affordability_navigation.md`
- `docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_optum_provider_integration_factory.md`
- `docs/reference/STORY_BANK_RICH.md`
- `docs/variants/VARIANT_FINALS_v4.md`

Reference-only PM variants are evidence/comparators, not incumbents. No claim
from `profile_maxing_lab` was used as an independent fact source.

---

## H-MONITORING, including H-MONITORING-AI

### Claim spines

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `H-AI-BOUNDARY` | Can this person place AI at the right point in an operational workflow? | One connector failure created 40–60 symptom alerts and ~45 minutes of diagnosis → AI should synthesize evidence, not detect or auto-remediate → deterministic detection plus GenAI over a 20+ failure taxonomy produced one incident card → diagnosis fell below 5 minutes | trial-to-close use, SLA +30%, unverified adoption figures |
| `H-ENTERPRISE-EVIDENCE` | Can this person turn an internal tool into a buyer-facing product surface? | Evaluators relied on an internal debugging view → auditability/decision context was the real product need → audit-ready monitoring/run history → failure identification fell 40% across 120K+ pipelines | GenAI incident-card mechanics, SLA outcome |
| `H-OPERATOR-CONTEXT` | Can this person redesign an operating surface around the decision users must make? | On-call teams lacked failure and escalation context → decision context mattered more than more alerts → operator view exposed both in real time → time-to-insight ~40% and SLA +30% | trial-conversion claim, AI synthesis |

### Recommended slate, priority order

1. **`H-MONITORING-canonical-ai-boundary` — canonical challenger.** Use: default AI product, data-platform, and operational decision-support proof.
   > Shipped an AI monitoring surface that turned alert storms into single incident cards; kept detection deterministic and used GenAI over a 20+ failure taxonomy to rank recovery actions, cutting diagnosis from 45 to under 5 minutes across 120K+ pipelines.
   Default because it preserves the AI-boundary judgment, artifact, direct
   diagnosis outcome, and enterprise scale on one connected path.

2. **`H-MONITORING-studyfetch-ai-incident-cards` — retain exact.** Use: compact AI product rendering when the deterministic boundary is not a funded criterion.
   > Shipped an AI-powered monitoring surface to replace manual alert triage; used a GenAI synthesizer and a 20+ failure taxonomy to consolidate alert storms into single incident cards, cutting triage time from 45 to under 5 minutes across 120K+ pipelines.
   Compact alternate, not additive proof.

3. **`H-ENTERPRISE-EVIDENCE-audit-ready-run-history` — challenger, accept.** Use: enterprise product roles emphasizing buyer evidence, auditability, and evaluation workflows.
   > Noticed enterprise evaluators using an internal debugging view as trial evidence; rebuilt it as an audit-ready run history, cutting failure identification time 40% across 120K+ pipelines.
   Material win over the five live non-AI PM variants: removes unexplained “Job
   Monitoring,” makes buyer behavior the trigger, and closes on the rebuild’s
   directly matched operational result rather than implying trial conversion.

The operator-context sibling with `30% SLA` is retired as the default metric
representation. The direct 45-to-under-5-minute diagnosis result wins.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `pm/h-monitoring/trial-conversion` | replace | `H-ENTERPRISE-EVIDENCE-audit-ready-run-history`; incumbent joins operational improvement to “trial-to-close” without an attributable conversion result. |
| `pm/h-monitoring/debugging-reframe` | replace | Same challenger; internal name/opening is opaque and outcome chain is overpacked. |
| `pm/h-monitoring/feature-ownership` | replace | Same challenger; “needed … to close contracts” overstates the evidence, while the buyer-observation trigger is supported. |
| `pm/h-monitoring/customer-trust` | replace | Same challenger; generic “translated requirements” hides the scarce observation and artifact. |
| `pm/h-monitoring/reliability-product` | retire_dominated | Generic observability feature bundle; #1 proves the same reliability surface with a distinctive mechanism and stronger observed outcome. |
| `pm/h-monitoring-ai/ai-monitoring-product` | retain_exact | Exact approved gold #1. |
| `pm/h-monitoring-ai/ai-reliability-product` | replace | `H-MONITORING-canonical-ai-boundary`; incumbent says the synthesizer was “trained” on the taxonomy and hides the detector/synthesizer judgment. |
| `nonpm/h-monitoring/cluster-a-operator-decision-surface` | replace | `H-MONITORING-canonical-ai-boundary`; the direct diagnosis result is stronger and more causally matched than the 30% SLA sibling. |
| `nonpm/h-monitoring/cluster-a-trust-surface` | retire_dominated | Same facts as operator-decision-surface with less precise hiring question. |
| `nonpm/h-monitoring/cluster-a-workflow-visibility` | replace | Canonical #1 preserves the strongest diagnosis result and makes the AI boundary explicit. |
| `nonpm/h-monitoring/cluster-a-evaluation-surface` | retire_dominated | Despite its label, the text never names evaluation; duplicates the operator-context spine. |
| `nonpm/h-monitoring/cluster-b-incident-surface` | retire_dominated | Activity-first and generic; no judgment or causal trigger. |
| `nonpm/h-monitoring/cluster-b-alert-routing` | retire_dominated | Result-first construction but no counterfactual ownership; duplicates #4. |

**Gold disposition:** retain `H-MONITORING-studyfetch-ai-incident-cards` exactly.

**Resolved decision:** use the 45-to-under-5-minute diagnosis result, not the 30%
SLA sibling, in the canonical monitoring bullet. The audit-ready surface and AI
incident-card layer remain alternate framings and must not be stacked as two wins.

---

## I-BILLING / I-RECONCILIATION

### Claim spines

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `I-CHURN-ROADMAP` | Can this person find the true customer problem and change a roadmap? | Silent cancellations lacked the usual complaint/price signal → billing accuracy was a trust/revenue problem → cross-system reconciliation case presented to leadership → roadmap shifted from feature velocity to auditability | 10% renewal result unless using the reconciliation spine; incident response |
| `I-DATA-JOIN` | Can this person connect siloed data to surface a non-obvious business signal? | Retention and billing teams saw separate fragments → join billing events to subscription lifecycle → first cross-org analysis exposed invoice errors behind silent churn → accuracy was reframed as revenue protection and reconciliation was prioritized | 80K restored population, 10% renewal, incident mechanics |
| `I-RENEWAL-INTEGRITY` | Can this person build an operating mechanism that changes a commercial outcome? | Cross-system mismatches created renewal risk → treat integrity as a shared-system problem → five-system reconciliation model → accuracy restored for 80K+ businesses and renewals +10% | roadmap-presentation claim, 50K hidden-account aggregation |

### Recommended slate, priority order

1. **`I-BILLING-canonical-renewal-integrity` — canonical challenger.** Use: default product, strategy, and revenue-integrity proof.
   > Traced silent SMB cancellations to billing mismatches across five systems; built a reconciliation model for 80K+ businesses and a financial case that shifted the roadmap from feature delivery to billing integrity, lifting renewals 10%.
   Default because the five-system boundary and realized 10% renewal lift make
   the commercial consequence stronger than ending at the roadmap decision.

2. **`I-BILLING-studyfetch-cancellation-diagnosis` — retain exact.** Use: the same roadmap-pivot criterion under a compact two-line budget.
   > Traced SMB cancellations to billing accuracy failures, not product gaps; designed a cross-system reconciliation framework and presented the financial impact to senior leadership, securing a roadmap pivot from feature velocity to auditability.
   Same hiring question as #1, but the best two-line form when page cost matters.
   Treat #1/#2 as use-case alternatives, never additive proof.

3. **`I-DATA-JOIN-revenue-protection` — challenger, accept.** Use: analytics-led product discovery connecting siloed usage and commercial signals.
   > Joined billing-event logs with subscription lifecycle data to uncover invoice errors behind silent SMB cancellations; reframed accuracy as revenue protection and secured a roadmap shift from feature delivery to reconciliation.
   Materially distinct analytics/discovery proof. It exposes the scarce method that
   moved the decision; #1 instead emphasizes executive influence.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `pm/i-billing/churn-renewal` | replace | Canonical #1; mixes 50K diagnosis and 80K restoration populations without explaining them and lacks an actual churn/renewal outcome. |
| `pm/i-billing/trust-reliability` | retire_dominated | “Eliminated the billing-driven churn category” is broader than the evidence and combines diagnosis, build, and outcome without the decision mechanism. |
| `pm/i-billing/exec-presentation` | replace | Canonical #1 for general use or #2 under a two-line budget; the default adds the realized renewal consequence. |
| `pm/i-billing/roadmap-pivot` | replace | `I-DATA-JOIN-revenue-protection`; preserves its unique cross-org analysis and adds the resulting decision. |
| `pm/i-billing/financial-case` | retire_dominated | Same roadmap question as #1 with a generic “business impact case” and less visible judgment. |
| `nonpm/i-reconciliation/cluster-a-revenue-integrity-anchor` | replace | Canonical #1 keeps the five-system scope, adds the decision mechanism, and closes on the same 10% renewal outcome. |
| `nonpm/i-reconciliation/cluster-a-commercial-risk-diagnostic` | replace | Canonical #1; same evidence with weaker ownership. |
| `nonpm/i-reconciliation/cluster-a-cancellation-trigger` | replace | Canonical #1; duplicates the diagnostic and adds no separate hiring question. |
| `nonpm/i-reconciliation/cluster-b-data-consistency-framework` | retire_dominated | Omits the stronger 10% outcome available on the same path. |
| `nonpm/i-reconciliation/cluster-b-billing-backbone` | retire_dominated | Duplicates renewal-integrity anchor while adding unquantified escalation reduction. |

**Gold disposition:** retain `I-BILLING-studyfetch-cancellation-diagnosis` as the
compact alternate. The three-service Amazon gold no longer owns the default;
the five-system, 80K+, 10% renewal rendering is canonical.

**Reference-only reconciliation warning:** `pm/i-reconciliation/hidden-aggregate`
and `influence-without-authority` contain a separate 12-team / 50K-account /
3K-per-month story. Do not revive it from reference status until that cluster has a
canonical evidence source; it cannot be spliced into the 80K/10% bullet.

**Resolved decision:** use five systems, 80K+ businesses, and 10% renewals; retire
three billing services from the canonical story. The data-join story in
`STORY_BANK_RICH.md` has additional
14%/45-day/LTV details, but the adjacent provenance note labels those amplified;
the challenger deliberately does not use them.

---

## I-GOVERNANCE

### Claim spine

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `I-RISK-SEQUENCING` | Can this person improve delivery through governance rather than more capacity? | 20K+ backlog across 8 teams created delivery drag → work needed risk sequencing, not undifferentiated throughput → risk-tiered triage/governance model → throughput +25% | billing accuracy, incident-response team count |

### Recommended slate, priority order

1. **`I-GOVERNANCE-canonical-risk-sequencing` — canonical challenger.** Use: strategy and consulting roles testing non-obvious diagnosis and prioritization.
   > Reframed delivery drag as a sequencing problem across 8 teams; built a risk-tiered prioritization model for 20K+ issues that improved throughput 25%.
   Default and exclusive owner of the 8-team scope.

2. **`I-RISK-SEQUENCING-ops-action` — challenger, accept.** Use: program and operations roles emphasizing an owned governance mechanism and throughput.
   > Built a risk-tiered triage model for a 20K+ issue backlog across 8 teams, prioritizing highest-risk work and improving delivery throughput 25%.
   Distinct operations/PgM hiring question: direct operating artifact and outcome,
   without result-by-activity construction.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `nonpm/i-governance/cluster-a-sequencing-reframe` | replace | Canonical #1 removes method inventory while preserving diagnosis, 8-team scope, artifact, and 25% throughput. |
| `nonpm/i-governance/cluster-a-governance-diagnostic` | retire_dominated | Same hiring question and evidence as #1, with less specific judgment. |
| `nonpm/i-governance/cluster-b-throughput-governance` | replace | `I-RISK-SEQUENCING-ops-action`; challenger makes the artifact the owned action and names how it worked. |
| `nonpm/i-governance/cluster-b-governance-model` | replace | Same challenger; incumbent redundantly repeats governance/prioritization. |
| `nonpm/i-governance/support-only-risk-prioritization` | retire_dominated | Shorter, but loses both trigger/judgment and owned artifact; page cost alone cannot save it. |

**Resolved cross-family decision:** the 8-team scope belongs exclusively to this
20K+ backlog governance story and is prohibited in I-INCIDENT.

---

## I-INCIDENT

### Claim spines

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `I-PARALLEL-RECOVERY` | Can this person restructure execution under time pressure? | Lifecycle mismatch canceled 1,500+ subscriptions → sequential fix/validation was too slow → parallel engineering and validation across teams → recovery moved from days to hours | refund segmentation and account ledger details |
| `I-UNEVEN-RECOVERY` | Can this person make a safe decision when one rollback cannot serve every customer? | A script error left 1,500 businesses in different commercial states → blanket rollback was unsafe → shared account-state ledger with restore/rebuild/refund cohorts → each account received a bounded recovery path | days-to-hours claim, 20K backlog, 8-team count |
| `I-RECOVERY-CONTROL` | Can this person create a cross-functional operating mechanism? | Engineering, Finance, and Support had incompatible account states/promises → one source of truth was required → ledger assigned state, owner, next action, and promise time → functions aligned on restore/rebuild/refund execution | generic “trust restored,” soft 72-hour/10-day results |

### Recommended slate, priority order

1. **`I-INCIDENT-canonical-parallel-recovery` — canonical challenger.** Use: incident leadership and operations roles emphasizing execution speed under pressure.
   > Led recovery after billing-state errors canceled subscriptions for 1,500+ businesses; ran fix-writing and QA validation in parallel, cutting resolution from days to hours.
   Default because the direct speed consequence remains while the duplicated
   8-team scope is removed.

2. **`I-UNEVEN-RECOVERY-cohort-ledger` — challenger, accept.** Use: product judgment roles testing safe segmentation when one rollback cannot serve every customer.
   > Rejected a blanket rollback after a billing failure canceled subscriptions for 1,500+ businesses; built a shared account-state ledger with restore, rebuild, and refund cohorts so Engineering, Finance, and Support could recover each account safely.
   Materially distinct judgment-under-ambiguity proof. It wins on decision quality
   and is supported by the on-file canonical story.

3. **`I-RECOVERY-CONTROL-state-owner-promise` — challenger, accept.** Use: cross-functional program roles emphasizing recovery controls, ownership, and coordination.
   > Built one recovery ledger for 1,500+ affected businesses, assigning each account a state, owner, next action, and promise time; aligned Engineering, Finance, and Support on restore, rebuild, or refund paths.
   Strongest non-PM program/operations form. Different hiring question from #2:
   operating-system design rather than rollback judgment.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `pm/i-incident/financial-risk` | replace | Canonical #1; incumbent centers “caught” and ends in generic containment without recovery outcome. |
| `pm/i-incident/crisis-management` | replace | Canonical #1 adds the billing-state trigger, concise parallelization, and days-to-hours result without duplicating 8-team scope. |
| `pm/i-incident/churn-defense` | retire_dominated | Generic risk framing; no owned operating artifact and “within hours” is less specific than #1. |
| `pm/i-incident/stakeholder-coord` | retire_dominated | Activity inventory without a matched outcome. |
| `nonpm/i-incident/cluster-a-recommendation-brief` | replace | #3; the live ledger/control plane is stronger and more operational than a brief. |
| `nonpm/i-incident/cluster-a-account-priority-brief` | replace | #3; “ranked accounts by urgency” is weaker than explicit state/owner/action/promise controls. |
| `nonpm/i-incident/cluster-a-incident-synthesis` | retire_dominated | “One recovery recommendation” erases the core fact that recovery could not be uniform. |
| `nonpm/i-incident/cluster-a-executive-recommendation` | retire_dominated | Same uniform-plan error; no distinct hiring question. |
| `nonpm/i-incident/cluster-b-incident-command` | retire_dominated | “Restoring trust with minimal disruption” is unmeasured and mechanism-free. |
| `nonpm/i-incident/cluster-b-cross-functional-coordination` | replace | Canonical #1; days-to-hours is the direct result of the parallel fix-and-validation mechanism, so the 7-day sibling is retired. |

**Gold disposition:** the Amazon incident gold is displaced because it assigns the
8-team scope to this story. The canonical parallel-recovery rendering keeps the
measured outcome without duplicating governance evidence.

**Resolved decision:** use days-to-hours and retire the 7-day sibling. Do not add
the 8-team scope; it is locked to I-GOVERNANCE.
The additional 92%/72h, 46%, <2% churn, and 4h→35m figures are not needed in this
slate and should not be recombined into these variants.

---

## O-AFFORDABILITY

### Claim spines

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `O-SAFE-ACTION` | Can this person turn an AI score into a safe, adoptable decision product? | Clinicians resisted a standalone prediction → the product needed bounded action and an exit → flag-and-suggest, navigator review, 90-day automatic stop → clinical pilot approval | hackathon prestige, detailed feature list, soft pilot results |
| `O-INTERVENTION-TIMING` | Can this person find the product insight behind an ML opportunity? | Post-claim outreach arrived after the care decision → prediction mattered only before the appointment → pre-appointment risk signals plus tiered intervention path → product advanced to pilot | 90-day stop rule, hackathon as lead |
| `O-PROTOTYPE-EVALUATION` | Can this person rapidly turn an ML idea into a testable workflow? | Affordability opportunity needed a concrete prototype → define inputs, evaluation metrics, and deployment workflow with clinicians → ML affordability engine → pilot approval | clinical-risk reframe, detailed interventions |
| `O-HACKATHON` | Can this person create a compelling AI solution quickly? | Competitive innovation prompt → high-OOP risk routed to lower-cost pathways → AI workflow → global hackathon win and pilot | responsible-AI guardrails |

### Recommended slate, priority order

1. **`O-SAFE-ACTION-flag-suggest-stop` — challenger, accept.** Use: responsible-AI and healthcare product roles emphasizing human review and bounded rollout.
   > Won pilot approval after clinicians pushed back on a standalone affordability score; reframed it as flag-and-suggest with navigator review and a 90-day automatic stop if outcomes trailed control.
   Material win for responsible-AI/healthcare roles: the scarce atom is the risk
   design that changed the organizational decision, not “used AI.”

2. **`O-INTERVENTION-TIMING-pre-appointment` — challenger, accept.** Use: product discovery roles emphasizing intervention timing and action-path design.
   > Reframed affordability support from post-claim outreach to pre-appointment action; built a risk model with a tiered path from in-app cost prompts to navigator or social-work support, advancing the product to pilot.
   Material win over all generic workflow incumbents: names the timing insight and
   the action architecture that answers it.

3. **`O-AFFORDABILITY-prototype-clinical-approval` — challenger, accept.** Use: builder and junior AI-product roles emphasizing rapid prototyping and evaluation design.
   > Prototyped an ML-based affordability engine with feature inputs, evaluation metrics and a deployment workflow; secured pilot approval from clinical leaders through Optum's global innovation program.
   Preserves the rapid-prototyping/evaluation signal while replacing a vague
   stakeholder reference with the actual decision owners and closing on approval.

4. **`nonpm/o-affordability/cluster-b-hackathon-impact` — retain exact.** Use: innovation and early-career roles where competitive achievement is a funded criterion.
   > Won Optum's global hackathon by designing an AI affordability workflow that flagged high out-of-pocket risk and routed members toward lower-cost care pathways, advancing to pilot.
   Compact and materially distinct competitive-achievement proof; use only when that
   hiring question matters.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `nonpm/o-affordability/cluster-a-ai-workflow-design` | replace | #2; incumbent names workflow inputs/outputs but not the timing insight that makes them valuable. |
| `nonpm/o-affordability/cluster-a-pilot-decision-workflow` | replace | #1; “guided members” is generic while guarded human review/exit explains why approval happened. |
| `nonpm/o-affordability/cluster-a-decision-workflow` | replace | #2; same generic workflow with no product judgment. |
| `nonpm/o-affordability/cluster-a-adoption-aware-workflow` | replace | #1; text claims adoption awareness but contains no adoption mechanism. |
| `nonpm/o-affordability/cluster-b-hackathon-impact` | retain_exact | Priority #4. |
| `nonpm/o-affordability/cluster-b-ai-solution-delivery` | retire_dominated | Same hackathon/pilot claim as retained incumbent with a weaker opener. |

**Gold disposition:** keep `O-AFFORDABILITY-studyfetch-ml-prototype` frozen inside
the historical StudyFetch fixture; use the new challenger ID for future selection so
the stable gold record is not silently reworded.

**Reference-only warning:** the six PM siblings are prohibited references, not live
incumbents. `responsible-ai`, `business-case-ai`, and `tiered-intervention` each
contain part of #1/#2, but none exposes the complete decision edge; do not revive
them by default.

**Cross-track consistency:** on-file mechanisms are admissible; their prior “soft”
labels do not block #1/#2. Hackathon and pilot recur across the family, so assembly
must still choose variants by distinct hiring question rather than stack multiple
forms of the same pilot-approval outcome.

---

## O-PROVIDER

### Claim spines

| Spine | Hiring question | Trigger → judgment → artifact → consequence | Excluded adjacent atoms |
|---|---|---|---|
| `O-INTEGRATION-FACTORY` | Can this person productize repeated integrations instead of shipping another one-off? | Three integrations failed late → ~80% of translation was common, 20% genuine variation → reusable mapping core with typed exceptions → custom engineering 12–14 weeks→2 and onboarding 6 months→10 weeks | $20M/50M context, member-access reframe |
| `O-CLINICAL-OWNERSHIP` | Can this person resolve a cross-functional ownership gap in a regulated product? | Schema disputes encoded contested clinical meaning and lacked an escalation owner → integration was a coverage/clinical-definition problem → Clinical Operations co-owned certification → first dispute resolved in 3 days and onboarding completed in 10 weeks | Kafka inventory, $20M context |
| `O-TECHNICAL-DIAGNOSIS` | Can this person unblock a complex customer integration? | Provider onboarding stalled on XML/REST mismatch → transformation contract was the blocker → custom transformation layer → onboarding 6 months→10 weeks | 80/20 reuse, market sizing |
| `O-MARKET-GAP` | Can this person translate network data into an expansion recommendation? | Coverage gaps existed across a 50M-member footprint → prioritize underserved markets → provider-expansion recommendation → ~$20M+ annual opportunity sized as context | personal revenue attribution, technical integration mechanism |

### Recommended slate, priority order

1. **`O-INTEGRATION-FACTORY-reusable-core` — challenger, accept.** Use: platform product roles emphasizing productization and reusable integration architecture.
   > Found 80% of transformation logic repeated across three failed provider integrations; built a reusable mapping core with typed exceptions, cutting custom engineering from 12–14 weeks to 2 and total onboarding from 6 months to 10 weeks.
   Material platform win over the one-off schema variants: repeated-failure diagnosis,
   reusable artifact, and two matched cycle-time outcomes without repeating the same
   80/20 idea in both diagnosis and solution language.

2. **`O-CLINICAL-OWNERSHIP-coverage-escalation` — challenger, accept.** Use: regulated client-delivery roles emphasizing cross-functional ownership and member access.
   > Reframed a stalled provider integration as a member-access gap, bringing Clinical Operations in to own disputed care definitions; resolved the first schema dispute in 3 days and completed onboarding in 10 weeks versus 6 months.
   Material strategy/client-delivery win: shows the non-technical ownership problem
   that the integration solved.

3. **`O-PROVIDER-amazon-schema-integration` — retain exact.** Use: customer-technical roles emphasizing integration diagnosis and delivery acceleration.
   > Unblocked a stalled provider integration by diagnosing a schema mismatch between legacy XML and Optum's REST APIs; designed a custom transformation layer that cut onboarding time from 6 months to 10 weeks.
   Best compact technical/customer-solution proof. #1 is richer but longer, so it
   does not Pareto-replace this gold for every page budget or hiring question.

4. **`O-MARKET-GAP-member-opportunity` — challenger, accept.** Use: strategy and market-sizing roles emphasizing opportunity diagnosis and recommendation.
   > Mapped provider-network gaps across a 50M-member footprint to identify underserved markets and shape a provider-expansion recommendation around a ~$20M+ addressable annual revenue opportunity.
   Distinct strategy/market-sizing question with healthcare-correct terminology;
   $20M remains opportunity context, never personal generated revenue.

### Every live incumbent

| Incumbent ID | Decision | Material reason / replacement |
|---|---|---|
| `nonpm/o-provider/cluster-a-expansion-constraint` | replace | #4; “main expansion constraint” is broader than evidence and contains a broken `provider- expansion` phrase. |
| `nonpm/o-provider/cluster-a-market-entry-recommendation` | replace | #4 preserves the distinct market-sizing proof and corrects “user” to healthcare “member.” |
| `nonpm/o-provider/cluster-a-segment-prioritization` | retire_dominated | Same market-gap spine as #4 with no additional attributable outcome. |
| `nonpm/o-provider/cluster-b-network-integration` | replace | Cleared gold #3; incumbent supplies no mechanism and implies direct extension across all 50M users. |
| `nonpm/o-provider/cluster-b-access-expansion` | replace | #2; generic “expanded” claim hides both artifact and ownership mechanism. |
| `nonpm/o-provider/support-only-market-gap-sizing` | retire_dominated | Shorter but removes the recommendation/decision, leaving analysis activity only. |

**Gold disposition:** retain `O-PROVIDER-amazon-schema-integration` exactly.

**Reference-only warning:** the PM `platform-scale` variant says “enabling $20M+ in
incremental annual revenue,” while the NONPM pool correctly says addressable
opportunity and canonical evidence calls it program context. Keep all direct personal
revenue forms prohibited. `gtm-execution` is mechanism inventory without the 80/20
or Clinical Ops insight.

**Human decision / inconsistency:** the 6-month→10-week result appears in both the
one-off integration and factory narrative. Do not stack both on one page or imply
that the full onboarding result repeated across multiple providers unless a
next-integration result is separately established.

---

## Cross-family decisions

1. **Intuit “8 teams” is now locked to governance.** I-INCIDENT may name functions
   or cross-functional execution, but not that number.
2. **Intuit billing is now locked to five systems / 80K+ businesses / 10% renewal.**
   Three billing services and the separate 12-team/50K-account reference are not
   interchangeable scale atoms.
3. **Hevo represents an evolution, not two independent wins.** The audit-ready
   monitoring surface and AI incident-card layer may coexist as variants, but should
   not occupy two bullets on one resume without explicit evidence that they are
   distinct contributions.
4. **Optum scale is context-sensitive.** 50M members and ~$20M opportunity describe
   program/network context. Attributable outcomes are integration mechanism,
   cycle-time, clinical ownership, prototype, and pilot decision.
5. **On-file mechanisms are admissible.** Prior counterfactual/soft labels do not
   independently block the cohort ledger, 90-day stop, or reusable integration
   factory. Human gates are reserved for actual cross-sibling conflicts or
   recombination risk.

## Batch result

- **Exact recommended slates:** H-MONITORING 3, I-BILLING 3,
  I-GOVERNANCE 2, I-INCIDENT 3, O-AFFORDABILITY 4,
  O-PROVIDER 4.
- **Live behavior:** unchanged.
- **Promotion rule:** accepted challengers pass the material audit and are eligible
  for the normal admission path. Holds remain only where an actual sibling conflict
  or recombination risk is unresolved.
