---
story_id: PX-13
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-13 - The Out-of-Sync Ledger

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Intuit · influence without authority / platform integrity / internal product · maxed lens: Product Engineer

## The product we finally build

A reconciliation overlay that detects when customer, subscription, offer, entitlement, and billing services disagree; assigns each mismatch a canonical owner and safe correction rule; auto-resolves known classes; and exposes the aggregate customer and revenue impact that no individual service team could see.

## Fifteen-second version

At Intuit, Support carried a manual rulebook for billing inconsistencies spread across more than a dozen teams. Each engineering team saw a handful of issues and believed the system was healthy; in aggregate, 50,000 accounts were out of sync. Without authority to rewrite every service, I built the shared case for a lightweight reconciliation overlay and a common ownership model. The maxed result auto-resolves 3,000 discrepancies a month, cuts the backlog 84%, and aligns teams because hidden platform debt becomes visible in customer and revenue terms.

## Situation and stakes

Distributed services held overlapping versions of the same commercial truth. A customer could be paid in one system, inactive in another, attached to an expired offer in a third, and entitled to the product somewhere else. Support engineers fixed known patterns manually through a rulebook.

The organizational design hid the problem. No service team's local queue looked catastrophic. Support absorbed the toil, customers absorbed the inconsistency, and engineering saw only the cases escalated to its boundary.

## The non-obvious insight

The core issue was not merely eventual consistency; it was **fragmented accountability**. A technical rewrite could take years and still fail if nobody owned the cross-service definition of a correct customer state.

The practical product is an overlay: make disagreement observable, safe classes correctable, novel classes owned, and aggregate impact impossible to ignore.

## What I own in the maxed version

- Perform the manual rulebook during onboarding and map every correction to the systems, fields, and owners involved.
- Aggregate mismatch incidents across 12 teams and quantify the hidden 50,000-account backlog.
- Define a canonical discrepancy contract: mismatch class, evidence snapshot, customer impact, safe action, owner, expiry, reversibility, and audit record.
- Propose the overlay rather than a risky big-bang database rewrite. The overlay compares authoritative signals, applies versioned correction rules, and leaves source services independently deployable.
- Create a severity model based on access loss, incorrect charge, renewal risk, and propagation to downstream services.
- Win adoption team by team by showing each lead both the shared customer impact and the engineering benefit: fewer recurring escalations, clearer ownership, and safer launches.
- Establish a weekly cross-service review for novel mismatch classes; a new rule cannot ship without owner, test case, rollback, and sunset condition.

## Product judgment and trade-offs

An overlay does not erase the underlying architecture debt. It adds a second-order system that must be governed carefully. The maxed decision accepts that cost because it delivers customer protection now and produces evidence for deeper fixes, while a multi-year rewrite carries enormous migration risk.

Automation is limited to reversible, well-observed classes. Unknown or financially sensitive mismatches route to a human owner.

## Counterfactual outcome

- Affected-account backlog: **50,000 -> 8,100** in two quarters.
- Known discrepancies auto-resolved: **3,000+ per month**.
- Manual support corrections: **-68%**.
- Median time to assign a novel mismatch to the responsible team: **nine days -> four hours**.
- Repeat inconsistency incidents after correction: **-57%** through versioned rules and regression tests.
- Renewal rate among previously discrepancy-exposed accounts: **+10%** relative improvement.

## Role-flex renderings

**Resume ammo**

- Exposed a 50K-account integrity backlog hidden across 12 teams and launched a governed reconciliation overlay that auto-resolved 3K+ discrepancies monthly and cut manual corrections 68%.
- Established a cross-service ownership ledger and severity model for billing-state mismatches, reducing novel-case assignment from nine days to four hours and repeat incidents 57%.

**Spoken short**

“When I joined Intuit, part of onboarding was running manual fixes for customer state that disagreed across billing services. Engineering teams thought the issue was small because each saw only its own queue. I aggregated the data and showed 50,000 accounts were affected. I did not have authority to rewrite 12 systems, so I proposed a lightweight reconciliation overlay plus a common ownership contract. It automated only reversible classes and routed novel ones to a named team. In the maxed outcome, it resolves 3,000 cases monthly and cuts manual support work 68%. I learned that influence starts by making a shared cost visible in a form every team can act on.”

**Outreach hook**

“At Intuit, the technical inconsistency was real, but the unlock was organizational: give fragmented teams one visible customer-state contract and ownership model.”

## Follow-up defense bank

- **Why was the aggregate 50K not known?** Each queue used different identifiers and severity rules; Support fixes were not linked back to one cross-service mismatch taxonomy.
- **Why not fix every source service?** That is the long-term direction, but the overlay protects customers, creates evidence, and avoids a synchronized multi-team rewrite.
- **How did you earn adoption?** Start with two high-volume classes, demonstrate reduced escalations for participating teams, then use the shared severity model to expand.
- **How do you avoid the overlay becoming permanent debt?** Every rule has an owner, expiry, source-fix link, and sunset condition. The overlay measures which underlying class deserves architectural removal.
- **What was yours?** Reference version: taxonomy, aggregate analysis, product contract, adoption plan, and governance; teams implement connectors and source fixes.

## What would make this true

1. Actual mismatch taxonomy, rulebook, and affected-account aggregation.
2. Team count and ownership map.
3. Overlay design or code artifacts.
4. Reversible versus human-review policy.
5. Backlog, automation, support, assignment, repeat-incident, and renewal metrics.
6. Confirmation of Akshat's influence across teams.

## Provenance ledger

- **A:** Distributed billing inconsistency, a manual Support rulebook, 12+ teams, roughly 50K affected accounts, 3K monthly auto-resolutions, and a 10% renewal context appear in local behavioral/resume sources.
- **R:** Fragmented accountability and a governed overlay sharpen the existing influence-without-authority story.
- **X:** Backlog reduction to 8,100, 68% manual-work reduction, nine-days-to-four-hours assignment, 57% repeat reduction, exact contract fields, and governance mechanics are counterfactual.
- **V:** The implementation, metrics, and personal decision rights require evidence.

