import json
from pathlib import Path
from types import SimpleNamespace

from resume.freeform import freeform_runner as runner
from shared.resume_profiles import PROFESSIONAL_COMPANY_ORDER, skills_section_heading
from shared.resume_v2_prompt import (
    build_pass1_prompt_override,
    company_headers_for_profile,
    skill_value_candidates_for_profile,
)
from shared.resume_v2_validation import V2SectionValidation


PM_STRATEGY = {
    "role_family": "pm",
    "archetype": "generalist",
    "top_signals": ["product judgment", "customer evidence"],
    "gaps": [],
}

VALID_SELECTION = {
    "FLAIRX AI": (
        "F-ENTERPRISE-amazon-deal-impact",
        "f-avatar-low-spec-antifraud-tradeoff",
    ),
    "GOJEK": (
        "G-PRICING-canonical-closed-loop",
        "G-LATENCY-studyfetch-readable-tradeoff",
        "G-SUPPLY-canonical-operating-model",
    ),
    "HEVO DATA": (
        "H-BATCHSHIFT-canonical-trial-trigger",
        "H-MONITORING-canonical-ai-boundary",
    ),
    "INTUIT": (
        "I-BILLING-canonical-renewal-integrity",
        "I-INCIDENT-canonical-parallel-recovery",
    ),
    "OPTUM": ("O-SAFE-ACTION-flag-suggest-stop",),
}


def _validation(ids=("a", "b"), *, summary="summary-a", fluo="fluo-a", errors=()):
    selected = tuple(
        SimpleNamespace(reviewed=SimpleNamespace(variant_id=variant_id))
        for variant_id in ids
    )
    return V2SectionValidation(
        errors=tuple(errors),
        warnings=(),
        selected=selected,
        summary=SimpleNamespace(candidate_id=summary) if summary else None,
        fluo_variant=SimpleNamespace(variant_id=fluo) if fluo else None,
        document=None,
    )


def test_retry_prompt_preserves_bank_and_carries_machine_readable_feedback():
    validation = _validation()
    signature = runner._v2_selection_signature(validation)

    prompt = runner._build_v2_selection_retry_prompt(
        "ORIGINAL CLOSED REVIEWED BANK",
        validation_errors=["story family repeated on one page: F-ENTERPRISE"],
        scorer_errors=["v2 release requires scorer verdict SEND"],
        previous_signature=signature,
        score_data={
            "holistic_score": 8.1,
            "verdict": "REVISE",
            "bullets": [
                {
                    "company": "FLAIRX AI",
                    "index": 1,
                    "score": 6.5,
                    "failure_mode": "JD_FIT",
                    "note": "weak fit",
                }
            ],
        },
    )

    assert prompt.startswith("ORIGINAL CLOSED REVIEWED BANK\n\n")
    assert prompt.count(runner._V2_RETRY_START) == 1
    assert prompt.count(runner._V2_RETRY_END) == 1
    assert "never rewrite, merge, shorten, expand or invent content" in prompt
    encoded = prompt.split("RETRY_FEEDBACK_JSON\n", 1)[1].split(
        f"\n{runner._V2_RETRY_END}", 1
    )[0]
    payload = json.loads(encoded)
    assert payload["maximum_retry_attempts"] == 1
    assert payload["previous_selection"] == signature
    assert payload["forbidden_selection"] == signature
    assert {item["source"] for item in payload["blockers"]} == {
        "exact-selection",
        "scorer-release",
    }
    assert payload["scorer_diagnostics"]["bullets"][0]["failure_mode"] == "JD_FIT"


def test_integrity_retry_reports_observed_ids_without_forbidding_unparsed_content():
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    raw = _raw_selection(override, VALID_SELECTION)
    signature = runner._v2_observed_raw_signature(raw, override)
    prompt = runner._build_v2_selection_retry_prompt(
        "ORIGINAL CLOSED REVIEWED BANK",
        integrity_blockers=(
            {"code": "SECTION_MULTIPLE", "message": "SECTION 0 appears twice"},
        ),
        validation_errors=(),
        scorer_errors=(),
        previous_signature=signature,
        score_data={},
        forbid_previous_combination=False,
    )
    encoded = prompt.split("RETRY_FEEDBACK_JSON\n", 1)[1].split(
        f"\n{runner._V2_RETRY_END}", 1
    )[0]
    payload = json.loads(encoded)

    assert payload["blockers"] == [
        {
            "source": "section-integrity",
            "code": "SECTION_MULTIPLE",
            "message": "SECTION 0 appears twice",
        }
    ]
    assert payload["previous_selection"]["experience_variant_ids"]
    assert payload["forbidden_selection"] is None
    assert "may be retained while repairing the output structure" in prompt


def test_forbidden_retry_combination_is_a_hard_validation_error():
    initial = _validation()
    previous = runner._v2_selection_signature(initial)

    repeated = runner._reject_forbidden_v2_retry_combination(initial, previous)
    changed = runner._reject_forbidden_v2_retry_combination(
        _validation(ids=("a", "c")),
        previous,
    )

    assert "repeated the forbidden prior selection" in " ".join(repeated.errors)
    assert changed.errors == ()


def _raw_selection(override, selection):
    variants = {variant.variant_id: variant for variant in override.bank.variants}
    summary = next(
        item
        for item in override.eligible_summaries
        if item.candidate_id == "summary/product/general-scaled-evidence"
    )
    headers = company_headers_for_profile(override.profile)
    experience = []
    for company in PROFESSIONAL_COMPANY_ORDER:
        experience.append(headers[company])
        experience.extend(f"• {variants[item].text}" for item in selection[company])

    fluo = variants["FL-INSTITUTIONAL-amazon-inline-prearrival"]
    skill_values = skill_value_candidates_for_profile(override.profile, override.bank)
    labels = override.profile.skill_rows
    skills = [skills_section_heading(labels)]
    for label in labels:
        value = (
            f"Fluo, {fluo.text}"
            if label == override.profile.fluo.label
            else skill_values[label][0]
        )
        skills.append(f"● {label}: {value}")

    return "\n\n".join(
        (
            f"SECTION 0 — PROFESSIONAL SUMMARY\n{summary.text}",
            "SECTION 1 — TOP 3 JD SIGNALS\nProduct judgment\nCustomer evidence\nExecution",
            "SECTION 2 — SELECTION NOTES\nmodel bookkeeping",
            "SECTION 3 — FULL EXPERIENCE SECTION\n" + "\n".join(experience),
            "SECTION 4 — SKILLS\n" + "\n".join(skills),
        )
    )


def _scorer(selection):
    bullets = []
    for company in PROFESSIONAL_COMPANY_ORDER:
        bullets.extend(
            {
                "company": company,
                "index": index,
                "score": 9.0,
                "failure_mode": "NONE",
                "note": "strong exact selection",
            }
            for index, _ in enumerate(selection[company], 1)
        )
    return {"holistic_score": 9.0, "verdict": "SEND", "bullets": bullets}


def test_run_single_reselects_once_from_same_bank_and_releases_only_valid_result(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "off")
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    invalid = dict(VALID_SELECTION)
    invalid["FLAIRX AI"] = (
        "F-ENTERPRISE-amazon-deal-impact",
        "F-ENTERPRISE-studyfetch-design-delivery",
    )
    responses = iter((_raw_selection(override, invalid), _raw_selection(override, VALID_SELECTION)))
    selection_calls = []

    def select(prompt, _model, label, **_kwargs):
        selection_calls.append((label, prompt))
        return next(responses)

    monkeypatch.setattr(runner, "call_api", select)
    scorer_results = iter((_scorer(invalid), _scorer(VALID_SELECTION)))
    monkeypatch.setattr(runner, "run_scorer", lambda *_args, **_kwargs: next(scorer_results))
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda *_args, **_kwargs: [{"name": "fixture", "status": "PASS", "detail": "ok"}],
    )
    monkeypatch.setattr(
        runner,
        "lint_assembled_resume",
        lambda *_args, **_kwargs: SimpleNamespace(issues=()),
    )
    jd = tmp_path / "jd.txt"
    jd.write_text("Product manager role", encoding="utf-8")
    out = tmp_path / "runs"

    ok = runner.run_single(
        jd_path=jd,
        model="test-model",
        out_dir=out,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=(PM_STRATEGY, "strategy"),
        run_trim=False,
    )

    assert ok is True
    assert [label for label, _ in selection_calls] == [
        "Pass 1: Select",
        "Pass 1b: Bounded re-select",
    ]
    retry_prompt = selection_calls[1][1]
    assert "F-ENTERPRISE-amazon-deal-impact" in retry_prompt
    assert "F-ENTERPRISE-studyfetch-design-delivery" in retry_prompt
    saved = next(out.glob("*.txt")).read_text(encoding="utf-8")
    assert "story family repeated on one page" in saved
    assert variants_text(override, "f-avatar-low-spec-antifraud-tradeoff") in saved


def variants_text(override, variant_id):
    return next(item.text for item in override.bank.variants if item.variant_id == variant_id)


def test_run_single_never_runs_a_second_retry_and_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "off")
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    invalid = dict(VALID_SELECTION)
    invalid["FLAIRX AI"] = (
        "F-ENTERPRISE-amazon-deal-impact",
        "F-ENTERPRISE-studyfetch-design-delivery",
    )
    raw = _raw_selection(override, invalid)
    selection_calls = []
    monkeypatch.setattr(
        runner,
        "call_api",
        lambda prompt, _model, label, **_kwargs: selection_calls.append(label) or raw,
    )
    monkeypatch.setattr(runner, "run_scorer", lambda *_args, **_kwargs: _scorer(invalid))
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda *_args, **_kwargs: [{"name": "fixture", "status": "PASS", "detail": "ok"}],
    )
    jd = tmp_path / "jd.txt"
    jd.write_text("Product manager role", encoding="utf-8")
    out = tmp_path / "runs"

    ok = runner.run_single(
        jd_path=jd,
        model="test-model",
        out_dir=out,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=(PM_STRATEGY, "strategy"),
        run_trim=False,
    )

    assert ok is False
    assert selection_calls == ["Pass 1: Select", "Pass 1b: Bounded re-select"]
    assert not out.exists()


def test_initial_section_integrity_failure_gets_the_single_retry(monkeypatch, tmp_path):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "off")
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    valid_raw = _raw_selection(override, VALID_SELECTION)
    duplicate_section_zero = valid_raw.split("\n\n", 1)[0] + "\n\n" + valid_raw
    responses = iter((duplicate_section_zero, valid_raw))
    selection_calls = []

    def select(prompt, _model, label, **_kwargs):
        selection_calls.append((label, prompt))
        return next(responses)

    monkeypatch.setattr(runner, "call_api", select)
    scorer_calls = []
    monkeypatch.setattr(
        runner,
        "run_scorer",
        lambda *_args, **_kwargs: scorer_calls.append(1) or _scorer(VALID_SELECTION),
    )
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda *_args, **_kwargs: [{"name": "fixture", "status": "PASS", "detail": "ok"}],
    )
    monkeypatch.setattr(
        runner,
        "lint_assembled_resume",
        lambda *_args, **_kwargs: SimpleNamespace(issues=()),
    )
    jd = tmp_path / "jd.txt"
    jd.write_text("Product manager role", encoding="utf-8")
    out = tmp_path / "runs"

    ok = runner.run_single(
        jd_path=jd,
        model="test-model",
        out_dir=out,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=(PM_STRATEGY, "strategy"),
        run_trim=False,
    )

    assert ok is True
    assert [label for label, _ in selection_calls] == [
        "Pass 1: Select",
        "Pass 1b: Bounded re-select",
    ]
    assert len(scorer_calls) == 1
    retry_prompt = selection_calls[1][1]
    payload = json.loads(
        retry_prompt.split("RETRY_FEEDBACK_JSON\n", 1)[1].split(
            f"\n{runner._V2_RETRY_END}", 1
        )[0]
    )
    assert payload["blockers"][0]["source"] == "section-integrity"
    assert payload["forbidden_selection"] is None


def test_integrity_retry_consumes_the_only_retry_before_semantic_validation(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "off")
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    valid_raw = _raw_selection(override, VALID_SELECTION)
    duplicate_section_zero = valid_raw.split("\n\n", 1)[0] + "\n\n" + valid_raw
    invalid = dict(VALID_SELECTION)
    invalid["FLAIRX AI"] = (
        "F-ENTERPRISE-amazon-deal-impact",
        "F-ENTERPRISE-studyfetch-design-delivery",
    )
    responses = iter((duplicate_section_zero, _raw_selection(override, invalid)))
    selection_calls = []
    monkeypatch.setattr(
        runner,
        "call_api",
        lambda prompt, _model, label, **_kwargs: selection_calls.append(label)
        or next(responses),
    )
    monkeypatch.setattr(runner, "run_scorer", lambda *_args, **_kwargs: _scorer(invalid))
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda *_args, **_kwargs: [{"name": "fixture", "status": "PASS", "detail": "ok"}],
    )
    jd = tmp_path / "jd.txt"
    jd.write_text("Product manager role", encoding="utf-8")
    out = tmp_path / "runs"

    ok = runner.run_single(
        jd_path=jd,
        model="test-model",
        out_dir=out,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=(PM_STRATEGY, "strategy"),
        run_trim=False,
    )

    assert ok is False
    assert selection_calls == ["Pass 1: Select", "Pass 1b: Bounded re-select"]
    assert not out.exists()


def test_integrity_retry_that_is_still_malformed_fails_before_scorer(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "off")
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    valid_raw = _raw_selection(override, VALID_SELECTION)
    malformed = valid_raw.split("\n\n", 1)[0] + "\n\n" + valid_raw
    selection_calls = []
    monkeypatch.setattr(
        runner,
        "call_api",
        lambda prompt, _model, label, **_kwargs: selection_calls.append(label) or malformed,
    )
    monkeypatch.setattr(
        runner,
        "run_scorer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("malformed retry must not reach scorer")
        ),
    )
    jd = tmp_path / "jd.txt"
    jd.write_text("Product manager role", encoding="utf-8")

    ok = runner.run_single(
        jd_path=jd,
        model="test-model",
        out_dir=tmp_path / "runs",
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=(PM_STRATEGY, "strategy"),
        run_trim=False,
    )

    assert ok is False
    assert selection_calls == ["Pass 1: Select", "Pass 1b: Bounded re-select"]
