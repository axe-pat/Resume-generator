"""Versioned resume assembly contracts and a deterministic resolver.

The queue lane is intentionally *not* part of this API.  Lanes describe when an
application should be handled; assembly profiles describe the page contract the
document must use.

These profiles do not replace Step 0's existing ``archetype``, ``role_family``,
``nonpm_subtype``, ``bullet_balance``, or framing axes.  They are deterministically
derived from those semantic decisions.  The model does not invent bullet counts
or decide where Fluo appears.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


PROFILE_REGISTRY_VERSION = "2026-09-03.2"
PROFESSIONAL_COMPANY_ORDER = (
    "FLAIRX AI",
    "GOJEK",
    "HEVO DATA",
    "INTUIT",
    "OPTUM",
)


class ProfileFamily(str, Enum):
    PRODUCT = "product"
    BUSINESS_LEADERSHIP = "business-leadership"
    CUSTOMER_TECHNICAL = "customer-technical"
    CAMPUS = "campus"


class SummaryMode(str, Enum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"
    OMIT = "omit"


class BulletBudgetDecision(str, Enum):
    """The only permitted ways to leave a professional preset's default total."""

    DEFAULT = "default"
    REBALANCE_DISTINCT_SIGNAL = "rebalance-distinct-signal"
    ADD_DISTINCT_SIGNAL = "add-distinct-signal"
    COMPACT_FOR_PAGE_FIT = "compact-for-page-fit"
    COMPACT_FOR_QUALITY = "compact-for-quality"


class TitleMode(str, Enum):
    FUNCTIONAL_PRODUCT_OWNER = "functional-product-owner"
    OFFICIAL_WITH_FUNCTIONAL_QUALIFIER = "official-with-functional-qualifier"
    OFFICIAL = "official"


class FluoPlacement(str, Enum):
    INLINE_REQUIRED = "inline-required"
    INLINE_RELEVANCE_GATED = "inline-relevance-gated"
    PROJECT_OPTIONAL = "project-optional"
    OMIT = "omit"


class SupportingProofMode(str, Enum):
    """How non-employer proof participates in the one-page evidence budget.

    This is deliberately an assembly modifier, not another role taxonomy.  The
    default keeps project/venture proof compact outside Experience.  A reviewed
    top-criterion decision may instead promote admitted project evidence and
    remove lower-marginal Experience bullets one-for-one.
    """

    INLINE = "inline"
    PROJECT_REPLACEMENT = "project-replacement"
    OMIT = "omit"


class SupportingProofReason(str, Enum):
    DEFAULT = "default"
    TOP_CRITERION_EVIDENCE = "top-criterion-evidence"


class SkillRowDecision(str, Enum):
    """Why a professional Skills plan contains its resolved row count."""

    DEFAULT_FIVE = "default-five"
    ADD_DISTINCT_SIXTH = "add-distinct-sixth"
    DROP_SIXTH_FOR_PAGE = "drop-sixth-for-page"


@dataclass(frozen=True)
class FluoPolicy:
    placement: FluoPlacement
    label: str = ""
    allowed_story_families: tuple[str, ...] = ()
    max_lines: int = 0
    counts_toward_experience: bool = False
    allow_experience: bool = False


@dataclass(frozen=True)
class BulletBudget:
    minimum: int
    target: int
    maximum: int

    def contains(self, count: int) -> bool:
        return self.minimum <= count <= self.maximum


@dataclass(frozen=True)
class SkillRowOption:
    """One profile-owned row label that may fill a flexible Skills slot.

    The strings in ``relevance_tags`` are routing evidence only. Exact row text
    remains owned by the reviewed value bank; this object never authorizes the
    model to write or keyword-stuff a Skills row.
    """

    label: str
    relevance_tags: tuple[str, ...]
    signal_kind: str


@dataclass(frozen=True)
class SkillAssemblyPolicy:
    """Bounded Skills shape for a single existing assembly profile.

    Five rows remain the professional default. The policy makes the *contents*
    of those five adaptive instead of relying on a sixth row to rescue a weak
    fixed slate. A sixth is only a pre-approved, distinct differentiator and is
    still subject to observed page geometry before release.
    """

    core_rows: tuple[str, ...]
    flexible_rows: tuple[SkillRowOption, ...]
    default_rows: tuple[str, ...]
    minimum_rows: int = 5
    target_rows: int = 5
    maximum_rows: int = 6

    def __post_init__(self) -> None:
        labels = tuple(option.label for option in self.flexible_rows)
        if len(set(self.core_rows)) != len(self.core_rows):
            raise ValueError("Skills core row labels must be unique")
        if len(set(labels)) != len(labels):
            raise ValueError("Skills flexible row labels must be unique")
        if set(self.core_rows) & set(labels):
            raise ValueError("Skills core and flexible row labels cannot overlap")
        if not (
            1 <= self.minimum_rows <= self.target_rows <= self.maximum_rows
        ):
            raise ValueError("Skills row bounds must satisfy 1 <= minimum <= target <= maximum")
        permitted = set(self.core_rows) | set(labels)
        if len(self.default_rows) != self.target_rows:
            raise ValueError("Skills default rows must match the target row count")
        if len(set(self.default_rows)) != len(self.default_rows):
            raise ValueError("Skills default row labels must be unique")
        if not set(self.core_rows).issubset(self.default_rows):
            raise ValueError("Skills default rows must preserve every core row")
        if not set(self.default_rows).issubset(permitted):
            raise ValueError("Skills default rows contain an unfunded label")

    @property
    def flexible_labels(self) -> tuple[str, ...]:
        return tuple(option.label for option in self.flexible_rows)


@dataclass(frozen=True)
class SkillsAssemblyPlan:
    """Exact row-label plan consumed by prompt assembly and validation."""

    profile_id: str
    row_labels: tuple[str, ...]
    decision: SkillRowDecision
    optional_sixth_label: str | None = None
    selection_audit: tuple[tuple[str, int], ...] = ()

    @property
    def row_count(self) -> int:
        return len(self.row_labels)

    @property
    def has_optional_sixth(self) -> bool:
        return self.optional_sixth_label is not None and self.row_count == 6


@dataclass(frozen=True)
class CompanySlot:
    company: str
    minimum: int
    target: int
    maximum: int


@dataclass(frozen=True)
class ResumeProfile:
    profile_id: str
    family: ProfileFamily
    experience_slots: tuple[CompanySlot, ...]
    bullet_budget: BulletBudget
    summary_mode: SummaryMode
    identity_heading: str
    funded_summary_identities: tuple[str, ...]
    title_mode: TitleMode
    skill_rows: tuple[str, ...]
    fluo: FluoPolicy
    selection_priorities: tuple[str, ...]
    skill_policy: SkillAssemblyPolicy | None = None

    @property
    def experience_bullet_total(self) -> int:
        """The center allocation, retained as the default profile shape."""
        return sum(slot.target for slot in self.experience_slots)

    @property
    def is_professional(self) -> bool:
        return self.family is not ProfileFamily.CAMPUS

    @property
    def summary_heading(self) -> str:
        """Backward-compatible alias for callers not yet migrated.

        The rendered line is a professional identity headline above the summary
        body, not the semantic name of a parser-dependent ``SUMMARY`` section.
        """
        return self.identity_heading

    def slots_dict(self) -> dict[str, int]:
        return {slot.company: slot.target for slot in self.experience_slots}

    def slot_bounds(self) -> dict[str, tuple[int, int, int]]:
        return {
            slot.company: (slot.minimum, slot.target, slot.maximum)
            for slot in self.experience_slots
        }


def skills_section_heading(row_labels: Iterable[str]) -> str:
    """Return the accurate standard heading for the rows actually rendered.

    ``Community``, ``Additional``, venture rows, and prose proof rows do not
    silently count as interests.  The longer heading is earned only by an
    explicit Interests row, so this remains deterministic at assembly time.
    """
    normalized = {
        str(label).strip().rstrip(":").casefold()
        for label in row_labels
        if str(label).strip()
    }
    return "SKILLS & INTERESTS" if "interests" in normalized else "SKILLS"


def validate_summary_identity(profile_id: str, summary_text: str) -> list[str]:
    """Require the summary's first clause to name a pool-funded identity."""
    profile = get_profile(profile_id)
    text = summary_text.strip()
    if not text:
        return [f"{profile_id}: required summary is empty"]
    first_clause = re.split(r"[,;:.!?]", text, maxsplit=1)[0].strip().casefold()
    if not any(identity.casefold() in first_clause for identity in profile.funded_summary_identities):
        allowed = ", ".join(profile.funded_summary_identities)
        return [
            f"{profile_id}: first summary clause must name a funded identity; "
            f"expected one of: {allowed}"
        ]
    return []


@dataclass(frozen=True)
class ExperienceAllocationPlan:
    """A resolved, exact company allocation for one professional resume.

    The profile target is the default build and normal cap. Eleven is a gated
    distinct-signal exception. Nine may protect admission quality or repair page
    fit. The model cannot emit an arbitrary count or company redistribution.
    """

    profile_id: str
    company_counts: tuple[tuple[str, int], ...]
    budget_decision: BulletBudgetDecision = BulletBudgetDecision.DEFAULT

    @property
    def total(self) -> int:
        return sum(count for _, count in self.company_counts)

    def counts_dict(self) -> dict[str, int]:
        return dict(self.company_counts)


@dataclass(frozen=True)
class PageProofPlan:
    """Page-wide evidence contract spanning Experience and Projects.

    ``ExperienceAllocationPlan`` remains authoritative for the normal inline
    build.  ``PROJECT_REPLACEMENT`` is the bounded exception demonstrated by a
    JD whose top screen is independently built work: one or two marginal
    Experience bullets may be displaced by two or three admitted project
    bullets while all five career blocks remain visible.
    """

    profile_id: str
    experience_plan: ExperienceAllocationPlan
    mode: SupportingProofMode = SupportingProofMode.INLINE
    reason: SupportingProofReason = SupportingProofReason.DEFAULT
    project_bullet_count: int = 0
    replaced_experience_count: int = 0

    @property
    def experience_bullet_count(self) -> int:
        return self.experience_plan.total

    @property
    def total_proof_units(self) -> int:
        return self.experience_bullet_count + self.project_bullet_count


def _professional_profile(
    profile_id: str,
    family: ProfileFamily,
    allocation: Sequence[int],
    *,
    identity_heading: str,
    funded_summary_identities: Sequence[str],
    summary_mode: SummaryMode,
    title_mode: TitleMode,
    skill_rows: Sequence[str],
    fluo: FluoPolicy,
    selection_priorities: Sequence[str],
    skill_policy: SkillAssemblyPolicy | None = None,
) -> ResumeProfile:
    if len(allocation) != len(PROFESSIONAL_COMPANY_ORDER):
        raise ValueError(f"{profile_id}: allocation must cover all five companies")
    slots = tuple(
        CompanySlot(
            company=company,
            minimum=(
                2
                if family is ProfileFamily.PRODUCT and company == "FLAIRX AI"
                else max(1, target - 1)
            ),
            target=target,
            # No company earns four bullets in a one-page professional resume.
            # Optum is continuity proof, not a three-bullet anchor.
            maximum=min(2 if company == "OPTUM" else 3, target + 1),
        )
        for company, target in zip(PROFESSIONAL_COMPANY_ORDER, allocation)
    )
    if sum(allocation) != 10:
        raise ValueError(f"{profile_id}: professional profiles must allocate 10 bullets")
    normalized_skill_rows = tuple(skill_rows)
    return ResumeProfile(
        profile_id=profile_id,
        family=family,
        experience_slots=slots,
        bullet_budget=BulletBudget(minimum=9, target=10, maximum=11),
        summary_mode=summary_mode,
        identity_heading=identity_heading,
        funded_summary_identities=tuple(funded_summary_identities),
        title_mode=title_mode,
        skill_rows=normalized_skill_rows,
        fluo=fluo,
        selection_priorities=tuple(selection_priorities),
        skill_policy=skill_policy or _default_professional_skill_policy(
            family=family,
            default_rows=normalized_skill_rows,
            fluo=fluo,
        ),
    )


_SKILL_RELEVANCE_TAGS: Mapping[str, tuple[str, ...]] = {
    "Product Leadership": (
        "product", "roadmap", "customer discovery", "requirements", "prioritization",
    ),
    "Data & Analytics": (
        "analytics", "data", "funnel", "cohort", "retention", "experiment", "kpi",
    ),
    "Technical": (
        "technical", "engineering", "api", "platform", "systems", "cloud", "integration",
    ),
    "AI & Automation": (
        " ai ", "artificial intelligence", "machine learning", "genai", "llm",
        "automation", "agentic", "model evaluation", "prototype",
    ),
    "AI Product Development": (
        " ai ", "artificial intelligence", "machine learning", "genai", "llm",
        "agentic", "model", "human-in-the-loop", "prototype",
    ),
    "Data Platforms": (
        "data platform", "infrastructure", "database", "pipeline", "developer",
        "reliability", "observability",
    ),
    "Strategy & Transformation": (
        "strategy", "transformation", "market sizing", "diligence", "scenario",
    ),
    "Operating Leadership": (
        "leadership", "operating", "governance", "portfolio", "stakeholder",
    ),
    "Analytics": (
        "analytics", "analysis", "data", "sql", "excel", "dashboard", "kpi",
    ),
    "Operations & Programs": (
        "operations", "program", "delivery", "governance", "execution",
    ),
    "Process Improvement": (
        "process", "continuous improvement", "root cause", "quality", "workflow",
    ),
    "Leadership": (
        "leadership", "team", "influence", "change management", "executive",
    ),
    "Commercial Strategy": (
        "commercial", "pricing", "monetization", "market", "competitive",
    ),
    "Customer & GTM": (
        "customer", "go-to-market", "gtm", "partnership", "revenue", "sales",
    ),
    "Solutions & Delivery": (
        "solution", "implementation", "delivery", "requirements", "rollout",
    ),
    "Data & Platforms": (
        "data", "platform", "pipeline", "api", "integration", "reliability",
    ),
    "Programming & Cloud": (
        "python", "java", "sql", "aws", "cloud", "programming", "technical",
    ),
    "Customer Value": (
        "customer", "adoption", "value realization", "stakeholder", "executive",
    ),
    "Technical Delivery": (
        "technical", "delivery", "integration", "release", "execution",
    ),
    "Customer Systems": (
        "customer", "enterprise", "workflow", "implementation", "reliability",
    ),
    "Additional": (
        "community", "volunteer", "mission", "education", "social impact",
    ),
    "Startup Product": (
        "student", "fintech", "consumer", "startup", "venture", "marketplace",
        "international", "partnership", "campus", "housing",
    ),
    "Venture Strategy/GTM": (
        "startup", "venture", "market entry", "partnership", "gtm", "go-to-market",
        "student", "fintech",
    ),
    "Venture Product": (
        "startup", "venture", "product", "prototype", "student", "fintech",
        "customer deployment",
    ),
    "Independent Product": (
        "independently built", "built something", "builder", "side project",
        "personal project", "bias to action", "vibe code", "agentic", "prototype",
        "end-to-end",
    ),
    "Community": (
        "volunteer", "mission", "education", "school", "underserved",
        "nonprofit", "social impact", "children", "youth",
    ),
    "Interests": (
        "music", "musician", "dj", "playlist", "audio", "entertainment",
        "fitness", "strength", "trekking", "hiking", "outdoors", "astrophysics",
        "psychology", "personal stake", "passion",
    ),
}


def _skill_signal_kind(label: str, fluo: FluoPolicy) -> str:
    if label == fluo.label and label:
        return "current-venture"
    return {
        "Independent Product": "independent-build",
        "Community": "community",
        "Additional": "community",
        "Interests": "personal-stake",
        "AI & Automation": "ai-capability",
        "AI Product Development": "ai-capability",
        "Technical": "technical-capability",
        "Programming & Cloud": "technical-capability",
        "Leadership": "leadership",
    }.get(label, label.casefold().replace(" & ", "-").replace(" ", "-"))


def _default_professional_skill_policy(
    *,
    family: ProfileFamily,
    default_rows: tuple[str, ...],
    fluo: FluoPolicy,
) -> SkillAssemblyPolicy:
    """Build the adaptive tail without creating another role taxonomy.

    Product pages keep three functional rows plus the current Fluo signal, then
    let the fifth row respond to the JD. Other professional pages keep their
    first four functional rows and make only the tail adaptive. The existing
    five-row slate remains the deterministic no-signal fallback.
    """

    if len(default_rows) != 5:
        raise ValueError("professional Skills defaults must contain five rows")
    if family is ProfileFamily.PRODUCT:
        core_rows = default_rows[:3]
    else:
        core_rows = default_rows[:4]
    flexible_labels = tuple(dict.fromkeys(
        (*default_rows[len(core_rows):], "Independent Product", "Community", "Interests")
    ))
    flexible_rows = tuple(
        SkillRowOption(
            label=label,
            relevance_tags=_SKILL_RELEVANCE_TAGS.get(label, (label.casefold(),)),
            signal_kind=_skill_signal_kind(label, fluo),
        )
        for label in flexible_labels
    )
    return SkillAssemblyPolicy(
        core_rows=core_rows,
        flexible_rows=flexible_rows,
        default_rows=default_rows,
    )


_PRODUCT_FLUO = FluoPolicy(
    placement=FluoPlacement.INLINE_REQUIRED,
    label="Startup Product",
    allowed_story_families=("product-system", "customer-insight", "gtm-partnership"),
    max_lines=2,
)
_BUSINESS_FLUO = FluoPolicy(
    placement=FluoPlacement.INLINE_RELEVANCE_GATED,
    label="Venture Strategy/GTM",
    allowed_story_families=("gtm-partnership", "founder-strategy", "customer-insight"),
    max_lines=2,
)
_TECHNICAL_FLUO = FluoPolicy(
    placement=FluoPlacement.INLINE_RELEVANCE_GATED,
    label="Venture Product",
    allowed_story_families=("product-system", "data-analytics", "customer-deployment"),
    max_lines=2,
)
_NO_FLUO = FluoPolicy(placement=FluoPlacement.OMIT)

_PRODUCT_SUMMARY_IDENTITIES = (
    "product manager",
    "product leader",
    "technical product leader",
    "product owner",
)
_ENTERPRISE_SUMMARY_IDENTITIES = (
    "strategy and operations",
    "strategy & operations",
    "business operator",
    "technical operator",
    "strategy professional",
)
_OPERATIONS_SUMMARY_IDENTITIES = (
    "operations and program",
    "operations & program",
    "operations manager",
    "operations leader",
    "technical operator",
    "engineer-turned-operator",
)
_COMMERCIAL_SUMMARY_IDENTITIES = (
    "commercial strategist",
    "commercial operator",
    "go-to-market strategist",
    "gtm strategist",
    "growth strategist",
)
_TECHNICAL_SUMMARY_IDENTITIES = (
    "technical solutions",
    "solutions consultant",
    "technical consultant",
    "customer-facing technologist",
    "deployed engineer",
    "implementation leader",
)
_CAMPUS_SUMMARY_IDENTITIES = (
    "usc marshall mba candidate",
    "usc mba candidate",
    "mba candidate at usc marshall",
    "usc marshall student",
)


PROFILE_REGISTRY: dict[str, ResumeProfile] = {
    "product-general": _professional_profile(
        "product-general",
        ProfileFamily.PRODUCT,
        (2, 3, 2, 2, 1),
        identity_heading="PRODUCT MANAGEMENT",
        funded_summary_identities=_PRODUCT_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.FUNCTIONAL_PRODUCT_OWNER,
        skill_rows=(
            "Product Leadership",
            "Data & Analytics",
            "Technical",
            "AI & Automation",
            "Startup Product",
        ),
        fluo=_PRODUCT_FLUO,
        selection_priorities=(
            "product-judgment",
            "customer-insight",
            "business-outcome",
            "technical-tradeoff",
            "cross-functional-leadership",
        ),
    ),
    "product-ai-zero-to-one": _professional_profile(
        "product-ai-zero-to-one",
        ProfileFamily.PRODUCT,
        (2, 3, 2, 2, 1),
        identity_heading="PRODUCT MANAGEMENT",
        funded_summary_identities=_PRODUCT_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.FUNCTIONAL_PRODUCT_OWNER,
        skill_rows=(
            "Product Leadership",
            "AI Product Development",
            "Data & Analytics",
            "Technical",
            "Startup Product",
        ),
        fluo=_PRODUCT_FLUO,
        selection_priorities=(
            "zero-to-one",
            "ai-product-judgment",
            "customer-workflow",
            "unit-economics",
            "technical-tradeoff",
        ),
    ),
    "product-data-platform": _professional_profile(
        "product-data-platform",
        ProfileFamily.PRODUCT,
        (2, 2, 3, 2, 1),
        identity_heading="PRODUCT MANAGEMENT",
        funded_summary_identities=_PRODUCT_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.FUNCTIONAL_PRODUCT_OWNER,
        skill_rows=(
            "Product Leadership",
            "Data Platforms",
            "Data & Analytics",
            "Technical",
            "Startup Product",
        ),
        fluo=_PRODUCT_FLUO,
        selection_priorities=(
            "platform-product-judgment",
            "enterprise-customer",
            "data-reliability",
            "adoption",
            "technical-tradeoff",
        ),
    ),
    "business-enterprise-leadership": _professional_profile(
        "business-enterprise-leadership",
        ProfileFamily.BUSINESS_LEADERSHIP,
        (1, 3, 2, 2, 2),
        identity_heading="STRATEGY & OPERATIONS",
        funded_summary_identities=_ENTERPRISE_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER,
        skill_rows=(
            "Strategy & Transformation",
            "Operating Leadership",
            "Analytics",
            "Technical",
            "Additional",
        ),
        fluo=_BUSINESS_FLUO,
        selection_priorities=(
            "enterprise-leadership",
            "business-judgment",
            "operating-mechanism",
            "executive-communication",
            "cross-functional-influence",
        ),
    ),
    "business-operations-leadership": _professional_profile(
        "business-operations-leadership",
        ProfileFamily.BUSINESS_LEADERSHIP,
        (1, 3, 3, 2, 1),
        identity_heading="OPERATIONS & PROGRAM MANAGEMENT",
        funded_summary_identities=_OPERATIONS_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER,
        skill_rows=(
            "Operations & Programs",
            "Process Improvement",
            "Analytics",
            "Technical",
            "Leadership",
        ),
        fluo=_NO_FLUO,
        selection_priorities=(
            "operating-mechanism",
            "throughput-reliability",
            "frontline-or-team-leadership",
            "cross-functional-execution",
            "continuous-improvement",
        ),
    ),
    "business-commercial-gtm": _professional_profile(
        "business-commercial-gtm",
        ProfileFamily.BUSINESS_LEADERSHIP,
        (2, 3, 2, 2, 1),
        identity_heading="COMMERCIAL STRATEGY",
        funded_summary_identities=_COMMERCIAL_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER,
        skill_rows=(
            "Commercial Strategy",
            "Customer & GTM",
            "Analytics",
            "Technical",
            "Venture Strategy/GTM",
        ),
        fluo=_BUSINESS_FLUO,
        selection_priorities=(
            "commercial-judgment",
            "customer-segmentation",
            "pricing-monetization",
            "enterprise-adoption",
            "cross-functional-influence",
        ),
    ),
    "customer-technical-client-value": _professional_profile(
        "customer-technical-client-value",
        ProfileFamily.CUSTOMER_TECHNICAL,
        (2, 2, 2, 2, 2),
        identity_heading="TECHNICAL SOLUTIONS",
        funded_summary_identities=_TECHNICAL_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER,
        skill_rows=(
            "Solutions & Delivery",
            "Data & Platforms",
            "Programming & Cloud",
            "Customer Value",
            "Additional",
        ),
        fluo=_TECHNICAL_FLUO,
        selection_priorities=(
            "customer-translation",
            "solution-design",
            "enterprise-adoption",
            "technical-depth",
            "business-value",
        ),
    ),
    "customer-technical-deployed-systems": _professional_profile(
        "customer-technical-deployed-systems",
        ProfileFamily.CUSTOMER_TECHNICAL,
        (2, 2, 3, 2, 1),
        identity_heading="TECHNICAL SOLUTIONS",
        funded_summary_identities=_TECHNICAL_SUMMARY_IDENTITIES,
        summary_mode=SummaryMode.REQUIRED,
        title_mode=TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER,
        skill_rows=(
            "Technical Delivery",
            "Data & Platforms",
            "Programming & Cloud",
            "Customer Systems",
            "Additional",
        ),
        fluo=_TECHNICAL_FLUO,
        selection_priorities=(
            "deployed-systems",
            "implementation-ownership",
            "technical-depth",
            "customer-workflow",
            "reliability",
        ),
    ),
    "campus-student-service": ResumeProfile(
        profile_id="campus-student-service",
        family=ProfileFamily.CAMPUS,
        experience_slots=(),
        bullet_budget=BulletBudget(minimum=8, target=9, maximum=10),
        summary_mode=SummaryMode.REQUIRED,
        identity_heading="PROFILE",
        funded_summary_identities=_CAMPUS_SUMMARY_IDENTITIES,
        title_mode=TitleMode.OFFICIAL,
        skill_rows=("Campus Service", "Operations", "Tools", "Languages"),
        fluo=FluoPolicy(
            placement=FluoPlacement.INLINE_RELEVANCE_GATED,
            label="USC Venture Work",
            allowed_story_families=("student-experience", "gtm-partnership"),
            max_lines=2,
        ),
        selection_priorities=(
            "student-service",
            "communication",
            "administrative-reliability",
            "community",
        ),
    ),
    "campus-analytics": ResumeProfile(
        profile_id="campus-analytics",
        family=ProfileFamily.CAMPUS,
        experience_slots=(),
        bullet_budget=BulletBudget(minimum=8, target=9, maximum=10),
        summary_mode=SummaryMode.REQUIRED,
        identity_heading="PROFILE",
        funded_summary_identities=_CAMPUS_SUMMARY_IDENTITIES,
        title_mode=TitleMode.OFFICIAL,
        skill_rows=("Analytics", "Tools", "Campus", "Languages"),
        fluo=FluoPolicy(
            placement=FluoPlacement.INLINE_RELEVANCE_GATED,
            label="Venture Data",
            allowed_story_families=("data-analytics", "product-system"),
            max_lines=2,
        ),
        selection_priorities=(
            "analysis",
            "dashboarding",
            "process-improvement",
            "stakeholder-communication",
        ),
    ),
    "campus-communications": ResumeProfile(
        profile_id="campus-communications",
        family=ProfileFamily.CAMPUS,
        experience_slots=(),
        bullet_budget=BulletBudget(minimum=8, target=9, maximum=10),
        summary_mode=SummaryMode.REQUIRED,
        identity_heading="PROFILE",
        funded_summary_identities=_CAMPUS_SUMMARY_IDENTITIES,
        title_mode=TitleMode.OFFICIAL,
        skill_rows=("Digital Communications", "Analytics", "Tools", "Languages"),
        fluo=FluoPolicy(
            placement=FluoPlacement.INLINE_RELEVANCE_GATED,
            label="Venture Communications",
            allowed_story_families=("gtm-partnership", "content-channel"),
            max_lines=2,
        ),
        selection_priorities=(
            "audience-communication",
            "digital-content",
            "campaign-analysis",
            "cross-functional-coordination",
        ),
    ),
}


@dataclass(frozen=True)
class ProfileResolution:
    profile_id: str | None
    confidence: float
    reason: str
    needs_review: bool

    @property
    def profile(self) -> ResumeProfile | None:
        if self.profile_id is None:
            return None
        return PROFILE_REGISTRY[self.profile_id]


def get_profile(profile_id: str) -> ResumeProfile:
    try:
        return PROFILE_REGISTRY[profile_id]
    except KeyError as exc:
        valid = ", ".join(sorted(PROFILE_REGISTRY))
        raise ValueError(f"Unknown resume profile {profile_id!r}; expected one of: {valid}") from exc


def validate_experience_allocation(plan: ExperienceAllocationPlan) -> list[str]:
    """Validate the exact bullet allocation that assembly and QC must share.

    Ten bullets is the default and normal cap. Eleven requires one additional
    admitted story with a distinct value signal. Nine is permitted either when
    ten cannot fit or when admission leaves no tenth bullet above the quality
    floor. Fewer than nine fails closed rather than backfilling weak evidence.
    """
    profile = get_profile(plan.profile_id)
    if not profile.is_professional:
        return [f"{plan.profile_id}: professional experience allocation is not used for campus profiles"]

    errors: list[str] = []
    counts = plan.counts_dict()
    expected_companies = tuple(slot.company for slot in profile.experience_slots)
    supplied_companies = tuple(company for company, _ in plan.company_counts)

    if supplied_companies != expected_companies:
        errors.append(
            f"company order must be {expected_companies}, got {supplied_companies}"
        )
    if len(counts) != len(plan.company_counts):
        errors.append("company_counts contains duplicate company keys")

    for slot in profile.experience_slots:
        count = counts.get(slot.company)
        if count is None:
            continue
        if not slot.minimum <= count <= slot.maximum:
            errors.append(
                f"{slot.company} count {count} must be within "
                f"{slot.minimum}-{slot.maximum} for {profile.profile_id}"
            )

    expected_total = {
        BulletBudgetDecision.DEFAULT: profile.bullet_budget.target,
        BulletBudgetDecision.REBALANCE_DISTINCT_SIGNAL: profile.bullet_budget.target,
        BulletBudgetDecision.ADD_DISTINCT_SIGNAL: profile.bullet_budget.maximum,
        BulletBudgetDecision.COMPACT_FOR_PAGE_FIT: profile.bullet_budget.minimum,
        BulletBudgetDecision.COMPACT_FOR_QUALITY: profile.bullet_budget.minimum,
    }[plan.budget_decision]
    if plan.total != expected_total:
        errors.append(
            f"{plan.budget_decision.value} allocation must total {expected_total}, "
            f"got {plan.total}"
        )

    targets = profile.slots_dict()
    if all(company in counts for company in targets):
        deltas = tuple(counts[company] - targets[company] for company in expected_companies)
        positive = sorted(delta for delta in deltas if delta > 0)
        negative = sorted(delta for delta in deltas if delta < 0)
        expected_delta_shape = {
            BulletBudgetDecision.DEFAULT: ([], []),
            BulletBudgetDecision.REBALANCE_DISTINCT_SIGNAL: ([1], [-1]),
            BulletBudgetDecision.ADD_DISTINCT_SIGNAL: ([1], []),
            BulletBudgetDecision.COMPACT_FOR_PAGE_FIT: ([], [-1]),
            BulletBudgetDecision.COMPACT_FOR_QUALITY: ([], [-1]),
        }[plan.budget_decision]
        if (positive, negative) != expected_delta_shape:
            errors.append(
                f"{plan.budget_decision.value} allocation must change the profile target by "
                f"{expected_delta_shape}, got {(positive, negative)}"
            )
    return errors


def validate_page_proof_plan(plan: PageProofPlan) -> list[str]:
    """Validate the bounded supporting-proof exception without weakening defaults."""
    errors: list[str] = []
    try:
        profile = get_profile(plan.profile_id)
    except ValueError as exc:
        return [str(exc)]

    if plan.experience_plan.profile_id != plan.profile_id:
        errors.append(
            "page proof profile must match the Experience allocation profile"
        )
        return errors
    if not profile.is_professional:
        return [f"{plan.profile_id}: page-wide professional proof planning is not used for campus profiles"]

    if plan.mode in {SupportingProofMode.INLINE, SupportingProofMode.OMIT}:
        errors.extend(validate_experience_allocation(plan.experience_plan))
        if plan.reason is not SupportingProofReason.DEFAULT:
            errors.append(f"{plan.mode.value} proof mode must use the default reason")
        if plan.project_bullet_count:
            errors.append(f"{plan.mode.value} proof mode cannot reserve project bullets")
        if plan.replaced_experience_count:
            errors.append(f"{plan.mode.value} proof mode cannot replace Experience bullets")
        return errors

    if plan.reason is not SupportingProofReason.TOP_CRITERION_EVIDENCE:
        errors.append(
            "project-replacement requires a recorded top-criterion-evidence decision"
        )
    if plan.project_bullet_count not in {2, 3}:
        errors.append("project-replacement requires exactly 2 or 3 admitted project bullets")
    if plan.replaced_experience_count not in {1, 2}:
        errors.append("project-replacement must displace exactly 1 or 2 Experience bullets")

    expected_experience = profile.bullet_budget.target - plan.replaced_experience_count
    if plan.experience_bullet_count != expected_experience:
        errors.append(
            "project-replacement Experience count must equal the 10-bullet center minus "
            f"the recorded replacement count ({expected_experience}), got "
            f"{plan.experience_bullet_count}"
        )

    counts = plan.experience_plan.counts_dict()
    expected_companies = tuple(slot.company for slot in profile.experience_slots)
    if tuple(company for company, _ in plan.experience_plan.company_counts) != expected_companies:
        errors.append(
            f"project-replacement company order must be {expected_companies}"
        )
    if len(counts) != len(plan.experience_plan.company_counts):
        errors.append("project-replacement company counts contain duplicate keys")
    for slot in profile.experience_slots:
        count = counts.get(slot.company)
        if count is None:
            errors.append(f"project-replacement is missing the {slot.company} career block")
            continue
        continuity_floor = 2 if (
            profile.family is ProfileFamily.PRODUCT and slot.company == "FLAIRX AI"
        ) else 1
        if count < continuity_floor:
            errors.append(
                f"project-replacement requires at least {continuity_floor} bullet(s) for "
                f"{slot.company}, got {count}"
            )
        if count > slot.maximum:
            errors.append(
                f"project-replacement exceeds the {slot.maximum}-bullet ceiling for "
                f"{slot.company}"
            )

    expected_total_range = range(profile.bullet_budget.target, profile.bullet_budget.maximum + 1)
    if plan.total_proof_units not in expected_total_range:
        errors.append(
            "project-replacement must keep 10-11 page-wide proof units, got "
            f"{plan.total_proof_units}"
        )
    if plan.project_bullet_count < plan.replaced_experience_count:
        errors.append(
            "project-replacement cannot remove more Experience evidence than it adds"
        )
    if plan.project_bullet_count > plan.replaced_experience_count + 1:
        errors.append(
            "project-replacement may add at most one extra proof unit beyond the displaced bullets"
        )
    return errors


def validate_profile_registry() -> list[str]:
    """Return configuration errors; an empty list means the registry is valid."""
    errors: list[str] = []
    for key, profile in PROFILE_REGISTRY.items():
        if key != profile.profile_id:
            errors.append(f"{key}: registry key does not match profile_id")
        if profile.is_professional:
            companies = tuple(slot.company for slot in profile.experience_slots)
            if companies != PROFESSIONAL_COMPANY_ORDER:
                errors.append(f"{key}: company order must be {PROFESSIONAL_COMPANY_ORDER}")
            if profile.experience_bullet_total != 10:
                errors.append(f"{key}: expected a 10-bullet center allocation")
            if profile.bullet_budget != BulletBudget(9, 10, 11):
                errors.append(f"{key}: professional bullet budget must be bounded at 9-11")
            if sum(slot.minimum for slot in profile.experience_slots) > profile.bullet_budget.minimum:
                errors.append(f"{key}: slot floors cannot produce the 9-bullet compact build")
            if sum(slot.maximum for slot in profile.experience_slots) < profile.bullet_budget.maximum:
                errors.append(f"{key}: slot ceilings cannot produce the 11-bullet additive build")
            for slot in profile.experience_slots:
                if not slot.minimum <= slot.target <= slot.maximum:
                    errors.append(f"{key}: invalid slot bounds for {slot.company}")
                if slot.company == "OPTUM" and slot.minimum < 1:
                    errors.append(f"{key}: Optum continuity floor must remain at least one")
            if profile.skill_policy is None:
                errors.append(f"{key}: professional profile requires a Skills assembly policy")
            else:
                if profile.skill_policy.default_rows != profile.skill_rows:
                    errors.append(
                        f"{key}: legacy skill_rows must equal the Skills policy default_rows"
                    )
                if profile.skill_policy.minimum_rows != 5:
                    errors.append(f"{key}: professional Skills minimum must remain five")
                if profile.skill_policy.target_rows != 5:
                    errors.append(f"{key}: professional Skills target must remain five")
                if profile.skill_policy.maximum_rows != 6:
                    errors.append(f"{key}: professional Skills maximum must remain six")
        elif profile.experience_slots:
            errors.append(f"{key}: campus profiles cannot use professional company slots")
        if profile.fluo.allow_experience or profile.fluo.counts_toward_experience:
            errors.append(f"{key}: Fluo cannot be promoted into Experience in this registry version")
        if profile.summary_mode is not SummaryMode.REQUIRED:
            errors.append(f"{key}: every assembly preset must preserve the identity summary")
        if not profile.identity_heading or profile.identity_heading != profile.identity_heading.upper():
            errors.append(f"{key}: identity heading must be non-empty uppercase text")
        if not profile.funded_summary_identities:
            errors.append(f"{key}: at least one pool-funded summary identity is required")
        if profile.fluo.placement is FluoPlacement.OMIT and profile.fluo.max_lines:
            errors.append(f"{key}: omitted Fluo policy cannot reserve lines")
    return errors


def _contains(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _strategy_text(strategy: Mapping[str, object]) -> str:
    pieces: list[str] = []
    for key in ("top_signals", "gaps"):
        value = strategy.get(key, [])
        if isinstance(value, (list, tuple)):
            pieces.extend(str(item) for item in value)
    for key in (
        "role_title",
        "archetype",
        "role_family",
        "nonpm_subtype",
        "bullet_balance",
        "primary_framing_axis",
        "secondary_framing_axis",
        "positioning_narrative",
    ):
        pieces.append(str(strategy.get(key, "")))
    return " ".join(pieces)


def _skill_relevance_score(text: str, option: SkillRowOption) -> tuple[int, int]:
    """Return (ranking score, semantic-match count) for one controlled row.

    Short tags use word boundaries so ``AI`` does not match ``retail``. Longer
    phrases intentionally use literal containment: the input is already the
    structured Step 0 rationale, not arbitrary resume prose.
    """

    matches = 0
    for raw_tag in option.relevance_tags:
        tag = raw_tag.strip().casefold()
        if not tag:
            continue
        if len(tag) <= 3 and tag.isalnum():
            found = bool(re.search(rf"\b{re.escape(tag)}\b", text, re.I))
        else:
            found = tag in text
        matches += int(found)
    return matches * 10, matches


def resolve_skills_assembly_plan(
    profile: ResumeProfile,
    strategy: Mapping[str, object] | None = None,
    *,
    available_labels: Iterable[str] | None = None,
    requested_rows: int = 5,
) -> SkillsAssemblyPlan:
    """Resolve the controlled five-row Skills slate and a possible sixth.

    This selects labels, never wording. The fifth row may change when a
    role-specific signal clearly beats the default tail. A requested sixth is
    returned only when it has positive role evidence and adds a signal kind not
    already present; page geometry remains a separate release gate.
    """

    if not profile.is_professional:
        if requested_rows != len(profile.skill_rows):
            raise ValueError(
                f"{profile.profile_id}: campus Skills plan requires exactly "
                f"{len(profile.skill_rows)} rows"
            )
        return SkillsAssemblyPlan(
            profile_id=profile.profile_id,
            row_labels=profile.skill_rows,
            decision=SkillRowDecision.DEFAULT_FIVE,
        )
    if requested_rows not in {5, 6}:
        raise ValueError("professional Skills requested_rows must be 5 or 6")
    if profile.skill_policy is None:
        raise ValueError(f"{profile.profile_id}: professional Skills policy is missing")

    policy = profile.skill_policy
    available = (
        {str(label).strip() for label in available_labels if str(label).strip()}
        if available_labels is not None
        else set(policy.default_rows)
    )
    missing_core = sorted(set(policy.core_rows) - available)
    if missing_core:
        raise ValueError(
            f"{profile.profile_id}: controlled value bank is missing core Skills rows "
            f"{missing_core}"
        )

    strategy_text = _strategy_text(strategy or {}).casefold()
    default_labels = set(policy.default_rows)
    scored: list[tuple[SkillRowOption, int, int, int]] = []
    for order, option in enumerate(policy.flexible_rows):
        if option.label not in available:
            continue
        semantic_score, match_count = _skill_relevance_score(strategy_text, option)
        fallback_score = 4 if option.label in default_labels else 0
        required_score = (
            1000
            if profile.fluo.placement is FluoPlacement.INLINE_REQUIRED
            and option.label == profile.fluo.label
            else 0
        )
        scored.append(
            (option, required_score + semantic_score + fallback_score, match_count, order)
        )

    flexible_needed = policy.target_rows - len(policy.core_rows)
    if len(scored) < flexible_needed:
        raise ValueError(
            f"{profile.profile_id}: only {len(scored)} funded flexible Skills rows are "
            f"available; {flexible_needed} required"
        )
    ranked = sorted(scored, key=lambda item: (-item[1], item[3], item[0].label))
    selected = list(ranked[:flexible_needed])
    optional_sixth: SkillRowOption | None = None

    if requested_rows == 6 and policy.maximum_rows >= 6:
        selected_kinds = {item[0].signal_kind for item in selected}
        eligible_sixths = [
            item
            for item in ranked[flexible_needed:]
            if item[2] > 0 and item[0].signal_kind not in selected_kinds
        ]
        if eligible_sixths:
            optional_sixth = eligible_sixths[0][0]
            selected.append(eligible_sixths[0])

    chosen_labels = {item[0].label for item in selected}
    ordered_flexible = tuple(
        option.label
        for option in policy.flexible_rows
        if option.label in chosen_labels
    )
    row_labels = tuple(policy.core_rows) + ordered_flexible
    decision = (
        SkillRowDecision.ADD_DISTINCT_SIXTH
        if optional_sixth is not None
        else SkillRowDecision.DEFAULT_FIVE
    )
    audit = tuple((item[0].label, item[1]) for item in ranked)
    return SkillsAssemblyPlan(
        profile_id=profile.profile_id,
        row_labels=row_labels,
        decision=decision,
        optional_sixth_label=(optional_sixth.label if optional_sixth else None),
        selection_audit=audit,
    )


def resolve_profile(
    *,
    strategy: Mapping[str, object] | None = None,
    context_tags: Iterable[str] = (),
    explicit_profile: str | None = None,
) -> ProfileResolution:
    """Map existing Step 0 semantics into an assembly preset.

    This function intentionally does not inspect the raw title or JD.  Role
    classification already belongs to Step 0; repeating it here would create a
    second taxonomy that could disagree with the live PM/NONPM router.  Campus
    presets are supplied explicitly or via a reviewed, specific context tag.
    """
    strategy = strategy or {}
    tags = {str(tag).strip().lower() for tag in context_tags if str(tag).strip()}

    if explicit_profile:
        get_profile(explicit_profile)
        return ProfileResolution(explicit_profile, 1.0, "validated explicit profile", False)

    campus_profiles = {
        "campus-student-service": "campus-student-service",
        "campus-analytics": "campus-analytics",
        "campus-communications": "campus-communications",
    }
    selected_campus = sorted(tags.intersection(campus_profiles))
    if len(selected_campus) == 1:
        profile_id = campus_profiles[selected_campus[0]]
        return ProfileResolution(profile_id, 1.0, "reviewed campus assembly tag", False)
    if len(selected_campus) > 1:
        return ProfileResolution(
            None,
            0.0,
            "multiple campus assembly tags supplied",
            True,
        )

    combined = _strategy_text(strategy).lower()

    nonpm_subtype = str(strategy.get("nonpm_subtype") or "").strip().lower()
    role_family = str(strategy.get("role_family") or "").strip().lower()
    archetype = str(strategy.get("archetype") or "").strip().lower()
    role_title = str(strategy.get("role_title") or "").strip().lower()
    # Some research-heavy product-strategy internships are easy for Step 0 to
    # misclassify as generic research/intelligence. Keep them on the product
    # profile only when the role is explicitly embedded in product decisions;
    # a title match alone is not enough.
    if "product strategy" in role_title:
        embedded_product_signals = (
            r"product team",
            r"product decisions?",
            r"user research",
            r"usability",
            r"prototypes?",
            r"product reviews?",
            r"development sprint",
            r"roadmap",
        )
        signal_count = sum(
            bool(re.search(pattern, combined, re.I))
            for pattern in embedded_product_signals
        )
        if signal_count >= 2:
            return ProfileResolution(
                "product-general",
                0.90,
                "embedded product-strategy work maps to the product profile",
                False,
            )
    if role_family == "pm" and nonpm_subtype:
        return ProfileResolution(
            None,
            0.0,
            "conflicting Step 0 output: PM role_family cannot carry nonpm_subtype",
            True,
        )
    if nonpm_subtype and role_family not in {"strategy-consulting", "ops-execution"}:
        return ProfileResolution(
            None,
            0.0,
            "conflicting Step 0 output: nonpm_subtype requires a non-PM role_family",
            True,
        )
    if nonpm_subtype == "client-implementation":
        deployed = _contains(
            combined,
            (
                r"deployed systems?",
                r"production deployment",
                r"implementation ownership",
                r"technical delivery",
            ),
        )
        return ProfileResolution(
            (
                "customer-technical-deployed-systems"
                if deployed
                else "customer-technical-client-value"
            ),
            0.90,
            "mapped Step 0 client-implementation subtype",
            False,
        )
    if nonpm_subtype == "commercial-gtm":
        return ProfileResolution(
            "business-commercial-gtm", 0.92, "mapped Step 0 commercial-GTM subtype", False
        )
    if nonpm_subtype == "ops-pgm":
        return ProfileResolution(
            "business-operations-leadership", 0.92, "mapped Step 0 operations subtype", False
        )
    if nonpm_subtype in {
        "strategy-consulting",
        "bizops-sando",
        "research-intelligence",
        "ai-automation",
    }:
        return ProfileResolution(
            "business-enterprise-leadership",
            0.88,
            f"mapped Step 0 {nonpm_subtype} subtype",
            False,
        )
    if role_family == "pm":
        valid_pm_archetypes = {
            "technical_pm",
            "growth_pm",
            "enterprise_pm",
            "strategy_pm",
            "ai_pm",
            "consumer_pm",
            "platform_pm",
            "generalist",
        }
        if archetype not in valid_pm_archetypes:
            return ProfileResolution(
                None,
                0.0,
                "PM Step 0 output is missing a supported archetype",
                True,
            )
        if archetype == "ai_pm":
            profile_id = "product-ai-zero-to-one"
        elif archetype in {"platform_pm", "enterprise_pm", "technical_pm"} and _contains(
            combined, (r"data platform", r"data infrastructure", r"analytics platform", r"database")
        ):
            profile_id = "product-data-platform"
        else:
            profile_id = "product-general"
        return ProfileResolution(profile_id, 0.90, "mapped existing Step 0 PM fields", False)

    if role_family in {"strategy-consulting", "ops-execution"}:
        return ProfileResolution(
            None,
            0.0,
            "non-PM Step 0 output is missing a supported nonpm_subtype",
            True,
        )

    return ProfileResolution(
        None,
        0.0,
        "explicit assembly preset or complete reviewed Step 0 output required",
        True,
    )


_REGISTRY_ERRORS = validate_profile_registry()
if _REGISTRY_ERRORS:
    raise RuntimeError("Invalid resume profile registry: " + "; ".join(_REGISTRY_ERRORS))
