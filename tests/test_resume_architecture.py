import pytest

from shared.resume_profiles import (
    PROFILE_REGISTRY,
    PROFESSIONAL_COMPANY_ORDER,
    BulletBudgetDecision,
    ExperienceAllocationPlan,
    FluoPlacement,
    PageProofPlan,
    ProfileFamily,
    SkillRowDecision,
    SupportingProofMode,
    SupportingProofReason,
    SummaryMode,
    TitleMode,
    get_profile,
    resolve_profile,
    resolve_skills_assembly_plan,
    skills_section_heading,
    validate_experience_allocation,
    validate_page_proof_plan,
    validate_profile_registry,
    validate_summary_identity,
)
from shared.variant_admission import (
    FactStatus,
    OutcomeTier,
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
        "outcome_tier": OutcomeTier.USER_OR_BUSINESS,
        "one_argument": True,
        "mechanism_supports_claim": True,
        "outcome_closes_claim": True,
        "outsider_legible": True,
        "best_available_outcome": True,
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


def test_product_profiles_start_flairx_at_two_and_gate_the_third_slot():
    for profile in PROFILE_REGISTRY.values():
        if profile.family is not ProfileFamily.PRODUCT:
            continue
        flairx = next(slot for slot in profile.experience_slots if slot.company == "FLAIRX AI")
        assert (flairx.minimum, flairx.target, flairx.maximum) == (2, 2, 3)


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


@pytest.mark.parametrize(
    ("profile_id", "summary"),
    [
        ("product-general", "Product manager and engineer with five years owning technical products."),
        ("business-enterprise-leadership", "Technical operator with five years scaling enterprise systems."),
        ("business-operations-leadership", "Engineer-turned-operator with cross-team delivery experience."),
        ("business-commercial-gtm", "Commercial strategist with pricing and market-entry experience."),
        ("customer-technical-client-value", "Technical solutions professional translating client needs into deployments."),
        ("campus-analytics", "USC Marshall MBA candidate with analytics and campus leadership experience."),
    ],
)
def test_required_summary_opens_with_a_pool_funded_identity(profile_id, summary):
    assert validate_summary_identity(profile_id, summary) == []


def test_required_summary_rejects_generic_unfunded_filler():
    errors = validate_summary_identity(
        "business-operations-leadership",
        "Results-driven professional with a proven track record of excellence.",
    )
    assert any("funded identity" in error for error in errors)


def test_embedded_product_strategy_role_does_not_fall_into_generic_research_route():
    result = resolve_profile(
        strategy={
            "role_title": "Intern - Product Strategy",
            "role_family": "strategy-consulting",
            "nonpm_subtype": "research-intelligence",
            "archetype": "consumer_pm",
            "top_signals": [
                "user research inside the product team",
                "usability testing that informs product decisions",
                "competitive analysis",
            ],
        }
    )
    assert result.profile_id == "product-general"
    assert result.needs_review is False


def test_standalone_product_strategy_research_does_not_get_pm_identity_from_title_alone():
    result = resolve_profile(
        strategy={
            "role_title": "Product Strategy Analyst",
            "role_family": "strategy-consulting",
            "nonpm_subtype": "research-intelligence",
            "archetype": "strategy_pm",
            "top_signals": ["market sizing", "competitive intelligence", "executive synthesis"],
        }
    )
    assert result.profile_id == "business-enterprise-leadership"


def test_skills_heading_depends_only_on_an_explicit_interests_row():
    assert skills_section_heading(("Product Leadership", "Technical", "Community")) == "SKILLS"
    assert skills_section_heading(("Technical", "Interests:")) == "SKILLS & INTERESTS"


def test_skills_plan_defaults_to_five_and_does_not_add_an_unfunded_sixth():
    profile = get_profile("product-general")
    available = profile.skill_rows + ("Interests",)
    generic_strategy = {
        "role_title": "Associate Product Manager",
        "role_family": "pm",
        "archetype": "generalist",
        "top_signals": ["roadmap prioritization", "analytics", "technical delivery"],
    }

    default = resolve_skills_assembly_plan(
        profile,
        generic_strategy,
        available_labels=available,
    )
    requested_six = resolve_skills_assembly_plan(
        profile,
        generic_strategy,
        available_labels=available,
        requested_rows=6,
    )

    assert default.row_count == 5
    assert default.decision is SkillRowDecision.DEFAULT_FIVE
    assert requested_six.row_count == 5
    assert requested_six.decision is SkillRowDecision.DEFAULT_FIVE
    assert not requested_six.has_optional_sixth


def test_harman_music_signal_can_win_the_adaptive_fifth_row():
    profile = get_profile("product-general")
    strategy = {
        "role_title": "User Research Intern, Software Experiences Business Unit",
        "role_family": "strategy-consulting",
        "nonpm_subtype": "research-intelligence",
        "bullet_balance": "diagnostic-heavy",
        "top_signals": [
            "user research into Gen Z music discovery and listening habits",
            "a personal stake in music as a musician, DJ, or playlist curator",
            "competitive analysis across streaming and short-form content",
        ],
        "primary_framing_axis": "workflow-discovery",
        "positioning_narrative": (
            "Translate how people find, share, and talk about music into product "
            "recommendations for HARMAN's software experiences team."
        ),
    }

    plan = resolve_skills_assembly_plan(
        profile,
        strategy,
        available_labels=profile.skill_rows + ("Interests",),
        requested_rows=5,
    )

    assert plan.row_count == 5
    assert plan.decision is SkillRowDecision.DEFAULT_FIVE
    assert "Interests" in plan.row_labels
    assert skills_section_heading(plan.row_labels) == "SKILLS & INTERESTS"


def test_product_user_community_language_does_not_misroute_to_volunteer_community():
    profile = get_profile("product-general")
    strategy = {
        "role_title": "Associate Product Manager",
        "role_family": "pm",
        "top_signals": [
            "creator and player community behavior analysis",
            "cross-functional experimentation and go-to-market",
        ],
        "positioning_narrative": "Understand a platform's creator community and ship features.",
    }

    plan = resolve_skills_assembly_plan(
        profile,
        strategy,
        available_labels=profile.skill_rows + ("Community",),
    )

    assert "Community" not in plan.row_labels
    assert plan.row_labels == profile.skill_rows


def test_sixth_skill_row_requires_a_distinct_relevant_signal():
    profile = get_profile("product-general")
    strategy = {
        "role_title": "Product Strategy Intern, Music AI",
        "role_family": "pm",
        "archetype": "ai_pm",
        "top_signals": [
            "AI workflow prototyping and model evaluation",
            "student customer discovery and fintech product launches",
            "a personal stake in music as a DJ or playlist curator",
        ],
        "primary_framing_axis": "ai-workflow",
        "secondary_framing_axis": "consumer-music-discovery",
    }

    plan = resolve_skills_assembly_plan(
        profile,
        strategy,
        available_labels=profile.skill_rows + ("Interests",),
        requested_rows=6,
    )

    assert plan.row_count == 6
    assert plan.decision is SkillRowDecision.ADD_DISTINCT_SIXTH
    assert plan.has_optional_sixth
    assert plan.optional_sixth_label in plan.row_labels
    assert "Interests" in plan.row_labels

    with pytest.raises(ValueError, match="5 or 6"):
        resolve_skills_assembly_plan(
            profile,
            strategy,
            available_labels=profile.skill_rows + ("Interests",),
            requested_rows=7,
        )


def test_professional_allocation_is_exact_after_a_bounded_budget_decision():
    default = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
    )
    assert validate_experience_allocation(default) == []

    rebalance_to_third_flairx = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 3),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.REBALANCE_DISTINCT_SIGNAL,
    )
    assert validate_experience_allocation(rebalance_to_third_flairx) == []

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

    quality_compact = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=compact.company_counts,
        budget_decision=BulletBudgetDecision.COMPACT_FOR_QUALITY,
    )
    assert validate_experience_allocation(quality_compact) == []


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
    assert any("must change the profile target" in error for error in errors)


def test_default_page_proof_plan_preserves_the_existing_experience_contract():
    experience = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
    )
    assert validate_page_proof_plan(
        PageProofPlan(profile_id="product-general", experience_plan=experience)
    ) == []


def test_project_replacement_can_promote_top_criterion_proof_without_erasing_career_continuity():
    experience = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 1),
            ("OPTUM", 1),
        ),
    )
    plan = PageProofPlan(
        profile_id="product-general",
        experience_plan=experience,
        mode=SupportingProofMode.PROJECT_REPLACEMENT,
        reason=SupportingProofReason.TOP_CRITERION_EVIDENCE,
        project_bullet_count=3,
        replaced_experience_count=2,
    )
    assert plan.experience_bullet_count == 8
    assert plan.total_proof_units == 11
    assert validate_page_proof_plan(plan) == []


def test_project_replacement_requires_a_bounded_reviewed_exception():
    experience = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 1),
            ("OPTUM", 1),
        ),
    )
    unreviewed = PageProofPlan(
        profile_id="product-general",
        experience_plan=experience,
        mode=SupportingProofMode.PROJECT_REPLACEMENT,
        project_bullet_count=3,
        replaced_experience_count=2,
    )
    assert any(
        "top-criterion-evidence" in error
        for error in validate_page_proof_plan(unreviewed)
    )

    overstuffed = PageProofPlan(
        profile_id="product-general",
        experience_plan=experience,
        mode=SupportingProofMode.PROJECT_REPLACEMENT,
        reason=SupportingProofReason.TOP_CRITERION_EVIDENCE,
        project_bullet_count=4,
        replaced_experience_count=2,
    )
    errors = validate_page_proof_plan(overstuffed)
    assert any("exactly 2 or 3" in error for error in errors)
    assert any("10-11" in error for error in errors)


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
        ({"outcome_tier": "business"}, "outcome_tier"),
        ({"one_argument": False}, "one_argument"),
        ({"mechanism_supports_claim": False}, "mechanism_supports_claim"),
        ({"outcome_closes_claim": False}, "outcome_closes_claim"),
        ({"outsider_legible": False}, "outsider_legible"),
        ({"best_available_outcome": False}, "best_available_outcome"),
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
