# Recruiting Decision Engine — Independent build
tags: ai_workflow · hiring | lenses: PM, builder/technical-PM
best-for: 0-to-1, AI-native building, "a product you built", judgment under a live failure, builder energy
resume: arms PM (primary) + builder/AI-native track
note: VERIFIED ARC ONLY — never claim the multi-user pilot or pilot metrics; recompute counts before public use.

## Hook (outreach + chat opener)
I independently built an AI recruiting engine for my own search that turns live job and relationship signals into the next application or conversation worth pursuing.

## Spoken (~60s — the spine)
Point tools could find roles, tailor documents, or draft messages, but none carried a live opportunity through the whole decision. I built the path from finding and ranking the right role to producing its tailored application and routing the right ask to the right person. One ranked action queue allocates limited time and outreach capacity across applications, referral asks, internship conversations, follow-ups, and longer-term relationships. I remain the PM and first user, using AI coding agents as the engineering team while I own the workflow, state model, acceptance criteria, and ship/rollback calls. A wrong company-person match once triggered a connection invite; I stopped the batch, withdrew it, and changed every send path to require independent employer evidence.
  +panel extension: entity-first model (company/role/person/relationship/application/artifact) · evidence ledger (why scored, why matched, which story, which source) · suggestion vs authority (models rank/draft; humans approve external sends) · fail-closed on purpose · cover letters only when the path requires one.

## Numbers (verified)
Current operating snapshot as of 1 Sep 2026: 190+ applications · 1,100+ targeted contacts · 300+ accepted connections · 100+ replies.
Send-path contract rewritten after the wrong-recipient incident.
⚠️ Counts are live and must be recomputed from the current application and Outreach trackers before public use.
⚠️ Three job offers are user-reported but not yet recorded in the outcome ledger. Use only after confirming each offer's engine path; if confirmed, replace an intermediate metric rather than appending another number.

## Resume renderings

**Summary rendering · approved for StudyFetch**
> Product manager and engineer with five years turning customer and usage signals into shipped AI, marketplace, and data products. Independently built an AI recruiting engine for my own search that turns live job and relationship signals into the next application or conversation worth pursuing.

**Project rendering · current verified default**
> Built the path from finding and ranking the right role to producing its tailored application and routing the right ask to the right person; operated it across 190+ applications and 1,100+ contacts, yielding 300+ accepted connections and 100+ replies.

**Project rendering · use only after three-offer attribution is confirmed**
> Built the path from finding and ranking the right role to producing its tailored application and routing the right ask to the right person; used it to land three offers and generate 100+ replies through targeted outreach.

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
