# Whole-bank material variant review — read this first

**Status:** review only. Nothing in these batches is wired into the live generator.

## Outcome

- Audited **135/135 live causal proof variants** across **22 semantic story
  families**. Every live ID appears exactly once.
- Re-derived the story paths rather than treating the Amazon and StudyFetch final
  bullets as the answer. Those gold bullets were challengers/incumbents in the
  comparison, and remain only where they still won.
- Reduced the proof surface to **63 use-case-labelled recommendations**, including
  newly written challengers. A family may keep multiple variants only when
  they answer materially different hiring questions.
- Separately covered all **22 summary/skills/community prompt records** and proposed
  funded, profile-specific summary and community alternatives; fixed skills rows
  remain exact rather than being gratuitously rewritten.
- Preserved **zero live behavior change**. Incumbents remain the shipping default
  until this review is approved and the challenger wins in shadow assembly.

The mechanism is:

> Choose one connected story path that best proves the page's highest-value hiring
> question; lead with the scarcest causal atom; name one decision or artifact;
> finish on that path's strongest attributable consequence; remove facts from
> adjacent paths.

This is implemented as a claim-spine challenger plus pairwise non-regression. A
cleaner sentence cannot replace an incumbent if it loses material signal.

## Review these new challengers first

These are not a universal ranking. Each label says the situation in which that
variant earns page space.

1. **FlairX — product judgment / customer retention**

   > Re-scoped FlairX's Ceipal integration after its API blocked score write-back, automating job and candidate imports to eliminate ~80% of recruiters' duplicate entry while retaining FlairX's highest-volume account.

2. **FlairX — AI reliability / device tradeoff**

   > Shipped anti-fraud controls that stayed viable on low-spec candidate devices by combining gaze, face-mesh and voice signals under 8% CPU and 150ms interruption latency.

3. **FlairX — organizational leverage**

   > Removed the CEO as the routing point for routine account decisions by converting founder-held deal context into self-serve HubSpot workflows for Product and GTM.

4. **FlairX — enterprise diligence**

   > Turned live usage and fulfillment data into diligence evidence for Genpact and L&T, replacing founder-held estimates with defensible views of service mix and delivery history.

5. **Fluo — proprietary consumer evidence**

   > Built a housing surface for students choosing leases sight unseen, combining campus patrol-zone coverage with per-ring rent benchmarks across a $1,028 to $3,750 monthly range that generic listing sites could not supply.

6. **Fluo — fintech product judgment / adverse selection**

   > Redirected Fluo's proposed $5,000 instant credit line into a secured-card-to-unsecured-credit ladder after showing demand concentrated among students with the least repayment capacity under F-1 work limits.

7. **Gojek — analytics / diagnosis**

   > Traded live fare recalculation for sub-second quotes by pre-caching pricing across 12 high-demand corridors; held fare variance within 4%, cut latency 70%, and recovered ~28K monthly rides.

8. **Hevo — AI boundary judgment**

   > Turned 40–60 symptom alerts from one connector failure into a single evidence-backed incident card; kept detection deterministic and used GenAI over a 20+ failure taxonomy to rank recovery actions, cutting diagnosis from ~45 minutes to under 5.

9. **Intuit — analytics to roadmap decision**

   > Joined billing-event logs with subscription lifecycle data to uncover invoice errors behind silent SMB cancellations; reframed accuracy as revenue protection and secured a roadmap shift from feature delivery to reconciliation.

10. **Intuit — judgment under uneven recovery**

    > Rejected a blanket rollback after a billing failure canceled subscriptions for 1,500+ businesses; built a shared account-state ledger with restore, rebuild, and refund cohorts so Engineering, Finance, and Support could recover each account safely.

11. **Optum — safe AI product design**

    > Won pilot approval after clinicians pushed back on a standalone affordability score; reframed it as flag-and-suggest with navigator review and a 90-day automatic stop if outcomes trailed control.

12. **Optum — reusable integration architecture**

    > Found 80% of transformation logic repeated across three failed provider integrations; built a reusable mapping core with typed exceptions, cutting custom engineering from 12–14 weeks to 2 and total onboarding from 6 months to 10 weeks.

## Canonical decisions now resolved

The eight metric/scope collisions above are locked in
[`CANONICAL_STORY_DECISIONS_2026-09-03.md`](CANONICAL_STORY_DECISIONS_2026-09-03.md):
Gojek supply uses `1.5 minutes`; pricing uses `20+ / A/B / 9% / $3.2M`; latency
uses `~28K monthly rides`; Hevo batch uses `8 customers`; Hevo monitoring uses
`45 to under 5 minutes`; Intuit billing uses `five systems / 80K+ / 10%`;
incident uses `days to hours`; and `8 teams` belongs exclusively to governance.
The machine-readable JSON and tests prevent a retired sibling from silently
reappearing in these reviewed slates. Live generator behavior is still unchanged.

## Page-fill answer

Bullet count is not the fill rule. Two observed 10-bullet resumes differed by about
63 points, or roughly five to six body lines. The shadow assembler therefore:

1. renders the semantically strongest base page;
2. uses approved spacing/layout adjustments first;
3. adds only an already-admitted, non-duplicative proof unit that funds a missing
   criterion;
4. accepts quality-protected white space if no such proof exists.

It never lengthens bullets, invents content, or inserts Skills/Interests merely as
padding.

## Full exact review maps

- [Batch A: FlairX, Fluo, projects, and Hevo flex](BATCH_A_FLAIRX_FLUO_PROJECTS.md)
- [Batch B: Gojek and Hevo batch shift](BATCH_B_GOJEK_HEVO_BATCH.md)
- [Batch C: Hevo monitoring, Intuit, and Optum](BATCH_C_HEVO_INTUIT_OPTUM.md)
- [Batch D: summaries, skills, and community](BATCH_D_SUMMARIES_SKILLS.md)
- [Canonical Gojek, Hevo, and Intuit story decisions](CANONICAL_STORY_DECISIONS_2026-09-03.md)

The JSON siblings are the deterministic ID-to-decision maps. The Markdown files
show the claim spines, exact surviving text, displaced signal, and use case.
