import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import shared.resume_fill as fill
from shared.resume_fill import PdfGeometryError, inspect_pdf_geometry
from shared.resume_fill import (
    ObservedPdfGeometry,
    PageFillReleaseStatus,
    PdfPageGeometry,
    assess_page_fill_release,
)


ROOT = Path(__file__).resolve().parents[1]
BASELINE = (
    ROOT
    / "docs"
    / "resume_generator_reviews"
    / "page_fill_observed_geometry_2026-09-03.json"
)


def _bbox_xml(*, y_max: float = 700.0) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
      <page width="612.0" height="792.0"><flow><block><line>
        <word xMin="36.0" yMin="40.0" xMax="80.0" yMax="51.0">Akshat</word>
        <word xMin="36.0" yMin="689.0" xMax="90.0" yMax="{y_max}">Interests</word>
      </line></block></flow></page>
    </doc></body></html>"""


def test_geometry_observer_uses_configured_usable_page(monkeypatch, tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(fill.shutil, "which", lambda _name: "/fake/pdftotext")
    monkeypatch.setattr(
        fill.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=_bbox_xml(), stderr=""),
    )

    geometry = inspect_pdf_geometry(pdf, top_margin_pt=36.0, bottom_margin_pt=36.0)

    assert geometry.page_count == 1
    assert geometry.pages[0].word_count == 2
    assert geometry.pages[0].content_top_pt == 40.0
    assert geometry.pages[0].content_bottom_pt == 700.0
    assert geometry.pages[0].raw_bottom_whitespace_pt == 92.0
    assert geometry.usable_bottom_whitespace_pt == 56.0
    assert geometry.usable_fill_ratio == pytest.approx((700.0 - 36.0) / 720.0)


def test_geometry_observer_fails_on_invalid_bbox(monkeypatch, tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(fill.shutil, "which", lambda _name: "/fake/pdftotext")
    monkeypatch.setattr(
        fill.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="not xml", stderr=""),
    )

    with pytest.raises(PdfGeometryError, match="invalid bbox XML"):
        inspect_pdf_geometry(pdf, top_margin_pt=36.0, bottom_margin_pt=36.0)


def test_geometry_observer_requires_renderer_owned_margins(tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-fake")

    with pytest.raises(PdfGeometryError, match="margins cannot be negative"):
        inspect_pdf_geometry(pdf, top_margin_pt=-1.0, bottom_margin_pt=36.0)


def test_existing_artifact_geometry_matches_frozen_audit_baseline():
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is unavailable")
    audit = json.loads(BASELINE.read_text(encoding="utf-8"))
    missing = [row["pdf"] for row in audit["artifacts"] if not (ROOT / row["pdf"]).is_file()]
    if missing:
        pytest.skip("local calibration artifact(s) unavailable: " + ", ".join(missing))

    observed = {}
    for row in audit["artifacts"]:
        geometry = inspect_pdf_geometry(
            ROOT / row["pdf"],
            top_margin_pt=row["top_margin_pt"],
            bottom_margin_pt=row["bottom_margin_pt"],
        )
        page = geometry.pages[0]
        observed[row["id"]] = geometry.usable_fill_ratio
        assert geometry.page_count == 1
        assert page.word_count == row["word_count"]
        assert page.content_bottom_pt == pytest.approx(row["last_word_y_max_pt"], abs=0.02)
        assert page.raw_bottom_whitespace_pt == pytest.approx(
            row["raw_bottom_whitespace_pt"], abs=0.02
        )
        assert geometry.usable_bottom_whitespace_pt == pytest.approx(
            row["usable_bottom_whitespace_pt"], abs=0.02
        )
        assert geometry.usable_fill_ratio == pytest.approx(
            row["usable_fill_ratio"], abs=0.00001
        )

    # This ordering is the visual distinction the old bullet-count proxy misses.
    assert observed["amazon-submitted-gold"] > observed["studyfetch-v4"]
    assert observed["studyfetch-v4"] > observed["xpansiv"]
    assert observed["xpansiv"] > observed["spectrum-reach"]


def _observed(fill_ratio: float) -> ObservedPdfGeometry:
    top = 54.0
    bottom = 36.0
    height = 792.0
    content_bottom = top + fill_ratio * (height - top - bottom)
    return ObservedPdfGeometry(
        path=Path("resume.pdf"),
        pages=(
            PdfPageGeometry(
                width_pt=612.0,
                height_pt=height,
                content_top_pt=54.0,
                content_bottom_pt=content_bottom,
                word_count=650,
            ),
        ),
        top_margin_pt=top,
        bottom_margin_pt=bottom,
    )


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (0.9299, PageFillReleaseStatus.BLOCK_UNDERFILLED),
        (0.93, PageFillReleaseStatus.READY_NEAR_FLOOR),
        (0.9499, PageFillReleaseStatus.READY_NEAR_FLOOR),
        (0.95, PageFillReleaseStatus.READY),
        (0.98, PageFillReleaseStatus.READY),
        (0.9801, PageFillReleaseStatus.READY_DENSE),
    ],
)
def test_v2_fill_release_thresholds_are_observed_and_bounded(ratio, expected):
    assessment = assess_page_fill_release(_observed(ratio), proof_units=10)

    assert assessment.status is expected
    assert assessment.release_allowed is (
        expected is not PageFillReleaseStatus.BLOCK_UNDERFILLED
    )
    assert assessment.proof_units == 10


def test_fill_release_assessment_requires_exactly_one_page():
    geometry = _observed(0.95)
    two_pages = ObservedPdfGeometry(
        path=geometry.path,
        pages=geometry.pages + geometry.pages,
        top_margin_pt=geometry.top_margin_pt,
        bottom_margin_pt=geometry.bottom_margin_pt,
    )

    with pytest.raises(PdfGeometryError, match="requires exactly one page"):
        assess_page_fill_release(two_pages)
