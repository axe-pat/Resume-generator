# Batch D — summaries, skills, and community

**Status:** review-only. No live prompt, selector, profile, or renderer changes.

## Audit result

The prompt inventory contains **22 rows on this surface**: 9 selectable NONPM
summaries, 5 reference-only PM summaries, 6 selectable analytics/skills rows, and
2 selectable community rows. Every one is mapped exactly once in the companion
JSON. The three campus summaries below are new review candidates and are not
included in that 22-row coverage count.

The 22-row count covers discrete, labelled prompt variants. NONPM's route-specific
keyword catalogs are generative inputs rather than fixed variants; they remain an
assembly/skills-evidence check and are not silently represented as reviewed text here.

Three corrections to the first draft are material:

1. `analytics-kpi` must stay. It is the only compact PM row centered on KPI
   definition; `analytics-data` is the heavier SQL/BI alternative, not a duplicate.
2. The old community rows join Niveda and an unrelated fundraiser. Split them.
   The mission-relevant Niveda gold proves one argument more strongly and at lower
   cognitive cost.
3. The first NONPM challengers were mostly full rewrites into polished abstractions.
   The revised slate starts from each incumbent, adds the required funded identity,
   removes the generic MBA objective, and preserves concrete proof anchors.

## Summary contract

A summary has one job: state the page's identity and make it believable before the
reader reaches Experience.

- Open with an identity funded by the assembly profile.
- Use **identity + evidence anchors**, **identity + rare differentiator**, or
  **identity + repeated decision pattern**.
- Attach “five years” to the broad professional identity, not to a narrow domain
  evidenced by only one recent role.
- Use only anchors selected elsewhere on the page; the summary cannot fund itself.
- Do not repeat Education or end in an MBA career objective.
- Prefer a surgical incumbent repair over a clean-slate rewrite.
- Character count is recorded for comparison, but the rendered page owns line cost.

## Product summary slate

These are use-case alternatives, not a universal ranking.

### Scaled general product — approved Amazon gold, 278 characters

> Product manager and engineer with five years owning technical products end to end: a $3.2M pricing launch on a marketplace serving 20M+ riders, the AI interview infrastructure behind FlairX's enterprise pilots, and the platform bet that unblocked Hevo Data's Fortune 500 trials.

### Independent builder and discovery — approved StudyFetch gold, 293 characters

> Product manager and engineer with five years turning customer and usage signals into shipped AI, marketplace, and data products. Independently built an AI recruiting engine for my own search that turns live job and relationship signals into the next application or conversation worth pursuing.

### AI / zero-to-one — challenger, 254 characters

> Product manager and engineer with five years turning customer and workflow constraints into shipped products across AI, marketplaces, and data platforms. At FlairX, owned enterprise AI hiring workflows from discovery and rapid prototyping through launch.

### Data platform and enterprise trust — challenger, 267 characters

> Product manager and engineer with five years shipping technical products where reliability has direct customer and revenue consequences. At Hevo, turned Fortune 500 auditability blockers into a batch-first platform bet and monitoring surface spanning 120K+ pipelines.

### Marketplace growth — challenger, 258 characters

> Product manager and engineer with five years using customer behavior and system performance to drive growth. At Gojek, separated price from latency abandonment; launched a $3.2M ride tier and independently cut quote latency 70% to recover ~28K monthly rides.

### Fintech and billing trust — challenger, 270 characters

> Product manager and engineer with five years using customer and system evidence to make revenue decisions. At Gojek, launched a $3.2M ride tier from price-sensitivity data; at Intuit, traced cancellations to billing errors and rebuilt reconciliation for 80K+ businesses.

The old PM references should be superseded, not treated as live failures. They are
currently non-selectable; each makes the three-month FlairX title the identity anchor
and spends scarce summary space repeating the MBA credential.

## NONPM summary replacements

Each challenger retains the incumbent route's best evidence while fixing its identity
and objective ending. The first clause validates against the profile listed.

### `nonpm-default` → enterprise/business leadership, 207 characters

> Technical operator with five years building the analytical frameworks and operating systems behind scaled execution: supply governance at Gojek, enterprise readiness at Hevo, and billing integrity at Intuit.

### `nonpm-strategy` → strategy/consulting, 199 characters

> Strategy professional with five years turning operating evidence into executive decisions: enterprise-readiness priorities at Hevo, billing-risk diagnosis at Intuit, and marketplace choices at Gojek.

### `nonpm-bizops` → BizOps/S&O, 217 characters

> Business operator with five years building the cadences behind scaled execution: risk-based triage for 20K+ issues across eight Intuit teams, a shared release mechanism at Hevo, and partner-supply governance at Gojek.

### `nonpm-research` → research/intelligence, 241 characters

> Strategy professional with five years using interviews, behavioral data, and system diagnostics to separate symptoms from the decision that matters. Work has shaped pricing at Gojek, enterprise bets at Hevo, and billing priorities at Intuit.

### `nonpm-client` → client implementation / technical solutions, 242 characters

> Implementation leader with five years translating customer constraints into deployed data, billing, and healthcare systems. At Hevo, enabled eight enterprise onboardings in 90 days; at Optum, cut provider onboarding from 6 months to 10 weeks.

### `nonpm-ops` → operations/program management, 201 characters

> Operations leader with five years building the mechanisms behind scaled execution: risk-based triage across eight Intuit teams, a shared release cadence at Hevo, and partner-supply governance at Gojek.

### `nonpm-commercial` → commercial/GTM, 235 characters

> Commercial strategist with five years turning customer, pricing, and operating evidence into growth decisions. Work has shaped a $3.2M ride tier at Gojek and an Optum provider-expansion recommendation around a $20M+ annual opportunity.

### `nonpm-ai-automation` → AI workflow transformation, 238 characters

> Technical operator with five years building decision systems, plus AI workflow work at FlairX, Optum, and L'Oréal. Designs human control into each system, from transcript-grounded interview scoring to human-reviewed affordability actions.

### `nonpm-technical` → technical PgM / platform operations, 224 characters

> Technical operator with five years turning platform constraints into cross-team execution. At Hevo, built release and monitoring mechanisms across 120K+ pipelines; at Intuit, built billing reconciliation for 80K+ businesses.

**Routing guard:** `nonpm-technical` is funded by the operations profile because the
live rule assigns it to technical PgM, data-strategy, and platform-operations JDs.
A client-deployment role must use `nonpm-client`; `customer-facing technologist`
would not be a funded first clause for the operations profile.

## Campus candidates — review only

These are not live prompt incumbents. Each requires the named page evidence; do not
use a Fluo/Niveda clause when that row is absent.

### Student service — requires selected Fluo and Niveda proof, 294 characters

> USC Marshall MBA candidate with five years coordinating customers and cross-functional teams in high-volume technical environments. Current student-facing work includes interviewing international students on financial and settling needs and supporting mobile-school education for 400+ children.

### Analytics — funded by corporate analytics evidence, 264 characters

> USC Marshall MBA candidate with five years turning operational data into decisions across marketplace, billing, and healthcare systems. Uses Python, SQL, Excel, and dashboards for predictive analysis, funnel diagnosis, process improvement, and executive reporting.

### Communications — requires selected USC/Fluo proof, 273 characters

> USC Marshall MBA candidate with five years translating technical products and operating evidence for customers, executives, and cross-functional teams. At USC, leads external and alumni relations work and has tested student-facing product messaging in live campus settings.

## Skills and community decisions

| Prompt row | Decision | Why |
|---|---|---|
| `analytics-standard` | Retain exact | Clean default discovery/experimentation retrieval row. |
| `analytics-research` | Retain exact | `Research-to-Roadmap` adds a distinct requirements/research signal. |
| `analytics-kpi` | **Retain exact — corrected** | Only compact variant centered on hypothesis design and KPI definition. |
| `execution-discovery` | Retain exact | Distinct execution/requirements row; a label-only rewrite is not a material gain. |
| `ai-automation` | Retain exact | Distinct AI-workflow and model-tradeoff retrieval row. |
| `analytics-data` | Retain exact | Distinct SQL, adoption, instrumentation, dashboard, and KPI surface. |
| `community-full` | Replace with one-argument alternatives | It splices two unrelated contributions and is longer than either proof needs. |
| `community-short` | Replace with one-argument alternatives | Shorter, but still splices Niveda and fundraising. |

Recommended community alternatives, chosen by role rather than combined:

- **Niveda full, approved StudyFetch gold:**
  > Community: Taught through Niveda Foundation's mobile-school initiative, delivering free, activity-based education by van in underserved Noida communities; the program has reached 400+ children.
- **Niveda compact:**
  > Community: Supported education for 400+ children through Niveda Foundation's mobile-school initiative.
- **Fundraising leadership:**
  > Community: Led a 5-member volunteer team that raised $20K for an anti-human-trafficking nonprofit.

Skills and community may occupy legitimate page space when they add funded evidence.
The fill loop may not add them merely to hide whitespace.
