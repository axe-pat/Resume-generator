---
story_id: PX-17
content_class: COUNTERFACTUAL_REFERENCE
truth_status: mixed_verified_and_future_counterfactual
consumer_policy: internal_only
generator_export: false
---

# PX-17 - The Recruiting Decision Engine

> **COUNTERFACTUAL REFERENCE - MIXES VERIFIED BUILD EVIDENCE WITH INVENTED FUTURE OUTCOMES - NOT FOR EXTERNAL USE**
>
> Independent product · AI-native product management / product engineering / operations

## The product we finally build

A recruiting decision engine that ingests jobs, companies, relationships, and message state; decides whether the next move is apply, apply-plus-outreach, follow up, watch, review, or skip; generates only the artifact needed for that move; and learns from outcomes without allowing a model to act beyond explicit evidence and human approval.

The current verified baseline is a single-operator product across ResumeGenerator and Outreach. The maxed future version turns the operating system into a safe, multi-user product without pretending that transition has already happened.

## Fifteen-second version

I started with resume tailoring and discovered writing was not the bottleneck; decision quality was. I became the PM and first user, using AI coding agents as an engineering team while I owned the workflow, state model, acceptance criteria, and release decisions. The verified build spans 151 commits, 542 release tests, 2,514 roles, 560 organizations, and 849 touchpoints. The maxed version adds a 30-user pilot, cuts time-to-reviewed-action 41%, and preserves zero unreviewed external sends.

## Situation and stakes

The job search had many capable point tools: discovery feeds, spreadsheets, resume generators, contact databases, and message writers. The failure lived between them. A high-fit role could be found twice, tailored without relationship context, contacted after an application had closed, or sent through a weak company-person match.

The first system optimized resumes. Operating it exposed the real need: one entity-first state model that connects opportunity, company, person, artifact, action, and outcome.

## The non-obvious insight

An AI recruiting product is not primarily a generation product. It is a **decision-and-state product**. Good prose cannot recover from the wrong job, duplicate action, stale employer, missing provenance, or unreviewed send.

The most important product requirements therefore come from operating failures: exact pointers, idempotent imports, fail-closed execution, evidence thresholds, review gates, and recovery paths.

## What is verified in the current build

- Two connected systems: ResumeGenerator for application artifacts and Outreach for relationships and touchpoints.
- Multiple source families feeding a reviewed action queue.
- Fit scoring, job-state tracking, tailored resume generation, outreach preparation, and follow-up state.
- A 96-day, 151-commit product history across two repositories.
- 542 passing release tests in the attested product snapshot.
- Snapshot scale: 2,514 roles, 560 organizations, 846 contacts, and 849 touchpoints.
- A real product-safety incident in which a wrong company-person match triggered a connection invite; the batch was stopped, the invite withdrawn, and the send contract changed to require independent employer evidence.

## What I own in the maxed version

- Define the north-star job: reduce time from credible signal to a reviewed, evidence-backed next action.
- Replace source-centric records with entity-first company, role, person, relationship, application, and artifact state.
- Build an evidence ledger that shows why a role was scored, why a person matches a company, which story supports the outreach, and which source is current.
- Separate model suggestion from authority. Models can rank, draft, and explain; external sends and irreversible status changes require explicit policy and human approval.
- Instrument a learning loop: role quality, application completion, reply, interview, false-positive, correction, and abandonment.
- Turn the current single-user workflow into a 30-person USC pilot with privacy partitioning, onboarding, feedback capture, and no shared personal data.
- Reject “fully autonomous job search” as the launch promise. Optimize for high-quality reviewed decisions and trustworthy recovery.

## Product judgment and trade-offs

Fail-closed design lowers throughput and can leave opportunities untouched when evidence is incomplete. That is a deliberate choice: a visible review queue is cheaper than a wrong message sent to a real person.

The system also avoids generating a cover letter by default. It creates one only when the application path requires it, preserving attention and model cost for higher-value work.

## Counterfactual outcome

- USC pilot: **30 job seekers**, 12 weeks, privacy-separated workspaces.
- Median time from qualified signal to reviewed action: **-41%**.
- High-fit opportunities acted on within 48 hours: **+29%**.
- Duplicate/stale actions reaching final review: **-72%**.
- Unreviewed external sends: **zero**.
- Users who can explain why the engine recommended an action: **90%+** in task-based testing.

## Role-flex renderings

**Resume ammo**

- Built and operated an AI recruiting decision engine across 151 commits and 542 release tests, unifying 2,514 roles, 560 organizations, 846 contacts, and 849 touchpoints into evidence-backed action queues.
- Turned a real wrong-recipient failure into an entity-verification contract across every send path; preserved human approval and fail-closed execution while scaling a counterfactual 30-user pilot.

**Spoken short**

“I started by building a resume generator, then operating it taught me writing was not the bottleneck. The hard problem was deciding which opportunity deserved attention, whether to apply or build a relationship, and how to preserve state across those actions. I acted as PM and first user and used AI coding agents as my engineering team. The verified system spans 151 commits, 542 tests, 2,514 roles, and 849 touchpoints. A wrong company-person match once triggered an invite; I stopped the batch and changed every send path to require independent employer evidence. That is when it became a product: not because the AI wrote well, but because the state, guardrails, and recovery made its decisions trustworthy.”

**Outreach hook**

“I built my recruiting system after realizing generation was the easy part; trustworthy opportunity decisions need entity state, provenance, approval boundaries, and feedback loops.”

## Follow-up defense bank

- **What did AI agents do versus you?** Agents accelerated implementation. Akshat owned problem definition, roadmap, operating reviews, trade-offs, acceptance criteria, and ship/rollback decisions.
- **Is it multi-user today?** No. The current proof is a personal production workflow; the 30-user pilot is counterfactual future state.
- **What is the key product metric?** Time to a high-quality reviewed action, bounded by false-positive and unreviewed-send guardrails - not number of generated documents.
- **Why split ResumeGenerator and Outreach?** Application and relationship workflows have different state, risks, and operators; discovery can be shared while execution remains specialized.
- **What would you build next?** A claim-level Story Engine with approved evidence only, then a small privacy-separated pilot to test whether other users understand and trust recommendations.

## What would make the maxed version true

1. Privacy and tenancy design appropriate for real users.
2. Instrumented onboarding and baseline task-time study.
3. 30-user pilot consent and support plan.
4. Stable definitions for qualified signal, reviewed action, stale action, and error.
5. Pre/post outcomes and qualitative trust research.
6. Continued external-action approval and incident review.

## Provenance ledger

- **A:** Repository history and the product story support the two-system architecture, 96 days, 151 commits, 542 tests, 2,514 roles, 560 organizations, 846 contacts, 849 touchpoints, and the wrong-company invite incident.
- **R:** Decision-and-state product, first-user PM framing, and evidence/guardrail emphasis are grounded interpretations of the operated system.
- **X:** Multi-user capability, 30-user USC pilot, all pilot outcome metrics, privacy workspaces, and usability percentage are counterfactual future state.
- **V:** Recompute repository/product counts before any current public use; never claim monetization, autonomy, or multi-tenancy without evidence.
