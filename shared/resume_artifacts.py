"""Observed DOCX-to-PDF release checks for generated resumes."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET

from shared.resume_lint import ArtifactInspectionError, RenderedPdfArtifact, inspect_pdf_artifact
from shared.resume_fill import (
    PageFillReleaseAssessment,
    PageFillReleasePolicy,
    PdfGeometryError,
    assess_page_fill_release,
    inspect_pdf_geometry,
)


class ResumeArtifactError(RuntimeError):
    pass


class ResumePageUnderfillError(ResumeArtifactError):
    """A recoverable, geometry-only one-page underfill result.

    This signal is deliberately narrower than ``ResumeArtifactError``.  It is
    raised only after page-count and rendered-text parity have both passed, so a
    caller may safely retry the *identical* content with a sanctioned looser
    layout without mistaking clipping, conversion, or content loss for whitespace.
    """

    def __init__(self, assessment: PageFillReleaseAssessment):
        self.assessment = assessment
        proof_detail = (
            f"; selected {assessment.proof_units} proof units"
            if assessment.proof_units is not None
            else ""
        )
        self.detail = (
            "V2_PAGE_UNDERFILLED: observed usable fill "
            f"{assessment.observed_fill_ratio:.1%} is below the "
            f"{assessment.minimum_release_fill_ratio:.1%} release floor; "
            f"{max(0.0, assessment.usable_bottom_whitespace_pt):.1f}pt "
            f"of usable height remains{proof_detail}. Rerun the identical content "
            "with one sanctioned looser layout; do not expand prose or add filler"
        )
        super().__init__(f"Resume PDF failed release checks: {self.detail}")


class ResumePageDensityError(ResumeArtifactError):
    """A recoverable, geometry-only page-density result.

    Text and one-page parity have already passed when this is raised.  The
    document is nevertheless too close to the bottom edge to be portable
    across Word/LibreOffice font metrics, so callers may retry the identical
    content once at the immediate tighter layout tier.
    """

    def __init__(self, assessment: PageFillReleaseAssessment):
        self.assessment = assessment
        self.detail = (
            "V2_PAGE_TOO_DENSE: observed usable fill "
            f"{assessment.observed_fill_ratio:.1%} exceeds the portable "
            "98.0% ceiling; rerender the identical content once at the next "
            "sanctioned tighter layout"
        )
        super().__init__(f"Resume PDF failed release checks: {self.detail}")


@dataclass(frozen=True)
class ResumeArtifactRelease:
    docx_path: Path
    pdf: RenderedPdfArtifact
    missing_fragments: tuple[str, ...]
    page_fill: PageFillReleaseAssessment | None = None

    @property
    def release_ready(self) -> bool:
        return self.pdf.page_count == 1 and not self.missing_fragments


_TEXT_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.I)
_BULLET_LINE_RE = re.compile(r"^\s*[\u2022\u25cf\-*]\s+(.+?)\s*$")
_SECTION_HEADINGS = {
    "EXPERIENCE",
    "PROJECTS",
    "PROJECTS & CONSULTING",
    "SKILLS",
    "SKILLS & INTERESTS",
}
_WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _compact(value: str) -> str:
    return "".join(_TEXT_TOKEN_RE.findall(value.casefold().replace("’", "'")))


def _soffice_executable() -> str:
    candidates = (
        shutil.which("soffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ResumeArtifactError("LibreOffice soffice executable is unavailable")


def inspect_docx_vertical_margins(path: str | Path) -> tuple[float, float]:
    """Read renderer-owned top/bottom page margins from the produced DOCX.

    Word stores margins in twentieths of a point. A one-page resume should not
    contain conflicting section margins; accepting the first value in that case
    would make the observed fill ratio ambiguous, so this fails closed.
    """

    source = Path(path)
    try:
        with zipfile.ZipFile(source) as archive:
            document_xml = archive.read("word/document.xml")
        root = ET.fromstring(document_xml)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ResumeArtifactError(
            f"could not inspect DOCX page margins in {source}: {exc}"
        ) from exc

    attr_top = f"{{{_WORDPROCESSING_NS}}}top"
    attr_bottom = f"{{{_WORDPROCESSING_NS}}}bottom"
    margin_nodes = root.findall(f".//{{{_WORDPROCESSING_NS}}}sectPr/{{{_WORDPROCESSING_NS}}}pgMar")
    margins: list[tuple[float, float]] = []
    for node in margin_nodes:
        try:
            top_twips = float(node.attrib[attr_top])
            bottom_twips = float(node.attrib[attr_bottom])
        except (KeyError, ValueError) as exc:
            raise ResumeArtifactError("DOCX section has invalid top/bottom page margins") from exc
        if top_twips < 0 or bottom_twips < 0:
            raise ResumeArtifactError("DOCX page margins cannot be negative")
        margins.append((top_twips / 20.0, bottom_twips / 20.0))
    if not margins:
        raise ResumeArtifactError("DOCX contains no explicit top/bottom page margins")
    unique = set(margins)
    if len(unique) != 1:
        raise ResumeArtifactError(
            f"DOCX contains conflicting vertical page margins: {sorted(unique)}"
        )
    return margins[0]


def _missing_fragments(rendered_text: str, expected_fragments: Iterable[str]) -> tuple[str, ...]:
    compact_render = _compact(rendered_text)
    missing: list[str] = []
    for fragment in expected_fragments:
        normalized = _compact(fragment)
        if normalized and normalized not in compact_render:
            missing.append(fragment)
    return tuple(missing)


def _is_section_heading(value: str) -> bool:
    normalized = " ".join(value.upper().split())
    return normalized in _SECTION_HEADINGS or normalized.startswith("SECTION ")


def _section_fragments(text: str, *, include_headers: bool) -> list[str]:
    """Parse canonical section lines, joining physical bullet continuations."""
    fragments: list[str] = []
    current_bullet: list[str] = []

    def flush_bullet() -> None:
        if current_bullet:
            fragments.append(" ".join(current_bullet))
            current_bullet.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        bullet = _BULLET_LINE_RE.match(raw_line)
        if bullet:
            flush_bullet()
            current_bullet.append(bullet.group(1).strip())
            continue
        if not stripped:
            flush_bullet()
            continue

        # A pipe-delimited employer/project row is a new header even when the
        # preceding bullet was not followed by a blank line. Other non-empty
        # lines following a bullet are physical continuations and must remain
        # part of the parity assertion.
        is_header = "|" in stripped or _is_section_heading(stripped)
        if current_bullet and not is_header:
            current_bullet.append(stripped)
            continue
        flush_bullet()

        if include_headers and not _is_section_heading(stripped):
            # Header components render in separate runs/lines, so assert each
            # canonical component independently rather than relying on layout.
            parts = [part.strip() for part in stripped.split("|") if part.strip()]
            fragments.extend(parts or [stripped])

    flush_bullet()
    return fragments


def expected_resume_fragments(sections: Mapping[str, str]) -> tuple[str, ...]:
    """Return all canonical resume content expected in the rendered PDF.

    The contract covers the complete summary, employer/project header fields,
    every logical Experience/Projects bullet, and every Skills row. Physical
    source line wrapping never weakens the bullet-level assertion.
    """
    fragments: list[str] = []
    summary = " ".join(str(sections.get("summary_section", "") or "").split())
    if summary:
        fragments.append(summary)
    fragments.extend(
        _section_fragments(
            str(sections.get("experience_section", "") or ""),
            include_headers=True,
        )
    )
    fragments.extend(
        _section_fragments(
            str(sections.get("projects_section", "") or ""),
            include_headers=True,
        )
    )
    fragments.extend(
        _section_fragments(
            str(sections.get("skills_section", "") or ""),
            include_headers=False,
        )
    )
    return tuple(fragments)


def render_resume_artifact(
    docx_path: str | Path,
    *,
    expected_fragments: Iterable[str] = (),
    pdf_path: str | Path | None = None,
    page_fill_policy: PageFillReleasePolicy | None = None,
    proof_units: int | None = None,
) -> ResumeArtifactRelease:
    """Render in an isolated LibreOffice profile, then inspect real PDF output.

    Conversion happens in a temporary directory, so a failed render cannot
    overwrite an earlier valid PDF. The destination is replaced only after a
    complete PDF has been produced and inspected successfully.
    """
    source = Path(docx_path).resolve()
    if not source.is_file():
        raise ResumeArtifactError(f"DOCX does not exist: {source}")
    destination = Path(pdf_path).resolve() if pdf_path else source.with_suffix(".pdf")
    destination.parent.mkdir(parents=True, exist_ok=True)

    staged_path: Path | None = None
    fill_assessment: PageFillReleaseAssessment | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="resume-render-") as temp_name:
            temp_root = Path(temp_name)
            render_dir = temp_root / "rendered"
            profile_dir = temp_root / "libreoffice-profile"
            render_dir.mkdir()
            profile_dir.mkdir()
            command = [
                _soffice_executable(),
                "--headless",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(render_dir),
                str(source),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "unknown conversion error").strip()
                raise ResumeArtifactError(f"LibreOffice conversion failed: {detail}")
            rendered = render_dir / f"{source.stem}.pdf"
            if not rendered.is_file():
                detail = (result.stdout or result.stderr or "no PDF produced").strip()
                raise ResumeArtifactError(f"LibreOffice did not produce the expected PDF: {detail}")
            # Stage beside the live destination, validate the staged bytes, then
            # atomically publish. A two-page or content-mismatched candidate can
            # never overwrite an earlier valid PDF.
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.stem}.candidate-",
                suffix=".pdf",
                dir=destination.parent,
                delete=False,
            ) as staged:
                staged_path = Path(staged.name)
            shutil.copy2(rendered, staged_path)
            artifact = inspect_pdf_artifact(staged_path)
            missing = _missing_fragments(artifact.text, expected_fragments)
            failures: list[str] = []
            underfill_error: ResumePageUnderfillError | None = None
            if artifact.page_count != 1:
                failures.append(f"observed {artifact.page_count} pages (expected exactly 1)")
            if missing:
                failures.append(f"{len(missing)} expected text fragment(s) missing")
            if page_fill_policy is not None and artifact.page_count == 1:
                top_margin_pt, bottom_margin_pt = inspect_docx_vertical_margins(source)
                geometry = inspect_pdf_geometry(
                    staged_path,
                    top_margin_pt=top_margin_pt,
                    bottom_margin_pt=bottom_margin_pt,
                )
                fill_assessment = assess_page_fill_release(
                    geometry,
                    policy=page_fill_policy,
                    proof_units=proof_units,
                )
                if not fill_assessment.release_allowed:
                    underfill_error = ResumePageUnderfillError(fill_assessment)
            if failures:
                if underfill_error is not None:
                    failures.append(underfill_error.detail)
                raise ResumeArtifactError(
                    "Resume PDF failed release checks: " + "; ".join(failures)
                )
            if underfill_error is not None:
                raise underfill_error
            staged_path.replace(destination)
            staged_path = None
    except (
        OSError,
        subprocess.TimeoutExpired,
        ArtifactInspectionError,
        PdfGeometryError,
    ) as exc:
        raise ResumeArtifactError(str(exc)) from exc
    finally:
        if staged_path is not None:
            try:
                staged_path.unlink()
            except FileNotFoundError:
                pass

    durable = RenderedPdfArtifact(destination, artifact.page_count, artifact.text)
    return ResumeArtifactRelease(
        docx_path=source,
        pdf=durable,
        missing_fragments=(),
        page_fill=fill_assessment,
    )
