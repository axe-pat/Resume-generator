# Day 6 – December 16

## Behavioural :

### TMAY

I’m Akshat, I grew up in New Delhi. I’m a computer engineer by training and currently an MBA student at USC Marshall, recruiting for Product Management roles.

Before business school, I spent about five years as a software engineer building and optimising backend systems that handled critical healthcare, billing, and marketplace data at companies like Optum, Intuit and Gojek.

Over my career I moved from feature building to architecting critical backend systems—like automated data reconciliation engines and revenue-critical APIs. I spent a lot of time thinking about failure modes, edge cases, and how systems behave under load, because I learned that at scale, reliability isn’t just a technical metric; it’s a form of user trust.

Over time, I realized I wanted to shape products, not just build them. That’s what led me to Hevo Data, a high-growth startup, where I got much closer to product thinking — analyzing the market, understanding enterprise customer needs, and working closely with PMs and leadership as we repositioned the product from an SMB tool to an enterprise-grade platform. That experience was my first real exposure to roadmap tradeoffs and product strategy, and it’s where my interest in PM really clicked.

I later returned to Gojek as a Senior Engineer, where I applied that product mindset at massive scale — working on ride-hailing workflows and platform reliability that affected millions of users.

I’m excited about Google because Core teams sit exactly at the intersection I care about: deep technical complexity and user enablement. Building infrastructure that is reliable, scalable, and quietly unlocks impact for millions is where I’ve done my best work, and where I’m excited to grow as a Product Manager.

### TMAY2

I’m Akshat, I grew up in New Delhi. I’m a computer engineer by training and currently an MBA student at USC Marshall, recruiting for Product Management roles.

Before business school, I spent about five years as a software engineer building and optimising backend systems that handled healthcare, billing, and marketplace data at companies like Optum, Intuit and Gojek.

Early in my career, I moved from feature development to owning and architecting business-critical backend systems.

Over time, I realized I wanted to influence not just how systems are built, but what gets built and why. That led me to a high-growth startup, where the engineering role came with much closer exposure to product thinking. I partnered closely with PMs and leadership to analyse market and customer needs, and help reposition the product for an upmarket shift. That experience was my first real immersion in product strategy, and it’s where my interest in PM truly solidified, ultimately leading me to business school.

I’m excited about Google because it sit exactly at the intersection I care about — deep technical complexity and user enablement. Building infrastructure that unlocks impact for millions.

### TMAY3 (Core P4a coded)

I’m Akshat, I grew up in New Delhi. I’m a computer engineer by training and currently an MBA student at USC Marshall, recruiting for Product Management roles.

Before business school, I spent about five years as a software engineer building and optimising backend systems at companies like Optum, Intuit and Gojek.

Early in my career, I moved from feature development to owning and architecting business-critical backend systems.

Over time, I realized I wanted to influence not just how systems are built, but what gets built and why. That led me to a high-growth startup, where the engineering role came with much closer exposure to product thinking. I partnered closely with PMs and leadership to analyse market and customer needs, and help reposition the product for an upmarket shift. That experience was my first real immersion in product strategy, and it’s where my interest in PM truly solidified, ultimately leading me to business school.

What ultimately draws me to Google—and specifically to the Core organization—is the challenge of solving questions that don’t have obvious answers, and improving the lives of Millions with those answers. My first window into this was in a mobile school van in New Delhi. I saw how a single Android phone, equipped with the right assistive tools, could completely change a child's learning trajectory by dissolving barriers they didn't even know they could cross.

### TMAY final

I’m Akshat, a computer engineer by training and currently an MBA candidate at USC Marshall. 
I worked as a SE for 5 years and my career has been a journey from owning the *how* of backend systems to wanting to define the *why* behind product decisions.

I started career at companies like Optum and Intuit, where I moved from feature work to architecting and owning business-critical systems. These were environments where **reliability and serving diverse user needs** weren’t just technical goals — they were foundational.

Over time, I wanted visibility into products end-to-end — not just how systems were built, but how technical tradeoffs translated into customer outcomes and business decisions. In a later role, I worked very closely with a PM on a major platform shift, balancing architecture decisions with product strategy. 

That experience is what led me to USC Marshall to pivot into Product Management.

**What ultimately draws me to Google is its unique ability to solve problems at a scale where a 1% improvement impacts millions**. 

Specifically, my interest in the **Core/P4A** team stems from a memory of me volunteering for a mobile school van for underserved children in a slum near new Delhi. Where I saw a child use an Android phone with **Read Along** to overcome a learning barrier traditional teaching hadn’t addressed.

I see Core as the 'Engine Room' of Google. You aren’t just building apps; you’re building the **primitives and standards** that sit underneath everything. 
I want to bring my background in reliability to ensure that accessibility is the path of least resistance for every developer at Google.

## Product Stories :

## Story 1

## Product Story 1 : **Hevo 2.0**

### The Context & User (The "Why")

"I want to talk about the launch of **Hevo 2.0**, which was our strategic pivot to break into the Enterprise market. using a complete rebuild of our product from a Monolith to a Microservices architecture.

- **The Market Trap:** At the time, Hevo was dangerously squeezed in the middle. **Fivetran** owned the enterprise with a high-cost, high-reliability model. **Airbyte** was eating the low end with open-source flexibility. We were positioned as the 'low-cost alternative' for SMBs, which meant we suffered from high churn and low contract values.
- **The Goal:** To survive and grow, we needed to move upmarket. We wanted to acquire **Enterprise Data Architects** at Fortune 500 companies—expanding our Total Addressable Market (TAM) beyond just startups.
- **The User:** Unlike our existing SMB users who valued 'speed and price,' these new Enterprise Architects prioritized **Auditability and Reliability**. They were managing mission-critical data for finance and compliance.

### The Problem

The problem was a fundamental mismatch between our architecture and this new user's needs.

- **Speed vs. Reliability:** Our platform was built on a **Streaming-First** architecture. This was great for speed (low latency), but it made guaranteeing 100% data consistency difficult.
- **The Trust Gap:** Enterprise Architects operate in a 'Zero Trust' environment. They need to know that if a network failure happens, the system will self-heal perfectly.
- **The Architectural Blocker:** Our streaming approach meant that failures often resulted in partial data loads or difficult-to-trace errors. We realized we couldn't just 'patch' this; we were optimizing for *latency* (speed) when the market demanded *integrity* (atomicity). To win the Enterprise, we had to fundamentally change how we processed data."

### ~~The Solution: Hevo 2.0 (The "Star")~~

To win this market, the company made a massive bet: moving from a monolithic, streaming-first architecture to a **Microservices-based 'Glass Box' platform**.

The high-level strategy had two pillars:

1. **Tenant Isolation:** Breaking the monolith so that one large client’s load wouldn't crash the system for everyone else.
2. **Transactional Guarantees:** Moving from 'best-effort' streaming to rigorous 'exactly-once' processing."

We built the new platform around three core product pillars:

1. **Guaranteed Delivery:** Moving from 'Best Effort' streaming to 'Transactional' batching to ensure zero data loss.
2. **Radical Transparency:** Giving users a 'Glass Box' view of their data (Job Monitoring), rather than a 'Black Box.'
3. **Standardization:** Ensuring every microservice behaved predictably across the entire platform."

### ~~updated Solution~~

> "To win this market, the company made a massive bet: moving from a monolithic, streaming-first architecture to a Microservices-based 'Glass Box' platform.
> 
> 
> The high-level strategy had two pillars:
> 
> 1. **Tenant Isolation:** Breaking the monolith so that one large client’s load wouldn't crash the system for everyone else.
> 2. **Transactional Guarantees:** Moving from 'best-effort' streaming to rigorous 'exactly-once' processing."

### 3. My Contribution (The "I")

> "Within this massive overhaul, I owned the end-to-end delivery of two critical product components: the Batch Processing Engine and the Monitoring Experience.
> 
> - **The Backend (Guaranteed Delivery):** I redesigned the core data ingestion workflow. I moved us from streaming to **Transactional Batching**, implementing 'Exactly-Once Processing.' This ensured that even if a server crashed, no data was ever duplicated or lost—a non-negotiable requirement for Enterprise SLAs.
> - **The Frontend (Radical Transparency):** I realized Enterprise users needed to *see* this reliability to trust it. I owned the new **Job Monitoring Dashboard**, specifically designing a reusable query and filter engine. This allowed users with 10,000+ pipelines to slice data by 'Error Type' or 'Source' instantly, turning a static log into a dynamic debug tool.

### Final updated Soln

### The Metrics (The "So What")

> "The launch was a turning point for the company:
> 
> - **Adoption:** We onboarded **8 Enterprise Clients** in the first 90 days because we could finally sign their strict SLAs.
> - **User Impact:** The new Monitoring Dashboard reduced the 'Time to Identify Errors' by **40%** for power users.
> - **Strategic:** We successfully migrated the customer base without churn, proving that the 'Microservices bet' paid off in reliability."

### ~~My Contribution (The "Director's Cut")~~

"I was responsible for delivering the **'Trust Layer'** of Hevo 2.0. This meant ensuring the backend was reliable (Batch) and, crucially, that the user *perceived* it as reliable (Job Monitoring).

**1. Enabling the Pivot (The Batch Engine)**

- **The Challenge:** The strategy relied on 'Transactional Guarantees,' but our legacy database couldn't support the load.
- 
    
    **My Execution:** I re-architected the core Mongo layer to handle the 40x state explosion required for batching. This was the 'engine room' work that made the 'Zero Duplication' promise physically possible.
    

**2. Defining the Experience (The JM Dashboard)**

- **The Product Decision:** This was where I had to shape the product. I looked at competitors like **Airbyte**, which overwhelmed users with raw logs.
- **The Trade-off:** I decided that for our Enterprise User, 'Less is More.' I defined the MVP for Job Monitoring (JM) to strip away low-level noise.
- **The Result:** Instead of a debugger, we built a 'Health Center.' I prioritized a view that grouped errors by **Batch ID**—allowing a Data Architect to see a failure, understand the blast radius, and click 'Retry' in seconds. This turned a technical console into a business control panel."

### Cleaner Story 1

### **1. The Context & User (The "Why")**

"I want to talk about the launch of **Hevo 2.0**, which was our strategic pivot to break into the Enterprise market using a complete rebuild of our product from a Monolith to a Microservices architecture.

- **The Market Trap:** At the time, Hevo was dangerously squeezed in the middle. **Fivetran** owned the enterprise with a high-cost, high-reliability model. **Airbyte** was eating the low end with open-source flexibility. We were positioned as the 'low-cost alternative' for SMBs, which meant we suffered from high churn and low contract values.
- **The Goal:** To survive and grow, we needed to move upmarket. We wanted to acquire **Enterprise Data Architects** at Fortune 500 companies—expanding our Total Addressable Market (TAM) beyond just startups.
- **The User:** Unlike our existing SMB users who valued 'speed and price,' these new Enterprise Architects prioritized **Auditability and Reliability**. They were managing mission-critical data for finance and compliance."

### **2. The Problem (The "Misalignment")**

"The problem was a fundamental mismatch between our architecture and this new user's needs.

- 
    
    **Speed vs. Reliability:** Our platform was built on a **Streaming-First** architecture. This was great for speed (low latency), but it made guaranteeing 100% data consistency difficult.
    
- **The Trust Gap:** Enterprise Architects operate in a 'Zero Trust' environment. They need to know that if a network failure happens, the system will self-heal perfectly.
- 
    
    **The Architectural Blocker:** Our streaming approach meant that failures often resulted in partial data loads or difficult-to-trace errors. We realized we couldn't just 'patch' this; we were optimizing for *latency* (speed) when the market demanded *integrity* (atomicity). To win the Enterprise, we had to fundamentally change how we processed data."
    

### **3. The Solution (The "Strategic Pivot")**

"To win the Enterprise, we executed a complete architectural pivot from 'Streaming-First' to **'Batch-First'**.

- **The Core Shift:** We moved to **Transactional Batch Processing**. Instead of continuous streams, we processed data in bounded windows.
- **The Value Prop:** This guaranteed **Atomicity**. A batch either succeeded 100% or rolled back completely—zero partial failures or 'silent duplicates.' This aligned perfectly with the Enterprise need for 'Zero Trust' correctness.
- **The Product Risk:** However, Batch dramatically increased complexity. Users now had to track thousands of runs, dependencies, and retries. We realized we couldn't just ship the backend; we needed a new product layer to make this complexity manageable."

### **4. My Contribution (The "Trust Architect")**

"I led the execution of this 'Reliability Stack,' owning both the **Batch Engine** (The Core) and **Job Monitoring** (The Interface).

- **The Engine Interface (Batch & State):**
    
    As Batch dramatically increased execution complexity, I led the redesign of our Mongo-backed state layer to support a much higher volume of run metadata and retries. My focus was ensuring the system could *reliably represent execution state* without performance degradation — a prerequisite for delivering strong correctness guarantees.
    
- **The Trust Layer (Job Monitoring):**
    
    I defined Job Monitoring not as a debugging tool, but as a **canonical execution narrative** for enterprise users. JM grouped runs by batch windows, surfaced failure states clearly, and gave Data Architects a single pane of glass to audit executions and reason about retries.
    
- **The Product Insight:**
    
    Batch increased power, but also cognitive load. JM was the product layer that translated system complexity into human trust — making the architecture usable for enterprise decision-makers.”
    

### **5. The Metrics (The "So What")**

"The launch was a turning point for the company:

- **Adoption:** We onboarded **8 Enterprise Clients** (including a major bank) in the first 90 days because we could finally sign their strict SLAs.
- **User Impact:** The new Monitoring Dashboard reduced the 'Time to Identify Errors' by **40%** for power users.
- **Strategic:** We successfully migrated the customer base without churn, proving that the 'Microservices bet' paid off in reliability."

### Follow-up questions:

### 1. Explaining the Business Mechanics

**A. "Why does 'Low Cost Alternative for SMBs' = High Churn?"**

- **The Logic:** SMBs (Startups/Small Biz) are volatile. They go bankrupt, get acquired, or constantly switch tools to save $50/month.
- **The Unit Economics:** If your average customer pays $200/month, you need *thousands* of them to make real revenue. But supporting thousands of small customers creates a massive support burden.
- **The Treadmill:** You have to acquire new customers faster than the old ones leave just to stay flat. It’s an exhausting, low-margin business model.

**B. "Why was Airbyte 'eating the low end'?"**

- **The Logic:** Airbyte is Open Source (OSS). Developers *love* OSS because it’s free to start and infinitely customizable.
- **The Threat:** Hevo’s value prop to SMBs was "Cheap & Easy." Airbyte came in and said, "We are Free & Hackable."
- **The Result:** If a startup engineer wanted a quick pipeline, they’d just spin up Airbyte on a free AWS instance. We couldn't compete on "price" anymore because you can't beat "free." We faced **commoditization**.

### The Strategic "Why": Why Target Enterprise?

When the interviewer asks, *"Why did you think Enterprise was the answer?"* you need a strong, 3-part answer.

"We looked at the market dynamics and realized the 'Middle' was a kill zone. We had three clear reasons to move Upmarket:"

1. **Unit Economics (LTV/CAC):**
    - "We wanted **Net Dollar Retention**. SMBs stay small. Enterprises land at $20k and expand to $100k. We needed customers who would grow *with* us, not churn out after 6 months."
2. **Defensibility (The Moat):**
    - "The low end (SMB) was becoming a commodity war with Airbyte. The high end (Enterprise) is a **Trust War**. If we could solve the 'Reliability' problem, we could build a defensive moat that open-source tools couldn't easily cross (due to compliance/support needs)."
3. **Survival:**
    - "Fivetran proved there was massive willingness to pay for 'Reliability as a Service.' We realized we were fighting for scraps at the bottom when the real budget was at the top—but only if we could prove our data was accurate."
    - 

**Q1: "Why didn't you just build more connectors to beat Fivetran?"**

- *The Trap:* Thinking features = value.
- *Your Answer:* "We considered that. But our data showed that Enterprise deals weren't stalling because we lacked *Connectors* (Breadth); they were stalling because we lacked *Trust* (Depth). Adding 50 new connectors to a leaky architecture would have just created 50 new ways to fail. We had to fix the foundation first."

**Q2: "Why didn't you just lower prices to kill Airbyte?"**

- *The Trap:* Engaging in a price war.
- *Your Answer:* "That’s a race to the bottom. Airbyte is open-source/free. We have infrastructure costs. We can't price-match 'free.' We had to differentiate on value—specifically, the value of a 'Managed, Guaranteed Service' that an open-source tool doesn't offer."

**Q3: "Moving to Batch/Enterprise sounds expensive (Engineering time). How did you justify the ROI?"**

- *The Trap:* Not knowing the cost of delay.
- *Your Answer:* "The cost of *not* doing it was irrelevance. Our churn analysis showed we would plateau within 12 months at our current trajectory. The ROI wasn't just 'new revenue'—it was extending the company's lifespan by unlocking a sustainable market segment."
- 

This is a great strategic question. If Fivetran is the "Gold Standard," why would anyone buy Hevo even *after* we fix the reliability?

Here is the answer, followed by the **Insight/Bet** section (which is absolutely the right step before the Solution).

### ♟️ The Strategy: How do we compete with Fivetran?

You don't beat the incumbent by being *better* at their main strength; you beat them by reaching **"Parity"** on their strength and winning on **Price & Experience**.

- **The Fivetran Problem:** Fivetran is the "Salesforce" of data pipelines—extremely expensive and rigid.
- **The Hevo Opportunity:** Many enterprises *hated* Fivetran's pricing but couldn't leave because they needed the reliability.
- **The Hevo 2.0 Strategy:** "If we can reach **Reliability Parity** (or get 99% close), we win the deal because we are 30-40% cheaper and offer better support."
    - *Before Hevo 2.0:* We weren't even in the room. We were "risky."
    - *After Hevo 2.0:* We became the "Smart, Cost-Effective Alternative."

**The Interview Line:**

> "We didn't need to be more reliable than Fivetran. We just needed to eliminate 'Reliability' as a reason to say 'No.' Once the risk was gone, we could win on our competitive advantages: better pricing, superior customer support, and a more intuitive UI."
> 

**Q: "You mentioned moving from Streaming to Batch. Usually, products want to get faster (lower latency). Why did you slow the product down? Did customers push back?"**

- **The Trap:** They are testing if you understand **User Needs vs. Technical Specs**. If you answer "Batch is easier to code," you fail.
- **The Answer:**
"We did receive initial pushback from Sales, who loved selling 'Real-Time.'
However, I looked at the actual usage data of our Enterprise prospects. They weren't powering live trading dashboards; they were powering **Hourly Executive Reports** and **Daily Financial Reconciliations**.
I realized that for *this specific user*, **Consistency is more valuable than Speed**.
I framed the trade-off to stakeholders this way: 'We are trading *milliseconds* of latency for *zero* data duplication.' Once I positioned it as '100% Accuracy,' the latency argument disappeared because an inaccurate report delivered fast is still useless."

---

### **Category 2: Prioritization (The MVP)**

**Q: "Job Monitoring (JM) could have been a massive project. How did you decide what to include in the MVP and what to cut?"**

- **The Trap:** They want to see if you can **Scope Down** based on user value, not just engineering capacity.
- **The Answer:**
"I used a **'Time to Action'** framework to prioritize.
My goal was: *How quickly can a user fix a failure?*
    - 
        
        **What I Cut:** Competitors like Airbyte showed raw, streaming logs. I cut this because scrolling through 10,000 log lines increases the 'Time to Action.'
        
    - 
        
        **What I Kept:** I prioritized a high-level **'Batch Status' view**. If a batch failed, we showed *only* the error summary and a 'Retry' button.
        
    - 
        
        **The Result:** This forced us to build a 'Universal Filtering Framework'  to standardize errors across microservices. By cutting the 'noise' of raw logs, we actually improved the user's ability to debug, reducing resolution time by 40%."
        

---

### **Category 3: Execution & Failure**

**Q: "This was a massive rewrite. What went wrong during the rollout? Tell me about a fire you had to fight."**

- **The Trap:** If you say "It went perfectly," you look junior. Senior PMs handle crises.
- **The Answer (Using your PDF details):**"We had a major issue with **'Query Regressions'** under real load.
Because we moved to microservices, we underestimated the impact of 'Batch Bursts'—where thousands of pipelines triggered simultaneously. The new Job Monitoring dashboard started timing out because it was scanning too many distributed collections.
**The Fix:** I didn't just ask engineers to 'optimize queries.' I changed the product behavior. We implemented a **'Lazy Loading'** pattern for the dashboard and introduced a strict **'Pagination Contract'**  across all services.
I effectively acted as the 'Reliability Enforcer' , ensuring that no microservice could ship without adhering to these new indexing and sorting rules. It stabilized the system without needing a rollback."

---

### **Category 4: Stakeholder Conflict**

**Q: "You froze feature development for a quarter. The Sales team must have hated that. How did you keep them on board?"**

- **The Trap:** They want to see **Influence without Authority**.
- **The Answer:**
"It was tense. Sales viewed Reliability as 'Engineering Hygiene,' not a 'Sales Feature.'
I changed the narrative by giving them a new weapon: **The 'Zero Data Loss' Guarantee.**
I worked with Product Marketing to create a one-pager comparing our 'Transactional Batch' model against competitors' 'Best Effort' streaming.
I told Sales: *'I'm not taking away features; I'm giving you the tool to displace Fivetran.'*
By tying the technical rewrite directly to their ability to close the specific Enterprise deals in their pipeline, I turned them from detractors into advocates for the delay."

### Background knowledge :

- **Fivetran (The Market Leader):** They are famous for using "Micro-batches" (usually 5–15 min intervals), not pure real-time streaming. This allows them to guarantee "Exactly-Once" delivery.
- **The Enterprise Logic:** Large companies (Banks, Healthcare) prefer **Consistency over Speed**. They don't need to see a transaction occur *1 millisecond* after it happens; they need to know that at 9:00 AM, their dashboard matches their bank ledger *exactly*.
- **The Technical "Why":** You are correct—debugging a stream is a nightmare because the data is "in flux." Debugging a batch is easy: "Did Batch #105 fail? Yes. Okay, retry Batch #105." This is called **Idempotency** (safely retrying without creating duplicates).

Examples to show atomicity is better :

- **Financial Reconciliation (The "Month-End Close" Scenario)**
    - **Scenario:** A CFO is closing the books for Q3. They need to move data from Netsuite (ERP) to Snowflake (Data Warehouse) to run the final report.
    - **The Risk:** If a streaming pipeline fails halfway, they might have $10M in Revenue but only $5M in Expenses loaded. The report says they are wildly profitable (incorrectly).
    - **Why Batch Wins:** With Atomicity, if the job fails, *nothing* is loaded. The CFO sees "Data Missing" (which is safe) rather than "Incorrect Data" (which is dangerous). They click "Retry," the batch runs fully, and the numbers balance.
- **Retail Inventory ("Available to Promise")**
    - **Scenario:** A retailer like Nike is syncing inventory levels from warehouses to their website.
    - **The Risk:** A customer buys a pair of shoes. The "Order" event flows through, but the "Decrement Inventory" event fails due to a stream glitch. The website thinks stock is still there.
    - **Why Batch Wins:** They prefer to update stock in 15-minute reliable batches. Either the entire inventory snapshot updates, or none of it does, ensuring they never sell shoes they don't have.

## Story 2

# **Product Story 2 (SECONDARY): Job Monitoring — Making Reliability Usable**

**Use this for:**

“Tell me about a feature you owned end-to-end”

“How do you translate complexity into a good user experience?”

“Tell me about improving an existing product”

“How do you think about observability / trust / UX?”

---

## 1️⃣ User (Be very specific)

**Primary user:**

Enterprise **Data Engineers / Data Architects** operating high-volume pipelines in production.

**Key user truth (say this):**

> “These users weren’t just running pipelines — they were on call for them.”
> 

That single line anchors urgency.

What they cared about:

- Knowing *whether* data was safe
- Understanding *what failed*
- Acting quickly without digging through internals

---

## 2️⃣ Problem (User pain, not system pain)

**The real problem:**

> “As the platform became more reliable internally, it actually became harder for users to understand what was happening.”
> 

Why:

- Batch introduced thousands of runs
- Failures were fragmented across logs, metadata, and tools
- Users couldn’t answer basic questions quickly:
    - *Did this run succeed?*
    - *Is downstream data safe?*
    - *What should I retry?*

**Key framing (important):**

> “Reliability without visibility still feels like unreliability to users.”
> 

That’s a strong PM statement.

---

## 3️⃣ Insight / Hypothesis (PM moment)

**Your hypothesis:**

> “If we wanted enterprises to trust the system, we needed to give them a clear, human-readable execution story — not just better logs.”
> 

Key leap:

- Observability ≠ debugging
- Observability = **confidence + decision-making**

This reframes JM from “engineer tooling” to **product surface**.

---

## 4️⃣ Solution (What you built, framed as product decisions)

**What JM became:**

> “We designed Job Monitoring as the canonical execution narrative for the platform.”
> 

Core product decisions (high-level):

- **Run-centric model:** Every pipeline execution had a clear lifecycle
- **Batch grouping:** Related runs were grouped so users could reason in windows, not events
- **Failure clarity:** Users could immediately see:
    - where it failed
    - whether it was partial or complete
    - whether retries were safe
- **Single pane of glass:** No more jumping between tools

Important line to keep:

> “The goal wasn’t to expose everything — it was to expose the right abstractions.”
> 

---

## 5️⃣ Tradeoffs (Show judgment)

Explicitly call these out:

- **Simplicity vs completeness:** We hid low-level noise in favor of clarity
- **Speed vs correctness:** Some views were slower but more trustworthy
- **Power users vs new users:** We optimized first for on-call engineers

This shows maturity.

---

## 6️⃣ Outcome / Metrics (Concrete, not flashy)

**User impact:**

- Time to identify failures dropped meaningfully (~40%)
- On-call engineers could act without engineering support
- JM became the default investigation entry point

**Product impact:**

> “JM shifted conversations from ‘is the system broken?’ to ‘I understand what happened and what to do next.’”
> 

That’s the win.

## Main Behavioural Stories

### The Crisis Commander (Intuit Faulty Script)

**Context (The Stakes)**

> "At Intuit, we faced a critical incident where a faulty script inadvertently migrated 1,500 companies out of our system.
> 
> 
> These were small businesses that relied on QuickBooks for daily operations, and they suddenly lost access to their paid subscriptions. Within hours, our support channels were flooded, and the issue threatened to cause mass churn and significant reputational damage. My goal was to lead the recovery—not just fixing the technical bug, but managing the client panic."
> 

**Action (The Leadership)**

> I stepped up to lead the **War Room** response. Operating in crisis mode for 10 days, I focused on three parallel streams to handle the problem end-to-end:
> 
> 
> **1. Cross-Functional Coordination (The Internal Loop):**
> I set up a real-time triage loop involving **Support, Product (PMs), Engineering, and QA**.
> 
> - Engineers coded fixes in real-time, and **QA tested them on the fly**—often verifying patches within minutes so we could deploy continuously. This reduced our cycle time from days to hours.
> 
> **2. Client Communication Strategy:**
> silence was our biggest risk. I worked with the Product team to draft **transparent scripts for Support, ensuring every affected client received an honest update about *why* this happened and *when* it would be fixed, rather than generic** 'technical difficulty' messages.
> 
> **3. Business Recovery (The Complexity):**
> Some of these clients were on **legacy offers from 2017** that had technically expired. We couldn't just 'turn them back on.' I had to work with the Offer Team to process refunds in such cases
> 

**Result (The Impact)**

> "We successfully restored access for all 1,500 companies and prevented major churn.
> 
> 
> In fact, because of the transparency and the proactive refunds, we received feedback from clients appreciating how we handled the mistake. We turned a potential PR disaster into a case study on customer support."
> 

**Learning (The Insight)**

> "This experience taught me that in a crisis, the technical fix is only half the solution. The other half is **communication**. If you are transparent and **empathetic** when things go wrong, you can often strengthen customer trust rather than lose it."
> 
- Leadership under pressure
- Ownership beyond role
- Crisis management
- Tell me about a difficult situation
- Tell me about a time you turned a negative customer experience into a positive one
- Tell me about a time you went above and beyond for a customer." (Focus on the *refunds/trust* part)

### Out-of-Sync (OOS) data consistency framework — Intuit

**Context (The Manual Toil)**

> "At Intuit, our billing architecture was distributed across multiple microservices. Data was replicated across teams, which led to inevitable consistency issues.
> 
> 
> The company's solution was primitive: we had a 'Rulebook' of manual fixes that Support Engineers executed by hand.
> 
> **The Trigger:** When I joined, I had to execute these manual fixes myself as part of onboarding. I found it incredibly frustrating. 
> 
> The Engineering teams were actually fine with the status quo because they weren't the ones feeling the pain—as long as Support dealt with the tickets, the engineers considered the system 'healthy.' I realized we didn't just have a data problem; we had an **incentive problem**."
> 

**Action (The Influence Strategy)**

> "I decided to automate myself out of this job. Since I was new and didn't have authority over the 12+ teams involved, I had to change how they viewed the cost:
> 
> 
> **1. The Assessment:** I realized a true architectural fix (changing database configurations) was too expensive. So, I pivoted to a lightweight 'Overlay' strategy.
> 
> **2. The Pitch (Aligning Incentives):** The Engineering Leads initially pushed back because in silos, the problem looked small. Team A saw 50 errors, Team B saw 20—it felt like noise.
> * I aggregated the data across all 12 teams to reveal the hidden monster: a **cumulative backlog of 50,000 affected accounts**.
> 
> - I showed them that while the daily trickle seemed manageable, the aggregate debt was actually blocking millions in revenue and preventing safe feature launches.

**Result (The Scale)**

> "The framework was adopted by all teams and eventually auto-resolved over 3,000 discrepancies monthly.
> 
> 
> We effectively eliminated the need for the manual 'Rulebook' for standard cases. By automating the reconciliation, we significantly reduced the support volume and, more importantly, improved data integrity, which led to a **10% lift in renewals**."
> 

**Learning (The Insight)**

> "I learned that influence is about exposing **hidden costs**. The engineers didn't care until I showed them that the 'operational noise' was actually technical debt that was slowing them down."
> 
- Influence without authority
- Platform / Core PM thinking
- Multi-team alignment
- "Tell me about a time you had to convince a team to change their mind." (Convincing them to adopt your framework).
- "Tell me about a time you solved a complex, systemic problem.”
- "Tell me about a time you simplified a complex process.”

### Underestimating scope → missed deadline (Intuit)

**Context (The Visibility Gap)**

> "Early in my time at Intuit, I was assigned a major 3-month project in a new domain.
> 
> 
> **The Mistake:** My manager set an aggressive deadline, and because I was new, I deferred to his judgment without doing deep due diligence.
> **The Process Failure:** The real issue, however, was our **cadence**. We only had weekly check-ins. As I hit unexpected technical roadblocks, I was working overtime to fix them, but because I only updated him every 7 days, the 'Red Flags' were getting lost. To him, the lack of visible progress looked like I wasn't working; to me, I was drowning in complexity that I couldn't communicate fast enough."
> 

**Action (The Pivot)**

> "By Month 2, I realized that sticking to the status quo would lead to failure. I had to pivot from being a 'passive reporter' to an 'active owner.'
> 
> 
> **1. The Data Gathering:** I stopped coding for a day and consulted a Senior Staff Engineer to validate the *real* timeline.
> 
> **2. The Reset Meeting:** I scheduled a tough conversation with my manager.
> 
> - **The Scope Fix:** I presented data showing the original deadline was impossible and proposed a **Phased Rollout**—delivering the critical path first to save the launch date.
> - **The Process Fix:** Crucially, I told him, **'Weekly updates aren't working. I need daily stand-ups so you can see the blockers as I see them.**' I **wanted to close the visibility gap."**

**Result (The Outcome)**

> "It was a tense conversation, but he agreed to the plan.
> 
> - **The Delivery:** We shipped the core product on the original date with zero bugs, and I delivered the rest in the follow-up sprint.
> - **The Relationship:** The switch to daily updates actually rebuilt his trust because he finally saw the effort and complexity I was navigating.
> - **The Failure:** We technically missed the *full* original scope deadline, but we saved the launch."

**Learning (The Insight)**

> "I learned that frequency of communication must match the complexity of the task.
> 
> 
> I used to think **'autonomy' meant working alone for a week. Now I know that for high-risk projects, 'autonomy' requires high-frequency feedback.** I never let a 'Yellow' status wait 5 days to turn 'Red' anymore."
> 
- "Tell me about a time you missed a deadline.”
- "Tell me about a time you failed.”
- “Receiving feedback”
- “Handling disagreement”

### The Strategist (Hevo 2.0 Enterprise Pivot)

**Context (The Market Gap)**

> "When I joined Hevo Data, we were successful with SMBs, but the company’s strategic goal was to move upmarket to Enterprise clients.
> 
> 
> The problem was our 'legacy' architecture. It was built for speed, not rigor. It lacked critical enterprise features like **'exactly-once processing'** and transactionality. We were trying to sell a Ferrari engine inside a Honda Civic, and enterprise trials were failing because data integrity wasn't at 100%. The ambiguity was: do we keep shipping features to satisfy current SMBs, or pause and rebuild for the future?"
> 

**Action (The Strategic Trade-off)**

> "I led the architectural overhaul for the Hevo 2.0 launch. This wasn't just a coding task; it was a roadmap prioritization decision.
> 
> - **The Trade-off:** I worked with Product leadership to make the hard call: we paused new feature development for a quarter to focus entirely on **reliability**.
> - **The Execution:** I designed a new architecture that guaranteed data integrity. I also implemented a **phased rollout plan**, ensuring we could migrate our largest users without downtime.
> - **The Alignment:** I had to convince the Sales team that pausing features now would unlock bigger deals later."

**Result (The Strategic Win)**

> "The bet paid off. The new architecture improved data integrity by 45%, which was the blocker for those big deals.
> 
> 
> Within 90 days of launch, we successfully onboarded **8 new enterprise clients**, proving that reliability was actually our most valuable feature. It taught me that sometimes the best product decision isn't adding a button; it's fixing the foundation."
> 
- Strategic thinking
- Product tradeoffs
- Long-term vs short-term decisions
- Tell me about a time you prioritized a roadmap.
- "Tell me about a time you made a difficult trade-off." (Features vs. Reliability)

## Back pocket

### The Advocate (Niveda Mobile School)

**Context (The Barrier)**

> "Before my corporate career, I volunteered at Niveda Vidya Mandir, a mobile school for underserved children in India.
> 
> 
> We drove a van equipped with books and Android phones into slums to teach kids. The biggest challenge wasn't lack of interest—**it was cultural resistance**. Many families refused to send their daughters to our mobile school because they were expected to help with household work. To the parents, education looked like 'lost income' or 'lost time.'"
> 

**Action (The User Empathy)**

> "I realized I **couldn't just preach about 'education.**' I had to understand their user needs.
> 
> - **The Deep Dive:** I engaged directly with the families to listen to their fears. I realized they viewed the school as a disruption.
> - **The Reframing:** I changed the value proposition. Instead of just 'learning to read,' I demonstrated how digital literacy (using Google Translate, Maps, and basic math) could help the families with their *current* economic struggles—like reading notices or calculating earnings without being cheated.
> - **The Access:** We used tools like **Google Read Along** to make the learning self-paced, so girls could learn in short bursts between chores, lowering the barrier to entry."

**Result (The Inclusion)**

> "This approach worked. We successfully enrolled several girls who had previously been kept home, including Sita, who became the first girl in her community to finish primary school through our program.
> 
> 
> It changed my definition of 'Product.' I learned that building the technology is easy; the real work is designing the **onboarding ramp** so that everyone can actually access it."
> 
- **The "Googleyness" Questions:**
    - "Tell me about a time you navigated a cultural barrier."
    - "Tell me about a time you advocated for an underrepresented group."
- **The Product Discovery Questions:**
    - "Tell me about a time you identified a user need that wasn't obvious." (Realizing parents weren't "anti-education," they were "pro-survival").

### The Servant Leader (Hevo Scrum Master)

**Context (The Gap)**

> "At Hevo Data, we were in a critical delivery phase when our Scrum Master unexpectedly fell ill.
> 
> 
> We were a lean team of five, and to make matters worse, we had a new engineer who was on-call for the first time. He was struggling with the pressure, and because the senior engineers were heads-down in their own code, he was drowning. The team was losing momentum, and we were at risk of missing our deadline."
> 

**Action (The Support)**

> "I stepped up to fill the leadership void—not by asking for a title, but by removing blockers.
> 
> - **Mentorship:** I noticed the new engineer was hesitant to ask for help, so I carved out time to pair with him on the on-call incidents, guiding him through the triage process so he felt supported rather than overwhelmed.
> - **Coordination:** I took over the daily stand-ups to keep the team aligned. I realized we were bottlenecking each other, so I split the team into smaller sub-groups based on strengths to parallelize the work.
> * **Transparency:** I kept leadership updated on our progress so they wouldn't panic about the Scrum Master's absence."

**Result (The Win)**

> "The immediate result was that the new engineer ramped up successfully and handled the on-call rotation with confidence.
> 
> 
> As a team, we regained our rhythm and actually completed the project **10% ahead of schedule**. It boosted team morale significantly because everyone felt unblocked and supported."
> 

**Learning (The Insight)**

> "This experience taught me that leadership isn't about authority or titles; it's about situational awareness—noticing when the team is struggling and stepping in to enable them to succeed."
> 

- Tell me about a time you helped a struggling colleague
- Tell me about a time you built team culture

### The Bottleneck (Hevo 2.0 Micromanagement)

**Context (The Trap)**

> "When I was leading the architectural overhaul for Hevo 2.0, the stakes were incredibly high—we were rebuilding the core engine for enterprise clients.
> 
> 
> Because I was the one who designed the new architecture, I fell into the trap of wanting to control every implementation detail. I felt that to ensure quality, I had to review every line of code and make every micro-decision myself."
> 

**Action (The Failure & Correction)**

> "The result was that I became a massive bottleneck.
> 
> - **The Failure:** My team was sitting idle waiting for my approvals, and our velocity slowed to a crawl. I could see the frustration in the senior engineers' eyes—they felt untrusted.
> - **The Feedback:** A mentor pulled me aside and said, 'Akshat, you are trying to scale the product, but you aren't scaling yourself.'
> - **The Correction:** I held a reset meeting. I apologized to the team for micromanaging and explicitly handed over ownership of key components (like the 'Job Monitoring' module) to two senior engineers. I shifted my role from 'Reviewer of Everything' to 'Architectural Guide.'"

**Result (The Recovery)**

> "It was uncomfortable at first to let go, but the team immediately moved faster.
> 
> 
> We recovered the timeline, and more importantly, the morale improved overnight because the engineers felt ownership again. One of the engineers I delegated to actually came up with a better optimization than I had planned."
> 

**Learning (The Growth)**

> "I learned that leadership isn't about control; it's about context. My job is to set the guardrails and let the team drive, not to grab the steering wheel."
> 
- “Tell me about a time you failed as a leader”
- “Delegated poorly”
- “Hurt team morale”
- “Received tough feedback”
- “Had to change your leadership style”