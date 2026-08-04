# Provider Integration Factory — Optum
tags: healthtech · platform / integrations · regulated delivery | lenses: PM, technical, ops
best-for: platform thinking, APIs/integrations, "reuse vs custom", cross-functional ownership, healthcare
resume: arms PM + technical/platform; keep $20M / 50M as program context only — not personal revenue
note: cycle-time and reuse metrics soft — confirm before external use.

## Hook (outreach + chat opener)
At Optum I learned that the hardest integration bugs often encode an unresolved clinical definition — the product has to standardize both the data contract and who decides.

## Spoken (~60s — the spine)
Three provider integrations had failed at the same late stage: treated as fully custom, schema and clinical-definition mismatches surfaced in QA, and nobody owned contested medical meaning. I audited the attempts and found ~80% of the transformation logic was common. So I productized onboarding as a reusable factory — versioned canonical model, 80/20 transformation with typed rule slots for real variation, replayable pipelines — and brought Clinical Operations in as co-owner of certification with a clear escalation SLA. We caught a specialty-code mismatch in week two instead of week ten and made the fix reusable. Regulated integration is both a platform problem and an ownership-design problem.
  +panel extension: reject one-provider hard-code despite deadline (pay two design weeks for the foundation) · specialty code maps differently outpatient/inpatient/telehealth · joint scorecard (schema, clinical semantics, privacy, reconciliation, rollback) · $20M / 50M-member figures = program scale context, not "I generated $20M."

## Numbers
~80% common transformation logic · onboarding framed 6 months → ~10 weeks · custom mapping 12–14 weeks → ~2 weeks
soft ⚠️: 99.97% post-launch reconciliation · 83% asset reuse on next integrations · 3-day clinical escalation SLA
context only (do not personalize): 50M-member network / $20M+ claims-flow opportunity

## Ownership (one line)
I owned the audit → reusable-core vs exception split, the 80/20 framework + certification path, and pulling Clinical Ops into contested definitions — ⚠️ confirm IC vs lead boundary; eng built the pipelines.

## If they drill
- Why not hard-code the urgent provider? → wins one launch, guarantees the next three fail the same way; reuse is the test (second provider must not change the canonical core).
- What was Clinical Ops for? → schema translation encodes clinical meaning; without an owner, disputes die in eng escalation.
- Specialty-code example? → same provider code ≠ same meaning across settings; caught early → reusable conditional rule.
- Did you own the $20M? → No. Program context only; attributable outcomes are mechanism + cycle time + launch reliability.

## Why-them (outreach)
healthtech / care networks / platform-API / B2B integration / regulated data products → lead platform story (pair with Affordability for responsible-AI).

---
<details reference>
LP: Dive Deep · Invent & Simplify · Earn Trust · Deliver Results · Are Right A Lot.
PEI: Personal Impact — move Clinical Ops into the loop without authority; tension = eng urgency vs platform bet.
Provenance: ported from profile_maxing_lab/PX-14 for slim-gold review (2026-07-23).
A: provider integration / 80-20 reuse / Clinical Ops unlock / cycle-time reduction appear in local sources; honest $20M-as-context already in lab.
R: "platform + ownership design" dual insight.
X/⚠️: exact weeks, 99.97%, 83% reuse, Kafka/replay specifics, ownership title — verify or soften.
</details>
