---
story_id: PX-14
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-14 - The Provider Integration Factory

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Optum · healthcare platform / integrations / regulated delivery · maxed lens: Product Engineer

## The product we finally build

A reusable provider-onboarding platform that turns legacy clinical and claims feeds into Optum's care-network contract through a versioned canonical model, configurable transformation rules, replayable event pipelines, and a joint clinical/technical certification process. The product closes access gaps without treating each provider as a fresh six-month engineering program.

## Fifteen-second version

Optum had repeatedly stalled provider integrations at the same place: late discovery of schema and clinical-definition mismatches. I audited the failed attempts and found roughly 80% of the transformation logic was common. I converted that into a reusable integration factory and brought Clinical Operations into the decision loop so disputes had an accountable owner. The maxed result takes onboarding from six months to 10 weeks, cuts custom mapping work from 12 weeks to two, and closes a network gap affecting a 50M-member program while keeping the $20M scale as program context, not personal attribution.

## Situation and stakes

The work looked like a backend integration: ingest a provider's legacy records and publish them into Optum's care and claims systems. The real consequence was member access. Until the provider joined the integrated network, members in the affected market were more likely to route out of network, increasing cost and creating confusing deductible exposure.

Three earlier integration attempts had failed after months of work. The pattern was consistent: provider-specific mapping grew unchecked, semantic mismatches surfaced during late QA, and neither the provider data team nor Optum engineering had authority to decide contested clinical definitions.

## The non-obvious insight

The repeated “custom” work was mostly the same. Demographics, procedure codes, coverage tiers, claim envelopes, identity, and event lifecycle formed a common core. The true variation lived in a bounded set of clinical and contractual rules.

The second insight was organizational: schema translation is not purely technical when the fields encode clinical meaning. Clinical Operations needed product ownership in the certification path, not ad hoc escalation after engineering disagreed.

## What I own in the maxed version

- Audit the prior attempts and classify mapping logic into reusable core, configurable rule, and provider-only exception.
- Define a canonical provider-event model with versioned contracts for member eligibility, encounter, procedure, claim, coverage, and specialty.
- Build an 80/20 transformation framework: common parsing and validation plus typed rule slots for specialty, setting, modifier, and contractual variation.
- Catch a high-risk specialty-code mismatch in week two: the same provider code maps differently for outpatient, inpatient, and telehealth settings. Convert the correction into a reusable conditional rule.
- Add Kafka-based replay and reconciliation so a failed consumer can recover without duplicate member or claim state.
- Create a joint certification scorecard: schema validity, clinical semantics, privacy, reconciliation, throughput, rollback, and operational readiness.
- Bring Clinical Operations in as co-owner of contested medical definitions and define a three-day escalation SLA.
- Reject a one-provider hard-code despite the immediate deadline; accept two additional design weeks to create the reusable foundation.

## Product judgment and trade-offs

The platform approach delays the first visible integration and adds governance. It earns that cost only if the common model truly survives different provider types. The maxed rollout therefore treats reuse as a testable claim: the second provider must onboard without changes to the canonical core.

The 50M-member and $20M figures remain scale context. The personally attributable outcome is the integration mechanism, cycle-time reduction, and reliability of the launch process.

## Counterfactual outcome

- End-to-end onboarding: **six months -> 10 weeks**.
- Custom transformation effort: **12-14 weeks -> two weeks**.
- Contested schema decisions: **weeks -> three business days** through Clinical Operations ownership.
- Event reconciliation after launch: **99.97%**, with replay-safe recovery and no duplicate member activation.
- The next two provider integrations reuse **83% of mapping and certification assets**.
- Program context: integration contributes to a network expansion serving **50M members** and a **$20M+ annual claims-flow opportunity**; these are not claimed as Akshat-produced revenue.

## Role-flex renderings

**Resume ammo**

- Productized Optum provider onboarding through a reusable 80/20 transformation contract and joint clinical certification path, cutting integration time from six months to 10 weeks.
- Designed versioned event, replay, and reconciliation controls for regulated provider data, achieving 99.97% launch reconciliation while reusing 83% of assets across subsequent integrations.

**Spoken short**

“Three Optum provider integrations had failed at the same late stage because every one was treated as custom and clinical-definition disputes had no owner. I audited the work and found about 80% of the transformation logic was common. I built a versioned integration framework with typed rule slots for the real variation and brought Clinical Operations into certification. We caught a specialty-code mismatch in week two instead of week ten and made it reusable. In the maxed outcome, onboarding drops from six months to 10 weeks. The lesson was that regulated integration is both a platform problem and an ownership-design problem.”

**Outreach hook**

“At Optum, I learned that the hardest integration bugs often encode an unresolved business or clinical definition; the product has to standardize both the data contract and who decides.”

## Follow-up defense bank

- **How did you prove 80% was reusable?** Compare mapping steps across failed integrations and require the next two providers to use the same canonical core without modification.
- **Why did Clinical Operations matter?** Engineering could parse a specialty code but could not authoritatively decide its meaning across care settings.
- **Why not use a commercial integration engine?** The regulated clinical semantics, internal event contracts, and audit requirements still needed a product-owned canonical layer.
- **What was your contribution?** Reference version: failure audit, canonical contract, rule model, certification criteria, escalation design, and launch review; engineers implement and operations/clinical owners certify.
- **How do you prevent a rule explosion?** Versioned rule ownership, usage telemetry, exception budgets, and promotion of repeated rules into the canonical core.

## What would make this true

1. Prior-attempt timeline and failure-mode evidence.
2. Actual common-versus-custom mapping analysis.
3. Canonical schema and event/replay artifacts.
4. Clinical escalation and certification records.
5. Onboarding, reuse, reconciliation, and incident data.
6. Explicit separation between personal result and program scale.

## Provenance ledger

- **A:** Optum employment, provider integration, reusable transformation work, Kafka/event-pipeline context, six-month-to-10-week framing, 50M-member scale, and $20M+ program context appear in local resume/story sources.
- **R:** Integration factory and ownership-design framing amplify the existing 80/20 and Clinical Operations story.
- **X:** 99.97% reconciliation, 83% reuse, exact certification scorecard, two subsequent providers, and several workflow details are counterfactual.
- **V:** Cycle times, 80/20 split, event design, scale context, and Akshat's ownership need source confirmation.

