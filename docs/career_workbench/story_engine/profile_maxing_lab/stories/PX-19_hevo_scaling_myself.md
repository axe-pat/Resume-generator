---
story_id: PX-19
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-19 - Scaling Myself, Not Just the Platform

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> Hevo Data · failure / feedback / leadership · maxed lens: behavioral satellite

## The product we finally build

A leadership operating system for a high-risk platform rebuild: explicit decision rights, automated quality gates, architecture records for cross-cutting choices, and visible decision-age metrics. The “product” in this story is the environment that lets engineers own outcomes without asking one person for permission while preserving narrow escalation paths for data-loss and rollback risk.

## The failure

During the Hevo 2.0 rebuild, I mistook technical context for a reason to approve every important implementation choice. I had helped shape the architecture, the deadline mattered, and I wanted to protect quality. Within three weeks, 17 pull requests and five design decisions were waiting on me. Cycle time doubled, engineers stopped proposing alternatives because they expected me to rewrite them, and the migration milestone slipped 11 days.

## Fifteen-second version

My first serious leadership failure was becoming the bottleneck on a platform rebuild I cared too much about. A mentor told me, “You are trying to scale the product without scaling yourself.” I apologized to the team, replaced approval-by-me with clear decision rights and quality guardrails, and moved from controller to unblocker. The maxed result cuts review cycle time from 2.6 days to 0.9, recovers the milestone, and leaves the team with more ownership than before the mistake.

## Why it happened

The behavior came from a defensible concern and an indefensible operating model. The system was high risk, several engineers were new to the domain, and a bad migration could corrupt customer data. But instead of making the quality bar explicit, I kept the bar in my head and inserted myself into every path.

The warning signs were visible: long review queues, private pings asking for permission, design meetings where I spoke first, and decisions escalating upward even when the owner already had the evidence.

## The feedback

A senior engineer gave me direct feedback: I was asking the team to own components while retaining the emotional veto on every consequential choice. The team could not be accountable and dependent at the same time.

I initially wanted to explain the risk. Instead, I reviewed the queue and saw he was right. My desire to prevent a failure had become the proximate cause of one.

## What I change in the maxed version

- Tell the team explicitly that my operating model failed and apologize without qualifying it.
- Publish a decision-rights map: component DRIs decide locally; cross-cutting contract changes require an architecture decision record; only data-loss and migration-rollback decisions escalate.
- Convert tacit quality preferences into three automated gates: compatibility tests, replay idempotency, and rollback proof.
- Stop attending every implementation review. Hold two office-hour blocks and a twice-weekly architecture forum instead.
- Require the DRI to present the recommendation and rejected alternatives before I speak.
- Track review wait time and decision age as leadership metrics, not just engineering metrics.
- Ask the engineer who challenged me to run a two-week check on whether the behavior actually changed.

## Counterfactual outcome

- Median review wait: **2.6 days -> 0.9 day**.
- Decisions waiting on Akshat: **22 -> three** within two weeks.
- The team recovers the 11-day slip before the next migration ring.
- One delegated owner finds a replay optimization that improves migration throughput **18%** beyond my original design.
- The follow-up pulse moves “I can make decisions without unnecessary escalation” from **2.8/5 -> 4.4/5**.

## Spoken short

“On Hevo 2.0, I cared so much about protecting a risky migration that I inserted myself into every design and code review. Within three weeks, the team had 17 pull requests and five decisions waiting on me, and the milestone slipped. A mentor told me I was trying to scale the product without scaling myself. He was right. I apologized, wrote explicit decision rights, converted my preferences into automated quality gates, and moved to office hours instead of approvals. In the idealized result, review wait falls from 2.6 days to under one, we recover the timeline, and a delegated owner beats my original design. I learned that leadership is not retaining every decision; it is making good decisions possible without you.”

## Follow-up defense bank

- **What was the hardest part?** Admitting that the behavior I thought represented ownership was reducing ownership for everyone else.
- **Why should we believe you changed?** Decision-age data, a follow-up pulse, and a specific person empowered to tell me if the old behavior returned.
- **What remained centralized?** Data-loss risk, rollback policy, and cross-cutting contracts. Delegation was bounded, not careless.
- **Would you act differently at the start?** Define decision rights and automated quality gates before the build, then intervene only on pre-agreed escalation conditions.
- **What if the delegated decision was wrong?** I would own the system that authorized it, use the rollback, and improve the guardrail without reclaiming every decision.

## What would make this true

1. Confirmation that the bottleneck and feedback occurred as described.
2. Real queue, cycle-time, and milestone data.
3. The actual operating change - DRI map, ADRs, office hours, or review policy.
4. Evidence that another person's ownership increased.
5. A reflection phrased in Akshat's natural voice.

## Provenance ledger

- **A:** The existing behavioral material says Akshat over-owned the Hevo 2.0 architecture, became a bottleneck, received “scale yourself” feedback, apologized, delegated, and recovered velocity.
- **R:** Framing the failure as incompatible accountability and dependency makes the leadership lesson more precise.
- **X:** 17 pull requests, five decisions, 11-day slip, cycle-time values, 18% optimization, pulse scores, and exact operating mechanisms are counterfactual.
- **V:** The actual feedback wording, scale of delay, remediation, and results require confirmation.
