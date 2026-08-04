# Recovery Control Plane — Intuit
tags: fintech_billing · crisis / ops · customer trust | lenses: PM, ops, behavioral
best-for: crisis, ambiguity, ownership, "tell me about a time things went wrong", stakeholder coordination
resume: arms ops (primary) + PM; light strategy
note: soft outcome metrics flagged — confirm before resume/interview use.

## Hook (outreach + chat opener)
My strongest crisis lesson came from a recovery that could not be uniform: the right operating product was a shared state model that made technical action and customer promises agree.

## Spoken (~60s — the spine)
A script error moved 1,500 QuickBooks businesses out of their paid state. The hard part wasn't the blast radius — it was that some sat on expired legacy offers, so a blanket rollback was unsafe. I treated recovery as a product with customer states, not a ticket queue: one account-level ledger, three cohorts by reversibility (restore / rebuild with approval / compensate), and parallel streams for engineering, finance/offers, and support. Every account had a state, owner, next action, and promise time; messages were cohort-aware instead of generic "technical difficulty." Most accounts restored fast; the rest got honest reconstruction or refunds. When recovery is uneven, predictability is a product feature.
  +panel extension: stop the migration path + preserve evidence before any second mutation · two-person validation gate on high-risk restores · daily ledger↔production reconciliation · after containment, turn ledger + cohort logic + cadence into a reusable incident kit · reject silent optimism (if a promise window slips, say so before it expires).

## Numbers
1,500 businesses affected · recovery framed as ledger + 3 cohorts · multi-team war room (eng, QA, support, finance, product)
soft ⚠️ (confirm before use): 92% restored within 72h · rest via rebuild/refund within ~10 days · repeat support contacts −46% · zero contradictory mutations after ledger gate · avoidable churn <2% of affected · kit later cuts next sev-1 setup 4h→35m

## Ownership (one line)
I drove the cohort model, shared ledger, and parallel workstream design that unified eng/QA/support/finance/product around one account state — ⚠️ confirm title/authority vs IC influence (you were SWE; maxed lens is "incident product owner").

## If they drill
- Why not blanket rollback? → expired legacy offers; restoring wrong commercial state is worse than a bounded wait.
- What were the three cohorts? → reversible (auto restore) / reconstructable (finance + customer confirm) / compensate-only (refund + assisted transition).
- Your part vs the room? → [ownership line] — name who owned script fix vs offer exceptions vs comms if drilled.
- How did you cut repeat contacts? → cohort-aware messages: what happened, what next, when the next update lands.
- What would you do differently? → ⚠️ fill with your real reflection (e.g. earlier ledger / earlier customer promise cadence).

## Why-them (outreach)
fintech / billing / marketplace ops / any role that cares about incident response, customer trust under failure, or cross-functional crisis execution → lead behavioral/ops story.

---
<details reference>
LP: Ownership · Bias for Action · Earn Trust · Deliver Results · Dive Deep.
PEI: Personal Impact / Courageous Change — uneven recovery, no safe universal fix; you moved people with a shared state model, not heroics.
Provenance: ported from profile_maxing_lab/PX-12 for slim-gold review (2026-07-23). Plot not yet formally Y/N-cleared by you.
A: 1,500 businesses / migration failure / war-room recovery arc appear in local story sources.
R: "predictability is a product" + cohort/ledger framing.
X/⚠️: 92%/72h, −46%, zero contradictory mutations, <2% churn, 4h→35m kit, exact cohort names + validation gates — verify or soften before external use.
</details>
