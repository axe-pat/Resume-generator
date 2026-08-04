# Recruiting Decision Engine — Independent build
tags: ai_workflow · hiring | lenses: PM, builder/technical-PM
best-for: 0-to-1, AI-native building, "a product you built", judgment under a live failure, builder energy
resume: arms PM (primary) + builder/AI-native track
note: VERIFIED ARC ONLY — never claim the multi-user pilot or pilot metrics; recompute counts before public use.

## Hook (outreach + chat opener)
I built my recruiting system after realizing generation was the easy part — trustworthy opportunity decisions need entity state, provenance, approval boundaries, and recovery when something goes wrong.

## Spoken (~60s — the spine)
I started by building a resume generator, then operating it taught me writing wasn't the bottleneck — decision quality was. A high-fit role could be found twice, tailored without relationship context, or contacted after the application closed. So I became the PM and first user, using AI coding agents as my engineering team while I owned the workflow, state model, acceptance criteria, and ship/rollback calls. The verified build spans 151 commits, 542 release tests, ~2,500 roles and hundreds of touchpoints. A wrong company-person match once triggered a connection invite; I stopped the batch, withdrew it, and changed every send path to require independent employer evidence. That's when it became a product — not because the AI wrote well, but because state, guardrails, and recovery made its decisions trustworthy.
  +panel extension: entity-first model (company/role/person/relationship/application/artifact) · evidence ledger (why scored, why matched, which story, which source) · suggestion vs authority (models rank/draft; humans approve external sends) · fail-closed on purpose · cover letters only when the path requires one.

## Numbers (verified)
96-day history · 151 commits · 542 passing release tests · ~2,514 roles / 560 orgs / ~849 touchpoints
send-path contract rewritten after the wrong-recipient incident
⚠️ recompute all counts from current repos before any resume/outreach use.

## Ownership (one line)
I owned problem definition, roadmap, operating reviews, trade-offs, acceptance criteria, and ship/rollback; AI coding agents accelerated implementation.

## If they drill
- AI agents vs you? → agents implemented; I owned definition, reviews, trade-offs, ship/rollback.
- Multi-user today? → No. Personal production workflow; multi-user is future work — don't claim it.
- Key metric? → time to a high-quality reviewed action, bounded by false-positive + unreviewed-send guardrails.
- Why split ResumeGenerator and Outreach? → different state/risks/operators; shared discovery, specialized execution.
- Build next? → claim-level Story Engine with approved evidence only, then a small privacy-separated pilot.

## Why-them (outreach)
AI product / workflow / recruiting-tech / anything valuing trust + state over raw generation → lead builder story.

---
<details reference>
LP: Ownership · Bias for Action · Insist on Highest Standards · Earn Trust · Invent & Simplify · Deliver Results.
PEI: Entrepreneurial Drive — you created the problem space by building+operating. Interpersonal texture is thin (solo); lean on the safety incident as the judgment-under-pressure beat.
Provenance: ported from profile_maxing_lab/PX-17 (verified sections only).
A: two-system architecture, 96 days, 151 commits, 542 tests, scale snapshot, wrong-company invite incident.
R: decision-and-state framing, first-user PM, evidence/guardrail emphasis.
EXCLUDED from gold: 30-user USC pilot + all pilot outcome metrics (remain lab/future). Never claim monetization, autonomy, or multi-tenancy.
</details>
