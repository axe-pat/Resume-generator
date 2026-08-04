---
story_id: PX-15
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-15 - The Affordability Navigation System

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Optum · responsible AI / healthcare workflow / experimentation · maxed lens: Product Engineer

## The product we finally build

A pre-appointment affordability-navigation system that identifies members likely to face avoidable out-of-pocket pressure, explains the contributing signals to a care navigator, and recommends a tiered human-reviewed intervention: cost-estimator prompt, navigator outreach, or social-work referral. It never changes care automatically, and the pilot contains a pre-agreed stop condition if outcomes underperform the control.

## Fifteen-second version

Optum's affordability support arrived after a high-cost claim, when the care decision was already made. I reframed the opportunity around leading indicators before the appointment and turned a hackathon model into a human-reviewed intervention product. The maxed version uses recall-first evaluation, explicit explanations, tiered actions, and a 90-day automatic bail-out criterion. That risk design earns clinical approval for a 2,400-member pilot and improves completed affordability actions 18% without a single automated care change.

## Situation and stakes

The hackathon concept could predict members at risk of financial pressure, but clinical leaders had seen predictive tools create false confidence and workflow harm. Their objection was not whether a model could rank risk. It was whether the organization could understand, contain, and stop the intervention if it behaved badly.

The existing workflow was reactive. A claim revealed high out-of-pocket exposure, then a coordinator called the member. At that point the appointment, provider, or medication choice had often already been made.

## The non-obvious insight

The primary design object is not a risk score; it is a safe next action at the right time. The model becomes useful only when its output maps to a bounded workflow, an accountable human, and an evaluation that reflects asymmetric harm.

Missing an at-risk member is more costly than asking a navigator to review a false positive. That makes recall the primary model metric, but operational capacity still constrains how many flags the team can absorb.

## What I own in the maxed version

- Frame the product around pre-appointment intervention and identify four leading-signal families: prescription fill gaps, recent emergency-department use, deductible utilization, and area-level income context.
- Co-design a tiered playbook with clinical and operations partners:
  - Tier 1: in-app care-cost estimator and lower-cost option education.
  - Tier 2: care-navigator review and outreach.
  - Tier 3: social-work or benefits-support referral.
- Keep the model **flag and suggest**: every Tier 2/3 action requires human review; no care-plan or provider change is automated.
- Choose recall-first evaluation and publish capacity guardrails, navigator override rate, and subgroup performance alongside model accuracy.
- Add member-facing explanation and consent where the workflow moves beyond informational guidance.
- Propose a randomized 90-day pilot with a hard stop if care completion, member harm, or subgroup disparity is worse than control beyond agreed thresholds.
- Reject the faster “risk-score dashboard” because it would create another queue without an owned intervention.

## Product judgment and trade-offs

Recall-first ranking increases false positives and navigator work. The tiered playbook contains that cost: low-risk members receive scalable information; expensive human interventions are reserved for the highest expected benefit.

Area-level income is a sensitive proxy. The maxed product uses it only as contextual support, audits subgroup effects, and never lets it independently determine access to care.

## Counterfactual outcome

- Pilot population: **2,400 members**, randomized with clinical oversight.
- At-risk-member recall: **87%** at an operating point that fits navigator capacity.
- Completed affordability actions: **+18%** versus control.
- Member-reported surprise-cost concern at 90 days: **-11%**.
- Navigator override rate: **14%**, reviewed weekly to improve rules and explanations.
- Automated changes to care or coverage: **zero**.
- No subgroup crosses the pre-defined harm/disparity stop threshold.

## Role-flex renderings

**Resume ammo**

- Converted an Optum hackathon model into a human-reviewed affordability-navigation pilot, pairing recall-first risk detection with tiered interventions and a 90-day automatic stop criterion.
- Improved completed affordability actions 18% across a 2,400-member counterfactual pilot while preserving navigator review, subgroup guardrails, and zero automated care changes.

**Spoken short**

“Our affordability idea initially looked like a model: predict who might face high out-of-pocket costs. Clinical leaders correctly pushed back because a score does not define a safe action. I reframed it as a pre-appointment navigation workflow. The model flagged and explained; a tiered playbook mapped risk to an estimator prompt, navigator call, or social-work referral; and humans approved every meaningful action. The piece that earned approval was a 90-day automatic bail-out rule. In the maxed pilot, completed affordability actions improve 18% with zero automated care changes. I learned that responsible AI is mostly product and operating design around the model.”

**Outreach hook**

“At Optum, the unlock for an AI affordability pilot was not a better prediction claim; it was giving clinicians a bounded intervention, clear override, and automatic exit.”

## Follow-up defense bank

- **Why optimize recall?** False negatives miss a preventable financial-harm intervention; false positives create a review cost. Capacity and override telemetry still constrain the operating point.
- **Why use the income proxy?** Only as contextual evidence; test alternatives, audit subgroup effects, and prohibit it from independently triggering a high-touch action.
- **What does the bail-out measure?** Care completion, member-reported harm, override/error patterns, and subgroup disparity against control at pre-registered thresholds.
- **What was yours?** Reference version: problem framing, workflow tiers, metric hierarchy, risk/stop design, and pilot plan; clinical leaders own medical safety and data/ML teams build the model.
- **What would you do if performance was good but navigators rejected the tool?** Treat override and workflow burden as product failures; pause scale and redesign explanation or routing.

## What would make this true

1. Actual hackathon artifact and model scope.
2. Clinical stakeholder objections and approval criteria.
3. Feature and intervention rationale reviewed for ethics and privacy.
4. Pilot protocol with randomization, thresholds, and capacity plan.
5. Recall, override, action completion, member outcome, and subgroup results.
6. Confirmed personal ownership and clinical boundaries.

## Provenance ledger

- **A:** Optum hackathon, affordability concept, pilot framing, flag-and-suggest, recall-first logic, tiered intervention idea, and 90-day bail-out appear in local story sources.
- **R:** Making the intervention rather than the score the primary product sharpens those anchors.
- **X:** 2,400 members, 87% recall, 18% action lift, 11% concern reduction, 14% override, randomization, consent specifics, and subgroup result are counterfactual.
- **V:** The existence and outcome of any real pilot, feature use, and personal role require confirmation.

