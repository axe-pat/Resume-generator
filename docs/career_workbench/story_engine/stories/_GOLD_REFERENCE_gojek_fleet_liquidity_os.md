# Fleet Liquidity OS — Gojek
tags: marketplace · platform / ecosystem · supply | lenses: PM, technical, strategy
best-for: platform/API products, marketplace supply, ecosystem partners, "contract design"
resume: arms PM + technical/platform; marketplace strategy secondary
note: +18% supply / −1.5 min ETA appear in resume bank — confirm ownership + measurement; onboarding cycle soft.

## Hook (outreach + chat opener)
I love platform problems where the API contract quietly excludes a whole market — at Gojek I redesigned the supply interface around how commercial fleets actually operate.

## Spoken (~60s — the spine)
In mature markets, adding the next individual driver was getting expensive while commercial fleets sat underused. Our API assumed every supplier was a driver pinging every 15 seconds — fleets know capacity in batches, so the first partner took four months and still produced unreliable matching. I reframed the question: not "make fleets speak the driver API," but "what's the minimum commitment a fleet can make that the marketplace can price, rank, and trust?" Four-hour capacity commitments, confidence-weighted matching, decay instead of binary disappear/overstate when telemetry drops, and an SLA-gated certification path. Batch capacity becomes corridor-level liquidity without fake pings.
  +panel extension: reject hard-coding the first partner's dispatch format · corridor-first rollout (calibrate confidence before city-wide) · four-stage launch (credentials → sandbox → prod cert → controlled corridor) · dashboard for committed vs observed supply.

## Numbers
Partner launch framed 4 months → ~6 weeks · active supply in target corridors **+18%** · pickup ETA **−1.5 min** (no extra driver-acq spend)
soft ⚠️: peak unfulfilled −23% · 3 fleet types on one contract without matching forks · exact confidence inputs

## Ownership (one line)
I owned the post-mortem insight, Fleet Supply Contract, confidence-weighted matching rules, and certification path — ⚠️ you were Senior SWE; confirm how much was product contract vs eng implementation.

## If they drill
- Why not force fleets onto the driver API? → they can't impersonate hundreds of phones; synthetic pings lie; missing pings hide real supply.
- Why four-hour windows? → truthful for how fleets operate; less precise than live drivers, contained by confidence weights.
- Why not hard-code partner #1? → one-off launch, not an ecosystem.
- Your part vs marketplace eng? → [ownership line].

## Why-them (outreach)
marketplace / mobility / platform-API / partner ecosystems / supply-side products → lead platform story (pair with fare-latency / pricing golds for Gojek depth).

---
<details reference>
LP: Dive Deep · Invent & Simplify · Are Right A Lot · Deliver Results · Think Big.
PEI: Entrepreneurial Drive / Personal Impact — change the platform contract; tension = urgency for one partner vs reusable ecosystem.
Provenance: ported from profile_maxing_lab/PX-08 for slim-gold review (2026-07-23). Related resume ammo already uses External Fleet API / +18% / −1.5 min.
A: fleet API, 4-hour commitments, confidence matching, +18% supply, −1.5 min ETA — in local sources.
R: "probability of corridor supply" reframing vs 15s ping assumption.
X/⚠️: 4mo→6wk, −23% unfulfilled, exact certification stages, PM-title ownership — verify or soften.
</details>
