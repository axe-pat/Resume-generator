"""Build an inert, authoritative Pass-1 override from reviewed resume assets.

The legacy PM and NONPM master prompts remain untouched.  Callers may append the
tail produced here in shadow mode, compare its output with the incumbent, and
discard it without changing live behavior.  The adapter owns no role taxonomy:
it delegates profile resolution to :mod:`shared.resume_profiles` and turns the
resolved profile plus a validated allocation plan into prompt instructions.

Experience and project bullets are selection-only.  Every selectable bullet is
loaded verbatim from the reviewed A/B/C batch slates; the model is explicitly
forbidden to rewrite, merge, shorten, or create one.  Batch D supplies the
profile-funded summary and community candidates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from shared.resume_profiles import (
    PROFESSIONAL_COMPANY_ORDER,
    BulletBudgetDecision,
    ExperienceAllocationPlan,
    FluoPlacement,
    ProfileResolution,
    ResumeProfile,
    SkillRowDecision,
    SkillsAssemblyPlan,
    SummaryMode,
    TitleMode,
    get_profile,
    resolve_profile,
    resolve_skills_assembly_plan,
    skills_section_heading,
    validate_experience_allocation,
    validate_summary_identity,
)
from shared.resume_runtime import (
    V2_SKILLS_SELECTOR_ENV,
    V2FeatureMode,
    requested_v2_skill_rows,
    resolve_v2_feature_mode,
)


ADAPTER_VERSION = "2026-09-03.2"
REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_BATCH_DIR = REPO_ROOT / "docs" / "resume_generator_reviews" / "variant_batches"
DEFAULT_CAUSAL_BATCH_PATHS = (
    REVIEW_BATCH_DIR / "BATCH_A_FLAIRX_FLUO_PROJECTS.json",
    REVIEW_BATCH_DIR / "BATCH_B_GOJEK_HEVO_BATCH.json",
    REVIEW_BATCH_DIR / "BATCH_C_HEVO_INTUIT_OPTUM.json",
)
DEFAULT_SUMMARY_BATCH_PATH = REVIEW_BATCH_DIR / "BATCH_D_SUMMARIES_SKILLS.json"

OVERRIDE_START = "<<< BEGIN RESUME V2 AUTHORITATIVE PASS-1 OVERRIDE >>>"
OVERRIDE_END = "<<< END RESUME V2 AUTHORITATIVE PASS-1 OVERRIDE >>>"

# These are the semantic families covered by the completed A/B/C audit.  This
# list describes the reusable candidate corpus, not a queue or employer route.
REQUIRED_REVIEW_FAMILIES = (
    "F-AVATAR",
    "F-CEIPAL",
    "F-ENTERPRISE",
    "F-OPS",
    "F-SOURCING",
    "FLUO",
    "P-FOUNDER",
    "P-GRAB",
    "P-LOREAL",
    "H-QUERY",
    "H-REGRESSION",
    "H-SUPPORT-OPS",
    "G-SUPPLY",
    "G-PRICING",
    "G-LATENCY",
    "H-BATCHSHIFT",
    "H-MONITORING",
    "I-BILLING",
    "I-GOVERNANCE",
    "I-INCIDENT",
    "O-AFFORDABILITY",
    "O-PROVIDER",
)

EXPERIENCE_FAMILIES = frozenset(
    family
    for family in REQUIRED_REVIEW_FAMILIES
    if family.startswith(("F-", "G-", "H-", "I-", "O-"))
)

# A recommendation explicitly held for a human is reviewed, but is not yet a
# shipping option.  Keeping it out of the tail is what makes the prompt bank a
# selectable slate instead of a review transcript.
NON_SELECTABLE_RECOMMENDATION_STATUSES = frozenset(
    {
        "challenger_hold_for_human",
        "hold_for_human",
        "rejected",
        "retired",
        "retire_dominated",
    }
)
RETIRED_VERDICTS = frozenset(
    {
        "retire",
        "retired",
        "retire_dominated",
        "reject",
        "rejected",
    }
)
# Quality/review status is deliberately not a shipping permission.  Earlier
# versions exposed every status except rejected/retired, which made labels such
# as ``challenger_review`` both documentation and an accidental live switch.
# The explicit allowlist preserves status for audit while keeping it out of the
# model's ranking context.
SHIPPING_SUMMARY_SELECTABILITY = {"shipping"}
KNOWN_SUMMARY_SELECTABILITY = frozenset({"shipping", "review"})
NON_SELECTABLE_SUPPORT_STATUSES = frozenset({"rejected", "retired"})


@dataclass(frozen=True)
class ReviewedBullet:
    story_family: str
    variant_id: str
    text: str
    use_case: str
    status: str
    source_batch: str
    archetype: str
    fluo_story_family: str
    line_cost: int
    assembly_modes: tuple[str, ...]


@dataclass(frozen=True)
class ReviewedSummary:
    candidate_id: str
    text: str
    use_case: str
    status: str
    selectability: str
    eligible_profiles: tuple[str, ...]
    required_page_evidence: tuple[str, ...]
    signal_tags: tuple[str, ...] = ()
    line_cost: int | None = None


@dataclass(frozen=True)
class ReviewedCommunity:
    candidate_id: str
    text: str
    use_case: str
    status: str
    selectability: str


@dataclass(frozen=True)
class ReviewedSupportRow:
    candidate_id: str
    row_label: str
    text: str
    use_case: str
    status: str
    selectability: str
    eligible_profiles: tuple[str, ...]
    relevance_tags: tuple[str, ...]
    line_cost: int


@dataclass(frozen=True)
class ReviewedPromptBank:
    covered_families: tuple[str, ...]
    variants: tuple[ReviewedBullet, ...]
    variants_by_family: tuple[tuple[str, tuple[ReviewedBullet, ...]], ...]
    suppressed_variant_ids: frozenset[str]
    summaries: tuple[ReviewedSummary, ...]
    communities: tuple[ReviewedCommunity, ...]
    support_rows: tuple[ReviewedSupportRow, ...] = ()

    def family_map(self) -> dict[str, tuple[ReviewedBullet, ...]]:
        return dict(self.variants_by_family)


@dataclass(frozen=True)
class Pass1PromptOverride:
    version: str
    resolution: ProfileResolution
    profile: ResumeProfile
    allocation_plan: ExperienceAllocationPlan
    bank: ReviewedPromptBank
    eligible_summaries: tuple[ReviewedSummary, ...]
    skills_plan: SkillsAssemblyPlan
    shadow_skills_plan: SkillsAssemblyPlan | None
    tail: str

    @property
    def profile_id(self) -> str:
        return self.profile.profile_id

    @property
    def bullet_total(self) -> int:
        return self.allocation_plan.total


@dataclass(frozen=True)
class AdaptedPass1Prompt:
    prompt: str
    override: Pass1PromptOverride


# Skills remain selectable for JD relevance, but never free-written.  Values
# here are profile-owned strings: the selector may choose one complete value
# for a funded label and may not reorder, splice, or keyword-inject it.
PROFILE_SKILL_VALUE_BANK: Mapping[str, tuple[str, ...]] = {
    "Product Leadership": (
        "Product Strategy, Roadmap Ownership, Customer Discovery, Requirements Definition, Backlog Prioritization",
        "User Research, Rapid Prototyping, Usability Testing, Experiment Design, Cross-functional Delivery",
        "Market Analysis, Competitive Research, Go-to-Market Strategy, Pricing, Product Launches",
    ),
    "Data & Analytics": (
        "Funnel Analysis, A/B Testing, Customer Interviews, Experiment Design, KPI Definition",
        "SQL, Product Usage Analysis, Funnel Instrumentation, Cohort Analysis, Retention, KPI Tracking",
        "Research-to-Roadmap, Funnel Analysis, A/B Testing, Customer Interviews, Experiment Design",
    ),
    "Technical": (
        "Python, Java, SQL, APIs, AWS, Docker, Git; Jira, Confluence",
        "Python, SQL, APIs, AWS, Docker, Figma; Jira, Confluence",
    ),
    "AI & Automation": (
        "LLM & GenAI Workflow Experimentation, Model Capability Tradeoff Evaluation, Rapid Prototyping",
    ),
    "AI Product Development": (
        "AI Workflow Design, Human-in-the-Loop Systems, Model Evaluation, Rapid Prototyping, GenAI Product Strategy",
        "LLM Workflows, Evaluation Design, AI Guardrails, Model Tradeoffs, Rapid Prototyping",
    ),
    "Data Platforms": (
        "Data Pipelines, Platform Reliability, Observability, API Design, Data Modeling, Developer Experience",
    ),
    "Strategy & Transformation": (
        "Operating Model Design, Market Sizing, Commercial Diligence, Scenario Analysis, Executive Recommendations",
    ),
    "Operating Leadership": (
        "Cross-functional Execution, Governance Design, Portfolio Prioritization, Operating Cadences, Stakeholder Alignment",
    ),
    "Analytics": (
        "Python, SQL, Tableau, Power BI, Excel, KPI Modeling, A/B Testing",
    ),
    "Operations & Programs": (
        "Cross-functional Program Management, Delivery Sequencing, Governance Design, OKR & KPI Tracking, Stakeholder Alignment",
    ),
    "Process Improvement": (
        "Process Mapping, Root-Cause Analysis, Risk Triage, Workflow Standardization, Continuous Improvement",
    ),
    "Leadership": (
        "Executive Communication, Team Leadership, Cross-functional Influence, Decision Cadences, Change Management",
    ),
    "Commercial Strategy": (
        "Customer Segmentation, Pricing & Monetization, Market Sizing, Commercial Diligence, Competitive Analysis",
    ),
    "Customer & GTM": (
        "Customer Discovery, ICP Definition, Funnel Analysis, Partnerships, Revenue Operations, Go-to-Market",
    ),
    "Venture Strategy/GTM": (
        "Market Entry, Partnership Strategy, Customer Segmentation, Offer Design, Go-to-Market Experimentation",
    ),
    "Solutions & Delivery": (
        "Solution Design, Implementation Planning, Requirements Translation, Rollout Sequencing, Issue Remediation",
    ),
    "Data & Platforms": (
        "Data Pipelines, APIs, Platform Integrations, Reliability, Observability, Data Modeling",
    ),
    "Programming & Cloud": (
        "Python, Java, SQL, AWS, Docker, APIs, Git",
    ),
    "Customer Value": (
        "Customer Discovery, Adoption Planning, Value Realization, Stakeholder Translation, Executive Communication",
    ),
    "Technical Delivery": (
        "Technical Program Delivery, Systems Integration, Release Planning, Risk Triage, Cross-functional Execution",
    ),
    "Customer Systems": (
        "Enterprise Workflows, Implementation Ownership, Incident Response, Adoption, Service Reliability",
    ),
}


def skill_value_candidates_for_profile(
    profile: ResumeProfile,
    bank: ReviewedPromptBank,
    row_labels: Sequence[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return the exact value allowlist for every possible funded Skills label."""

    values: dict[str, tuple[str, ...]] = {}
    inline_fluo_values = tuple(
        f"Fluo, {variant.text}"
        for variant in bank.family_map().get("FLUO", ())
        if "inline" in variant.assembly_modes
        and variant.line_cost <= profile.fluo.max_lines
        and variant.fluo_story_family in profile.fluo.allowed_story_families
    )
    labels = tuple(row_labels or profile.skill_rows)
    support_values: dict[str, tuple[str, ...]] = {}
    for label in {row.row_label for row in bank.support_rows}:
        support_values[label] = tuple(
            row.text
            for row in bank.support_rows
            if row.row_label == label and profile.profile_id in row.eligible_profiles
        )
    for label in labels:
        if label == profile.fluo.label:
            base = PROFILE_SKILL_VALUE_BANK.get(label, ())
            candidates = base + inline_fluo_values
        elif label in {"Additional", "Community"}:
            candidates = tuple(item.text for item in bank.communities)
        elif label in support_values:
            candidates = support_values[label]
        else:
            candidates = PROFILE_SKILL_VALUE_BANK.get(label, ())
        if not candidates:
            raise ValueError(
                f"{profile.profile_id}: no controlled Skills value funds {label!r}"
            )
        values[label] = candidates

    if (
        profile.fluo.label
        and profile.fluo.label not in values
        and profile.fluo.placement is FluoPlacement.INLINE_RELEVANCE_GATED
    ):
        if not inline_fluo_values:
            raise ValueError(
                f"{profile.profile_id}: no eligible inline Fluo value is available"
            )
        values[profile.fluo.label] = inline_fluo_values
    return values


def available_skill_labels_for_profile(
    profile: ResumeProfile,
    bank: ReviewedPromptBank,
) -> tuple[str, ...]:
    """Return policy labels that currently have at least one shipping value."""

    if profile.skill_policy is None:
        candidates = profile.skill_rows
    else:
        candidates = tuple(
            dict.fromkeys((*profile.skill_policy.core_rows, *profile.skill_policy.flexible_labels))
        )
    funded: list[str] = []
    for label in candidates:
        try:
            skill_value_candidates_for_profile(profile, bank, (label,))
        except ValueError:
            continue
        funded.append(label)
    return tuple(funded)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"review artifact does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def _normalized_status(value: object) -> str:
    return str(value or "reviewed_recommendation").strip().lower().replace("-", "_")


def _is_retired_verdict(value: object) -> bool:
    status = _normalized_status(value)
    return status in RETIRED_VERDICTS or status.startswith("retire_")


def load_reviewed_prompt_bank(
    *,
    causal_batch_paths: Sequence[Path] = DEFAULT_CAUSAL_BATCH_PATHS,
    summary_batch_path: Path = DEFAULT_SUMMARY_BATCH_PATH,
) -> ReviewedPromptBank:
    """Load the reviewed prompt bank and fail closed on coverage drift.

    ``recommended_variants`` is the sole bullet source.  Incumbent rows are
    consumed only to build a suppression set, never as fallback content.
    """

    family_rows: dict[str, tuple[ReviewedBullet, ...]] = {}
    all_recommendation_ids: set[str] = set()
    all_recommendation_text: set[str] = set()
    incumbent_ids: set[str] = set()
    explicitly_retired_ids: set[str] = set()
    held_recommendation_ids: set[str] = set()
    errors: list[str] = []

    for path in causal_batch_paths:
        batch = _load_json(path)
        mode = str(batch.get("mode", batch.get("status", ""))).replace("_", "-")
        if mode != "review-only":
            errors.append(f"{path.name}: expected review-only mode, got {mode!r}")
        wiring = batch.get("live_wiring", batch.get("live_prompts_modified"))
        if wiring is not False:
            errors.append(f"{path.name}: review batch must remain inert")
        families = batch.get("families")
        if not isinstance(families, dict):
            errors.append(f"{path.name}: families must be an object")
            continue

        for family_name, family in families.items():
            if family_name in family_rows:
                errors.append(f"{family_name}: appears in more than one review batch")
                continue
            if not isinstance(family, dict):
                errors.append(f"{family_name}: family review must be an object")
                continue

            incumbents = family.get("incumbents", ())
            if not isinstance(incumbents, list):
                errors.append(f"{family_name}: incumbents must be a list")
                incumbents = ()
            for incumbent in incumbents:
                stable_id = str(incumbent.get("stable_id", "")).strip()
                if not stable_id:
                    errors.append(f"{family_name}: incumbent is missing stable_id")
                    continue
                incumbent_ids.add(stable_id)
                if _is_retired_verdict(incumbent.get("verdict")):
                    explicitly_retired_ids.add(stable_id)

            recommendations = family.get("recommended_variants")
            if not isinstance(recommendations, list):
                errors.append(f"{family_name}: recommended_variants must be a list")
                recommendations = ()

            selectable: list[ReviewedBullet] = []
            for record in recommendations:
                variant_id = str(record.get("variant_id", "")).strip()
                text = str(record.get("text", "")).strip()
                use_case = str(record.get("use_case", "")).strip()
                status = _normalized_status(record.get("status"))
                archetype = str(record.get("archetype", "")).strip().lower()
                fluo_story_family = str(record.get("fluo_story_family", "")).strip()
                line_cost = int(record.get("line_cost", 0) or 0)
                assembly_modes = tuple(str(item) for item in record.get("assembly_modes", ()))
                if not variant_id:
                    errors.append(f"{family_name}: recommendation is missing variant_id")
                    continue
                if variant_id in all_recommendation_ids:
                    errors.append(f"{variant_id}: duplicate recommended variant ID")
                all_recommendation_ids.add(variant_id)
                if not text:
                    errors.append(f"{family_name}/{variant_id}: recommendation has no text")
                elif text in all_recommendation_text:
                    errors.append(f"{family_name}/{variant_id}: duplicate recommended text")
                all_recommendation_text.add(text)
                if not use_case:
                    errors.append(f"{family_name}/{variant_id}: recommendation has no use case")
                if status in NON_SELECTABLE_RECOMMENDATION_STATUSES:
                    held_recommendation_ids.add(variant_id)
                    continue
                if family_name in EXPERIENCE_FAMILIES and archetype not in {
                    "diagnostic", "action", "context", "impact-first"
                }:
                    errors.append(
                        f"{family_name}/{variant_id}: selectable Experience variant "
                        "requires controlled archetype metadata"
                    )
                if family_name == "FLUO" and fluo_story_family not in {
                    "product-system", "customer-insight", "gtm-partnership",
                    "founder-strategy", "data-analytics", "customer-deployment",
                }:
                    errors.append(
                        f"{family_name}/{variant_id}: selectable Fluo variant requires "
                        "controlled fluo_story_family metadata"
                    )
                if family_name == "FLUO" and (
                    line_cost not in {1, 2, 3, 4}
                    or not assembly_modes
                    or set(assembly_modes) - {"inline", "project-replacement"}
                ):
                    errors.append(
                        f"{family_name}/{variant_id}: selectable Fluo variant requires "
                        "line_cost and controlled assembly_modes metadata"
                    )
                selectable.append(
                    ReviewedBullet(
                        story_family=family_name,
                        variant_id=variant_id,
                        text=text,
                        use_case=use_case,
                        status=status,
                        source_batch=path.name,
                        archetype=archetype,
                        fluo_story_family=fluo_story_family,
                        line_cost=line_cost,
                        assembly_modes=assembly_modes,
                    )
                )

            if family_name in EXPERIENCE_FAMILIES and not selectable:
                errors.append(
                    f"{family_name}: an Experience family has no selectable reviewed variant"
                )
            if not selectable and recommendations:
                errors.append(
                    f"{family_name}: every recommended variant is still held or rejected"
                )
            if not recommendations and incumbents and not all(
                _is_retired_verdict(row.get("verdict")) for row in incumbents
            ):
                errors.append(
                    f"{family_name}: empty slate is permitted only when every incumbent is retired"
                )
            family_rows[family_name] = tuple(selectable)

    observed_families = set(family_rows)
    missing_families = sorted(set(REQUIRED_REVIEW_FAMILIES) - observed_families)
    unexpected_families = sorted(observed_families - set(REQUIRED_REVIEW_FAMILIES))
    if missing_families:
        errors.append(f"review bank is missing story families: {missing_families}")
    if unexpected_families:
        errors.append(f"review bank has unowned story families: {unexpected_families}")
    retired_recommended = sorted(explicitly_retired_ids & all_recommendation_ids)
    if retired_recommended:
        errors.append(f"retired variants returned to a recommended slate: {retired_recommended}")

    summary_batch = _load_json(summary_batch_path)
    if summary_batch.get("mode") != "review-only" or summary_batch.get("live_wiring") is not False:
        errors.append(f"{summary_batch_path.name}: summary review must remain inert")

    summaries: list[ReviewedSummary] = []
    summary_ids: set[str] = set()
    for record in summary_batch.get("summary_candidates", ()):
        candidate_id = str(record.get("candidate_id", "")).strip()
        text = str(record.get("text", "")).strip()
        use_case = str(record.get("use_case", "")).strip()
        status = _normalized_status(record.get("status"))
        # Release permission is explicit and independent of editorial status.
        # Missing permission fails validation instead of silently exposing a
        # newly-authored candidate to the live selector.
        selectability = str(record.get("selectability", "")).strip().lower()
        profiles = tuple(str(item).strip() for item in record.get("eligible_profiles", ()))
        evidence = tuple(str(item).strip() for item in record.get("required_page_evidence", ()))
        signal_tags = tuple(
            str(item).strip() for item in record.get("signal_tags", ()) if str(item).strip()
        )
        raw_line_cost = record.get("line_cost")
        line_cost = int(raw_line_cost) if raw_line_cost not in (None, "") else None
        if not candidate_id or not text or not use_case or not profiles:
            errors.append(f"{candidate_id or '<summary>'}: incomplete summary candidate")
            continue
        if candidate_id in summary_ids:
            errors.append(f"{candidate_id}: duplicate summary candidate ID")
        summary_ids.add(candidate_id)
        if selectability not in KNOWN_SUMMARY_SELECTABILITY:
            errors.append(
                f"{candidate_id}: summary selectability must be one of "
                f"{sorted(KNOWN_SUMMARY_SELECTABILITY)}, got {selectability!r}"
            )
        for profile_id in profiles:
            try:
                identity_errors = validate_summary_identity(profile_id, text)
            except ValueError as exc:
                errors.append(f"{candidate_id}: {exc}")
            else:
                errors.extend(f"{candidate_id}: {error}" for error in identity_errors)
        if selectability in SHIPPING_SUMMARY_SELECTABILITY:
            summaries.append(
                ReviewedSummary(
                    candidate_id=candidate_id,
                    text=text,
                    use_case=use_case,
                    status=status,
                    selectability=selectability,
                    eligible_profiles=profiles,
                    required_page_evidence=evidence,
                    signal_tags=signal_tags,
                    line_cost=line_cost,
                )
            )

    communities: list[ReviewedCommunity] = []
    community_ids: set[str] = set()
    for record in summary_batch.get("community_candidates", ()):
        candidate_id = str(record.get("candidate_id", "")).strip()
        text = str(record.get("text", "")).strip()
        use_case = str(record.get("use_case", "")).strip()
        status = _normalized_status(record.get("status"))
        selectability = str(record.get("selectability", "")).strip().lower()
        if not candidate_id or not text or not use_case:
            errors.append(f"{candidate_id or '<community>'}: incomplete community candidate")
            continue
        if candidate_id in community_ids:
            errors.append(f"{candidate_id}: duplicate community candidate ID")
        community_ids.add(candidate_id)
        if selectability not in KNOWN_SUMMARY_SELECTABILITY:
            errors.append(
                f"{candidate_id}: community selectability must be one of "
                f"{sorted(KNOWN_SUMMARY_SELECTABILITY)}, got {selectability!r}"
            )
        if (
            selectability in SHIPPING_SUMMARY_SELECTABILITY
            and status not in NON_SELECTABLE_SUPPORT_STATUSES
        ):
            communities.append(
                ReviewedCommunity(candidate_id, text, use_case, status, selectability)
            )

    support_rows: list[ReviewedSupportRow] = []
    support_ids: set[str] = set()
    for record in summary_batch.get("support_row_candidates", ()):
        candidate_id = str(record.get("candidate_id", "")).strip()
        row_label = str(record.get("row_label", "")).strip()
        text = str(record.get("text", "")).strip()
        use_case = str(record.get("use_case", "")).strip()
        status = _normalized_status(record.get("status"))
        selectability = str(record.get("selectability", "")).strip().lower()
        profiles = tuple(str(item).strip() for item in record.get("eligible_profiles", ()))
        relevance_tags = tuple(
            str(item).strip() for item in record.get("relevance_tags", ()) if str(item).strip()
        )
        try:
            line_cost = int(record.get("line_cost", 0) or 0)
        except (TypeError, ValueError):
            line_cost = 0
        if (
            not candidate_id
            or row_label not in {"Independent Product", "Interests"}
            or not text
            or not use_case
            or not profiles
            or not relevance_tags
            or line_cost not in {1, 2, 3}
        ):
            errors.append(f"{candidate_id or '<support-row>'}: incomplete support-row candidate")
            continue
        if candidate_id in support_ids:
            errors.append(f"{candidate_id}: duplicate support-row candidate ID")
        support_ids.add(candidate_id)
        if selectability not in KNOWN_SUMMARY_SELECTABILITY:
            errors.append(
                f"{candidate_id}: support-row selectability must be one of "
                f"{sorted(KNOWN_SUMMARY_SELECTABILITY)}, got {selectability!r}"
            )
        for profile_id in profiles:
            try:
                get_profile(profile_id)
            except ValueError as exc:
                errors.append(f"{candidate_id}: {exc}")
        if selectability in SHIPPING_SUMMARY_SELECTABILITY:
            support_rows.append(
                ReviewedSupportRow(
                    candidate_id=candidate_id,
                    row_label=row_label,
                    text=text,
                    use_case=use_case,
                    status=status,
                    selectability=selectability,
                    eligible_profiles=profiles,
                    relevance_tags=relevance_tags,
                    line_cost=line_cost,
                )
            )

    professional_profiles = tuple(
        profile_id
        for profile_id in (
            "product-general",
            "product-ai-zero-to-one",
            "product-data-platform",
            "business-enterprise-leadership",
            "business-operations-leadership",
            "business-commercial-gtm",
            "customer-technical-client-value",
            "customer-technical-deployed-systems",
        )
    )
    for profile_id in professional_profiles:
        if not any(profile_id in summary.eligible_profiles for summary in summaries):
            errors.append(f"{profile_id}: no reviewed summary candidate is funded")

    if errors:
        raise ValueError("invalid reviewed prompt bank: " + "; ".join(errors))

    ordered_family_rows = tuple(
        (family, family_rows[family]) for family in REQUIRED_REVIEW_FAMILIES
    )
    variants = tuple(
        variant for _, family_variants in ordered_family_rows for variant in family_variants
    )
    suppressed = (incumbent_ids - {variant.variant_id for variant in variants}) | held_recommendation_ids
    return ReviewedPromptBank(
        covered_families=REQUIRED_REVIEW_FAMILIES,
        variants=variants,
        variants_by_family=ordered_family_rows,
        suppressed_variant_ids=frozenset(suppressed),
        summaries=tuple(summaries),
        communities=tuple(communities),
        support_rows=tuple(support_rows),
    )


def default_allocation_plan(profile_id: str) -> ExperienceAllocationPlan:
    profile = get_profile(profile_id)
    if not profile.is_professional:
        raise ValueError(f"{profile_id}: Pass-1 professional prompt adapter does not serve campus profiles")
    return ExperienceAllocationPlan(
        profile_id=profile_id,
        company_counts=tuple((slot.company, slot.target) for slot in profile.experience_slots),
    )


def _resolve_professional_profile(
    *,
    strategy: Mapping[str, object],
    context_tags: Iterable[str],
    explicit_profile: str | None,
) -> tuple[ProfileResolution, ResumeProfile]:
    resolution = resolve_profile(
        strategy=strategy,
        context_tags=context_tags,
        explicit_profile=explicit_profile,
    )
    if resolution.needs_review or resolution.profile is None:
        raise ValueError(f"Step 0 did not resolve a shippable profile: {resolution.reason}")
    if not resolution.profile.is_professional:
        raise ValueError(
            f"{resolution.profile_id}: Pass-1 professional prompt adapter does not serve campus profiles"
        )
    return resolution, resolution.profile


_OFFICIAL_HEADERS = {
    "FLAIRX AI": "FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA",
    "GOJEK": "GOJEK | Senior Software Engineer | Jan 2025 – Jul 2025 | Gurgaon, India",
    "HEVO DATA": "HEVO DATA | Software Engineer 2 | Nov 2023 – Jan 2025 | Bengaluru, India",
    "INTUIT": "INTUIT | Software Engineer 2 | Aug 2022 – Oct 2023 | Bengaluru, India",
    "OPTUM": "OPTUM | Software Engineer | Jul 2020 – Aug 2022 | Gurgaon, India",
}
_PRODUCT_OWNER_HEADERS = {
    **_OFFICIAL_HEADERS,
    "GOJEK": "GOJEK | Product Owner, Marketplace | Jan 2025 – Jul 2025 | Gurgaon, India",
    "HEVO DATA": "HEVO DATA | Product Owner, Data Platform | Nov 2023 – Jan 2025 | Bengaluru, India",
}


def _headers_for_title_mode(title_mode: TitleMode) -> Mapping[str, str]:
    if title_mode is TitleMode.FUNCTIONAL_PRODUCT_OWNER:
        return _PRODUCT_OWNER_HEADERS
    # The separately approved title-qualifier ledger is not part of A-D.  In
    # qualifier mode the safe base is therefore the official header; callers
    # may apply a separately approved qualifier, but the model may not invent one.
    return _OFFICIAL_HEADERS


def company_headers_for_profile(profile: ResumeProfile) -> Mapping[str, str]:
    """Return the exact, renderer-facing headers owned by an assembly profile."""

    return dict(_headers_for_title_mode(profile.title_mode))


def _title_mode_rule(title_mode: TitleMode) -> str:
    if title_mode is TitleMode.FUNCTIONAL_PRODUCT_OWNER:
        return (
            "Use the exact Product Owner headers below for Gojek and Hevo; keep the "
            "other approved titles unchanged."
        )
    if title_mode is TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER:
        return (
            "Preserve the official title shown below. Append a functional qualifier only "
            "when a separately approved title mapping supplies it; never infer or invent one."
        )
    return "Use every official title exactly as shown below."


def _fluo_rule(profile: ResumeProfile) -> tuple[str, str]:
    policy = profile.fluo
    allowed = ", ".join(policy.allowed_story_families) or "none"
    metadata = (
        f"{policy.placement.value}; label={policy.label or 'none'}; "
        f"allowed_story_families={allowed}; max_lines={policy.max_lines}; "
        "counts_toward_experience=false; allow_experience=false"
    )
    if policy.placement is FluoPlacement.INLINE_REQUIRED:
        rule = (
            f"Select exactly one FLUO variant verbatim and render it as a compact "
            f"{profile.fluo.label}: Fluo row in Section 4. Use only a colon and comma "
            "as glue; do not add an em dash or paraphrase the selected variant. Select "
            f"only a FLUO entry whose assembly_modes includes inline and whose line_cost "
            f"is at most {profile.fluo.max_lines}."
        )
    elif policy.placement is FluoPlacement.INLINE_RELEVANCE_GATED:
        rule = (
            f"Record an explicit include/omit decision. Include at most one FLUO variant "
            f"verbatim as {profile.fluo.label}: Fluo only when it materially fits the JD. "
            "If that label is not one of the base skill rows, replace Additional rather "
            "than adding a sixth row. Use only a colon and comma as glue. Select only an "
            f"entry whose assembly_modes includes inline and whose line_cost is at most "
            f"{profile.fluo.max_lines}."
        )
    elif policy.placement is FluoPlacement.PROJECT_OPTIONAL:
        rule = (
            "Record an explicit include/omit decision. If included, use one reviewed FLUO "
            "variant verbatim in Section 3B; never put Fluo in Experience."
        )
    else:
        rule = "Omit Fluo completely, even if an earlier prompt recommends it."
    return metadata, rule


def _format_reviewed_bank(bank: ReviewedPromptBank) -> list[str]:
    lines = [
        "REVIEWED BULLET BANK — THE ONLY SELECTABLE EXPERIENCE/PROJECT WORDING",
        "Every bullet is immutable. Copy one complete quoted string exactly; do not rewrite,",
        "merge, shorten, expand, paraphrase, or combine facts across variants.",
        "",
    ]
    for family, variants in bank.variants_by_family:
        lines.append(f"STORY FAMILY {family}")
        if not variants:
            lines.append("NO SELECTABLE REVIEWED VARIANT. Do not use this family.")
            lines.append("")
            continue
        for variant in variants:
            lines.append(
                f"[reviewed-variant:{variant.variant_id}] status={variant.status}; "
                f"archetype={variant.archetype or 'n/a'}; "
                f"fluo_story_family={variant.fluo_story_family or 'n/a'}; "
                f"line_cost={variant.line_cost or 'n/a'}; "
                f"assembly_modes={','.join(variant.assembly_modes) or 'n/a'}; "
                f"use_case={variant.use_case}"
            )
            lines.append(json.dumps(variant.text, ensure_ascii=False))
        lines.append("")
    return lines


def _format_summary_bank(summaries: Sequence[ReviewedSummary]) -> list[str]:
    lines = [
        "PROFILE-FUNDED SUMMARY BANK — SELECT EXACTLY ONE VERBATIM",
        "A summary is selectable only when every required_page_evidence family appears in",
        "the final page. Never merge two summaries or inject a JD qualifier.",
    ]
    for summary in summaries:
        evidence = ", ".join(summary.required_page_evidence) or "none"
        lines.append(
            f"[reviewed-summary:{summary.candidate_id}] "
            f"required_page_evidence={evidence}; use_case={summary.use_case}"
        )
        lines.append(json.dumps(summary.text, ensure_ascii=False))
    lines.append("")
    return lines


def _format_community_bank(communities: Sequence[ReviewedCommunity]) -> list[str]:
    if not communities:
        return []
    lines = ["REVIEWED COMMUNITY ROWS — OPTIONAL, VERBATIM"]
    for community in communities:
        lines.append(
            f"[reviewed-community:{community.candidate_id}] "
            f"use_case={community.use_case}"
        )
        lines.append(json.dumps(community.text, ensure_ascii=False))
    lines.append("")
    return lines


def _default_profile_bank(
    full_bank: ReviewedPromptBank,
    profile: ResumeProfile,
    *,
    skill_labels: Sequence[str] | None = None,
    include_all_skill_options: bool = False,
) -> ReviewedPromptBank:
    """Return only candidates the default no-Projects profile can release."""

    filtered_rows: list[tuple[str, tuple[ReviewedBullet, ...]]] = []
    removed_ids: set[str] = set()
    for family, variants in full_bank.variants_by_family:
        if family in EXPERIENCE_FAMILIES:
            eligible = variants
        elif family == "FLUO" and profile.fluo.placement is not FluoPlacement.OMIT:
            eligible = tuple(
                variant
                for variant in variants
                if "inline" in variant.assembly_modes
                and variant.line_cost <= profile.fluo.max_lines
                and variant.fluo_story_family in profile.fluo.allowed_story_families
            )
        else:
            eligible = ()
        eligible_ids = {variant.variant_id for variant in eligible}
        if eligible:
            filtered_rows.append((family, eligible))
        removed_ids.update(
            variant.variant_id for variant in variants if variant.variant_id not in eligible_ids
        )

    if (
        profile.fluo.placement is FluoPlacement.INLINE_REQUIRED
        and not any(family == "FLUO" for family, _ in filtered_rows)
    ):
        raise ValueError(f"{profile.profile_id}: no releasable inline Fluo variant")

    possible_skill_labels = set(skill_labels or profile.skill_rows)
    if include_all_skill_options and profile.skill_policy is not None:
        possible_skill_labels.update(profile.skill_policy.flexible_labels)
    communities = (
        full_bank.communities
        if possible_skill_labels.intersection({"Additional", "Community"})
        else ()
    )
    support_rows = tuple(
        row
        for row in full_bank.support_rows
        if row.row_label in possible_skill_labels
        and profile.profile_id in row.eligible_profiles
    )
    variants = tuple(
        variant for _, family_variants in filtered_rows for variant in family_variants
    )
    return ReviewedPromptBank(
        covered_families=tuple(family for family, _ in filtered_rows),
        variants=variants,
        variants_by_family=tuple(filtered_rows),
        suppressed_variant_ids=full_bank.suppressed_variant_ids | frozenset(removed_ids),
        summaries=full_bank.summaries,
        communities=communities,
        support_rows=support_rows,
    )


def _format_skill_value_bank(
    profile: ResumeProfile,
    bank: ReviewedPromptBank,
    row_labels: Sequence[str] | None = None,
) -> list[str]:
    lines = [
        "PROFILE-FUNDED SKILLS VALUE BANK — SELECT EXACTLY ONE VALUE PER ROW",
        "Copy one complete value for each funded label. Do not rewrite, splice,",
        "reorder within a value, or inject JD keywords.",
    ]
    for label, candidates in skill_value_candidates_for_profile(
        profile, bank, row_labels
    ).items():
        lines.append(f"SKILLS LABEL {label}")
        for index, value in enumerate(candidates, start=1):
            lines.append(f"[approved-skill-value:{label}:{index}]")
            lines.append(json.dumps(value, ensure_ascii=False))
        lines.append("")
    return lines


def _summary_is_default_assembly_feasible(
    summary: ReviewedSummary,
    allocation_plan: ExperienceAllocationPlan,
    bank: ReviewedPromptBank,
) -> bool:
    """Return whether default professional v2 can fund a summary from Experience.

    Project replacement is intentionally not wired into the default professional
    path yet.  A summary that requires project-only or unknown evidence must not
    be exposed as selectable, because the release validator would necessarily
    reject it after the model chose it.
    """

    family_map = bank.family_map()
    required_by_company: dict[str, int] = {}
    for story_family in summary.required_page_evidence:
        company = next(
            (
                owner
                for prefix, owner in {
                    "F-": "FLAIRX AI",
                    "G-": "GOJEK",
                    "H-": "HEVO DATA",
                    "I-": "INTUIT",
                    "O-": "OPTUM",
                }.items()
                if story_family.startswith(prefix)
            ),
            None,
        )
        if (
            story_family not in EXPERIENCE_FAMILIES
            or not family_map.get(story_family)
            or company is None
        ):
            return False
        required_by_company[company] = required_by_company.get(company, 0) + 1

    counts = allocation_plan.counts_dict()
    return all(count <= counts.get(company, 0) for company, count in required_by_company.items())


def _build_tail_text(
    *,
    profile: ResumeProfile,
    allocation_plan: ExperienceAllocationPlan,
    bank: ReviewedPromptBank,
    eligible_summaries: Sequence[ReviewedSummary],
    skills_plan: SkillsAssemblyPlan,
) -> str:
    headers = _headers_for_title_mode(profile.title_mode)
    fluo_metadata, fluo_instruction = _fluo_rule(profile)
    skills_heading = skills_section_heading(skills_plan.row_labels)
    counts = allocation_plan.counts_dict()
    allocation_text = " | ".join(
        f"{company}={counts[company]}" for company in PROFESSIONAL_COMPANY_ORDER
    )

    lines = [
        OVERRIDE_START,
        f"adapter_version={ADAPTER_VERSION}",
        "",
        "PRECEDENCE — CRITICAL",
        "This final block supersedes every conflicting instruction earlier in the legacy",
        "PM or NONPM prompt, including fixed company counts, fixed bullet totals, summary",
        "omission, title relabeling, Fluo placement, old story pools, and output shape.",
        "Earlier bullet variants are context only and are NOT selectable unless their exact",
        "ID and exact text are repeated in the reviewed bank below.",
        "",
        "RESOLVED PROFILE CONTRACT",
        f"profile_id={profile.profile_id}",
        f"family={profile.family.value}",
        f"identity_heading={profile.identity_heading}",
        f"summary_mode={profile.summary_mode.value}",
        f"title_mode={profile.title_mode.value}",
        f"title_rule={_title_mode_rule(profile.title_mode)}",
        f"skills_heading={skills_heading}",
        f"skills_rows={' | '.join(skills_plan.row_labels)}",
        f"skills_row_decision={skills_plan.decision.value}",
        f"selection_priorities={' | '.join(profile.selection_priorities)}",
        f"fluo_policy={fluo_metadata}",
        f"fluo_instruction={fluo_instruction}",
        "",
        "EXACT EXPERIENCE ALLOCATION",
        f"bullet_budget_decision={allocation_plan.budget_decision.value}",
        f"exact_experience_bullet_total={allocation_plan.total}",
        f"exact_company_allocation={allocation_text}",
        "All five companies must appear exactly once, in the order below, even when a",
        "company receives only one bullet. Never erase Optum or another career block.",
        "The Intuit allocation must include exactly one I-INCIDENT variant; this is the",
        "protected cross-functional leadership story. Do not substitute an adjacent",
        "Intuit story merely because its surface keywords resemble the JD.",
        "Select at most one variant from each STORY FAMILY across the entire page.",
        "Two differently worded variants from the same family are duplicate evidence,",
        "not two bullets, and will fail release validation.",
        "",
    ]
    if allocation_plan.budget_decision is BulletBudgetDecision.ADD_DISTINCT_SIGNAL:
        added_company = next(
            company
            for company, count in allocation_plan.company_counts
            if count > profile.slots_dict()[company]
        )
        lines.extend(
            [
                "ELEVENTH-PROOF MARGINAL VALUE GATE — CRITICAL",
                f"The additional {added_company} bullet is not page filler. It must add a",
                "JD-relevant proof dimension absent from the other ten bullets: a new",
                "mechanism, decision type, stakeholder, or outcome. Repeating keywords,",
                "scale, discovery, or execution already established elsewhere does not qualify.",
                "If no admitted variant in that company clears this marginal-value test, do",
                "not fabricate, paraphrase, or duplicate evidence; fail the requested allocation.",
                "",
            ]
        )
    lines.extend(_format_reviewed_bank(bank))
    lines.extend(_format_summary_bank(eligible_summaries))
    lines.extend(_format_community_bank(bank.communities))
    lines.extend(_format_skill_value_bank(profile, bank, skills_plan.row_labels))

    lines.extend(
        [
            "EXACT OUTPUT FORMAT — PRODUCE EACH SECTION ONCE, IN THIS ORDER",
            "Do all comparison and correction silently. Output no preamble, drafts,",
            "re-tallies, or reasoning outside the five sections below.",
            "",
            "SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)",
            "[exactly one eligible reviewed summary string; summary body only]",
            "",
            "SECTION 1 — TOP 3 JD SIGNALS",
            "[exactly three concise JD signals]",
            "",
            "SECTION 2 — SELECTION NOTES",
            f"Profile: {profile.profile_id}",
            f"Identity heading: {profile.identity_heading}",
            f"Exact bullet total: {allocation_plan.total}",
            f"Allocation: {allocation_text}",
            f"Skills rows: {' | '.join(skills_plan.row_labels)}",
            "Selected variants: [one reviewed-variant ID per output bullet, in output order]",
            "Summary: [one reviewed-summary ID]",
            "Fluo decision: [include with reviewed-variant ID, or omit when policy permits]",
            "",
            "SECTION 3 — FULL EXPERIENCE SECTION (paste-ready, no markdown bold)",
        ]
    )
    for company in PROFESSIONAL_COMPANY_ORDER:
        lines.append(headers[company])
        lines.extend(
            f"• [verbatim reviewed variant {index + 1} of {counts[company]}]"
            for index in range(counts[company])
        )
        lines.append("")
    lines.extend(
        [
            "DEFAULT PROFESSIONAL PROJECT POLICY",
            "Do not output SECTION 3B or any Projects content. Supporting-proof project",
            "replacement remains unavailable until a separate PageProofPlan is wired.",
            "",
            f"SECTION 4 — {skills_heading} (paste-ready)",
            skills_heading,
            f"● [render exactly {skills_plan.row_count} profile-funded rows in the listed order, selecting one",
            "  exact approved-skill-value for each label; when a relevance-gated Fluo row",
            "  replaces Additional, preserve the resolved row count; apply the Fluo policy exactly]",
            "",
            "FINAL IMMUTABILITY CHECK",
            f"The {allocation_plan.total} Experience bullet strings must each be exact string",
            "matches to reviewed-variant entries above. Creating a new bullet is a structural",
            "failure, even when its facts are true or its wording seems stronger.",
            OVERRIDE_END,
        ]
    )
    return "\n".join(lines).strip()


def validate_prompt_override(override: Pass1PromptOverride) -> list[str]:
    """Validate the rendered tail itself, including stale-ID exclusion."""

    tail = override.tail
    errors: list[str] = []
    if tail.count(OVERRIDE_START) != 1 or tail.count(OVERRIDE_END) != 1:
        errors.append("authoritative override sentinels must each appear exactly once")
    if "supersedes every conflicting instruction" not in tail:
        errors.append("override does not declare precedence over the legacy prompt")
    if "Every bullet is immutable" not in tail or "exact string" not in tail:
        errors.append("override does not enforce verbatim bullet immutability")

    for family in override.bank.covered_families:
        if tail.count(f"STORY FAMILY {family}\n") != 1:
            errors.append(f"{family}: story family is missing or duplicated in override")
    for variant in override.bank.variants:
        marker = f"[reviewed-variant:{variant.variant_id}]"
        if tail.count(marker) != 1:
            errors.append(f"{variant.variant_id}: reviewed marker must appear exactly once")
        quoted = json.dumps(variant.text, ensure_ascii=False)
        if tail.count(quoted) != 1:
            errors.append(f"{variant.variant_id}: immutable text must appear exactly once")
    for suppressed_id in override.bank.suppressed_variant_ids:
        if f"[reviewed-variant:{suppressed_id}]" in tail:
            errors.append(f"{suppressed_id}: stale, retired, or held variant leaked into override")

    expected_summaries = {summary.candidate_id for summary in override.eligible_summaries}
    actual_summary_markers = {
        line.split("]", 1)[0].split(":", 1)[1]
        for line in tail.splitlines()
        if line.startswith("[reviewed-summary:")
    }
    if actual_summary_markers != expected_summaries:
        errors.append(
            "summary markers do not match the profile-funded reviewed candidates: "
            f"expected {sorted(expected_summaries)}, got {sorted(actual_summary_markers)}"
        )

    counts = override.allocation_plan.counts_dict()
    allocation_text = " | ".join(
        f"{company}={counts[company]}" for company in PROFESSIONAL_COMPANY_ORDER
    )
    if f"exact_experience_bullet_total={override.bullet_total}" not in tail:
        errors.append("dynamic exact bullet total is missing from override")
    if f"exact_company_allocation={allocation_text}" not in tail:
        errors.append("exact company allocation is missing from override")
    if f"identity_heading={override.profile.identity_heading}" not in tail:
        errors.append("identity heading is missing from override")
    if f"summary_mode={SummaryMode.REQUIRED.value}" not in tail:
        errors.append("required summary contract is missing from override")
    if f"title_mode={override.profile.title_mode.value}" not in tail:
        errors.append("title mode is missing from override")
    if f"fluo_policy={override.profile.fluo.placement.value};" not in tail:
        errors.append("Fluo policy is missing from override")
    if f"skills_rows={' | '.join(override.skills_plan.row_labels)}" not in tail:
        errors.append("resolved Skills row plan is missing from override")

    for label, candidates in skill_value_candidates_for_profile(
        override.profile,
        override.bank,
        override.skills_plan.row_labels,
    ).items():
        for index, value in enumerate(candidates, start=1):
            exact_entry = (
                f"[approved-skill-value:{label}:{index}]\n"
                f"{json.dumps(value, ensure_ascii=False)}"
            )
            if tail.count(exact_entry) != 1:
                errors.append(
                    f"{label} skill value {index}: approved marker and exact text "
                    "must appear together exactly once"
                )

    if "SECTION 3B — PROJECTS & CONSULTING" in tail:
        errors.append("default professional v2 must not expose a Section 3B output block")
    if "Do not output SECTION 3B or any Projects content" not in tail:
        errors.append("default professional v2 must explicitly forbid Projects output")

    headers = _headers_for_title_mode(override.profile.title_mode)
    for company in PROFESSIONAL_COMPANY_ORDER:
        if tail.count(headers[company]) != 1:
            errors.append(f"{company}: exact header must appear once in output contract")
    return errors


def build_pass1_prompt_override(
    strategy: Mapping[str, object],
    *,
    context_tags: Iterable[str] = (),
    explicit_profile: str | None = None,
    allocation_plan: ExperienceAllocationPlan | None = None,
    causal_batch_paths: Sequence[Path] = DEFAULT_CAUSAL_BATCH_PATHS,
    summary_batch_path: Path = DEFAULT_SUMMARY_BATCH_PATH,
    summary_candidate_id: str | None = None,
    skills_selector_mode: str | V2FeatureMode | None = None,
    requested_skill_rows: int | None = None,
    environment: Mapping[str, str] | None = None,
) -> Pass1PromptOverride:
    """Resolve Step 0 and build one validated, authoritative Pass-1 tail."""

    resolution, profile = _resolve_professional_profile(
        strategy=strategy,
        context_tags=context_tags,
        explicit_profile=explicit_profile,
    )
    plan = allocation_plan or default_allocation_plan(profile.profile_id)
    if plan.profile_id != profile.profile_id:
        raise ValueError(
            f"allocation profile {plan.profile_id!r} does not match resolved profile "
            f"{profile.profile_id!r}"
        )
    allocation_errors = validate_experience_allocation(plan)
    if allocation_errors:
        raise ValueError("invalid Experience allocation: " + "; ".join(allocation_errors))

    full_bank = load_reviewed_prompt_bank(
        causal_batch_paths=causal_batch_paths,
        summary_batch_path=summary_batch_path,
    )
    candidate_bank = _default_profile_bank(
        full_bank,
        profile,
        include_all_skill_options=True,
    )
    default_skills_plan = SkillsAssemblyPlan(
        profile_id=profile.profile_id,
        row_labels=profile.skill_rows,
        decision=SkillRowDecision.DEFAULT_FIVE,
    )
    selector_mode = resolve_v2_feature_mode(
        V2_SKILLS_SELECTOR_ENV,
        skills_selector_mode,
        environment=environment,
    )
    row_request = (
        requested_skill_rows
        if requested_skill_rows is not None
        else requested_v2_skill_rows(environment=environment)
    )
    # Skills never outrank substantive page proof. The optional sixth is only
    # considered after this profile's Experience allocation has already reached
    # its admitted proof ceiling; otherwise the 10 -> 11 distinct-story path
    # gets first claim on genuine page headroom.
    if row_request == 6 and plan.total < profile.bullet_budget.maximum:
        row_request = 5
    adaptive_skills_plan = resolve_skills_assembly_plan(
        profile,
        strategy,
        available_labels=available_skill_labels_for_profile(profile, candidate_bank),
        requested_rows=row_request,
    )
    skills_plan = (
        adaptive_skills_plan
        if selector_mode is V2FeatureMode.APPLY
        else default_skills_plan
    )
    shadow_skills_plan = (
        adaptive_skills_plan if selector_mode is V2FeatureMode.SHADOW else None
    )
    bank = _default_profile_bank(
        full_bank,
        profile,
        skill_labels=skills_plan.row_labels,
    )
    eligible_summaries = tuple(
        summary
        for summary in bank.summaries
        if profile.profile_id in summary.eligible_profiles
        and _summary_is_default_assembly_feasible(summary, plan, bank)
    )
    if summary_candidate_id is not None:
        eligible_summaries = tuple(
            summary
            for summary in eligible_summaries
            if summary.candidate_id == summary_candidate_id
        )
        if not eligible_summaries:
            raise ValueError(
                f"{profile.profile_id}: requested summary {summary_candidate_id!r} "
                "is not shipping-selectable and funded by the assembled page"
            )
    if profile.summary_mode is SummaryMode.REQUIRED and not eligible_summaries:
        raise ValueError(f"{profile.profile_id}: no reviewed summary is eligible")

    tail = _build_tail_text(
        profile=profile,
        allocation_plan=plan,
        bank=bank,
        eligible_summaries=eligible_summaries,
        skills_plan=skills_plan,
    )
    override = Pass1PromptOverride(
        version=ADAPTER_VERSION,
        resolution=resolution,
        profile=profile,
        allocation_plan=plan,
        bank=bank,
        eligible_summaries=eligible_summaries,
        skills_plan=skills_plan,
        shadow_skills_plan=shadow_skills_plan,
        tail=tail,
    )
    errors = validate_prompt_override(override)
    if errors:
        raise ValueError("invalid Pass-1 override: " + "; ".join(errors))
    return override


def adapt_legacy_pass1_prompt(
    legacy_prompt: str,
    strategy: Mapping[str, object],
    **override_kwargs: object,
) -> AdaptedPass1Prompt:
    """Append one v2 tail without mutating a legacy prompt file.

    Passing an already-adapted prompt is rejected rather than stacking two
    authoritative blocks whose precedence would be ambiguous.
    """

    if OVERRIDE_START in legacy_prompt or OVERRIDE_END in legacy_prompt:
        raise ValueError("legacy prompt already contains a v2 authoritative override")
    override = build_pass1_prompt_override(strategy, **override_kwargs)
    prompt = f"{legacy_prompt.rstrip()}\n\n{override.tail}\n"
    return AdaptedPass1Prompt(prompt=prompt, override=override)
