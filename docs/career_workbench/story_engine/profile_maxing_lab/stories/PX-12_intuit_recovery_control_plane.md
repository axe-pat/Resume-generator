---
story_id: PX-12
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-12 - The Recovery Control Plane

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Intuit · crisis leadership / operations / customer trust · maxed lens: incident product owner

## The product we finally build

A recovery control plane for a one-time migration failure affecting 1,500 QuickBooks businesses. It gives every account a known state, safe recovery path, customer promise, and owner. Technical restoration, offer reconstruction, refunds, support communication, and executive reporting run from the same cohort model instead of five disconnected war-room threads.

## Fifteen-second version

A faulty script migrated 1,500 businesses out of their paid state, and not every account could simply be rolled back because some sat on expired legacy offers. I treated recovery as a product with customer states, not a queue of tickets. I established one account-level ledger, split the population into reversible, reconstructable, and compensate-only cohorts, and ran engineering recovery and transparent communication in parallel. The maxed result restores 92% within 72 hours, resolves the rest through consented offer rebuilds or refunds, and leaves a reusable incident playbook.

## Situation and stakes

The failure cut small businesses off from subscriptions they used to run payroll and accounting. Support queues spiked within hours. The technical temptation was to focus on the script and promise a universal rollback.

The data made that promise unsafe. Accounts had different offer histories, entitlement states, and payment conditions. Some legacy offers had expired years earlier and could not be recreated through the normal product path. A blanket script could restore access for many while silently putting others into a new, incorrect commercial state.

## The non-obvious insight

During an irreversible or uneven recovery, **predictability becomes part of the product**. Customers can tolerate a bounded wait better than a sequence of contradictory updates. The war room therefore needs one state machine that drives both remediation and communication.

## What I own in the maxed version

- Stop the migration path, preserve evidence, and define the account-level recovery invariant: no second automated mutation without a verified before-state and reversible plan.
- Create three cohorts:
  1. **Reversible:** original offer and entitlement can be restored automatically.
  2. **Reconstructable:** prior state can be rebuilt with finance/offer-team approval and customer confirmation.
  3. **Compensate-only:** exact prior state is legally or technically unavailable; refund and assisted transition are required.
- Stand up a shared ledger with account, cohort, last known good state, owner, next action, validation status, customer promise time, and communication history.
- Run three parallel workstreams: recovery engineering and QA, offer/finance exceptions, and support communication.
- Replace generic “technical difficulty” language with cohort-aware messages that say what happened, what the customer can expect next, and when the next update will arrive.
- Define a two-person validation gate for high-risk restores and a daily reconciliation between the ledger and production state.
- After containment, turn the ledger, cohort logic, and communication cadence into a reusable incident kit.

## Product judgment and trade-offs

Speed is not one number. A universal rollback is faster for the median account but dangerous for edge cases. Cohorting adds operational overhead while letting the team restore the easy majority quickly and handle irreversible states honestly.

The maxed plan rejects silent optimism. If a promise window is at risk, the customer hears that before it expires, even if the update is uncomfortable.

## Counterfactual outcome

- Affected businesses: **1,500** with 100% assigned a recovery state and owner within six hours.
- **92% restored within 72 hours**; remaining accounts resolved through approved reconstruction or proactive refund within 10 days.
- Duplicate or contradictory account mutations: **zero** after the ledger gate launches.
- Repeat support contacts per affected account: **-46%** after cohort-aware messaging begins.
- Major avoidable churn held below **2%** of the affected population.
- Recovery kit later reduces setup time for the next severity-one incident from **four hours to 35 minutes**.

## Role-flex renderings

**Resume ammo**

- Led a 10-day recovery for 1,500 QuickBooks businesses by unifying Engineering, QA, Support, Finance, and Product around an account-level recovery ledger and reversible cohort plan.
- Restored 92% of accounts within 72 hours and resolved non-reversible legacy states through transparent reconstruction/refund paths, cutting repeat contacts 46% with zero contradictory mutations.

**Spoken short**

“A script error moved 1,500 QuickBooks businesses out of their paid state. The hard part was that some legacy offers had expired, so a blanket rollback was unsafe. I created a recovery control plane: one account ledger, three cohorts based on reversibility, and parallel technical and communication workstreams. Every account had a state, owner, next action, and promise time. In the maxed outcome, 92% are restored within 72 hours, the rest receive approved reconstruction or refunds, and repeat support contacts fall because customers get honest, cohort-specific updates. I learned that when recovery is uneven, predictability is a product feature.”

**Outreach hook**

“My strongest crisis lesson came from a recovery that could not be uniform: the right operating product was a shared state model that made technical action and customer promises agree.”

## Follow-up defense bank

- **Why did you need a new ledger?** Ticket systems tracked interactions, not a verified recovery state across entitlement, offer, payment, and communication owners.
- **What did you do in the first hour?** Stop further mutation, preserve logs, identify the affected population, name the invariant, and create an initial cohorting query.
- **Why not wait until the fix was known before communicating?** Silence creates repeated contacts and false expectations. The first message can accurately state impact, containment, and next-update time.
- **What was your role versus the incident commander?** In this reference version, I own the recovery model, cross-workstream operating cadence, and customer-state integrity; designated technical and executive incident commanders retain their formal authorities.
- **What would you do differently?** Pre-build the cohort/ledger pattern and simulation rather than inventing it under pressure.

## What would make this true

1. Incident timeline and exact affected-account count.
2. Real offer/entitlement edge cases and recovery categories.
3. Evidence of Akshat's formal or de facto coordination role.
4. Account restoration and resolution timestamps.
5. Support-contact, churn, refund, and communication data.
6. The actual reusable artifact created after the incident.

## Provenance ledger

- **A:** A faulty script affected about 1,500 businesses; recovery lasted roughly 10 days; Engineering, QA, Product, Support, and offer/refund teams were involved; some legacy offers could not simply be restored. These elements appear in local behavioral sources.
- **R:** Parallel recovery and communication and “predictability is part of the product” extend the existing learning.
- **X:** Three named cohorts, six-hour assignment, 92%/72-hour recovery, contact/churn outcomes, zero mutations, shared ledger fields, and reusable-kit result are counterfactual.
- **V:** Incident role, timing, cohort sizes, and all outcome metrics require confirmation.

