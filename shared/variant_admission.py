"""One-time admission gate for resume story variants.

Per-run generation may only select variants that have passed this gate.  The
gate judges the underlying evidence and the *per-variant* portions of the
canonical playbook, not JD fit or resume-level composition.  In particular,
Section 9 of ``VARIANT_FINALS_v4.md`` is assembly-owned and is not certified by
the status recorded here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from shared.resume_profiles import PROFILE_REGISTRY
from shared.variant_text_lint import lint_candidate_variant_text


VARIANT_ADMISSION_VERSION = "2026-09-02.1"
CANONICAL_VARIANT_RULEBOOK = "docs/variants/VARIANT_FINALS_v4.md"


class FactStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class VariantRulebookStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class OutcomeTier(str, Enum):
    """Strongest attributable outcome carried by the variant, best to weakest."""

    USER_OR_BUSINESS = "user-or-business"
    OBSERVED_BEHAVIOR = "observed-behavior"
    DECISION_OR_ORGANIZATION = "decision-or-organization"
    QUALITY_OR_EFFICIENCY = "quality-or-efficiency"
    THROUGHPUT_OR_INPUT = "throughput-or-input"
    ARCHITECTURE_OR_BUILD_COUNT = "architecture-or-build-count"


@dataclass(frozen=True)
class VariantAdmissionPolicy:
    min_stakes: int = 3
    min_difficulty: int = 2
    min_defensibility: int = 3
    min_distinctiveness: int = 2
    min_line_cost: int = 1
    max_line_cost: int = 4
    required_rulebook: str = CANONICAL_VARIANT_RULEBOOK


DEFAULT_ADMISSION_POLICY = VariantAdmissionPolicy()


@dataclass(frozen=True)
class ResumeVariant:
    variant_id: str
    story_id: str
    text: str
    value_signals: tuple[str, ...]
    role_tags: tuple[str, ...]
    fact_status: FactStatus
    variant_rulebook_status: VariantRulebookStatus
    variant_rulebook_version: str
    stakes: int
    difficulty: int
    defensibility: int
    distinctiveness: int
    line_cost: int
    outcome_tier: OutcomeTier
    one_argument: bool
    mechanism_supports_claim: bool
    outcome_closes_claim: bool
    outsider_legible: bool
    best_available_outcome: bool
    decision_quality: int | None = None
    human_presence: int | None = None
    metric_salience: int | None = None
    eligible_profiles: tuple[str, ...] = ()
    fact_atoms: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmissionResult:
    variant_id: str
    admitted: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    policy_version: str = VARIANT_ADMISSION_VERSION


def _score_errors(name: str, score: int | None) -> list[str]:
    if score is None:
        return []
    if not 0 <= score <= 4:
        return [f"{name} must be between 0 and 4"]
    return []


def check_variant_admission(
    variant: ResumeVariant,
    policy: VariantAdmissionPolicy = DEFAULT_ADMISSION_POLICY,
) -> AdmissionResult:
    """Check whether a variant may enter the selectable shipping pool."""
    errors: list[str] = []
    warnings: list[str] = []

    if not variant.variant_id.strip():
        errors.append("variant_id is required")
    if not variant.story_id.strip():
        errors.append("story_id is required")
    if not variant.text.strip():
        errors.append("text is required")
    if not variant.value_signals:
        errors.append("at least one value_signal is required")
    if not variant.role_tags:
        errors.append("at least one role_tag is required")
    if not isinstance(variant.outcome_tier, OutcomeTier):
        errors.append("outcome_tier must use the controlled OutcomeTier vocabulary")

    required_quality_gates = {
        "one_argument": variant.one_argument,
        "mechanism_supports_claim": variant.mechanism_supports_claim,
        "outcome_closes_claim": variant.outcome_closes_claim,
        "outsider_legible": variant.outsider_legible,
        "best_available_outcome": variant.best_available_outcome,
    }
    for gate_name, passed in required_quality_gates.items():
        if passed is not True:
            errors.append(f"{gate_name} must be explicitly approved")

    for field_name in (
        "stakes",
        "difficulty",
        "defensibility",
        "distinctiveness",
        "decision_quality",
        "human_presence",
        "metric_salience",
    ):
        errors.extend(_score_errors(field_name, getattr(variant, field_name)))

    if variant.fact_status is not FactStatus.APPROVED:
        errors.append(f"fact_status must be approved, got {variant.fact_status.value}")
    if variant.variant_rulebook_status is not VariantRulebookStatus.APPROVED:
        errors.append(
            "variant_rulebook_status must be approved, got "
            f"{variant.variant_rulebook_status.value}"
        )
    if variant.variant_rulebook_version != policy.required_rulebook:
        errors.append(
            f"variant_rulebook_version must be {policy.required_rulebook}, "
            f"got {variant.variant_rulebook_version or '<missing>'}"
        )
    if variant.stakes < policy.min_stakes:
        errors.append(
            f"stakes {variant.stakes} is below admission floor {policy.min_stakes}"
        )
    if variant.difficulty < policy.min_difficulty:
        errors.append(
            f"difficulty {variant.difficulty} is below admission floor {policy.min_difficulty}"
        )
    if variant.defensibility < policy.min_defensibility:
        errors.append(
            "defensibility "
            f"{variant.defensibility} is below admission floor {policy.min_defensibility}"
        )
    if variant.distinctiveness < policy.min_distinctiveness:
        errors.append(
            "distinctiveness "
            f"{variant.distinctiveness} is below admission floor {policy.min_distinctiveness}"
        )
    if not policy.min_line_cost <= variant.line_cost <= policy.max_line_cost:
        errors.append(
            f"line_cost must be {policy.min_line_cost}-{policy.max_line_cost}, "
            f"got {variant.line_cost}"
        )

    unknown_profiles = sorted(set(variant.eligible_profiles) - set(PROFILE_REGISTRY))
    if unknown_profiles:
        errors.append(f"unknown eligible_profiles: {unknown_profiles}")

    if variant.decision_quality is not None and variant.decision_quality < 2:
        warnings.append("decision quality is weak; prefer only when another value signal dominates")
    if variant.human_presence is not None and variant.human_presence < 1:
        warnings.append("no meaningful human/customer/leader presence")
    if variant.metric_salience is not None and variant.metric_salience < 2:
        warnings.append("metrics may make the work look smaller rather than stronger")
    if not variant.fact_atoms:
        warnings.append("fact_atoms are not yet recorded for rewrite containment")
    if not variant.source_refs:
        warnings.append("approved variant has no source reference recorded")

    return AdmissionResult(
        variant_id=variant.variant_id,
        admitted=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def check_variant_for_profile(
    variant: ResumeVariant,
    profile_id: str,
    policy: VariantAdmissionPolicy = DEFAULT_ADMISSION_POLICY,
) -> AdmissionResult:
    """Apply pool admission plus an optional profile allow-list."""
    if profile_id not in PROFILE_REGISTRY:
        raise ValueError(f"Unknown resume profile {profile_id!r}")
    base = check_variant_admission(variant, policy)
    errors = list(base.errors)
    if variant.eligible_profiles and profile_id not in variant.eligible_profiles:
        errors.append(f"variant is not eligible for profile {profile_id}")
    return AdmissionResult(
        variant_id=variant.variant_id,
        admitted=not errors,
        errors=tuple(errors),
        warnings=base.warnings,
    )


def check_new_candidate_admission(
    variant: ResumeVariant,
    policy: VariantAdmissionPolicy = DEFAULT_ADMISSION_POLICY,
) -> AdmissionResult:
    """Apply metadata admission plus deterministic text rules to new candidates.

    This is intentionally a separate, shadow-only path.  Existing incumbents
    predate several stricter operational rules and remain protected by pairwise
    non-regression review; new challengers do not get to repeat known defects.
    """

    base = check_variant_admission(variant, policy)
    errors = list(base.errors)
    warnings = list(base.warnings)
    text_report = lint_candidate_variant_text(variant.text)
    errors.extend(
        f"text rule {issue.code}: {issue.message}" for issue in text_report.blockers
    )
    warnings.extend(
        f"text review {issue.code}: {issue.message}"
        for issue in text_report.review_items
    )
    return AdmissionResult(
        variant_id=variant.variant_id,
        admitted=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def admitted_variants(
    variants: Iterable[ResumeVariant],
    *,
    profile_id: str | None = None,
    policy: VariantAdmissionPolicy = DEFAULT_ADMISSION_POLICY,
) -> list[ResumeVariant]:
    """Return only variants safe to expose to the per-JD selector."""
    selected: list[ResumeVariant] = []
    for variant in variants:
        result = (
            check_variant_for_profile(variant, profile_id, policy)
            if profile_id
            else check_variant_admission(variant, policy)
        )
        if result.admitted:
            selected.append(variant)
    return selected
