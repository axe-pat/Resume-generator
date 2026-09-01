# FLUO STORY POOL V1

> Built 28 Aug 2026. Replaces the four one-line variants in `FLUO_RESUME_ENTRY_REVIEW.md`.
> Seven stories, drafted as narratives first, bullets second.
>
> **Why this document exists.** The prior Fluo entry was written from
> `Fluo_Work_Summary_Akshat.docx` and `Fluo_Context_Handoff.md` only. Neither the
> 57-page playbook, the 18-slide strategy deck, the assessment deck, the eleven-directions
> model, the UX package, nor the live app were in the source hierarchy. Roughly 90% of the
> evidence base was invisible to every prior run, including the kickoff prompt's own
> candidate-family list, which was assembled from the handoff. That list is void.
>
> **Authority boundary.** This document governs evidence and candidate stories, not a fixed
> resume placement. Placement is decided per application. The only externally safe partnership
> statement today is `secured a USC partnership`. The exact office, counterparty wording, scope,
> date, and written status are still being worked. Any more specific institutional mechanics in
> the narrative below are research notes, not resume-ready claims.

---

## Source hierarchy (corrected)

| Rank | Source | Date | What it carries |
|---|---|---|---|
| 1 | The live app (16 screenshots, `Fluo material/app_screenshots/`) | Aug 2026 | What actually shipped |
| 2 | `Fluo_Assessment.pptx` (12 slides) | 25 Aug 2026 | Product audit, the acquisition/retention split, the eight-week plan |
| 3 | `Fluo_Seven_Directions.md` (11 directions, 2 parts) | Aug 2026 | Revenue modeling, market-contraction test, credit-ladder analysis |
| 4 | `Fluo Settling Plan P1 MVP Playbook_Nil.pdf` (57pp) | 16 Aug 2026 | Strategy, segmentation, lifecycle, engagement rules |
| 5 | `source_docs/fluo_settling_plan_concept_15.html` | Jul 2026 | The USC artifact. Intake, 35 steps, two personas, CPT reroute, university track |
| 6 | `Fluo_UX_Package_v3.html` | Aug 2026 | 33-screen spec, 13-frame onboarding, vocabulary lock |
| 7 | `Fluo_AI_Settling_Guide_Strategy.pptx` (18 slides) | Jun 2026 | Market frame, SWOT, competitive set, roadmap |
| 8 | `source_docs/Fluo_Work_Summary_Akshat.docx` | 10 Aug 2026 | Jul–early Aug workstream record |
| 9 | `Fluo material/Fluo_Context_Handoff.md` | 21 Aug 2026 | State, relationships, legal findings |

`MBB_CONTENT_PACK.md` is **not** a factual source. Its "landed USC partnership" language predated
the actual close and must not be cited as evidence for it.

---

## The finding that reordered everything

**What is most impressive in the app is not a clever decision. It is the surface with the
highest stakes carrying data nobody else can assemble.**

Earlier passes ranked surfaces on *was this a smart call*. That produced things like "put a
patrol zone on a map," which is a footnote, not a story. Ranked instead on **stakes plus
non-replicability**, the order is:

1. **Housing.** The only surface attached to a $12,000–$45,000 annual decision, made sight
   unseen from 8,000 miles away, carrying information (patrol-zone coverage, per-ring rent
   benchmarks, senior verification) that cannot be scraped or bought.
2. **The ambassador roster.** The hardest thing achieved, and the thing sitting underneath
   housing. Strip it and Trojan Verified is a listings page with a map.
3. Everything else.

**The general rule this produced, which governs every bullet below:** lead with the insight
that made the mechanism necessary, never with the mechanism. The mechanism is the part
anyone would have executed once they had the insight, so it is the least impressive half.

---

# THE STORIES

---

## 1 · We lose the moment they land
**FL-INSTITUTIONAL** · *outcome currency: institutional distribution, cohort density*
**Strongest story in the corpus.**

**The one line.** Fluo was building a settling plan for students who had already arrived. The
product could never win that user, because the moment a student lands they have peers to ask
and they trust a person over an app. The only window Fluo could own was pre-arrival, and the
only entity that reaches a student pre-arrival is the university, which turned out to already
be running Fluo's exact workflow badly.

**The setup.** The roadmap had settling as the wedge and the plan as the retention surface.
The unexamined assumption underneath was that the app competes for the student's attention
*after* they land.

**The chain.** Four links, each forcing the next.

1. **Timing.** Nobody uses a settling plan three months into the program. The value is
   concentrated in a window that starts closing the day they arrive.
2. **Trust.** Worse than timing. Once a student is on campus they have a network, and on the
   questions that actually matter (visa, work authorization, money) they ask a person. Fluo
   does not lose that fight on features. It loses it structurally, and no amount of product
   work reverses it.
3. **Channel.** So the only defensible acquisition moment is pre-arrival, when the student has
   nobody to ask yet. But that student is 8,000 miles away, is not searching for Fluo, and is
   unreachable through any channel a five-person pre-seed company can buy.
4. **The institution.** Exactly one entity already holds that student at that moment, and the
   student has already opted in to hearing from them: the program office.

**The commonality that made it a deal instead of a pitch.** Every program office already sends
an identical pre-arrival checklist and chases completion by email all summer. It is a static,
unordered page: no dates, no sequence, no idea what blocks what. When students hit trouble they
take it to WhatsApp, where the office cannot see it, cannot help, and the next cohort learns
nothing. The same list rendered live shows how many of your class have finished each item and
where people are getting stuck.

**Three-way payoff, which is why it closed.**
- *University:* higher completion, fewer repeat questions, first visibility into where students
  stall. Staffing relief on work they already carry.
- *Fluo:* downloads at the one moment they can be captured, the university's credibility stamped
  onto a pre-seed app, and cohort density. The community layer needs roughly 15 people per step
  before it shows anything real, and 150 users scattered across every school clears no step.
  One office delivers a whole class at once.
- *Student:* the answer sits in the app instead of a WhatsApp thread.

**Execution.** Built the pitch as a working product rather than a deck: their own static page
beside the same items live and dated, cohort progress on each. Split the ask so step one needed
no permission at all (build from what is already public, students self-report, nothing flows
from the university, so there is no agreement to negotiate and nothing for IT to review). The
only ask is a mention in an email already going out. A USC partnership is now confirmed; the
exact outreach path, counterparty, scope, timing, and written status remain open.

**What is pitchable.** Lead with *the product could not win the user it was built for, and the
reason was trust, not features.* That is a hard thing to conclude about your own roadmap, it is
genuinely non-obvious, and everything downstream is a consequence. The closed partnership is
the proof the reasoning was right, not the story itself.

*Angles: PM (product-market timing, trust ceiling) · BD and strategy (channel derived from a
constraint) · consulting (deal design where the ask costs the counterparty nothing).*

**Source:** `fluo_settling_plan_concept_15.html` ("The way in"), `Fluo_Assessment.pptx` s5 and
s10 + notes, `Fluo_Work_Summary_Akshat.docx` Workstream 3.

---

## 2 · The app is not the business
**FL-BUSINESS** · *outcome currency: capital allocation, roadmap sequencing*

**The one line.** The founder asked what Fluo is in three years. Eleven revenue lines modeled to
unit economics returned an answer she had not asked for: the settling app is a customer-acquisition
and data-capture layer, and the business underneath it is international-student housing finance
moving into credit.

**The setup.** Five people, no capital, no revenue, and a founder with 23 years in payments who
had a fintech destination in mind but no sequence to reach it.

**The insight.** Everyone reads a shrinking market as uniformly bad news. New international
enrolment down 17%, applications down another 10%, and graduate students, Fluo's actual user,
are the worst-hit segment. The non-obvious consequence is that it does not make everything
worse, it **sorts**. Any line whose revenue scales with new arrivals is fighting the tide. Any
line whose revenue scales with the installed base, or with how hard people compete over a
shrinking pool, has a tailwind.

That single test reorders the entire list. It puts a lease-guarantee product on top, because
fewer international students means landlords compete harder for the ones who exist, so a product
that lets a landlord approve an otherwise-declinable tenant *appreciates* as the market
contracts. Every other idea on the list gets worse.

**The uncomfortable conclusion, delivered anyway.** The settling app is not the business. It
should be resourced as an acquisition layer rather than treated as the product.

**Then she overruled it.** Her call: consumer app for traction, raise, then embed fintech,
because starting with fintech means no users to prove anything and a lot of competitors. Rather
than defend the conclusion, Part Two answers her question instead: what makes a student open
this app every week, inside eight weeks, with five people and no capital. Six new filters,
anything failing two is out. The document records that Part One was correct and deferred by
founder decision, not wrong.

**The finding that came out of the second pass**, the sharpest line in the corpus: every
international-specific problem is a transition (arrival, SSN, CPT, OPT, graduation) and
transitions are episodic by definition. Every genuinely weekly behaviour is already occupied by
WhatsApp, Instagram, DoorDash, LinkedIn, Chase. So international-specific wins acquisition, and
something else has to win retention. That is the whole problem.

**What is pitchable.** Two beats, and the second is what makes it rare. First, *told the founder
the product she asked me to build is not the business, with the model behind it.* Second, *when
she overruled me I re-ran the analysis against her constraint instead of relitigating mine.*
Conviction plus deference to the person who owns the decision. Almost nobody can evidence both,
and consulting and leadership-program interviewers screen for exactly that pair.

*Angles: consulting · BizOps (revenue-line modeling) · corporate strategy (market-contraction test).*

**Source:** `Fluo_Seven_Directions.md` (base assumptions, "the one market fact", ranking,
Part Two filters), `Fluo_Assessment.pptx` s2.

---

## 3 · Right destination, wrong opening move
**FL-CREDIT** · *outcome currency: founder influence, capital discipline*

**The one line.** The founder wanted to ship a $5,000 instant credit line. The analysis agreed
with where she was going, showed the product as specified would select for the borrowers least
able to repay, and handed back a three-stage ladder reaching the same destination on data Fluo
would own by then.

**The setup.** Her signature product, her domain, 23 years of underwriting experience against
none. The question she put on the table was whether it repeats what constrained MPOWER and Prodigy.

**Being precise about why it does not.** A $2,000 line over six to twelve months, repaid while
enrolled, by a borrower physically on a campus you have a relationship with, is a different
asset from a $40,000 loan repaid after graduation from anywhere on earth. Loss severity differs
by twenty times. And MPOWER's constraint was never defaults: they securitised $313.2M with
A-rated senior notes. It was capital supply against a long-duration asset.

**So the instinct was right. The problems were elsewhere, and finding them was the work.**

- **Adverse selection, the real one.** The students who most want $5,000 fast are the ones with
  no family cushion and no other option. Demand is loudest exactly where credit quality is
  worst, and any product leading with speed selects for it.
- **Ability to repay is legally capped.** An F-1 student's entire lawful US income is a
  20-hour campus job.
- **Unit economics are break-even at best.** ~$200/yr of interest against ~$80 expected
  charge-off and ~$120 cost of capital.
- **"Instant" is the wrong promise.** Instant means underwriting on nothing. The actual edge is
  the opposite: *fast because we verified you six months ago.* The I-20 financial certification,
  the funding source, the lease, six months of on-time rent. Approval feels instant to the
  student because the work happened during settling.

**The handback.** Secured card now, rent reporting at month six, unsecured line at month twelve
to eighteen. Right destination, wrong opening move, and anyone skipping to stage three is
underwriting on nothing.

**What is pitchable.** *Reframed the founder's flagship product from a speed promise into a
verification promise.* Never said no. Found the version of her idea that is actually defensible
and gave it back better than she brought it. The adverse-selection line is the memorable half
and it is provable from first principles, so it survives any drill-down.

*Angles: consulting (disagreeing upward) · fintech and technical PM · BizOps. Also the best
"disagreed with a senior stakeholder" behavioral answer available.*

**Source:** `Fluo_Seven_Directions.md` §5.

---

## 4 · Trojan Verified Housing
**FL-HOUSING** · *outcome currency: partner supply, proprietary data*
**The most impressive surface in the product.**

**The one line.** Housing is the only decision in an international student's first year worth
$12,000 to $45,000, it gets made from 8,000 miles away by someone who has never seen the city,
and it is the one surface where Fluo knows something a listing site structurally cannot.

**The setup.** The June deck named housing as pain number one (30 to 40 hours wasted, scams, no
SSN) and listed the partners as *"Lorenzo / Element / University Gateway (to be confirmed)."*
Three names, none closed.

**Why it was hard.** Two supply problems at once. Buildings had to agree to be verified, and
students had to agree to do the verifying. Neither has an obvious reason to say yes to a
pre-seed app with 150 users.

**The pitch that made buildings closeable.** Not review control, which no leasing office grants.
Instead: aggregate 10,000+ reviews across platforms, distil them to safety, landlord
responsiveness and real costs, and *"we can't control public reviews, but we amplify real
positive student experiences to promote your housing."* Upside with no editorial risk, which
is the only version a property manager can say yes to.

**What shipped.** Lorenzo, Jasper and University Gateway live and verified by 16 August. Element
out, Jasper in: that swap is the residue of real BD, one prospect lost and one found. Listings
spanning $1,028 to $3,750 a month. Per-ring one-bedroom benchmarks (USC $2,450, DTLA $2,700,
K-Town $2,200) so a student can separate a fair price from a markup on day one. Free Lyft Zone
flags. And the USC DPS patrol zone as a first-class map layer.

**Why the DPS layer is the point.** Not because it is a safety feature. Because it is the single
piece of information a student cannot get from Zillow, from a WhatsApp group, or from a campus
tour, since it requires knowing how the university's own police coverage is drawn. It is the
proof the surface was built by someone who is actually at USC, and it is why a citywide
competitor cannot copy the page even with ten times the listings.

**What it became.** The housing surface records which building every student lives in. That is
the routing layer for anything physical (one runner drops 25 meals in one lobby where a citywide
competitor drives across LA) and it is the counterparty list plus underwriting input for the
lease-guarantee product that ranked first in the revenue model.

**What is pitchable.** Lead with stakes and asymmetry: the only surface tied to a five-figure
decision, carrying data a competitor structurally cannot assemble. The BD is the proof, since a
partner list reading "to be confirmed" in June is three verified buildings live in August.

*Angles: consumer PM · marketplace supply · BD · data strategy.*

**Source:** app screenshots 13–16, `Fluo_AI_Settling_Guide_Strategy.pptx` s11, playbook p13–14,
`Fluo_Assessment.pptx` s3, `Fluo_Seven_Directions.md` §1 and §10.

---

## 5 · The credibility a pre-seed company cannot earn
**FL-AMBASSADORS** · *outcome currency: borrowed credibility, field capacity*
**The hardest thing achieved, and the thing sitting under story 4.**

**The one line.** Five USC students put their real names, schools and graduation years on camera
for an app with 150 users and no brand. The win is not that they posted. The win is that a
company with no track record now carries credibility it could not otherwise buy, and every other
surface becomes believable because of it.

**Why this is the hard part.** Fluo's only stated moat is trust. A pre-seed app asking an
international student to commit to $2,500 a month of housing has no standing to be trusted.
A verified review from a named senior at your own school *is* standing. It cannot be bought
with ad spend. Zolve has raised $406M and cannot manufacture USC senior endorsements, because
credibility at a campus is not a purchasable input.

**The design that made it work.** Two ambassador roles, deliberately separated. Second-years
carry credibility precisely because they never used the product and cannot claim to. First-years
supply proof-of-use once they have real progress worth showing. Conflating the two is exactly
what makes ambassador programs read as paid shills, and the separation is what keeps the
guidance credible.

**What shipped.** Preet Sadhwani USC '27 (health insurance, settling, packing, 1:09), Aditi Dora
USC '26 (housing search, 1:14), Gautham Anand USC '27 (securing an internship, 1:40), Elina
Salyakhova USC '27 (money mistakes, 1:51), plus Xinran. Categories map exactly to the product's
pillars: Settling In, Housing, Careers, Finances.

**What it compounds into, and this is why it ranks second overall.**
- It is what makes Trojan Verified actually verified. Strip the roster and housing is a listings
  page with a map.
- It is the field capacity for local BD. Ten ambassadors at four independents each is thirty
  merchants in two weeks, the only reason a five-person company can attempt a local marketplace
  at all. `Fluo_Assessment.pptx` s3 states it directly: *"The videos are not the asset. The
  ambassador roster is."*
- It is the supply side of the graduation flywheel. The terminal node of the shipped Journey
  path is literally "become the senior."

**What is pitchable.** Lead with credibility transfer, not with recruiting. *Borrowed the
institutional and peer credibility a pre-seed company cannot earn on its own.* Then the two-role
design as the mechanism. The count of five is evidence, not the story.

*Angles: GTM · community and marketplace supply · brand and trust · consumer PM.*

**Source:** app screenshots 3 and 12, `Fluo_Work_Summary_Akshat.docx` (ambassador model),
`Fluo_Assessment.pptx` s3 and s9, `Fluo_Seven_Directions.md` (Part Two assets).

---

## 6 · The job that unlocks the number
**FL-PLAN** · *outcome currency: user insight, shipped scope*

**The one line.** The founder had rejected a static checklist and wanted gamification. The
failure was structural, not motivational, and the proof was a dependency almost no international
student knows exists: your on-campus job is what unlocks your SSN, because Social Security will
not issue a number without an employment letter.

**Why it matters.** Students treat the campus job as optional pocket money, start looking in
week three, and their SSN arrives a month late. Everything downstream slips with it: direct
deposit, first credit card, the start of a US credit file. A student who understood one
dependency finishes the semester with a credit history. A student who did not starts building
one in the middle of spring recruiting.

**What came out of it.** Adding points to static content leaves it static. The real defect was
that no item on the list knew what any other item blocked. So: a twelve-question intake deciding
which steps *exist at all*, not merely their order. Two students, identical questions, genuinely
different plans (20 steps for one; 15 plus an entirely different ITIN and Form 8843 route for
the other). A plan that reshapes mid-journey: campus job collapses, the CPT branch replaces the
SSN chain, three downstream dates slide (SSN card 5 Oct → 24 Oct, direct deposit 8 Oct → 27 Oct,
first credit card 26 Oct → 14 Nov). *Same destination, different route.* No model call anywhere
in the engine, deliberately, so every date is auditable and it matches the founder's
curated-presets positioning.

**Shipped** as 90 dated moves across five chapters, carrying real amounts (SEVIS $350, DS-160
$160, LAX transit $35–50), URGENT/MED/LOW triage, locked future weeks, and a Customize button.
And the proof the reframe survived to production: the UX package locks the vocabulary so the
words "checklist" and "tasks" never appear in the interface. She rejected a checklist in July;
by launch a student cannot find the word.

**What is pitchable.** Lead with the dependency. It is the most memorable thing in this corpus
and it does what no metric can: it proves you understood a user whose life you had to learn from
scratch. An interviewer remembers it after the call ends.

**Honest caveat.** This ends in a shipped product, not an outcome. It carries on insight, and
needs a story beside it that carries on impact.

*Angles: consumer PM (user insight) · technical PM (dependency modeling, the deliberate no-AI
tradeoff) · zero-to-one.*

**Source:** `fluo_settling_plan_concept_15.html`, `Fluo_Work_Summary_Akshat.docx` Workstream 1,
`Fluo_UX_Package_v3.html`, app screenshots 1–2 and week views.

---

## 7 · The number I told her not to trust
**FL-SOURCING** · *outcome currency: coverage, disclosed risk*
*Already on the McKinsey resume, unchanged. Still the cleanest technical-judgment story.*

**The one line.** Built a job feed off public ATS endpoints cross-referenced against DOL H-1B
filings, then told the founder unprompted why the headline number was weaker than it looked.

**What was built.** 31 companies live from 230 candidates, 8,145 postings, zero duplicates on
re-run, full refresh in roughly three minutes, employer list derived from public DOL H-1B LCA
data filtered to SoCal worksites. Explicitly rejected LinkedIn and Playwright session automation
on terms-of-service and ban-risk grounds.

**The disclosure, unprompted.** 17 of 31 sat on vendor-documented APIs (Greenhouse, Lever,
Ashby) while 14 relied on undocumented Workday endpoints, a materially greyer position. 31 was
framed as a coverage floor for a working demo, never a market-wide capture rate. The bottleneck
was named as manual per-company ATS and slug mapping, not engineering. And the H-1B caveat was
held non-negotiable: sponsorship history is a company-level signal, never a promise that a
specific role sponsors.

**The proposal.** A bounded 100-company calibration study to replace the estimate with a
measured figure at roughly ±10 points, tightening to ±7 at 200.

**The strategic upgrade** (`Fluo_Assessment.pptx` s10). The career product should not be a job
board: Handshake, LinkedIn and every AI-apply startup win that fight and USC's own alumni portals
are graveyards. The differentiated version is **employer sponsorship evidence**, and this
prototype is the proof it can be built.

*Angles: technical PM · data platform · diligence.*

**Source:** `Fluo_Work_Summary_Akshat.docx` Workstream 4, `Fluo_Assessment.pptx` s10.

---

## 8 · Interviews said value; usage exposed discovery
**FL-FIELD-VALIDATION** · *outcome currency: customer discovery, behavioral corroboration, experiment design*

**The one line.** Sixty conversations with new and returning students at Lorenzo showed that
live offers made sense once surfaced but were difficult to discover. Live usage carried the
harder signal: only 3 of 20 spots on Fluo's first merchant offer were claimed.

**The decision.** Separated awareness from demand instead of treating low redemption as a verdict
on the offer itself. The next step was a receipt-verified retest, not a paid card-linked build.

**Why it matters.** The strength is the closed evidence loop: direct customer conversations,
behavioral corroboration, a consequential diagnosis, and a cheaper next test. Neither interview
enthusiasm nor one weak usage number is allowed to decide the roadmap alone.

**Source:** user-confirmed Lorenzo move-in fieldwork (60 new and returning students);
`Fluo_Assessment.pptx` and live-app Cafe Dulce offer (3 of 20 claims);
`Fluo_Seven_Directions.md` (receipt-verification test sequence).

---

# THE BULLETS

## Recommended, the single high-altitude bullet

The altitude is deliberate: Fluo's differentiator against FlairX and Gojek is not scale, it is
**scope**, so the bullet spans the engagement rather than one project. Scope-only bullets score
4 on the internal scorer ("scope-claiming opener without mechanism"), so each carries one hard
external anchor (USC) that makes the scope claim checkable.

**Option A — scope-first** · ACTION-FIRST · 245 chars
> Reset the product roadmap by separating what acquires an international student from what retains one, since settling is a one-time transition while the weekly habit already belongs to WhatsApp; secured a USC partnership as the acquisition channel.

**Option B — outcome-first** · DIAGNOSTIC
> Secured a USC partnership after concluding Fluo could not win students post-arrival, when they trust peers over an app; reset the roadmap around pre-arrival acquisition and long-term retention.

*B is stronger for PM, since the insight is the opener and the insight is the differentiated
part. A is stronger for consulting and BizOps, since it leads on the reframe.*

## Second bullet, when Fluo sits in Experience

A role header with one bullet reads as a role that was not much; two is the minimum that reads
as employment and the maximum before it reads as padding. The second must carry a **different
value signal**, never another strategy line.

**Consulting, BizOps, leadership programs** · 223
> Redirected the founder's flagship $5,000 instant credit line into a secured-card ladder after showing demand concentrates where repayment capacity is weakest, with an F-1 student's lawful income capped at a 20-hour campus job.

**Consumer / growth PM** · 216
> Surfaced that an on-campus job gates the SSN application, because Social Security will not issue a number without an employment letter, so students treating campus work as pocket money lose a month of financial runway.

**Technical / data PM** · 250 · *unchanged, already on the resume*
> Built a compliant job-sourcing prototype pulling 8,145 live postings from 31 DOL-verified H-1B sponsors; flagged that 14 relied on undocumented endpoints and proposed a 100-company study to replace estimates with a coverage figure accurate to ±10 points.

## Bank, by story

**FL-INSTITUTIONAL**
- *[distribution-strategy]* DIAGNOSTIC — Identified institutional distribution as the one channel where a single relationship can reach an incoming cohort; secured a USC partnership after reframing the product around pre-arrival acquisition.
- *[enterprise-BD]* DIAGNOSTIC — Matched Fluo to universities' recurring pre-arrival checklist workflow; positioned the product as support for work institutions already carry and secured a USC partnership.
- *[product-as-pitch]* ACTION-FIRST — Built the partnership pitch as a working product artifact, showing how a static pre-arrival checklist could become a live, dated workflow with cohort progress.

**FL-BUSINESS**
- *[market-structure]* DIAGNOSTIC · 211 — Reframed a contracting market as the ranking test after new international enrolment fell 17%, since a product that helps a landlord approve an otherwise-declinable tenant appreciates as the applicant pool shrinks.
- *[capital-allocation]* ACTION-FIRST · 197 — Modeled 11 revenue directions to year-three unit economics and ranked them on feasibility at five people, then benched 11 more with a stated reason each so the founder could see what had been rejected.
- *[contract-structure]* DIAGNOSTIC · 205 — Found a 9x revenue gap inside partnerships already signed: an insurance affiliate bounty pays roughly $75 once, where a licensed producer earns about $356 a year for as long as the policy renews.
- *[scope-discipline]* CONTEXT-FIRST · 183 — Rewrote the growth plan against the founder's constraint after she ruled out a fintech-first launch, filtering every option through six tests and recording which test each rejected idea failed.

**FL-HOUSING**
- *[partnership-BD]* ACTION-FIRST · 205 — Converted a partner list marked to-be-confirmed into three verified buildings live, pitching leasing offices on amplified student reviews, the only form of review participation a property manager will grant.
- *[proprietary-data]* ACTION-FIRST · 200 — Built the one housing surface a listing site cannot copy, carrying campus patrol-zone coverage and per-ring rent benchmarks across a $1,028 to $3,750 spread, for students choosing a lease sight unseen.

**FL-AMBASSADORS**
- *[credibility-transfer]* ACTION-FIRST · 195 — Recruited five named USC seniors onto camera to lend a pre-seed app credibility it could not earn, keeping them separate from first-year users so their guidance never read as a paid endorsement.
- *[moat]* DIAGNOSTIC · 180 — Made verified housing actually verified by building the senior roster behind it, the one asset a competitor holding $406M cannot manufacture at a campus it does not attend.

**FL-PLAN**
- *[zero-to-one]* ACTION-FIRST · 192 — Shipped a 90-move settling product across five chapters for a founder who had already rejected a static checklist, locking that word out of the interface so students see dated moves and a journey.
- *[systems-design]* DIAGNOSTIC · 227 — Diagnosed the failed checklist as a structure problem, since no item on it knew what any other item blocked; rebuilt it as a dependency plan where a collapsed campus job reroutes through CPT and slides three downstream dates.

**FL-SOURCING**
- *[competitive-positioning]* DIAGNOSTIC · 197 — Repositioned the career product away from a job board Handshake already owns and toward employer sponsorship evidence, built on a prototype pulling 8,145 postings from 31 DOL-verified sponsors.

**FL-FIELD-VALIDATION**
- *[discovery-usage-loop]* DIAGNOSTIC — Interviewed 60 new and returning students at Lorenzo move-in and found that live offers made sense once surfaced but were difficult to discover; confirmed the pattern in usage data, with just 3 of 20 spots claimed on Fluo's first merchant offer, then separated awareness from demand and designed a receipt-verified retest.

---

# ENTRY SHAPE

**Title.** The founder has confirmed title flexibility, but the current default does not use a
title because Fluo sits in Skills/Additional Information or a compact project slot. If a future
application deliberately promotes Fluo into Experience, agree on the public title first and use
two independently defensible bullets. Plausible future options include `Product Lead` for PM and
`Product & Strategy Lead` for consulting or BizOps.
- **Avoid `Chief of Staff`.** Excellent for an MBA leadership program, actively harmful elsewhere,
  because it reads as founder-adjacent rather than product-owning. The positioning problem is
  proving product ownership, and this swaps one misread for another.

**Future Experience header, only after explicit approval:** `FLUO | Product Lead | Jul 2026 – Present | Los Angeles, CA`
**Descriptor:** `Fluo (pre-seed fintech, international student life platform)`

**Placement, by lane.**

| Lane | Section | Bullets | Use |
|---|---|---|---|
| PM, startup, 2027 new-grad | **Skills / Additional Information** by default | 1 | Choose the most JD-relevant story; promote only deliberately |
| McKinsey and consulting | **Projects & Consulting** | 1 | Usually Option A |
| Amazon shared leadership resume | **Skills & Interests** | 1 | Option B, current decision |
| Consumer / growth PM | **Skills or Projects** | 1 | Option B or FL-PLAN `[user-insight]` |
| Lane C campus roles | **Skills / Additional Information or Projects** | 0–1 | Use only when the USC, student, analytics, communications, or founder-work angle helps |

Fluo's location is therefore flexible, not random: the section and story must earn their space
against the JD. It does not automatically enter Experience, and it can be omitted when a stronger
role-specific proof exists.

**Why Projects for consulting.** Consulting resumes are read for trajectory and brand, and the
Experience block is stronger undiluted as FlairX, Gojek, Hevo, Intuit, Optum. Five clean
employment entries beat four plus a startup. Section context also sets the bar: a Fluo bullet
under Experience beside the strongest scaled-company proof can read as the weakest line on the
page, while the identical bullet under Projects can read as unusually strong for a project.

**Guardrails.** Never two variants from the same story. Never two strategy bullets in a row
(near-duplicate). Never a third Fluo bullet.

---

# HONEST RATING against the current resume

Benchmark is `profile/handcrafted_resumes/Akshat_Pathak_McKinsey_FT_Associate.docx`.

| Existing bullet | Score |
|---|---|
| FlairX $1.2M pilot | 9.5 |
| FlairX 70% cost cut, 55%→80% margin | 9.5 |
| Gojek $110M supply model | 9 |
| Gojek 9% conversion, $3.2M | 9 |
| Hevo batch-first pivot | 9 |
| Fluo sourcing prototype | 8.5 |
| Fluo GTM resize *(carries an attribution problem)* | 7.5 |

| New variant | Score | Verdict |
|---|---|---|
| Option B (USC + roadmap reset) | **9** | **Clears.** Only Fluo bullet that stands beside the $1.2M line without shrinking |
| Option A (roadmap reset + USC) | **9** | **Clears** |
| FL-BUSINESS `[market-structure]` | **9** | **Clears.** McKinsey-shaped: one public fact, one non-obvious inversion, no fake metric |
| FL-CREDIT (credit-line redirect) | **8.5–9** | **Clears.** Drops to 8 if she has not accepted the recommendation |
| FL-PLAN `[user-insight]` (SSN) | **8.5** | **Clears**, but carries no number. Second bullet, never first |
| FL-PLAN `[zero-to-one]` | **8.5** | **Clears** |
| FL-SOURCING `[technical-diligence]` | **8.5** | Already there, still good |
| FL-AMBASSADORS `[credibility-transfer]` | **8** | Borderline. Strong for consumer PM, thin for McKinsey |
| FL-HOUSING `[partnership-BD]` | **8** | Borderline. Three buildings reads small beside $110M |
| FL-BUSINESS `[capital-allocation]` | **8** | Good, competes with `[market-structure]` and loses |

**Structural read.** Fluo will never win on magnitude against Gojek or FlairX. It wins on
**ownership breadth and institutional closes**, so every Fluo bullet must carry either a named
counterparty or a company-level decision. Any bullet describing a feature, however good the
feature, loses to a $1.2M line sitting two inches above it.

---

# METRIC CANON

⚠️ marks anything an interviewer can drill or that needs confirmation before shipping.

| Figure | Story | Status |
|---|---|---|
| A USC partnership is confirmed | FL-INSTITUTIONAL | Publicly safe only at this altitude; exact office, counterparty wording, scope, date, and written status remain open |
| Cold-email path, school/program identity, timing, and response sequence | FL-INSTITUTIONAL | Internal working detail; do not use externally until confirmed |
| 412 students at USC this fall | FL-INSTITUTIONAL | real (concept_15) |
| ~15 people per step for cohort density | FL-INSTITUTIONAL | real, design threshold |
| New international enrolment down 17%, applications down 10% | FL-BUSINESS | real, public (NAFSA / IIE) |
| 11 directions modeled, 11 benched | FL-BUSINESS | real |
| $75 affiliate vs ~$356 producer commission, 9x | FL-BUSINESS | ⚠️ the 10% commission rate is flagged as an estimate in the source. Verify before quoting |
| $5,000 line redirected to a secured ladder | FL-CREDIT | real analysis ⚠️ say "recommended" unless she has accepted |
| MPOWER $313.2M securitised, A-rated senior notes | FL-CREDIT | real, public |
| Lorenzo, Jasper, University Gateway live; $1,028–$3,750 | FL-HOUSING | real, visible in product |
| USC $2,450 / DTLA $2,700 / K-Town $2,200 avg 1BR | FL-HOUSING | real, visible in product |
| Five named ambassadors | FL-AMBASSADORS | real, four visible in product, fifth named in Seven Directions |
| Zolve $406M raised | FL-AMBASSADORS | real, public |
| 30 merchants in two weeks | FL-AMBASSADORS | ⚠️ **a plan, not a result.** "push" or "target" only. Never "signed 30" |
| 90 moves, 5 chapters, live | FL-PLAN | real, visible in product |
| 20 vs 15 steps; CPT reroute sliding 3 dates | FL-PLAN | real (concept_15) |
| 8,145 postings, 31 sponsors, 17/14 split, ±10pp | FL-SOURCING | real |
| 300 → 2,200 addressable | FL-GTM | ⚠️ two different 2,200s sit four paragraphs apart in the work summary. Know which denominator is being stacked |
| 60 new and returning students interviewed at Lorenzo move-in | FL-FIELD-VALIDATION | user-confirmed |
| 3 of 20 spots claimed on the first merchant offer | FL-FIELD-VALIDATION | real, visible in product |

---

# OUT OF BOUNDS

- **No ownership of wallet, card, credit scoring, stablecoin or underwriting product concepts.**
  Those are the founder's. The *analysis* of them (story 3) is claimable; the product ideas are not.
- **No claiming the deck's LATER roadmap column** (stablecoin wallet, Fluo credit card, alternative
  credit scoring, licensing Fluo Score).
- **No claiming the 1,000-user or 70%-weekly-active targets.** Those are targets on deck s3 and s17
  against a live base still around 150.
- **The calendar correction is not yours.** `Fluo_Work_Summary_Akshat.docx` Workstream 2 credits it
  to Jarumon, raised in review. The sizing is yours; the calendar catch is not. The current McKinsey
  resume bullet implies otherwise and should be fixed to: *"Corrected the fall launch plan from 300
  to 2,200 addressable students against real enrolment figures, then rebuilt targeting around the
  one cohort still overseas under the 30-day F-1 entry rule."*
- **No realized outcomes from plans.** Distinguish designed / prototyped / proposed from shipped /
  launched per item.
- **EMOB flag.** Any variant touching the first-90-days lifecycle calendar (playbook p55) inherits
  Early Month-on-Book framing, and playbook p53 says outright *"Adapt the credit-card LCM logic."*
  No recommended bullet depends on it.

---

# OPEN ITEMS

1. **USC, one sentence:** which office, who agreed, what exactly they agreed to, what date, and
   whether it is in writing. This single fact carries the best bullet in the pool.
2. **Did Jarumon accept the credit-ladder recommendation?** Changes "redirected" to "recommended."
3. **Element out, Jasper in** — confirm what happened. "Replaced a partner that fell through" is a
   stronger line than "signed three."
4. **Cafe Dulce terms** — confirm the $5 cap and 20 spots were your call.
5. **Ambassador recruiting** — confirm you recruited them personally, and whether you run the program.
6. **Live user count and retention, with a date.**
7. **Marshall case competition** — what it is, when, your role. Not yet in any story.
8. **Field-validation loop resolved.** Sixty Lorenzo conversations informed the awareness-versus-
   demand diagnosis; usage showed 3 of 20 claims, and the next test moved to receipt verification.

---

# CUT, AND WHY

- **Cafe Dulce economics.** $100 of exposure on a page carrying $1.2M and $110M reads as a rounding
  error. The till insight (a student holding up a phone to a cashier who has never heard of the
  brand stops opening the app) is excellent interview material and a poor resume line.
- **The coin economy audit.** 1,000 coins to the dollar, nine cards reading "49,500 more." Real,
  quantified, and it is texture inside FL-PLAN rather than a story.
- **"Shipped 90 moves"** as a standalone. That is the ending of story 6, not a story. Scope without
  a decision.
- **The demote-the-settling-plan recommendation.** Genuinely good judgment, and a bad bullet: it
  optimizes for surviving a drill-down that only happens if a bullet earns the interview first.

---

# BEHAVIORAL / CARL (flagged, not written — out of scope for this pool)

1. Telling a founder the product she commissioned is not the business, then re-running the analysis
   when she overruled it.
2. Disagreeing with a 23-year domain expert on her flagship product, and handing back a better
   version rather than a no.
3. Disclosing the weakest part of your own work before anyone asked. Three independent instances:
   the 17/14 endpoint split, reading Fluo Friday's 3-of-20 honestly, and pre-listing the three
   weakest points of your own assessment deck.
4. Concluding your own shipped feature could not win its user, and finding the channel that could.
5. Securing an institutional partnership after reframing the product around pre-arrival distribution; confirm outreach mechanics before drafting the behavioral story.
