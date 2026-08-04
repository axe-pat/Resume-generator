# Enterprise Trust Pivot — Hevo
tags: data_infra · enterprise SaaS · product strategy | lenses: strategy, PM, ops
best-for: product strategy, segmentation, "drive change", roadmap tradeoffs, architecture-as-strategy
resume: arms strategy (primary) + PM + ops tracks

## Hook (outreach + chat opener)
At Hevo the hard call wasn't which reliability feature to add — it was choosing the customer and changing the execution model around the promise they actually bought.

## Spoken (~60s — the spine)
Hevo looked like it had a feature problem, but the real issue was strategic: open source was eating the low end, enterprise trials were failing on trust, and we were still optimizing for real-time speed most workloads didn't need. Usage data showed customers consumed hourly or daily — architects were buying integrity: complete data, known state, safe replay, audit proof. So segmentation came before architecture. I built the segment + lost-trial case, then helped drive the Hevo 2.0 bet: rebuild around batch-first transactional execution with explicit rollback and audit history, plus a ring-based migration. Eight enterprise customers in 90 days, base migrated without churn. Architecture becomes product strategy when it defines the promise a buyer can trust.
  +panel extension: three-path memo (improve streaming / wrapper / rebuild) — chose rebuild because the trust failure was in the execution model · ring migration (internal→partners→low-risk→base) with guardrails · counter-position vs Fivetran/Airbyte · conscious cost = feature freeze + multi-quarter rewrite.

## Numbers
8 enterprise customers in 90 days · base migrated, no involuntary churn
soft ⚠️ (confirm before use): trial-to-paid 31%→64% · consistency incidents −45% · 97% automated migration · eval proof hours→<10 min

## Ownership (one line)
I owned the segment/trial-loss evidence, product contract, guardrails, and migration sequencing; leadership approved the strategic bet; engineering owned the rewrite. ⚠️ confirm your influence line.

## If they drill
- Why not just add reliability features to streaming? → monitoring explains a partial load, it can't make it atomic; the failure was the product contract.
- Overfitting to loud prospects? → interview themes + freshness distribution + failed-trial codes + retention/expansion economics.
- Protect existing customers? → compatibility layer, dual-run comparison, per-ring rollback, migrate only after guardrails passed.
- What would change your mind? → a revenue-weighted cohort truly needing sub-minute freshness → dual execution tier.

## Why-them (outreach)
enterprise data infra / ELT / anything selling "trust/correctness" upmarket → lead strategy story.

---
<details reference>
LP: Are Right A Lot · Dive Deep · Think Big · Deliver Results · Earn Trust.
PEI: Courageous Change / Entrepreneurial Drive — company not yet in crisis, you argued to pause velocity for a foundation bet. Bring who pushed back + how segment evidence moved them.
Provenance: ported from profile_maxing_lab/PX-09 after plot clearance (2026-07-21).
A: Hevo 2.0 pivot, streaming→batch tradeoff, enterprise architects, 8 customers in 90 days, migration without churn — in local sources.
R: "buyer pays for trust" spine + architecture-as-contract framing.
X/⚠️: 31→64%, −45%, 97%, <10-min proof, exact three-path memo + ring design, ownership boundary — verify before external use.
</details>
