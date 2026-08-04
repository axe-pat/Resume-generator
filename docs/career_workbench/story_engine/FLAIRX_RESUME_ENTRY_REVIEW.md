# FlairX Resume Entry — Review Draft

> **DRAFT — NOT YET WIRED INTO RESUME GENERATION.** This file separates resume-ready framing from claims that still need Akshat's confirmation. The `_GOLD_REFERENCE_` files remain quarantined and are not treated as fact-cleared sources.

## Proposed header

`FLAIRX AI | AI PRODUCT MANAGER INTERN | [May 2026 – Aug 2026] | [Remote / location to confirm]`

Confirm the company's public spelling (`FlairX AI` appears in the internship JD), exact dates, and location label.

## Recommended generalist PM set

- Led a 4-engineer, 2-designer pod to deliver FlairX's first internal-interview workflow in two weeks, pairing privacy-safe M365 scheduling with AI-generated scorecards for Genpact.
- Owned FlairX's Ceipal ATS integration from discovery to marketplace launch; shipped a pull-first MVP when vendor APIs blocked write-back, reducing duplicate entry for a key account.
- Turned client demand into a 0-to-1 sourcing product; designed inbound distribution and AI-assisted outbound sourcing, secured LinkedIn XML-feed approval, and handed the spec to engineering.

Why this set: together the bullets show 0-to-1 product delivery, enterprise discovery, AI-workflow design, platform/API judgment, MVP scoping, partner-channel work, and current formal PM ownership without making the section read like an engineering role.

## Targeted swap variants

### Technical / platform PM

- Resolved a 20-minute avatar-vendor cap blocking enterprise interviews; led build-vs-buy analysis, negotiated usage-based pricing, and defined a provider-agnostic routing layer.

Potential quantified version, only after confirmation:

- Resolved a 20-minute avatar-vendor cap blocking enterprise interviews; led build-vs-buy analysis, negotiated $0.10/min pricing, and defined a routing layer with $0.009/min fallback providers.

### Strategy / BizOps

- Built FlairX's first commercial data spine in HubSpot, translating product usage events and customer feedback into self-serve account intelligence for enterprise diligence and GTM decisions.

## Claims requiring confirmation before external use

1. Internal-interview workflow: did the team deliver this to production or to a pilot-ready state in two weeks? Were the pod size (4 engineers, 2 designers) and Genpact attribution exact?
2. Scheduling metric: was `42%` the baseline share of recruiter time spent coordinating, or a measured post-launch reduction? Do not claim "cut 42%" unless the latter is defensible.
3. Ceipal: did the pull-first MVP launch publicly on the marketplace? Can we say it reduced roughly 80% of duplicate entry and/or retained the account, or should the outcome stay qualitative?
4. Sourcing: confirm that LinkedIn XML-feed approval was secured and that the end-to-end Sourced spec was handed to engineering. Commercial pricing, ACV lift, and adoption results are explicitly excluded because the story marks them as proposed/invented.
5. Avatar infrastructure: confirm which elements shipped versus were designed—LiveGen contract, provider wrapper, cost routing, anti-fraud layer, and fallback endpoints—and whether vendor pricing can appear publicly.

## Proposed resume architecture after approval

Keep the established 11-bullet one-page budget, but change the experience mix to:

- FlairX: 3
- Gojek: 3
- Hevo Data: 3
- Intuit: 2
- Optum: remove from the primary generalist resume

This preserves recentness and formal PM ownership while retaining the strongest marketplace, enterprise-data, and financial-trust evidence. Role-title decisions for Gojek and Hevo should be handled as a separate factual-positioning review.

## Engine work after wording approval

- Add fact-cleared FlairX story variants to the PM story pool.
- Refresh `profile/profile.md` with the internship and verified facts.
- Update hard-coded company headers and bullet counts in generation, rewrite, scorer, parsing, DOCX, and test paths.
- Add FlairX to strategy-story routing so role-specific runs can choose the generalist set or the technical/BizOps swap.
- Regenerate, inspect saved text, render the DOCX, and verify one-page fit.
