# Variant rule enforcement coverage

## Outcome

The candidate-variant path now runs the complete documented rule set through one
ownership catalog instead of choosing a convenient checklist. The catalog contains
**99 named rules** from `VARIANT_FINALS_v4.md`, the operational voice/scorer rules,
the v2 architecture audit, and the material-claim mechanism.

Run the gate from the repository root:

```bash
PYTHONPATH=. venv/bin/python resume/variants/rule_coverage.py
```

Current result:

```text
Rule ownership coverage: 99/99 mapped
Owner counts: assembly 16; deterministic-variant 25; not-applicable 5; structured-critic 53
Structured review dimensions: 15
```

“Mapped” does not mean “already solved.” The command keeps missing rules and internal
rulebook conflicts visible and still exits nonzero if a rule loses its owner or a
structured rule drops out of the mandatory review card.

## What runs for every new challenger

`shared/variant_text_lint.py` applies deterministic single-bullet checks. Blocking
checks include weak or forbidden openers, including **`Saved`**, subordinate-clause
openers, known generic mechanisms, em dashes, parentheses, first-person register,
forbidden filler, decorative metric openers, vague stakeholder nouns, fragment-list
outcomes, passive trade-off wording, missing punctuation, and diagnostic-opener
archetype mismatches.

It also emits non-blocking review proxies for high predicate load, low cohesion across
the two clauses, conjunction load, ambiguous late subjects, passive constructions,
duration padding, false precision, and outlier length. These are deliberately proxies:
a regex can force inspection of a possible split story, but cannot prove causality.

`resume/variants/challenger_runner.py` now rejects any candidate missing one of the
15 mandatory structured review dimensions. An accepted challenger cannot fail any
dimension. This forces the critic to adjudicate materiality, criterion proof, archetype,
single-story integrity, causal closure, ownership, mechanism, earned detail, outcome
and attribution, outsider legibility, cognitive load, evidence loop, rhetoric, fact
containment, and family-level non-regression every time.

`shared/resume_lint.py` remains the sole owner of assembled-page checks: profile and
allocation, archetype mix, repetition, figures, phrase overlap, scale coherence,
section integrity, rendered-text parity, and observed one-page output. The new variant
gate does not duplicate those checks.

## The Ceipal failure is now caught

The rejected draft:

> Saved FlairX's highest-volume account after Ceipal's read-only API blocked score
> write-back; shipped a pull-first MVP that removed roughly 80% of duplicate work and
> launched on Ceipal's marketplace as a new B2B channel.

Deterministic result:

- `FORBIDDEN_OR_WEAK_OPENER`: `Saved` is blocked.
- `PREDICATE_LOAD_HIGH`: at least five actions/outcomes are compressed together.
- `LOW_CLAUSE_COHESION_PROXY`: the two beats share too little semantic anchoring, so
  the structured `single_story_spine` and `causal_closure` decisions cannot be skipped.

This captures the real failure without pretending lexical overlap can decide whether
account retention, duplicate-work removal, and marketplace distribution form one story.

## Important rule-hygiene finding

The rulebook is useful but not fully conflict-free. Three conflicts remain visible:

1. Contrast is described both as one per company and one per full page. The current
   assembly linter uses the stricter page-wide cap.
2. Impact-first is variously capped at `2`, `exactly 2`, and `2–3`. Route-owned
   archetype contracts currently decide the actual bound.
3. The voice prompt says at most one `and` per bullet, but reviewed gold bullets exceed
   that without becoming unreadable. It is therefore a review proxy, not an automatic
   blocker.

Two substantive gaps remain: semantic provenance for every external phrase/proper noun,
and the underlying facts-ledger boundary. Fact atoms and source references exist, but
exact semantic entailment is not deterministic yet. Neither gap is silently waived.

## Integration boundary

The live generator is unchanged by this work. The reusable entrypoints are:

- `lint_candidate_variant_text(text, declared_archetype=...)`
- `check_new_candidate_admission(variant)`
- `challenger_runner.validate_response(payload, bundle)`
- `lint_assembled_resume(document, RELEASE_POLICY)` for page release

Existing incumbents are not retroactively rejected by stricter challenger-only rules.
They require pairwise review because doing otherwise would newly fail known fixtures.
New candidates receive no such grandfathering.

The shadow gate currently identifies three exact cleanup items among the 22 reviewed
gold records before a strict live-v2 release can apply the same contract universally:

- `I-INCIDENT-amazon-parallel-response`: forbidden `Coordinated` opener.
- `O-AFFORDABILITY-studyfetch-ml-prototype`: vague `stakeholders` noun.
- `NIVEDA-studyfetch-mobile-school`: missing terminal period.

The last two are mechanical. The incident opener requires a material pairwise rewrite,
not an automatic synonym swap.
