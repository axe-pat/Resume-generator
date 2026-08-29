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


PROFILE_REGISTRY_VERSION = "2026-08-28.5"
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
    return ResumeProfile(
        profile_id=profile_id,
        family=family,
        experience_slots=slots,
        bullet_budget=BulletBudget(minimum=9, target=10, maximum=11),
        summary_mode=summary_mode,
        identity_heading=identity_heading,
        funded_summary_identities=tuple(funded_summary_identities),
        title_mode=title_mode,
        skill_rows=tuple(skill_rows),
        fluo=fluo,
        selection_priorities=tuple(selection_priorities),
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
