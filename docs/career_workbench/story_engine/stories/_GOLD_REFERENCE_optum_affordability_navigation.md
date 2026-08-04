# Affordability Navigation — Optum
tags: healthtech · responsible AI · clinical workflow | lenses: PM, AI product
best-for: responsible AI, stakeholder trust, experimentation, "AI project with guardrails", healthcare
resume: arms PM (primary) + AI/responsible-AI track
note: pilot outcome numbers are soft — confirm before any external use.

## Hook (outreach + chat opener)
At Optum the unlock for an AI affordability pilot wasn't a better prediction claim — it was giving clinicians a bounded intervention, clear override, and an automatic exit.

## Spoken (~60s — the spine)
Affordability support used to arrive after a high-cost claim, when the care decision was already made. A hackathon model could rank who's at financial risk, but clinical leaders correctly pushed back: a score isn't a safe action. I reframed it as a pre-appointment navigation product — flag and suggest, not auto-change care. The model explained contributing signals; a tiered playbook mapped risk to cost-estimator education, navigator outreach, or social-work referral; humans approved every meaningful action. The piece that earned approval was a 90-day automatic bail-out if outcomes underperformed control. Responsible AI is mostly product and operating design around the model.
  +panel extension: leading signals (fill gaps, ED use, deductible utilization, area-level income as context only) · recall-first eval with capacity guardrails · reject "risk-score dashboard" (another queue, no owned intervention) · subgroup / disparity stop thresholds · zero automated care or coverage changes.

## Numbers
Hackathon → human-reviewed intervention product · flag-and-suggest · 90-day bail-out criterion · 0 automated care changes
soft ⚠️ (confirm before use): 2,400-member pilot · recall ~87% · completed affordability actions +18% vs control · surprise-cost concern −11% · navigator override ~14%

## Ownership (one line)
I owned the product reframe (score → safe next action), tiered playbook with clinical/ops partners, evaluation + stop rules, and the "no automated care change" boundary — ⚠️ confirm what you personally shipped vs hackathon team / clinical owners.

## If they drill
- Why not just ship a risk dashboard? → creates a queue without an owned intervention; clinicians won't trust it.
- Why recall-first? → missing an at-risk member costs more than a false positive a navigator can dismiss; capacity still caps volume.
- Income proxy? → contextual only; never independently decides access; audit subgroup effects.
- What earned clinical approval? → bounded actions + human review + hard stop if harm/disparity vs control.
- Your part vs the model team? → [ownership line].

## Why-them (outreach)
healthtech / responsible AI / clinical workflow / trust & safety / anything selling "AI with guardrails" → lead AI-product story.

---
<details reference>
LP: Customer Obsession · Earn Trust · Dive Deep · Are Right A Lot · Deliver Results.
PEI: Personal Impact — clinical pushback on predictive tools; you moved them with risk design, not model accuracy claims.
Provenance: ported from profile_maxing_lab/PX-15 for slim-gold review (2026-07-23).
A: Optum affordability / hackathon / flag-and-suggest / responsible-AI framing appear in local story sources.
R: "primary object is safe next action, not risk score" + bail-out as product feature.
X/⚠️: 2,400 pilot, 87% recall, +18%, −11%, 14% override, exact signal families + tiers — verify or soften before external use.
</details>
