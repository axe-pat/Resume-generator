import pytest

from shared.resume_fill import (
    AdaptiveFillPolicy,
    FillAction,
    PageFillObservation,
    PageFillReleaseAssessment,
    PageFillReleaseStatus,
    assess_optional_skill_row_release,
    decide_adaptive_fill,
)


POLICY = AdaptiveFillPolicy(9, 10, 11)


def test_underfill_tries_layout_before_adding_content():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=1,
            usable_fill_ratio=0.80,
            proof_units=10,
            looser_layout_available=True,
            approved_addition_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.TRY_LOOSER_LAYOUT


def test_underfill_adds_only_an_already_approved_proof():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=1,
            usable_fill_ratio=0.80,
            proof_units=10,
            approved_addition_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.ADD_APPROVED_PROOF


def test_underfill_never_backfills_weak_evidence():
    decision = decide_adaptive_fill(
        PageFillObservation(page_count=1, usable_fill_ratio=0.80, proof_units=10),
        POLICY,
    )

    assert decision.action is FillAction.ACCEPT_UNDERFILL


def test_maximum_proof_count_cannot_be_exceeded_to_fill_space():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=1,
            usable_fill_ratio=0.80,
            proof_units=11,
            approved_addition_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.ACCEPT_UNDERFILL


def test_overflow_tries_compact_layout_before_removing_content():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=2,
            usable_fill_ratio=1.10,
            proof_units=10,
            tighter_layout_available=True,
            removable_lowest_value_proof_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.TRY_TIGHTER_LAYOUT


def test_overflow_can_remove_only_a_pre_ranked_unprotected_proof():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=2,
            usable_fill_ratio=1.10,
            proof_units=10,
            removable_lowest_value_proof_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.REMOVE_LOWEST_VALUE_PROOF


def test_overflow_does_not_remove_below_quality_floor():
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=2,
            usable_fill_ratio=1.10,
            proof_units=9,
            removable_lowest_value_proof_available=True,
        ),
        POLICY,
    )

    assert decision.action is FillAction.BLOCK


def test_profile_can_explicitly_allow_more_than_eleven_proof_units():
    policy = AdaptiveFillPolicy(9, 10, 12)
    decision = decide_adaptive_fill(
        PageFillObservation(
            page_count=1,
            usable_fill_ratio=0.82,
            proof_units=11,
            approved_addition_available=True,
        ),
        policy,
    )

    assert decision.action is FillAction.ADD_APPROVED_PROOF


def test_inside_fill_band_is_accepted_without_content_mutation():
    decision = decide_adaptive_fill(
        PageFillObservation(page_count=1, usable_fill_ratio=0.95, proof_units=10),
        POLICY,
    )

    assert decision.action is FillAction.ACCEPT


def test_distinct_sixth_skill_row_requires_portable_rendered_headroom():
    acceptable = PageFillReleaseAssessment(
        status=PageFillReleaseStatus.READY,
        observed_fill_ratio=0.96,
        usable_bottom_whitespace_pt=22.0,
        minimum_release_fill_ratio=0.93,
    )
    dense = PageFillReleaseAssessment(
        status=PageFillReleaseStatus.READY,
        observed_fill_ratio=0.975,
        usable_bottom_whitespace_pt=17.0,
        minimum_release_fill_ratio=0.93,
    )

    assert assess_optional_skill_row_release(
        acceptable,
        distinct_signal=True,
    ).allowed
    assert not assess_optional_skill_row_release(
        acceptable,
        distinct_signal=False,
    ).allowed
    assert not assess_optional_skill_row_release(
        dense,
        distinct_signal=True,
    ).allowed


@pytest.mark.parametrize(
    "policy",
    [
        (0, 10, 11),
        (10, 9, 11),
        (9, 12, 11),
    ],
)
def test_invalid_proof_bounds_fail_closed(policy):
    with pytest.raises(ValueError):
        AdaptiveFillPolicy(*policy)
