# Incident Intelligence — Hevo
tags: data_infra · ai_workflow · observability/AI product | lenses: PM, technical
best-for: "tell me about an AI project", simplifying complexity, workflow/reliability, alert fatigue
resume: arms PM (primary) + technical/platform tracks

## Hook (outreach + chat opener)
At Hevo I built an AI incident layer that turned 40–60 alert storms into one evidence-backed root-cause card, cutting diagnosis from ~45 min to under 5.

## Spoken (~60s — the spine)
One connector failure could fire 40–60 technically-correct alerts; on-call burned the first 45 minutes just finding the leak while the exec dashboard went stale. I didn't make an LLM the detector — deterministic, connector-specific rules found the evidence, and the AI's job was to group symptoms, explain blast radius, and rank recovery actions into one incident card. We ran it in shadow mode and only suppressed noise once confidence held. Diagnosis dropped under 5 minutes, MTTR ~40%. The lesson: the best AI products are a translation layer between messy system data and a human decision — not a black box.
  +panel extension: "silent failure" class (running but zero records) · 20+ category failure taxonomy · why NOT autonomous remediation (asymmetric data downside) · confidence-shaped UX (high→one card / med→two hypotheses / low→raw alerts).

## Numbers
40–60 alerts → 1 card · ~45 min → <5 · MTTR ~−40%
soft ⚠️ (confirm before use): ~91% operator agreement · zero high-sev false suppress · +22pp enterprise eval

## Ownership (one line)
I owned discovery, the incident-card contract, taxonomy + confidence UX, and the rollout call; platform/ML engineers built and operated it. ⚠️ confirm exact split.

## If they drill
- Why AI at all? → synthesis across topology + failure history, not detection.
- Hallucination? → retrieval limited to telemetry/topology/runbooks/taxonomy; every claim needs an evidence pointer or the card degrades to raw alerts.
- Why not auto-fix? → a wrong restart can lose/duplicate customer data; humans keep approval until class-specific safety is proven.
- Your part vs team's? → [ownership line above].
- How measured (45→5, MTTR)? → ⚠️ lock before/after-vs-estimate defense line.

## Why-them (outreach)
observability / AI-ops / data-reliability / incident-management companies → this is your lead story.

---
<details reference>
LP: Customer Obsession · Invent & Simplify · Dive Deep · Deliver Results · Earn Trust.
PEI: Entrepreneurial Drive — ⚠️ add interpersonal tension (who resisted trusting AI cards / resourcing) before PEI use.
Provenance: ported from profile_maxing_lab/PX-10 after plot clearance (2026-07-21). Supersedes draft hevo_ai_monitoring.md. Overlaps Job Monitoring predecessor — treat as evolution (visibility → incident intelligence), not a 2nd story.
A: 40–60 alerts, 45-min diagnosis, <5-min target, 20+ taxonomy, connector baselines, silent failures, ~40% MTTR — in local sources.
R: "AI as evidence-backed translation layer" framing.
X/⚠️: 6-week shadow, 91% agreement, zero false-suppress, +22pp eval, exact confidence-UX rules, ownership boundary — verify before external use.
</details>
