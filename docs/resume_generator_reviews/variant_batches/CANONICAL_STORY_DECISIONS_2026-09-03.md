# Canonical story decisions — Gojek, Hevo, and Intuit

**Status:** reviewed decision artifact only. Nothing here is wired into a live prompt
or selector yet.

The user confirmed that every on-file value is defensible and asked for one
representation to govern future variants. “Largest number wins” is not the rule.
The selected representation must be the most attributable realized result, close the
same causal path as the mechanism, remain legible to an outsider, and avoid repeating
the same scale currency in neighboring stories.

## The eight locks

| Story | Canonical choice | What is retired |
|---|---|---|
| G-SUPPLY | 18% supply and **1.5-minute** pickup-ETA reduction | 2 minutes; $110M+ as personal/project impact |
| G-PRICING | **20+ interviews, A/B proof, 9%, $3.2M incremental revenue** | 30+ interviews; $15M+ annual value |
| G-LATENCY | **~28K recovered monthly rides** | ~$5M+ annual-value conversion |
| H-BATCHSHIFT | **8 enterprise customers in 90 days** | 12 customers on this claim path |
| H-MONITORING | **45 minutes to under 5 across 120K+ pipelines** | 30% SLA in the canonical bullet |
| I-BILLING | **five systems, 80K+ businesses, 10% renewal lift** | three billing services in the canonical bullet |
| I-INCIDENT | **days to hours**, no eight-team claim | 7-day duration; eight-team scope |
| I-GOVERNANCE | **8 teams belongs here exclusively** | eight-team scope anywhere in I-INCIDENT |

## Exact preferred defaults

### G-SUPPLY

> Led Gojek's fleet integration platform and partner operating model; replaced bespoke builds with a standardized API and validation workflow, enabling 18% supply growth and cutting pickup ETAs by 1.5 minutes across Singapore and Bali.

This keeps the Amazon operating-model strength, uses the playbook's stronger “Led”
ownership verb, and changes “growing” to the more accurate platform-level attribution
“enabling.”

### G-PRICING

> Separated price-sensitive abandonment from quote-latency drop-off through funnel analysis and 20+ rider interviews; validated a lower-cost ride tier through A/B tests, lifting conversion 9% and generating $3.2M in incremental revenue.

This removes the former tradeoff between the two gold variants: it keeps the scarce
cause-separation insight and closes the qualitative-to-behavioral loop with A/B proof.
The $3.2M is realized incremental revenue; the $15M+ annual-value currency is retired.

### G-LATENCY

> Traded live fare recalculation for sub-second quotes by pre-caching pricing across 12 high-demand corridors; held fare variance within 4%, cut latency 70%, and recovered ~28K monthly rides.

This is already the most outsider-legible gold. Recovered rides are the direct product
result; using another dollar figure beside G-PRICING would add less proof and more
currency repetition.

### H-BATCHSHIFT

> Drove Hevo 2.0's batch-first shift after Fortune 500 trials stalled on auditability; traded streaming speed for verifiable correctness and clear failure boundaries, improving stability 45% and onboarding 8 enterprise customers in 90 days.

Eight customers is the number directly tied in the Hevo 2.0 sources to the execution-
model decision and strict-SLA readiness. The 12-customer variants join monitoring
requirements to this architecture path, so the larger number is less attributable
inside this story.

### H-MONITORING

> Shipped an AI monitoring surface that turned alert storms into single incident cards; kept detection deterministic and used GenAI over a 20+ failure taxonomy to rank recovery actions, cutting diagnosis from 45 to under 5 minutes across 120K+ pipelines.

The direct workflow outcome beats the 30% SLA derivative. This version also preserves
the important AI-boundary decision: rules detect the failure; GenAI synthesizes the
evidence and ranks the next actions.

### I-BILLING

> Traced silent SMB cancellations to billing mismatches across five systems; built a reconciliation model for 80K+ businesses and a financial case that shifted the roadmap from feature delivery to billing integrity, lifting renewals 10%.

Five systems supplies the strongest scope, while the financial case retains the PM
influence signal and the 10% renewal lift closes on a realized customer/business
outcome rather than the internal roadmap decision alone.

### I-INCIDENT

> Led recovery after billing-state errors canceled subscriptions for 1,500+ businesses; ran fix-writing and QA validation in parallel, cutting resolution from days to hours.

The source describes a longer overall crisis but a days-to-hours improvement in the
fix-and-validation cycle. That causal before/after is more valuable than saying the
whole response lasted seven days. The eight-team number is removed.

### I-GOVERNANCE

> Reframed delivery drag as a sequencing problem across 8 teams; built a risk-tiered prioritization model for 20K+ issues that improved throughput 25%.

Eight teams belongs only here: it is the natural scope of the cross-team backlog and
governance mechanism. The incident sources instead name functions involved in the war
room, so duplicating “8 teams” there would be evidence migration, not added signal.

## What “one going forward” means

The text above is the default for each story. The generator may retain a shorter or
role-emphasized alternate only when it stays on the same causal path and never uses a
retired metric or moves a scale atom to another story. It may omit a metric for page
fit; it may not substitute a conflicting one.

The machine-readable companion is
`CANONICAL_STORY_DECISIONS_2026-09-03.json`. Tests lock the eight selected values,
exact preferred text, source-path existence, length/readability constraints, Gojek
currency separation, and exclusive ownership of “8 teams.”
