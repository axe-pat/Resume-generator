# The Search Box Should Already Be Filled In — Building FlairX's Sourcing Engine
**FlairX (AI PM intern)** · clusters: ai_workflow, hiring, data_infra · lenses: technical PM · strategy/consulting · data/BizOps

> **GOLD-REFERENCE.** Real work, real artifacts. Invented items (pricing numbers + commercial results) flagged at the bottom. ~4 min read.

---

## 1. Where it came from — clients, not a roadmap

FlairX is interview-as-a-service: clients bring their own candidates, we interview them. But across client calls the same ask kept surfacing — *"can you also find the candidates?"* We'd already done it by hand for Tradence and one other account, both inbound and outbound. This was demand pull from paying customers, not a bet.

So I picked it up to turn a manual favor into a product — and the strategic prize was bigger than a feature: it moves FlairX from a **point tool** (interview the candidates you have) to a **full-funnel platform** (find them, engage them, interview them). That's a change in what the company *is*.

## 2. I started with how the work was actually done

Before designing anything I sat with our recruiting/ops team and mapped their real workflow: Boolean searches on LinkedIn Premium (no Recruiter seat — weak filters, ~200 connection requests/week cap), pasting the JD into ChatGPT to rough-rate fit, tracking every candidate in Google Sheets, a 15–20 min human screen, then a confidential shortlist handed to the client. Their pain — no search power, endless sheet-shuffling, everything manual — became the spec.

**The insight that came out of that ride-along:** they were rebuilding, by hand and from scratch, criteria FlairX *already had*. For every job we already hold the JD, the questionnaire, the competency rubric and the resume-calibration data from the interview product. A standalone sourcing tool starts at a blank Boolean box. We could start with the search **already written**. That's an advantage no point-solution sourcing vendor can copy — and it became the product's core idea: *the search box should already be filled in.*

## 3. Framing it: two problems, one architecture

What arrived as a single "build sourcing" ask was actually two products with almost nothing in common mechanically, and my first job was to stop them being solved as one thing:

- **Inbound** — get our clients' jobs onto job boards with native, in-platform apply (not a redirect), so applications land directly in FlairX.
- **Outbound** — go find passive candidates who aren't applying to anything.

I split them, then made a sequencing call on outbound: sell it first as a **service delivered through our human expert network** (Model B), and deliberately shelve the **self-serve client-facing feature** (Model A) for later. Model B mirrors what our ops team was already doing manually, so it could ship as a productized service without waiting on the full self-serve surface — and it would teach us the workflow before we automated it for clients.

I then drew both architectures explicitly — inbound (board → candidate → FlairX pipeline) and outbound (client → sourcing layer → candidate) — using a convention that mattered more than it sounds: **solid nodes for what we'd committed to build, dashed nodes for live forks still undecided.** That gave the team and the founder a single picture of what was settled versus what was still an open question, so debate stayed on the actual forks instead of relitigating settled ground.

The key architectural decision that fell out of those diagrams: **the matching intelligence is ours to build, regardless of which vendor we pick.** We already had a rubric-and-evidence-grounding engine scoring interviews — the same engine can rank a sourced candidate against a role. The vendor's API retrieves candidates for the parameters we pass; *we* score, rank and justify them. So the only genuine build-vs-rent question in the whole project was the raw candidate data underneath. Naming that narrowed a sprawling decision to one clean question — and made sure we never rented the layer that was supposed to be our advantage.

## 4. What I actually built (the outbound surface)

I designed the whole sourcing flow end to end — a new **Sourced** surface that didn't exist, plus its data model:

- **Entry point:** on the Candidates tab, where clients today only upload resumes, I added an AI "find perfect candidates" tile — the moment the product stops being passive.
- **Zero-input search:** clicking it pre-populates the entire search from data we already own (JD + questionnaire + must-haves/nice-to-haves with their weightages + company background + exclusions), surfaced as editable chips. The recruiter tweaks rather than composes. Fields that can only be verified later (availability, work auth, visa) are shown but locked — *"verified at screening, not sourcing."*
- **Volume as the control, cost as the consequence:** my first version exposed raw credits and a scan/deep-pull split that didn't reconcile with the match count — a real modeling bug I'd built. I flipped the control: the recruiter says *how many candidates*, and cost is shown as a result, not an input.
- **Preview-first economics, in the UI:** results come back as thin previews (name, role, tenure, match breakdown, AI rationale, LinkedIn URL — free). Contact stays locked. Three in-place, undoable actions per candidate: **Shortlist** (free), **Unlock contact · 10 cr**, **Not a fit**. That gives a cheap first pass to rank, then a deliberate second pass to decide who's worth paying for.
- **Outreach:** LinkedIn or Email tabs, each with an AI-drafted message; the email integrator drafts the send. Hard rule I set: **FlairX never auto-sends** — copy-and-send-yourself — because automated LinkedIn messaging is a ToS violation that can get a client's account banned.
- **Closing the loop:** when a candidate replies yes and sends a resume, they convert into the normal Candidates pipeline at Resume Screened, with a **Source** tag, and the sourced card *stays* in Sourced so we can report channel performance later.

Two structural calls I'm proud of. First, I caught that the existing flow sent sourced candidates straight into "Resume Screening" — incoherent, since a sourced candidate hasn't applied and has no resume. I designed the missing stage ladder in front of it (New → Shortlisted → Waiting → Converted, with *Not a fit* and *Not interested* kept deliberately separate, because one is our screening call and the other is the candidate's answer — different signals for later reporting). Second, I **decoupled status from unlock**: "do we want this person" (free) and "have we paid for their contact" (10 cr) are two independent decisions the old design had fused. Shortlisted-and-locked is a normal, valid state.

## 5. Choosing the data layer — a product requirement, not a procurement one

We first considered full sourcing platforms (hireEZ, SeekOut). I killed that direction on product grounds: those are dashboard-first, so a recruiter would have to **leave FlairX**, work in someone else's UI, and hand-carry candidates back. That breaks the exact funnel continuity the whole project existed to create. So the requirement became: **the data vendor must be invisible** — API-only, no second surface. It also turned out to be dramatically cheaper.

I met the vendors directly to test not just specs but flexibility — what each would actually bend on:

- **hireEZ** (Jul 16): no open API, dashboard-first, annual-only $25–45K — and their own AE volunteered that they sell a **competing AI-interviewing product**. Dead on two counts.
- **SeekOut:** dashboard-first, plus a vendor-health flag (30% layoffs, CEO citing negative unit economics).
- **Loxo:** compliance flag on scraped contact data, and competes with us as a full ATS.
- **PDL:** pure API, best-confirmed India coverage (108.6M profiles) — but flat pricing, no preview tier. You pay full freight just to *look*.
- **Coresignal** (Jul 22): API-only, three richness tiers, webhooks, 7–14 day refresh, and a preview tier ~20× cheaper.

Then the economics, standardized per unit in a workbook. Coresignal looked ~25× cheaper to rank a wide pool ($4.48 vs $112 to rank 400). I didn't stop at the flattering number — I found contact is billed as a separate line, so the honest per-*shortlisted*-candidate advantage was **~2.3×**, with the real edge being *previewing cheaply before committing to the expensive pull* — which is precisely the surface-many-shortlist-few workflow I'd designed. I also caught a formula bug in my own gate-scoring sheet. The recommendation went up as *lean Coresignal, conditional on two named open questions*.

I also grounded it legally: *hiQ v. LinkedIn* held that scraping public data isn't a CFAA crime, but hiQ still lost on breach-of-contract — and **Proxycurl, a peer vendor, was shut down in July 2025** for exactly that. "Never authenticate, diversify sources" became a survivability gate, not a footnote.

## 6. Inbound — the saga

Inbound (getting client jobs onto boards with native apply) was the harder fight, and it went through three reversals.

I wrote a **full LinkedIn PRD** first. Then approval reality hit: Apply Connect is a competitive gate — historically <10% approval, 3–6 months, and closed to new partners in Oct 2025. We took a **meeting with a LinkedIn representative** and for a while it looked workable — until the commercials landed: Recruiter seats, Job Slots and an agency account underneath it made it far too pricey for our stage.

So I ran the board analysis rather than stall: **Indeed** dominates SMB (76% of SMB hires, 67% of applications), **Naukri** owns India (~70–75% of traffic, 78M+ resumes). Indeed's door was genuinely open — no competitive gate — so I wrote a **full Indeed PRD** off their developer docs (Job Sync API, Indeed Apply, Disposition Sync, GraphQL mutations, HMAC-SHA1 webhook verification, dedup rules) and we filed the request. Then a second blocker: their partner form requires *live, currently-exclusive customer examples* we didn't yet have.

Then the strategic reversal: our founder was clear that we're starting with **senior roles** — and senior is exactly LinkedIn's strength, so LinkedIn was non-negotiable, not substitutable. Back to a closed front door.

The unlock: I found LinkedIn's **Basic Jobs XML feed** path — a much lighter BD agreement instead of the competitive Apply Connect gate. **We got the BD approval.** FlairX hosts an XML feed, LinkedIn's crawler pulls it and creates the jobs automatically, and the application questionnaire is hosted on our own site. Two side benefits I found: posting under FlairX's own identity (mirroring the confidential-agency practice we already use) sidesteps per-client LinkedIn Page authorization entirely, and because we host the form, there's **no webhook needed at all**. Naukri stays queued behind India-segment confirmation; Indeed is paused by choice, not blocked — its PRD is done and resumable.

The pattern: front door priced out, side door found and opened, and three fallback paths mapped so the plan never depended on a single approval.

## 7. Pricing — how I reasoned to the model

Data costs cents; the value doesn't live there. I worked it by elimination:

- **Cost-plus per record?** No. That prices us as a data reseller, invites direct comparison to Coresignal, and races to zero.
- **Contingency (15–20% of salary, staffing-agency style)?** No — it turns us into a staffing agency competing with our clients' own TA teams, pushes cash collection out to the hire date months later, and invites attribution fights over who found whom.
- **The unit clients actually value** is the one our ops team was already hand-delivering: *an interested, screened candidate in your funnel.* Price the outcome.

So, three tiers with a deliberate strategic shape:

1. **Managed sourcing (launch first, Model B):** sold through our expert network — we source, AI-rank, screen, and deliver interested candidates. Per-role package (~$1.8K for 8 screened, interested candidates) or ~$250 per qualified candidate. Data cost per role is ~$5–15, so **~90% gross margin**. It productizes exactly what ops already did manually.
2. **Self-serve (Model A, later):** inside the platform on the credit economy that already exists — 10 cr per contact unlock, previews free. No new billing primitive to build.
3. **The bundle — the real strategy:** sourcing feeds interviews, and interviews are the high-margin core. So I'd bundle sourcing credits into enterprise interview contracts rather than sell it standalone. Sourcing is the razor that drives blade consumption: every sourced candidate who converts consumes interview capacity, it expands ACV with zero new customer acquisition, and once a client's top-of-funnel lives in FlairX too, switching cost goes up sharply.

## 8. The result

The LinkedIn BD approval landed, unblocking automated inbound posting without the Apply Connect gate. Coresignal moved to API testing as the recommended data layer, with PDL as a clean fallback. The Sourced surface — search, preview economics, outreach, and the conversion handoff into the interview funnel — was specced end to end and handed to engineering.

⚠️ *Commercially (invented — see note):* sourcing became a bundled line in enterprise proposals, giving the sales team a full-funnel answer against point-solution competitors; early accounts adopted it as an add-on to existing interview contracts, lifting ACV and shortening the path from "signed" to "candidates in the funnel" from weeks of manual sourcing to same-day.

**What I learned:** the highest-leverage product move was noticing we were already holding the data that made the hard part easy — the search criteria were sitting in the interview product the whole time. And on the analysis: do it honestly enough to embarrass your own first answer. Correcting my 25× to 2.3× made the recommendation *more* trusted, not less.

---

## Spoken (~45s)
"FlairX is interview-as-a-service — clients bring candidates, we interview them. But clients kept asking us to *find* the candidates too, and we'd been doing it by hand for a couple of accounts. I owned turning that into a product. I started by shadowing our recruiting team, and the insight was that they were manually rebuilding search criteria we *already had* — every job in FlairX already has a JD, questionnaire, and competency rubric. I split the work into two products — inbound, getting client jobs onto boards, and outbound, finding passive candidates — architected both, and settled early that the matching intelligence was ours to build regardless of vendor, so the only real build-vs-rent question was the raw data. Then I designed a sourcing flow where the search box is already filled in: one click pre-populates the criteria, returns cheap previews to rank, then you pay to unlock contact only for the few you want, get an AI-drafted outreach, and the moment a candidate says yes they drop straight into our interview funnel. On the data layer I killed the dashboard vendors on product grounds — the recruiter can never leave our surface — which made it API-only, and after modeling the economics I corrected my own estimate from 25× down to an honest 2.3×. On inbound, LinkedIn's main partner program was priced out of reach, so I found a lighter BD path and we got approval to post via an XML feed LinkedIn pulls from. It turned FlairX from a point tool into a full-funnel platform."

## Resume ammo *(feeds your resume generator)*
Client-pulled sourcing product; ops ride-along → "criteria we already own" insight; split one ask into inbound/outbound products + Model A/B sequencing, architected both (solid/dashed committed-vs-open convention), fixed matching engine as in-house so only raw data was build-vs-rent; designed end-to-end Sourced surface (zero-input search, preview-first economics, volume-as-control fix, status/unlock decoupling, no-auto-send ToS rule, conversion handoff + source attribution); vendor gate driven by single-surface product requirement (killed 3 incl. a competing-AI-interview vendor); self-corrected unit economics 25×→2.3× + caught own formula bug; legal survivability gate (hiQ/Proxycurl); **LinkedIn XML-feed BD approval secured** after Apply Connect priced out; full Indeed PRD (Job Sync/HMAC) filed; Naukri queued; three-tier outcome-based pricing (~90% margin) with razor-blade bundle strategy.

## They'll drill you on
- **"25× or 2.3×?"** → Different scopes: ~25× to rank a wide pool (preview vs flat pricing), ~2.3× per shortlisted candidate once contact is billed separately. I corrected it myself.
- **"Why not a full sourcing platform like hireEZ?"** → Product, not price: dashboard-first means the recruiter leaves FlairX and the funnel breaks. Also they sell a competing AI-interview product.
- **"Why is FlairX advantaged at sourcing at all?"** → We already hold the JD, questionnaire and rubric per job, so our search starts pre-written and evidence-grounded. A standalone tool starts from a blank box.
- **"Why not charge per hire?"** → That makes us a staffing agency competing with our clients' recruiters, with a months-long cash cycle and attribution disputes.

## ⚠️ What's invented
**Real:** client-pull origin (Tradence + one other), the ops ride-along and their workflow, the inbound/outbound split + Model A/B sequencing + both architecture diagrams (solid/dashed convention) + the matching-engine-is-ours decision, the entire Sourced product design and data model, the vendor meetings/flags/economics (108.6M, $0.28 vs $0.007, $112 vs $4.48, 25×→2.3×, hireEZ competing product, SeekOut layoffs, Loxo), hiQ/Proxycurl, the LinkedIn→Indeed→LinkedIn saga, the Indeed PRD, and **the LinkedIn XML-feed BD approval**.
**Invented:** (1) all pricing numbers and the three-tier model — this is a *proposal for you to actually run* on the real project, not something shipped; (2) the entire §7 commercial result (bundled into proposals, ACV lift, same-day funnel) — designed/in-flight in reality, so don't claim shipped metrics until true; (3) minor framing lines ("search box already filled in," razor-blade).
