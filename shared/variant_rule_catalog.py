"""Exhaustive ownership catalog for documented resume-variant rules.

The catalog is the anti-cherry-picking contract: every named rule in the v4
variant rulebook, the operational rewrite/scorer prompts, and the v2 architecture
audit has one enforcement home.  ``status`` is deliberately honest; a mapped
rule can still be shadow-only, missing, or internally conflicted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuleOwner(str, Enum):
    DETERMINISTIC_VARIANT = "deterministic-variant"
    STRUCTURED_CRITIC = "structured-critic"
    ASSEMBLY = "assembly"
    NOT_APPLICABLE = "not-applicable"


class CoverageStatus(str, Enum):
    ENFORCED = "enforced"
    SHADOW = "shadow"
    MISSING = "missing"
    CONFLICT = "conflict"
    GUIDANCE = "guidance"


@dataclass(frozen=True)
class VariantRuleSpec:
    rule_id: str
    source: str
    name: str
    owner: RuleOwner
    status: CoverageStatus
    implementation: str
    note: str = ""


def _r(
    rule_id: str,
    source: str,
    name: str,
    owner: RuleOwner,
    status: CoverageStatus,
    implementation: str,
    note: str = "",
) -> VariantRuleSpec:
    return VariantRuleSpec(rule_id, source, name, owner, status, implementation, note)


DV = RuleOwner.DETERMINISTIC_VARIANT
SC = RuleOwner.STRUCTURED_CRITIC
AS = RuleOwner.ASSEMBLY
NA = RuleOwner.NOT_APPLICABLE
E = CoverageStatus.ENFORCED
S = CoverageStatus.SHADOW
M = CoverageStatus.MISSING
C = CoverageStatus.CONFLICT
G = CoverageStatus.GUIDANCE


RULE_CATALOG: tuple[VariantRuleSpec, ...] = (
    # VARIANT_FINALS_v4.md, Sections 1-2.
    _r("V4-01-SPINE", "v4:s1", "One opener-mechanism-outcome spine", SC, E, "challenger.rulebook_checks"),
    _r("V4-01-ARCHETYPE", "v4:s1,s11", "Choose the archetype that carries the real signal", SC, E, "challenger.rulebook_checks"),
    _r("V4-01-MECHANISM", "v4:s1", "Name a specific decision or artifact", SC, E, "challenger.rulebook_checks"),
    _r("V4-01-OUTCOME", "v4:s1", "Close on a proportionate attributable outcome", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-WHY-NOW", "v4:s2", "Explain why the work mattered now", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-CAUSALITY", "v4:s2", "Make every causal bridge explicit", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-EARNED-DETAIL", "v4:s2,s5", "Use one earned detail that passes detection and removal", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-LENGTH", "v4:s2;voice:s3", "Keep a render-efficient two- or three-line length", DV, S, "variant_text_lint.LENGTH_OUTSIDE_PREFERRED_RANGE", "v4 prefers 130-215 and accepts 216-260; voice prompt says 90-299"),
    _r("V4-02-NO-EM-DASH", "v4:s2", "No em dashes", DV, S, "variant_text_lint.EM_DASH_PRESENT"),
    _r("V4-02-NO-PARENS", "v4:s2", "No parentheses", DV, S, "variant_text_lint.PARENTHESES_PRESENT"),
    _r("V4-02-MOM-TEST", "v4:s2", "An outside nontechnical recruiter understands it in one read", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-ONE-ARGUMENT", "v4:s2,s8", "Do not splice adjacent story beats", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-MECHANISM-FIT", "v4:s2", "Mechanism directly answers the opener", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-OUTCOME-CLOSURE", "v4:s2,s8", "Outcome completes the opening claim", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-BEST-OUTCOME", "v4:s2,s5,s8", "Prefer the strongest downstream attributable outcome", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-OUTSIDER-LEGIBILITY", "v4:s2,s8", "Introduce internal names by function", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-CLOSED-EVIDENCE", "v4:s2", "Discovery stories close qualitative evidence with behavior and a decision", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-COGNITIVE-LOAD", "v4:s2", "Avoid fake complexity and stacked concepts", SC, E, "challenger.rulebook_checks"),
    _r("V4-02-OPENER-VARIETY", "v4:s2,s8,s9", "Vary openers within blocks and across page", AS, E, "resume_lint._lint_archetypes_and_openers"),

    # Sections 3-5: opener, mechanism, and earned-detail choices.
    _r("V4-03-ORIENTATION", "v4:s3", "Orient before technical numbers or shorthand", SC, E, "challenger.rulebook_checks"),
    _r("V4-03-GAP-FIRST", "v4:s3", "State the gap before its solution when the gap creates the need", SC, E, "challenger.rulebook_checks"),
    _r("V4-03-PRODUCT-INSIGHT", "v4:s3", "Lead with product insight over approval mechanics", SC, E, "challenger.rulebook_checks"),
    _r("V4-03-TRANSFORMATION", "v4:s3", "Reshaped names both before-state and after-state", SC, E, "challenger.rulebook_checks"),
    _r("V4-03-JOURNEY", "v4:s3", "Converted is reserved for a real stage transition", SC, E, "challenger.rulebook_checks"),
    _r("V4-04-DESIGN-DECISION", "v4:s4", "Name the design decision rather than a category", SC, E, "challenger.rulebook_checks"),
    _r("V4-04-BUILT-BY", "v4:s4", "Built X by Y is an optional end-to-end construction", NA, G, "writing guidance", "example construction, not a universal requirement"),
    _r("V4-04-DIAGNOSING-CONSTRUCTION", "v4:s4", "By diagnosing is an optional diagnosis construction", NA, G, "writing guidance", "example construction, not a universal requirement"),
    _r("V4-04-TRADEOFF", "v4:s4", "Use trading rather than accepting for an intentional tradeoff", DV, S, "variant_text_lint.PASSIVE_TRADEOFF_WORDING"),
    _r("V4-04-REFRAME", "v4:s4", "A reframe names both sides", SC, E, "challenger.rulebook_checks"),
    _r("V4-04-FROM-TO", "v4:s4", "From X to Y is optional range compression", NA, G, "writing guidance", "example construction, not a universal requirement"),
    _r("V4-04-ORG-RIPPLE", "v4:s4", "Show action to adoption or organization to result when evidenced", SC, E, "challenger.rulebook_checks"),
    _r("V4-04-FACT-BOUNDARY", "v4:s4", "Mechanism details resolve to source evidence", DV, M, "facts ledger plus fact-atom containment", "current metadata records atoms but does not prove every proper noun or phrase"),
    _r("V4-05-REMOVAL", "v4:s5", "Drop decorative detail that survives removal", SC, E, "challenger.rulebook_checks"),
    _r("V4-05-NO-FORCED-DETAIL", "v4:s5", "Clarity beats forced specificity", SC, E, "challenger.rulebook_checks"),
    _r("V4-05-TECHNICAL-PM", "v4:s5", "Technical detail must carry PM meaning and business consequence", SC, E, "challenger.rulebook_checks"),
    _r("V4-05-JARGON", "v4:s5,s8", "Do not stack technical terms without PM meaning", SC, E, "challenger.rulebook_checks"),
    _r("V4-05-VISCERAL-RESULT", "v4:s5", "Prefer the more concrete result when it proves the same claim", SC, E, "challenger.rulebook_checks"),

    # Sections 6-8: attribution and readability.
    _r("V4-06-ATTRIBUTION", "v4:s6,s8", "Distinguish enabled platform outcome from personal result", SC, E, "challenger.rulebook_checks"),
    _r("V4-06-SCALE-CONTEXT", "v4:s6", "Use platform scale as context, not personal output", SC, E, "challenger.rulebook_checks"),
    _r("V4-06-CONTRAST-CAP", "v4:s6,s9;voice:s2", "Limit contrast constructions", AS, C, "resume_lint.CONTRAST_PHRASE_CAP_EXCEEDED", "v4 says per company and elsewhere 1 page-wide; current linter uses page-wide 1"),
    _r("V4-07-TWO-BEAT", "v4:s7", "Use one natural primary pause and a linear two-beat rhythm", DV, S, "variant_text_lint.TOO_MANY_PRIMARY_PAUSES plus critic"),
    _r("V4-07-WHERE", "v4:s7", "Where is optional technical-context phrasing", NA, G, "writing guidance", "preferred construction, not a universal requirement"),
    _r("V4-07-OWNERSHIP", "v4:s7", "Use active direct-ownership language", SC, E, "challenger.rulebook_checks"),
    _r("V4-07-DURATION", "v4:s7", "Drop duration that is context rather than a transformation metric", DV, S, "variant_text_lint.DURATION_AS_CONTEXT_PROXY"),
    _r("V4-07-VERB-ENERGY", "v4:s7,s10", "Match verb energy across sibling variants", SC, E, "family-level challenger comparison"),
    _r("V4-07-IMPROVED-BY", "v4:s7,s10", "Do not open Improved X by Y", DV, S, "variant_text_lint.IMPROVED_BY_OPENER"),
    _r("V4-07-PRECISION", "v4:s7", "Use ranges for estimates and precision only for measurements", DV, S, "variant_text_lint.FALSE_PRECISION_PROXY", "measurement exception requires critic or facts"),
    _r("V4-07-START-OLD", "v4:s7", "Challenge the incumbent before rebuilding from source", NA, G, "challenger pairwise process", "process order, not a prose property"),
    _r("V4-08-GENERIC-MECHANISM", "v4:s8", "Reject documented generic mechanism phrases", DV, S, "variant_text_lint.GENERIC_MECHANISM_PHRASE plus critic"),
    _r("V4-08-WRONG-ARCHETYPE", "v4:s8,s11", "Reject an archetype that buries the scarce signal", SC, E, "challenger.rulebook_checks"),
    _r("V4-08-FORCED-CONTRAST", "v4:s8", "Contrast must encode a real corrected assumption", SC, E, "challenger.rulebook_checks plus assembly cap"),
    _r("V4-08-MONOTONY", "v4:s8,s9", "No three consecutive diagnostic bullets in one block", AS, E, "resume_lint.DIAGNOSTIC_STREAK_EXCEEDED"),
    _r("V4-08-SPLIT-ARGUMENT", "v4:s8", "Do not combine disconnected paths", SC, E, "challenger.rulebook_checks", "LOW_CLAUSE_COHESION_PROXY and PREDICATE_LOAD_HIGH force review but do not decide semantics"),
    _r("V4-08-MISMATCHED-OUTCOME", "v4:s8", "Outcome must answer the opener", SC, E, "challenger.rulebook_checks"),
    _r("V4-08-INPUT-OUTCOME", "v4:s8", "Do not end on activity volume when downstream behavior exists", SC, E, "challenger.rulebook_checks"),
    _r("V4-08-INSIDER-CONTEXT", "v4:s8", "Explain internal objects by function", SC, E, "challenger.rulebook_checks"),

    # Sections 9-11: assembled-page composition and critic calibration.
    _r("V4-09-DISTRIBUTION", "v4:s9,s11", "Use route-specific archetype bounds", AS, E, "resume_lint.ArchetypeContract"),
    _r("V4-09-NONDIAGNOSTIC-FLOOR", "v4:s9", "Meet route-owned action plus impact floor", AS, E, "resume_lint.ACTION_IMPACT_FLOOR_MISSED"),
    _r("V4-09-OWNERSHIP-FLOOR", "v4:s9", "At least one page bullet opens with strong ownership", AS, E, "resume_lint.OWNERSHIP_OPENER_MISSING"),
    _r("V4-09-IMPACT-CAP", "v4:s3,s9,s11", "Cap impact-first bullets", AS, C, "resume_lint.ArchetypeContract", "same rulebook says max 2-3, exactly 2, and max 2"),
    _r("V4-10-SHIPPED-DESIGNED", "v4:s10", "Prefer Shipped over Designed only when production is evidenced", SC, E, "challenger.rulebook_checks"),
    _r("V4-10-LED-DROVE", "v4:s10", "Prefer Led only for accountable end-to-end ownership", SC, E, "challenger.rulebook_checks"),
    _r("V4-10-CUT-REDUCED", "v4:s10", "Match Cut or Reduced to magnitude and evidence", SC, E, "challenger.rulebook_checks"),
    _r("V4-11-NO-CEILING", "v4:s11", "Do not privilege one archetype in scoring", SC, E, "archetype-specific critic check"),
    _r("V4-11-CAUGHT", "v4:s11", "Classify Caught and other detection verbs as diagnostic", DV, S, "variant_text_lint.ARCHETYPE_METADATA_MISMATCH"),

    # Operational prompt rules that are stricter than or absent from v4.
    _r("VOICE-REGISTER", "voice:s3", "Implied subject and no personal pronouns", DV, S, "variant_text_lint.PERSONAL_PRONOUN_PRESENT"),
    _r("VOICE-NO-MARKDOWN", "legacy-rulebook;voice:output", "Paste-ready prose contains no Markdown", DV, S, "variant_text_lint.MARKDOWN_PRESENT"),
    _r("VOICE-AND-CAP", "voice:s3", "Maximum one and per bullet", DV, C, "variant_text_lint.CONJUNCTION_LOAD_HIGH", "known gold variants exceed it, so it remains a review proxy rather than a blocker"),
    _r("VOICE-PARALLEL-CLAUSE", "voice:s3", "Avoid While X also Y parallel branches", DV, S, "variant_text_lint.SUBORDINATE_CLAUSE_OPENER plus critic"),
    _r("VOICE-LATE-SUBJECT", "voice:s3", "Avoid which, this, or it when referent requires backtracking", DV, S, "variant_text_lint.LATE_SUBJECT_PROXY"),
    _r("VOICE-FORBIDDEN-WORDS", "voice:s3;targeted-swap", "Reject forbidden filler words", DV, S, "variant_text_lint.FORBIDDEN_WORD_PRESENT"),
    _r("VOICE-FORBIDDEN-OPENERS", "voice:s3;targeted-swap", "Reject weak or participation-first openers", DV, S, "variant_text_lint.FORBIDDEN_OR_WEAK_OPENER"),
    _r("VOICE-SUBORDINATE-OPENER", "architecture:group-b", "Reject subordinate-conjunction openers", DV, S, "variant_text_lint.SUBORDINATE_CLAUSE_OPENER"),
    _r("VOICE-VAGUE-STAKEHOLDER", "voice:s3;targeted-swap", "Name actual functions instead of stakeholders", DV, S, "variant_text_lint.VAGUE_STAKEHOLDER_NOUN"),
    _r("VOICE-METRIC-FIRST", "voice:s3", "Do not front-load a bare decorative metric", DV, S, "variant_text_lint.DECORATIVE_METRIC_OPENER"),
    _r("VOICE-FRAGMENT-OUTCOME", "architecture:group-b", "Tie outcome fragments to a verb", DV, S, "variant_text_lint.FRAGMENT_LIST_OUTCOME"),
    _r("VOICE-PASSIVE", "scorer:failure-modes", "Avoid passive or nominalized ownership", DV, S, "variant_text_lint.PASSIVE_CONSTRUCTION_PROXY plus critic"),
    _r("VOICE-TERMINAL-PUNCT", "architecture:group-a", "Candidate carries terminal punctuation", DV, S, "variant_text_lint.TERMINAL_PUNCTUATION_MISSING"),
    _r("VOICE-ONE-DETAIL", "voice:earned-detail", "Use one primary earned detail", SC, E, "challenger.rulebook_checks"),
    _r("VOICE-NO-INVENT", "voice:earned-detail;targeted-swap", "Do not invent or recombine facts during rewrite", SC, E, "fact containment veto plus source_fact_atoms"),

    # Architecture v2 deterministic page and process requirements.
    _r("ARCH-DUPLICATE-FIGURE", "architecture:t1", "Detect repeated figures", AS, E, "resume_lint.FIGURE_REPEATED_*"),
    _r("ARCH-DUPLICATE-PHRASE", "architecture:t1", "Detect repeated three-word phrases", AS, E, "resume_lint.PHRASE_REPEATED"),
    _r("ARCH-SCALE-COHERENCE", "architecture:t1", "Surface incoherent page-level dollar scales", AS, E, "resume_lint.CURRENCY_SCALE_INCOHERENT"),
    _r("ARCH-PUNCTUATION", "architecture:t1", "Use consistent terminal punctuation", AS, E, "resume_lint.BULLET_PUNCTUATION_INCONSISTENT"),
    _r("ARCH-DATE-FORMAT", "architecture:t1", "Use one date format", AS, E, "resume_lint.DATE_FORMAT_INCONSISTENT"),
    _r("ARCH-LINE-PREDICTION", "architecture:t1", "Use rendered geometry rather than bullet count for page fit", AS, E, "resume_fill plus observed PDF geometry"),
    _r("ARCH-PAGE-COUNT", "architecture:t0,t1", "Require an observed one-page PDF", AS, E, "resume_lint.PAGE_COUNT_INVALID"),
    _r("ARCH-SECTION-INTEGRITY", "architecture:t0", "Reject duplicate or ambiguous model section sets", AS, E, "resume_lint.MODEL_SECTION_DUPLICATED"),
    _r("ARCH-RENDER-PARITY", "architecture:t0", "Rendered text equals assembled text", AS, E, "resume_lint.RENDERED_TEXT_MISMATCH"),
    _r("ARCH-PROVENANCE", "architecture:t1,t6", "Every external claim resolves to an approved source atom", DV, M, "facts ledger and semantic atom matcher", "semantic source matching is still missing"),
    _r("ARCH-IDENTITY-SIGNIFICANCE", "architecture:group-b", "Bullet subject proves significant role identity, not low-level detection", SC, E, "materiality and criterion-proof checks"),
    _r("ARCH-INTRA-REDUNDANCY", "architecture:group-b", "Do not restate one claim twice inside a bullet", SC, E, "challenger.rulebook_checks"),
    _r("ARCH-INSIGHT-DIFFICULTY", "architecture:group-b", "Insight should not be obvious to a competent peer", SC, E, "variant admission difficulty plus challenger.rulebook_checks"),
    _r("ARCH-NONREGRESSION", "architecture:t4", "Challenger must materially Pareto-dominate its incumbent", SC, E, "claim_spine.decide_pairwise"),
    _r("ARCH-CRITERION-PROOF", "material-mechanism", "Prove a funded hiring criterion, not topical similarity", SC, E, "challenger.rulebook_checks"),
    _r("ARCH-COUNTERFACTUAL", "material-mechanism", "Make counterfactual ownership visible", SC, E, "challenger.rulebook_checks"),
    _r("ARCH-SCARCE-ATOM", "material-mechanism", "Lead with the scarcest causal atom", SC, E, "challenger.rulebook_checks"),
    _r("ARCH-PAGE-VALUE", "material-mechanism", "Retain only positive marginal page value", SC, E, "pairwise material rank plus adaptive assembly"),
    _r("ARCH-COMPRESSION", "material-mechanism", "Compress by information role, not arbitrary character count", SC, E, "challenger.rulebook_checks"),
)


STRUCTURED_CRITIC_RULE_GROUPS: dict[str, frozenset[str]] = {
    "materiality": frozenset(
        {
            "V4-02-WHY-NOW",
            "ARCH-IDENTITY-SIGNIFICANCE",
            "ARCH-INSIGHT-DIFFICULTY",
            "ARCH-PAGE-VALUE",
        }
    ),
    "criterion_and_scarce_signal": frozenset(
        {
            "ARCH-CRITERION-PROOF",
            "ARCH-SCARCE-ATOM",
            "V4-03-PRODUCT-INSIGHT",
        }
    ),
    "archetype_fit": frozenset(
        {
            "V4-01-ARCHETYPE",
            "V4-03-TRANSFORMATION",
            "V4-03-JOURNEY",
            "V4-08-WRONG-ARCHETYPE",
            "V4-10-SHIPPED-DESIGNED",
            "V4-10-LED-DROVE",
            "V4-10-CUT-REDUCED",
            "V4-11-NO-CEILING",
        }
    ),
    "single_story_spine": frozenset(
        {
            "V4-01-SPINE",
            "V4-02-ONE-ARGUMENT",
            "V4-08-SPLIT-ARGUMENT",
            "ARCH-INTRA-REDUNDANCY",
        }
    ),
    "causal_closure": frozenset(
        {
            "V4-01-OUTCOME",
            "V4-02-CAUSALITY",
            "V4-02-MECHANISM-FIT",
            "V4-02-OUTCOME-CLOSURE",
            "V4-04-ORG-RIPPLE",
            "V4-08-MISMATCHED-OUTCOME",
        }
    ),
    "counterfactual_ownership": frozenset(
        {
            "ARCH-COUNTERFACTUAL",
            "V4-07-OWNERSHIP",
        }
    ),
    "mechanism_specificity": frozenset(
        {
            "V4-01-MECHANISM",
            "V4-03-ORIENTATION",
            "V4-03-GAP-FIRST",
            "V4-04-DESIGN-DECISION",
            "V4-04-REFRAME",
        }
    ),
    "earned_detail": frozenset(
        {
            "V4-02-EARNED-DETAIL",
            "V4-05-REMOVAL",
            "V4-05-NO-FORCED-DETAIL",
            "V4-05-TECHNICAL-PM",
            "VOICE-ONE-DETAIL",
        }
    ),
    "attribution_and_outcome": frozenset(
        {
            "V4-02-BEST-OUTCOME",
            "V4-05-VISCERAL-RESULT",
            "V4-06-ATTRIBUTION",
            "V4-06-SCALE-CONTEXT",
            "V4-08-INPUT-OUTCOME",
        }
    ),
    "outsider_legibility": frozenset(
        {
            "V4-02-MOM-TEST",
            "V4-02-OUTSIDER-LEGIBILITY",
            "V4-08-INSIDER-CONTEXT",
        }
    ),
    "cognitive_load": frozenset(
        {
            "V4-02-COGNITIVE-LOAD",
            "V4-05-JARGON",
            "ARCH-COMPRESSION",
        }
    ),
    "evidence_loop": frozenset({"V4-02-CLOSED-EVIDENCE"}),
    "rhetorical_integrity": frozenset({"V4-08-FORCED-CONTRAST"}),
    "fact_containment": frozenset({"VOICE-NO-INVENT"}),
    "family_non_regression": frozenset(
        {
            "V4-07-VERB-ENERGY",
            "ARCH-NONREGRESSION",
        }
    ),
}

STRUCTURED_CHALLENGER_DIMENSIONS = frozenset(STRUCTURED_CRITIC_RULE_GROUPS)


def validate_rule_catalog() -> list[str]:
    errors: list[str] = []
    ids = [rule.rule_id for rule in RULE_CATALOG]
    if len(ids) != len(set(ids)):
        duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
        errors.append(f"duplicate rule ids: {duplicates}")
    for rule in RULE_CATALOG:
        if not rule.rule_id or not rule.source or not rule.name or not rule.implementation:
            errors.append(f"{rule.rule_id or '<missing>'}: incomplete catalog record")
        if rule.owner is RuleOwner.NOT_APPLICABLE and rule.status is not CoverageStatus.GUIDANCE:
            errors.append(f"{rule.rule_id}: not-applicable rules must be guidance")
        if rule.status is CoverageStatus.MISSING and not rule.note:
            errors.append(f"{rule.rule_id}: missing rule needs an explicit gap note")
    grouped_rule_ids = [
        rule_id
        for rule_ids in STRUCTURED_CRITIC_RULE_GROUPS.values()
        for rule_id in rule_ids
    ]
    if len(grouped_rule_ids) != len(set(grouped_rule_ids)):
        errors.append("structured critic rule groups contain duplicate rule ids")
    expected_structured = {
        rule.rule_id
        for rule in RULE_CATALOG
        if rule.owner is RuleOwner.STRUCTURED_CRITIC
        and rule.status in {CoverageStatus.ENFORCED, CoverageStatus.SHADOW}
    }
    actual_structured = set(grouped_rule_ids)
    if actual_structured != expected_structured:
        errors.append(
            "structured critic rule groups mismatch: "
            f"missing={sorted(expected_structured - actual_structured)} "
            f"extra={sorted(actual_structured - expected_structured)}"
        )
    return errors
