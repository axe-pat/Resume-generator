import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_app
from resume.freeform import freeform_runner as runner
from shared.resume_profiles import BulletBudgetDecision, get_profile


VALID_MODEL_OUTPUT = """\
SECTION 0 — PROFESSIONAL SUMMARY
Product manager and engineer who turns customer evidence into shipped products.

SECTION 1 — TOP 3 JD SIGNALS
1. Customer discovery

SECTION 2 — VARIANT SELECTION NOTES
Selected admitted variants.

SECTION 3 — FULL EXPERIENCE SECTION
FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA
• Built a customer-led product workflow and shipped it with engineering.

SECTION 4 — SKILLS & INTERESTS
SKILLS & INTERESTS
● Product Focus: Customer Discovery
● Tools: SQL
● Community: Education volunteer
● Venture Product: Fluo - Built a verified student workflow.
● Interests: Hiking
"""


def _warning_checks(_sections, track="pm"):
    return [
        {
            "name": "advisory",
            "status": "WARN",
            "detail": f"warning for {track}",
        }
    ]


def _run_minimal(monkeypatch, tmp_path: Path, *, make_docx: bool = False) -> tuple[bool, Path]:
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    out_dir = tmp_path / "runs"
    monkeypatch.setattr(runner, "call_api", lambda *_args, **_kwargs: VALID_MODEL_OUTPUT)
    monkeypatch.setattr(runner, "run_quality_checks", _warning_checks)
    ok = runner.run_single(
        jd_path=jd_path,
        model="test-model",
        out_dir=out_dir,
        make_docx=make_docx,
        run_strategy=False,
        run_rewrite=False,
        run_score=False,
        run_fix=False,
        run_trim=False,
    )
    return ok, out_dir


def test_pass1_section_integrity_blocks_before_legacy_parser(monkeypatch, tmp_path):
    malformed = VALID_MODEL_OUTPUT.replace(
        "SECTION 0 — PROFESSIONAL SUMMARY\n",
        "SECTION 0 — PROFESSIONAL SUMMARY\nDraft summary.\n\n"
        "SECTION 0 — PROFESSIONAL SUMMARY\n",
        1,
    )
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    out_dir = tmp_path / "runs"
    monkeypatch.setattr(runner, "call_api", lambda *_args, **_kwargs: malformed)

    def parser_must_not_run(_response):
        raise AssertionError("extract_sections ran before the integrity gate")

    monkeypatch.setattr(runner, "extract_sections", parser_must_not_run)

    ok = runner.run_single(
        jd_path=jd_path,
        model="test-model",
        out_dir=out_dir,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=False,
        run_fix=False,
        run_trim=False,
    )

    assert ok is False
    assert not out_dir.exists()


def test_qc_warnings_are_advisory_but_failures_block_release():
    warning = [{"name": "warning", "status": "WARN", "detail": "review"}]
    failure = [{"name": "failure", "status": "FAIL", "detail": "block"}]

    assert runner.print_qc(warning) is True
    assert runner.print_qc(failure) is False


def test_top_level_shadow_runs_and_persists_summary_selection_without_changing_prompt(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "shadow")
    # Even an apply request cannot change an artifact while the top-level
    # runtime remains shadow.
    monkeypatch.setenv("RESUME_V2_SUMMARY_SELECTOR", "apply")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Associate product manager for a consumer marketplace", encoding="utf-8")
    out_dir = tmp_path / "runs"
    pass1_prompts = []
    comparison_calls = 0

    def api(prompt, _model, label):
        nonlocal comparison_calls
        if "Summary compare" in label:
            comparison_calls += 1
            return json.dumps(
                {
                    "verdict": "keep_incumbent",
                    "rationale": "The incumbent retains the broader funded evidence.",
                    "critical_regressions": [],
                }
            )
        pass1_prompts.append(prompt)
        return VALID_MODEL_OUTPUT

    monkeypatch.setattr(runner, "call_api", api)
    monkeypatch.setattr(runner, "run_quality_checks", _warning_checks)

    ok = runner.run_single(
        jd_path=jd_path,
        model="test-model",
        out_dir=out_dir,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=False,
        run_fix=False,
        pre_strategy=(
            {
                "role_family": "pm",
                "archetype": "generalist",
                "top_signals": ["marketplace", "customer discovery"],
            },
            "",
        ),
        run_trim=False,
    )

    assert ok is True
    assert comparison_calls >= 1
    assert len(pass1_prompts) == 1
    assert "<<< BEGIN RESUME V2 AUTHORITATIVE PASS-1 OVERRIDE >>>" not in pass1_prompts[0]
    audit_path = out_dir / "v2_audits" / "jd_summary_selection.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["top_level_runtime"] == "shadow"
    assert audit["requested_selector_mode"] == "apply"
    assert audit["effective_selector_mode"] == "shadow"
    assert audit["artifact_changed"] is False


def test_hard_qc_failure_releases_no_resume_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda _sections, track="pm": [
            {"name": "hard failure", "status": "FAIL", "detail": track}
        ],
    )
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    out_dir = tmp_path / "runs"
    monkeypatch.setattr(runner, "call_api", lambda *_args, **_kwargs: VALID_MODEL_OUTPUT)

    ok = runner.run_single(
        jd_path=jd_path,
        model="test-model",
        out_dir=out_dir,
        make_docx=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=False,
        run_fix=False,
        run_trim=False,
    )

    assert ok is False
    assert not out_dir.exists()


def test_saved_text_and_docx_receive_identical_experience(monkeypatch, tmp_path):
    captured = {}

    def expansion_must_not_run(*_args, **_kwargs):
        raise AssertionError("post-QC expansion must not run")

    def capture_docx(sections, _jd_path, _out_dir, _docx_out_dir, **_kwargs):
        captured["experience"] = sections["experience_section"]
        docx_path = tmp_path / "resume.docx"
        docx_path.write_bytes(b"docx")
        return docx_path

    def capture_release(_docx_path, *, expected_fragments):
        captured["expected_fragments"] = tuple(expected_fragments)
        return SimpleNamespace(pdf=SimpleNamespace(path=tmp_path / "resume.pdf"))

    monkeypatch.setattr(runner, "run_expansion_pass", expansion_must_not_run)
    monkeypatch.setattr(runner, "generate_docx", capture_docx)
    monkeypatch.setattr(runner, "render_resume_artifact", capture_release)

    ok, out_dir = _run_minimal(monkeypatch, tmp_path, make_docx=True)

    assert ok is True
    saved = next(out_dir.glob("*.txt")).read_text(encoding="utf-8")
    assert captured["experience"] in saved
    assert (
        "Product manager and engineer who turns customer evidence into shipped products."
        in captured["expected_fragments"]
    )
    assert (
        "Built a customer-led product workflow and shipped it with engineering."
        in captured["expected_fragments"]
    )
    assert "Interests: Hiking" in captured["expected_fragments"]


def test_docx_failure_makes_run_single_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "generate_docx", lambda *_args, **_kwargs: None)

    ok, _out_dir = _run_minimal(monkeypatch, tmp_path, make_docx=True)

    assert ok is False


def test_generate_docx_never_drops_interests_to_repair_overflow(monkeypatch, tmp_path):
    script = tmp_path / "resume_docx.js"
    script.write_text("// fixture", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    captured = {}
    layout_calls = 0

    def overflow_then_fit(*_args, **_kwargs):
        nonlocal layout_calls
        layout_calls += 1
        layout = {
            "name": "T3",
            "line": 200,
            "sec_before": 140,
            "sec_after": 70,
            "margin_bot": 648,
        }
        return (layout, 1000, 900) if layout_calls == 1 else (layout, 800, 900)

    def capture_payload(command, **_kwargs):
        captured.update(json.loads(Path(command[-1]).read_text(encoding="utf-8")))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(runner, "DOCX_SCRIPT", script)
    monkeypatch.setattr(runner, "_choose_layout_tier", overflow_then_fit)
    monkeypatch.setattr(runner.subprocess, "run", capture_payload)
    monkeypatch.setattr(shutil, "which", lambda _name: "/fake/node")
    runner._configure_track_contract("pm")
    sections = runner.extract_sections(VALID_MODEL_OUTPUT)

    result = runner.generate_docx(sections, jd_path, tmp_path, tmp_path)

    assert result is not None
    assert layout_calls == 1
    assert any(
        row.get("bold_label") == "Interests" for row in captured["skills_rows"]
    )


def test_generate_docx_forced_t2_uses_exact_sanctioned_layout(monkeypatch, tmp_path):
    script = tmp_path / "resume_docx.js"
    script.write_text("// fixture", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    captured = {}

    def auto_choice_must_not_run(*_args, **_kwargs):
        raise AssertionError("a forced sanctioned tier must bypass the estimator")

    def capture_payload(command, **_kwargs):
        captured.update(json.loads(Path(command[-1]).read_text(encoding="utf-8")))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(runner, "DOCX_SCRIPT", script)
    monkeypatch.setattr(runner, "_choose_layout_tier", auto_choice_must_not_run)
    monkeypatch.setattr(runner.subprocess, "run", capture_payload)
    monkeypatch.setattr(shutil, "which", lambda _name: "/fake/node")
    runner._configure_track_contract("pm")
    sections = runner.extract_sections(VALID_MODEL_OUTPUT)

    result = runner.generate_docx(
        sections,
        jd_path,
        tmp_path,
        tmp_path,
        forced_layout_tier="T2",
    )

    assert result is not None
    assert captured["layout"] == {
        "line": 210,
        "section_before": 200,
        "section_after": 100,
        "margin_bottom": 720,
    }


def test_forced_layout_tier_is_closed_to_known_neighbors(monkeypatch, tmp_path):
    script = tmp_path / "resume_docx.js"
    script.write_text("// fixture", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    monkeypatch.setattr(runner, "DOCX_SCRIPT", script)
    runner._configure_track_contract("pm")
    sections = runner.extract_sections(VALID_MODEL_OUTPUT)

    with pytest.raises(ValueError, match="unknown layout tier"):
        runner.generate_docx(
            sections,
            jd_path,
            tmp_path,
            tmp_path,
            forced_layout_tier="T-1",
        )

    assert runner._next_looser_layout_tier("T3") == "T2.5"
    assert runner._next_looser_layout_tier("T2.5") == "T2"
    assert runner._next_looser_layout_tier("T2") == "T1"
    assert runner._next_looser_layout_tier("T1") == "T0"
    assert runner._next_looser_layout_tier("T0") is None
    with pytest.raises(ValueError, match="unknown layout tier"):
        runner._next_looser_layout_tier("T-1")

    assert runner._next_tighter_layout_tier("T0") == "T1"
    assert runner._next_tighter_layout_tier("T1") == "T2"
    assert runner._next_tighter_layout_tier("T2") == "T2.5"
    assert runner._next_tighter_layout_tier("T2.5") == "T3"
    assert runner._next_tighter_layout_tier("T3") is None
    with pytest.raises(ValueError, match="unknown layout tier"):
        runner._next_tighter_layout_tier("T-1")


def test_pdf_release_failure_makes_run_single_fail(monkeypatch, tmp_path):
    def generate_docx(*_args, **_kwargs):
        path = tmp_path / "resume.docx"
        path.write_bytes(b"docx")
        return path

    monkeypatch.setattr(runner, "generate_docx", generate_docx)
    monkeypatch.setattr(
        runner,
        "render_resume_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            runner.ResumeArtifactError("observed 2 pages")
        ),
    )

    ok, _out_dir = _run_minimal(monkeypatch, tmp_path, make_docx=True)

    assert ok is False


def test_run_app_propagates_resume_pipeline_failure(monkeypatch, tmp_path):
    (tmp_path / "jd.txt").write_text("Product role", encoding="utf-8")
    failed_pipeline = SimpleNamespace(run_single=lambda **_kwargs: False)
    monkeypatch.setattr(
        run_app,
        "_import_pipelines",
        lambda: (failed_pipeline, None, None),
    )

    with pytest.raises(RuntimeError, match="failed release checks"):
        run_app.run_app(
            company="Test Company",
            model="test-model",
            run_resume=True,
            run_cl=False,
            run_strategy=False,
            run_rewrite=False,
            run_score=False,
            run_qc=False,
            make_docx=False,
            app_dir_override=str(tmp_path),
            smart_cost=False,
        )


def test_run_app_renames_and_tracks_released_pdf(monkeypatch, tmp_path):
    (tmp_path / "jd.txt").write_text("Product role", encoding="utf-8")
    today = "2099-01-02"

    def successful_run(**kwargs):
        app_dir = Path(kwargs["out_dir"])
        (app_dir / f"{today}_jd.txt").write_text(
            "SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)\n"
            "------------------------------------------------------------------------\n"
            "COMPANY | Role\n• Built a product and shipped it.\n",
            encoding="utf-8",
        )
        (app_dir / f"{today}_jd.docx").write_bytes(b"docx")
        (app_dir / f"{today}_jd.pdf").write_bytes(b"released-pdf")
        return True

    pipeline = SimpleNamespace(run_single=successful_run)
    monkeypatch.setattr(run_app, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(run_app, "_today", lambda: today)
    monkeypatch.setattr(run_app, "_import_pipelines", lambda: (pipeline, None, None))

    run_app.run_app(
        company="Test Company",
        model="test-model",
        run_resume=True,
        run_cl=False,
        run_strategy=False,
        run_rewrite=False,
        run_score=False,
        run_qc=False,
        make_docx=True,
        app_dir_override=str(tmp_path),
        smart_cost=False,
    )

    assert (tmp_path / f"resume_{today}.docx").is_file()
    assert (tmp_path / f"resume_{today}.pdf").read_bytes() == b"released-pdf"
    audit_path = next(tmp_path.glob("generation_audit_*.json"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["artifacts"]["resume_pdf"] == f"resume_{today}.pdf"


def test_v2_underfill_recovery_requests_one_profile_bounded_distinct_proof(
    monkeypatch,
):
    monkeypatch.setenv("RESUME_V2_BULLET_BUDGET", "11")
    monkeypatch.delenv("RESUME_V2_ADD_COMPANY", raising=False)
    profile = get_profile("product-general")

    plan = runner._v2_allocation_request_from_environment(profile)

    assert plan is not None
    assert plan.budget_decision is BulletBudgetDecision.ADD_DISTINCT_SIGNAL
    assert plan.total == 11
    assert plan.counts_dict() == {
        "FLAIRX AI": 3,
        "GOJEK": 3,
        "HEVO DATA": 2,
        "INTUIT": 2,
        "OPTUM": 1,
    }


def test_v2_underfill_recovery_can_target_an_explicit_profile_slot(monkeypatch):
    monkeypatch.setenv("RESUME_V2_BULLET_BUDGET", "11")
    monkeypatch.setenv("RESUME_V2_ADD_COMPANY", "INTUIT")
    profile = get_profile("product-general")

    plan = runner._v2_allocation_request_from_environment(profile)

    assert plan is not None
    assert plan.counts_dict()["INTUIT"] == 3
    assert plan.counts_dict()["FLAIRX AI"] == 2


def test_v2_underfill_recovery_rejects_unbounded_or_ineligible_requests(monkeypatch):
    profile = get_profile("product-general")
    monkeypatch.setenv("RESUME_V2_BULLET_BUDGET", "12")
    with pytest.raises(ValueError, match="supports only the profile target"):
        runner._v2_allocation_request_from_environment(profile)

    monkeypatch.setenv("RESUME_V2_BULLET_BUDGET", "11")
    monkeypatch.setenv("RESUME_V2_ADD_COMPANY", "GOJEK")
    with pytest.raises(ValueError, match="slot with headroom"):
        runner._v2_allocation_request_from_environment(profile)


def test_docx_only_route_applies_pdf_gate_and_renames_both(monkeypatch, tmp_path):
    (tmp_path / "jd.txt").write_text("Product role", encoding="utf-8")
    source_date = "2099-01-03"
    (tmp_path / f"resume_{source_date}.txt").write_text(
        "SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "Product builder summary.\n\n"
        "SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "FLAIRX AI | Role\n• Built and shipped the product.\n\n"
        "SECTION 4 — SKILLS & INTERESTS (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "SKILLS & INTERESTS\n● Product Focus: Discovery\n",
        encoding="utf-8",
    )

    def generate_docx(_sections, _jd_path, out_dir, **_kwargs):
        path = Path(out_dir) / f"{source_date}_jd.docx"
        path.write_bytes(b"docx")
        return path

    def release_pdf(_sections, docx_path):
        pdf_path = Path(docx_path).with_suffix(".pdf")
        pdf_path.write_bytes(b"released-pdf")
        return SimpleNamespace(pdf=SimpleNamespace(path=pdf_path))

    pipeline = SimpleNamespace(generate_docx=generate_docx)
    monkeypatch.setattr(run_app, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(run_app, "_import_pipelines", lambda: (pipeline, None, None))
    monkeypatch.setattr(run_app, "_release_resume_pdf", release_pdf)

    run_app.docx_only_app(
        "Test Company",
        app_dir_override=str(tmp_path),
    )

    assert (tmp_path / f"resume_{source_date}.docx").is_file()
    assert (tmp_path / f"resume_{source_date}.pdf").read_bytes() == b"released-pdf"


def test_score_only_route_applies_pdf_gate_and_preserves_prior_until_release(
    monkeypatch, tmp_path
):
    (tmp_path / "jd.txt").write_text("Product role", encoding="utf-8")
    source_date = "2099-01-04"
    (tmp_path / f"resume_{source_date}.txt").write_text(
        "SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "Product builder summary.\n\n"
        "SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "FLAIRX AI | Role\n• Built and shipped the product.\n\n"
        "SECTION 4 — SKILLS & INTERESTS (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "SKILLS & INTERESTS\n● Product Focus: Discovery\n",
        encoding="utf-8",
    )
    prior_docx = tmp_path / f"resume_{source_date}_r8.0.docx"
    prior_docx.write_bytes(b"prior-valid-docx")

    def generate_docx(_sections, _jd_path, out_dir, _docx_out_dir, **_kwargs):
        path = Path(out_dir) / f"{source_date}_jd_r8.5.docx"
        path.write_bytes(b"candidate-docx")
        return path

    def release_pdf(_sections, docx_path):
        # The prior published artifact must still exist while the candidate is
        # being validated.
        assert prior_docx.read_bytes() == b"prior-valid-docx"
        pdf_path = Path(docx_path).with_suffix(".pdf")
        pdf_path.write_bytes(b"released-pdf")
        return SimpleNamespace(pdf=SimpleNamespace(path=pdf_path))

    def score_experience(experience, *_args, **_kwargs):
        if "Revised and shipped" in experience:
            return {"holistic_score": 8.5, "bullets": []}
        return {
            "holistic_score": 8.0,
            "bullets": [{"score": 7.0, "company": "FLAIRX AI", "index": 1}],
        }

    def revise_experience(experience, *_args, **_kwargs):
        return experience.replace(
            "Built and shipped the product.",
            "Revised and shipped the product from customer evidence.",
        ), "revision log"

    pipeline = SimpleNamespace(
        run_scorer=score_experience,
        print_score=lambda *_args, **_kwargs: None,
        run_targeted_fixes=revise_experience,
        generate_docx=generate_docx,
        _sanitize_summary_section=lambda text: text.strip(),
        _THREE_LINE_CHARS=200,
        _MAX_ALLOWED_THREE_LINERS=2,
    )
    monkeypatch.setattr(run_app, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(run_app, "resolve_company", lambda _company: tmp_path)
    monkeypatch.setattr(run_app, "_import_pipelines", lambda: (pipeline, None, None))
    monkeypatch.setattr(run_app, "_release_resume_pdf", release_pdf)

    run_app.score_only_app("Test Company", "test-model")

    assert prior_docx.read_bytes() == b"prior-valid-docx"
    assert (tmp_path / f"resume_{source_date}_r8.5.docx").read_bytes() == b"candidate-docx"
    assert (tmp_path / f"resume_{source_date}_r8.5.pdf").read_bytes() == b"released-pdf"
    revised_audit = (tmp_path / f"resume_{source_date}.txt").read_text(encoding="utf-8")
    assert "Revised and shipped the product from customer evidence." in revised_audit


def test_score_only_release_failure_preserves_source_txt(monkeypatch, tmp_path):
    (tmp_path / "jd.txt").write_text("Product role", encoding="utf-8")
    source_date = "2099-01-05"
    txt_path = tmp_path / f"resume_{source_date}.txt"
    txt_path.write_text(
        "SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "Product builder summary.\n\n"
        "SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "FLAIRX AI | Role\n• Built and shipped the product.\n\n"
        "SECTION 4 — SKILLS & INTERESTS (paste-ready)\n"
        "------------------------------------------------------------------------\n"
        "SKILLS & INTERESTS\n● Product Focus: Discovery\n",
        encoding="utf-8",
    )
    original_bytes = txt_path.read_bytes()

    def score_experience(experience, *_args, **_kwargs):
        if "Revised and shipped" in experience:
            return {"holistic_score": 8.5, "bullets": []}
        return {
            "holistic_score": 8.0,
            "bullets": [{"score": 7.0, "company": "FLAIRX AI", "index": 1}],
        }

    def generate_docx(*_args, **_kwargs):
        path = tmp_path / f"{source_date}_jd_r8.5.docx"
        path.write_bytes(b"candidate-docx")
        return path

    pipeline = SimpleNamespace(
        run_scorer=score_experience,
        print_score=lambda *_args, **_kwargs: None,
        run_targeted_fixes=lambda experience, *_args, **_kwargs: (
            experience.replace(
                "Built and shipped the product.",
                "Revised and shipped the product from customer evidence.",
            ),
            "revision log",
        ),
        generate_docx=generate_docx,
        _sanitize_summary_section=lambda text: text.strip(),
        _THREE_LINE_CHARS=200,
        _MAX_ALLOWED_THREE_LINERS=2,
    )
    monkeypatch.setattr(run_app, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(run_app, "resolve_company", lambda _company: tmp_path)
    monkeypatch.setattr(run_app, "_import_pipelines", lambda: (pipeline, None, None))
    monkeypatch.setattr(
        run_app,
        "_release_resume_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("parity failed")),
    )

    with pytest.raises(RuntimeError, match="parity failed"):
        run_app.score_only_app("Test Company", "test-model")

    assert txt_path.read_bytes() == original_bytes


def test_atomic_txt_replace_failure_keeps_prior_audit(monkeypatch, tmp_path):
    txt_path = tmp_path / "resume.txt"
    txt_path.write_text("prior audit", encoding="utf-8")
    monkeypatch.setattr(
        run_app.os,
        "chmod",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("chmod failed")),
    )

    with pytest.raises(OSError, match="chmod failed"):
        run_app._atomic_replace_text(txt_path, "revised audit")

    assert txt_path.read_text(encoding="utf-8") == "prior audit"
    assert not list(tmp_path.glob(".resume.txt.candidate-*.tmp"))
