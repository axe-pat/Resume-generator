from pathlib import Path

import pytest

from shared.resume_fill import (
    AdaptiveAssemblyRequest,
    AdaptiveFillPolicy,
    FillAction,
    LayoutCandidate,
    ObservedPdfGeometry,
    PdfPageGeometry,
    ProofKind,
    ProofVariant,
    select_adaptive_assembly,
)


LAYOUTS = (
    LayoutCandidate("relaxed", -1),
    LayoutCandidate("standard", 0),
    LayoutCandidate("compact", 1),
)


def _geometry(fill_ratio: float, *, pages: int = 1) -> ObservedPdfGeometry:
    top, bottom, height = 36.0, 36.0, 792.0
    content_bottom = top + fill_ratio * (height - top - bottom)
    page = PdfPageGeometry(612.0, height, 40.0, content_bottom, 600)
    return ObservedPdfGeometry(Path("shadow.pdf"), (page,) * pages, top, bottom)


def _proof(
    index: int,
    *,
    criterion: str | None = None,
    kind: ProofKind = ProofKind.EXPERIENCE,
    admitted: bool = True,
    protected: bool = False,
    marginal: float = 1.0,
    rank: int | None = None,
    line_cost: float = 2.0,
) -> ProofVariant:
    return ProofVariant(
        variant_id=f"V{index}",
        kind=kind,
        material_rank=rank or index,
        line_cost=line_cost,
        funded_criteria=(criterion or f"criterion-{index}",),
        marginal_page_value=marginal,
        admitted=admitted,
        protected=protected,
    )


def _request(
    count: int,
    *,
    maximum: int = 11,
    candidates=(),
    geometry=None,
    layouts=(LayoutCandidate("standard", 0),),
    current_layout="standard",
    profile_id="product-general",
) -> AdaptiveAssemblyRequest:
    selected = tuple(_proof(index) for index in range(1, count + 1))
    funded = tuple(f"criterion-{index}" for index in range(1, maximum + 3))
    return AdaptiveAssemblyRequest(
        policy=AdaptiveFillPolicy(
            9,
            10,
            maximum,
            profile_id=profile_id,
            funded_criteria=funded,
        ),
        selected=selected,
        unselected_candidates=tuple(candidates),
        geometry=geometry or _geometry(0.85),
        current_layout_id=current_layout,
        layouts=tuple(layouts),
    )


@pytest.mark.parametrize("starting_count", [9, 10])
def test_sparse_nine_or_ten_adds_one_distinct_admitted_candidate(starting_count):
    candidate = _proof(starting_count + 1, marginal=3.0, rank=1, line_cost=2.5)

    decision = select_adaptive_assembly(
        _request(starting_count, candidates=(candidate,))
    )

    assert decision.action is FillAction.ADD_APPROVED_PROOF
    assert decision.added_variant_id == candidate.variant_id
    assert decision.proof_units_after == starting_count + 1
    assert decision.reason_code == "ADD_DISTINCT_ADMITTED_PROOF"


def test_sparse_eleven_does_not_exceed_standard_profile_maximum():
    decision = select_adaptive_assembly(
        _request(11, candidates=(_proof(12, marginal=5.0),))
    )

    assert decision.action is FillAction.ACCEPT_UNDERFILL
    assert decision.reason_code == "QUALITY_PROTECTED_UNDERFILL"
    assert decision.proof_units_after == 11
    assert decision.added_variant_id is None


def test_named_profile_can_explicitly_add_a_twelfth_proof():
    decision = select_adaptive_assembly(
        _request(
            11,
            maximum=12,
            candidates=(_proof(12, marginal=4.0),),
            profile_id="named-deep-technical-profile",
        )
    )

    assert decision.action is FillAction.ADD_APPROVED_PROOF
    assert decision.proof_units_after == 12
    assert decision.added_variant_id == "V12"


def test_layout_relaxation_is_attempted_before_a_good_addition():
    decision = select_adaptive_assembly(
        _request(
            10,
            candidates=(_proof(11, marginal=4.0),),
            layouts=LAYOUTS,
        )
    )

    assert decision.action is FillAction.TRY_LOOSER_LAYOUT
    assert decision.next_layout_id == "relaxed"
    assert decision.selected_variant_ids == tuple(f"V{i}" for i in range(1, 11))


def test_sparse_page_without_good_candidate_preserves_quality_and_audits_rejections():
    candidates = (
        _proof(11, criterion="criterion-1", marginal=9.0),
        _proof(12, admitted=False, marginal=9.0),
        _proof(13, kind=ProofKind.SKILL, marginal=9.0),
        _proof(14, marginal=0.0),
    )

    decision = select_adaptive_assembly(_request(10, candidates=candidates))

    assert decision.action is FillAction.ACCEPT_UNDERFILL
    assert decision.release_allowed
    assert decision.selected_variant_ids == tuple(f"V{i}" for i in range(1, 11))
    rejection_reasons = {
        item.variant_id: item.reasons for item in decision.candidate_audit
    }
    assert "no-distinct-funded-criterion" in rejection_reasons["V11"]
    assert "not-admitted" in rejection_reasons["V12"]
    assert "non-proof-filler-kind" in rejection_reasons["V13"]
    assert "non-positive-marginal-page-value" in rejection_reasons["V14"]


def test_in_band_page_is_no_regression_identity_operation():
    request = _request(
        10,
        candidates=(_proof(11, marginal=9.0),),
        geometry=_geometry(0.95),
        layouts=LAYOUTS,
    )

    decision = select_adaptive_assembly(request)

    assert decision.action is FillAction.ACCEPT
    assert decision.release_allowed
    assert decision.selected_variant_ids == tuple(item.variant_id for item in request.selected)
    assert decision.next_layout_id is None
    assert decision.added_variant_id is None
    assert decision.removed_variant_id is None


def test_overflow_tries_tighter_layout_before_removal():
    decision = select_adaptive_assembly(
        _request(10, geometry=_geometry(1.01), layouts=LAYOUTS)
    )

    assert decision.action is FillAction.TRY_TIGHTER_LAYOUT
    assert decision.next_layout_id == "compact"


def test_overflow_removes_only_unprotected_lowest_marginal_proof():
    selected = tuple(_proof(index) for index in range(1, 8)) + (
        _proof(8, protected=True, marginal=0.1, rank=10, line_cost=3.0),
        _proof(9, marginal=0.5, rank=8, line_cost=2.0),
        _proof(10, marginal=0.5, rank=9, line_cost=3.0),
    )
    request = _request(10, geometry=_geometry(1.01))
    request = AdaptiveAssemblyRequest(
        policy=request.policy,
        selected=selected,
        unselected_candidates=(),
        geometry=request.geometry,
        current_layout_id=request.current_layout_id,
        layouts=request.layouts,
    )

    decision = select_adaptive_assembly(request)

    assert decision.action is FillAction.REMOVE_LOWEST_VALUE_PROOF
    assert decision.removed_variant_id == "V10"
    assert "V8" in decision.selected_variant_ids
    assert decision.proof_units_after == 9


def test_overflow_never_removes_below_profile_minimum():
    decision = select_adaptive_assembly(_request(9, geometry=_geometry(1.01)))

    assert decision.action is FillAction.BLOCK
    assert decision.reason_code == "OVERFLOW_WITHOUT_BOUNDED_REPAIR"


def test_unsanctioned_or_irreversible_layouts_are_never_selected():
    layouts = (
        LayoutCandidate("loose-unsanctioned", -2, sanctioned=False),
        LayoutCandidate("loose-irreversible", -1, reversible=False),
        LayoutCandidate("standard", 0),
    )

    decision = select_adaptive_assembly(_request(10, layouts=layouts))

    assert decision.action is FillAction.ACCEPT_UNDERFILL
    assert decision.next_layout_id is None


def test_invalid_selected_proof_blocks_instead_of_being_repaired_around():
    request = _request(9)
    request = AdaptiveAssemblyRequest(
        policy=request.policy,
        selected=(_proof(1, admitted=False),) + request.selected[1:],
        unselected_candidates=(),
        geometry=request.geometry,
        current_layout_id=request.current_layout_id,
        layouts=request.layouts,
    )

    decision = select_adaptive_assembly(request)

    assert decision.action is FillAction.BLOCK
    assert decision.reason_code == "INVALID_SELECTED_PROOF"
