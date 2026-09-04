from __future__ import annotations

import run_app


def _resume(*bullets: str) -> str:
    return "\n".join(
        ["IBM | Product Strategy Intern | 2026"]
        + [f"• {bullet}" for bullet in bullets]
    )


def test_validation_counts_context_and_unknown_bullets_in_actual_total() -> None:
    result = run_app._validate_resume_constraints(
        _resume(
            "Built a prototype for researchers.",
            "Designed the evidence review workflow.",
            "Won a global innovation competition.",
            "Diagnosed a hidden adoption barrier.",
            "Expanded research coverage by interviewing new listener segments.",
            "Serving two business units, translated findings into recommendations.",
            "Coordinated weekly research readouts.",
            "Partnered with design on synthesis.",
            "Presented findings to senior leaders.",
            "Documented the final recommendation.",
        )
    )

    assert result["stats"] == {
        "total_bullets": 10,
        "action_count": 2,
        "impact_count": 1,
        "diagnostic_count": 1,
        "context_count": 2,
        "unknown_count": 4,
        "has_ownership_verb": True,
        "company_sections": {
            "IBM": {
                "count": 10,
                "openers": [
                    "built",
                    "designed",
                    "won",
                    "diagnosed",
                    "expanded",
                    "serving",
                    "coordinated",
                    "partnered",
                    "presented",
                    "documented",
                ],
                "categories": [
                    "action",
                    "action",
                    "impact-first",
                    "diagnostic",
                    "context",
                    "context",
                    "unknown",
                    "unknown",
                    "unknown",
                    "unknown",
                ],
                "diagnostic_streak": 1,
            }
        },
    }
    assert any("3/10 bullets" in issue for issue in result["issues"])
    assert any("2 context, 4 unknown" in issue for issue in result["issues"])


def test_validation_keeps_monotony_and_ownership_checks_conservative() -> None:
    result = run_app._validate_resume_constraints(
        _resume(
            "Diagnosed a workflow gap.",
            "Found a second unmet need.",
            "Mapped the unresolved dependency.",
            "Coordinated the follow-up.",
            "Expanded coverage by adding a new segment.",
        )
    )

    assert result["stats"]["total_bullets"] == 5
    assert result["stats"]["diagnostic_count"] == 3
    assert result["stats"]["context_count"] == 1
    assert result["stats"]["unknown_count"] == 1
    assert result["stats"]["has_ownership_verb"] is False
    assert any("[MONOTONY] IBM: 3 consecutive diagnostic" in issue for issue in result["issues"])
    assert any("[OWNERSHIP]" in issue for issue in result["issues"])


def test_led_scope_frame_is_context_but_plain_led_remains_action() -> None:
    assert (
        run_app._categorize_bullet_opener(
            "Led a platform from pilot to launch across three markets."
        )
        == "context"
    )
    assert run_app._categorize_bullet_opener("Led the incident response.") == "action"


def test_exact_reviewed_variant_uses_admitted_archetype_before_opener_guess() -> None:
    # "Re-scoped" is deliberately absent from the heuristic verb sets. Its
    # reviewed variant metadata, not a guess from prose, owns the archetype.
    assert (
        run_app._categorize_bullet_opener(
            "Re-scoped FlairX's Ceipal integration after its API blocked score "
            "write-back, automating job and candidate imports to eliminate ~80% "
            "of recruiters' duplicate entry while retaining FlairX's highest-volume "
            "account."
        )
        == "action"
    )
