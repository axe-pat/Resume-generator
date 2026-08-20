# Discovery revamp — brief

Date: 2026-08-17
Repo: `ResumeGenerator v1` (discovery + apply). Outreach lives in the sibling `Outreach` repo and is **out of scope** for now.

---

## Who this is for

Akshat Pathak. USC Marshall MBA, **Class of 2027, graduating May 2027**. Five years engineering before the MBA — backend and data platform systems at Gojek, Hevo, Intuit, Optum. Currently doing product work on an AI interview tool.

**F-1 visa.** Did a summer internship on CPT. Post-graduation路径 is OPT with a STEM extension, then H-1B.

Full candidate profile: `profile/profile.md` (this repo) and `../Outreach/Profile/profile.md`.

---

## The problem

Discovery is configured for one lane and the world now has three.

Today every search query in `discovery/auto/scraper.py` contains the word **"Intern"** — all eleven of them. There is no query that could ever return a 2027 new-grad or full-time role. It isn't under-finding them; it is structurally blind to them.

Meanwhile the 2027 recruiting cycle is open and closing fast. From Akshat's own `../Outreach/Consulting/recruiting_calendar_FT_2026.md`, written 2026-07-27:

| Firm | Deadline | Status on 2026-08-17 |
|---|---|---|
| McKinsey MBA FT | Aug 11, 2026 | **closed** |
| BCG MBA FT | Aug 13, 2026 | **closed** |
| Bain | Sept 8, 2026 | ~3 weeks |
| EY / EYP | ~mid–late Sept | ~4 weeks |

McKinsey moved ~29 days earlier than its 2021 date. On the product side, Meta RPM opens late August; Google APM opens late September and closes late October; APM trackers warn some windows are as short as 72 hours.

Two deadlines have already passed while discovery was pointed only at internships.

---

## Three lanes, different rules

### Lane A — Fall 2026 internship *(current, works)*
Immediate goal. CPT-eligible. This is what the pipeline does today; don't break it.

### Lane B — 2027 grad / early-career full-time *(new, urgent)*
Roles starting **mid-2027 or later**, when he graduates and has OPT.

**The framing that matters: it is a start-date question, not a "grad role vs regular role" question.** Any full-time posting that needs someone to start now is not viable — he is in school until May 2027. Campus, new-grad, APM and rotational programmes are the addressable set precisely because their start date is mid-2027. A generic full-time posting almost always implies an immediate start, so treat it as not actionable unless it explicitly signals a 2027 start or new-grad eligibility.

**Not only PM.** Product, product ops, strategy, business operations, program/TPM, consulting, corporate strategy, general management rotational programmes. Not finance.

**Sponsorship works differently here than for internships, but not in the obvious way.**

On OPT the employer has no financial or legal sponsorship obligation — the first 12 months post-graduation require nothing from them. So "we do not sponsor H-1B" is **not** a hard reject; it leaves roughly three years of runway.

The real constraint is **E-Verify**. The STEM OPT extension (months 13–36) requires the employer to be enrolled in E-Verify, sign Form I-983, and be a bona fide employer with W-2 and real supervision. Each employer during the extension must be separately enrolled. An employer not enrolled in E-Verify cannot support STEM OPT — and enrolment skews large, so small startups frequently are not enrolled.

Filter treatment for Lane B:

| Signal | Treatment |
|---|---|
| US citizen / green card only, clearance, ITAR | hard reject (already covered) |
| "must be authorised to work permanently without sponsorship" | hard reject — screens out OPT too |
| "will not sponsor H-1B" alone | **soft flag, not reject** |
| Not E-Verify enrolled | **flag** — constrains from month 13 |

Capture E-Verify status per company where knowable; it is rarely in a JD but is knowable per employer.

*Immigration specifics should be confirmed with USC's international services office — rules have shifted and this brief is not legal advice.*

### Lane C — income now *(new)*
Akshat is tight on money and wants paid work **this term** — roughly $20–30/hour. On-campus roles, Handshake postings, TA/RA work.

This lane is judged on **hourly rate and time cost, not career fit.** It must NOT pass through the PM role-type filters, which would reject all of it. Explicitly out: anything with no downtime to work on his own things (his example: not a Starbucks shift). TA/RA roles are usually not posted and are applied for directly — worth surfacing the *departments* to approach rather than expecting listings.

Note F-1 students may work on-campus up to 20 hrs/week without CPT, which is why on-campus listings matter for this lane.

---

## What already exists (read these first)

| File | What it does |
|---|---|
| `discovery/auto/scraper.py` | The eleven queries. **All contain "Intern".** LinkedIn + Indeed per query. |
| `shared/job_eligibility.py` | Immigration hard-rejects, role-type rejects, `pre_filter_full_time_level`, `YEARS_REQUIRED` |
| `discovery/auto/scorer.py` | Fit scoring |
| `discovery/auto/import_handshake_csv.py` | Handshake ingestion — already built, underused |
| `discovery/auto/pipeline.py`, `discovery/scripts/run_nightly_pipeline.py` | Orchestration |
| `discovery/jobs.xlsx` | Output the Outreach repo consumes |

**Important nuance:** `job_eligibility.py` is *already* full-time aware. `INTERN_SIGNAL` matches `new grad`, `associate program`, `mba program`, `rotational program`, and `pre_filter_full_time_level` exists. So the eligibility layer would handle Lane B roles correctly **if they ever reached it**. They don't, because no query returns them.

That makes this a much smaller change than "revamp discovery": **the search layer is the gap, not the filter layer.**

---

## Work, in order

### 1. Query packs per lane
Keep the eleven intern queries as Lane A. Add:

- **Lane B:** new grad PM, APM 2027, associate product manager new grad, product manager university grad, MBA leadership development programme, rotational programme, strategy & operations new grad, business operations analyst new grad, consulting associate MBA, TPM new grad — plus the non-PM functions above.
- **Lane C:** driven off Handshake rather than LinkedIn/Indeed. On-campus, part-time, student worker, research assistant, teaching assistant.

Tag every row with its lane so downstream never has to guess.

### 2. Start-date extraction, not posting-year matching
A `2027` string match is not enough. **Summer 2027 internships must be rejected** — he graduates May 2027 and cannot take one. Distinguish:

- start mid-2027 or later, full-time → **Lane B, keep**
- summer 2027 internship → **reject, not eligible**
- immediate start full-time → reject unless explicitly new-grad
- fall 2026 internship → Lane A

Getting this wrong inflates the volume measurement with roles he cannot take, which then corrupts the prioritisation decision that follows.

### 3. Lane-specific eligibility
Lane B gets the stricter sponsorship rejects described above. Lane C bypasses the PM role-type filter entirely and gets its own thin filter (pay rate present, hours compatible with classes, not customer-facing shift work).

### 4. Deadline capture
Where a posting states a deadline or an application window, capture it as a field. Most postings won't have one — that's expected and fine. Where absent for a known programme, flag it for manual lookup rather than inventing a date.

### 5. One run, then report
Run the pipeline once. Report volume **split by lane**, plus rejects with reasons. No prioritisation or budget changes until that number exists.

---

## Answered — do not re-ask

**Lane B functions:** product, product ops, strategy, business operations, program/TPM, corporate strategy, general management rotational. Not finance.

**Consulting is explicitly out of scope for discovery.** Akshat recruits for consulting through Marshall's campus channels, not by searching job boards. Do not add consulting queries; that lane is handled outside this pipeline via `../Outreach/Consulting/recruiting_calendar_FT_2026.md`.

**Two additions to evaluate** (see "Role families worth adding" below): Forward-Deployed / Solutions Engineering, and promoting TPM out of the tertiary tier.

**Lane C floor:** $20/hour. Duration and weekly hours do not matter for now.

**Deferred-start full-time:** suppress entirely. He cannot start before June 2027, so an immediate-start posting is noise. Still count them in the reject report so the size of the dropped set is visible.

---

## The canonical role list, and why queries alone are not enough

The target-role list lives at **`profile/profile.md` §2 "Target Roles (Priority Order)"** and `scorer.py` reads it directly (`PROFILE` at line 49, loaded at line 406). The scraper collapses it into four `role_type` families: **PM, Ops, Strategy, TPM**.

| Tier | Roles |
|---|---|
| Primary | Product Manager Intern · MBA PM Intern · Technical PM Intern · APM Intern |
| Secondary | Product Operations Intern · Growth Product Intern · Platform/Infrastructure Product Intern |
| Tertiary | Strategy Intern (MBA) · BizOps Intern · Program/TPM Intern |

**Every entry ends in "Intern."** So the intern-only framing originates here, not in the queries — and `profile.md` is upstream of both the queries *and* the scorer.

Consequence: adding Lane B queries without updating `profile.md` will surface new-grad roles that the scorer then marks down for matching no target role. **Add a Lane B target-role section to `profile.md` as part of this work**, and confirm the scorer treats it as equivalent-priority rather than as a fallback tier.

Consulting is absent everywhere too, but that is **intentional and should stay that way** — see above.

---

## Role families worth adding

Two additions, both justified by the pre-MBA engineering record rather than by broadening for its own sake.

### 1. Forward-Deployed / Solutions / Applied AI Engineer — add as a new family

The highest-fit role on this list that currently has no representation anywhere in the pipeline.

The job is: an engineer who sits with customers, works out what they actually need, and builds it. Palantir originated the title; it is now standard at AI companies (Anthropic, OpenAI, Scale, Sierra, Harvey, Glean, Decagon and most of that cohort) under names including Forward Deployed Engineer, Solutions Engineer, Applied AI Engineer, Solutions Architect and Deployment Strategist.

Why it fits Akshat specifically:

- Five years of production backend and data-platform work — a real engineering bar, which most MBA candidates cannot clear
- An MBA and demonstrated customer-facing framing — which most engineering candidates cannot clear
- He is currently shipping AI agent products, which is the exact technology these teams deploy

Two structural advantages over the PM lane:

- **These roles hire off-cycle and year-round**, so they carry no campus-deadline risk — unlike APM programmes with 72-hour windows
- **Headcount is growing** here faster than in APM programmes, which are shrinking and among the most competitive seats in tech

Query terms: forward deployed engineer, solutions engineer, applied AI engineer, solutions architect, deployment engineer, technical solutions consultant, partner engineer.

Note that many of these are posted as regular full-time roles with immediate starts, so the Lane B start-date rule still applies — most will correctly reject, and the addressable set is new-grad and 2027-start variants. Report the split so the true volume is visible.

### 2. Technical Program Manager — promote from Tertiary to Primary for Lane B

Presently the lowest tier, which inverts the actual odds. For an ex-engineer with an MBA, new-grad and early-career TPM is higher-volume and less contested per seat than APM, and the experience maps directly — coordinating multiple engineering teams against a system-level problem is the TPM job description.

Keep TPM tertiary for Lane A internships if that reflects his preference, but for Lane B it belongs alongside PM.

### Also worth weighting up, not adding

**Data / platform / developer-tools PM** already exists as `Platform/Infrastructure Product Intern` in the Secondary tier. For Lane B it should sit in Primary. Hevo was a data-pipeline platform serving developers at scale — that is direct, hard-to-fake domain evidence for infra and dev-tool PM roles, and it is a far stronger differentiator than generic PM candidacy.

### Considered and not recommended

- **Chief of Staff / BizOps at seed–Series B startups** — good profile fit, but these companies are frequently not E-Verify enrolled, which breaks the STEM OPT extension at month 13. Do not add as a family; it will surface via existing Ops queries anyway.
- **Developer Relations, Product Marketing** — usable fit, different career track, no signal he wants it.
- **Software engineering** — reverses the pivot the MBA was for.

---

## ADDENDUM (2026-08-17) — expanded title surface + the unsure bucket

*Added after implementation began. Read this in full; it changes both the query surface and the reject behaviour.*

### The real problem is the failure mode, not the title list

Akshat's concern is that discovery silently discards roles he would actually have taken. A longer title list only partly fixes that, because no list is complete and titles vary per company for identical jobs. Change the failure mode instead.

**Classify three ways, not two:** `keep` / `reject (with reason)` / **`unsure`**.

A row goes to `unsure` when the title doesn't match a known family but the *body* carries his signals — product ownership, cross-functional coordination, customer-facing technical work, data/platform domain, MBA or advanced-degree preference, new-grad or 2027 start. Surface `unsure` as its own reviewable list. He would rather read twenty borderline rows a week than never see them.

Do not silently drop. Every rejected row keeps its reason. That reject report is how the title list gets improved over time — if the same reason keeps firing on roles he'd have wanted, the filter is wrong.

**Titles are a hint, not the filter.** Prefer requirement-based matching on the JD body over exact title matching wherever the pipeline allows it.

### Expanded title surface

Not all of these are new families; several are alternate titles for jobs already in scope, and that is the point — the same job is titled differently at different companies.

**Product**
Product Manager · Associate Product Manager · APM · Technical Product Manager · Product Owner · AI/ML Product Manager · Platform Product Manager · Infrastructure Product Manager · Data Product Manager · Developer Platform Product Manager · Growth Product Manager · Product Analyst

**Product Ops / Program**
Product Operations Manager · Technical Program Manager · Program Manager · Business Program Manager *(Microsoft's usual title)* · Product Operations Associate

**Strategy / BizOps**
Strategy & Operations *(often "S&O")* · Business Operations / BizOps · Business Planning & Operations *(BP&O)* · Corporate Strategy · Corporate Development · Chief of Staff · Revenue Operations · GTM Strategy & Operations · Growth Strategy · Special Projects

**Technical GTM — the new family**
Forward Deployed Engineer · Forward Deployed Software Engineer · Solutions Engineer · Sales Engineer · Pre-Sales Engineer · Solutions Architect · Customer Engineer *(Google Cloud's title)* · Partner Engineer · Partner Solutions Architect · Technical Account Manager · Implementation Engineer / Consultant · Deployment Strategist *(Palantir's title)* · Applied AI Engineer · Field Engineer · Value Engineer

**Rotational / leadership programmes — MBA-specific, high value, deadline-bearing**
Rotational Product Manager *(Meta RPM)* · MBA Leadership Development Program · Product Management Leadership Program · Business Leadership Program · Technology Leadership Program · Pathways Operations Manager *(Amazon)*

These programmes are the most deadline-sensitive rows in the whole pipeline. Capture application windows aggressively here.

**Strategic Product Lead / SPL — include it.** Confirmed by Akshat as a real title in use at Mercor and at similar AI companies. It did not surface in a generic web search because it is concentrated in the AI-startup cohort rather than being a legacy big-tech title, so treat absence from generic sources as weak evidence here. Also include the adjacent real titles **Strategic Partner Manager / Strategic Partnerships Lead** (Google, Meta, YouTube) and **Product Strategy / Product Strategy & Operations** (Stripe, Airbnb).

### One exclusion that still holds

Individual-contributor **software engineering** roles stay excluded — that reverses the pivot the MBA was for. Note the distinction from Technical GTM: Forward Deployed and Solutions roles sit in the go-to-market org, not the engineering org, and are commercial roles that require code. They are in scope. `Software Engineer`, `Backend Engineer`, `Full Stack Engineer` and similar are not.

---

## Constraints

- Don't break Lane A. The fall internship remains the immediate goal.
- Report before applying anything destructive to `jobs.xlsx`.
- Outreach is a separate repo and out of scope. It consumes `jobs.xlsx`, so keep the schema stable or flag changes.
- This is a discovery change. Resume and cover-letter generation, and the apply queue, come after volume is known.
