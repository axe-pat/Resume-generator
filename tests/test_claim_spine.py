from dataclasses import replace

import pytest

from shared.claim_spine import (
    ClaimCandidate,
    ClaimSpine,
    CriticalVetoes,
    MaterialRank,
    PairwiseCase,
    PairwiseVerdict,
    REPO_ROOT,
    decide_pairwise,
    load_pairwise_cases,
    validate_case,
    validate_cases,
)
from shared.gold_variant_registry import load_registry


def _candidate(
    candidate_id: str,
    *,
    story_id: str = "STORY",
    claim_id: str | None = None,
    criteria=("criterion",),
    rank=(3, 3, 3, 3, 3),
    line_cost=2,
    critical=None,
    judgment="made a product judgment",
):
    if critical is None:
        critical = CriticalVetoes(True, True, True, True, True, True)
    return ClaimCandidate(
        candidate_id=candidate_id,
        story_id=story_id,
        claim_id=claim_id or story_id,
        text=f"{candidate_id} text",
        spine=ClaimSpine(
            trigger="material trigger",
            judgment=judgment,
            mechanism="specific decision",
            outcome="attributable outcome",
        ),
        scarce_atom="insight",
        criterion_proof=frozenset(criteria),
        counterfactual_ownership="The result depended on the candidate's decision.",
        decision_rationale="",
        excluded_adjacent_atoms=(),
        critical=critical,
        material_rank=MaterialRank(*rank),
        line_cost=line_cost,
    )


def _case(incumbent, challenger, **kwargs):
    return PairwiseCase(
        case_id="case",
        target="target",
        slot_question="What material criterion does this prove?",
        incumbent=incumbent,
        challenger=challenger,
        source_refs=("fixture/source",),
        **kwargs,
    )


def test_nine_golden_pairs_are_valid_and_choose_the_known_winner():
    cases = load_pairwise_cases()
    assert len(cases) == 9
    assert len({case.case_id for case in cases}) == 9
    assert validate_cases(cases) == []
    for case in cases:
        assert validate_case(case) == []
        assert case.expected_verdict is PairwiseVerdict.ACCEPT_CHALLENGER
        assert decide_pairwise(case).verdict is case.expected_verdict
        assert all((REPO_ROOT / source_ref).exists() for source_ref in case.source_refs)


def test_golden_challengers_are_exact_approved_gold_text():
    approved = {variant.variant_id: variant.text for variant in load_registry()}
    for case in load_pairwise_cases():
        assert case.challenger.candidate_id in approved
        assert case.challenger.text == approved[case.challenger.candidate_id]


def test_challenger_critical_veto_keeps_incumbent():
    challenger = replace(
        _candidate("challenger", rank=(4, 4, 4, 4, 4)),
        critical=CriticalVetoes(True, False, True, True, True, True),
    )
    decision = decide_pairwise(_case(_candidate("incumbent"), challenger))
    assert decision.verdict is PairwiseVerdict.KEEP_INCUMBENT
    assert decision.challenger_failures == ("causal_edge_integrity",)


def test_both_critical_failures_require_human_review():
    failed = CriticalVetoes(True, True, True, True, False, True)
    decision = decide_pairwise(
        _case(
            replace(_candidate("incumbent"), critical=failed),
            replace(_candidate("challenger"), critical=failed),
        )
    )
    assert decision.verdict is PairwiseVerdict.HUMAN_REVIEW


def test_critically_unsafe_incumbent_does_not_waive_challenger_material_regression():
    failed = CriticalVetoes(True, True, True, True, False, True)
    incumbent = replace(
        _candidate("incumbent", rank=(4, 4, 4, 4, 4)),
        critical=failed,
    )
    challenger = _candidate("challenger", rank=(4, 4, 4, 4, 3))
    decision = decide_pairwise(_case(incumbent, challenger))
    assert decision.verdict is PairwiseVerdict.HUMAN_REVIEW
    assert "critically unsafe" in decision.reason


def test_pareto_improvement_accepts_challenger():
    decision = decide_pairwise(
        _case(
            _candidate("incumbent", rank=(3, 3, 3, 3, 3)),
            _candidate("challenger", rank=(4, 3, 3, 3, 3)),
        )
    )
    assert decision.verdict is PairwiseVerdict.ACCEPT_CHALLENGER


def test_material_tradeoff_requires_human_review_and_keeps_incumbent_as_default():
    decision = decide_pairwise(
        _case(
            _candidate("incumbent", rank=(3, 4, 3, 3, 3)),
            _candidate("challenger", rank=(4, 3, 3, 3, 3)),
        )
    )
    assert decision.verdict is PairwiseVerdict.HUMAN_REVIEW
    assert "incumbent remains shipping default" in decision.reason


def test_incumbent_wins_exact_material_and_line_cost_tie():
    decision = decide_pairwise(
        _case(_candidate("incumbent"), _candidate("challenger"))
    )
    assert decision.verdict is PairwiseVerdict.KEEP_INCUMBENT


def test_line_cost_can_break_exact_material_tie_only_for_same_claim():
    incumbent = _candidate("incumbent", story_id="SAME", claim_id="CLAIM-A", line_cost=3)
    same_claim = _candidate("challenger", story_id="SAME", claim_id="CLAIM-A", line_cost=2)
    other_claim = _candidate("other", story_id="SAME", claim_id="CLAIM-B", line_cost=2)

    assert (
        decide_pairwise(_case(incumbent, same_claim)).verdict
        is PairwiseVerdict.ACCEPT_CHALLENGER
    )
    assert (
        decide_pairwise(_case(incumbent, other_claim)).verdict
        is PairwiseVerdict.KEEP_INCUMBENT
    )


def test_keep_both_requires_page_budget_and_mutually_unique_criterion_proof():
    incumbent = _candidate("incumbent", criteria=("leadership", "operations"))
    distinct = _candidate("challenger", criteria=("leadership", "prototyping"))
    subset = _candidate("subset", criteria=("leadership",))

    funded = _case(
        incumbent,
        distinct,
        request_keep_both=True,
        page_can_fund_both=True,
    )
    unfunded = replace(funded, page_can_fund_both=False)
    not_distinct = replace(funded, challenger=subset)

    assert decide_pairwise(funded).verdict is PairwiseVerdict.KEEP_BOTH
    assert decide_pairwise(unfunded).verdict is PairwiseVerdict.KEEP_INCUMBENT
    assert decide_pairwise(not_distinct).verdict is PairwiseVerdict.KEEP_INCUMBENT


def test_judgment_or_explicit_decision_rationale_is_required():
    missing = replace(
        _candidate("challenger", judgment=""),
        decision_rationale="",
    )
    case = _case(_candidate("incumbent"), missing)
    assert any("spine.judgment or decision_rationale" in error for error in validate_case(case))
    with pytest.raises(ValueError, match="spine.judgment or decision_rationale"):
        decide_pairwise(case)

    rationale_only = replace(missing, decision_rationale="The trigger made this decision necessary.")
    assert validate_case(_case(_candidate("incumbent"), rationale_only)) == []


def test_ownership_is_a_valid_scarce_causal_atom():
    ownership_led = replace(_candidate("ownership-led"), scarce_atom="ownership")
    assert validate_case(_case(_candidate("incumbent"), ownership_led)) == []
