# Batch A material-variant challenge: FlairX, Fluo, projects, and Hevo flex

**Date:** 2026-09-03
**Scope:** 44 live-selectable incumbents across 12 semantic families
**Status:** local reasoning audit only; no live prompt, registry, or generator behavior changed

## Decision rule

Each family was rebuilt from its canonical story evidence where available and otherwise from
the prompt-owned fact block. The recommended slate contains only materially different claim
spines. An incumbent wins a tie. A replacement is proposed only when it improves at least one
material dimension without losing criterion proof, stakes, ownership, outcome quality,
outsider legibility, or fact containment. Conflicting facts remain human decisions.

The requested 2–4 target is treated as a ceiling and normal range, not a quota. Numbering only
enumerates a slate; it does not declare one universal winner. Each sibling has an explicit
`use_case` in the machine-readable sibling, and the selector chooses by the hiring question.
The highest-risk distinctions are repeated inline below. H-REGRESSION funds one strong shipping
variant. P-GRAB funds none until its story is documented. Padding either family to two would
violate the admission gate.

Decision labels:

- **retain**: exact incumbent remains in the recommended slate.
- **replace**: use the named exact challenger instead.
- **retire**: dominated rendering; no distinct hiring question survives.
- **hold**: potentially useful, but a fact or ownership decision must be resolved first.

---

## 1. F-AVATAR

### Highest-value claim spines

1. **Dependency strategy:** vendor cap breaks enterprise-length interviews → rendering is a
   product dependency, not procurement → make providers swappable and move to usage pricing →
   restore hour-long rounds and cut cost per minute 70%.
2. **Build-versus-buy judgment:** vendor failure invites an internal build → video research
   would starve the real roadmap → reject the build after a GPU/latency/maintenance audit →
   protect roadmap velocity while preserving vendor independence.
3. **Candidate-trust engineering:** replacement provider lacks anti-fraud controls → protect
   integrity without degrading the interview → bound gaze/voice telemetry by CPU and latency →
   keep the control usable on low-spec devices.

### Recommended slate, criterion-conditional

1. `F-AVATAR-shared-provider-unit-economics` **retain known gold**
   **Use case:** enterprise product strategy, dependency risk, and unit economics.
   > Rebuilt AI interview rendering onto swappable providers after a vendor's 20-minute cap ended hour-long enterprise rounds mid-call; replaced a monthly platform fee with usage-only pricing, cutting cost per minute 70%.

2. `pm/f-avatar/technical-diligence` **retain exact**
   **Use case:** build-versus-buy and technical product judgment.
   > Audited MuseTalk/EchoMimic across GPU cost, VRAM, latency, plus maintenance burden; rejected an in-house build to protect core roadmap velocity.

3. `f-avatar-low-spec-antifraud-tradeoff` **new challenger**
   **Use case:** AI product reliability and user-experience tradeoff.
   > Shipped anti-fraud controls that stayed viable on low-spec candidate devices by combining gaze, face-mesh and voice signals under 8% CPU and 150ms interruption latency.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/f-avatar/platform-turnaround` | replace with `F-AVATAR-shared-provider-unit-economics` | Gold closes the dependency claim with the user-visible broken-round trigger and an attributable 70% cost outcome; the incumbent stops at shipping infrastructure. |
| `pm/f-avatar/unit-economics` | retire | Same pricing proof is carried with higher stakes and causal closure by the gold variant. The `$0.009` fallback is secondary currency. |
| `pm/f-avatar/platform-resilience` | retire | Provider routing is a partial rendering of the dependency spine and has no measured consequence; gold preserves the same ownership with better stakes and outcome. |
| `pm/f-avatar/technical-diligence` | retain | Distinct build-versus-buy judgment not preserved by the gold variant. |
| `pm/f-avatar/trust-performance` | replace with `f-avatar-low-spec-antifraud-tradeoff` | Challenger preserves shipment and every verified constraint while replacing internal product naming and feature inventory with the candidate-experience tradeoff those facts prove. |

### Human decisions

- None. User-confirmed that the FlairX stories shipped and the claims are verified; stale
  counterfactual labels are not treated as evidence against that direct confirmation.

---

## 2. F-CEIPAL

### Highest-value claim spines

1. **Product judgment under a vendor constraint:** duplicate ATS work threatens the flagship
   account → Ceipal can supply jobs and candidates but cannot accept FlairX scores → ship the
   useful import path first → remove roughly 80% of re-entry and retain the account.
2. **Ecosystem conversion:** a customer-specific integration can become a public product →
   launch the supported import path on Ceipal's Marketplace → open an ATS-based inbound channel.
3. **Data-contract ownership:** Ceipal payloads do not match FlairX's model → specify decoding,
   normalization, and attribution → create clean, auditable imported records.
4. **Integration reliability:** retries, key rotation, and timezones can silently corrupt syncs →
   design idempotency and explicit failure detection → keep candidate state trustworthy.

### Causal repair of the rejected combined challenger

The previous challenger failed the one-argument, outcome-closure, outsider-legibility, and
low-cognitive-load gates. `Saved` asserted the result before showing ownership. “Pull-first MVP”
did not explain what shipped, “duplicate work” did not identify what recruiters repeated, and the
Marketplace channel arrived as a second outcome with no visible connection to account retention.

These are the three strongest complete renderings, ordered by use case. The first and third fund
different hiring questions and survive; the second is a readable customer-workflow alternative
but is dominated by the first because it loses the explicit re-scoping decision.

1. **General PM, prioritization, and product judgment — selected default**

   > Re-scoped FlairX's Ceipal integration after its API blocked score write-back, automating job and candidate imports to eliminate ~80% of recruiters' duplicate entry while retaining FlairX's highest-volume account.

2. **Customer workflow and enterprise adoption — considered, not admitted**

   > Shipped direct Ceipal job and candidate imports despite the API rejecting FlairX screening results; eliminated ~80% of recruiter re-entry, retaining FlairX's highest-volume account.

3. **Platform ecosystems, partnerships, and GTM — selected specialist**

   > Converted a customer-specific Ceipal integration into a public Marketplace product by shipping job and candidate imports despite blocked score write-back, opening FlairX's first ATS-based inbound channel.

### Recommended slate, criterion-conditional

1. `f-ceipal-pull-first-account-retention` **new challenger, best general version**
   > Re-scoped FlairX's Ceipal integration after its API blocked score write-back, automating job and candidate imports to eliminate ~80% of recruiters' duplicate entry while retaining FlairX's highest-volume account.

2. `f-ceipal-marketplace-product-channel` **new challenger, ecosystem specialist**
   > Converted a customer-specific Ceipal integration into a public Marketplace product by shipping job and candidate imports despite blocked score write-back, opening FlairX's first ATS-based inbound channel.

3. `pm/f-ceipal/technical-integration` **retain exact**
   > Specified a translation layer for Ceipal's Base64 entity IDs and compound fields, converting inconsistent ATS payloads into clean, attributable FlairX records.

4. `pm/f-ceipal/marketplace-gtm` **retain exact**
   > Designed idempotent Ceipal webhooks with duplicate-event caching and key-rotation alerts, preventing retry storms or silent authentication failures from corrupting candidate syncs.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/f-ceipal/ecosystem-platform` | replace with `f-ceipal-marketplace-product-channel` | Challenger gives the public Marketplace launch one matched outcome: converting a customer-specific build into an ATS-based inbound channel. |
| `pm/f-ceipal/mvp-tradeoff` | replace with `f-ceipal-pull-first-account-retention` | Challenger translates “pull-first” into the actual scope decision, jobs and candidates first, then closes on account retention. |
| `pm/f-ceipal/customer-adoption` | replace with `f-ceipal-pull-first-account-retention` | Challenger identifies the blocked half, the shipped half, the work removed, and the account outcome in one linear chain. |
| `pm/f-ceipal/technical-integration` | retain | The proposed rewrite would improve the auditability close but lose the exact Base64 earned detail; that is a material tradeoff, so the incumbent wins. |
| `pm/f-ceipal/marketplace-gtm` | retain | The label is wrong, but labels are metadata rather than sentence quality. Adding timezone safeguards would lose the incumbent's duplicate-cache mechanism; the incumbent wins the wording tie. |

### Human decisions

- None. User-confirmed that the FlairX stories shipped and the claims are verified.

---

## 3. F-ENTERPRISE

### Highest-value claim spines

1. **Enterprise objection to product wedge:** Genpact will not outsource final rounds → the
   policy objection is a workflow gap → build a client-run scheduling and AI-evaluation suite →
   ship in two weeks and clear the workflow blocker.
2. **Unstructured-to-structured AI workflow:** executives reject questionnaires → preserve a
   natural interview → convert transcripts into evidence-linked competency scores.
3. **Scheduling reliability:** declines and replacements can silently drop candidates → define
   the failure-state contract → keep interviews live until a replacement is confirmed.

### Recommended slate, criterion-conditional

1. `F-ENTERPRISE-amazon-deal-impact` **retain known gold**
   > Unblocked $1.2M of enterprise pilots after Genpact refused to outsource final-round interviews; reframed the policy objection as a workflow gap & led engineering and design to ship M365 panel scheduling with transcript-grounded AI scoring in 2 weeks.

2. `F-ENTERPRISE-studyfetch-design-delivery` **retain known gold**
   > Turned Genpact's ban on outsourced final rounds into FlairX's client-run interview suite; wireframed privacy-safe M365 scheduling and transcript-grounded AI-scoring flows, then led product and engineering to ship the suite in 2 weeks.

3. `pm/f-enterprise/ai-workflow` **retain exact**
   > Designed a split-mode interview experience that let executives skip rigid questionnaires while a post-call GenAI pipeline converted transcripts into evidence-linked competency scores.

4. `pm/f-enterprise/workflow-reliability` **retain exact**
   > Defined 32 failure states for global panel scheduling, from Outlook declines to quorum fallbacks; kept live interviews intact until replacement slots were confirmed.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/f-enterprise/zero-to-one` | replace with `F-ENTERPRISE-amazon-deal-impact` | Known gold preserves the objection, reframe, team ownership, artifacts, and two-week shipment while adding the verified enterprise-pilot outcome. |
| `pm/f-enterprise/enterprise-discovery` | retire | Same wedge spine without shipment, team ownership, or a concrete outcome. |
| `pm/f-enterprise/ai-workflow` | retain | Distinct AI product judgment around unstructured executive interviews. |
| `pm/f-enterprise/workflow-reliability` | retain | Distinct reliability/requirements proof with a directly matched operational consequence. |
| `pm/f-enterprise/enterprise-platform` | retire | Inventory of suite components; no dominant decision or attributable consequence. |

### Human decisions

- None. User-confirmed fact spine: Akshat designed the mocks/flows for all FlairX stories, a
  designer may have applied final visual touchups, all shipped, and the quantified claims are
  verified. The leadership and hands-on-design siblings remain separate because they prove
  materially different hiring questions.

---

## 4. F-OPS

### Highest-value claim spines

1. **Influence without authority:** commercial context is founder-held because trust, not
   tooling, is the constraint → earn permission incrementally → create self-serve visibility
   without routing routine decisions through the CEO.
2. **Commercial data product:** verbal service-mix estimates cannot support scale → map product
   events into a split HubSpot model → give Product and GTM one live revenue/fulfillment view.
3. **Enterprise diligence:** buyers require delivery evidence → turn operating telemetry into
   procurement-ready proof → replace verbal estimates with defensible service history.
4. **Voice-of-customer loop:** objections live in email → normalize them into account timelines →
   make customer evidence queryable for roadmap and deal decisions.

### Recommended slate, criterion-conditional

1. `f-ops-ceo-routing-removal` **new challenger**
   **Use case:** operating-model change and organizational leverage.
   > Removed the CEO as the routing point for routine account decisions by converting founder-held deal context into self-serve HubSpot workflows for Product and GTM.

2. `f-ops-commercial-data-spine` **new challenger**
   **Use case:** RevOps data product and cross-functional decision visibility.
   > Built FlairX's first commercial data spine by mapping backend product events into HubSpot and separating AI-screening usage from expert services, giving Product and GTM one live view of revenue and fulfillment.

3. `f-ops-diligence-evidence` **new challenger**
   **Use case:** enterprise diligence and commercial enablement.
   > Turned live usage and fulfillment data into diligence evidence for Genpact and L&T, replacing founder-held estimates with defensible views of service mix and delivery history.

4. `pm/f-ops/feedback-system` **retain exact**
   **Use case:** voice-of-customer operations and roadmap evidence.
   > Mapped customer emails, objections, and feature requests into account timelines, creating a queryable voice-of-customer system for roadmap plus GTM decisions.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/f-ops/commercial-ops` | replace with `f-ops-commercial-data-spine` | Challenger names the decisive service split and closes on the users' shared operating view. |
| `pm/f-ops/data-product` | replace with `f-ops-commercial-data-spine` | Challenger adds event-driven ownership and revenue/fulfillment use without losing the shared-source-of-truth claim. |
| `pm/f-ops/influence-without-authority` | replace with `f-ops-ceo-routing-removal` | Challenger makes the material operating change the subject. It preserves the founder-held constraint and self-serve mechanism; “earned trust” is valid interview texture but not stronger resume currency than removing the decision bottleneck. |
| `pm/f-ops/gtm-enablement` | replace with `f-ops-diligence-evidence` | Challenger names the evidence source and removes vague “defensible views of capacity.” |
| `pm/f-ops/feedback-system` | retain | Distinct closed qualitative-data artifact; none of the other slates proves voice-of-customer infrastructure. |

### Human decisions

- None. The recommended variants do not claim role-based access or that the diligence artifact
  independently caused pilot closure.

---

## 5. F-SOURCING

### Highest-value claim spines

1. **Customer discovery to product:** recruiters rebuild criteria FlairX already owns → make
   the search prefilled and evidence-grounded → hand engineering an end-to-end sourcing surface.
2. **Architecture boundary:** one request hides inbound distribution and outbound discovery →
   separate them and keep matching intelligence in-house → reduce build-versus-rent to raw data.
3. **Distribution unblock:** Apply Connect is uneconomic → find the Basic Jobs XML path → secure
   approval for automated posting without client Page authorization.
4. **Honest unit economics:** a 25× headline ignores contact cost → correct the unit to shortlisted
   candidate and design preview-before-unlock → recommend against the honest 2.3× comparison.

### Recommended slate, criterion-conditional

1. `pm/f-sourcing/partnership-gtm` **retain exact**
   **Use case:** partnerships, distribution, and GTM unblock.
   > Secured LinkedIn Basic Jobs XML approval after Apply Connect proved uneconomic, opening automated job distribution without client Page authorization or webhook dependencies.

2. `pm/f-sourcing/build-vs-rent` **retain exact**
   **Use case:** platform architecture and build-versus-rent judgment.
   > Split one sourcing request into inbound distribution and outbound discovery; kept matching intelligence in-house while narrowing build-vs-rent to raw candidate data.

3. `pm/f-sourcing/unit-economics` **retain exact**
   **Use case:** unit economics, intellectual honesty, and preview-before-purchase design.
   > Corrected Coresignal economics from a headline 25× advantage to an honest 2.3× per shortlisted candidate; designed preview-before-unlock controls around the real cost driver.

4. `pm/f-sourcing/product-discovery` **retain exact**
   **Use case:** customer research and recruiter-workflow insight only; never the universal FlairX lead.
   > Found recruiters manually rebuilding criteria FlairX already owned; turned each JD, questionnaire, and rubric into a prefilled search plus evidence-grounded candidate ranking.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/f-sourcing/product-discovery` | retain | Best customer-workflow insight; prefilled criteria and evidence-grounded ranking are the counterfactual artifact. |
| `pm/f-sourcing/zero-to-one` | retire | Splices discovery, vendor economics, and distribution into one sentence; the outcome does not close one claim spine. |
| `pm/f-sourcing/build-vs-rent` | retain | Distinct architecture and make-versus-buy judgment. |
| `pm/f-sourcing/unit-economics` | retain | User-confirmed on-file claims are true. It is the family's strongest unit-economics and self-correction proof and does not duplicate the architecture or distribution siblings. |
| `pm/f-sourcing/partnership-gtm` | retain | Distinct, closed distribution outcome with a named constraint and approval path. |

### Human decisions

- None. The user's direct confirmation that on-file claims are true governs over the stale
  counterfactual labels. Keep `25×` and `2.3×` together because they measure different units;
  never present `25×` alone as the final economics.

---

## 6. FLUO

### Highest-value claim spines

1. **Timing and institutional distribution:** Fluo cannot beat peer trust after arrival → the
   product must acquire pre-arrival → use the university office already running this workflow →
   secure a USC partnership.
2. **Closed discovery loop:** students understand live offers when surfaced, but redemption is
   low → separate awareness from demand → triangulate interviews with usage and design a cheaper
   receipt-verified retest.
3. **High-stakes proprietary housing:** students choose five-figure leases sight unseen → generic
   listings cannot supply campus-specific safety and pricing context → build the local evidence
   surface competitors cannot scrape.
4. **Fintech product judgment:** an instant credit line would select for students with the least
   repayment capacity → use settling evidence over time → stage the product from secured card
   to unsecured credit instead of underwriting on nothing.

### Recommended slate, criterion-conditional

1. `FL-INSTITUTIONAL-amazon-inline-prearrival` **retain known gold**
   > Concluded Fluo could not win a student after arrival, since arrivals trust peers over an app; closed a USC program office partnership as the pre-arrival acquisition channel.

2. `FL-FIELD-VALIDATION-studyfetch-closed-loop` **retain known gold**
   > Interviewed 60 new and returning students at a student-housing move-in near USC and found that live offers made sense once surfaced but were difficult to discover; confirmed the pattern in usage data, with just 3 of 20 spots claimed on Fluo's first merchant offer, then separated awareness from demand and designed a receipt-verified retest.

3. `fluo-proprietary-housing-evidence` **new challenger**
   > Built a housing surface for students choosing leases sight unseen, combining campus patrol-zone coverage with per-ring rent benchmarks across a $1,028 to $3,750 monthly range that generic listing sites could not supply.

4. `fluo-credit-adverse-selection-ladder` **new challenger**
   > Redirected Fluo's proposed $5,000 instant credit line into a secured-card-to-unsecured-credit ladder after showing demand concentrated among students with the least repayment capacity under F-1 work limits.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/fluo/fluo-product-system` | retire | Real zero-to-one work, but dependency mechanics and build counts are lower-stakes than the four funded Fluo signals. Preserve in story evidence, not the default small slate. |
| `pm/fluo/fluo-data-platform` | retire | The build is real, but 31 employers, 8,145 postings, endpoint disclosure, and a proposed calibration still end on inputs and a future study. Even the stronger strategic rendering, repositioning Fluo away from a generic job board and toward sponsorship evidence, proves feasibility rather than a consequential user or business result. The credit-product decision adds materially higher stakes and founder-level product judgment, so this data-feed story leaves the core shipping slate. |
| `pm/fluo/fluo-roadmap-partnership` | replace with `FL-INSTITUTIONAL-amazon-inline-prearrival` | Gold is the same spine with cleaner outsider orientation and a more precise institutional outcome. |
| `pm/fluo/fluo-founder-execution` | retire | Engagement inventory with no dominant decision or attributable result. |

### Human decisions

- Partnership is confirmed only at program-office altitude. Keep the exact office,
  counterparty, scope, date, and written status out until resolved.
- The field-validation variant deliberately says “student-housing move-in near USC,” not
  “Lorenzo,” because the location name is not legible to an outside reader.

---

## 7. P-FOUNDER

### Highest-value claim spines

1. **Segment sequencing:** undifferentiated early adoption → benchmark competitors and clarify
   target customers → decide which customer segments to pursue first → sequence GTM before the
   acquisition.
2. **Positioning:** unclear market position → benchmark alternatives and clarify target customer →
   refine the commercial position and adoption plan.

The on-file sentences are admissible. They still fund only two materially different claims;
there is no adopted-decision or attributable-outcome detail that would justify a stronger
challenger.

### Recommended slate, criterion-conditional

1. `nonpm/p-founder/segment-prioritization` **retain exact**
   > Advised a cloud startup founder on which customer segments to prioritize first; benchmarked competitors, clarified target customers, and sequenced the go-to-market plan ahead of acquisition.

2. `nonpm/p-founder/commercial-positioning` **retain exact**
   > Advised a cloud startup founder on market positioning and early adoption strategy; benchmarked competitors, clarified target customers, and refined the go-to-market plan ahead of acquisition.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `nonpm/p-founder/strategy-operating-model` | retire | “Growth strategy,” “scale-up readiness,” and “pressure-tested the operating model” are generic and name no decision artifact or consequence. |
| `nonpm/p-founder/commercial-positioning` | retain | Distinct positioning question; it is materially different from segment sequencing. |
| `nonpm/p-founder/segment-prioritization` | retain | Most concrete judgment in the family: which segment first and how GTM was sequenced. |

### Human decisions

- None. “Ahead of acquisition” remains temporal and must never be rewritten as causal.

---

## 8. P-GRAB

### Highest-value claim spine

1. **Mobility/safety translation:** rider-safety and operating constraints → product and safety
   design brief. The sentence names neither the key constraint, Akshat's judgment, nor a changed
   decision or outcome, so it fails materiality and counterfactual ownership as resume proof.

### Recommended slate

**Shipping slate: none.** The on-file sentence is admissible but materially too weak. Creating a
second rendering would only paraphrase the same low-signal claim.

### Incumbent decision

| Incumbent | Decision | Material reason |
|---|---|---|
| `nonpm/p-grab/mobility-safety` | retire | “Translated constraints into a brief” is activity, not counterfactual ownership or outcome. It does not earn scarce page space against the corporate and stronger project bank. |

### Human decisions

- None. Future evidence about a specific safety tradeoff or adopted decision may create a new
  candidate, but the current incumbent is retired on content quality.

---

## 9. P-LOREAL

### Highest-value claim spines

1. **Workflow diagnosis:** map creative bottlenecks across two business units → translate the
   bottlenecks into three automation recommendations → deliver for executive review.
2. **Evaluation artifact:** heterogeneous creative workflows need comparable decisions → build
   a GenAI-tool evaluation framework → use it to prioritize three recommendations.

The on-file prompt evidence is admissible and supports two distinct consulting claims.

### Recommended slate, criterion-conditional

1. `nonpm/p-loreal/workflow-diagnostic` **retain exact**
   > Mapped creative workflow bottlenecks across 2 L'Oréal business units; translated them into 3 GenAI automation recommendations for executive review.

2. `nonpm/p-loreal/evaluation-framework` **retain exact**
   > Mapped creative workflows across 2 L'Oréal business units and built a framework to evaluate GenAI tools, prioritizing 3 automation recommendations for executive review.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `nonpm/p-loreal/workflow-diagnostic` | retain | Strongest diagnostic path; bottlenecks cause recommendations rather than merely sharing an AI topic. |
| `nonpm/p-loreal/ai-automation` | retire | Generic midpoint between the other two; no workflow problem or evaluation artifact. |
| `nonpm/p-loreal/evaluation-framework` | retain | Distinct consulting artifact and decision discipline, useful when evaluation methodology is the criterion. |

### Human decisions

- None. No adoption or business outcome is present, so later rewrites must not invent one.

---

## 10. H-QUERY

### Highest-value claim spines

1. **On-call product discovery:** engineers cannot isolate failures across large environments →
   create one reusable investigation surface → make it the default entry point and cut latency.
2. **Technical platform leverage:** dashboard queries are slow and fragmented → redesign MongoDB
   indexes and shared filters → achieve 50% lower query latency across every Hevo 2.0 dashboard.

### Recommended slate, criterion-conditional

1. `pm/h-query/product-discovery` **retain exact**
   > Identified that engineers managing 10,000+ pipelines lacked fast, reliable triage tooling; built a filtering framework adopted across all Hevo 2.0 dashboards, cutting query latency 50% and making it the default pipeline investigation entry point.

2. `pm/h-query/analytics-tools` **retain exact**
   > Shipped a reusable query and filtering framework adopted across all Hevo 2.0 dashboards, cutting query latency 50% via MongoDB index redesign; enabled on-call engineers to filter by Error Type and Source across 10,000+ pipeline environments.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/h-query/product-discovery` | retain | Best product/user rendering; the default investigation entry point closes the discovery claim. |
| `pm/h-query/analytics-tools` | retain | Distinct technical/data-platform rendering with index redesign and concrete filtering dimensions. |

### Human decisions

- None. The on-file variants are admissible; “pipelines” and “pipeline environments” are treated
  as contextual renderings of the same approved scale, not an incompatible numeric claim.

---

## 11. H-REGRESSION

### Highest-value claim spine

1. **Shared release mechanism:** manual QA is the release bottleneck → establish regression
   gates across four teams → catch integration/schema failures before QA → cut release cycles
   from 14 to 4 days and ship enterprise fixes three times faster.

### Recommended slate

1. `H-REGRESSION-amazon-shared-release` **retain known gold**
   > Cut release cycles from 14 to 4 days by establishing a shared release mechanism across 4 engineering teams; automated regression gates replaced manual QA sign-off and caught integration/schema-contract failures pre-QA, shipping enterprise fixes 3× faster.

One variant is correct here. Both live incumbents are same-claim paraphrases; a forced second
variant would create false choice.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `pm/h-regression/execution-velocity` | replace with `H-REGRESSION-amazon-shared-release` | Gold makes the cross-team operating mechanism the ownership proof and preserves both release and enterprise-fix outcomes. |
| `pm/h-regression/platform-quality` | replace with `H-REGRESSION-amazon-shared-release` | Gold retains testing strategy and manual-gate removal while adding the matched enterprise delivery consequence. |

### Human decisions

- None. The approved gold retains both the observed release-cycle change and its delivery-speed
  interpretation; they are not competing sibling values.

---

## 12. H-SUPPORT-OPS

### Highest-value claim spines

1. **Operating-model reframe:** recurring escalations are an ownership-design failure → define
   severity-based intake and escalation paths → give Support and Engineering a common model.
2. **Operational outcome:** ad hoc handoffs slow enterprise incidents → assign routing and named
   ownership by tier → cut issue-resolution time 30%.

### Recommended slate, criterion-conditional

1. `h-support-ops-resolution-ownership` **new challenger**
   > Cut enterprise issue-resolution time 30% by replacing ad hoc Support-to-Engineering handoffs with severity-based routing and named ownership by incident tier.

2. `nonpm/h-support-ops/cluster-a-operating-model-reframe` **retain exact**
   > Reframed recurring escalations as an ownership-design gap between Support and Engineering; introduced severity-based intake rules and clearer escalation paths for enterprise incidents.

### Incumbent decisions

| Incumbent | Decision | Material reason |
|---|---|---|
| `nonpm/h-support-ops/cluster-a-operating-model-reframe` | retain | Distinct strategy/diagnosis sibling; preserves the non-obvious ownership-gap reframe without borrowing a metric. |
| `nonpm/h-support-ops/cluster-b-sla-governance-model` | replace with `h-support-ops-resolution-ownership` | Challenger names the failed before-state and tightens the mechanism/outcome chain. |
| `nonpm/h-support-ops/cluster-b-governance-delivery` | replace with `h-support-ops-resolution-ownership` | Same quantified claim, but challenger removes duplicated SLA language and makes the handoff change legible in one read. |
| `nonpm/h-support-ops/support-only-escalation-ownership` | retire | Dominated by the diagnostic sibling when a metric is unavailable and by the quantified challenger when it is available. |

### Human decisions

- None. The prompt-owned fact block explicitly assigns 30% to issue-resolution time and frames
  recurring escalations as an ownership gap between Support and Engineering.

---

## Batch-level disposition

| Family | Live incumbents | Recommended shipping slate | New challengers | Human holds |
|---|---:|---:|---:|---:|
| F-AVATAR | 5 | 3 | 1 | 0 |
| F-CEIPAL | 5 | 3 | 1 | 0 |
| F-ENTERPRISE | 5 | 4 | 0 | 0 |
| F-OPS | 5 | 4 | 3 | 0 |
| F-SOURCING | 5 | 4 | 0 | 0 |
| FLUO | 4 | 4 | 2 | 0 |
| P-FOUNDER | 3 | 2 | 0 | 0 |
| P-GRAB | 1 | 0 | 0 | 0 |
| P-LOREAL | 3 | 2 | 0 | 0 |
| H-QUERY | 2 | 2 | 0 | 0 |
| H-REGRESSION | 2 | 1 | 0 | 0 |
| H-SUPPORT-OPS | 4 | 2 | 1 | 0 |
| **Total** | **44** | **31** | **8** | **0** |

## Critical review queue

1. **No human holds remain in Batch A.** P-GRAB is retired on content quality rather than held
   for provenance. P-FOUNDER and P-LOREAL are admissible as written.
2. **Wording boundary, not a hold:** Fluo's partnership is confirmed, but exact office, counterparty, scope,
   date, and written status remain open and must not be invented.

No item in this document has been promoted. The next safe step is a human pass over the
critical review queue, followed by exact registry proposals for approved slates only.
