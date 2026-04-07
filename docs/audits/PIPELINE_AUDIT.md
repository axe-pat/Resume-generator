# Resume Pipeline Audit — March 2026
*End-to-end analysis of architectural issues, anti-patterns, quality ceilings, and content gaps*

---

## How to read this doc

Issues are grouped into five categories, roughly ordered by their impact on final resume quality. Within each category, items are ranked highest-impact first. Severity tags: 🔴 Major | 🟡 Medium | 🟢 Minor.

---

## Category 1: Architectural Anti-Patterns ("Make It Bad → Fix It")

These are the ones you suspected — places where a later pass exists only to undo something an earlier pass introduced, instead of getting it right at the source.

---

### 1A 🔴 QC-13 Trim Pass: generated bloat → dedicated API call to trim it

**What happens:** Pass 1 and Pass 2 sometimes produce 4-liners (≥260 chars). When more than 2 bullets hit that threshold, `run_length_trim()` fires as a separate Sonnet API call to trim them down.

**The root cause:** The prompt instruction was *removed* from being an enforced constraint and demoted to a "calibration guide only" — specifically because it was causing the model to spend 872s doing inline character-counting. That fix solved the runtime problem but punted bullet-length enforcement entirely downstream.

**Why this matters:** The trim pass (a) costs ~$0.04, (b) can produce worse bullets by stripping load-bearing detail, and (c) adds another re-score call on top if it fires. It's $0.06+ of remediation for something that should never have been generated.

**Better fix direction:** The story bank variants themselves are the source. Most variants are already 130–220 chars. The actual problem is that Pass 2 *expands* Pass 1 bullets. The regression guard catches +60-char bloat but a bullet going from 165 to 224 chars (a natural 3-liner) is allowed. Constraining Pass 2's expansion via the regression guard threshold (e.g., revert if P2 > 230 chars AND P1 was a 2-liner) would eliminate most QC-13 firings without needing the trim pass at all.

---

### 1B 🔴 Expansion Pass: trim-induced underfill → another API call to expand

**What happens:** After QC-13 trim, fill_pct can drop below 85%. The expansion pass then fires to re-expand the shortest bullets.

**The cycle:** Pass 2 expands → QC-13 trims → Expansion re-expands. Each step costs a Sonnet call. In the worst case (trim fires, then expansion fires), you're paying for 3 extra API calls to end up approximately where you started.

**Better fix direction:** If the story bank and Pass 2 produced bullets in the right range from the start (most at 145–175 chars, a few natural 3-liners at 200–220), neither trim nor expansion would fire in normal operation. These passes are valid safety nets but shouldn't be routine. They're currently routine.

**Secondary issue:** The expansion pass prompt is a hardcoded string literal inside `freeform_runner.py` (`_EXPANSION_PROMPT_TEMPLATE`). Every other prompt is a versioned file in `prompts/`. This one can't be iterated on, version-controlled, or read without opening the runner. Should be extracted to `prompts/freeform_expansion.txt`.

---

### 1C 🟡 Em Dash Strip: model outputs forbidden characters → post-processing removes them

**What happens:** After Pass 2 and again after Pass 4, the code explicitly strips em dashes with `re.sub(r'\s*\u2014\s*', ': ', ...)`. Both prompts say em dashes are forbidden. There's also a QC-11 check. That's three layers of enforcement for one forbidden character.

**Why this pattern exists:** The model keeps introducing em dashes despite clear prompt instruction. Rather than fixing the prompt compliance, two separate strip-and-replace calls were added.

**The problem:** Replacing em dash with `: ` is a lossy transformation that produces syntactically weird bullets ("identified X: not Y but Z"). It rarely breaks anything badly but it's a structural patch over a prompt compliance problem. And the replacement can produce double colons (`: ... :`) which triggers the regression guard in a downstream run.

**Better fix direction:** This is less severe than 1A/1B because it's cheap (no API call). But the right fix is in the prompt: em dash is already forbidden, but the examples in the prompts should demonstrate the *alternatives* more explicitly (when to use `;`, when to use `:`, when to restructure). Models follow by example more reliably than by prohibition.

---

### 1D 🟡 Regression Guard: reverts Pass 2 output when it's "too long" instead of preventing over-length at the source

**What happens:** After Pass 2, the regression guard compares each bullet to its Pass 1 counterpart. If a bullet grew >60 chars, it gets reverted to the Pass 1 version.

**The problem:** The threshold is generous. A bullet going from 155 chars (P1) to 215 chars (P2) is allowed — that's a 2-liner becoming a 3-liner — because it's only 60 chars over. Most 3-liners are created in this window. Meanwhile, a P1 bullet at 225 chars reverted to exactly 225 chars just because P2 made it 286 chars is losing a perfectly good rewrite for an arbitrary number.

**Secondary problem:** Regression guard uses a flat char count (+60) without knowing whether the P1 bullet was already a 2-liner or 3-liner. The guard should be: if P2 produces a bullet that would be ≥3 lines AND the P1 bullet was ≤2 lines, revert.

---

### 1E 🟡 QC-03 Retry: missing intuit_incident → retry full Pass 2

**What happens:** If Pass 2 drops the Intuit incident story (mentions "1,500+"), the code reruns the entire Pass 2 prompt with a hardcoded extra_constraint prepended, then re-scores.

**The cost:** ~$0.06 per occurrence (full Pass 2 + re-score). This fires rarely but is entirely avoidable — if the Pass 2 prompt reliably preserved the incident bullet, the retry would never be needed.

**The root cause:** Pass 2 sometimes rewrites away the `1,500+` number in pursuit of better voice. The NO-INVENT constraint in the prompt should protect this (all numbers verbatim), but the model occasionally paraphrases "1,500+ businesses" to "over a thousand businesses." A simpler fix: add explicit instruction in Pass 2 to never paraphrase number-based proper nouns (the same way it's told never to paraphrase company names).

---

## Category 2: Pass Redundancy and Overlap

---

### 2A 🔴 Pass 1 generates full bullets that Pass 2 rewrites — one of these is doing redundant work

**The intended design:** Pass 1 selects variants verbatim from the story bank. Pass 2 rewrites voice.

**The actual behavior:** Looking at Pass 2 rewrite logs, Pass 2 routinely makes substantial changes — switching archetypes (Impact-first → Mechanism-first on G3), restructuring clause order, replacing vague phrasings with earned ones. These are not "voice tweaks"; they're fundamental structural changes.

**The redundancy:** Pass 1 writes 11 bullets. Pass 2 rewrites those same 11 bullets — often substantially. So effectively:
- Pass 1 does selection + structural formatting
- Pass 2 redoes the structural formatting

**Better design option A:** Make Pass 1 output *only* selection decisions (which variant, which order, why) and have Pass 2 generate the actual bullets from the raw story bank material. This eliminates the intermediate state that needs re-processing.

**Better design option B:** Keep current structure but add a "minimum intervention" pass check — only rewrite bullets that clearly fail the archetype/earned-detail criteria. Skip already-good bullets entirely. This is nominally in the prompt but in practice Pass 2 touches nearly every bullet.

---

### 2B 🟡 Strategy pass (Pass 0) runs Sonnet for a rich JSON, but most fields are thrown away for resume generation

**What happens:** Pass 0 generates a full JSON with company_type, archetype, hook_angle, story_recommendations, tone, gaps, positioning_narrative, primary_framing_axis, secondary_framing_axis. The resume pipeline injects only a formatted 4-field block from this (primary/secondary framing axis, top signals, gaps, narrative).

**Fields ignored by resume:** company_type, archetype, hook_angle, story_recommendations, tone, archetype_reasoning, story_reasoning, company_research_angle.

**Why this matters:** The `story_recommendations` field specifically names 1-2 stories to prioritize — but the resume pipeline never reads this field. Pass 1 picks variants based on primary_framing_axis and secondary_framing_axis, but not on the scorer's explicit story recommendations. These are the same signal but the strategy's pick is more direct and often more targeted.

**Fix direction:** Pass 1 should receive the story_recommendations field and use it to weight its variant selection. It's one extra line in the `_format_strategy_block()` function.

---

### 2C 🟡 Pass 3 (Score) + Pass 4 (Fix) + Pass 4 re-score = 3 Sonnet calls, with limited expected gain per fix attempt

**What happens:** After Pass 3 scores weak bullets, Pass 4 fixes them, then re-scores. With MAX_FIX_ATTEMPTS=1, that's always exactly 3 scoring/fix API calls (Pass 3 + Pass 4 fix + Pass 4 re-score).

**The observed gain:** Looking at actual outputs, Pass 4 typically moves bullets from 7.0 to 7.5-8.0 — it rarely gets a bullet from 7 to 9. The README notes: "second attempt almost never helps for WEAK_MECHANISM/VAGUE_OUTCOME failures caused by missing source metrics."

**The core issue:** Pass 4's instruction says "fix only the flagged bullets, reproduce all others verbatim." But it's sending the ENTIRE experience section as context. The model reads 11 bullets to fix 2-3. You're paying for the full context read on every bullet even when only 2 are being fixed.

**Fix direction:** For a BULLET_TOO_LONG failure mode, the trim could be done deterministically in Python (character-count-based trimming of the last clause) rather than via an API call. Not suitable for all failure modes, but BULLET_TOO_LONG in particular is mechanical.

---

### 2D 🟢 API key is re-read from disk on every single API call

`call_api()` calls `load_api_key()` which re-opens and re-parses `.env` on every call. With 5-7 API calls per run, the key is read from disk 5-7 times. Not a correctness issue but sloppy. Should be loaded once at startup and passed down or cached.

---

## Category 3: Content Quality Ceilings

These aren't pipeline bugs — they're fundamental limits on what the system can produce given the current story material. No amount of pass-optimization will fix these.

---

### 3A ✅ ATTRIBUTION_MISMATCH on G-SUPPLY ($110M+) — resolved 2026-03-26

**The key finding:** G-SUPPLY variants previously contained no `$110M+` mention, so Pass 1 and Pass 2 were synthesizing it from strategy context — producing ATTRIBUTION_MISMATCH bullets scoring 7.0.

**Two-part fix applied:**
1. `$110M+` added verbatim to the `[ecosystem-GTM]` variant as scale context ("Gojek's $110M+ ride marketplace"). Now flows through legitimately when that variant is selected.
2. Attribution guard added to Pass 1 (`freeform_master_v2.txt`) and Pass 2 (`freeform_voice_rewrite.txt`) hard constraints: blocks adding these figures if not already present in the selected variant / Pass 1 input.

**Guard language:** "NEVER include '$110M', '$20M', '50M members'... unless it appears verbatim in the specific variant you selected." Stops hallucination from strategy context without blocking legitimate use.

---

### 3B ✅ O-PROVIDER ($20M+ / 50M members) — resolved 2026-03-26

Same structural issue. Pass 1 or 2 sometimes included "50M members" or "$20M+ incremental annual revenue" as leading metrics for O-PROVIDER.

**Two-part fix applied:**
1. `$20M+ in incremental annual revenue` added to the `[platform-scale]` variant (which already had `50M members`). That variant now reads: "Integrated a new provider into Optum's 50M-member care network — enabling $20M+ in incremental annual revenue — by diagnosing a schema mismatch..."
2. Same attribution guard as 3A blocks Pass 2 from adding these figures from strategy context.

**The remaining metric-thinness note:** For variants other than `[platform-scale]`, the core metric is still "cut onboarding from 6 months to 10 weeks." If there's a concrete panel-size metric for the specific provider integrated (e.g., "200K-member panel"), adding it to a `[platform-scale]` sub-variant would move that bullet from 8 to 9 (see 5D).

---

### 3C ✅ H-GENAI replaced with H-MONITORING-AI for AI roles — resolved 2026-03-27

**Original problem:** H-GENAI bullets consistently scored 7 (WEAK_MECHANISM / VAGUE_OUTCOME). No concrete business outcome, mechanism was just "evaluated" and "authored."

**Fix applied:** H-GENAI retired from H-FLEX. Replaced with H-MONITORING-AI — the AI-assisted monitoring platform built at Hevo with anomaly detection + GenAI-based incident summarization, ~40% MTTR reduction across 120K+ enterprise pipelines. Confirmed by user as real work done at Hevo. Expected score ceiling: 8.0+ (concrete mechanism + metric + shipped product).

**Variants added:**
- `[AI-monitoring-product]`: "Shipped an AI-powered monitoring platform at Hevo Data — integrated anomaly detection for proactive failure identification and GenAI-based incident summarization, reducing MTTR ~40% across 120K+ enterprise pipelines."
- `[AI-reliability-product]`: "Reduced pipeline MTTR ~40% by designing an AI-powered monitoring surface that integrated anomaly detection and GenAI-based failure summarization; became the primary investigation entry point for enterprise data engineers managing 120K+ pipelines."

---

### 3D 🟡 REPETITIVE_FRAMING: Hevo block defaults to 3 Diagnostic openers

**What happens:** The best H-BATCHSHIFT variants are Diagnostic. The best H-MONITORING variants (especially [debugging-reframe]) are Diagnostic. When Pass 2 also rewrites H-FLEX as Diagnostic, you get 3 consecutive Diagnostic openers in the Hevo block, triggering REPETITIVE_FRAMING at the section level.

**The holistic penalty:** -0.2 at section level when 4+ bullets share a structural formula. With 3 Diagnostics in Hevo alone and 2-3 more in Gojek and Intuit, this fires frequently.

**Fix direction:** The story bank should explicitly flag which variant to use when "Diagnostic fatigue" is a risk. H-MONITORING has strong non-Diagnostic variants ([trial-conversion], [feature-ownership]) that don't require the Diagnostic opener. Pass 2 should be instructed: if more than 3 bullets in the section already use a Diagnostic opener, switch to Mechanism-first or Context-first for this bullet even if Diagnostic would otherwise be optimal.

---

### 3E 🟡 The story bank has 9 G-SUPPLY variants but they're not meaningfully differentiated for the scorer

**The problem:** There are now 5 G-SUPPLY variants (`[supply-diagnosis]`, `[API-launch]`, `[problem-diagnosis]`, `[ecosystem-GTM]`, `[partner-taxonomy]` — added 2026-03-26). They all produce bullets in the 120-200 char range, all use the same core metrics (18% supply, 1.5 min ETA), and all frame around marketplace supply. The scorer will give them similar scores regardless of which variant is chosen.

**More importantly:** None of the variants create a "wow" 9.0+ bullet because the earned detail is thin. The insight ("supply shortage was a platform extensibility problem") is good, but "designed integration requirements" and "built the business case" are relatively generic mechanism phrases. The real credentialing detail — what specific partner onboarding bottleneck was removed, what the technical approach was — is absent.

---

### 3F 🟡 O-AFFORDABILITY can't get above 8 without a concrete outcome metric

The scorer's note on O-AFFORDABILITY: "no metric beyond the win itself — volume of members analyzed, estimated savings, or adoption would elevate this to 9." The hackathon win is a self-credentialing opener and scores 8, but without scale ("X members screened," "Y% cost reduction estimate," "piloted with N clinical teams") it stays at 8.

---

### 3G 🟡 The story bank is calibrated for monetization/enterprise roles; PLG roles hit a ceiling

For PLG-focused JDs (Typeface, consumer growth roles), the closest stories are G-PRICING (research → tier launch) and H-BATCHSHIFT (segment pivot). Neither is PLG-native. The scorer will note JD fit gaps for activation, self-serve, viral loop signals.

For AI-heavy roles: H-MONITORING-AI now covers this slot (see 3C — resolved). AI JD fit is materially improved.

---

## Category 4: Scoring Calibration Issues

---

### 4A 🟡 The holistic score formula creates a ceiling around 8.3–8.5 for the current story bank

**The math (updated 2026-03-27):** With the current story bank post-fixes, realistic bullet score distribution is:
- 2 bullets at 9.0 (H-BATCHSHIFT + H-REGRESSION or I-RECONCILIATION when well-executed)
- 5-7 bullets at 8.0
- 1-2 bullets at 7.0 (attribution-vulnerable O-PROVIDER, if attribution guard misses)
- For AI JDs: H-MONITORING-AI replaces H-GENAI, eliminating the chronic 7.0 AI slot

Average ≈ 8.3–8.5. Penalties still fire occasionally (REPETITIVE_FRAMING -0.2) but attribution guards now prevent ATTRIBUTION_MISMATCH on G-SUPPLY and O-PROVIDER.

**To reach 8.5+ consistently:** H-QUERY upgrade (50% latency reduction, all-dashboards scope) should lift H-QUERY from 7-8 to a reliable 8-8.5. H-MONITORING-AI eliminates the 7.0 AI ceiling. Together these raise the expected holistic floor to 8.3-8.5 for most JDs.

---

### 4B 🟡 The scorer uses the same rubric for very different bullet types, disadvantaging "execution" stories

The rubric penalizes WEAK_MECHANISM, VAGUE_OUTCOME, and DECORATIVE_DETAIL. But some stories are inherently mechanism-thin: O-AFFORDABILITY (hackathon win = credentialing outcome, mechanism is prototyping), O-PROVIDER (API integration = execution, mechanism is schema mapping). These can't score 9+ by design because the rubric rewards analytical insight > execution.

This isn't a bug — it reflects real quality differences. But it means those story slots have a structurally lower ceiling than the Diagnostic stories.

---

### 4C 🟢 The scorer sometimes applies contradictory logic on archetype correctness

In the StockX run: Intuit #2 uses Impact-first ("Caught a billing failure impacting 1,500+...") and scores 8.0. The scorer notes the impact-first is correct because containment is the credentialing signal. But the Pass 2 prompt's DECISION CHAIN would have chosen Diagnostic here (Akshat owns the insight of "caught it before it spread"). In the eBay run the same bullet uses Impact-first and scores 8.0.

The scorer and Pass 2 apply slightly different archetype decision rules. When they disagree, Pass 4 gets confused about what to fix.

---

## Category 5: Content Expansion — What Would Move the Score Ceiling?

This is a separate question from pipeline fixes: if you added new stories to the story bank, what would have the highest expected impact on holistic scores?

---

### 5A 🔴 A Hevo monetization or retention story would unlock H3 from B-tier to A-tier

**Current H3 options:** H-REGRESSION (execution, 8 max), H-QUERY (tooling, 7-8), H-GENAI (AI, 7).

All three lack a business outcome that a PM hiring manager cares about. If you have any story from Hevo around:
- A pricing or packaging decision for a plan tier
- A customer retention initiative (what moved retention, what you shipped, outcome)
- A new feature you shipped with a clear adoption metric
- A customer journey improvement with a measurable business result

...that slot goes from a 7–8 ceiling to potentially a 9.0 slot. The H-BATCHSHIFT story scores 9.0 because it has a PM insight (auditability > features), a mechanism (batch-first pivot), and a business outcome (8 enterprise customers in 90 days). H3 needs a story with that same structure.

---

### 5B 🟡 A L'Oréal or MBA project slot (additional content section) would help for roles wanting broader PM exposure

You mentioned having L'Oréal bullets and strategy project bullets in the Bullet Bank. The current resume has 4 companies × 11 bullets. Adding a 5th section (e.g., "PROJECTS & CONSULTING" with 2 bullets — L'Oréal AI automation + USC Grab shuttle) would:
- Address JD fit gaps for consumer/CPG/AI strategy roles
- Provide a PLG-adjacent slot (if the Grab shuttle work had a user metric)
- Fill whitespace without shrinking existing bullets

**The tradeoff:** A 5th section tightens the docx layout significantly. With the current 4-tier system you'd need to drop total bullet count or accept tighter line spacing. Worth exploring as an optional layout variant.

---

### 5C 🟡 The G-SUPPLY story needs a sharper "earned detail"

The insight in G-SUPPLY is "supply shortage was a marketplace extensibility problem." That's good. But the mechanism is thin: "defined integration specs and partner onboarding workflow." What specifically made this non-obvious? Was there a particular partner type that unlocked disproportionate supply? Was there a specific technical constraint (max fleet size, geographic coverage rule, SLA requirement from the partner) that shaped the design? Any of those would lift G-SUPPLY from a 7.5-8 to a 9 bullet.

---

### 5D 🟢 O-PROVIDER needs a "panel size" or "member reach" metric for the specific integration

"Cut onboarding from 6 months to 10 weeks" is a clean efficiency metric but it's a one-time PM execution story. If the specific provider that was onboarded serves a knowable number of members (e.g., "enabling 200K member panel" or "adding 50 new provider locations"), that metric is directly attributable and would move the bullet from 7-8 to 8-9.

---

## Summary: Biggest Wins by Category

| Priority | Issue | Expected Score Impact | Cost to Fix | Status |
|---|---|---|---|---|
| 1 | Block Pass 1/2 from adding $110M/$20M attribution-mismatch metrics (guard) | +0.2 holistic per run | Hard constraint in Pass 1 + Pass 2 prompts | ✅ Done 2026-03-26 |
| 2 | Add $110M / $20M+ / 50M members to correct story bank variants | Same +0.2 — metrics now flow legitimately | Story bank edits in freeform_master_v2.txt | ✅ Done 2026-03-26 |
| 3 | Pass story_recommendations to Pass 1 via strategy formatted block | +0.1 JD fit per run | One-line code change in strategy.py | ✅ Done 2026-03-26 |
| 4 | Add Diagnostic saturation rule to Pass 2 prompt | +0.2 holistic (REPETITIVE_FRAMING) per affected run | Prompt addition in freeform_voice_rewrite.txt | ✅ Done 2026-03-26 |
| 5 | Lower expansion pass trigger 85%→80%, require ≥2 spare lines | Saves ~$0.04/run | Threshold change in freeform_runner.py | ✅ Done 2026-03-26 |
| 6 | Replace H-GENAI with a real Hevo business outcome story | +0.5-0.8 for AI-heavy JDs | New story content from Akshat | ✅ Done 2026-03-27 — H-MONITORING-AI added (anomaly detection + GenAI summarization, ~40% MTTR) |
| 7 | Tighten regression guard: revert P2→P1 if P1 was 2-liner AND P2 ≥ 230 chars | Eliminates QC-13 trim + expansion cycle ($0.06-0.10/run) | Code change to regression guard in freeform_runner.py | ✅ Done 2026-03-26 |
| 8 | Sharper G-SUPPLY earned detail (specific partner/technical constraint) | G-SUPPLY 7.5→9.0 ceiling unlock | **New story detail needed from Akshat** | ⚡ Partial — `[partner-taxonomy]` variant added 2026-03-26 using Bullet Bank material (metro/bus/private fleet taxonomy); deeper specifics (SLA, technical constraints) still blocked on Akshat |
| 9 | Add panel-size metric to O-PROVIDER for specific integration | O-PROVIDER 8→9 ceiling unlock | **New story detail needed from Akshat** | ⏳ Blocked — needs story material |
| 10 | Extract `_EXPANSION_PROMPT_TEMPLATE` to `prompts/freeform_expansion.txt` | Maintainability only | File move + code change | ⏳ Pending |
| 11 | Cache API key at startup instead of re-reading from disk each call | Negligible performance | Minor code refactor | ⏳ Pending |

---

## On the "Empty Space" Problem

You mentioned pushing bullets shorter creates empty space. Here's the actual failure mode:

The page fill calculation uses character count as a proxy for line count. Short bullets (130-145 chars) are estimated as 2-liners. If a run produces 11 short bullets averaging 150 chars, fill_pct drops below 85% and the expansion pass fires.

The real fix is **not** to make bullets longer again — it's to calibrate the story bank and layout so the page is naturally ~90-95% full with 11 good 2-liner bullets. With the current 4-tier system, 11 bullets averaging 155 chars produces roughly 85-90% fill at T0. The expansion pass threshold (85%) is very close to this natural fill level, causing it to fire on nearly every clean run.

Recommend: lower the expansion trigger from 85% to 80%, or only fire it if spare_lines >= 3. This eliminates most spurious expansion calls while still catching genuinely underutilized pages.

---

**Additional items resolved 2026-03-27:**
- H-QUERY upgrade: `50% query latency reduction` + `adopted across all Hevo 2.0 dashboards` added to both H-QUERY variants. Now A-tier for analytics/data-platform JDs.
- Professional Summary: 6 JD-tailored variants added to `freeform_master_v2.txt` (Section 0 pool). `freeform_runner.py` extracts and stores `summary_section`. `resume_docx.js` renders it as a "PROFESSIONAL SUMMARY" section. Fill estimator updated to account for summary DXA.
- Strategy Project: L'Oréal and Cloud Startup variants added as 6th Skills row. For AI JDs, L'Oréal variant replaces `[ai-automation]` row (max 6 rows maintained). Selection rules in SKILLS POOL.

*Generated: 2026-03-26 | Last updated: 2026-03-27 | 8 of 11 core items resolved*
