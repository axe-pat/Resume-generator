import pytest

from shared.resume_profiles import (
    PROFILE_REGISTRY,
    PROFESSIONAL_COMPANY_ORDER,
    BulletBudgetDecision,
    ExperienceAllocationPlan,
    FluoPlacement,
    ProfileFamily,
    SummaryMode,
    TitleMode,
    get_profile,
    resolve_profile,
    skills_section_heading,
    validate_experience_allocation,
    validate_profile_registry,
)
from shared.variant_admission import (
    FactStatus,
    VariantRulebookStatus,
    ResumeVariant,
    admitted_variants,
    check_variant_admission,
    check_variant_for_profile,
)


def _strong_variant(**overrides):
    fields = {
        "variant_id": "G-PRICING-product-judgment",
        "story_id": "G-PRICING",
        "text": "Converted willingness-to-pay research into a tiered offer with measurable adoption.",
        "value_signals": ("customer-insight", "pricing-monetization"),
        "role_tags": ("product", "commercial"),
        "fact_status": FactStatus.APPROVED,
        "variant_rulebook_status": VariantRulebookStatus.APPROVED,
        "variant_rulebook_version": "docs/variants/VARIANT_FINALS_v4.md",
        "stakes": 4,
        "difficulty": 3,
        "defensibility": 4,
        "distinctiveness": 3,
        "line_cost": 2,
        "decision_quality": 3,
        "human_presence": 3,
        "metric_salience": 3,
        "eligible_profiles": ("product-general", "business-commercial-gtm"),
        "fact_atoms": ("willingness-to-pay research", "tiered offer", "adoption"),
        "source_refs": ("story://gojek/pricing",),
    }
    fields.update(overrides)
    return ResumeVariant(**fields)


def test_profile_registry_is_valid_and_queue_independent():
    assert validate_profile_registry() == []
    assert all("amazon" not in profile_id for profile_id in PROFILE_REGISTRY)
    assert all("lane-a" not in profile_id for profile_id in PROFILE_REGISTRY)
    assert all("lane-b" not in profile_id for profile_id in PROFILE_REGISTRY)


def test_professional_profiles_use_a_bounded_9_to_11_budget_with_a_ten_bullet_center():
    allocations = set()
    for profile in PROFILE_REGISTRY.values():
        if profile.family is ProfileFamily.CAMPUS:
            continue
        assert profile.bullet_budget.minimum == 9
        assert profile.bullet_budget.target == 10
        assert profile.bullet_budget.maximum == 11
        assert profile.experience_bullet_total == 10
        assert tuple(slot.company for slot in profile.experience_slots) == PROFESSIONAL_COMPANY_ORDER
        assert profile.slots_dict()["OPTUM"] >= 1
        assert profile.slot_bounds()["OPTUM"][0] >= 1
        allocations.add(tuple(slot.target for slot in profile.experience_slots))

    assert len(allocations) >= 3


def test_fluo_never_counts_as_experience_and_varies_by_profile_policy():
    for profile in PROFILE_REGISTRY.values():
        assert not profile.fluo.allow_experience
        assert not profile.fluo.counts_toward_experience

    assert get_profile("product-general").fluo.placement is FluoPlacement.INLINE_REQUIRED
    assert (
        get_profile("business-commercial-gtm").fluo.placement
        is FluoPlacement.INLINE_RELEVANCE_GATED
    )
    assert get_profile("business-operations-leadership").fluo.placement is FluoPlacement.OMIT


def test_summary_and_title_policy_are_profile_contracts():
    product = get_profile("product-general")
    business = get_profile("business-enterprise-leadership")
    operations = get_profile("business-operations-leadership")
    commercial = get_profile("business-commercial-gtm")
    technical = get_profile("customer-technical-client-value")
    campus = get_profile("campus-student-service")

    assert product.summary_mode is SummaryMode.REQUIRED
    assert product.identity_heading == "PRODUCT MANAGEMENT"
    assert product.summary_heading == product.identity_heading
    assert product.title_mode is TitleMode.FUNCTIONAL_PRODUCT_OWNER
    assert business.summary_mode is SummaryMode.REQUIRED
    assert business.identity_heading == "STRATEGY & OPERATIONS"
    assert operations.identity_heading == "OPERATIONS & PROGRAM MANAGEMENT"
    assert commercial.identity_heading == "COMMERCIAL STRATEGY"
    assert technical.summary_mode is SummaryMode.REQUIRED
    assert technical.identity_heading == "TECHNICAL SOLUTIONS"
    assert technical.title_mode is TitleMode.OFFICIAL_WITH_FUNCTIONAL_QUALIFIER
    assert campus.identity_heading == "PROFILE"
    assert campus.title_mode is TitleMode.OFFICIAL


def test_skills_heading_depends_only_on_an_explicit_interests_row():
    assert skills_section_heading(("Product Leadership", "Technical", "Community")) == "SKILLS"
    assert skills_section_heading(("Technical", "Interests:")) == "SKILLS & INTERESTS"


def test_professional_allocation_is_exact_after_a_bounded_budget_decision():
    default = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 3),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
    )
    assert validate_experience_allocation(default) == []

    add_distinct = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 3),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.ADD_DISTINCT_SIGNAL,
    )
    assert validate_experience_allocation(add_distinct) == []

    compact = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.COMPACT_FOR_PAGE_FIT,
    )
    assert validate_experience_allocation(compact) == []


def test_professional_allocation_rejects_free_form_count_changes():
    plan = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 3),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.DEFAULT,
    )
    errors = validate_experience_allocation(plan)
    assert any("must total 10" in error for error in errors)


@pytest.mark.parametrize(
    ("strategy", "context_tags", "expected"),
    [
        (
            {
                "role_family": "pm",
                "archetype": "platform_pm",
                "primary_framing_axis": "data platform infrastructure",
            },
            (),
            "product-data-platform",
        ),
        ({"role_family": "pm", "archetype": "ai_pm"}, (), "product-ai-zero-to-one"),
        ({"role_family": "pm", "archetype": "consumer_pm"}, (), "product-general"),
        (
            {"role_family": "ops-execution", "nonpm_subtype": "ops-pgm"},
            (),
            "business-operations-leadership",
        ),
        (
            {"role_family": "strategy-consulting", "nonpm_subtype": "commercial-gtm"},
            (),
            "business-commercial-gtm",
        ),
        (
            {"role_family": "ops-execution", "nonpm_subtype": "client-implementation"},
            (),
            "customer-technical-client-value",
        ),
        (
            {
                "role_family": "ops-execution",
                "nonpm_subtype": "client-implementation",
                "primary_framing_axis": "production deployment and technical delivery",
            },
            (),
            "customer-technical-deployed-systems",
        ),
        ({}, ("campus-analytics",), "campus-analytics"),
        ({}, ("campus-communications",), "campus-communications"),
    ],
)
def test_assembly_resolver_consumes_existing_strategy_or_reviewed_campus_tag(
    strategy, context_tags, expected
):
    result = resolve_profile(strategy=strategy, context_tags=context_tags)
    assert result.profile_id == expected
    assert not result.needs_review


def test_profile_resolver_accepts_validated_override_and_fails_closed_when_ambiguous():
    explicit = resolve_profile(
        explicit_profile="business-enterprise-leadership",
    )
    assert explicit.profile_id == "business-enterprise-leadership"
    assert explicit.confidence == 1.0

    ambiguous = resolve_profile()
    assert ambiguous.profile_id is None
    assert ambiguous.needs_review

    with pytest.raises(ValueError):
        resolve_profile(explicit_profile="queue-role-47")


def test_existing_step_zero_fields_map_to_an_assembly_profile_without_a_new_taxonomy():
    strategy = {
        "role_family": "ops-execution",
        "nonpm_subtype": "client-implementation",
        "bullet_balance": "balanced",
        "primary_framing_axis": "client-implementation",
    }
    resolved = resolve_profile(strategy=strategy)
    assert resolved.profile_id == "customer-technical-client-value"
    assert resolved.reason == "mapped Step 0 client-implementation subtype"


def test_assembly_resolver_does_not_reclassify_incomplete_step_zero_output():
    incomplete = resolve_profile(strategy={"role_family": "ops-execution"})
    assert incomplete.profile_id is None
    assert incomplete.needs_review
    assert "missing" in incomplete.reason

    incomplete_pm = resolve_profile(strategy={"role_family": "pm"})
    assert incomplete_pm.profile_id is None
    assert incomplete_pm.needs_review
    assert "archetype" in incomplete_pm.reason

    conflicting = resolve_profile(
        strategy={
            "role_family": "pm",
            "archetype": "generalist",
            "nonpm_subtype": "commercial-gtm",
        }
    )
    assert conflicting.profile_id is None
    assert conflicting.needs_review
    assert "conflicting" in conflicting.reason


def test_variant_admission_accepts_strong_approved_evidence():
    result = check_variant_admission(_strong_variant())
    assert result.admitted
    assert result.errors == ()


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"stakes": 1}, "stakes"),
        ({"difficulty": 1}, "difficulty"),
        ({"defensibility": 2}, "defensibility"),
        ({"distinctiveness": 1}, "distinctiveness"),
        ({"fact_status": FactStatus.PENDING}, "fact_status"),
        (
            {"variant_rulebook_status": VariantRulebookStatus.PENDING},
            "variant_rulebook_status",
        ),
        (
            {"variant_rulebook_version": "docs/variants/VARIANT_FINALS_v3.md"},
            "variant_rulebook_version",
        ),
        ({"line_cost": 5}, "line_cost"),
    ],
)
def test_variant_admission_rejects_weak_or_uncleared_evidence(overrides, expected_fragment):
    result = check_variant_admission(_strong_variant(**overrides))
    assert not result.admitted
    assert any(expected_fragment in error for error in result.errors)


def test_variant_admission_warns_but_does_not_block_lightweight_lineage_gaps():
    result = check_variant_admission(_strong_variant(fact_atoms=(), source_refs=()))
    assert result.admitted
    assert len(result.warnings) == 2


def test_profile_eligibility_is_checked_after_global_variant_admission():
    variant = _strong_variant()
    product = check_variant_for_profile(variant, "product-general")
    operations = check_variant_for_profile(variant, "business-operations-leadership")

    assert product.admitted
    assert not operations.admitted
    assert "not eligible" in operations.errors[-1]
    assert admitted_variants([variant], profile_id="product-general") == [variant]
    assert admitted_variants([variant], profile_id="business-operations-leadership") == []
