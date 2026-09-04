import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from resume.freeform import freeform_runner as runner
from shared.resume_fill import PageFillReleaseAssessment, PageFillReleaseStatus


V2_MODEL_OUTPUT = """\
SECTION 0 — PROFESSIONAL SUMMARY
Product manager and engineer who turns customer evidence into shipped products.

SECTION 1 — TOP 3 JD SIGNALS
1. Customer discovery

SECTION 2 — VARIANT SELECTION NOTES
Selected reviewed variants.

SECTION 3 — FULL EXPERIENCE SECTION
FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA
• Built a customer-led product workflow and shipped it with engineering.

SECTION 4 — SKILLS
SKILLS
● Product Focus: Customer Discovery
● Tools: SQL
"""


def _candidate_names() -> tuple[str, str]:
    return "2099-01-01_jd_r9.0.docx", "2099-01-01_jd_r9.0.pdf"


def _underfill_error(ratio: float = 0.90):
    return runner.ResumePageUnderfillError(
        PageFillReleaseAssessment(
            status=PageFillReleaseStatus.BLOCK_UNDERFILLED,
            observed_fill_ratio=ratio,
            usable_bottom_whitespace_pt=50.0,
            minimum_release_fill_ratio=0.93,
            proof_units=10,
        )
    )


def test_v2_render_failure_preserves_prior_visible_artifacts(monkeypatch, tmp_path):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, pdf_name = _candidate_names()
    prior_docx = publish_dir / docx_name
    prior_pdf = publish_dir / pdf_name
    prior_docx.write_bytes(b"prior-valid-docx")
    prior_pdf.write_bytes(b"prior-valid-pdf")

    def generate_candidate(_sections, _jd_path, _out_dir, candidate_dir, **_kwargs):
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"invalid-candidate-docx")
        return staged

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(
        runner,
        "render_resume_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            runner.ResumeArtifactError("observed 2 pages")
        ),
    )

    with pytest.raises(runner.ResumeArtifactError, match="observed 2 pages"):
        runner._generate_and_publish_v2_artifacts(
            {},
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(bullets=()),
        )

    assert prior_docx.read_bytes() == b"prior-valid-docx"
    assert prior_pdf.read_bytes() == b"prior-valid-pdf"
    assert not list(publish_dir.glob(".resume-v2-candidate-*"))


def test_v2_underfill_rerenders_identical_content_once_at_next_looser_tier(
    monkeypatch, tmp_path
):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, pdf_name = _candidate_names()
    sections = runner.extract_sections(V2_MODEL_OUTPUT)
    original_sections = copy.deepcopy(sections)
    assembled = SimpleNamespace(name="assembled", bullets=tuple(range(10)))
    layout_calls = []
    render_calls = 0

    def generate_candidate(
        supplied_sections,
        _jd_path,
        _out_dir,
        candidate_dir,
        *,
        forced_layout_tier=None,
        **_kwargs,
    ):
        assert supplied_sections == original_sections
        layout_calls.append(forced_layout_tier)
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(f"docx-{forced_layout_tier}".encode())
        return staged

    def render_candidate(docx_path, **_kwargs):
        nonlocal render_calls
        render_calls += 1
        if render_calls == 1:
            raise _underfill_error()
        staged_pdf = Path(docx_path).with_suffix(".pdf")
        staged_pdf.write_bytes(b"pdf-T2.5")
        return SimpleNamespace(
            docx_path=Path(docx_path),
            pdf=SimpleNamespace(path=staged_pdf),
            page_fill=SimpleNamespace(
                observed_fill_ratio=0.96,
                status=PageFillReleaseStatus.READY,
            ),
        )

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(runner, "render_resume_artifact", render_candidate)
    monkeypatch.setattr(runner, "_selected_layout_tier_name", lambda _sections: "T3")
    monkeypatch.setattr(
        runner,
        "call_api",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("layout-only recovery must not invoke a model")
        ),
    )
    monkeypatch.setattr(
        runner,
        "attach_pdf_artifact",
        lambda document, _path: SimpleNamespace(source=document),
    )
    monkeypatch.setattr(
        runner,
        "lint_assembled_resume",
        lambda *_args, **_kwargs: SimpleNamespace(blockers=(), warnings=()),
    )

    published_docx, published_pdf, warnings, page_fill = (
        runner._generate_and_publish_v2_artifacts(
            sections,
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=assembled,
        )
    )

    assert layout_calls == [None, "T2.5"]
    assert render_calls == 2
    assert sections == original_sections
    assert published_docx.read_bytes() == b"docx-T2.5"
    assert published_pdf.read_bytes() == b"pdf-T2.5"
    assert warnings == ()
    assert page_fill.observed_fill_ratio == 0.96
    assert not list(publish_dir.glob(".resume-v2-candidate-*"))


def test_v2_underfill_retry_never_walks_more_than_one_looser_tier(
    monkeypatch, tmp_path
):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, pdf_name = _candidate_names()
    prior_docx = publish_dir / docx_name
    prior_pdf = publish_dir / pdf_name
    prior_docx.write_bytes(b"prior-valid-docx")
    prior_pdf.write_bytes(b"prior-valid-pdf")
    sections = runner.extract_sections(V2_MODEL_OUTPUT)
    layout_calls = []

    def generate_candidate(
        _sections,
        _jd_path,
        _out_dir,
        candidate_dir,
        *,
        forced_layout_tier=None,
        **_kwargs,
    ):
        layout_calls.append(forced_layout_tier)
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"candidate")
        return staged

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(
        runner,
        "render_resume_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(_underfill_error()),
    )
    monkeypatch.setattr(runner, "_selected_layout_tier_name", lambda _sections: "T3")

    with pytest.raises(runner.ResumePageUnderfillError):
        runner._generate_and_publish_v2_artifacts(
            sections,
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(bullets=tuple(range(10))),
        )

    assert layout_calls == [None, "T2.5"]
    assert prior_docx.read_bytes() == b"prior-valid-docx"
    assert prior_pdf.read_bytes() == b"prior-valid-pdf"
    assert not list(publish_dir.glob(".resume-v2-candidate-*"))


def test_v2_underfill_at_loose_t0_fails_without_retry(monkeypatch, tmp_path):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, _ = _candidate_names()
    layout_calls = []

    def generate_candidate(
        _sections,
        _jd_path,
        _out_dir,
        candidate_dir,
        *,
        forced_layout_tier=None,
        **_kwargs,
    ):
        layout_calls.append(forced_layout_tier)
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"candidate")
        return staged

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(
        runner,
        "render_resume_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(_underfill_error()),
    )
    monkeypatch.setattr(runner, "_selected_layout_tier_name", lambda _sections: "T0")

    with pytest.raises(runner.ResumePageUnderfillError):
        runner._generate_and_publish_v2_artifacts(
            runner.extract_sections(V2_MODEL_OUTPUT),
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(bullets=tuple(range(10))),
        )

    assert layout_calls == [None]


def test_v2_publishes_docx_and_pdf_only_after_final_release_lint(
    monkeypatch, tmp_path
):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, pdf_name = _candidate_names()
    prior_docx = publish_dir / docx_name
    prior_pdf = publish_dir / pdf_name
    prior_docx.write_bytes(b"prior-valid-docx")
    prior_pdf.write_bytes(b"prior-valid-pdf")
    assembled = SimpleNamespace(name="assembled", bullets=())
    observed = []

    def generate_candidate(_sections, _jd_path, _out_dir, candidate_dir, **_kwargs):
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"validated-docx")
        return staged

    def render_candidate(docx_path, *, expected_fragments, **_kwargs):
        assert prior_docx.read_bytes() == b"prior-valid-docx"
        assert prior_pdf.read_bytes() == b"prior-valid-pdf"
        assert tuple(expected_fragments)
        staged_pdf = Path(docx_path).with_suffix(".pdf")
        staged_pdf.write_bytes(b"validated-pdf")
        observed.append("rendered")
        return SimpleNamespace(
            docx_path=Path(docx_path),
            pdf=SimpleNamespace(path=staged_pdf),
            page_fill=SimpleNamespace(
                observed_fill_ratio=0.96,
                status=PageFillReleaseStatus.READY,
            ),
        )

    def attach_candidate(document, pdf_path):
        assert document is assembled
        assert Path(pdf_path).read_bytes() == b"validated-pdf"
        observed.append("attached")
        return SimpleNamespace(name="rendered-document")

    def release_lint(document, policy):
        assert document.name == "rendered-document"
        assert policy is runner.RELEASE_POLICY
        assert prior_docx.read_bytes() == b"prior-valid-docx"
        assert prior_pdf.read_bytes() == b"prior-valid-pdf"
        observed.append("linted")
        return SimpleNamespace(blockers=(), warnings=())

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(runner, "render_resume_artifact", render_candidate)
    monkeypatch.setattr(runner, "attach_pdf_artifact", attach_candidate)
    monkeypatch.setattr(runner, "lint_assembled_resume", release_lint)
    monkeypatch.setattr(
        runner,
        "expected_resume_fragments",
        lambda _sections: ("customer-led product workflow",),
    )

    published_docx, published_pdf, warnings, page_fill = (
        runner._generate_and_publish_v2_artifacts(
            {},
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=assembled,
        )
    )

    assert observed == ["rendered", "attached", "linted"]
    assert published_docx == prior_docx
    assert published_pdf == prior_pdf
    assert prior_docx.read_bytes() == b"validated-docx"
    assert prior_pdf.read_bytes() == b"validated-pdf"
    assert warnings == ()
    assert page_fill.observed_fill_ratio == 0.96
    assert not list(publish_dir.glob(".resume-v2-candidate-*"))


def test_v2_dense_page_rerenders_identical_content_once_at_next_tighter_tier(
    monkeypatch, tmp_path
):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, _ = _candidate_names()
    sections = runner.extract_sections(V2_MODEL_OUTPUT)
    original_sections = copy.deepcopy(sections)
    layout_calls = []
    render_calls = 0

    def generate_candidate(
        supplied_sections,
        _jd_path,
        _out_dir,
        candidate_dir,
        *,
        forced_layout_tier=None,
        **_kwargs,
    ):
        assert supplied_sections == original_sections
        layout_calls.append(forced_layout_tier)
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(f"docx-{forced_layout_tier}".encode())
        return staged

    def render_candidate(docx_path, **_kwargs):
        nonlocal render_calls
        render_calls += 1
        staged_pdf = Path(docx_path).with_suffix(".pdf")
        staged_pdf.write_bytes(f"pdf-{render_calls}".encode())
        status = (
            PageFillReleaseStatus.READY_DENSE
            if render_calls == 1
            else PageFillReleaseStatus.READY
        )
        return SimpleNamespace(
            docx_path=Path(docx_path),
            pdf=SimpleNamespace(path=staged_pdf),
            page_fill=PageFillReleaseAssessment(
                status=status,
                observed_fill_ratio=0.99 if render_calls == 1 else 0.96,
                usable_bottom_whitespace_pt=7.0 if render_calls == 1 else 25.0,
                minimum_release_fill_ratio=0.93,
                proof_units=10,
            ),
        )

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(runner, "render_resume_artifact", render_candidate)
    monkeypatch.setattr(runner, "_selected_layout_tier_name", lambda _sections: "T2")
    monkeypatch.setattr(
        runner,
        "attach_pdf_artifact",
        lambda document, _path: SimpleNamespace(source=document),
    )
    monkeypatch.setattr(
        runner,
        "lint_assembled_resume",
        lambda *_args, **_kwargs: SimpleNamespace(blockers=(), warnings=()),
    )

    published_docx, published_pdf, _, page_fill = (
        runner._generate_and_publish_v2_artifacts(
            sections,
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(bullets=tuple(range(10))),
        )
    )

    assert layout_calls == [None, "T2.5"]
    assert render_calls == 2
    assert sections == original_sections
    assert published_docx.read_bytes() == b"docx-T2.5"
    assert published_pdf.read_bytes() == b"pdf-2"
    assert page_fill.status is PageFillReleaseStatus.READY


def test_optional_sixth_skills_fallback_removes_only_that_reviewed_row():
    sections = {
        "skills_section": (
            "SKILLS & INTERESTS\n"
            "● Product Leadership: Roadmap Prioritization\n"
            "● Data & Analytics: Funnel Analysis\n"
            "● Technical: Python\n"
            "● AI & Automation: Agentic Workflows\n"
            "● Startup Product: Fluo, tested student offers\n"
            "● Interests: DJing house music"
        )
    }

    revised = runner._drop_optional_skill_row(
        sections,
        optional_label="Interests",
        expected_labels=(
            "Product Leadership",
            "Data & Analytics",
            "Technical",
            "AI & Automation",
            "Startup Product",
        ),
    )

    assert revised is not sections
    assert revised["skills_section"].startswith("SKILLS\n")
    assert "Interests" not in revised["skills_section"]
    assert "Startup Product: Fluo, tested student offers" in revised["skills_section"]
    assert sections["skills_section"].startswith("SKILLS & INTERESTS\n")


def test_sixth_skills_row_fails_into_the_dedicated_fallback_path_when_too_dense(
    monkeypatch,
    tmp_path,
):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, _ = _candidate_names()

    def generate_candidate(_sections, _jd_path, _out_dir, candidate_dir, **_kwargs):
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"six-row-docx")
        return staged

    def render_candidate(docx_path, **_kwargs):
        staged_pdf = Path(docx_path).with_suffix(".pdf")
        staged_pdf.write_bytes(b"six-row-pdf")
        return SimpleNamespace(
            docx_path=Path(docx_path),
            pdf=SimpleNamespace(path=staged_pdf),
            page_fill=PageFillReleaseAssessment(
                status=PageFillReleaseStatus.READY,
                observed_fill_ratio=0.975,
                usable_bottom_whitespace_pt=17.0,
                minimum_release_fill_ratio=0.93,
                proof_units=10,
            ),
        )

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(runner, "render_resume_artifact", render_candidate)

    with pytest.raises(
        runner.OptionalSixthSkillRowRejected,
        match="OPTIONAL_SIXTH_SKILL_ROW_REJECTED",
    ):
        runner._generate_and_publish_v2_artifacts(
            runner.extract_sections(V2_MODEL_OUTPUT),
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(
                bullets=tuple(range(10)),
                skill_rows=tuple(range(6)),
            ),
            skills_plan=SimpleNamespace(
                row_count=6,
                has_optional_sixth=True,
            ),
        )

    assert not list(publish_dir.glob("*.docx"))
    assert not list(publish_dir.glob("*.pdf"))


def test_v2_rejects_renderer_docx_identity_mismatch(monkeypatch, tmp_path):
    publish_dir = tmp_path / "published"
    publish_dir.mkdir()
    docx_name, _ = _candidate_names()

    def generate_candidate(_sections, _jd_path, _out_dir, candidate_dir, **_kwargs):
        staged = Path(candidate_dir) / docx_name
        staged.write_bytes(b"candidate")
        return staged

    def render_wrong_docx(docx_path, **_kwargs):
        staged_pdf = Path(docx_path).with_suffix(".pdf")
        staged_pdf.write_bytes(b"pdf")
        return SimpleNamespace(
            docx_path=Path(docx_path).with_name("different.docx"),
            pdf=SimpleNamespace(path=staged_pdf),
            page_fill=SimpleNamespace(
                observed_fill_ratio=0.96,
                status=PageFillReleaseStatus.READY,
            ),
        )

    monkeypatch.setattr(runner, "generate_docx", generate_candidate)
    monkeypatch.setattr(runner, "render_resume_artifact", render_wrong_docx)

    with pytest.raises(runner.ResumeArtifactError, match="validated a DOCX other than"):
        runner._generate_and_publish_v2_artifacts(
            runner.extract_sections(V2_MODEL_OUTPUT),
            tmp_path / "jd.txt",
            tmp_path / "runs",
            publish_dir,
            score=9.0,
            track="pm",
            profile=SimpleNamespace(),
            assembled_document=SimpleNamespace(bullets=tuple(range(10))),
        )

    assert not list(publish_dir.glob("*.docx"))
    assert not list(publish_dir.glob("*.pdf"))


def test_v2_render_failure_defers_txt_release(monkeypatch, tmp_path):
    monkeypatch.setenv("RESUME_GENERATOR_MODE", "v2")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Product role", encoding="utf-8")
    out_dir = tmp_path / "runs"
    out_dir.mkdir()
    prior_txt = out_dir / f"{runner.datetime.now():%Y-%m-%d}_jd.txt"
    prior_txt.write_bytes(b"prior-valid-audit")

    allocation = SimpleNamespace(counts_dict=lambda: {"FLAIRX AI": 1})
    override = SimpleNamespace(
        profile_id="product-general",
        profile=SimpleNamespace(profile_id="product-general"),
        allocation_plan=allocation,
    )
    assembled = SimpleNamespace(name="assembled")

    monkeypatch.setattr(runner, "load_prompt", lambda *_args, **_kwargs: "legacy")
    monkeypatch.setattr(
        runner,
        "adapt_legacy_pass1_prompt",
        lambda *_args, **_kwargs: SimpleNamespace(prompt="v2", override=override),
    )
    monkeypatch.setattr(runner, "_configure_v2_contract", lambda _override: None)
    monkeypatch.setattr(
        runner,
        "canonicalize_v2_selection_notes",
        lambda sections, _override: sections.get("selection_notes", ""),
    )
    monkeypatch.setattr(runner, "call_api", lambda *_args, **_kwargs: V2_MODEL_OUTPUT)
    monkeypatch.setattr(
        runner,
        "run_scorer",
        lambda *_args, **_kwargs: {
            "holistic_score": 9.0,
            "verdict": "SEND",
            "bullets": [],
        },
    )
    monkeypatch.setattr(
        runner,
        "run_quality_checks",
        lambda _sections, track="pm", profile=None: [
            {"name": "advisory", "status": "WARN", "detail": track}
        ],
    )
    monkeypatch.setattr(
        runner,
        "validate_scorer_release_evidence",
        lambda *_args, **_kwargs: ([], []),
    )
    monkeypatch.setattr(
        runner,
        "validate_v2_sections",
        lambda *_args, **_kwargs: SimpleNamespace(
            errors=(), warnings=(), document=assembled
        ),
    )
    monkeypatch.setattr(
        runner,
        "lint_assembled_resume",
        lambda *_args, **_kwargs: SimpleNamespace(
            issues=(), blockers=(), warnings=()
        ),
    )
    monkeypatch.setattr(
        runner,
        "_generate_and_publish_v2_artifacts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            runner.ResumeArtifactError("observed 2 pages")
        ),
    )

    save_calls = []
    monkeypatch.setattr(
        runner,
        "save_output",
        lambda *_args, **_kwargs: save_calls.append(True),
    )

    ok = runner.run_single(
        jd_path=jd_path,
        model="test-model",
        out_dir=out_dir,
        make_docx=True,
        run_strategy=False,
        run_rewrite=False,
        run_score=True,
        run_fix=False,
        pre_strategy=({}, ""),
        run_trim=False,
    )

    assert ok is False
    assert save_calls == []
    assert prior_txt.read_bytes() == b"prior-valid-audit"
    assert not list(out_dir.glob("*.docx"))
    assert not list(out_dir.glob("*.pdf"))
