# Interview Answer Engine

This is the lightweight taste model for TMAY and "Why this company?" answers. It borrows the same idea as the resume and cover-letter bank: score what works, name what fails, then write against guardrails.

## What A Great TMAY Must Do

### Non-Negotiable TMAY Rule

TMAY is not a background summary. It is the first positioning surface of the interview.

Every sentence must do one of four jobs:

- establish credible range, scale, or maturity
- show agency in the engineering-to-PM transition
- plant a role-specific signal the interviewer is already screening for
- create a clean hook for follow-up questions

If a sentence is merely true, cut it. If it is true and useful for this JD, keep it.

### 6/10 TMAY

- Chronological resume summary.
- Mentions MBA, engineering background, startup, and AI.
- Correct but forgettable.
- Could be used for any PM internship by swapping the company name.

Failure mode: "I have X background, I like Y, this role combines X and Y."

### 8/10 TMAY

- Has a clean career arc.
- Names the transition from engineering execution to product judgment.
- Uses one strong story, usually Hevo or Gojek.
- Connects the role to a real pattern in Akshat's career.

Still missing: a memorable claim about what Akshat uniquely sees.

### 9/10 TMAY

- Opens with identity, but quickly moves into a thesis.
- Has one clear turn: "I realized X, and that changed what I wanted to own."
- Uses one lived example as proof, not a list of jobs.
- Ends with why this role is the next honest test of that thesis.
- Sounds like Akshat: direct, specific, slightly personal, not over-polished.
- Plants "Easter eggs" for the interviewer: startup proximity, founder/PM adjacency, exact JD skill signals, and a natural follow-up story.

Strong TMAY template:

1. Static ground: "I am Akshat..." + domain breadth + large-company maturity.
2. Large-company extraction: name the most JD-relevant skill learned at Optum/Intuit, not generic reliability.
3. Agency turn: "I felt I was too far downstream..." or similar.
4. Startup proof: Hevo as the chosen transition, especially when the target is a startup/growth company.
5. Current builder proof: AI side project only if it maps to the JD.
6. Role landing: why this exact role is the logical next test.

## Static Opening Guidance

Preferred base:

> "I'm Akshat, a first-year MBA at USC Marshall. Before business school, I spent about five years as a software engineer across logistics, fintech, healthcare, and SaaS. I started at larger companies like Optum and Intuit..."

After that, do not use generic phrases like:

- "reliability, latency, and data quality had real business consequences"
- "large-scale systems"
- "cross-functional teams"

Unless they are translated into the JD's language.

Examples:

- For AI conversation / ambiguity roles: "I learned to untangle messy workflows where each team saw only a slice of the issue, ask better questions before jumping to solutions, and turn scattered inputs into a plan people could align around."
- For compliance / trust-heavy roles: "I worked on billing, healthcare, and provider workflows where unclear system behavior quickly became a customer trust or financial-risk problem."
- For startup/founder roles: "Those larger companies gave me depth and operating discipline, but I wanted to move closer to product decisions end-to-end."

## Story Selection Rules

Pick the one highlighted experience based on the JD:

- Hevo Data: best when the role values startup proximity, enterprise SaaS, PM-adjacent work, product strategy, Principal PM/founder adjacency, trust, observability, or upmarket motion.
- Gojek: best when the role values consumer behavior, metrics, conversion, marketplace dynamics, pricing, funnel analysis, or very large-scale product impact.
- Optum: best when the role values healthcare, regulated AI, stakeholder approval, responsible AI, risk controls, or clinical/business workflow design.
- Intuit: best when the role values fintech, billing, monetization, SMBs, cross-functional prioritization, roadmap tradeoffs, or ambiguity across many teams.

Do not include Gojek just because it is recent. Do not include Hevo just because it is easy. The selected story must be the cleanest proof for the JD.

## Retrieval Guard

Before drafting TMAY or Why, run a story-retrieval pass against the role's exact nouns and verbs. Do not rely only on the stories already surfaced in the active prep doc.

Minimum local searches:

- Search the active prep folder.
- Search `docs/reference/STORY_BANK_RICH.md`.
- Search `resume/freeform/prompts/freeform_master_v2.txt`.
- Search `docs/variants/VARIANT_FINALS_v4.md`.
- Search `cover_letters/story_bank/`.

For AI roles, explicitly search:

- `H-MONITORING-AI`
- `GenAI`
- `AI-powered monitoring`
- `failure taxonomy`
- `incident card`
- `actionable insights`
- `silent failure`
- `conversation data`
- `drop off`

If the JD has `AI`, `conversation`, `behavior`, `logs`, `drop off`, `next action`, `insights`, or `requirements`, check whether `H-MONITORING-AI`, `Gojek latency`, `Optum AI affordability`, or `ResumeGenerator` is a better proof story than plain Hevo 2.0.

Failure to avoid:

- Using `Hevo Job Monitoring` as a generic trust story when `H-MONITORING-AI` is the sharper AI product story.
- Using a current prep shortlist as the full story universe.
- Choosing the easiest story instead of the most JD-shaped story.

## What A Great "Why This Company" Must Do

### 6/10 Why

- Praises the company.
- Repeats the JD.
- Says the role combines AI, PM, and startup impact.

Failure mode: "Your company is exciting because AI is the future."

### 8/10 Why

- Names a real product tension.
- Connects the company to a past experience.
- Includes why Akshat likes the operating environment.

Still missing: a point of view on the product.

### 9/10 Why

- Starts with a specific product/company tension, not praise.
- Shows why Akshat has earned intuition in that space.
- Names what he would be curious to diagnose first.
- Includes one human reason for the environment: close to leadership, small team, fast feedback.
- Has a sentence the interviewer could remember.

Strong Why template:

1. Product tension: "What is hard about this company/product is..."
2. Earned intuition: "I have seen a version of that at..."
3. Builder/current relevance: "I have also been building..."
4. Startup/team fit: "The environment matters because..."
5. Memorable close: "That is the kind of problem I want to be close to."

## Akshat Voice Guardrails

- Preserve scar tissue. If the rough answer has a real lived angle, keep it.
- Keep the "I realized..." moment. That is where the answer becomes human.
- Use one strong analogy or sentence, not five polished slogans.
- Prefer "what I learned" over "what I am passionate about."
- Prefer "the product problem is..." over "I am excited because..."
- Mention side projects only when they prove builder energy or domain intuition.
- Avoid generic MBA-clean phrasing that erases specificity.

## Scoring Rubric

Score each answer out of 10:

- Career arc: does it explain the move from engineering to PM?
- Specificity: could another candidate say this?
- Role fit: does it match the exact product problem?
- Proof: is there one real story doing work?
- Voice: does it sound like Akshat, not a prompt?
- Memorability: is there one sentence worth remembering?

Reject if:

- It is mostly a JD summary.
- It lists too many experiences without a turn.
- It overclaims ML/product ownership.
- It sounds like cover-letter prose read aloud.
- It ends with generic enthusiasm.
