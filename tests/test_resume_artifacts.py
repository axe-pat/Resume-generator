from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

import shared.resume_artifacts as artifacts
from shared.resume_artifacts import (
    ResumeArtifactError,
    ResumePageUnderfillError,
    expected_resume_fragments,
    inspect_docx_vertical_margins,
    render_resume_artifact,
)
from shared.resume_lint import RenderedPdfArtifact
from shared.resume_fill import (
    ObservedPdfGeometry,
    PageFillReleaseStatus,
    PdfPageGeometry,
    V2_PAGE_FILL_RELEASE_POLICY,
)


def _fake_render(monkeypatch, *, text="PRODUCT MANAGEMENT\nExpected bullet", pages=1):
    monkeypatch.setattr(artifacts, "_soffice_executable", lambda: "/fake/soffice")

    def fake_run(command, **_kwargs):
        out_dir = Path(command[command.index("--outdir") + 1])
        source = Path(command[-1])
        (out_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-fake")
        return SimpleNamespace(returncode=0, stdout="converted", stderr="")

    monkeypatch.setattr(artifacts.subprocess, "run", fake_run)
    monkeypatch.setattr(
        artifacts,
        "inspect_pdf_artifact",
        lambda path: RenderedPdfArtifact(Path(path), pages, text),
    )


def test_render_resume_artifact_uses_observed_page_and_text(monkeypatch, tmp_path):
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    _fake_render(monkeypatch)

    release = render_resume_artifact(
        source,
        expected_fragments=("PRODUCT MANAGEMENT", "Expected bullet"),
    )

    assert release.release_ready
    assert release.pdf.path == source.with_suffix(".pdf")
    assert source.with_suffix(".pdf").is_file()


def test_render_resume_artifact_reports_page_and_content_failures(monkeypatch, tmp_path):
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    _fake_render(monkeypatch, text="PRODUCT MANAGEMENT", pages=2)

    with pytest.raises(
        ResumeArtifactError,
        match=r"observed 2 pages.*1 expected text fragment",
    ):
        render_resume_artifact(source, expected_fragments=("Missing bullet",))

    assert not source.with_suffix(".pdf").exists()


def test_invalid_candidate_does_not_replace_an_earlier_valid_pdf(monkeypatch, tmp_path):
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    destination = source.with_suffix(".pdf")
    destination.write_bytes(b"old-valid-pdf")
    _fake_render(monkeypatch, text="Wrong content", pages=1)

    with pytest.raises(ResumeArtifactError, match="expected text fragment"):
        render_resume_artifact(source, expected_fragments=("Expected bullet",))

    assert destination.read_bytes() == b"old-valid-pdf"


def test_render_resume_artifact_does_not_replace_pdf_when_conversion_fails(
    monkeypatch, tmp_path
):
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    destination = source.with_suffix(".pdf")
    destination.write_bytes(b"old-valid-pdf")
    monkeypatch.setattr(artifacts, "_soffice_executable", lambda: "/fake/soffice")
    monkeypatch.setattr(
        artifacts.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="conversion failed"
        ),
    )

    with pytest.raises(ResumeArtifactError, match="conversion failed"):
        render_resume_artifact(source)

    assert destination.read_bytes() == b"old-valid-pdf"


def test_render_resume_artifact_requires_a_real_docx(tmp_path):
    with pytest.raises(ResumeArtifactError, match="DOCX does not exist"):
        render_resume_artifact(tmp_path / "missing.docx")


def test_expected_fragments_include_summary_and_every_proof_bullet():
    sections = {
        "summary_section": "Product builder summary.",
        "experience_section": "COMPANY | Role\n• Experience one.\n- Experience two.",
        "projects_section": "PROJECTS\n● Project one.\n* Project two.",
        "skills_section": "SKILLS\n● Tools: SQL",
    }

    assert expected_resume_fragments(sections) == (
        "Product builder summary.",
        "COMPANY",
        "Role",
        "Experience one.",
        "Experience two.",
        "Project one.",
        "Project two.",
        "Tools: SQL",
    )


def test_expected_fragments_join_wrapped_bullets_and_skills_rows():
    sections = {
        "summary_section": "Product builder\nwith customer evidence.",
        "experience_section": (
            "COMPANY | Product Manager | Jan 2026 - Present | Los Angeles, CA\n"
            "• Identified a hidden customer need and designed the workflow\n"
            "  across three product surfaces, then shipped the fix.\n"
        ),
        "projects_section": (
            "PROJECTS & CONSULTING\n"
            "Recruiting Engine | Independent Builder | 2026\n"
            "• Built the end-to-end decision engine\n"
            "  with evidence gates before external action.\n"
        ),
        "skills_section": (
            "SKILLS & INTERESTS\n"
            "● Product Focus: Customer discovery, rapid prototyping,\n"
            "  experimentation, and roadmap execution\n"
            "● Interests: DJing and trekking\n"
        ),
    }

    fragments = expected_resume_fragments(sections)

    assert "Product builder with customer evidence." in fragments
    assert (
        "Identified a hidden customer need and designed the workflow across three "
        "product surfaces, then shipped the fix."
        in fragments
    )
    assert (
        "Built the end-to-end decision engine with evidence gates before external action."
        in fragments
    )
    assert (
        "Product Focus: Customer discovery, rapid prototyping, experimentation, and "
        "roadmap execution"
        in fragments
    )
    assert "Interests: DJing and trekking" in fragments


def _write_docx_with_margins(path: Path, *, top: int = 1080, bottom: int = 720):
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:sectPr><w:pgMar w:top="{top}" w:bottom="{bottom}"/></w:sectPr></w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def _geometry(fill_ratio: float) -> ObservedPdfGeometry:
    top = 54.0
    bottom = 36.0
    height = 792.0
    content_bottom = top + fill_ratio * (height - top - bottom)
    return ObservedPdfGeometry(
        path=Path("candidate.pdf"),
        pages=(
            PdfPageGeometry(612.0, height, 54.0, content_bottom, 650),
        ),
        top_margin_pt=top,
        bottom_margin_pt=bottom,
    )


def test_docx_vertical_margins_are_read_from_rendered_contract(tmp_path):
    source = tmp_path / "resume.docx"
    _write_docx_with_margins(source, top=1080, bottom=648)

    assert inspect_docx_vertical_margins(source) == (54.0, 32.4)


def test_v2_observed_underfill_blocks_before_pdf_publication(monkeypatch, tmp_path):
    source = tmp_path / "resume.docx"
    _write_docx_with_margins(source)
    destination = source.with_suffix(".pdf")
    destination.write_bytes(b"old-valid-pdf")
    _fake_render(monkeypatch)
    monkeypatch.setattr(
        artifacts,
        "inspect_pdf_geometry",
        lambda *_args, **_kwargs: _geometry(0.90),
    )

    with pytest.raises(
        ResumePageUnderfillError,
        match=r"V2_PAGE_UNDERFILLED.*90\.0%.*93\.0%.*selected 10 proof units",
    ) as caught:
        render_resume_artifact(
            source,
            expected_fragments=("Expected bullet",),
            page_fill_policy=V2_PAGE_FILL_RELEASE_POLICY,
            proof_units=10,
        )

    assert caught.value.assessment.observed_fill_ratio == pytest.approx(0.90)
    assert caught.value.assessment.proof_units == 10
    assert destination.read_bytes() == b"old-valid-pdf"


def test_underfill_with_missing_text_is_not_recoverable_layout_only(
    monkeypatch, tmp_path
):
    source = tmp_path / "resume.docx"
    _write_docx_with_margins(source)
    _fake_render(monkeypatch, text="PRODUCT MANAGEMENT", pages=1)
    monkeypatch.setattr(
        artifacts,
        "inspect_pdf_geometry",
        lambda *_args, **_kwargs: _geometry(0.90),
    )

    with pytest.raises(ResumeArtifactError) as caught:
        render_resume_artifact(
            source,
            expected_fragments=("Missing bullet",),
            page_fill_policy=V2_PAGE_FILL_RELEASE_POLICY,
            proof_units=10,
        )

    assert not isinstance(caught.value, ResumePageUnderfillError)
    assert "expected text fragment" in str(caught.value)
    assert "V2_PAGE_UNDERFILLED" in str(caught.value)
    assert not source.with_suffix(".pdf").exists()


def test_v2_near_floor_releases_with_observed_warning(monkeypatch, tmp_path):
    source = tmp_path / "resume.docx"
    _write_docx_with_margins(source)
    _fake_render(monkeypatch)
    monkeypatch.setattr(
        artifacts,
        "inspect_pdf_geometry",
        lambda *_args, **_kwargs: _geometry(0.94),
    )

    release = render_resume_artifact(
        source,
        expected_fragments=("Expected bullet",),
        page_fill_policy=V2_PAGE_FILL_RELEASE_POLICY,
        proof_units=10,
    )

    assert release.release_ready
    assert release.page_fill is not None
    assert release.page_fill.status is PageFillReleaseStatus.READY_NEAR_FLOOR
    assert release.page_fill.warning
