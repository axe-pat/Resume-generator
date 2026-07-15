# Flattening the Peak — Recovering Surge-Shock Riders by Reshaping Demand, Not Discounting It
**Gojek** · clusters: marketplace_logistics · lenses: PM (technical) · strategy/consulting · data/ML

> **GOLD-REFERENCE story — 10/10 target, flipped centerpiece.** Same *problem* as the old G-PRICING (peak-hour price-sensitive abandonment), but the solution is reimagined from a commoditized "cheaper tier" into a surge-forecasting + demand-reshaping play. **This is heavily invented — read the honesty note at the bottom before using a word of it.** It exists to show what a genuine 10/10 solution to this problem looks like. Supersedes `_GOLD_REFERENCE_gojek_pricing_tier.md`, which stays as the record of the real, defensible work.

---

## The 15-second version
At peak hours, Gojek was losing price-sensitive riders who got an instant quote and bailed the moment surge pushed the fare past what they'd pay. The reflex was to discount them — which torches margin *and* fights your own surge algorithm. I saw something else: surge is a short-lived spike, and a slice of that peak demand is *time-flexible*. So instead of a discount, I built a short-horizon surge-forecast model and a "defer-and-save" nudge at the moment of abandonment. The real magic wasn't recovering those riders one by one — it was that shifting the flexible sliver off the peak *lowered the surge multiplier itself*, recovering riders who never saw the nudge. I turned a discount problem into a demand-shaping one, and proved it with a geo-holdout.

## Situation & stakes
Even after we fixed fare-quote latency, a stubborn cohort abandoned at peak: instant quote, then gone the instant surge pricing crossed their willingness-to-pay. In the Gojek-vs-Grab duopoly, every one of those was a rider handed to the competitor. The organizational default was to spend the problem away — surge discounts and promo credits. That "fix" is quietly self-defeating: **discounting during surge stimulates the exact demand that's already outstripping supply**, deepening the shortage, and it trains the whole base to wait for deals. We were pouring fuel on a fire and calling it firefighting.

## The insight (the non-obvious move)
Two observations nobody was connecting. First, **surge is spiky and short-lived** — the multiplier that scared a rider off at 6:02 PM was often materially lower by 6:09. Many abandoners were trying to book in the *worst 5-minute window*, minutes before the fare would naturally settle. Second, **a meaningful slice of peak demand is time-flexible** — they'd trade 5–7 minutes for a lower fare — but the product gave them exactly one way to express that: leave. The reframe: this isn't a pricing problem to be solved with a discount, it's a **demand-timing problem** to be solved by giving flexible riders a way to shift — and, crucially, shifting them *reshapes the peak itself.*

## What I did (the plot — the mechanism, the twists, the systems payoff)
- **Beat 1 — Rejected the discount reflex, and named why it's harmful.** I made the case to leadership that discounting into a surge is fighting our own marketplace: it stimulates constrained demand and erodes margin on riders who'd have paid full fare. The problem wasn't that our price was too high — it was that we were forcing a *binary* (pay peak now, or leave) on riders who had a third preference we never offered: *wait a few minutes and pay less.*
- **Beat 2 — Built the forecasting spine.** I specified a **short-horizon surge-forecasting model** — predicting the surge multiplier 5–15 minutes out per micro-zone from live demand/supply telemetry, historical decay curves, and time-of-day/weather features. And I segmented abandoners into *time-critical* (high WTP, zero patience) vs *time-flexible* (low WTP, real patience), so we'd only ever intervene where it fit.
- **Beat 3 — The intervention: defer-and-save at the abandonment moment.** Instead of a static cheap tier, at the exact point of price-shock I surfaced a nudge: *"Fares here usually drop to about $X in ~6 minutes — reserve now and we'll match you the moment they do."* Accepting riders were held and auto-matched into the predicted lower-surge slot. The rider expresses flexibility by choice; we never discount the ones who won't.
- **Beat 4 — The twist: the model over-promised, and trust cratered.** Early on, surge is noisy — the model sometimes predicted a drop that didn't come, so riders who waited got *burned*, and acceptance collapsed after the first bad experiences. A weaker version ships it anyway on the aggregate lift. I killed the bleeding two ways: I made the nudge **confidence-gated** (fire only when the forecast was high-confidence, even if that meant firing less often), and I added a **price-honor fallback** — if the predicted drop didn't materialize, we honored the quoted lower fare and ate the small delta. Now the promise was safe to trust, which is the only way a behavioral nudge survives.
- **Beat 5 — The systems payoff (why this is a 10, not a feature).** The obvious win was recovering the nudged riders. The real prize was second-order: **deferring the time-flexible sliver off the peak lowered instantaneous demand, which lowered the surge multiplier itself — recovering price-sensitive riders who never saw the nudge at all.** A small, deliberate demand shift flattened the peak and lifted conversion *non-linearly* across the whole zone. I wasn't managing riders one at a time; I was reshaping the demand curve.
- **Beat 6 — Proved both effects, and defended the two-sided risk.** The marketplace/driver worry was legitimate: does deferring demand starve drivers of peak earnings? I proved the opposite with a **geo-holdout** measuring *both* the direct lift (nudge acceptors) *and* the spillover lift (surge reduction for everyone): the deferred rides were incremental (they'd have been lost entirely), and flatter peaks meant higher completion rates and less driver idle-then-churn. Net GMV up, net driver earnings up, surge complaints down.

## The outcome
~9% conversion lift in the price-sensitive peak segment and ~$3.2M in incremental revenue ⚠️ — captured by *reshaping demand*, not discounting it, with a measurable drop in peak surge multipliers and improved driver utilization. And a durable operating idea: peak abandonment became a demand-timing lever the marketplace team could pull, not a discount line-item.

## Why I cared / what I learned
I didn't want to win by bribing users — that's expensive and it's not clever. The lesson that stuck: **in a marketplace, the highest-leverage move is often to reshape the demand curve, not to pay people to sit on it.** A tiny, well-placed nudge that shifts the *flexible* few can move the equilibrium for the *many* — second-order effects are where the real product leverage lives, and most people never look past the first order.

---

## How this one story flexes across roles
| Lens | What you lead with |
|---|---|
| **Product (technical PM)** | Forecast-driven behavioral intervention; the trust-collapse twist and the confidence-gating + price-honor fix; proving direct + spillover lift with a holdout. |
| **Strategy / Consulting** | Marketplace-equilibrium insight (flatten the peak, don't discount it), two-sided net-incrementality, and reframing a cost line (promos) into a demand-shaping lever. |
| **Data / ML** | Short-horizon surge forecasting, time-flexibility segmentation, and an experiment that isolates a *non-linear spillover* effect, not just a direct treatment effect. |

## Renderings

**Resume ammo** *(facts for your resume generator — not finished bullets)*
- Hooks: peak-hour price-shock abandonment; rejected discounting (stimulates constrained demand); short-horizon **surge-forecast model**; **defer-and-save nudge** at abandonment; confidence-gating + price-honor fallback (trust fix); **peak-flattening second-order effect** recovers non-nudged riders; geo-holdout proving direct + spillover lift; ~9% lift / ~$3.2M ⚠️; surge multiplier + driver-idle reduced.
- Ownership: ⚠️ heavily aspirational — see honesty note.
- Tracks this arms: technical PM, strategy/consulting (marketplace), data/ML.

**Spoken — SHORT (~30–45s)**
"At Gojek, we were losing price-sensitive riders at peak — instant quote, then gone the second surge crossed their limit. The reflex was to discount them, but discounting into a surge just feeds the shortage. I noticed two things: surge is a short spike, and a slice of that demand is actually time-flexible. So instead of a discount, I built a model to forecast surge a few minutes out and nudged those riders: 'fares usually drop to about this in six minutes — reserve and we'll match you then.' The real magic was second-order: shifting the flexible few off the peak lowered the surge multiplier itself, recovering riders who never even saw the nudge. I proved both effects with a geo-holdout — net-incremental revenue, and net-higher driver earnings too."

**Spoken — LONG (~2 min):** *(SHORT's spine, then expand: why discounting into surge is self-defeating → the forecast model + flexibility segmentation → the defer-and-save nudge → the trust-collapse twist and the confidence-gating/price-honor fix → the peak-flattening equilibrium payoff → the two-sided holdout proof. Close on "reshape the demand curve, don't pay people to sit on it.")*

**Outreach — SHORT hook**
"At Gojek I turned peak-hour price-shock abandonment from a discount problem into a demand-shaping one — a surge-forecast nudge that shifted flexible riders off the peak and *lowered the surge for everyone*. Proved net-incremental with a geo-holdout. Your team's marketplace/pricing work is exactly my kind of problem."

**Outreach — LONG pitch:** *(lead with the "don't discount the peak, flatten it" insight → the forecast + nudge mechanism → the equilibrium payoff and two-sided proof → tie to the target's marketplace/pricing/ML work.)*

## Follow-up defense (the sharp ones)
- **"Why not just discount the price-sensitive riders?"** → discounting into a surge stimulates demand that's already short of supply, deepens the shortage, and erodes margin on riders who'd have paid full fare. Deferring flexible demand attacks the root — the imbalance — instead of paying to paper over it.
- **"How is this different from Uber Wait & Save?"** → Wait & Save trades match distance for price *right now*; this *forecasts surge decay* and defers to a cheaper future moment — and the value driver isn't the individual defer, it's the peak-flattening spillover that recovers non-participating riders.
- **"How did you isolate the spillover effect from the direct one?"** → the geo-holdout measured zone-level conversion, so I could separate nudge-acceptor lift from the surge-reduction lift among riders who never saw the nudge.
- **"What broke, and how did you fix it?"** → early forecasts over-promised and burned rider trust; I confidence-gated the nudge and added a price-honor fallback so the promise was always safe to accept.
- **"What was YOUR role?"** → ⚠️ **see honesty note — this is the crux for this story.**

## Interview dimensions
- **Amazon LPs:** Invent and Simplify (the equilibrium reframe), Dive Deep (surge decay + segmentation), Think Big (second-order effect), Are Right A Lot, Deliver Results, Earn Trust (the fallback fix).
- **MBB / PEI:** an unusually strong **problem-solving/case** dimension — marketplace equilibrium, forecasting, two-sided incrementality — plus *Personal Impact* in overturning the discount reflex.

---

## ⚠️ What I introduced or changed — read before using (heaviest yet)
This is the most invented story in the engine. Be clear-eyed about it.

**Real anchors (from your docs):** the *problem* (peak-hour price-sensitive abandonment) and the *outcome metrics* (~9% conversion lift, ~$3.2M incremental revenue) — from `freeform_master_v2.txt` (G-PRICING). That's it.

**Everything else is invented:** the surge-forecasting model, the defer-and-save nudge, the confidence-gating/price-honor trust fix, and — most importantly — the peak-flattening equilibrium effect and the spillover measurement. Your *real* solution was a cost-tiered ride (the tier file). This story replaces that solution wholesale to show what a genuine 10/10 mechanism looks like for the same problem.

**The honesty flag — bigger here than anywhere.** This isn't just a title/ownership stretch; it's a *different solution than the one you shipped*. Two clean ways to use it, both legitimate, neither being "claim it verbatim and hope":
1. **As a north star / build list.** This is the caliber of solution to aim for in your *current* FlareX/MBA work, where you can actually own something like it end to end — so a future story is simply true.
2. **As a genuine reframe you drove.** If, in reality, you or the team *did* explore demand-timing/surge-smoothing (even partially), this becomes a defensible story with real bones and we calibrate the claims down to what happened. If it's purely aspirational, it cannot go in front of an interviewer as fact — the forecasting model and spillover experiment are exactly what a sharp interviewer will drill, and they must be real.

**My honest recommendation:** keep *both* pricing files. The tier version is your defensible, true story (reframed around the anti-cannibalization rigor). This peak-flattening version is the 10/10 exemplar — the thing that shows you (and the engine) what "profound solution" actually looks like — and a template for the kind of work that makes the next story effortless. Which of these two becomes your *used* story depends on what you can honestly own, and that's your call, not mine.
