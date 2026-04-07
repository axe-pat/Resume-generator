# Hevo 2.0 revised Product story

### Hevo 2 story

## **1. Context & Why This Even Existed**

> “I want to talk about Hevo 2.0, which was our strategic pivot to move upmarket from SMBs to the Enterprise segment.”
> 

**Why we needed a pivot (say this crisply):**

- **The SMB model wasn’t sustainable**
    - Low contract values
    - High churn
    - Constant treadmill of acquisition just to stay flat
- **The market was polarizing**
    - **Fivetran** dominated Enterprise with high-cost, high-reliability
    - **Airbyte** was commoditizing the low end with open-source
- Sitting in the middle as a *‘cheap SMB tool’* was a **kill zone**

> “To survive and grow, we needed customers with long-term retention, expansion potential, and real willingness to pay.”
> 

---

## **2. The User We Chose (Explicit Segmentation)**

**Target user:**

**Enterprise Data Architects / Platform Owners** at Fortune 500 companies.

**Critical difference from SMBs:**

- SMBs optimized for **speed and price**
- Enterprises optimized for **auditability, correctness, and trust**

> “These users were responsible for financial reporting and compliance. Even rare data inconsistencies were deal-breakers.”
> 

This line anchors *everything* that follows.

---

## **3. The Problem (Product–Market Misalignment)**

> “The problem wasn’t missing features — it was a mismatch between how our system worked and what this user needed.”
> 
- **Our architecture:** Streaming-first
    - Optimized for low latency
    - Continuous execution
- **Enterprise expectation:**
    - Zero-trust mindset
    - Clear failure boundaries
    - Verifiable correctness

**The core insight (keep this verbatim):**

> “We were optimizing for latency when the market demanded integrity.”
> 

Streaming failures led to:

- Partial loads
- Hard-to-audit states
- Loss of confidence during trials

> “We realized we couldn’t patch our way into Enterprise trust. We had to change the processing model itself.”
> 

---

## **4. The Strategic Solution (What We Bet On)**

> “We made a deliberate product decision to pivot from a streaming-first model to a batch-first, transactional architecture.”
> 

**Why Batch (frame it as user-aligned):**

- Bounded execution windows
- Atomic success or rollback
- Clear auditability

**The tradeoff (explicitly acknowledge):**

- Higher system complexity
- Slower perceived speed
- Significant engineering investment

> “Batch increased correctness, but it also increased cognitive load — which is why we treated observability as a first-class product, not an afterthought.”
> 

(This sets up JM naturally without going deep yet.)

---

## **5. Outcome & Metrics (So What?)**

> “The launch was a turning point.”
> 
- **Enterprise adoption:**
    
    Onboarded **8 enterprise customers** within 90 days once we could meet strict SLAs
    
- **User impact:**
    
    Job Monitoring reduced **time to identify failures by ~40%** for on-call engineers
    
- **Strategic validation:**
    
    We migrated the customer base without churn, proving the rewrite unlocked reliability *without* breaking existing users
    

> “Reliability went from being the reason deals died to something sales could confidently sell.”
> 

### Final structure :

## **1. Context & the Question We Were Facing**

> “I want to talk about a product I worked on at Hevo Data, where we had to answer a fundamental question about the future of the business.”
> 

**The question was:**

> How do we build a sustainable data platform when the market is splitting into two extremes — cheap and flexible on one end, and expensive but highly reliable on the other?
> 

### **What triggered this question**

- **The SMB model had taken us far — but was starting to plateau**
    - **We had strong early adoption among startups and growth-stage companies**
    - **The product was easy to adopt and delivered fast time-to-value**
    - This helped us build revenue and brand credibility in the SMB segment
- **But the economics stopped scaling**
    - **Contract values stayed small**
    - Churn increased as SMBs shut down, got acquired, or switched tools
    - **Growth increasingly came from replacing churn rather than expansion**
- **At the same time, the market around us was polarizing**
    - **Fivetran** dominated Enterprise with high-cost, high-reliability
    - **Airbyte** was commoditizing the low end with open-source
    - Sitting in the middle as a *“managed but low-cost SMB tool”* was becoming a **kill zone**

> “What changed was the slope. The model that helped us grow early was no longer compounding. **We weren’t in trouble yet — but we could clearly see where we would plateau if we didn’t evolve**.”
> 

---

## **2. The User We Chose (Explicit Segmentation)**

> “Once we framed the problem, the next decision was who we were really building for.”
> 

**Target user:**

**Enterprise Data Architects / Platform Owners** at Fortune 500 companies.

**Critical difference from SMBs:**

- SMBs optimized for **speed and price**
- Enterprises optimized for **auditability, correctness, and trust**

> “These users were responsible for financial reporting and compliance. Even rare data inconsistencies were deal-breakers.”
> 

This user choice **anchored every downstream decision**.

---

## Core Problem

> “The core problem wasn’t that we were serving SMBs — it was that our architecture was optimized for a use case most customers didn’t actually need.”
> 

At the time, Hevo was built on a **streaming-first architecture**, optimized for low latency and continuous execution. This worked well early on, but as the product scaled, we started questioning whether we were solving the *right* problem.

> “Instead of assuming real-time was inherently valuable, we looked closely at how customers were actually using the product.”
> 

**What we learned from customer behavior and feedback:**

- Across both SMBs and larger teams, most pipelines powered:
    - Hourly analytics
    - Operational dashboards
    - Daily or periodic reporting
- Very few customers truly needed millisecond-level freshness
- For the majority, **15-minute freshness was more than acceptable**

Importantly, we also realized this didn’t mean giving up “near real-time” use cases entirely.

> “We already supported rolling micro-batches, which allowed us to deliver near–real-time behavior when needed, without requiring pure streaming semantics.”
> 

So the real user need wasn’t:

- *“Data must arrive instantly”*

It was:

- *“Data must arrive predictably, correctly, and be safe to reason about.”*

What mattered far more than raw speed was:

- Knowing the data was **complete**
- Being confident it was **consistent**
- Being able to **reason about failures and retries**

This led to the core insight:

> “We were optimizing for latency when the market — across segments — demanded integrity.”
> 

In practice, the streaming model made failures harder to reason about:

- Partial loads were difficult to audit
- Retries risked duplication
- Even rare inconsistencies eroded trust, especially during larger trials

> “We realized this wasn’t something we could patch around. The issue wasn’t missing features — it was that our execution model itself was misaligned with how customers actually derived value from the product.”
> 

---

## **4. The Strategic Decision & Tradeoff**

> “We explored a few paths, but the hardest decision came down to this tradeoff:
> 
> 
> **continue shipping features for SMB velocity, or slow down to rebuild the foundation for enterprise trust.**”
> 

**The decision we made:**

> Pivot from a streaming-first model to a batch-first, transactional architecture.
> 

**Why batch aligned with this user:**

- Bounded execution windows
- Atomic success or rollback
- Clear auditability for compliance

**What we gave up (explicit tradeoff):**

- Slower perceived speed
- Paused feature velocity
- Significant engineering investment

> “Batch dramatically improved correctness, but it also increased system and user complexity — which is why we treated observability as a first-class product, not an afterthought.”
> 

(This cleanly sets up Job Monitoring when needed.)

---

## **5. Outcomes & How We Measured Success**

> “The launch was a turning point for the company.”
> 

**Business impact:**

- **8 enterprise customers onboarded** within 90 days once we could meet strict SLAs
- Expansion-ready contracts replaced high-churn SMB deals

**User impact:**

- Job Monitoring reduced **time to identify failures by ~40%** for on-call engineers

**Strategic validation:**

- Migrated the existing customer base without churn
- Reliability went from *“the reason deals died”* to *“something sales could confidently sell”*

> “The biggest validation was that reliability stopped being a risk conversation and became a selling point.”
> 

### How this answers all qqs :

## How this one story answers all middle questions (via reordering)

Here’s the exact mapping you asked for:

---

### 🟦 “Tell me about a product you worked on”

**Order:**

1 → 2 → 3 → 4 → 5

(What you just refined)

---

### 🟦 “Tell me about a difficult tradeoff”

**Order:**

4 → 1 → 3 → 5

Open with:

> “The hardest tradeoff was choosing reliability over feature velocity…”
> 

> The hardest tradeoff was pausing feature velocity in order to invest in correctness and long-term reliability.
> 

Then give just enough context to justify it.

---

### 🟦 “Tell me about a product decision you influenced”

**Order:**

4 → 3 → 2 → 5

Lead with:

> “The decision was whether to rebuild the core or keep shipping features…”
> 

---

### 🟦 “How did you prioritize?”

**Order:**

3 → 4 → 1 → 5

Frame prioritization as:

> “Given these constraints, here’s what we didn’t build.”
> 

---

### 🟦 “Tell me about a complex product”

**Order:**

3 → 2 → 4 → 5

Emphasize:

- Zero-trust users
- Atomicity
- Observability

---

### 🟦 “How did you define success?”

**Order:**

5 → 3 → 4

Start with metrics, then reverse-engineer the logic.

### JM story :

“As part of a larger platform rebuild where we shifted to more reliable, batch-based execution, we dramatically improved correctness — but that exposed a new problem around how users understood what was happening.”

## **1. Context (Why This Existed)**

> “As part of the Hevo 2.0 rebuild, we significantly improved backend reliability — but that exposed a new problem.”
> 

> The question became: How do we make a highly reliable system actually feel reliable to the people on call for it?
> 

> “We realized that backend correctness alone wasn’t enough. If users couldn’t quickly understand what happened and what to do next, they still wouldn’t trust the platform.”
> 

This frames JM as **necessary**, not incremental.

---

## **2. User (Be Explicit)**

**Primary user:**

Enterprise **Data Engineers / Data Architects** running high-volume pipelines in production.

**Key user truth (keep verbatim):**

> “These users weren’t just running pipelines — they were on call for them.”
> 

What they cared about:

- Is downstream data safe?
- What failed, exactly?
- What action do I take right now?

---

## **3. Problem (User Pain, Not System Pain)**

> “Ironically, as the system became more reliable internally, it became harder for users to understand what was happening.”
> 

Why:

- Batch execution created **thousands of runs**
- Failure signals were scattered across logs and metadata
- Users couldn’t answer basic questions quickly:
    - *Did this run fully succeed?*
    - *Is this a partial failure?*
    - *Is it safe to retry?*

**Anchor line:**

> “Reliability without visibility still feels like unreliability to users.”
> 

---

## **4. Solution & Tradeoffs (Product Decisions)**

> “We designed Job Monitoring as the canonical execution narrative for the platform.”
> 

**Core product decisions:**

- **Run-centric model:** Every execution had a clear lifecycle
- **Batch-level grouping:** Users reasoned in meaningful windows, not events
- **Failure clarity over exhaustiveness:** Clear state, safe retries
- **Single pane of glass:** No jumping between tools

**Explicit tradeoffs:**

- Simplicity over raw completeness
- Correctness over UI speed
- Optimized first for on-call engineers

> “The goal wasn’t to expose everything — it was to expose the right abstractions.”
> 

---

## **5. Outcome & Validation**

**User impact:**

- ~40% reduction in time to identify failures
- On-call engineers could act without platform support
- JM became the default investigation entry point

**Product impact:**

> “JM shifted conversations from ‘Is the system broken?’ to ‘I understand what happened and what to do next.’”
> 

That’s the win.

### JM story final

## **1. Context (Why This Existed)**

> “After a platform rebuild where we significantly improved backend correctness, we realized users still didn’t trust the system — because they couldn’t quickly understand what was happening.”
> 

The system was more reliable than before, but incidents were still stressful and slow to resolve.

> “The gap wasn’t backend reliability — it was how that reliability surfaced to users during failures.”
> 

This is where Job Monitoring came in.

---

## **2. User (Be Explicit and Grounded)**

**Primary user:**

Enterprise **Data Engineers / Data Architects** running high-volume pipelines in production.

**Key user truth (keep this):**

> “These users weren’t just running pipelines — they were on call for them.”
> 

In practice, that meant:

- They were paged when something broke
- They had minutes, not hours, to decide whether data was safe
- They were accountable for downstream impact, not just pipeline status

---

## **3. The Problem (What *Actually* Didn’t Work for Users)**

> “When something failed, users couldn’t quickly answer the questions that mattered most.”
> 

Specifically, **three things broke down**:

### 1️⃣ **Failure state was ambiguous**

- A pipeline could show as “failed,” but users couldn’t tell:
    - Was it a partial failure?
    - Did some destinations succeed?
    - Was downstream data corrupted or safe?

### 2️⃣ **Information was fragmented**

- Run metadata lived in one place
- Logs lived somewhere else
- Retry actions were disconnected from context

> “Users had to mentally stitch together what happened across multiple tools while already under pressure.”
> 

### 3️⃣ **Scale made things worse**

- Batch execution created **thousands of runs**
- There was no way to:
    - Quickly isolate the *important* failures
    - Prioritize runs with the highest blast radius
    - Answer questions like:
        - *‘Show me all failures in the last hour’*
        - *‘Which runs failed more than N times?’*
        - *‘What’s blocking today’s critical dashboards?’*

**Anchor line (now very concrete):**

> “Reliability without fast, actionable visibility still feels like unreliability — especially during incidents.”
> 

---

## **4. Solution & Tradeoffs (Product Decisions)**

> “We designed Job Monitoring as the canonical execution and decision surface for the platform.”
> 

### Core product decisions

- **Run-centric execution model**
    
    Every pipeline execution had:
    
    - **A clear lifecycle**
    - **Explicit success / partial / failure states**
    - **Safe-to-retry indicators**
- **Batch-level grouping**
    
    Runs were grouped into meaningful execution windows so users could reason in **units of work**, not individual events.
    
- **Filtering & sorting for triage (important but scoped)**
    
    We added:
    
    - Filters for failure count, status, and time windows
    - Sorting by recency and severity
        
        → so on-call engineers could immediately focus on **what mattered most**
        
- **Single pane of glass**
    
    All of this lived in one place — no context switching during incidents.
    

**Explicit tradeoffs (judgment signal):**

- **Clarity over exhaustiveness** — we hid low-level noise
- **Correctness over speed** — some views loaded slower but were always accurate
- **Triage over exploration** — optimized first for incident response, not analytics

> “The goal wasn’t to expose everything — it was to help users make the right decision quickly.”
> 

---

## **5. Outcome & Validation**

**User impact:**

- ~**40% reduction** in time to identify and act on failures
- On-call engineers could assess data safety without platform support
- Incident response became more predictable and less stressful

**Product impact:**

> “JM shifted conversations from ‘What broke?’ to ‘I understand what happened and what I should do next.’”
> 

That’s when reliability actually became **usable**.

### How this answers qqs :

## 🟦 Category A — Product Ownership & Execution

### 1️⃣ *Tell me about a feature you owned end-to-end*

**Use JM → primary**

**Order:**

1. Context
2. User
3. Problem
4. Solution & Tradeoffs
5. Outcome

**Why it works:**

- Clear ownership boundary
- Concrete scope
- Shipped impact
- Metrics tied directly to the feature

This is **JM’s strongest use case**.

---

### 2️⃣ *Tell me about a product you improved*

**Use JM → primary**

**Order:**

1. Problem
2. Insight
3. Solution
4. Outcome

**Angle:**

- Existing platform became more reliable
- You improved *usability and trust*, not just features

---

## 🟦 Category B — User Experience & Simplification

### 3️⃣ *How do you translate complexity into a good user experience?*

**Use JM → primary**

**Order:**

1. User
2. Problem (incident-time confusion)
3. Solution (abstractions, filtering, run model)
4. Tradeoffs

**Why it works:**

- Clear articulation of *what not to expose*
- Strong abstraction judgment
- Filtering/sorting as decision tools, not UI sugar

---

### 4️⃣ *Tell me about a time you simplified something complex*

**Use JM → primary**

**Order:**

1. Problem
2. Tradeoff (clarity vs completeness)
3. Solution
4. Outcome

**Key line to emphasize:**

> “The goal wasn’t to expose everything — it was to expose the right abstractions.”
> 

---

## 🟦 Category C — Product Judgment & Tradeoffs

### 5️⃣ *Tell me about a tradeoff you made*

**Use JM → secondary (execution-level tradeoff)**

**Order:**

1. Tradeoff
2. Problem
3. Solution
4. Outcome

**Tradeoffs to highlight:**

- Simplicity vs power
- Speed vs correctness
- Triage vs exploration

This complements (not replaces) the **Hevo tradeoff**.

---

### 6️⃣ *How did you prioritize what to build?*

**Use JM → strong**

**Order:**

1. User (on-call urgency)
2. Problem (what blocks decisions)
3. Solution (what you built *first*)
4. Outcome

**Emphasize:**

- You optimized for **incident response**, not dashboards
- Filters/sorting built to surface *what matters now*

---

## 🟦 Category D — Trust, Reliability & Observability

### 7️⃣ *How do you think about observability?*

**Use JM → primary**

**Order:**

1. Problem
2. Insight (observability ≠ logs)
3. Solution
4. Outcome

**Core framing:**

> “Observability is about confidence and decision-making, not raw visibility.”
> 

This is a very **senior PM answer**.

---

### 8️⃣ *Tell me about a time users didn’t trust the system*

**Use JM → primary**

**Order:**

1. Problem
2. User pain
3. Solution
4. Outcome

**Key idea:**

- Backend reliability existed
- Perceived trust did not
- JM closed that gap

---

## 🟦 Category E — Metrics & Impact

### 9️⃣ *How did you define success for a product you worked on?*

**Use JM → strong**

**Order:**

1. Outcome
2. Problem
3. Solution

**Metrics to cite:**

- Time to identify failures (~40%)
- Reduction in support escalation
- JM becoming default entry point

---

### 🔟 *Tell me about a product that didn’t work initially*

**Use JM → optional**

You can say:

- Early versions surfaced too much raw data
- Users were still overwhelmed
- Iterated toward abstractions + filters

This is optional, but available.

---

# Google specific stuff (Ignore for other interviews)

## A) 5 QUESTIONS THIS TEAM IS VERY LIKELY TO ASK

## 1️⃣ “How would you improve reading accessibility across Google products?”

### What they’re *actually* testing

- Can you think **platform-first**, not feature-first?
- Do you avoid designing one-off UX?

### Insight to carry

> Start from capabilities, not screens.
> 

Say things like:

- Shared reading primitives (font, spacing, highlights)
- Consistent APIs across Chrome / Android / Web
- Accessibility defaults, with user override

❌ Don’t jump straight into a Chrome feature mock.

---

## 2️⃣ “How would you design for users with dyslexia or ADHD?”

### What they’re testing

- Do you understand **cognitive load**, not just disability labels?
- Can you avoid stereotyping users?

### Insight to carry

> Disabilities vary — customization > assumptions.
> 

Strong angles:

- Adjustable reading modes
- Progressive assistance (off → light → strong)
- User control over summarization / focus

❌ Avoid “one dyslexic mode.”

---

## 3️⃣ “How do you balance accessibility with performance or simplicity?”

### What they’re testing

- Tradeoff thinking
- Core maturity

### Insight to carry

> Accessibility should be cheap by default, not expensive by choice.
> 

Good framing:

- Baseline accessibility baked in
- Advanced support opt-in
- Platform abstractions reduce per-team cost

❌ Don’t frame accessibility as a tax.

---

## 4️⃣ “How would you measure success for accessibility features?”

### What they’re testing

- Do you know how to measure **invisible wins**?

### Insight to carry

> Use proxy metrics, not just engagement.
> 

Examples:

- Task completion rate
- Reduced time-to-comprehension
- Fewer retries / drop-offs
- Qual + longitudinal feedback

❌ Avoid “DAU” as your main metric.

---

## 5️⃣ “How would you ensure other teams actually adopt what Core builds?”

### What they’re testing

- Whether you understand **enablement, not authority**

### Insight to carry

> Adoption comes from defaults + ergonomics, not mandates.
> 

Good answers include:

- Easy APIs
- Good documentation
- Clear incentives
- Making the right thing the easiest thing

❌ Don’t say “we’d require teams to…”

### Above thing Detailed

# 1️⃣ Clarifying Question #1

### *“How would you improve reading accessibility across Google products?”*

You’re right to be confused — on the surface it sounds vague.

Here’s what it **does NOT** mean:

❌ “Design a new Chrome reading feature”

❌ “Add one dyslexia mode”

❌ “Improve a single app”

---

### What it ACTUALLY means (Core lens)

It means:

> “If you were responsible for the foundations that enable reading accessibility across many products, how would you approach the problem?”
> 

Key difference:

- **Feature PM** → What should Chrome do?
- **Core PM** → What should *every team* get for free?

---

### Example mental shift

Instead of:

> “I’d add a simplified reading view in Chrome”
> 

Think:

> “I’d define a shared ‘reading accessibility layer’ that products like Chrome, Search, Docs, and Android can all plug into.”
> 

This is the **Core abstraction leap** they’re testing for.

---

### Concrete things they expect you to think about

- Common primitives:
    - Font controls
    - Line spacing
    - Highlighting
    - TTS hooks
- APIs teams can call
- Consistency across platforms
- User preferences that follow the user

They want to see:

> “Does this person naturally think one layer higher?”
> 

---

# 2️⃣ Deepening all 5 questions (so they actually make sense)

---

## 1️⃣ Improve reading accessibility across Google products

### What’s hard here

- Many products
- Different surfaces
- Different user needs

### What good answers show

- You start with **shared needs**
- You design **reusable capabilities**
- You allow **local customization**

### Simple answer skeleton

> “I’d start by identifying the common reading challenges, define platform-level primitives to address them, and let individual products compose those primitives differently.”
> 

---

## 2️⃣ Designing for dyslexia or ADHD

### The trap

Treating dyslexia/ADHD as:

- One condition
- One solution

### What they want

Understanding that:

- Needs vary widely
- Users often don’t want labels
- Control matters more than correctness

### Key insight

> Accessibility is about reducing cognitive load, not diagnosing users.
> 

So you talk about:

- Adjustable support
- Progressive assistance
- User control

---

## 3️⃣ Balancing accessibility with performance or simplicity

### Why this is a Core question

Core teams *always* face this:

- More options = complexity
- More features = perf risk

### What good looks like

You say:

- Accessibility is not “extra”
- Baseline support is default
- Advanced support is opt-in

Key framing:

> “The goal is to make accessibility cheap for teams and invisible for users unless they need it.”
> 

---

## 4️⃣ Measuring success for accessibility

### Why this is tricky

- Success is often absence of friction
- Users may never explicitly say “this helped”

### What they want to hear

- Proxy metrics
- Behavioral signals
- Long-term impact

Examples:

- Reduced abandonment
- Faster task completion
- Fewer retries
- Qual feedback loops

You’re showing **maturity** here.

---

## 5️⃣ Ensuring adoption by other teams

### Why this is Core-critical

Core teams fail if:

- Teams ignore their tools
- APIs are hard to use
- Docs are bad

### What good PMs say

- Make it the default
- Make it easy
- Make it beneficial

Key sentence:

> “Adoption is a product problem, not an enforcement problem.”
> 

---

# 3️⃣ Your marketing / discoverability insight — this is VERY sharp

You’re asking:

> “If these features exist, why don’t people know about them?”
> 

This is **not a naive question** — it’s a **Core-level insight**.

---

### What’s likely happening (informed reasoning)

- Many accessibility features are:
    - Buried in settings
    - Activated only when needed
    - Designed to be invisible by default
- Users who need them often discover them:
    - Through advocacy groups
    - Through OS onboarding
    - Through support channels

So yes:

> You probably don’t know about them because you’re not the target user.
> 

And that’s *intentional*, to some extent.

---

### But here’s the Core tension (THIS IS GOLD)

> If features are too hidden → underutilized
> 
> 
> If features are too promoted → noisy / stigmatizing
> 

This is a **fantastic Core P4A problem**.

---

## Turn this into a GREAT question to ask them

Here are **two excellent versions** — pick ONE.

### Option 1 (discoverability-focused)

> “Accessibility features often walk a line between being discoverable and being unobtrusive. How does the team think about helping users find the support they need without making the experience noisy or stigmatizing?”
> 

### Option 2 (marketing / awareness angle)

> “For accessibility features that are built into the platform, how do you think about awareness and adoption, especially for users who might benefit but don’t self-identify as having a disability?”
> 

Both are:

- Thoughtful
- Team-specific
- Not something a generic PM would ask

---

# Final takeaway (important)

If you walk in with:

- Platform-first thinking
- Respect for variability
- Sensitivity to invisibility vs discoverability
- Curiosity about adoption, not just features

You will **feel native to Core P4A**, not like an outsider.

If you want next, we can:

- Practice answering **Question #1 live**
- Or craft **2–3 Core-specific sound bites** you can reuse across answers

You’re thinking about the right things.

### B) 5 QUESTIONS YOU SHOULD ASK *THEM* (Core P4A–smart)

## 1️⃣ “How do you think about success for Core teams, given much of the impact is indirect?”

Signals:

- You understand invisible work
- You respect platform impact

---

## 2️⃣ “What’s been hardest about scaling accessibility across so many products?”

Signals:

- Systems thinking
- Curiosity about real constraints

---

## 3️⃣ “Where do you see the biggest tension today — between flexibility for users and consistency across platforms?”

Signals:

- Tradeoff awareness
- Core PM maturity

---

## 4️⃣ “How does Core partner with feature teams when accessibility needs differ by region or user group?”

Signals:

- International + P4A awareness
- Cross-team collaboration instincts

---

## 5️⃣ “What does great PM judgment look like on this team six months in?”

Signals:

- You’re thinking about **how to be effective**, not just getting the job

### 3 QUESTIONS YOU SHOULD ASK *THEM*

Accessibility features often walk a line between being discoverable and being unobtrusive. How does the team think about helping users find the support they need without making the experience noisy or stigmatizing?

“Because Core teams often have indirect impact, how do you think about measuring success and progress for PMs on this team?”

“What’s been hardest about getting accessibility foundations adopted consistently across different product teams?”

**“What does strong PM judgment look like on this team in the first six months?”**