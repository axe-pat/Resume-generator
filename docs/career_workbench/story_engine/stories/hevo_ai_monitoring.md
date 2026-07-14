# Hevo AI Monitoring — The Incident Card  —  Hevo Data · data_infra / ai_workflow

> **Status: DRAFT v0.1** — pre-filled from existing docs. Items marked ⚠️ need your confirmation or input. Nothing here is locked; the point is to react.
> Distilled from: `STORY_BANK_RICH.md` (H-MONITORING-AI, both variants), `interview_story_scripts.md` (Hevo incident card), `Day 6` (Job Monitoring).

---

## Snapshot
- **One-line hook:** A single root error lit the dashboard with 40–60 disjoint alerts; I built an AI layer that collapsed the storm into one root-cause "incident card," cutting diagnosis from 45 min to under 5.
- **Cluster tag(s):** data_infra, ai_workflow (secondary: observability / incident management)
- **Best for (JD nouns):** AI/GenAI product, LLM workflow design, turning messy operational data into a clean user decision, observability, incident management, alert fatigue, internal tools / support productivity, "tell me about an AI project," "a time you simplified something complex"
- **Role tracks it can serve:** PM (primary), product/technical strategy (secondary)
- **Timeframe & duration:** late 2024 ⚠️ (confirm rough dates + how long it took)

## The Facts (defensible core)
- **Situation & why it mattered NOW:** Hevo's largest enterprise customers were monitoring pipelines on a dashboard that fired **one alert per symptom, not per root cause**. A single failed source connector cascaded into 40–60 downstream failure events, each with its own alert. The trigger for *acting now*: GenAI/LLMs had matured enough to read the alert chaos and group by root cause — the tech finally existed to fix a long-standing pain.
- **Scale / stakes:** Enterprise accounts running 120K+ pipeline environments ⚠️ (confirm the 120K figure — it appears in the rich bank but not the spoken script). On-call engineers burned the **first 45 minutes of every incident** on manual alert-to-root-cause mapping ("finding the leak") instead of fixing.
- **My role & ownership boundary:** ⚠️ **THIS IS THE ONE I MOST NEED FROM YOU.** The docs say "I designed and launched an AI platform." At Hevo you were an engineer — so what was your *actual* role here? Did you originate the idea, design the product/logic, build it, or drive it cross-functionally? Who else was involved (PM? ML? support)? Amazon and MBB will both drill this hard, so we want the honest, specific "I did X, they did Y."
- **What would NOT have happened without me:** ⚠️ (depends on the above)
- **Mechanism / key decision:** Two-layer design —
  - *Detection layer:* per-connector SLA thresholds instead of global thresholds (a Salesforce connector has different baseline latency than a MongoDB connector), using a 14-day rolling baseline (throughput, error rate, sync latency), flagging root-cause events rather than symptoms. ⚠️ (confirm the per-connector + 14-day + 2-std-dev specifics are real vs. reconstructed)
  - *Synthesis layer:* a GenAI model over Hevo's internal failure taxonomy (20+ categorized failure types — schema drift, rate-limit exhaustion, auth token expiry, etc.) producing **one incident card**: connector name, failure category, downstream pipelines affected, est. time-to-resolution, ranked recovery actions.
- **Alternatives I considered and rejected:** "More/better alerts" and broader monitoring coverage — rejected; the answer was *fewer, smarter* alerts. Global thresholds — rejected as either too noisy or too coarse. ⚠️ (any others you weighed?)
- **Trade-off I consciously accepted:** ⚠️ (need this — e.g., per-connector baselines add config/maintenance complexity vs. simple global rules; or trusting AI-grouped output vs. raw alerts. What did you knowingly give up?)
- **Metrics:**
  - 40–60 alerts per incident → **1 card**. *Defense:* ⚠️ confirm typical storm size.
  - Diagnosis time **45 min → under 5 min**. *Defense:* ⚠️ how was this measured — before/after on real incidents, or estimate?
  - **MTTR ~40% reduction** (rich bank). *Defense:* ⚠️ real and defensible, or drop in favor of the 45→5 number?

## Interview Dimensions
- **Amazon LPs demonstrated:** Customer Obsession (engineer pain at 2 AM), Invent and Simplify (storm → one card), Dive Deep (per-connector baselines, failure taxonomy), Deliver Results (45→5 min). ⚠️ Ownership depends on your actual role.
- **MBB / PEI dimension:** Best fit is **Entrepreneurial Drive** (spotted a chronic pain, drove a novel AI solution). ⚠️ Weak spot: the *interpersonal tension* — who resisted? Was there pushback on spending effort on AI, on trusting AI-generated cards, on resourcing? MBB needs a person-vs-person friction here; right now the story is all product insight, no conflict.
  - The interpersonal tension: ⚠️ (need)
  - How I moved people without authority: ⚠️ (need)
  - Why I personally cared: ⚠️ (need — did the alert-storm pain touch you directly?)
- **Behavioral buckets this answers:** "tell me about an AI project," "a time you simplified complexity," "improved a workflow," "took initiative / drove something new," "made a technical thing usable."

## Renderings

### Resume bullets (draft — react)
- Designed an AI-powered incident-monitoring layer that grouped 40–60 cascading pipeline alerts into a single root-cause card, cutting enterprise on-call diagnosis time from ~45 minutes to under 5. *(PM)*
- Built a GenAI synthesis layer over a 20+ category failure taxonomy that translated raw alert storms into ranked, actionable recovery steps, reducing MTTR ~40%. *(PM / technical)*
- Replaced global alert thresholds with per-connector SLA baselines (14-day rolling), eliminating symptom-level alert noise and surfacing root-cause events directly. *(technical/platform)*

### Spoken — SHORT (~30–45s, HireVue)
At Hevo, support engineers watched a dashboard for pipeline failures, but one root error could trigger 40 to 60 downstream alerts — technically accurate, operationally overwhelming. They'd lose the first 45 minutes just figuring out what actually broke. I built an AI incident-card workflow that grouped alerts by root cause, matched them to historical failure patterns, and surfaced one card with the root issue, affected systems, and next steps. Diagnosis dropped from 45 minutes to under 5. It taught me the best AI products are often translation layers between messy system data and a clear human decision.

### Spoken — LONG (~2 min, panel)
*(Context)* At Hevo, we had a central dashboard our support engineers monitored 24/7 for pipeline errors. The problem: software is literal, so one root-level error fired a separate alert for every downstream symptom — a storm of 40 to 60 disjoint notifications at once. Engineers wasted the first 45 minutes of every incident playing detective, sorting noise to find what actually broke.
*(Action)* When LLMs matured, I realized we finally had the right tool — not to add more alerts, but to *read* the storm and group it by root cause instead of symptom. I designed the platform in two layers: a detection layer that used per-connector baselines rather than one global threshold, because a Salesforce connector behaves nothing like a MongoDB one; and a synthesis layer, a GenAI model over our internal failure taxonomy that condensed the mess into a single incident card — the root problem, the systems impacted, and a ranked checklist to fix it.
*(Result)* Diagnosis went from 45 minutes to under 5. ⚠️ *(add MTTR line if confirmed.)*
*(Learning)* It taught me to use GenAI as a translation engine — turning chaotic background data into a clean, trustworthy interface a stressed human can act on.

### Outreach — SHORT hook (1–2 lines)
⚠️ draft — At Hevo I built an AI layer that turned 40–60 alert storms into a single root-cause card and cut incident diagnosis from 45 min to under 5 — which is why [company]'s work on [observability / AI ops / data reliability] is right in my lane.

### Outreach — LONG pitch (one paragraph)
⚠️ draft — I spent my Hevo years close to the pain that data-infra teams live with: a dashboard that was technically correct but operationally useless, firing 40–60 alerts for a single root failure while on-call engineers lost 45 minutes per incident just finding the cause. I built a two-layer AI system — per-connector detection plus a GenAI synthesis layer over our failure taxonomy — that collapsed the storm into one actionable incident card and took diagnosis under 5 minutes. That combination of data-pipeline depth and AI-as-translation-layer is exactly the problem space [company] is working in, which is why I wanted to reach out.

## Follow-up Defense Bank (draft — we'll fill answers together)
- **"What was *your* specific contribution vs the team's?"** → ⚠️ need your input.
- **"How did you measure 45→5 minutes?"** → ⚠️ real before/after or estimate?
- **"Why per-connector baselines instead of global — what did that cost you?"** → complexity trade-off ⚠️.
- **"How did you get engineers to trust an AI-generated card over raw alerts?"** → ⚠️ (trust/adoption — likely the hidden conflict).
- **"What would you do differently?"** → ⚠️ need.
- **"How is this different from your earlier Job Monitoring work?"** → decide relationship with story #4 (before/after vs separate).

## Provenance
- Sources: `docs/reference/STORY_BANK_RICH.md` (H-MONITORING-AI, Story 1 "Alert Fog" + Story 2 "Predictive Shift"), `story_sources/interview_story_scripts.md` (Hevo incident card), `Day 6` (Job Monitoring predecessor).
- Confidence notes: 40–60 alerts and 45→5 min appear consistently across docs (treat as core). The 120K environments, 14-day/2-std-dev thresholds, and ~40% MTTR appear only in the rich bank — confirm before using in behaviorals.
