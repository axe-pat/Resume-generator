import json
from dataclasses import dataclass

import pytest

from shared.resume_summary_selection import select_reviewed_summary


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    text: str
    use_case: str = "general product"
    status: str = "internal-status-must-not-reach-comparator"
    required_page_evidence: tuple[str, ...] = ()
    signal_tags: tuple[str, ...] = ()
    line_cost: int = 2


def _candidate(candidate_id: str) -> Candidate:
    return Candidate(candidate_id, f"Exact summary text for {candidate_id}.")


def _response(selected_id: str, *, regressions=()):
    return json.dumps(
        {
            "selected_id": selected_id,
            "rationale": "The selected candidate is materially stronger for this page.",
            "critical_regressions": list(regressions),
        }
    )


def test_selector_returns_exact_bank_object_and_audits_challenger_win():
    incumbent = _candidate("summary-a")
    challenger = _candidate("summary-b")
    prompts = []

    def compare(prompt):
        prompts.append(prompt)
        return _response("summary-b")

    result = select_reviewed_summary(
        (incumbent, challenger),
        strategy={"role_family": "pm", "top_signals": ["customer discovery"]},
        jd_text="Build prototypes from customer and usage evidence.",
        comparator=compare,
    )

    assert result.selected is challenger
    assert result.audit.selected_text == challenger.text
    assert result.audit.candidate_order == ("summary-a", "summary-b")
    assert result.audit.invalid_response_count == 0
    assert result.audit.rounds[0].resolution == "selector_select_candidate"
    assert result.audit.rounds[0].raw_response
    assert len(prompts) == 1
    assert "internal-status-must-not-reach-comparator" not in prompts[0]
    assert incumbent.text in prompts[0]
    assert challenger.text in prompts[0]


def test_complete_slate_is_decided_in_one_call():
    first = _candidate("summary-a")
    second = _candidate("summary-b")
    third = _candidate("summary-c")
    prompts = []

    def compare(prompt):
        prompts.append(prompt)
        return _response("summary-b")

    result = select_reviewed_summary(
        (first, second, third),
        strategy="role_family=pm",
        jd_text="A product role.",
        comparator=compare,
    )

    assert result.selected is second
    assert len(prompts) == 1
    assert len(result.audit.rounds) == 1
    assert result.audit.rounds[0].candidate_ids == (
        "summary-a",
        "summary-b",
        "summary-c",
    )
    assert all(candidate.text in prompts[0] for candidate in (first, second, third))


@pytest.mark.parametrize(
    "bad_response",
    (
        "```json\n{}\n```",
        {"selected_id": "summary-a", "rationale": "tied"},
        {
            "selected_id": "summary-b",
            "rationale": "better",
            "critical_regressions": ["identity funding"],
        },
        {
            "selected_id": "summary-b",
            "rationale": "better",
            "critical_regressions": [],
            "rewritten_summary": "invented",
        },
    ),
)
def test_invalid_or_contradictory_response_keeps_incumbent(bad_response):
    incumbent = _candidate("summary-a")
    result = select_reviewed_summary(
        (incumbent, _candidate("summary-b")),
        strategy={},
        jd_text="A product role.",
        comparator=lambda _prompt: bad_response,
    )

    assert result.selected is incumbent
    assert result.audit.invalid_response_count == 1
    assert result.audit.rounds[0].response_valid is False
    assert result.audit.rounds[0].resolution == "invalid_response_keep_incumbent"
    assert result.audit.rounds[0].fallback_reason


def test_callback_exception_keeps_incumbent_and_is_fully_audited():
    incumbent = _candidate("summary-a")

    def broken(_prompt):
        raise TimeoutError("comparison timed out")

    result = select_reviewed_summary(
        (incumbent, _candidate("summary-b")),
        strategy={},
        jd_text="A product role.",
        comparator=broken,
    )

    row = result.audit.rounds[0]
    assert result.selected is incumbent
    assert row.raw_response == "null"
    assert row.fallback_reason == "TimeoutError: comparison timed out"
    assert result.audit.to_dict()["rounds"][0]["selected_id"] == "summary-a"


def test_single_candidate_is_deterministic_and_does_not_call_comparator():
    incumbent = _candidate("summary-a")

    def must_not_run(_prompt):
        raise AssertionError("comparator should not run")

    result = select_reviewed_summary(
        (incumbent,),
        strategy={},
        jd_text="A product role.",
        comparator=must_not_run,
    )

    assert result.selected is incumbent
    assert result.audit.rounds == ()
    assert result.audit.invalid_response_count == 0


def test_explicit_incumbent_changes_only_starting_point_not_input_order_audit():
    first = _candidate("summary-a")
    second = _candidate("summary-b")
    result = select_reviewed_summary(
        (first, second),
        strategy={},
        jd_text="A product role.",
        comparator=lambda _prompt: _response("summary-b"),
        incumbent_candidate_id="summary-b",
    )

    assert result.selected is second
    assert result.audit.initial_incumbent_id == "summary-b"
    assert result.audit.candidate_order == ("summary-a", "summary-b")
    assert result.audit.rounds[0].candidate_ids == ("summary-a", "summary-b")


@pytest.mark.parametrize(
    "candidates, error",
    (
        ((), "at least one"),
        (
            (_candidate("summary-a"), _candidate("summary-a")),
            "duplicate candidate_id",
        ),
        (
            (
                _candidate("summary-a"),
                Candidate("summary-b", _candidate("summary-a").text),
            ),
            "duplicate exact summary text",
        ),
    ),
)
def test_invalid_candidate_slates_fail_closed(candidates, error):
    with pytest.raises(ValueError, match=error):
        select_reviewed_summary(
            candidates,
            strategy={},
            jd_text="A product role.",
            comparator=lambda _prompt: _response("summary-a"),
        )
