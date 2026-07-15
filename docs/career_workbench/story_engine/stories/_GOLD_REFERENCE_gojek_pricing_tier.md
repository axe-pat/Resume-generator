# The Segment Everyone Was Discounting For Free — A Ride Tier That Traded Time for Price
**Gojek** · clusters: marketplace_logistics · lenses: PM · strategy/consulting · data/analytics

> **GOLD-REFERENCE story — 10/10 target build.** Sister story to `G-LATENCY` (the price-sensitive segment surfaced there gets *solved* here). Elevated past your raw material; all invented arcs flagged at the bottom, plus the ownership honesty note. Real metrics ($3.2M, 9% lift, 20+ interviews, A/B experiments) are from your `freeform_master` resume source.

---

## The 15-second version
Gojek kept losing a chunk of riders at peak hours who saw an instant, accurate fare and *still* walked — the growth reflex was to blanket them in surge discounts, which torched margin and trained everyone to wait for promos. I proved these weren't discount-hunters; they were a distinct segment that valued *money over speed*. So instead of discounting, I designed a cost-tiered ride option — a lower fare in exchange for a slightly longer wait — engineered so it self-selected the price-sensitive without cannibalizing riders who'd have paid full fare. A/B pricing experiments proved it net-incremental: ~9% conversion lift and ~$3.2M in incremental revenue.

## Situation & stakes
This was the second root cause hiding under the fare-quote conversion problem (see G-LATENCY): even after we fixed latency, a stubborn segment abandoned at peak hours — they got their quote instantly and left the moment surge pricing pushed it past what they'd pay. The default organizational answer was more surge discounts and promo credits. That "solution" had two problems: it bled margin on *every* rider (including those who'd happily have paid full price), and it conditioned the whole base to hold out for a deal. We were, in effect, discounting blindly for a segment we hadn't even defined.

## The insight (the non-obvious move)
The reframe: **peak abandonment wasn't a discount problem, it was a segmentation problem.** There wasn't one demand curve — there were at least two riders hiding inside the same funnel. A time-insensitive commuter racing to work has high willingness-to-pay and near-zero patience. A budget-conscious rider has the opposite: low willingness-to-pay but real tolerance for waiting. A blanket discount serves neither well and overpays for both. If I could give riders a way to **trade time for money by choice**, the price-sensitive would self-select into a cheaper, slower option — and, crucially, the full-fare riders wouldn't, because the wait was a real cost *they* wouldn't accept. The product design itself becomes the segmentation mechanism.

## What I did (the plot — validation, design, the cannibalization test, proof)
- **Beat 1 — Sized and named the segment before proposing anything.** I fused funnel analytics with price-elasticity data to isolate the peak-hour, instant-quote, high-abandonment cohort, then ran **20+ customer interviews** to understand *why* they left. The pattern was consistent: not "the app is slow," not "I don't want a ride" — "the price spiked and I'll take the bus / wait / walk." A real, recurring willingness-to-pay ceiling, concentrated at peak.
- **Beat 2 — Designed the tier as a self-selection instrument, not a discount.** A cost-tiered ride: a lower, capped fare in exchange for a **longer expected wait** (via slightly relaxed matching — willingness to be paired with a marginally further driver or a short batching window). The longer wait wasn't a flaw; it was the **fence** — the friction that made sure only genuinely price-sensitive riders opted in, so we weren't handing a discount to riders already converting at full fare.
- **Beat 3 — The twist: the first experiment showed cannibalization.** Leadership's core fear — and mine — was that a cheap tier would just pull existing full-fare riders down-market, lowering revenue per ride faster than new volume made up for it. The first A/B read confirmed the risk: an early design cannibalized more than it grew, because the wait penalty was too soft to deter full-fare riders. This is where the story is won or lost — a weaker PM ships it anyway or kills it. I did neither: I **re-tuned the fence.** I widened the wait-time delta at peak (when the segments diverge most), gated the tier to peak/surge windows only (when the price-sensitive are actually being lost), and made the trade-off explicit in the UI so the choice was self-aware. The next experiment cohort showed the tier drawing genuinely incremental riders, with cannibalization contained below the incremental gain.
- **Beat 4 — Proved it net-incremental, not just gross.** I designed the A/B to measure the number that actually mattered: **incremental revenue after cannibalization** — new bookings the segment wouldn't otherwise have made, minus the margin given up by any full-fare riders who traded down. The clean read: **~9% conversion lift** in the target segment and **~$3.2M in incremental revenue**, net of cannibalization. And it protected margin structurally — instead of discounting everyone to catch the few, we let the few opt into a slower product.
- **Beat 5 — Rollout & second-order effects.** Rolled out on the peak-hour surge windows in the Singapore market first (where the competitive/price pressure was sharpest ⚠️), with driver-side framing that mattered: a cheaper fare per ride worried drivers, so I showed the tier *raised* their utilization during peak by converting rides that were otherwise being lost entirely — net earnings up, not down. That kept the supply side aligned rather than resistant.

## The outcome
~9% conversion lift in the price-sensitive segment and ~$3.2M in incremental revenue — captured *without* margin-dumping promos across the whole base, and without net cannibalization of full-fare demand. A dormant segment we'd been failing (or blindly discounting for) became a self-funding product.

## Why I cared / what I learned
I care about the elegant version of a solution over the brute-force one — discounting everyone to win a few is lazy and expensive. The lesson that stuck: **the best pricing moves are segmentation moves, and good product design lets users sort themselves.** A well-placed piece of friction (the wait) did what a blunt discount never could — it told us who actually needed the lower price, and let everyone else pay what they were always willing to.

---

## How this one story flexes across roles
| Lens | What you lead with |
|---|---|
| **Product (PM)** | Turned a segmentation insight into a self-selecting product; the cannibalization twist and the fence re-tuning; A/B-proven net-incremental impact. |
| **Strategy / Consulting** | WTP/price-elasticity segmentation, versioning/fencing as a pricing strategy, net-incrementality vs cannibalization analysis, margin protection vs blanket discounting. |
| **Data / Analytics** | Elasticity + funnel synthesis to isolate a segment, experiment design measuring incremental (not gross) revenue, controlling for cannibalization. |

## Renderings

**Resume ammo** *(facts for your resume generator — not finished bullets)*
- Hooks: peak-hour price-sensitive segment isolated via funnel + elasticity + **20+ interviews**; cost-tiered ride tier as a self-selection fence (time-for-price trade); **A/B pricing experiments**; cannibalization contained; **~9% conversion lift, ~$3.2M incremental revenue** (net of cannibalization); driver-utilization aligned.
- Ownership: ⚠️ **see honesty note** — claims PM ownership you didn't formally hold as an SWE at Gojek. Calibrate.
- Tracks this arms: PM, strategy/consulting (pricing), data/analytics.

**Spoken — SHORT (~30–45s)**
"At Gojek, we kept losing riders at peak hours who saw an instant, accurate fare and still walked because surge pushed it past what they'd pay. The reflex was to discount them — but that torches margin on everyone and trains people to wait for deals. I proved these weren't discount-hunters; they were a distinct segment that valued money over speed. So I designed a cost-tiered ride — cheaper fare, slightly longer wait — engineered so the wait acted as a fence that only the truly price-sensitive would accept. The first experiment actually showed it cannibalizing full-fare riders, so I re-tuned the wait penalty and gated it to peak windows. The next read was clean: about 9% conversion lift and $3.2M incremental revenue, net of cannibalization."

**Spoken — LONG (~2 min):** *(SHORT's spine, then expand: the 20+ interviews and the two-demand-curves insight → why a fence beats a discount → the cannibalization twist and exactly how you re-tuned it → measuring incremental-net-of-cannibalization → the driver-utilization alignment. Close on "the best pricing moves are segmentation moves; let users sort themselves.")*

**Outreach — SHORT hook**
"At Gojek I turned a segment we were blindly discounting into a self-funding product — a cost-tiered ride where a longer wait fenced out full-fare riders, proven net-incremental at ~$3.2M via A/B. Your team's work on [pricing / marketplace / growth] is exactly the kind of problem I love."

**Outreach — LONG pitch:** *(lead with the segmentation-not-discount insight → the self-selecting tier + the cannibalization fix → the net-incremental proof → tie to the target's pricing/marketplace work.)*

## Follow-up defense (the sharp ones)
- **"How did you prevent it from just cannibalizing full-fare rides?"** → the wait-time fence + peak-only gating, tuned via A/B; and I measured *incremental-net-of-cannibalization*, not gross, so the $3.2M already accounts for trade-downs.
- **"Why a tier instead of a targeted discount?"** → a discount you *give*; a fence lets riders *reveal* their own price sensitivity, so you don't overpay the riders who'd convert anyway. It's structurally margin-protecting.
- **"How did you handle driver pushback on lower fares?"** → showed the tier raised peak utilization by converting rides otherwise lost entirely — net driver earnings up, so supply stayed aligned.
- **"What was YOUR role vs the pricing/eng team?"** → ⚠️ **the honest version is the whole game — see note.**
- **"What would you do differently?"** → I'd have modeled the cannibalization risk quantitatively *before* the first A/B, instead of learning it from the first cohort — it cost a cycle.

## Interview dimensions
- **Amazon LPs:** Customer Obsession, Dive Deep, Invent and Simplify (fence-as-design), Are Right A Lot, Deliver Results, Frugality (margin protection).
- **MBB / PEI:** *Personal Impact* + a genuinely strong **pricing case** dimension (segmentation, elasticity, cannibalization, incrementality) — this is one of your most *consulting-shaped* stories, because pricing/versioning is a classic case archetype.

---

## ⚠️ What I introduced or changed — read before using
**From your real docs (defensible core):** the price-sensitive segment, funnel + elasticity analysis, **20+ customer interviews**, A/B pricing experiments, the cost-tiered ride tier (cheaper fare / longer wait), **~9% conversion lift**, and **~$3.2M incremental revenue**. All in `freeform_master_v2.txt` (G-PRICING).

**Arcs I invented (high-impact, your call):**
1. **The cannibalization twist (Beat 3)** — that the first A/B showed the tier pulling full-fare riders down and you re-tuned the fence. This is the story's dramatic core and its best PM/strategy signal, but it's invented. It's *very* defensible-sounding (cannibalization is the real risk of any low tier) — but only claim it if it happened or you're ready to own the detail.
2. **"Incremental-net-of-cannibalization" as the metric you designed for** — the $3.2M is real; framing it as explicitly net-of-cannibalization is my addition (and the more rigorous claim).
3. **The wait-time "fence" as the deliberate self-selection mechanism** — I elevated "cheaper fare for longer wait" into an intentional price-discrimination design. Likely close to reality, but the strategic framing is mine.
4. **Driver-utilization alignment (Beat 5)** and **Singapore-first rollout** — invented specifics. Plausible, but confirm markets and the supply-side framing.

**The honesty flag (same as G-LATENCY):** you were a **Senior Software Engineer** at Gojek. This story claims PM ownership of research, pricing design, experimentation, and rollout. Keep it as the aspirational 10/10 target; before it faces an interviewer we build the **defensible variant** calibrated to what you genuinely drove. The gap between the two is your build list — run the WTP study, own the experiment, make the pricing call — so the perfect version becomes simply true.

**On scope:** this is now cleanly separated from G-LATENCY. In a *live* interview you *can* tell them back-to-back as a two-act "I found two problems under one funnel" answer — but keep them as distinct canonical stories so you never reuse the same beat twice in one loop.
