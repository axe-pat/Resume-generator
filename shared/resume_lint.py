"""Deterministic assembly and release checks for generated resumes.

This module owns only document-level rules.  It consumes the profile/allocation
decision, selected bullet metadata, and rendered artifact; it does not reroute a
JD, admit variants, rewrite prose, or assign a model score.

Two policies are exposed deliberately:

``ASSEMBLY_POLICY``
    Runs before rendering and checks the structured page contract.

``RELEASE_POLICY``
    Adds observed PDF page count and rendered-text parity.  A resume is not
    release-ready merely because the pre-render estimate says it should fit.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Sequence

from shared.resume_profiles import (
    ExperienceAllocationPlan,
    FluoPlacement,
    ProfileFamily,
    SummaryMode,
    get_profile,
    skills_section_heading,
    validate_experience_allocation,
    validate_summary_identity,
)


ASSEMBLY_LINT_VERSION = "2026-08-29.1"


class LintSeverity(str, Enum):
    BLOCKER = "blocker"
    WARNING = "warning"


@dataclass(frozen=True)
class LintIssue:
    code: str
    severity: LintSeverity
    message: str
    locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class LintReport:
    issues: tuple[LintIssue, ...]
    artifact_required: bool = False
    version: str = ASSEMBLY_LINT_VERSION

    @property
    def blockers(self) -> tuple[LintIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is LintSeverity.BLOCKER)

    @property
    def warnings(self) -> tuple[LintIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is LintSeverity.WARNING)

    @property
    def passed(self) -> bool:
        return not self.blockers

    @property
    def release_ready(self) -> bool:
        return self.artifact_required and self.passed


@dataclass(frozen=True)
class ExperienceBullet:
    text: str
    archetype: str | None = None
    variant_id: str = ""
    story_id: str = ""


@dataclass(frozen=True)
class ExperienceBlock:
    company: str
    title: str
    date_text: str
    bullets: tuple[ExperienceBullet, ...]


@dataclass(frozen=True)
class SkillRow:
    label: str
    text: str


@dataclass(frozen=True)
class ArchetypeContract:
    """Route-owned composition bounds consumed by the assembly linter.

    The linter never invents these targets.  Step 0 / selection supplies them
    from the existing ``bullet_balance`` and route rules.
    """

    minimum_counts: tuple[tuple[str, int], ...] = ()
    maximum_counts: tuple[tuple[str, int], ...] = ()
    minimum_action_plus_impact: int = 0
    maximum_consecutive_diagnostic: int = 2


@dataclass(frozen=True)
class AssembledResume:
    profile_id: str
    identity_heading: str
    summary_text: str
    experience_blocks: tuple[ExperienceBlock, ...]
    skills_heading: str
    skill_rows: tuple[SkillRow, ...]
    allocation_plan: ExperienceAllocationPlan | None = None
    archetype_contract: ArchetypeContract | None = None
    raw_model_output: str = ""
    projects_text: str = ""
    fluo_included: bool | None = None
    fluo_story_family: str | None = None
    rendered_page_count: int | None = None
    rendered_text: str = ""

    @property
    def bullets(self) -> tuple[ExperienceBullet, ...]:
        return tuple(bullet for block in self.experience_blocks for bullet in block.bullets)


@dataclass(frozen=True)
class AssemblyLintPolicy:
    require_raw_section_integrity: bool = True
    require_archetype_metadata: bool = True
    require_rendered_artifact: bool = False
    expected_page_count: int = 1
    long_bullet_chars: int = 260
    repeated_phrase_words: int = 3
    maximum_phrase_warnings: int = 6
    currency_scale_ratio: float = 25.0
    required_model_sections: tuple[str, ...] = ("0", "3", "4")


ASSEMBLY_POLICY = AssemblyLintPolicy()
RELEASE_POLICY = replace(ASSEMBLY_POLICY, require_rendered_artifact=True)


@dataclass(frozen=True)
class RenderedPdfArtifact:
    path: Path
    page_count: int
    text: str


class ArtifactInspectionError(RuntimeError):
    pass


_SECTION_MARKER_RE = re.compile(r"(?im)^\s*SECTION\s+(0|1|2|3B|3|4)\b")
_ANALYSIS_LEAK_MARKERS = (
    "variant selection",
    "story selection",
    "action-first tally",
    "monotony check",
    "monotony alert",
    "selected because",
    "story ordering",
    "wait, re-read",
    "re-check",
)
_BULLET_PREFIX_RE = re.compile(r"^[\s\u2022\u25cf\-*]+")
_RENDERED_BULLET_RE = re.compile(r"(?m)^\s*[\u2022\u25cf\uf0b7]\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_FIGURE_RE = re.compile(
    r"(?<![\w])"
    r"(?P<currency>[$€£])?\s*"
    r"(?P<number>\d+(?:,\d{3})*(?:\.\d+)?(?:\s*[–-]\s*\d+(?:\.\d+)?)?)"
    r"\s*(?P<magnitude>[KMB])?"
    r"\s*(?P<suffix>%|\+|x|×)?"
    r"(?:\s*(?P<unit>minutes?|mins?|hours?|days?|weeks?|months?|years?|"
    r"businesses?|customers?|users?|rides?|teams?|engineers?|designers?|"
    r"markets?|countries?|corridors?|interviews?|customers?|logos?))?",
    re.I,
)
_DATE_RANGE_RE = re.compile(
    r"^(?P<start>[A-Z][a-z]{2}\s+\d{4})\s*(?P<dash>[-–—])\s*"
    r"(?P<end>[A-Z][a-z]{2}\s+\d{4}|Present)$"
)
_OWNERSHIP_OPENERS = {
    "built",
    "created",
    "drove",
    "established",
    "launched",
    "led",
    "owned",
    "shipped",
    "scaled",
    "unblocked",
}
_UNIT_CANONICAL = {
    "minute": "minute",
    "minutes": "minute",
    "min": "minute",
    "mins": "minute",
    "hour": "hour",
    "hours": "hour",
    "day": "day",
    "days": "day",
    "week": "week",
    "weeks": "week",
    "month": "month",
    "months": "month",
    "year": "year",
    "years": "year",
    "business": "business",
    "businesses": "business",
    "customer": "customer",
    "customers": "customer",
    "user": "user",
    "users": "user",
    "ride": "ride",
    "rides": "ride",
    "team": "team",
    "teams": "team",
    "engineer": "engineer",
    "engineers": "engineer",
    "designer": "designer",
    "designers": "designer",
    "market": "market",
    "markets": "market",
    "country": "country",
    "countries": "country",
    "corridor": "corridor",
    "corridors": "corridor",
    "interview": "interview",
    "interviews": "interview",
    "logo": "logo",
    "logos": "logo",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "through",
    "to",
    "with",
}


def inspect_pdf_artifact(path: str | Path) -> RenderedPdfArtifact:
    """Read observed page count and extractable text from a rendered PDF."""
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise ArtifactInspectionError(f"PDF does not exist: {pdf_path}")

    pdfinfo = shutil.which("pdfinfo")
    pdftotext = shutil.which("pdftotext")
    missing = [
        name
        for name, value in (("pdfinfo", pdfinfo), ("pdftotext", pdftotext))
        if not value
    ]
    if missing:
        raise ArtifactInspectionError(
            "Rendered PDF inspection requires: " + ", ".join(missing)
        )

    try:
        info = subprocess.run(
            [pdfinfo, str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        text = subprocess.run(
            [pdftotext, "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ArtifactInspectionError(f"Could not inspect {pdf_path}: {detail}") from exc

    match = re.search(r"(?im)^Pages:\s*(\d+)\s*$", info)
    if not match:
        raise ArtifactInspectionError(f"pdfinfo did not report a page count for {pdf_path}")
    return RenderedPdfArtifact(pdf_path, int(match.group(1)), text)


def _issue(
    issues: list[LintIssue],
    code: str,
    severity: LintSeverity,
    message: str,
    *locations: str,
) -> None:
    issues.append(LintIssue(code, severity, message, tuple(locations)))


def _normalized_text(text: str) -> str:
    text = text.casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    return " ".join(_TOKEN_RE.findall(text))


def _compact_render_text(text: str) -> str:
    return "".join(_TOKEN_RE.findall(text.casefold().replace("’", "'")))


def _summary_block(raw: str) -> str:
    match = re.search(
        r"(?ims)^\s*SECTION\s+0\b[^\n]*\n(?:[─═\-=]+\s*\n)?"
        r"(.*?)(?=^\s*SECTION\s+(?:1|2|3B?|4)\b|^\s*---+\s*$|\Z)",
        raw,
    )
    return match.group(1).strip() if match else ""


def _lint_raw_sections(
    raw: str,
    issues: list[LintIssue],
    required_sections: Sequence[str],
) -> None:
    if not raw.strip():
        _issue(
            issues,
            "RAW_OUTPUT_MISSING",
            LintSeverity.BLOCKER,
            "The generator release has no raw Pass 1 output to validate.",
            "raw_model_output",
        )
        return

    counts = Counter(match.group(1).upper() for match in _SECTION_MARKER_RE.finditer(raw))
    required = {section.upper() for section in required_sections}
    for section in sorted(required):
        if counts[section] == 0:
            _issue(
                issues,
                "MODEL_SECTION_MISSING",
                LintSeverity.BLOCKER,
                f"Required SECTION {section} is missing from the model output.",
                f"SECTION {section}",
            )
        elif counts[section] > 1:
            _issue(
                issues,
                "MODEL_SECTION_DUPLICATED",
                LintSeverity.BLOCKER,
                f"SECTION {section} appears {counts[section]} times; "
                "release requires one final section set.",
                f"SECTION {section}",
            )

    for section, count in sorted(counts.items()):
        if section not in required and count > 1:
            _issue(
                issues,
                "MODEL_SECTION_DUPLICATED",
                LintSeverity.BLOCKER,
                f"SECTION {section} appears {count} times; parser choice would be ambiguous.",
                f"SECTION {section}",
            )

    if "0" in required and counts["0"] == 1:
        summary = _summary_block(raw)
        lowered = summary.casefold()
        nonblank_lines = [line for line in summary.splitlines() if line.strip()]
        leak_markers = [marker for marker in _ANALYSIS_LEAK_MARKERS if marker in lowered]
        if len(_TOKEN_RE.findall(summary)) > 80 or len(nonblank_lines) > 4 or leak_markers:
            details = f" markers={leak_markers}" if leak_markers else ""
            _issue(
                issues,
                "SUMMARY_ANALYSIS_LEAK",
                LintSeverity.BLOCKER,
                "SECTION 0 contains reasoning instead of one paste-ready summary." + details,
                "SECTION 0",
            )


def _lint_profile_contract(document: AssembledResume, issues: list[LintIssue]) -> None:
    try:
        profile = get_profile(document.profile_id)
    except ValueError as exc:
        _issue(issues, "PROFILE_UNKNOWN", LintSeverity.BLOCKER, str(exc), "profile_id")
        return

    if document.identity_heading.strip() != profile.identity_heading:
        _issue(
            issues,
            "IDENTITY_HEADING_MISMATCH",
            LintSeverity.BLOCKER,
            f"Expected {profile.identity_heading!r}, got {document.identity_heading!r}.",
            "identity_heading",
        )

    summary_required = profile.summary_mode is SummaryMode.REQUIRED
    if summary_required or document.summary_text.strip():
        for error in validate_summary_identity(document.profile_id, document.summary_text):
            _issue(
                issues,
                "SUMMARY_IDENTITY_UNFUNDED",
                LintSeverity.BLOCKER,
                error,
                "summary",
            )

    row_labels = tuple(row.label for row in document.skill_rows)
    accurate_heading = skills_section_heading(row_labels)
    if document.skills_heading.strip() != accurate_heading:
        _issue(
            issues,
            "SKILLS_HEADING_INACCURATE",
            LintSeverity.BLOCKER,
            f"Rows require {accurate_heading!r}, got {document.skills_heading!r}.",
            "skills_heading",
        )
    duplicates = sorted(label for label, count in Counter(row_labels).items() if count > 1)
    if duplicates:
        _issue(
            issues,
            "SKILL_ROW_DUPLICATED",
            LintSeverity.BLOCKER,
            f"Duplicate Skills row labels: {duplicates}.",
            "skills",
        )

    fluo_companies = [
        block.company
        for block in document.experience_blocks
        if "fluo" in block.company.casefold()
    ]
    if fluo_companies:
        _issue(
            issues,
            "FLUO_IN_EXPERIENCE",
            LintSeverity.BLOCKER,
            "Fluo is outside Experience for every approved assembly profile.",
            *fluo_companies,
        )

    placement = profile.fluo.placement
    included = document.fluo_included
    if placement is FluoPlacement.INLINE_REQUIRED and included is not True:
        _issue(
            issues,
            "FLUO_REQUIRED_MISSING",
            LintSeverity.BLOCKER,
            f"{document.profile_id} requires the inline {profile.fluo.label!r} row.",
            "skills",
        )
    elif placement is FluoPlacement.OMIT and included is not False:
        _issue(
            issues,
            "FLUO_MUST_BE_OMITTED",
            LintSeverity.BLOCKER,
            f"{document.profile_id} does not permit Fluo in this page shape.",
            "skills",
        )
    elif (
        placement
        in {FluoPlacement.INLINE_RELEVANCE_GATED, FluoPlacement.PROJECT_OPTIONAL}
        and included is None
    ):
        _issue(
            issues,
            "FLUO_DECISION_MISSING",
            LintSeverity.BLOCKER,
            "A relevance-gated Fluo profile requires an explicit include/omit decision.",
            "fluo_included",
        )

    fluo_rows = [
        row
        for row in document.skill_rows
        if row.label.casefold() == profile.fluo.label.casefold()
        or "fluo" in row.text.casefold()
    ]
    fluo_in_projects = "fluo" in document.projects_text.casefold()
    if included:
        labels = {label.casefold() for label in row_labels}
        if (
            placement is not FluoPlacement.PROJECT_OPTIONAL
            and profile.fluo.label.casefold() not in labels
        ):
            _issue(
                issues,
                "FLUO_ROW_LABEL_MISSING",
                LintSeverity.BLOCKER,
                f"Included Fluo proof must use the fixed row label {profile.fluo.label!r}.",
                "skills",
            )
        if placement is FluoPlacement.PROJECT_OPTIONAL and not fluo_in_projects:
            _issue(
                issues,
                "FLUO_PROJECT_MISSING",
                LintSeverity.BLOCKER,
                "The recorded Fluo project decision has no Fluo content in Projects.",
                "projects",
            )
        if document.fluo_story_family not in profile.fluo.allowed_story_families:
            allowed = ", ".join(profile.fluo.allowed_story_families)
            _issue(
                issues,
                "FLUO_STORY_FAMILY_INVALID",
                LintSeverity.BLOCKER,
                f"Fluo story family must be one of: {allowed}.",
                "fluo_story_family",
            )
    elif fluo_rows or fluo_in_projects:
        _issue(
            issues,
            "FLUO_DECLARATION_MISMATCH",
            LintSeverity.BLOCKER,
            "Fluo content is present even though the assembly decision records omission.",
            "skills/projects",
        )

    if profile.family is ProfileFamily.CAMPUS:
        if document.allocation_plan is not None:
            _issue(
                issues,
                "CAMPUS_ALLOCATION_PLAN_INVALID",
                LintSeverity.BLOCKER,
                "Campus profiles do not use the five-company professional allocation plan.",
                "allocation_plan",
            )
        actual_total = sum(len(block.bullets) for block in document.experience_blocks)
        if not profile.bullet_budget.contains(actual_total):
            _issue(
                issues,
                "CAMPUS_BULLET_BUDGET_INVALID",
                LintSeverity.BLOCKER,
                f"{document.profile_id} permits {profile.bullet_budget.minimum}-"
                f"{profile.bullet_budget.maximum} bullets; assembled page has "
                f"{actual_total}.",
                "experience",
            )
        return

    if document.allocation_plan is None:
        _issue(
            issues,
            "ALLOCATION_PLAN_MISSING",
            LintSeverity.BLOCKER,
            "Professional release requires the exact recorded allocation decision.",
            "allocation_plan",
        )
        return

    if document.allocation_plan.profile_id != document.profile_id:
        _issue(
            issues,
            "ALLOCATION_PROFILE_MISMATCH",
            LintSeverity.BLOCKER,
            f"Allocation uses {document.allocation_plan.profile_id}, not {document.profile_id}.",
            "allocation_plan",
        )
    for error in validate_experience_allocation(document.allocation_plan):
        _issue(issues, "ALLOCATION_INVALID", LintSeverity.BLOCKER, error, "allocation_plan")

    expected_counts = document.allocation_plan.counts_dict()
    actual_companies = tuple(block.company for block in document.experience_blocks)
    expected_companies = tuple(expected_counts)
    if actual_companies != expected_companies:
        _issue(
            issues,
            "EXPERIENCE_ORDER_MISMATCH",
            LintSeverity.BLOCKER,
            f"Expected company order {expected_companies}, got {actual_companies}.",
            "experience",
        )
    for block in document.experience_blocks:
        expected = expected_counts.get(block.company)
        if expected is not None and len(block.bullets) != expected:
            _issue(
                issues,
                "COMPANY_BULLET_COUNT_MISMATCH",
                LintSeverity.BLOCKER,
                f"{block.company}: expected {expected} bullets, got {len(block.bullets)}.",
                block.company,
            )
    actual_total = sum(len(block.bullets) for block in document.experience_blocks)
    if actual_total != document.allocation_plan.total:
        _issue(
            issues,
            "TOTAL_BULLET_COUNT_MISMATCH",
            LintSeverity.BLOCKER,
            f"Allocation records {document.allocation_plan.total} bullets; "
            f"assembled page has {actual_total}.",
            "experience",
        )


def _opening_word(text: str) -> str:
    clean = _BULLET_PREFIX_RE.sub("", text.strip())
    match = re.search(r"[A-Za-z]+(?:'[A-Za-z]+)?", clean)
    return match.group(0).casefold() if match else ""


def _normalized_archetype(value: str) -> str:
    normalized = value.casefold().replace("_", "-")
    aliases = {
        "impact": "impact-first",
        "action-first": "action",
        "context-first": "context",
    }
    return aliases.get(normalized, normalized)


def _lint_archetypes_and_openers(
    document: AssembledResume,
    policy: AssemblyLintPolicy,
    issues: list[LintIssue],
) -> None:
    opener_locations: dict[str, list[str]] = defaultdict(list)
    archetypes: list[str] = []
    missing_archetypes: list[str] = []

    for block in document.experience_blocks:
        block_openers: Counter[str] = Counter()
        diagnostic_streak = 0
        for index, bullet in enumerate(block.bullets, start=1):
            location = f"{block.company} bullet {index}"
            opener = _opening_word(bullet.text)
            if opener:
                opener_locations[opener].append(location)
                block_openers[opener] += 1

            if not bullet.archetype:
                missing_archetypes.append(location)
                diagnostic_streak = 0
                continue
            archetype = _normalized_archetype(bullet.archetype)
            archetypes.append(archetype)
            if archetype == "diagnostic":
                diagnostic_streak += 1
                maximum = (
                    document.archetype_contract.maximum_consecutive_diagnostic
                    if document.archetype_contract
                    else 2
                )
                if diagnostic_streak > maximum:
                    _issue(
                        issues,
                        "DIAGNOSTIC_STREAK_EXCEEDED",
                        LintSeverity.BLOCKER,
                        f"{block.company} exceeds the {maximum}-bullet diagnostic streak cap.",
                        location,
                    )
            else:
                diagnostic_streak = 0

        repeated = sorted(opener for opener, count in block_openers.items() if count > 1)
        if repeated:
            _issue(
                issues,
                "OPENING_VERB_REPEATED_IN_COMPANY",
                LintSeverity.BLOCKER,
                f"{block.company} repeats opening verb(s): {repeated}.",
                block.company,
            )

    for opener, locations in sorted(opener_locations.items()):
        if len(locations) >= 3:
            _issue(
                issues,
                "OPENING_VERB_OVERUSED",
                LintSeverity.BLOCKER,
                f"Opening verb {opener!r} appears {len(locations)} times across the page.",
                *locations,
            )

    if policy.require_archetype_metadata and missing_archetypes:
        _issue(
            issues,
            "ARCHETYPE_METADATA_MISSING",
            LintSeverity.BLOCKER,
            "Every selected bullet needs its admitted archetype metadata; "
            "prose is not reclassified heuristically.",
            *missing_archetypes,
        )

    if document.archetype_contract and not missing_archetypes:
        counts = Counter(archetypes)
        for raw_archetype, minimum in document.archetype_contract.minimum_counts:
            archetype = _normalized_archetype(raw_archetype)
            if counts[archetype] < minimum:
                _issue(
                    issues,
                    "ARCHETYPE_FLOOR_MISSED",
                    LintSeverity.BLOCKER,
                    f"{archetype} requires at least {minimum}; "
                    f"assembled page has {counts[archetype]}.",
                    "experience",
                )
        for raw_archetype, maximum in document.archetype_contract.maximum_counts:
            archetype = _normalized_archetype(raw_archetype)
            if counts[archetype] > maximum:
                _issue(
                    issues,
                    "ARCHETYPE_CEILING_EXCEEDED",
                    LintSeverity.BLOCKER,
                    f"{archetype} permits at most {maximum}; "
                    f"assembled page has {counts[archetype]}.",
                    "experience",
                )
        action_impact = counts["action"] + counts["impact-first"]
        minimum = document.archetype_contract.minimum_action_plus_impact
        if action_impact < minimum:
            _issue(
                issues,
                "ACTION_IMPACT_FLOOR_MISSED",
                LintSeverity.BLOCKER,
                f"Action plus impact-first requires at least {minimum}; "
                f"assembled page has {action_impact}.",
                "experience",
            )

    if not any(opener in _OWNERSHIP_OPENERS for opener in opener_locations):
        _issue(
            issues,
            "OWNERSHIP_OPENER_MISSING",
            LintSeverity.BLOCKER,
            "No bullet opens with a strong ownership verb.",
            "experience",
        )


def _figure_key(match: re.Match[str]) -> str | None:
    currency = (match.group("currency") or "").casefold()
    number = re.sub(r"\s+", "", match.group("number")).replace(",", "")
    magnitude = (match.group("magnitude") or "").casefold()
    suffix = (match.group("suffix") or "").casefold().replace("×", "x")
    unit = (match.group("unit") or "").casefold()
    unit = _UNIT_CANONICAL.get(unit, unit)
    # Small, unitless integers are overwhelmingly list/count syntax rather than
    # salient resume figures.  Keep them only when their formatting carries meaning.
    if not any((currency, magnitude, suffix, unit)):
        try:
            if float(number.split("-")[0]) < 1000:
                return None
        except ValueError:
            return None
    return f"{currency}{number}{magnitude}{suffix}:{unit}"


def _figures(text: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    for match in _FIGURE_RE.finditer(text):
        key = _figure_key(match)
        if key:
            found.append((key, match.group(0).strip()))
    return tuple(found)


def _currency_value(match: re.Match[str]) -> float | None:
    if not match.group("currency"):
        return None
    number_text = re.sub(r"\s+", "", match.group("number")).replace(",", "")
    if "-" in number_text or "–" in number_text:
        return None
    try:
        value = float(number_text)
    except ValueError:
        return None
    multiplier = {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}
    return value * multiplier[(match.group("magnitude") or "").casefold()]


def _content_phrase_windows(text: str, size: int) -> set[str]:
    tokens = _TOKEN_RE.findall(text.casefold())
    phrases: set[str] = set()
    for index in range(len(tokens) - size + 1):
        window = tokens[index : index + size]
        if sum(token not in _STOPWORDS for token in window) < 2:
            continue
        phrases.add(" ".join(window))
    return phrases


def _lint_page_composition(
    document: AssembledResume,
    policy: AssemblyLintPolicy,
    issues: list[LintIssue],
) -> None:
    entries: list[tuple[str, str]] = [("summary", document.summary_text)]
    for block in document.experience_blocks:
        entries.extend(
            (f"{block.company} bullet {index}", bullet.text)
            for index, bullet in enumerate(block.bullets, start=1)
        )

    normalized_seen: dict[str, str] = {}
    for location, text in entries[1:]:
        normalized = _normalized_text(text)
        prior = normalized_seen.get(normalized)
        if normalized and prior:
            _issue(
                issues,
                "BULLET_DUPLICATED",
                LintSeverity.BLOCKER,
                "The same bullet appears more than once.",
                prior,
                location,
            )
        normalized_seen[normalized] = location

    figure_locations: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for location, text in entries:
        for key, display in _figures(text):
            figure_locations[key].append((location, display))

    for occurrences in figure_locations.values():
        unique_locations = tuple(dict.fromkeys(location for location, _ in occurrences))
        if len(unique_locations) < 2:
            continue
        display = occurrences[0][1]
        company_counts = Counter(
            location.split(" bullet ")[0]
            for location in unique_locations
            if " bullet " in location
        )
        if any(count > 1 for count in company_counts.values()):
            severity = LintSeverity.BLOCKER
            code = "FIGURE_REPEATED_IN_COMPANY"
        elif "summary" in unique_locations:
            # A single flagship metric may be intentionally echoed in the summary
            # (the Amazon gold reference does this).  Surface the page-cost tradeoff,
            # but do not turn a contextual editorial choice into a false hard stop.
            severity = LintSeverity.WARNING
            code = "SUMMARY_FIGURE_REUSED"
        else:
            severity = LintSeverity.WARNING
            code = "FIGURE_REPEATED_ACROSS_COMPANIES"
        _issue(
            issues,
            code,
            severity,
            f"Figure {display!r} is repeated across assembled content.",
            *unique_locations,
        )

    scale_entries = list(entries)
    if document.projects_text.strip():
        scale_entries.append(("projects", document.projects_text))
    scale_entries.extend(
        (f"skills row {row.label}", row.text) for row in document.skill_rows
    )
    currency_values: list[tuple[float, str, str]] = []
    for location, text in scale_entries:
        for match in _FIGURE_RE.finditer(text):
            value = _currency_value(match)
            if value is not None:
                currency_values.append((value, match.group(0).strip(), location))

    if len(currency_values) >= 2:
        smallest = min(currency_values, key=lambda item: item[0])
        largest = max(currency_values, key=lambda item: item[0])
        if smallest[0] > 0 and largest[0] / smallest[0] >= policy.currency_scale_ratio:
            _issue(
                issues,
                "CURRENCY_SCALE_INCOHERENT",
                LintSeverity.WARNING,
                f"Dollar proof spans {smallest[1]} to {largest[1]}; "
                "verify the smaller figure strengthens the page.",
                smallest[2],
                largest[2],
            )

    phrase_locations: dict[str, list[str]] = defaultdict(list)
    for location, text in entries:
        for phrase in _content_phrase_windows(text, policy.repeated_phrase_words):
            phrase_locations[phrase].append(location)
    phrase_issues = 0
    for phrase, locations in sorted(phrase_locations.items()):
        unique_locations = tuple(dict.fromkeys(locations))
        if len(unique_locations) < 2:
            continue
        _issue(
            issues,
            "PHRASE_REPEATED",
            LintSeverity.WARNING,
            f"Repeated {policy.repeated_phrase_words}-word phrase: {phrase!r}.",
            *unique_locations,
        )
        phrase_issues += 1
        if phrase_issues >= policy.maximum_phrase_warnings:
            break

    bullets = document.bullets
    contrast_count = sum(
        len(re.findall(r"\bnot\b[^.;!?\n]{0,60}\bbut\b|\brather than\b", bullet.text, re.I))
        for bullet in bullets
    )
    if contrast_count > 1:
        _issue(
            issues,
            "CONTRAST_PHRASE_CAP_EXCEEDED",
            LintSeverity.BLOCKER,
            f"The page uses {contrast_count} contrast constructions; maximum is one.",
            "experience",
        )

    punctuation_styles = Counter()
    for block in document.experience_blocks:
        if not _DATE_RANGE_RE.match(block.date_text.strip()):
            _issue(
                issues,
                "DATE_FORMAT_INCONSISTENT",
                LintSeverity.WARNING,
                f"Date range is not 'Mon YYYY – Mon YYYY/Present': {block.date_text!r}.",
                block.company,
            )
        for index, bullet in enumerate(block.bullets, start=1):
            location = f"{block.company} bullet {index}"
            text = bullet.text.strip()
            punctuation_styles[text[-1:] if text else ""] += 1
            if len(text) > policy.long_bullet_chars:
                _issue(
                    issues,
                    "BULLET_DENSITY_HIGH",
                    LintSeverity.WARNING,
                    f"Bullet is {len(text)} characters; verify its rendered line cost.",
                    location,
                )
    if len(punctuation_styles) > 1 or (punctuation_styles and "." not in punctuation_styles):
        _issue(
            issues,
            "BULLET_PUNCTUATION_INCONSISTENT",
            LintSeverity.WARNING,
            f"Bullet terminal punctuation is inconsistent: {dict(punctuation_styles)}.",
            "experience",
        )


def _lint_rendered_artifact(document: AssembledResume, issues: list[LintIssue]) -> None:
    if document.rendered_page_count is None:
        _issue(
            issues,
            "PAGE_COUNT_UNVERIFIED",
            LintSeverity.BLOCKER,
            "Release requires an observed PDF page count, not a page-fit estimate.",
            "rendered_pdf",
        )
    elif document.rendered_page_count != 1:
        _issue(
            issues,
            "PAGE_COUNT_INVALID",
            LintSeverity.BLOCKER,
            f"Rendered resume has {document.rendered_page_count} pages; "
            "release requires exactly one.",
            "rendered_pdf",
        )

    if not document.rendered_text.strip():
        _issue(
            issues,
            "RENDERED_TEXT_UNVERIFIED",
            LintSeverity.BLOCKER,
            "Release requires text extracted from the rendered PDF.",
            "rendered_pdf",
        )
        return

    compact_render = _compact_render_text(document.rendered_text)
    expected_fragments: list[tuple[str, str]] = [
        ("identity_heading", document.identity_heading),
        ("summary", document.summary_text),
        ("skills_heading", document.skills_heading),
    ]
    expected_fragments.extend(
        (f"{block.company} bullet {index}", bullet.text)
        for block in document.experience_blocks
        for index, bullet in enumerate(block.bullets, start=1)
    )
    expected_fragments.extend(
        (f"skills row {row.label}", f"{row.label} {row.text}") for row in document.skill_rows
    )
    for location, text in expected_fragments:
        compact_expected = _compact_render_text(text)
        if compact_expected and compact_expected not in compact_render:
            _issue(
                issues,
                "RENDERED_TEXT_MISMATCH",
                LintSeverity.BLOCKER,
                "Assembled content is missing or changed in the rendered PDF text.",
                location,
            )

    experience_match = re.search(
        rf"(?ims)^\s*EXPERIENCE\s*$"
        rf"(?P<body>.*?)"
        rf"^\s*{re.escape(document.skills_heading)}\s*$",
        document.rendered_text,
    )
    if not experience_match:
        _issue(
            issues,
            "RENDERED_EXPERIENCE_BOUNDARY_MISSING",
            LintSeverity.BLOCKER,
            "Could not isolate Experience from the rendered PDF text.",
            "rendered_pdf",
        )
    else:
        rendered_bullet_count = len(
            _RENDERED_BULLET_RE.findall(experience_match.group("body"))
        )
        expected_bullet_count = len(document.bullets)
        if rendered_bullet_count != expected_bullet_count:
            _issue(
                issues,
                "RENDERED_BULLET_COUNT_MISMATCH",
                LintSeverity.BLOCKER,
                f"Rendered Experience has {rendered_bullet_count} bullet markers; "
                f"expected {expected_bullet_count}.",
                "rendered_pdf",
            )

    lowered = document.rendered_text.casefold()
    leak_markers = [marker for marker in _ANALYSIS_LEAK_MARKERS if marker in lowered]
    if leak_markers:
        _issue(
            issues,
            "RENDERED_ANALYSIS_LEAK",
            LintSeverity.BLOCKER,
            f"Rendered PDF contains internal reasoning markers: {leak_markers}.",
            "rendered_pdf",
        )


def lint_assembled_resume(
    document: AssembledResume,
    policy: AssemblyLintPolicy = ASSEMBLY_POLICY,
) -> LintReport:
    """Run deterministic page checks and return a non-averaged release verdict."""
    issues: list[LintIssue] = []
    if policy.require_raw_section_integrity:
        _lint_raw_sections(
            document.raw_model_output,
            issues,
            policy.required_model_sections,
        )
    _lint_profile_contract(document, issues)
    _lint_archetypes_and_openers(document, policy, issues)
    _lint_page_composition(document, policy, issues)
    if policy.require_rendered_artifact:
        _lint_rendered_artifact(document, issues)
    return LintReport(
        tuple(issues),
        artifact_required=policy.require_rendered_artifact,
    )


def lint_model_section_integrity(
    raw_model_output: str,
    required_sections: Sequence[str] = ("0", "3", "4"),
) -> LintReport:
    """Validate one Pass 1 response before any ambiguous parser choice is made."""
    issues: list[LintIssue] = []
    _lint_raw_sections(raw_model_output, issues, required_sections)
    return LintReport(tuple(issues))


def attach_pdf_artifact(document: AssembledResume, path: str | Path) -> AssembledResume:
    """Return the assembly record with observed PDF evidence attached."""
    artifact = inspect_pdf_artifact(path)
    return replace(
        document,
        rendered_page_count=artifact.page_count,
        rendered_text=artifact.text,
    )


def issue_codes(report: LintReport, severity: LintSeverity | None = None) -> set[str]:
    """Small test/reporting helper; not part of release policy."""
    return {
        issue.code
        for issue in report.issues
        if severity is None or issue.severity is severity
    }
