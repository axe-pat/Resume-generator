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
    assert payload["repair_scope"] is None


def test_targeted_scorer_retry_scope_reopens_only_failed_slots():
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    sections = runner.extract_sections(_raw_selection(override, VALID_SELECTION))
    sections["selection_notes"] = runner.canonicalize_v2_selection_notes(
        sections,
        override,
    )
    scores = _scorer(VALID_SELECTION)
    scores["holistic_score"] = 8.0
    scores["verdict"] = "REVISE"
    scores["bullets"][4]["score"] = 7.0
    scores["bullets"][4]["failure_mode"] = "READABILITY_FAILURE"
    scores["bullets"][9]["score"] = 7.0
    scores["bullets"][9]["failure_mode"] = "WEAK_MECHANISM"
    validation = runner.validate_v2_sections(sections, override, scores)

    scope = runner._v2_targeted_scorer_retry_scope(validation, scores)

    assert scope is not None
    assert [item["variant_id"] for item in scope["must_replace"]] == [
        "G-SUPPLY-canonical-operating-model",
        "O-SAFE-ACTION-flag-suggest-stop",
    ]
    assert "G-PRICING-canonical-closed-loop" in scope["must_retain_variant_ids"]
    assert scope["must_retain_summary_id"] == "summary/product/general-scaled-evidence"
    assert scope["must_retain_fluo_variant_id"] == "FL-INSTITUTIONAL-amazon-inline-prearrival"


def test_targeted_retry_enforcement_rejects_collateral_changes():
    initial = _validation(ids=("keep", "replace"), summary="summary-a", fluo="fluo-a")
    scope = {
        "must_retain_variant_ids": ["keep"],
        "must_replace": [{"variant_id": "replace"}],
        "must_retain_summary_id": "summary-a",
        "must_retain_fluo_variant_id": "fluo-a",
    }

    collateral = runner._enforce_v2_targeted_retry_scope(
        _validation(ids=("other", "replace"), summary="summary-b", fluo="fluo-b"),
        scope,
    )

    joined = " | ".join(collateral.errors)
    assert "discarded passing" in joined
    assert "repeated variants assigned for replacement" in joined
    assert "changed summary" in joined
    assert "changed Fluo" in joined


def test_targeted_comparison_keeps_tie_incumbent_and_accepts_pareto_winner():
    override = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    initial_sections = runner.extract_sections(_raw_selection(override, VALID_SELECTION))
    initial_sections["selection_notes"] = runner.canonicalize_v2_selection_notes(
        initial_sections,
        override,
    )
    initial = runner.validate_v2_sections(initial_sections, override, _scorer(VALID_SELECTION))

    challenger_selection = dict(VALID_SELECTION)
    challenger_selection["GOJEK"] = (
        "G-PRICING-canonical-closed-loop",
        "G-LATENCY-studyfetch-readable-tradeoff",
        "G-SUPPLY-C2-contract-design",
    )
    challenger_selection["OPTUM"] = (
        "O-AFFORDABILITY-prototype-clinical-approval",
    )
    challenger_sections = runner.extract_sections(
        _raw_selection(override, challenger_selection)
    )
    challenger_sections["selection_notes"] = runner.canonicalize_v2_selection_notes(
        challenger_sections,
        override,
    )
    challenger = runner.validate_v2_sections(
        challenger_sections,
        override,
        _scorer(challenger_selection),
    )
    scope = {
        "must_replace": [
            {
                "company": "GOJEK",
                "index": 3,
                "variant_id": "G-SUPPLY-canonical-operating-model",
                "score": 7.0,
                "failure_mode": "READABILITY_FAILURE",
                "note": "too many clauses",
            },
            {
                "company": "OPTUM",
                "index": 1,
                "variant_id": "O-SAFE-ACTION-flag-suggest-stop",
                "score": 7.0,
                "failure_mode": "WEAK_MECHANISM",
                "note": "thin mechanism",
            },
        ]
    }
    pairs = runner._v2_targeted_retry_pairs(initial, challenger, scope)

    def critical():
        return {name: True for name in runner._V2_PAIRWISE_CRITICAL_KEYS}

    def ranks(*values):
        return dict(zip(runner._V2_PAIRWISE_RANK_KEYS, values))

    result = {
        "comparisons": [
            {
                "company": "GOJEK",
                "index": 3,
                "incumbent_variant_id": "G-SUPPLY-canonical-operating-model",
                "challenger_variant_id": "G-SUPPLY-C2-contract-design",
                "incumbent_critical": critical(),
                "challenger_critical": critical(),
                "incumbent_rank": ranks(4, 4, 4, 4, 4),
                "challenger_rank": ranks(4, 3, 4, 4, 4),
                "rationale": "The challenger is shorter but loses operating-model value.",
            },
            {
                "company": "OPTUM",
                "index": 1,
                "incumbent_variant_id": "O-SAFE-ACTION-flag-suggest-stop",
                "challenger_variant_id": "O-AFFORDABILITY-prototype-clinical-approval",
                "incumbent_critical": critical(),
                "challenger_critical": critical(),
                "incumbent_rank": ranks(3, 3, 3, 3, 3),
                "challenger_rank": ranks(4, 3, 3, 3, 3),
                "rationale": "The challenger proves the JD criterion more directly.",
            },
        ],
        "final_page_checks": {
            name: True for name in runner._V2_PAIRWISE_PAGE_KEYS
        },
        "page_rationale": "The mixed winner page improves one slot without regression.",
    }

    decisions, errors = runner._decide_v2_targeted_comparison(result, pairs)
    final_sections = runner._apply_v2_targeted_comparison_decisions(
        initial_sections=initial_sections,
        challenger_sections=challenger_sections,
        initial=initial,
        challenger=challenger,
        decisions=decisions,
        override=override,
    )

    assert errors == []
    assert decisions == {("GOJEK", 3): "incumbent", ("OPTUM", 1): "challenger"}
    assert "Led Gojek's fleet integration platform" in final_sections["experience_section"]
    assert "Prototyped an ML-based affordability engine" in final_sections["experience_section"]


def test_targeted_comparison_fails_closed_on_page_regression():
    pair = {
        "company": "GOJEK",
        "index": 1,
        "incumbent_variant_id": "old",
        "challenger_variant_id": "new",
    }
    critical = {name: True for name in runner._V2_PAIRWISE_CRITICAL_KEYS}
    rank = {name: 3 for name in runner._V2_PAIRWISE_RANK_KEYS}
    result = {
        "comparisons": [
            {
                **pair,
                "incumbent_critical": critical,
                "challenger_critical": critical,
                "incumbent_rank": rank,
                "challenger_rank": {**rank, "criterion_strength": 4},
                "rationale": "stronger",
            }
        ],
        "final_page_checks": {
            **{name: True for name in runner._V2_PAIRWISE_PAGE_KEYS},
            "nonduplication": False,
        },
    }

    _, errors = runner._decide_v2_targeted_comparison(result, [pair])

    assert any("final page failed" in error for error in errors)


def test_targeted_comparison_keeps_incumbent_on_material_tradeoff():
    pair = {
        "company": "INTUIT",
        "index": 2,
        "incumbent_variant_id": "old",
        "challenger_variant_id": "new",
    }
    critical = {name: True for name in runner._V2_PAIRWISE_CRITICAL_KEYS}
    incumbent_rank = {name: 3 for name in runner._V2_PAIRWISE_RANK_KEYS}
    challenger_rank = {**incumbent_rank, "criterion_strength": 4, "outcome_quality": 2}
    result = {
        "comparisons": [
            {
                **pair,
                "incumbent_critical": critical,
                "challenger_critical": critical,
                "incumbent_rank": incumbent_rank,
                "challenger_rank": challenger_rank,
                "rationale": "One criterion improves but outcome quality falls.",
            }
        ],
        "final_page_checks": {
            name: True for name in runner._V2_PAIRWISE_PAGE_KEYS
        },
    }

    decisions, errors = runner._decide_v2_targeted_comparison(result, [pair])

    assert decisions == {("INTUIT", 2): "incumbent"}
    assert errors == ["targeted retry produced no material improvement"]


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
