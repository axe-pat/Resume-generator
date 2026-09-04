"""Pure planning primitives for an observed, quality-first resume fill loop.

This module is intentionally not imported by the live generator.  It records the
decision order for the v2 shadow implementation without changing legacy output.
Content selection/admission remains authoritative; page fill may only choose a
layout or request an already-approved proof-unit addition/removal.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PdfGeometryError(RuntimeError):
    """Raised when observed PDF text geometry cannot be inspected."""


@dataclass(frozen=True)
class PdfPageGeometry:
    width_pt: float
    height_pt: float
    content_top_pt: float | None
    content_bottom_pt: float | None
    word_count: int

    @property
    def raw_bottom_whitespace_pt(self) -> float | None:
        if self.content_bottom_pt is None:
            return None
        return self.height_pt - self.content_bottom_pt


@dataclass(frozen=True)
class ObservedPdfGeometry:
    path: Path
    pages: tuple[PdfPageGeometry, ...]
    top_margin_pt: float
    bottom_margin_pt: float

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def usable_fill_ratio(self) -> float | None:
        """Fraction of the configured one-page usable height occupied by text.

        Poppler coordinates run downward from the page top.  This intentionally
        uses the configured margins rather than inferred first/last-word padding,
        so two documents with different page layouts remain comparable.
        """

        if self.page_count != 1:
            return None
        page = self.pages[0]
        if page.content_bottom_pt is None:
            return 0.0
        usable_bottom = page.height_pt - self.bottom_margin_pt
        usable_height = usable_bottom - self.top_margin_pt
        if usable_height <= 0:
            return None
        return (page.content_bottom_pt - self.top_margin_pt) / usable_height

    @property
    def usable_bottom_whitespace_pt(self) -> float | None:
        if self.page_count != 1 or self.pages[0].content_bottom_pt is None:
            return None
        return (
            self.pages[0].height_pt
            - self.bottom_margin_pt
            - self.pages[0].content_bottom_pt
        )


def _parse_bbox_xml(xml_text: str) -> tuple[PdfPageGeometry, ...]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise PdfGeometryError(f"pdftotext returned invalid bbox XML: {exc}") from exc

    pages: list[PdfPageGeometry] = []
    for element in root.iter():
        if not element.tag.endswith("page"):
            continue
        try:
            width = float(element.attrib["width"])
            height = float(element.attrib["height"])
        except (KeyError, ValueError) as exc:
            raise PdfGeometryError("bbox page is missing numeric width/height") from exc
        word_boxes = [
            word
            for word in element.iter()
            if word.tag.endswith("word")
        ]
        try:
            tops = [float(word.attrib["yMin"]) for word in word_boxes]
            bottoms = [float(word.attrib["yMax"]) for word in word_boxes]
        except (KeyError, ValueError) as exc:
            raise PdfGeometryError("bbox word is missing numeric yMin/yMax") from exc
        pages.append(
            PdfPageGeometry(
                width_pt=width,
                height_pt=height,
                content_top_pt=min(tops) if tops else None,
                content_bottom_pt=max(bottoms) if bottoms else None,
                word_count=len(word_boxes),
            )
        )
    if not pages:
        raise PdfGeometryError("pdftotext bbox output contains no pages")
    return tuple(pages)


def inspect_pdf_geometry(
    path: str | Path,
    *,
    top_margin_pt: float,
    bottom_margin_pt: float,
) -> ObservedPdfGeometry:
    """Inspect actual word bounds without participating in live release.

    This observer is deliberately separate from ``resume_artifacts``.  Callers
    must supply renderer-owned margins; PDFs do not reliably encode them.
    """

    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise PdfGeometryError(f"PDF does not exist: {pdf_path}")
    if top_margin_pt < 0 or bottom_margin_pt < 0:
        raise PdfGeometryError("configured margins cannot be negative")
    executable = shutil.which("pdftotext")
    if not executable:
        raise PdfGeometryError("pdftotext is required for bbox geometry inspection")
    try:
        result = subprocess.run(
            [executable, "-bbox-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise PdfGeometryError(f"could not inspect {pdf_path}: {detail.strip()}") from exc
    pages = _parse_bbox_xml(result.stdout)
    if any(top_margin_pt + bottom_margin_pt >= page.height_pt for page in pages):
        raise PdfGeometryError("configured margins consume the full page height")
    return ObservedPdfGeometry(
        path=pdf_path,
        pages=pages,
        top_margin_pt=float(top_margin_pt),
        bottom_margin_pt=float(bottom_margin_pt),
    )


class FillAction(str, Enum):
    ACCEPT = "accept"
    ACCEPT_UNDERFILL = "accept-underfill"
    TRY_LOOSER_LAYOUT = "try-looser-layout"
    TRY_TIGHTER_LAYOUT = "try-tighter-layout"
    ADD_APPROVED_PROOF = "add-approved-proof"
    REMOVE_LOWEST_VALUE_PROOF = "remove-lowest-value-proof"
    BLOCK = "block"


class PageFillReleaseStatus(str, Enum):
    """Observed one-page fill outcome used by the v2 publication boundary."""

    READY = "ready"
    READY_NEAR_FLOOR = "ready-near-floor"
    READY_DENSE = "ready-dense"
    BLOCK_UNDERFILLED = "block-underfilled"


@dataclass(frozen=True)
class PageFillReleasePolicy:
    """Calibrated observed-geometry thresholds for a rendered resume.

    ``minimum_release_fill_ratio`` is a hard v2 floor: documents below it are
    visibly sparse in the frozen corpus. The neighboring bands are warnings,
    not content mutation requests. No policy decision may author prose.
    """

    minimum_release_fill_ratio: float = 0.93
    near_floor_warning_ratio: float = 0.95
    dense_warning_ratio: float = 0.98

    def __post_init__(self) -> None:
        if not (
            0
            < self.minimum_release_fill_ratio
            <= self.near_floor_warning_ratio
            <= self.dense_warning_ratio
            <= 1
        ):
            raise ValueError(
                "page-fill thresholds must satisfy 0 < minimum <= near-floor "
                "<= dense <= 1"
            )


V2_PAGE_FILL_RELEASE_POLICY = PageFillReleasePolicy()


@dataclass(frozen=True)
class PageFillReleaseAssessment:
    status: PageFillReleaseStatus
    observed_fill_ratio: float
    usable_bottom_whitespace_pt: float
    minimum_release_fill_ratio: float
    proof_units: int | None = None

    @property
    def release_allowed(self) -> bool:
        return self.status is not PageFillReleaseStatus.BLOCK_UNDERFILLED

    @property
    def warning(self) -> str | None:
        if self.status is PageFillReleaseStatus.READY_NEAR_FLOOR:
            return (
                "observed page fill is above the release floor but inside the "
                "near-floor review band"
            )
        if self.status is PageFillReleaseStatus.READY_DENSE:
            return (
                "observed page fill exceeds the preferred dense-page threshold; "
                "the independent one-page and text-parity gates still passed"
            )
        return None


@dataclass(frozen=True)
class OptionalSkillRowReleasePolicy:
    """Portable headroom required after a distinct sixth Skills row renders."""

    maximum_fill_ratio: float = 0.97
    minimum_bottom_whitespace_pt: float = 18.0

    def __post_init__(self) -> None:
        if not 0 < self.maximum_fill_ratio <= 1:
            raise ValueError("optional Skills maximum fill ratio must be in (0, 1]")
        if self.minimum_bottom_whitespace_pt < 0:
            raise ValueError("optional Skills bottom whitespace cannot be negative")


OPTIONAL_SKILL_ROW_RELEASE_POLICY = OptionalSkillRowReleasePolicy()


@dataclass(frozen=True)
class OptionalSkillRowReleaseAssessment:
    allowed: bool
    observed_fill_ratio: float
    usable_bottom_whitespace_pt: float
    reason: str


def assess_optional_skill_row_release(
    page_fill: PageFillReleaseAssessment,
    *,
    distinct_signal: bool,
    policy: OptionalSkillRowReleasePolicy = OPTIONAL_SKILL_ROW_RELEASE_POLICY,
) -> OptionalSkillRowReleaseAssessment:
    """Gate a rendered sixth Skills row without treating whitespace as evidence.

    Relevance/distinctness is decided before rendering. Geometry can veto the
    optional row, never justify it.
    """

    if not distinct_signal:
        reason = "sixth Skills row has no independently funded distinct signal"
        allowed = False
    elif page_fill.observed_fill_ratio > policy.maximum_fill_ratio + 1e-9:
        reason = (
            f"rendered fill {page_fill.observed_fill_ratio:.1%} exceeds the optional-row "
            f"ceiling {policy.maximum_fill_ratio:.1%}"
        )
        allowed = False
    elif page_fill.usable_bottom_whitespace_pt < policy.minimum_bottom_whitespace_pt - 1e-9:
        reason = (
            f"rendered bottom headroom {page_fill.usable_bottom_whitespace_pt:.1f}pt is below "
            f"the optional-row floor {policy.minimum_bottom_whitespace_pt:.1f}pt"
        )
        allowed = False
    else:
        reason = "distinct sixth Skills row retains reviewed portable page headroom"
        allowed = True
    return OptionalSkillRowReleaseAssessment(
        allowed=allowed,
        observed_fill_ratio=page_fill.observed_fill_ratio,
        usable_bottom_whitespace_pt=page_fill.usable_bottom_whitespace_pt,
        reason=reason,
    )


def assess_page_fill_release(
    geometry: ObservedPdfGeometry,
    *,
    policy: PageFillReleasePolicy = V2_PAGE_FILL_RELEASE_POLICY,
    proof_units: int | None = None,
) -> PageFillReleaseAssessment:
    """Classify observed PDF geometry without estimating or editing content."""

    if geometry.page_count != 1:
        raise PdfGeometryError(
            f"page-fill release assessment requires exactly one page; observed "
            f"{geometry.page_count}"
        )
    ratio = geometry.usable_fill_ratio
    whitespace = geometry.usable_bottom_whitespace_pt
    if ratio is None or whitespace is None:
        raise PdfGeometryError("single-page PDF has no inspectable content bounds")
    if ratio < 0 or ratio > 1.5:
        raise PdfGeometryError(
            f"observed fill ratio {ratio:.4f} is outside the inspectable range"
        )

    epsilon = 1e-9
    if ratio < policy.minimum_release_fill_ratio - epsilon:
        status = PageFillReleaseStatus.BLOCK_UNDERFILLED
    elif ratio < policy.near_floor_warning_ratio - epsilon:
        status = PageFillReleaseStatus.READY_NEAR_FLOOR
    elif ratio > policy.dense_warning_ratio + epsilon:
        status = PageFillReleaseStatus.READY_DENSE
    else:
        status = PageFillReleaseStatus.READY
    return PageFillReleaseAssessment(
        status=status,
        observed_fill_ratio=ratio,
        usable_bottom_whitespace_pt=whitespace,
        minimum_release_fill_ratio=policy.minimum_release_fill_ratio,
        proof_units=proof_units,
    )


class ProofKind(str, Enum):
    EXPERIENCE = "experience"
    PROJECT = "project"
    SKILL = "skill"
    COMMUNITY = "community"
    INTEREST = "interest"


@dataclass(frozen=True)
class AdaptiveFillPolicy:
    """Profile-owned proof bounds plus a preferred observed fill band."""

    minimum_proof_units: int
    target_proof_units: int
    maximum_proof_units: int
    minimum_fill_ratio: float = 0.93
    maximum_fill_ratio: float = 0.98
    profile_id: str = "unspecified"
    funded_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (
            0 < self.minimum_proof_units
            <= self.target_proof_units
            <= self.maximum_proof_units
        ):
            raise ValueError("proof-unit bounds must satisfy 0 < minimum <= target <= maximum")
        if not 0 < self.minimum_fill_ratio < self.maximum_fill_ratio <= 1:
            raise ValueError("fill ratios must satisfy 0 < minimum < maximum <= 1")


@dataclass(frozen=True)
class PageFillObservation:
    """Observed PDF geometry and the bounded repair options still available."""

    page_count: int
    usable_fill_ratio: float
    proof_units: int
    looser_layout_available: bool = False
    tighter_layout_available: bool = False
    approved_addition_available: bool = False
    removable_lowest_value_proof_available: bool = False


@dataclass(frozen=True)
class FillDecision:
    action: FillAction
    reason: str


@dataclass(frozen=True)
class LayoutCandidate:
    """One reviewed renderer layout; higher compactness consumes less height."""

    layout_id: str
    compactness: int
    sanctioned: bool = True
    reversible: bool = True


@dataclass(frozen=True)
class ProofVariant:
    """Selection-owned material used by the inert assembly selector.

    ``material_rank`` is ordinal (1 is strongest). ``line_cost`` is an observed
    or renderer-calibrated line estimate, not a character count. The selector
    never edits the variant text.
    """

    variant_id: str
    kind: ProofKind
    material_rank: int
    line_cost: float
    funded_criteria: tuple[str, ...]
    marginal_page_value: float
    admitted: bool = True
    protected: bool = False


@dataclass(frozen=True)
class CandidateAudit:
    variant_id: str
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AdaptiveAssemblyRequest:
    policy: AdaptiveFillPolicy
    selected: tuple[ProofVariant, ...]
    unselected_candidates: tuple[ProofVariant, ...]
    geometry: ObservedPdfGeometry
    current_layout_id: str
    layouts: tuple[LayoutCandidate, ...]


@dataclass(frozen=True)
class AdaptiveAssemblyDecision:
    action: FillAction
    reason_code: str
    audit_reasons: tuple[str, ...]
    selected_variant_ids: tuple[str, ...]
    proof_units_before: int
    proof_units_after: int
    observed_fill_ratio: float | None
    next_layout_id: str | None = None
    added_variant_id: str | None = None
    removed_variant_id: str | None = None
    candidate_audit: tuple[CandidateAudit, ...] = ()

    @property
    def release_allowed(self) -> bool:
        return self.action in {FillAction.ACCEPT, FillAction.ACCEPT_UNDERFILL}


def _next_layout(
    current_layout_id: str,
    layouts: tuple[LayoutCandidate, ...],
    *,
    tighter: bool,
) -> LayoutCandidate | None:
    current = next((item for item in layouts if item.layout_id == current_layout_id), None)
    if current is None:
        return None
    eligible = [
        item
        for item in layouts
        if item.sanctioned
        and item.reversible
        and (
            item.compactness > current.compactness
            if tighter
            else item.compactness < current.compactness
        )
    ]
    if not eligible:
        return None
    return (
        min(eligible, key=lambda item: (item.compactness, item.layout_id))
        if tighter
        else max(eligible, key=lambda item: (item.compactness, item.layout_id))
    )


def _audit_addition_candidates(
    request: AdaptiveAssemblyRequest,
) -> tuple[CandidateAudit, ...]:
    selected_ids = {item.variant_id for item in request.selected}
    covered = {
        criterion
        for item in request.selected
        for criterion in item.funded_criteria
    }
    profile_funded = set(request.policy.funded_criteria)
    audits: list[CandidateAudit] = []
    for candidate in request.unselected_candidates:
        reasons: list[str] = []
        if candidate.variant_id in selected_ids:
            reasons.append("already-selected")
        if not candidate.admitted:
            reasons.append("not-admitted")
        if candidate.kind not in {ProofKind.EXPERIENCE, ProofKind.PROJECT}:
            reasons.append("non-proof-filler-kind")
        if candidate.marginal_page_value <= 0:
            reasons.append("non-positive-marginal-page-value")
        if candidate.line_cost <= 0:
            reasons.append("non-positive-line-cost")
        funded = set(candidate.funded_criteria) & profile_funded
        if not funded:
            reasons.append("criterion-not-funded-by-profile")
        elif not (funded - covered):
            reasons.append("no-distinct-funded-criterion")
        audits.append(CandidateAudit(candidate.variant_id, not reasons, tuple(reasons)))
    return tuple(audits)


def select_adaptive_assembly(request: AdaptiveAssemblyRequest) -> AdaptiveAssemblyDecision:
    """Select the next shadow-only layout/content action without rewriting prose."""

    policy = request.policy
    selected_ids = tuple(item.variant_id for item in request.selected)
    count = len(request.selected)
    ratio = request.geometry.usable_fill_ratio
    base = dict(
        selected_variant_ids=selected_ids,
        proof_units_before=count,
        proof_units_after=count,
        observed_fill_ratio=ratio,
    )
    if len(set(selected_ids)) != count:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "DUPLICATE_SELECTED_VARIANT",
            ("selected variant IDs must be unique",),
            **base,
        )
    invalid_selected = [
        item.variant_id
        for item in request.selected
        if not item.admitted
        or item.kind not in {ProofKind.EXPERIENCE, ProofKind.PROJECT}
        or item.material_rank < 1
        or item.line_cost <= 0
    ]
    if invalid_selected:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "INVALID_SELECTED_PROOF",
            ("selected proof is not admitted/valid: " + ", ".join(invalid_selected),),
            **base,
        )
    if not policy.minimum_proof_units <= count <= policy.maximum_proof_units:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "PROFILE_BUDGET_VIOLATION",
            (
                f"{policy.profile_id} permits {policy.minimum_proof_units}-"
                f"{policy.maximum_proof_units} proof units; observed {count}",
            ),
            **base,
        )
    current_layout = next(
        (item for item in request.layouts if item.layout_id == request.current_layout_id),
        None,
    )
    if current_layout is None or not current_layout.sanctioned:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "UNSANCTIONED_CURRENT_LAYOUT",
            (f"current layout {request.current_layout_id!r} is not sanctioned",),
            **base,
        )
    if request.geometry.page_count < 1:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "GEOMETRY_UNINSPECTABLE",
            ("observed PDF contains no pages",),
            **base,
        )
    if ratio is None and request.geometry.page_count == 1:
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "GEOMETRY_UNINSPECTABLE",
            ("single-page PDF has no usable fill measurement",),
            **base,
        )

    overflowed = request.geometry.page_count > 1 or (
        ratio is not None and ratio > policy.maximum_fill_ratio
    )
    if overflowed:
        tighter = _next_layout(request.current_layout_id, request.layouts, tighter=True)
        if tighter:
            return AdaptiveAssemblyDecision(
                FillAction.TRY_TIGHTER_LAYOUT,
                "TIGHTER_LAYOUT_BEFORE_REMOVAL",
                (f"try sanctioned reversible layout {tighter.layout_id} before removing proof",),
                next_layout_id=tighter.layout_id,
                **base,
            )
        removable = [
            item
            for item in request.selected
            if not item.protected and item.admitted
        ]
        if count > policy.minimum_proof_units and removable:
            removed = min(
                removable,
                key=lambda item: (
                    item.marginal_page_value,
                    -item.material_rank,
                    -item.line_cost,
                    item.variant_id,
                ),
            )
            remaining = tuple(item for item in selected_ids if item != removed.variant_id)
            return AdaptiveAssemblyDecision(
                FillAction.REMOVE_LOWEST_VALUE_PROOF,
                "REMOVE_UNPROTECTED_LOWEST_MARGINAL_PROOF",
                (
                    f"no tighter sanctioned layout remains; remove {removed.variant_id}",
                    f"marginal_page_value={removed.marginal_page_value:g}; "
                    f"material_rank={removed.material_rank}; line_cost={removed.line_cost:g}",
                ),
                selected_variant_ids=remaining,
                proof_units_before=count,
                proof_units_after=count - 1,
                observed_fill_ratio=ratio,
                removed_variant_id=removed.variant_id,
            )
        return AdaptiveAssemblyDecision(
            FillAction.BLOCK,
            "OVERFLOW_WITHOUT_BOUNDED_REPAIR",
            ("no tighter layout or removable unprotected proof remains",),
            **base,
        )

    if ratio is not None and ratio < policy.minimum_fill_ratio:
        looser = _next_layout(request.current_layout_id, request.layouts, tighter=False)
        if looser:
            return AdaptiveAssemblyDecision(
                FillAction.TRY_LOOSER_LAYOUT,
                "RELAX_LAYOUT_BEFORE_ADDITION",
                (f"try sanctioned reversible layout {looser.layout_id} before adding proof",),
                next_layout_id=looser.layout_id,
                **base,
            )
        audits = _audit_addition_candidates(request)
        eligible_ids = {item.variant_id for item in audits if item.eligible}
        eligible = [
            item for item in request.unselected_candidates if item.variant_id in eligible_ids
        ]
        if count < policy.maximum_proof_units and eligible:
            added = min(
                eligible,
                key=lambda item: (
                    -item.marginal_page_value,
                    item.material_rank,
                    -item.line_cost,
                    item.variant_id,
                ),
            )
            return AdaptiveAssemblyDecision(
                FillAction.ADD_APPROVED_PROOF,
                "ADD_DISTINCT_ADMITTED_PROOF",
                (
                    f"{added.variant_id} adds a distinct profile-funded criterion",
                    f"marginal_page_value={added.marginal_page_value:g}; "
                    f"material_rank={added.material_rank}; line_cost={added.line_cost:g}",
                ),
                selected_variant_ids=selected_ids + (added.variant_id,),
                proof_units_before=count,
                proof_units_after=count + 1,
                observed_fill_ratio=ratio,
                added_variant_id=added.variant_id,
                candidate_audit=audits,
            )
        reason = (
            "profile maximum already reached"
            if count >= policy.maximum_proof_units
            else "no candidate clears admission, funded-distinctness, and positive marginal value"
        )
        return AdaptiveAssemblyDecision(
            FillAction.ACCEPT_UNDERFILL,
            "QUALITY_PROTECTED_UNDERFILL",
            (reason,),
            candidate_audit=audits,
            **base,
        )

    return AdaptiveAssemblyDecision(
        FillAction.ACCEPT,
        "OBSERVED_FILL_IN_BAND",
        ("one-page observed geometry is inside the profile fill band",),
        **base,
    )


def decide_adaptive_fill(
    observation: PageFillObservation,
    policy: AdaptiveFillPolicy,
) -> FillDecision:
    """Choose the next deterministic assembly action.

    Layout is always tried before changing content.  Content changes are requests
    to the selection layer, never rewrites: additions must already have cleared
    admission, distinctness, and marginal-value review; removals must already be
    ranked as the lowest-value unprotected proof.  If no strong addition exists,
    underfill is accepted rather than backfilled with weak evidence.
    """

    if observation.page_count < 1:
        return FillDecision(FillAction.BLOCK, "render did not produce an inspectable page")
    if not 0 <= observation.usable_fill_ratio <= 1.5:
        return FillDecision(FillAction.BLOCK, "observed fill ratio is outside the inspectable range")
    if not policy.minimum_proof_units <= observation.proof_units <= policy.maximum_proof_units:
        return FillDecision(FillAction.BLOCK, "proof count violates the selected profile budget")

    overflowed = observation.page_count > 1
    too_dense = observation.usable_fill_ratio > policy.maximum_fill_ratio
    if overflowed or too_dense:
        if observation.tighter_layout_available:
            return FillDecision(
                FillAction.TRY_TIGHTER_LAYOUT,
                "observed output is overfull; try the next approved compact layout",
            )
        if (
            observation.removable_lowest_value_proof_available
            and observation.proof_units > policy.minimum_proof_units
        ):
            return FillDecision(
                FillAction.REMOVE_LOWEST_VALUE_PROOF,
                "no tighter layout remains; remove only the pre-ranked lowest-value proof",
            )
        return FillDecision(
            FillAction.BLOCK,
            "observed output is overfull and no bounded layout/content repair remains",
        )

    if observation.usable_fill_ratio < policy.minimum_fill_ratio:
        if observation.looser_layout_available:
            return FillDecision(
                FillAction.TRY_LOOSER_LAYOUT,
                "page is underfilled; consume space with approved typography before adding content",
            )
        if (
            observation.approved_addition_available
            and observation.proof_units < policy.maximum_proof_units
        ):
            return FillDecision(
                FillAction.ADD_APPROVED_PROOF,
                "page remains underfilled at the loosest layout and a distinct admitted proof is available",
            )
        return FillDecision(
            FillAction.ACCEPT_UNDERFILL,
            "quality floor outranks page fill; no strong bounded addition is available",
        )

    return FillDecision(FillAction.ACCEPT, "observed one-page output is inside the preferred fill band")


__all__ = [
    "AdaptiveAssemblyDecision",
    "AdaptiveAssemblyRequest",
    "AdaptiveFillPolicy",
    "CandidateAudit",
    "FillAction",
    "FillDecision",
    "LayoutCandidate",
    "ObservedPdfGeometry",
    "PageFillObservation",
    "PageFillReleaseAssessment",
    "PageFillReleasePolicy",
    "PageFillReleaseStatus",
    "PdfGeometryError",
    "PdfPageGeometry",
    "ProofKind",
    "ProofVariant",
    "V2_PAGE_FILL_RELEASE_POLICY",
    "assess_page_fill_release",
    "decide_adaptive_fill",
    "inspect_pdf_geometry",
    "select_adaptive_assembly",
]
