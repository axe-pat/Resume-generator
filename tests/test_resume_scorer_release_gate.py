from __future__ import annotations

from resume.freeform import freeform_runner


def _experience(counts=(3, 3, 3, 2)) -> str:
    companies = ("FLAIRX AI", "GOJEK", "HEVO DATA", "INTUIT")
    lines: list[str] = []
    for company, count in zip(companies, counts):
        lines.append(f"{company} | Title | Jan 2025 – Present | City, ST")
        lines.extend(f"• Distinct reviewed bullet {company} {index}." for index in range(1, count + 1))
    return "\n".join(lines)


def _score_data(experience: str, *, holistic: float = 8.7, verdict: str = "SEND") -> dict:
    bullets = []
    for block in freeform_runner.parse_experience_blocks(experience):
        for index, _ in enumerate(block["bullets"], 1):
            bullets.append(
                {
                    "company": block["key"],
                    "index": index,
                    "score": 8.5,
                    "note": "Specific mechanism and attributable result.",
                }
            )
    return {"holistic_score": holistic, "verdict": verdict, "bullets": bullets}


def test_scorer_prompt_uses_observed_bullet_count(monkeypatch, tmp_path):
    prompt_path = tmp_path / "scorer.txt"
    prompt_path.write_text("Score all {{BULLET_COUNT}} bullets: {{EXPERIENCE_SECTION}}")
    monkeypatch.setattr(freeform_runner, "SCORER_PROMPT", prompt_path)
    experience = _experience((2, 3, 2, 2))

    prompt = freeform_runner.load_scorer_prompt(experience, "JD")

    assert "Score all 9 bullets" in prompt
    assert "{{BULLET_COUNT}}" not in prompt


def test_valid_send_scorer_payload_passes_release_integrity():
    experience = _experience()

    errors, warnings = freeform_runner.validate_scorer_release_evidence(
        _score_data(experience), experience, require_send=True
    )

    assert errors == []
    assert warnings == []


def test_parse_failure_and_missing_bullet_evaluations_block_release():
    experience = _experience()
    payload = _score_data(experience)
    payload["parse_error"] = "invalid JSON"
    payload["bullets"] = payload["bullets"][:-1]

    errors, _ = freeform_runner.validate_scorer_release_evidence(
        payload, experience, require_send=True
    )

    assert any("parse failed" in error for error in errors)
    assert any("expected 11" in error for error in errors)


def test_revise_holistic_is_advisory_when_every_bullet_clears_vetoes():
    experience = _experience()

    errors, warnings = freeform_runner.validate_scorer_release_evidence(
        _score_data(experience, holistic=8.4, verdict="REVISE"),
        experience,
        require_send=True,
    )

    assert errors == []
    assert any("aggregate scorer verdict is advisory" in warning for warning in warnings)


def test_scorer_company_index_sequence_must_match_selected_output():
    experience = _experience()
    payload = _score_data(experience)
    payload["bullets"][0]["company"] = "GOJEK"

    errors, _ = freeform_runner.validate_scorer_release_evidence(
        payload, experience, require_send=True
    )

    assert any("company/index keys" in error for error in errors)


def test_page_global_scorer_indices_are_normalized_when_order_is_unambiguous():
    experience = _experience((2, 2, 2, 2))
    payload = _score_data(experience)
    for position, item in enumerate(payload["bullets"], 1):
        item["index"] = position

    normalized, warnings = freeform_runner.normalize_scorer_bullet_indices(
        payload,
        experience,
    )
    errors, validation_warnings = freeform_runner.validate_scorer_release_evidence(
        payload,
        experience,
        require_send=True,
    )

    assert [item["index"] for item in normalized["bullets"]] == [1, 2] * 4
    assert warnings
    assert errors == []
    assert validation_warnings == warnings


def test_send_holistic_score_cannot_hide_a_weak_bullet():
    experience = _experience()
    payload = _score_data(experience, holistic=8.8, verdict="SEND")
    payload["bullets"][3]["score"] = 7.0
    payload["bullets"][3]["failure_mode"] = "WEAK_MECHANISM"

    errors, _ = freeform_runner.validate_scorer_release_evidence(
        payload,
        experience,
        require_send=True,
    )

    assert any("below 8.0" in error for error in errors)
    assert any("explicit bullet failure" in error for error in errors)
