# The Average Is Where Problems Hide — Winning a Duopoly at the Fare-Quote Step
**Gojek** · clusters: marketplace_logistics · lenses: PM · strategy/consulting · data/analytics

> **GOLD-REFERENCE story — 10/10 target build.** This is deliberately elevated well past your raw material: I invented plot arcs, a controlled experiment, and an org-conflict spine to show what a perfect PM/consulting version looks like. **Read the "What I introduced" section at the bottom carefully — a large share of this is aspirational, and you decide what you can honestly own.** Numbers from your real docs vs invented are separated there.

---

## The 15-second version
Gojek was bleeding conversion at the final fare-quote step in Singapore, and the org was about to spend its way out of it — the growth team wanted a promo blitz, engineering said the system was healthy. I didn't buy either. I proved the average latency was hiding a brutal tail that was killing our highest-intent users, reframed speed as a *competitive weapon* in a duopoly, and when the latency fix only half-worked, I dug again and found a second, hidden segment leaving on price. I shipped a budget tier for them and proved the whole thing with a geo-holdout experiment: ~28K incremental monthly rides, and a new metric the org still uses so it never hides behind an average again.

## Situation & stakes
Singapore was a two-horse race — Gojek vs Grab — near-parity on price and driver density, where marginal share came from execution, not economics. Our conversion funnel had a stubborn ~18% drop-off at the fare-quote step: the user requests a ride, we compute a fare, and a large chunk vanish before booking. It was a first-order growth problem, and two camps had already formed. **Growth** wanted to attack it with surge discounts and promo credits — fast, expensive, margin-destroying. **Engineering** pushed back that there was nothing to fix: average quote latency was a healthy 1.3s and every dashboard was green. The promo plan was about to win by default. I thought both were wrong.

## The insight (the non-obvious move)
Two beliefs no one in the room held: first, **the average was lying** — a healthy mean can hide a lethal tail, and tail latency at the exact moment of peak purchase intent is where high-intent users die silently. Second, **in a duopoly, latency isn't a performance metric, it's a competitive one** — when two apps are open at once, you're not racing a benchmark, you're racing Grab to the quote. Reframing a "slow API" as "we're losing a race we didn't know we were in" is what turned an engineering footnote into a marketplace-strategy problem.

## What I did (the plot — diagnosis, twists, and proof)
- **Beat 1 — Broke the average open.** I pulled session telemetry and correlated quote-response time against booking completion, stratified by latency bucket. The mean of 1.3s was masking a **p95 of 3.8s** — and conversion fell off a cliff: **92% under 1.5s → 71% at 1.5–2.5s → 41% above 2.5s.** 5% of sessions were hitting conversion-destroying delays on every request. I took it to leadership not as "our API is slow" but as *"we are showing a blank wall to our highest-intent users at the moment they most want to buy."* That reframe bought me a mandate over the growth team's promo plan.
- **Beat 2 — The competitive twist (why Singapore?).** Abandonment was **2.3x higher at peak hours** and **40% higher in Singapore than in less-contested Indonesian cities.** That pattern doesn't fit a pure tech story — it fits **multi-homing**: in a duopoly, high-intent commuters open both apps and book whoever quotes first. I modeled it: every **100ms** of peak latency reduction ≈ **180–220 recovered bookings/day** in Singapore alone. Latency was a competitive weapon, and I had the elasticity curve to prove it.
- **Beat 3 — The fix that only half-worked (the real test).** I got the roadmap pivoted and shipped the architecture change: replace per-fare full-route computation with **pre-cached pricing tiers for the 12 highest-demand corridors** (60% of peak volume). The trade-off was explicit and mine to own — cached tiers introduced a **±4% fare variance** vs real-time pricing; I built the case that this was within user tolerance and well below competitive sensitivity. p95 dropped **~70%**, to under 1.1s. **But conversion only partially recovered.** The cliff flattened, yet a residual drop-off remained — users who now got an *instant* quote and still walked. A lesser version of me declares victory on the latency win. The data said I wasn't done.
- **Beat 4 — Numbers tell you where, humans tell you why.** I ran a fast round of user interviews on the still-abandoning segment. The pattern was clear and different: **price shock.** During peak surge, they got their fare instantly and left because it exceeded willingness-to-pay — a completely separate problem hiding behind the first. So I shipped a **budget ride tier**: a cheaper fare in exchange for a slightly longer wait, which self-selected the price-sensitive segment *without* cannibalizing riders who valued speed.
- **Beat 5 — Proving it like a perfect PM would.** Rather than claim credit off a correlation, I designed a **geo-holdout experiment** — matched Singapore zones received the latency fix + budget tier while comparable control zones didn't — to isolate *incremental* impact. The clean read: **~28K incremental monthly rides** causally attributable, not just coincident. And I institutionalized the lesson: I got **Time-to-Quote (p95, not mean)** adopted as a first-class marketplace-health metric, so the org could never again let an average hide a cliff.

## The outcome
~28K incremental monthly rides (experimentally isolated), p95 quote latency down ~70%, a price-sensitive segment recovered without margin-dumping promos, and a durable operating change — p95 Time-to-Quote as a tracked marketplace metric — plus the growth team's promo budget redirected to higher-return bets.

## Why I cared / what I learned
I hated that we were about to spend millions papering over a problem we hadn't diagnosed. Two lessons stuck: **the average is where problems go to hide** — always look at the distribution and the tail — and **data tells you where users leave, but only humans tell you why**, which is the difference between fixing one problem and finding the second one nobody saw.

---

## How this one story flexes across roles
| Lens | What you lead with |
|---|---|
| **Product (PM)** | Distribution-level diagnosis, the reframe that won the roadmap, the two-segment plot, and proving impact with a controlled geo-experiment + a new north-star metric. |
| **Strategy / Consulting** | Market-structure analysis (duopoly multi-homing), latency-as-competitive-weapon with an elasticity model, willingness-to-pay segmentation, and redirecting spend from promos to a structural fix. |
| **Data / Analytics** | Averages vs tails (p95), abandonment-cliff stratification, causal design (geo-holdout) over correlation. |

## Renderings

**Resume ammo** *(facts for your resume generator — not finished bullets)*
- Hooks: p95 3.8s hidden behind 1.3s avg; abandonment cliff 92%→71%→41%; multi-homing/duopoly insight (100ms ≈ 180–220 bookings/day); pre-cached corridor pricing (±4% variance trade-off) → −70% p95; budget tier for price-sensitive segment; **geo-holdout experiment → ~28K incremental monthly rides**; institutionalized p95 Time-to-Quote metric.
- Ownership: ⚠️ **see honesty note** — as written this claims PM-level ownership you did not formally hold at Gojek. Calibrate.
- Tracks this arms: PM, strategy/consulting, data/analytics.

**Spoken — SHORT (~30–45s)**
"At Gojek in Singapore, we were losing ~18% of users at the final fare-quote step, and the company was about to throw promo discounts at it while engineering insisted the system was fine — average latency was a healthy 1.3 seconds. I didn't buy it. I broke the average open and found a p95 of nearly 4 seconds — we were showing a blank wall to our highest-intent users. In a two-app market, that's a race we were losing to Grab. I got the fix prioritized and cut tail latency 70% — but conversion only half-recovered, so I dug again and found a second segment leaving on price shock, and shipped a budget tier for them. I proved the whole thing with a geo-holdout experiment: about 28,000 incremental rides a month."

**Spoken — LONG (~2 min):** *(SHORT's spine, then expand each beat: the org standoff → the cliff stratification and the reframe → the multi-homing competitive model → the ±4% cached-pricing trade-off and the partial recovery → the interviews + budget tier → the geo-experiment and the p95 metric. Close on "the average is where problems hide, and humans tell you the why.")*

**Outreach — SHORT hook**
"At Gojek I found our fare-quote conversion problem wasn't price — it was a hidden latency tail losing us the multi-homing race against Grab, and then a second price-sensitive segment underneath it. Proved a ~28K/month incremental fix with a geo-holdout. Your team's work on [marketplace / conversion / pricing] is exactly my kind of problem."

**Outreach — LONG pitch:** *(lead with the average-is-lying + duopoly insight → the two-segment diagnosis you drove → the experimentally-proven outcome → tie to the target's marketplace/growth work.)*

## Follow-up defense (the sharp ones)
- **"How did you isolate impact from everything else changing?"** → the geo-holdout: matched treatment vs control zones, so the ~28K is incremental, not coincident.
- **"Why cached pricing tiers over just faster compute?"** → full-route computation was the latency source; caching the top-12 corridors (60% of peak volume) bought the biggest win fastest. The ±4% fare variance was the conscious trade-off, and I proved it sat below competitive sensitivity.
- **"Why did conversion only partially recover after the latency fix?"** → because a second, independent segment was leaving on price, not speed — which is exactly why I didn't stop at the latency win.
- **"What was YOUR role vs engineering/growth?"** → ⚠️ **the honest version of this answer is the whole ballgame — see note below.**
- **"What would you do differently?"** → run the qualitative interviews *before* assuming the whole cliff was latency — I'd have found the price segment a sprint earlier.

## Interview dimensions
- **Amazon LPs:** Dive Deep (the p95 story is a textbook example), Customer Obsession, Are Right A Lot, Bias for Action, Deliver Results, Insist on High Standards (the experiment).
- **MBB / PEI:** *Personal Impact* — you overturned two entrenched camps with evidence and no positional authority. The tension is the growth-vs-engineering standoff; the "problem-solving" case dimension is the structured, multi-hypothesis diagnosis + causal proof.

---

## ⚠️ What I introduced or changed — read before using
This is the story where fabrication is heaviest, so I'm splitting it explicitly.

**From your real docs (defensible core):** the p95 3.8s vs 1.3s avg, the 92→71→41% cliff, 2.3x peak / 40% Singapore abandonment, 100ms ≈ 180–220 bookings, pre-cached top-12 corridors, ±4% variance, ~70% latency cut, the budget tier, ~28K monthly rides, and the Time-to-Quote metric. These all appear in `STORY_BANK_RICH.md` and/or your interview scripts.

**Narrative scaffolding I invented (plausible, low-risk):** the growth-wants-promos vs engineering-says-fine org standoff, and the leadership-reframe moment. This is connective tissue to create tension; likely close to reality but not in your docs.

**Arcs I invented outright (high-impact, higher-risk — your call):**
1. **The sequential "fix half-worked → dig again" plot (Beats 3→4).** Your docs treat speed and price as *parallel* discoveries; I made them *sequential* because it's a far more compelling and testing arc. This is a storytelling choice, not a recorded fact.
2. **The geo-holdout experiment (Beat 5).** Invented. This is the single biggest upgrade — causal proof is what separates a 7 from a 10 — but it's also the most falsifiable. If you didn't run a controlled experiment, you cannot claim it in an Amazon loop; they will ask about the design and you must be able to defend it.
3. **The elasticity model / "100ms = bookings" as something *you* built** — the number is yours; framing it as your model is my addition.

**The honesty flag (important):** you were a **Senior Software Engineer** at Gojek, not the PM. As written, this story claims end-to-end PM ownership — diagnosis, roadmap pivot, product decision, experiment, metric adoption. That's the *10/10 target*, and it shows you what "perfect" looks like — but before you put this in front of an interviewer, we need to decide the honest ownership line: what you genuinely drove vs contributed to vs are narrating as "we." A story that collapses under "what exactly was your role?" is worse than a humbler true one. My recommendation: keep this as the aspirational north star, then we build a **defensible variant** that's still excellent but that you can own without flinching. That calibration is the next conversation.
