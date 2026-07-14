# Story Engine — Audit & Plan

*Author pass: 2026-07-08. Purpose: audit the raw story material scattered across ResumeGenerator + Outreach, find the gaps, and propose the architecture for a single "story engine" that feeds resume bullets, behavioral interviews, and outreach angles from one source of truth.*

---

## 0. The Vision (restated so we're aligned)

Stories are the raw material. Everything downstream — resumes, cover letters, behavioral answers, cold outreach — is a *rendering* of the same underlying stories. Today those stories exist, but they're scattered across ~7 documents in 4 different formats, each written for one narrow purpose, with no canonical layer. The resume engine has plateaued not because the generator is weak but because **the stories feeding it have hit their ceiling.**

The story engine fixes the input, not the output. It does three jobs:

1. **Fuel** — each story rich enough to mint a perfect bullet for *any* resume we generate (PM, and going forward strategy / ops / consulting — not IB/finance).
2. **Behavioral readiness** — each story structured, memorized, and defensible under follow-up drilling for interviews.
3. **Outreach angles** — pattern-match the profile against a target company and surface the sharpest, most-tailored pitch (this is where the 450-company tracker gets its ammunition).

One canonical story = one document. Roughly 10–15 stories total.

---

## 1. Where the story material lives today

| Asset | Location | Purpose it serves | Format |
|---|---|---|---|
| `STORY_BANK_RICH.md` | `ResumeGenerator/docs/reference/` | Resume/cover-letter fuel — max PM signal, keyed to weak bullet codes | 6 clusters × 2 deep variants |
| `interview_story_scripts.md` | `.../career_workbench/story_sources/` | Spoken STAR versions for interviews | 2 stories (Hevo, Gojek) |
| `Behaviourals.md` | `.../cover_letters/story_bank/` | Rough behavioral prep + Epson TMAY/Why drafts | CARL/STAR fragments |
| `Day 6 – December 16.md` | `.../cover_letters/story_bank/` | Longest behavioral bank; TMAY variants + product stories | Sprawling |
| `Hevo 2.0 revised Product story.md` | `.../cover_letters/story_bank/` | Deep Hevo product/segmentation material | 1230 lines, one company |
| `answer_engine.md` | `.../career_workbench/` | The **rubric / taste model** for TMAY + Why answers | Scoring guide |
| `profile.md` | `ResumeGenerator/profile/` | Stable profile — source of truth for scorer + generators | Structured profile |
| `story_fit_targets.csv` | `Outreach/workspace/` | 21 companies → story cluster → "why you have a case" | Outreach seed |
| `Coffee chat dump.txt` | `Outreach/Consulting/resources/` | Raw consulting coffee-chat notes + angles | Unstructured |
| `interview_prep/` | `.../career_workbench/interview_prep/` | Per-company prep folders + `prep_template.md`; active FlairX/Pebl, archived Hypertherm | Company-scoped |

Note on `interview_prep/`: this is a **consumer** of stories, not a store of them — but its `prep_template.md` (TMAY 45s/90s, story-shortlist table, question buckets, debrief) is exactly the per-interview surface the engine should feed, and its archived prep held enrichment not in the rich bank (e.g. Hevo 2.0's "middle-market kill zone," "8 enterprise customers in 90 days"). The engine's canonical stories become what these prep folders pull from, and the template's "promote reusable story back into the bank" debrief step becomes the loop that keeps the bank growing.

**The structural problem:** the same story (e.g., Hevo AI monitoring) appears in `STORY_BANK_RICH`, `interview_story_scripts`, and `Day 6` — three times, three shapes, and if you improve one, the others silently drift. There is no canonical record any of them derive from.

---

## 2. Full story inventory

Every distinct story I could find, graded on the three jobs. Legend: **A** = strong/ready, **B** = usable but needs work, **C** = weak/fragment, **—** = doesn't exist yet.

### Gojek (Senior SWE — marketplace / consumer)

| # | Story | Resume | Behavioral | Outreach | Verdict |
|---|---|---|---|---|---|
| 1 | **Fare-quote latency / funnel drop-off** — p95 tail latency + price-sensitivity, budget tier, ~28K monthly rides | A | A | A | **Keep.** Flagship data story. Has resume-rich + spoken script. |
| 2 | **External Fleet API platform** — supply diversification, 4-hr supply windows, confidence score, +18% supply | A | B | A | **Keep, deepen behavioral.** Rich resume material, no spoken STAR yet. |

### Hevo Data (SWE — data infra / startup)

| # | Story | Resume | Behavioral | Outreach | Verdict |
|---|---|---|---|---|---|
| 3 | **AI Monitoring / Incident Card** — alert storm 40–60→1 card, failure taxonomy, MTTR 45→5 min | A | A | A | **Keep.** Sharpest AI-product story. Fully built across 3 docs. |
| 4 | **Job Monitoring — reliability usable** — first Hevo project, making failure legible | B | B | B | **Refine.** Predecessor to #3; risks redundancy — decide if it's its own story or the "before" of #3. |
| 5 | **Hevo 2.0 Enterprise Pivot (The Strategist)** — segmentation, competing w/ Fivetran, upmarket bet | A | A | A | **Keep.** Best product-strategy story; 1230-line source is over-grown and needs distilling. |
| 6 | **Micromanagement / Bottleneck** — leadership failure, "scale yourself not just the product" | — | B | — | **Keep as behavioral-only.** Standard "failure/feedback" story. |
| 7 | **Scrum Master / Servant Leader** | — | C | — | **Back-pocket.** Thin; keep only if you need a second leadership angle. |

### Intuit (SWE — fintech / billing)

| # | Story | Resume | Behavioral | Outreach | Verdict |
|---|---|---|---|---|---|
| 8 | **Billing accuracy / roadmap pivot** — silent churn, LTV math, "accuracy debt rate," $1.8M exposure | A | B | A | **Keep, add spoken STAR.** Rich resume material; no interview script yet. |
| 9 | **Crisis Commander** — faulty script migrated 1,500 companies out; 10-day war room; parallel recovery | B | A | B | **Keep.** Best crisis/ownership story. Not yet mined for resume/outreach. |
| 10 | **Out-of-Sync (OOS) framework** — influence w/o authority, 50K accounts, ~3K/mo auto-resolved, 10% renewal lift | A | A | A | **Keep.** Does double duty (product + behavioral). Very strong. |
| 11 | **Underestimating scope / missed deadline** — phased rollout, cadence fix | — | B | — | **Keep as behavioral-only.** Solid "mistake" story. |

### Optum (SWE — healthtech)

| # | Story | Resume | Behavioral | Outreach | Verdict |
|---|---|---|---|---|---|
| 12 | **Provider Integration / Care Network** — 80/20 reusable template, Clinical Ops unlock, $20M reframed | A | B | A | **Keep, add spoken STAR.** Strong; behavioral version missing. |
| 13 | **AI Affordability pilot** — hackathon win, "flag & suggest," recall-first, 90-day bail-out criterion | A | B | A | **Keep, add spoken STAR.** Best "responsible AI + stakeholder trust" story. |

### MBA / current / side projects — **the biggest gap**

| # | Story | Resume | Behavioral | Outreach | Verdict |
|---|---|---|---|---|---|
| 14 | **FlareX — AI PM internship** (current) | — | — | — | **CREATE.** You flagged this. Live AI-product work; nothing written down. Highest-value new story. |
| 15 | **L'Oréal — AI creative/workflow automation** | — | C | C | **CREATE.** Exists only as a PDF + passing mentions. Your only formal AI-consulting story. |
| 16 | **Grab shuttles — new mobility safety/strategy** (MBA) | — | — | — | **CREATE or drop.** Mentioned in profile.md, undocumented. Decide if real enough to build. |
| 17 | **ResumeGenerator / Outreach engine** (this build) | — | C | B | **CREATE.** Your live "builder energy" proof; already cited in FlareX/Pebl answers, never written as a story. |
| 18 | **BarRaiser — 3rd-party technical interviewer** (2023) | — | C | C | **CREATE (light).** 6 months evaluating SWE interviews — a unique, credible angle for any hiring/HR-tech company. |

### Personal / back-pocket

| # | Story | Verdict |
|---|---|---|
| 19 | **Niveda Mobile School (The Advocate)** | Back-pocket only. Social-impact / advocacy / "outside work" prompts. |

**Count:** ~13 built stories (grades A/B), ~5 to create, 2 back-pocket. Matches your "downwards of 10–15" instinct — with the real opportunity in the *new* material (14–18).

---

## 3. Gap analysis — what's actually holding the engine back

**Gap 1 — No canonical layer.** The #1 structural issue. Stories live in 3+ formats with no source of truth, so improvements don't propagate and the resume generator pulls from whichever doc it happened to be pointed at.

**Gap 2 — The new stories don't exist.** FlareX, L'Oréal, the side-project engine, BarRaiser. This is where your *current* narrative lives and it's the freshest, most relevant material for outreach — and it's almost entirely unwritten. Everything documented is pre-MBA.

**Gap 3 — `profile.md` is stale.** Last updated March 2026. No FlareX, no L'Oréal detail, no MBA consulting, no side projects. Every generator reads this file, so the whole system is running on a pre-MBA snapshot of you.

**Gap 4 — Behavioral coverage is lopsided.** Resume-rich stories (Fleet API, Billing, both Optum stories) have no spoken STAR version. Behavioral-rich stories (Crisis Commander) have never been mined for resume/outreach. Each canonical story should carry *all three* renderings so nothing is trapped in one format.

**Gap 5 — Outreach angles cover only 6 clusters, keyed to old companies.** `story_fit_targets.csv` maps cleanly to your career (data infra→Hevo, fintech→Intuit, healthtech→Optum, marketplace→Gojek, ai-workflow→L'Oréal/side-projects, hiring→FlareX/BarRaiser). That's a *good* spine — but the "why you have a case" text is generic because the underlying stories aren't tuned for pitching. The engine should generate the angle from the canonical story, not hand-write it per company.

**Gap 6 — Redundancy to resolve.** Hevo Job Monitoring (#4) vs AI Monitoring (#3) overlap heavily. Decide: two distinct stories, or one story with a "before/after" arc. Same call on the 3 duplicate copies of each flagship story.

---

## 4. Proposed architecture

### 4.1 One canonical schema per story (v2)

Each story becomes a single markdown file holding *everything* about the story once; every downstream artifact is derived from it. v2 is built to satisfy the four hardest consumers at once: **Amazon PM behaviorals** (Leadership-Principle-mapped, "I"-not-"we", quantified, survives 5–6 follow-ups), **MBB fit / McKinsey PEI** (one dimension told in depth, interpersonal tension, persuasion without authority, personal stake, reflection), **resumes across tracks** (PM / strategy / ops / consulting), and **outreach** (short cold hook + long pitch).

```
# <Story Name>  —  <Company> · <Cluster>

## Snapshot
- One-line hook:
- Cluster tag(s): data_infra / fintech_billing / healthtech / marketplace / ai_workflow / hiring
- Best for (JD nouns/skills this proves):
- Role tracks it can serve: PM / strategy / ops / consulting
- Timeframe & duration:

## The Facts (defensible core)
- Situation & why it mattered NOW (the trigger):
- Scale / stakes ($ , users, trust, risk):
- My role & ownership boundary — explicit "I did X" vs "the team did Y":
- What would NOT have happened without me:
- Mechanism / key decision (the specific technique — must pass the removal test):
- Alternatives I considered and rejected, and why:
- Trade-off I consciously accepted (what I gave up):
- Metrics — for each: baseline → result, over what window, how measured, my attribution, and one line on "how I'd defend this if drilled":

## Interview Dimensions
- Amazon Leadership Principles demonstrated (e.g., Ownership, Dive Deep, Earn Trust, Bias for Action, Deliver Results, Are Right A Lot):
- MBB / PEI dimension (Personal Impact / Entrepreneurial Drive / Courageous Change / Inclusive Leadership):
  - The interpersonal tension (who pushed back / what was the conflict):
  - How I moved people without authority:
  - Why I personally cared (the stake / emotional texture):
- Behavioral buckets this answers (failure, conflict, ambiguity, influence, data, leadership, tradeoff...):

## Renderings
### Resume ammo  (NOT finished bullets — the resume generator + freeform playbooks own rendering)
  - quantified hooks, ownership boundary, and which role tracks the story arms
  - the story engine is the fact source; the existing resume system consumes it
### Spoken — SHORT (~30–45s, crisp, for HireVue / rapid-fire)
### Spoken — LONG (~2 min, full STAR/CARL with room for the interviewer to drill)
### Outreach — SHORT hook (1–2 lines, cold message opener)
### Outreach — LONG pitch (one paragraph: why this makes me a credible, tailored case for a company in this cluster)

## Follow-up Defense Bank
- The 6–10 drill-downs an Amazon bar-raiser or MBB interviewer would ask, each with my answer.
  Must include: "What was YOUR specific contribution?" · "What data / how did you measure?" ·
  "What did you consider and not do?" · "Who disagreed and how did you handle it?" ·
  "What would you do differently?"

## Provenance
- Source docs distilled from:
- Confidence notes (anything reconstructed / rounded / to re-verify):
```

**On your questions directly:** yes — the `Interview Dimensions` block + `Follow-up Defense Bank` are what make this Amazon- and MBB-grade rather than just resume-grade. Amazon lives and dies on LP mapping + surviving follow-ups; MBB lives on the tension/persuasion/personal-stake sub-fields. And the split renderings give you short *and* long on both the spoken side (rapid HireVue vs deep panel) and the outreach side (cold-DM hook vs full pitch paragraph).

We'll prove this on ONE story first (proposed: **Hevo AI Monitoring** — most complete, dedups its 3 copies), you react to the shape, we lock it, then roll out.

### 4.2 Folder structure

```
docs/career_workbench/story_engine/
├── STORY_ENGINE_AUDIT_AND_PLAN.md   ← this file
├── INDEX.md                          ← master table: story → clusters → status → best-for
├── stories/
│   ├── hevo_ai_monitoring.md
│   ├── gojek_latency.md
│   ├── intuit_crisis_commander.md
│   └── ... (one per canonical story)
├── clusters.md                       ← the 6 clusters + which stories/angles serve each
└── _archive/                         ← the old scattered docs, kept for reference, not edited
```

The existing scattered docs stay in place (nothing deleted), but the story engine becomes the single source of truth. `profile.md`, the resume freeform prompts, and `story_fit_targets.csv` all get re-pointed at it over time.

### 4.3 How it feeds the three engines

- **Resume generation** → pulls `## Renderings → Resume bullets` and `## The Facts`. Richer facts = better bullets. When we add strategy/ops/consulting resumes, the same facts get re-rendered for that track (the `Role tracks` field flags which stories qualify).
- **Behavioral prep** → pulls `## Renderings → Spoken STAR` + `## Follow-up defense`. Company-specific prep folders reference canonical stories instead of re-drafting them.
- **Outreach** → the `Cluster tag` + `Outreach angle` fields feed `story_fit_targets.csv`. For a target like Pebble, the engine matches clusters, pulls the 1–2 sharpest stories, and composes the angle — instead of you hand-writing "why you have a case" per company.

---

## 4.4 The Probe Protocol — how I push you to make each story exhaustive

You asked me to actively push you to surface detail we're missing, not passively transcribe. So for every story we build, I run this battery. My job is to keep asking until each field is defensible, flag any answer that's thin or generic, and apply the **removal test** to every claimed detail: *if I delete this sentence, does the story still prove something? If yes, the detail isn't earning its place — go deeper.*

I'll drill these nine dimensions per story:

1. **Situation depth.** Who *exactly* was the user/customer (role, not "users")? What was at stake in dollars, trust, or scale? And critically — *why did this land on your desk now?* Every strong story has a trigger.

2. **Your specific role.** What did *you* do versus the team? If I gave your job to a competent peer, what specifically would have gone differently? What was your actual authority — and if you had none, that's the story, so name it. (This is the field Amazon drills hardest and where "we" quietly hides weak ownership.)

3. **The mechanism.** What was the *specific* technique or decision — not the category? "Anomaly detection" is a category; "per-connector SLA thresholds on a 14-day rolling baseline" is a mechanism. What would a competent person *not* have thought to do? Removal test applies hardest here.

4. **Alternatives & judgment.** What other options were on the table, and why did you kill them? What was the trade-off you *consciously* accepted, knowing the downside? A story with no rejected alternative reads as luck, not judgment.

5. **The numbers.** For every metric: baseline before, result after, over what time window, measured how, and *how much of it was attributable to you*? Then — can you defend it if an interviewer pushes twice? We mark anything reconstructed so behaviorals stay bulletproof.

6. **People & politics (the MBB gold).** Who disagreed with you? Who did you have to win over with no authority? What did that specific conversation feel like — what was the objection, what did you say, where was the friction? MBB fit interviews are *built* on this and it's the most under-documented dimension in your current material.

7. **Failure & reflection.** What went wrong, or what would you do differently now? What did this specifically change about how you work? "I learned communication is important" fails; "I now demand daily check-ins on any high-risk project because weekly hid the risk until month two" passes.

8. **Personal stake.** Why did *you* care about this beyond it being your job? What did it cost you — time, stress, reputation risk? MBB and the best PM interviewers want the human texture; it's also what makes an outreach pitch feel authentic instead of templated.

9. **Reusability mapping.** Which JD nouns/skills does this legitimately prove? Which role tracks can it serve (PM / strategy / ops / consulting)? Which company clusters does it arm for outreach? This is what lets one story render into many surfaces.

When you answer a story, I'll tell you which of these nine are solid, which are thin, and exactly what I still need — so we don't declare a story "done" until it can survive an Amazon bar-raiser, anchor an MBB PEI answer, mint a bullet for any track, and open a cold pitch.

---

## 5. Phased roadmap

**Phase 0 — Align (this doc).** Agree on schema + scope. ✅ in progress.

**Phase 1 — Prove the template.** Build ONE canonical story end-to-end (Hevo AI Monitoring), collapsing its 3 existing copies into one. You react to the format; we lock the schema.

**Phase 2 — Migrate the strong 4-company stories.** Convert stories #1, 2, 3, 5, 8, 9, 10, 12, 13 into canonical docs. Each gets all three renderings so no story is trapped in one format. Fills Gap 1 + Gap 4.

**Phase 3 — Mine the new material.** Create #14 FlareX, #15 L'Oréal, #17 side-project engine, #18 BarRaiser (and decide on #16 Grab). This is a working session where you talk, I structure. Fills Gap 2 — the biggest lever for fresh outreach.

**Phase 4 — Refresh profile.md + resolve redundancy.** Update the source-of-truth profile with MBA/FlareX/side-project facts; resolve the Job-Monitoring-vs-AI-Monitoring overlap. Fills Gap 3 + Gap 6.

**Phase 5 — Wire outreach.** Rebuild `story_fit_targets.csv` generation off canonical clusters so any of the 450 tracked companies gets an auto-composed, story-backed angle. Fills Gap 5.

**Phase 6 — Interview loop.** Standing prep workflow: for any interview, the engine assembles a company-specific behavioral pack from canonical stories + the `answer_engine.md` rubric.

---

## 6. Open decisions for you

Settled so far: schema is now v2 (Amazon LP + MBB/PEI + short/long spoken + short/long outreach); we start with one story and react before rolling out; metrics treated as mostly-real but each still carries a defense line.

Still open:

1. **Schema v2 sign-off** — does Section 4.1 now capture everything, or add/cut fields before we commit?
2. **First story** — I propose **Hevo AI Monitoring** (dedups 3 copies + it's your sharpest AI story). Confirm, or pick another.
3. **Job Monitoring (#4)** — its own story, or fold into AI Monitoring as the "before"?
4. **Grab shuttles (#16)** — real enough to build, or drop?
5. **Probe depth** — the Section 4.4 protocol is thorough; for the first story do you want the full nine-dimension drill, or a lighter pass to see the shape first?
