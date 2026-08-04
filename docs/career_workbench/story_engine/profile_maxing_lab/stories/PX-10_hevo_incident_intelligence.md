---
story_id: PX-10
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-10 - The Incident Intelligence Layer

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Hevo Data · AI product / observability / enterprise trust · maxed lens: Product Engineer

## The product we finally build

An incident-intelligence layer that watches connector-specific behavior, distinguishes a root failure from its downstream symptoms, and produces one evidence-backed incident card: what broke, which pipelines and business consumers are affected, why the system believes that, and the next safe recovery action. It operates in shadow mode before it is allowed to suppress raw alerts, and every AI conclusion links back to deterministic telemetry.

## Fifteen-second version

Hevo's monitoring surface could turn one connector failure into 40-60 alerts, leaving on-call engineers to spend 45 minutes reconstructing the root cause. I designed a two-layer product: connector-specific detection plus an AI synthesizer over our failure taxonomy, with evidence links and confidence gates. The maxed result collapses the storm to one incident card, takes diagnosis below five minutes, and reduces MTTR 40% without asking engineers to trust a black box.

## Situation and stakes

Enterprise data teams did not primarily suffer from a lack of telemetry. They suffered from too much unstructured telemetry at the worst possible moment. A single authentication expiry or schema change could cascade through dozens of dependent pipelines. Every symptom fired separately; the operator had to reconstruct topology, sequence, and business impact while an executive dashboard was already going stale.

A second failure class made the problem worse: a pipeline could remain marked “running” while emitting no records. The dashboard looked green even as downstream consumers read hours-old data.

## The non-obvious insight

The valuable AI was not an autonomous fixer and not a prettier log summary. It was a translation layer between deterministic system evidence and a human decision under stress.

That implies a hybrid design. Detection remains explicit and connector-aware. AI groups, explains, and ranks; it does not invent the event. Trust comes from showing the evidence chain and failing open to raw telemetry when confidence is low.

## What I own in the maxed version

- Shadow on-call engineers and support; map the first 45 minutes of incident work into repeatable decisions and information gaps.
- Define per-connector baselines for throughput, error rate, and sync latency over a rolling window instead of one global threshold.
- Add a “silent failure” class: running state plus throughput cessation beyond the connector's expected cadence.
- Build a 20+ category failure taxonomy with platform, support, and connector owners; map each class to evidence, blast radius, and safe actions.
- Specify the incident-card contract: root event, confidence, affected pipelines, downstream business consumers, last good sync, projected staleness, ranked recovery actions, and evidence links.
- Run six weeks in shadow mode. Compare the card's root cause and action ranking with operator decisions; only suppress duplicate symptom alerts for high-confidence classes.
- Reject autonomous remediation at launch. A wrong restart can duplicate or lose customer data; operators keep approval authority.

## Product judgment and trade-offs

Per-connector baselines and evidence-backed cards cost more to maintain than a single global anomaly model. The maxed product accepts that complexity because false confidence is worse than visible noise in enterprise data infrastructure.

The key guardrail is **confidence-shaped UX**: high confidence produces one primary card with symptoms grouped underneath; medium confidence presents two hypotheses; low confidence preserves the original alerts and says why synthesis failed.

## Counterfactual outcome

- Alerts reviewed per incident: **40-60 -> one primary card**.
- Median root-cause diagnosis: **45 minutes -> under five**.
- Mean time to recovery: **-40%**.
- AI root-cause agreement with senior operators: **91%** after shadow calibration.
- High-severity false suppression: **zero** during the first quarter.
- Enterprise evaluation pass rate for monitoring and auditability: **+22 percentage points**.

## Role-flex renderings

**Resume ammo**

- Built an evidence-backed AI incident layer that grouped 40-60 cascading alerts into one root-cause card, cutting diagnosis from 45 minutes to under five and MTTR 40%.
- Earned operator trust through connector-specific baselines, six-week shadow calibration, confidence-shaped UX, and telemetry links; achieved 91% root-cause agreement with zero high-severity false suppression.

**Spoken short**

“At Hevo, one connector failure could create 40 to 60 technically correct alerts. Engineers spent the first 45 minutes finding the leak. I avoided making an LLM the detector; deterministic, connector-specific rules identified evidence, and the AI's job was to group symptoms, explain blast radius, and rank recovery actions. We ran it in shadow mode and only suppressed noise when confidence held. In the maxed version, operators get one evidence-backed card, diagnosis drops below five minutes, and MTTR falls 40%.”

**Outreach hook**

“My favorite AI products do not ask users to trust a clever answer; they make a high-stress decision simpler while preserving the evidence underneath it.”

## Follow-up defense bank

- **Why use AI at all?** The evidence is structured, but mapping dozens of symptoms across topology and failure history into a clear incident hypothesis is a synthesis task.
- **How did you measure 91%?** Senior operators label the root cause independently in shadow mode; agreement is measured at the failure-class and originating-connector levels.
- **Why not automate recovery?** Data movement has asymmetric downside. A false restart or replay can duplicate or lose records; human approval remains until class-specific safety is proven.
- **How did you prevent hallucination?** Retrieval is restricted to telemetry, topology, runbooks, and the controlled taxonomy. Every claim requires an evidence pointer; otherwise the card degrades gracefully.
- **What was your contribution?** Reference version: discovery, product contract, taxonomy facilitation, confidence UX, evaluation design, and rollout decision; platform/ML engineers implement and operate it.

## What would make this true

1. Raw alert-storm samples and time-on-task observation.
2. A versioned failure taxonomy and connector-baseline spec.
3. Shadow-mode evaluation set with senior-operator labels.
4. Confidence thresholds, suppression rules, and incident kill switch.
5. Pre/post diagnosis and MTTR measurement with consistent definitions.
6. Named ownership boundaries confirmed by the team.

## Provenance ledger

- **A:** 40-60 alerts, 45-minute diagnosis, under-five-minute target, 20+ failure taxonomy, connector-specific baselines, silent failures, and ~40% MTTR reduction appear in local story sources.
- **R:** Positioning AI as an evidence-backed translation layer is a stronger product framing of those anchors.
- **X:** Six-week shadow run, 91% agreement, zero severe suppression, +22-point evaluation lift, confidence UX behavior, and exact rollout rules are counterfactual.
- **V:** All measurements, the existence of an AI deployment, and Akshat's ownership require confirmation.
