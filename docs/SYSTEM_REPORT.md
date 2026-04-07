# Resume Generator — System Report
**Date:** March 17, 2026 | **Version:** freeform_master_v2 | **Model:** claude-sonnet-4-6

---

## What the System Does

You paste a JD. One API call later you get a paste-ready, 11-bullet experience section
tailored to that role. No manual work. Here's what happens inside that call:

**1. Signal extraction**
The model reads the JD and identifies the 3 strongest hiring signals — the things
the role values most (e.g. "pricing strategy," "cross-functional execution,"
"AI/ML product thinking"). These drive every downstream decision.

**2. Story selection**
Three story slots are flexible: Hevo H3 (picks from Regression / Query Engine / GenAI),
Intuit I2 (picks from Prioritization Framework / Roadmap Ownership), and Optum ordering.
The AI picks the story whose subject matter best matches the JD's domain signals.

**3. Variant selection**
For each of the 11 story slots, the AI picks one of 4–5 labeled variants. Each variant
is the same underlying story framed differently — e.g. [pricing-strategy] leads with
the research-to-roadmap arc; [churn-renewal] leads with identifying billing accuracy
as a churn driver. The AI matches framing axis to JD signal.

**4. Story ordering**
Within each company block, the AI reorders stories so the most JD-relevant story
leads. For Rubrik (monetization PM), the pricing story leads at Gojek. For Typeface
(PLG), the funnel/experimentation story leads.

**5. Quality checks (automated)**
6 checks run after every generation:
- QC-01: All 4 company headers present verbatim
- QC-02: Bullet counts exactly 3/3/3/2 = 11
- QC-03: Intuit incident story (1,500+ businesses) present — protected, never dropped
- QC-04: No "leveraged" or forbidden words
- QC-05: No opening verb repeated 3+ times
- QC-06: Section 3 successfully extracted

---

## Batch Run Results — March 17, 2026 (all 7 JDs)

**QC: 42/42 checks passed across all 7 runs.**

---

### DOCUSIGN — Navigator Data Onboarding PM
**Signals:** Research-to-roadmap execution · Enterprise data platform / B2B SaaS
pipelines · PRD & requirements ownership with cross-functional leads

**Key selections:**
- G-PRICING [funnel-synthesis] leads — "synthesizing funnel analytics... into
  structured product requirements" mirrors the JD's explicit research-to-PRD arc
- H3 → H-QUERY [product-discovery] — *only* JD where Query Engine was chosen; the
  data onboarding team context makes "pipeline visibility and data exploration" a
  direct fit rather than a stretch
- I2 → I-ROADMAP [roadmap-ownership] — chosen over Prioritization because Docusign
  explicitly asks for a prioritized PRD as the internship deliverable

**Output quality: 8.5/10**
The H3=Query Engine is the sharpest pick across all 7 runs — it's genuinely
contextually right, not just the least bad option.

---

### IBM — AI Product Manager Intern
**Signals:** AI/ML product thinking · Cross-functional stakeholder communication
· Data-driven product strategy & prioritization

**Key selections:**
- H3 → H-GENAI [AI-strategy] — correctly chose GenAI over Regression/Query; IBM's
  Watson and AI-platform identity makes this the clear signal match
- O reordered: AI Affordability leads at Optum, Provider second — smart for a role
  where AI product experience is Signal 1
- G2 → G-SUPPLY [developer-API] — developer-facing API platform framing chosen to
  match IBM's emphasis on "translating technical concepts for stakeholders"

**Output quality: 8/10**
One concern: the incident response story (1,500+ SMBs) is placed as I1 (lead) with
stakeholder-coord framing. For IBM, the financial-case billing story is probably a
stronger lead since Signal 3 is data-driven strategy. The incident feels more like
a closing proof than an opener. Minor ordering judgment call.

---

### Q2 — Product Management Intern (Digital Banking)
**Signals:** Cross-functional collaboration & communication · User research &
data-driven product thinking · Roadmap planning & feature definition

**Key selections:**
- G3 → G-LATENCY [cross-functional-drive] — correctly chose the "worked with Product
  and Marketplace teams" variant to mirror Q2's cross-functional emphasis
- H3 → H-REGRESSION [platform-quality] — Q2 is a banking infrastructure platform;
  reliability/quality framing fits better than GenAI or data exploration
- I-FLEX → Prioritization [framework-design] — right call; Q2 is a broad PM role,
  not monetization-specific, so the general framework story beats roadmap ownership

**Output quality: 8/10**
Same I1 ordering note as IBM — incident leads when billing/financial might be
stronger. Otherwise solid and well-targeted to fintech context.

---

### QUALCOMM — Product Management Intern
**Signals:** Data analysis & requirement gathering · Cross-functional communication
& stakeholder alignment · Product strategy & ecosystem/platform thinking

**Key selections:**
- G2 → G-SUPPLY [ecosystem-GTM] — the only JD where ecosystem-GTM was chosen for
  supply; "multi-partner supply platform... partner integration requirements and
  onboarding workflows" mirrors Qualcomm's ecosystem partner language precisely
- H3 → H-GENAI [AI-strategy] — correct; Qualcomm is an AI silicon company, GenAI
  pipeline work is directly relevant
- O1 → O-PROVIDER [GTM-execution] — "defined integration requirements and drove GTM
  execution" mirrors Qualcomm's verbatim JD language about requirements gathering

**Output quality: 8.5/10**
The ecosystem-GTM and GenAI choices are the sharpest in this run. Qualcomm's JD
language about "review customer requirements, identify gaps" maps cleanly onto
multiple bullets here.

---

### TYPEFACE — Product Manager Intern
**Signals:** Product-led growth & experimentation · Data-driven insight & user
research · Cross-functional collaboration on intuitive product experiences

**Key selections:**
- Most heavily reordered run: all 4 company blocks reordered to lead with PLG/
  experimentation signals. Hevo leads with Monitoring (product surface ownership)
  instead of BatchShift; Optum leads with AI Affordability instead of Provider
- I-FLEX → Prioritization [framework-design] leads Intuit (backlog + cross-functional
  alignment over monetization framing — right for a PLG product company)
- I-BILLING [churn-renewal] placed second — retaining users is a PLG signal

**Output quality: 8/10**
Typeface is the hardest JD to serve because PLG-specific stories (viral loops, self-
serve onboarding, product-qualified leads) simply don't exist in the bank. The system
correctly identified what to foreground but the underlying stories are marketplace
and enterprise — not PLG-native. Story-level limitation, not a framing limitation.

---

### RUBRIK — MBA Intern, Monetization PM
**Signals:** Monetization & pricing strategy · Cross-functional stakeholder leadership
& executive communication · Analytical rigor & business case development

**Key selections:**
- Most precision-targeted run. Every Intuit bullet uses monetization-specific framing:
  I1=[churn-renewal], I2=[monetization-roadmap] ("owned the feature roadmap for
  monetization services"), I3=[financial-risk] ("coordinated remediation, refunds...
  to limit financial exposure")
- G-PRICING [pricing-strategy] leads Gojek — the WTP research + A/B + strategic
  recommendation story is the single best monetization signal in the whole bank
- H1 → H-BATCHSHIFT [business-model-pivot] — correctly frames Hevo 2.0 as a
  business model decision (what enterprise customers pay for) not an architecture one

**Output quality: 8.5/10**
The best-targeted run. H3 (regression framework) is still the weakest slot — no
Hevo story is monetization-specific enough to match the surrounding bullets. The
ceiling for this JD is ~8.5 given current raw material.

---

### VERKADA — MBA Product Management Intern
**Signals:** Pricing & monetization strategy · Customer insight → product definition
· Cross-functional execution & launch

**Key selections:**
- G-PRICING [pricing-strategy] leads — same as Rubrik, correctly identified pricing
  as Signal 1 for a hardware/security company with a pricing-strategy PM role
- G2 → G-SUPPLY [ecosystem-GTM] — partner/channel framing fits Verkada's physical
  security ecosystem (dealers, integrators)
- O1 → O-PROVIDER [GTM-execution] — "drove GTM execution for a new provider
  partnership" maps to Verkada's physical channel and launch-execution emphasis

**Output quality: 8.5/10**
Clean and well-targeted. Verkada and Rubrik produce the strongest outputs because
both are pricing/monetization roles and the bank has genuine monetization stories.

---

## Cross-Run Patterns

**What the system does consistently well:**
- Correct H3 story selection: GenAI for AI-heavy roles (Qualcomm, IBM), Query Engine
  for data platform roles (Docusign), Regression for execution/reliability roles
  (Q2, Typeface, Verkada, Rubrik)
- Monetization framing activates cleanly: when the JD signals pricing or retention,
  the system reliably picks [pricing-strategy], [churn-renewal], [financial-risk],
  and [monetization-roadmap] variants — no manual intervention needed
- Story reordering works: 5 of 7 JDs saw meaningful within-company reordering that
  improved signal alignment

**What converges across runs (watch for this):**
- G-PRICING [funnel-synthesis] is the most-used G1 variant (appears in 5/7 runs).
  If two of your applications go to the same company or the same recruiter reviews
  multiple profiles, this convergence is visible. The system has 4 other G-PRICING
  variants — consider manually overriding G1 for variety across applications.
- H2=Monitoring [feature-ownership] appears in 6/7 runs. The variant is genuinely
  strong but the consistency may read as templated to a careful reader.

---

## Hard Limitations

### 1. H3 ceiling (structural)
The third Hevo slot — Regression, Query Engine, or GenAI — is never A-tier for PM
roles. These are process/tooling stories that lack business outcome framing. There
is no fix within the current bank. Adding a genuinely PM-framed Hevo story (e.g.
Hevo's pricing model, a customer retention initiative, a new tier launch) would
unlock this slot. Until then: H3 is a B, not an A.

### 2. PLG story gap (raw material)
Typeface, and any future PLG-focused JD, will always be slightly undertargeted.
The bank has zero stories with viral coefficients, self-serve activation, PQL funnels,
or growth loops. These are things you'd need to add as new story material if you're
targeting product-led growth companies heavily.

### 3. Intuit I1 ordering (judgment call)
For non-monetization JDs (IBM, Q2, Qualcomm), the model sometimes leads Intuit with
the incident response story rather than the billing/financial story. The incident is
strong on cross-functional leadership, but the billing story's "identified churn
driver → shifted roadmap" arc is usually a stronger PM-thinking opener. This could
be addressed by adding a rule to the prompt: "prefer billing as I1 unless the JD's
primary signal is crisis management or incident response."

### 4. Title mismatch (not solvable here)
Every role is titled "Software Engineer" or "Senior Software Engineer." PM intern
recruiters know this background exists, but the title gap creates friction at the
screening stage that no bullet optimization resolves. This is handled outside the
resume — MBA program context, cover letter, referrals.

### 5. Skills section not yet built
The bottom section (Product Focus, Analytics, Tools, Community, Interests) is not
yet generated by the system. Currently it requires manual assembly. This is the
next planned build.

### 6. No doc output yet
The system outputs paste-ready text. Final formatting into a .docx with correct
fonts, margins, and ATS-safe structure is the last planned build.

---

## Output Score Summary

| JD         | Role Type            | Score | Strongest Slot           | Weakest Slot      |
|------------|----------------------|-------|--------------------------|-------------------|
| Rubrik     | Monetization PM      | 8.5   | I2 [monetization-roadmap]| H3 (regression)   |
| Verkada    | Pricing PM           | 8.5   | G1 [pricing-strategy]    | H3 (regression)   |
| Docusign   | Data Onboarding PM   | 8.5   | H3 [query/data platform] | I2 (ordering)     |
| Qualcomm   | Platform/Ecosystem   | 8.5   | G2 [ecosystem-GTM]       | H3 (GenAI thin)   |
| IBM        | AI PM                | 8.0   | H3 [AI-strategy] + O1   | I1 ordering       |
| Q2         | Fintech PM           | 8.0   | G3 [cross-functional]    | I1 ordering       |
| Typeface   | PLG PM               | 8.0   | Story reordering         | PLG story gap     |

---

## What Gets You From 8.5 to 9.5

The gap between 8.5 and 9.5 is not the system — it's the raw material. Specifically:

**Add these 3 things to the bank and the ceiling jumps:**

1. **A monetization/pricing story from Hevo** — e.g. "Evaluated two pricing models
   for Hevo 2.0's enterprise tier: per-connector vs. volume-based; recommended the
   volume model based on 12 customer interviews and competitive analysis." This story
   doesn't currently exist but the experience likely supports it.

2. **A PLG/activation story** — even one: something with a self-serve funnel, trial
   activation, or product-qualified lead framing. This unlocks Typeface, Zoom,
   Creatify, and similar JDs at a whole new level.

3. **A sharper Hevo H3 story** — either retire the regression/query/GenAI options
   and replace with a customer-facing product story that has a business outcome,
   or add a 4th Hevo story (e.g. Hevo's go-to-market to SMB vs. enterprise segment
   decision as a product strategy story).

---

## Usage

```bash
# Single run
python freeform_runner.py Rubrik
python freeform_runner.py jds/verkada.txt

# Batch — all JDs in jds/
python freeform_runner.py --batch

# Override model (default: claude-sonnet-4-6)
python freeform_runner.py Rubrik --model claude-sonnet-4-6
```

Output saved to: `runs/freeform/YYYY-MM-DD_<company>.txt`
Each file contains: JD signals → variant selection notes → paste-ready bullets → QC log

---

## Next Steps (in priority order)

1. **Fix Intuit I1 ordering rule** — add prompt instruction: prefer billing as I1
   for most roles, incident leads only when crisis/incident management is Signal 1+
2. **Add Skills section (Section 4)** — Product Focus pool + Analytics row templates
   + Tools pool + hardcoded Community/Interests
3. **Add 1–2 new stories to the bank** — monetization/pricing at Hevo, PLG story
4. **Build .docx output** — final formatted resume from paste-ready text
