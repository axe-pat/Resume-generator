"""Contracts for the inert reviewed-bank Pass-1 prompt adapter."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from shared.resume_profiles import (
    PROFILE_REGISTRY,
    BulletBudgetDecision,
    ExperienceAllocationPlan,
)
from shared.resume_v2_prompt import (
    DEFAULT_CAUSAL_BATCH_PATHS,
    DEFAULT_SUMMARY_BATCH_PATH,
    OVERRIDE_END,
    OVERRIDE_START,
    REQUIRED_REVIEW_FAMILIES,
    SHIPPING_SUMMARY_SELECTABILITY,
    adapt_legacy_pass1_prompt,
    build_pass1_prompt_override,
    load_reviewed_prompt_bank,
    validate_prompt_override,
)


PM_STRATEGY = {
    "role_family": "pm",
    "archetype": "ai_pm",
    "top_signals": ["AI workflow design", "customer discovery"],
    "gaps": [],
}

NONPM_STRATEGY = {
    "role_family": "ops-execution",
    "nonpm_subtype": "commercial-gtm",
    "bullet_balance": "balanced",
    "top_signals": ["commercial strategy", "customer segmentation"],
    "gaps": [],
}


def test_adapter_uses_existing_step0_resolver_for_product_and_nonpm_profiles():
    product = build_pass1_prompt_override(PM_STRATEGY)
    nonpm = build_pass1_prompt_override(NONPM_STRATEGY)

    assert product.profile_id == "product-ai-zero-to-one"
    assert product.resolution.reason == "mapped existing Step 0 PM fields"
    assert nonpm.profile_id == "business-commercial-gtm"
    assert nonpm.resolution.reason == "mapped Step 0 commercial-GTM subtype"


def test_override_supersedes_legacy_shape_and_encodes_profile_contract_exactly():
    override = build_pass1_prompt_override(PM_STRATEGY)
    tail = override.tail

    assert tail.count(OVERRIDE_START) == tail.count(OVERRIDE_END) == 1
    assert "supersedes every conflicting instruction earlier" in tail
    assert "profile_id=product-ai-zero-to-one" in tail
    assert "identity_heading=PRODUCT MANAGEMENT" in tail
    assert "summary_mode=required" in tail
    assert "title_mode=functional-product-owner" in tail
    assert "fluo_policy=inline-required;" in tail
    assert "exact_experience_bullet_total=10" in tail
    assert (
        "exact_company_allocation=FLAIRX AI=2 | GOJEK=3 | HEVO DATA=2 | "
        "INTUIT=2 | OPTUM=1"
    ) in tail
    assert "All five companies must appear exactly once" in tail
    assert validate_prompt_override(override) == []


def test_reviewed_bank_has_complete_family_coverage_and_excludes_suppressed_variants():
    bank = load_reviewed_prompt_bank()
    assert bank.covered_families == REQUIRED_REVIEW_FAMILIES
    assert set(bank.family_map()) == set(REQUIRED_REVIEW_FAMILIES)
    assert all(variant.text.strip() for variant in bank.variants)

    tail = build_pass1_prompt_override(PM_STRATEGY).tail
    selectable_ids = {variant.variant_id for variant in bank.variants}
    assert selectable_ids
    assert selectable_ids.isdisjoint(bank.suppressed_variant_ids)
    assert all(f"[reviewed-variant:{variant_id}]" not in tail for variant_id in bank.suppressed_variant_ids)


def test_every_exposed_bullet_is_a_verbatim_review_recommendation():
    override = build_pass1_prompt_override(PM_STRATEGY)
    for variant in override.bank.variants:
        assert override.tail.count(f"[reviewed-variant:{variant.variant_id}]") == 1
        assert override.tail.count(json.dumps(variant.text, ensure_ascii=False)) == 1
    assert "Every bullet is immutable" in override.tail
    assert "Creating a new bullet is a structural" in override.tail


def test_prompt_exposes_only_controlled_complete_skills_values():
    override = build_pass1_prompt_override(PM_STRATEGY)
    assert "PROFILE-FUNDED SKILLS VALUE BANK" in override.tail
    assert "Do not rewrite, splice" in override.tail
    for label in override.profile.skill_rows:
        assert f"SKILLS LABEL {label}" in override.tail
    assert "selecting one" in override.tail
    assert "exact approved-skill-value for each label" in override.tail


def test_every_professional_profile_has_a_complete_controlled_skills_bank():
    for profile_id, profile in PROFILE_REGISTRY.items():
        if not profile.is_professional:
            continue
        override = build_pass1_prompt_override({}, explicit_profile=profile_id)
        for label in profile.skill_rows:
            assert f"SKILLS LABEL {label}" in override.tail


def test_sixth_skills_row_waits_until_experience_proof_ceiling_is_exhausted():
    strategy = {
        "role_family": "pm",
        "archetype": "generalist",
        "top_signals": ["AI product", "education mission", "student customers"],
        "gaps": [],
    }
    ten = build_pass1_prompt_override(
        strategy,
        explicit_profile="product-general",
        skills_selector_mode="shadow",
        requested_skill_rows=6,
    )
    eleven_plan = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 3),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.ADD_DISTINCT_SIGNAL,
    )
    eleven = build_pass1_prompt_override(
        strategy,
        explicit_profile="product-general",
        allocation_plan=eleven_plan,
        skills_selector_mode="shadow",
        requested_skill_rows=6,
    )

    assert ten.shadow_skills_plan is not None
    assert ten.shadow_skills_plan.row_count == 5
    assert eleven.shadow_skills_plan is not None
    assert eleven.shadow_skills_plan.row_count == 6
    assert eleven.shadow_skills_plan.has_optional_sixth


def test_only_profile_eligible_summaries_are_exposed():
    product = build_pass1_prompt_override(PM_STRATEGY)
    eligible = {summary.candidate_id for summary in product.eligible_summaries}
    assert eligible
    assert all(product.profile_id in summary.eligible_profiles for summary in product.eligible_summaries)
    assert "summary/nonpm/commercial-growth-decisions" not in product.tail

    nonpm = build_pass1_prompt_override(NONPM_STRATEGY)
    assert "summary/nonpm/commercial-growth-decisions" in nonpm.tail
    assert "summary/product/general-scaled-evidence" not in nonpm.tail


def test_summary_shipping_allowlist_preserves_status_but_hides_ranking_cues(
    tmp_path,
):
    """Review state remains auditable without becoming a selector hint."""

    data = json.loads(DEFAULT_SUMMARY_BATCH_PATH.read_text(encoding="utf-8"))
    product_ids = (
        "summary/product/general-scaled-evidence",
        "summary/product/marketplace-growth",
        "summary/product/fintech-billing-trust",
        "summary/product/customer-usage-to-shipped",
        "summary/product/research-to-decision",
    )
    product_by_id = {
        record["candidate_id"]: record for record in data["summary_candidates"]
    }
    product_records = [product_by_id[candidate_id] for candidate_id in product_ids]
    status_and_selectability = (
        ("approved_gold", "shipping"),
        ("shipping_incumbent", "shipping"),
        ("reviewed_selectable", "shipping"),
        ("review_pending", "review"),
        ("challenger_review", "review"),
    )
    for record, (status, selectability) in zip(
        product_records,
        status_and_selectability,
    ):
        # Make each fixture feasible for the same profile so this test isolates
        # release selectability rather than page-evidence routing.
        record["eligible_profiles"] = ["product-general"]
        record["required_page_evidence"] = []
        record["status"] = status
        record["selectability"] = selectability

    summary_path = tmp_path / "summary-bank.json"
    summary_path.write_text(json.dumps(data), encoding="utf-8")

    override = build_pass1_prompt_override(
        PM_STRATEGY,
        explicit_profile="product-general",
        summary_batch_path=summary_path,
    )
    exposed = {summary.candidate_id: summary for summary in override.eligible_summaries}
    shipping_records = product_records[:3]
    review_records = product_records[3:]

    assert SHIPPING_SUMMARY_SELECTABILITY == {"shipping"}
    assert set(exposed) == {record["candidate_id"] for record in shipping_records}
    assert {summary.status for summary in exposed.values()} == {
        "approved_gold",
        "shipping_incumbent",
        "reviewed_selectable",
    }
    assert {summary.selectability for summary in exposed.values()} == {"shipping"}
    assert {
        record["candidate_id"] for record in review_records
    }.isdisjoint(exposed)

    summary_prompt = override.tail.split(
        "PROFILE-FUNDED SUMMARY BANK", 1
    )[1].split("PROFILE-FUNDED SKILLS VALUE BANK", 1)[0]
    for ranking_cue in (
        "status=",
        "selectability=",
        "approved_gold",
        "shipping_incumbent",
        "reviewed_selectable",
        "review_pending",
        "challenger_review",
    ):
        assert ranking_cue not in summary_prompt


def test_real_review_bank_declares_release_permission_for_every_summary_and_support_row():
    data = json.loads(DEFAULT_SUMMARY_BATCH_PATH.read_text(encoding="utf-8"))
    for collection in (
        "summary_candidates",
        "community_candidates",
        "support_row_candidates",
    ):
        assert data[collection]
        assert all(
            record.get("selectability") in {"shipping", "review"}
            for record in data[collection]
        )


def test_missing_summary_selectability_fails_closed(tmp_path):
    data = json.loads(DEFAULT_SUMMARY_BATCH_PATH.read_text(encoding="utf-8"))
    data["summary_candidates"][0].pop("selectability")
    summary_path = tmp_path / "summary-bank.json"
    summary_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="summary selectability"):
        load_reviewed_prompt_bank(summary_batch_path=summary_path)


def test_community_review_permission_is_fail_closed_and_not_a_prompt_ranking_cue():
    bank = load_reviewed_prompt_bank()
    assert {row.candidate_id for row in bank.communities} == {
        "community/niveda-mobile-school-full"
    }

    override = build_pass1_prompt_override(
        {}, explicit_profile="business-enterprise-leadership"
    )
    community_prompt = override.tail.split(
        "REVIEWED COMMUNITY ROWS", 1
    )[1].split("PROFILE-FUNDED SKILLS VALUE BANK", 1)[0]
    assert "status=" not in community_prompt
    assert "challenger_review" not in community_prompt
    assert "community/niveda-mobile-school-compact" not in community_prompt
    assert "community/fundraising-leadership" not in community_prompt


def test_default_professional_prompt_excludes_project_dependent_summaries_and_section():
    product = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    product_summary_ids = {summary.candidate_id for summary in product.eligible_summaries}
    assert "summary/product/independent-builder" not in product_summary_ids
    assert "summary/product/independent-builder" not in product.tail

    enterprise = build_pass1_prompt_override(
        {}, explicit_profile="business-enterprise-leadership"
    )
    enterprise_summary_ids = {
        summary.candidate_id for summary in enterprise.eligible_summaries
    }
    assert "summary/nonpm/ai-human-control" not in enterprise_summary_ids
    assert "summary/nonpm/ai-human-control" not in enterprise.tail

    assert "Do not output SECTION 3B or any Projects content" in product.tail
    assert "SECTION 3B — PROJECTS & CONSULTING" not in product.tail


def test_prompt_bank_is_filtered_to_default_route_feasible_candidates():
    product = build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")
    product_families = product.bank.family_map()
    assert not any(family.startswith("P-") for family in product_families)
    assert product.bank.communities == ()
    assert "FL-FIELD-VALIDATION-studyfetch-closed-loop" not in {
        variant.variant_id for variant in product.bank.variants
    }
    assert all(
        "inline" in variant.assembly_modes
        and variant.line_cost <= product.profile.fluo.max_lines
        and variant.fluo_story_family in product.profile.fluo.allowed_story_families
        for variant in product_families["FLUO"]
    )

    operations = build_pass1_prompt_override(
        {}, explicit_profile="business-operations-leadership"
    )
    assert "FLUO" not in operations.bank.family_map()
    assert not any(family.startswith("P-") for family in operations.bank.family_map())
    assert operations.bank.communities == ()

    enterprise = build_pass1_prompt_override(
        {}, explicit_profile="business-enterprise-leadership"
    )
    assert enterprise.bank.communities


def test_explicit_nine_and_eleven_bullet_plans_change_the_exact_output_contract():
    nine = ExperienceAllocationPlan(
        profile_id="product-ai-zero-to-one",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.COMPACT_FOR_QUALITY,
    )
    nine_override = build_pass1_prompt_override(PM_STRATEGY, allocation_plan=nine)
    assert nine_override.bullet_total == 9
    assert "Exact bullet total: 9" in nine_override.tail
    assert nine_override.tail.count("• [verbatim reviewed variant") == 9

    eleven = ExperienceAllocationPlan(
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
    eleven_override = build_pass1_prompt_override(PM_STRATEGY, allocation_plan=eleven)
    assert eleven_override.bullet_total == 11
    assert "Exact bullet total: 11" in eleven_override.tail
    assert eleven_override.tail.count("• [verbatim reviewed variant") == 11
    assert "ELEVENTH-PROOF MARGINAL VALUE GATE" in eleven_override.tail
    assert "The additional FLAIRX AI bullet is not page filler" in eleven_override.tail
    assert "a new\nmechanism, decision type, stakeholder, or outcome" in eleven_override.tail
    assert "do\nnot fabricate, paraphrase, or duplicate evidence" in eleven_override.tail


def test_adapter_appends_exactly_one_tail_without_mutating_legacy_text():
    legacy = "LEGACY PM MASTER\nold fixed shape"
    adapted = adapt_legacy_pass1_prompt(legacy, PM_STRATEGY)
    assert adapted.prompt.startswith(legacy)
    assert adapted.prompt.count(OVERRIDE_START) == 1
    assert adapted.prompt.count(OVERRIDE_END) == 1
    assert adapted.prompt.endswith("\n")

    with pytest.raises(ValueError, match="already contains"):
        adapt_legacy_pass1_prompt(adapted.prompt, PM_STRATEGY)


def test_incomplete_review_family_fails_closed(tmp_path):
    copied_paths = []
    for source in DEFAULT_CAUSAL_BATCH_PATHS:
        data = json.loads(source.read_text(encoding="utf-8"))
        if source.name.startswith("BATCH_A"):
            data["families"].pop("F-CEIPAL")
        destination = tmp_path / source.name
        destination.write_text(json.dumps(data), encoding="utf-8")
        copied_paths.append(destination)

    with pytest.raises(ValueError, match="missing story families.*F-CEIPAL"):
        load_reviewed_prompt_bank(
            causal_batch_paths=tuple(copied_paths),
            summary_batch_path=DEFAULT_SUMMARY_BATCH_PATH,
        )


def test_retired_variant_cannot_reenter_recommended_slate(tmp_path):
    copied_paths = []
    retired_id = None
    for source in DEFAULT_CAUSAL_BATCH_PATHS:
        data = json.loads(source.read_text(encoding="utf-8"))
        if source.name.startswith("BATCH_A"):
            family = data["families"]["F-AVATAR"]
            retired = next(
                row for row in family["incumbents"] if str(row["verdict"]).startswith("retire")
            )
            retired_id = retired["stable_id"]
            family["recommended_variants"].append(
                {
                    "variant_id": retired_id,
                    "status": "incumbent",
                    "use_case": "invalid regression fixture",
                    "text": "This retired wording must never re-enter the selectable prompt bank.",
                }
            )
        destination = tmp_path / source.name
        destination.write_text(json.dumps(data), encoding="utf-8")
        copied_paths.append(destination)

    assert retired_id
    with pytest.raises(ValueError, match="retired variants returned"):
        load_reviewed_prompt_bank(
            causal_batch_paths=tuple(copied_paths),
            summary_batch_path=DEFAULT_SUMMARY_BATCH_PATH,
        )


def test_unresolved_or_campus_profile_is_not_silently_guessed():
    with pytest.raises(ValueError, match="did not resolve"):
        build_pass1_prompt_override({})
    with pytest.raises(ValueError, match="does not serve campus"):
        build_pass1_prompt_override({}, explicit_profile="campus-analytics")


def test_validation_detects_a_suppressed_marker_if_tail_is_tampered():
    override = build_pass1_prompt_override(PM_STRATEGY)
    suppressed_id = next(iter(override.bank.suppressed_variant_ids))
    tampered = replace(
        override,
        tail=override.tail + f"\n[reviewed-variant:{suppressed_id}]",
    )
    errors = validate_prompt_override(tampered)
    assert any("leaked into override" in error for error in errors)


def test_validation_detects_tampered_controlled_skill_value():
    override = build_pass1_prompt_override(PM_STRATEGY)
    tampered = replace(
        override,
        tail=override.tail.replace(
            "Product Strategy, Roadmap Ownership, Customer Discovery",
            "Product Strategy, Blockchain, Customer Discovery",
            1,
        ),
    )

    errors = validate_prompt_override(tampered)

    assert any("approved marker and exact text" in error for error in errors)
