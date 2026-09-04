"""Release-gate tests for an assembled v2 Pass-1 response.

These tests deliberately build one valid page from the real reviewed A-D bank,
then mutate a single contract surface at a time.  That keeps the assertions tied
to shipping assets while making each failure attributable to one v2 invariant.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from shared.resume_lint import ASSEMBLY_POLICY, LintSeverity, lint_assembled_resume
from shared.resume_profiles import PROFESSIONAL_COMPANY_ORDER, skills_section_heading
from shared.resume_v2_prompt import (
    Pass1PromptOverride,
    build_pass1_prompt_override,
    company_headers_for_profile,
    load_reviewed_prompt_bank,
    skill_value_candidates_for_profile,
)
from shared.resume_v2_validation import validate_v2_sections
from resume.freeform.freeform_runner import canonicalize_v2_selection_notes


PM_STRATEGY = {
    "role_family": "pm",
    "archetype": "general_pm",
    "top_signals": ["product judgment", "customer evidence"],
    "gaps": [],
}

DEFAULT_SELECTION = {
    "FLAIRX AI": (
        "F-ENTERPRISE-amazon-deal-impact",
        "f-avatar-low-spec-antifraud-tradeoff",
    ),
    "GOJEK": (
        "G-PRICING-canonical-closed-loop",
        "G-LATENCY-studyfetch-readable-tradeoff",
        "G-SUPPLY-canonical-operating-model",
    ),
    "HEVO DATA": (
        "H-BATCHSHIFT-canonical-trial-trigger",
        "H-MONITORING-canonical-ai-boundary",
    ),
    "INTUIT": (
        "I-BILLING-canonical-renewal-integrity",
        "I-INCIDENT-canonical-parallel-recovery",
    ),
    "OPTUM": ("O-SAFE-ACTION-flag-suggest-stop",),
}

DEFAULT_SUMMARY_ID = "summary/product/general-scaled-evidence"
DEFAULT_FLUO_ID = "FL-INSTITUTIONAL-amazon-inline-prearrival"


def _variant_map(override: Pass1PromptOverride):
    return {variant.variant_id: variant for variant in override.bank.variants}


def _summary_map(override: Pass1PromptOverride):
    return {summary.candidate_id: summary for summary in override.eligible_summaries}


def _sections(
    override: Pass1PromptOverride,
    *,
    selection: dict[str, tuple[str, ...]] | None = None,
    company_order: tuple[str, ...] = PROFESSIONAL_COMPANY_ORDER,
    summary_id: str = DEFAULT_SUMMARY_ID,
    fluo_id: str = DEFAULT_FLUO_ID,
    skill_labels: tuple[str, ...] | None = None,
    fluo_row_prefix: str = "Fluo, ",
) -> dict[str, str]:
    selected = selection or DEFAULT_SELECTION
    variants = _variant_map(override)
    summary = _summary_map(override)[summary_id]
    headers = company_headers_for_profile(override.profile)

    experience_lines: list[str] = []
    selected_ids: list[str] = []
    for company in company_order:
        experience_lines.append(headers[company])
        for variant_id in selected[company]:
            selected_ids.append(variant_id)
            experience_lines.append(f"• {variants[variant_id].text}")

    fluo = variants[fluo_id]
    labels = skill_labels or override.profile.skill_rows
    allowed_skill_values = skill_value_candidates_for_profile(
        override.profile,
        override.bank,
    )
    skill_lines = [skills_section_heading(labels)]
    for label in labels:
        if label == override.profile.fluo.label:
            text = f"{fluo_row_prefix}{fluo.text}"
        else:
            text = allowed_skill_values[label][0]
        skill_lines.append(f"● {label}: {text}")

    notes = "\n".join(
        (
            f"Profile: {override.profile_id}",
            f"Selected variants: {', '.join(selected_ids)}",
            f"Summary: {summary.candidate_id}",
            f"Fluo decision: include with {fluo.variant_id}",
        )
    )
    experience = "\n".join(experience_lines)
    skills = "\n".join(skill_lines)
    raw = "\n\n".join(
        (
            f"SECTION 0 — PROFESSIONAL SUMMARY\n{summary.text}",
            "SECTION 1 — TOP 3 JD SIGNALS\nProduct judgment\nCustomer evidence\nExecution",
            f"SECTION 2 — SELECTION NOTES\n{notes}",
            f"SECTION 3 — FULL EXPERIENCE SECTION\n{experience}",
            f"SECTION 4 — SKILLS\n{skills}",
        )
    )
    return {
        "summary_section": summary.text,
        "selection_notes": notes,
        "experience_section": experience,
        "projects_section": "",
        "skills_section": skills,
        "raw": raw,
    }


@pytest.fixture(scope="module")
def product_override() -> Pass1PromptOverride:
    return build_pass1_prompt_override(PM_STRATEGY, explicit_profile="product-general")


def _messages(result) -> str:
    return "\n".join(result.errors)


def _blocker_codes(document) -> set[str]:
    report = lint_assembled_resume(document, ASSEMBLY_POLICY)
    return {
        issue.code
        for issue in report.issues
        if issue.severity is LintSeverity.BLOCKER
    }


def test_real_reviewed_selection_builds_a_valid_structured_page(product_override):
    result = validate_v2_sections(_sections(product_override), product_override, {})

    assert result.passed, _messages(result)
    assert tuple(item.reviewed.variant_id for item in result.selected) == tuple(
        variant_id
        for company in PROFESSIONAL_COMPANY_ORDER
        for variant_id in DEFAULT_SELECTION[company]
    )
    assert result.summary is not None
    assert result.summary.candidate_id == DEFAULT_SUMMARY_ID
    assert result.fluo_variant is not None
    assert result.fluo_variant.variant_id == DEFAULT_FLUO_ID
    assert result.document is not None
    assert tuple(block.company for block in result.document.experience_blocks) == (
        PROFESSIONAL_COMPANY_ORDER
    )


def test_horizontal_formatting_divider_does_not_become_resume_content(product_override):
    sections = _sections(product_override)
    sections["experience_section"] = sections["experience_section"] + "\n---"

    result = validate_v2_sections(sections, product_override, {})

    assert result.passed, _messages(result)


def test_live_audit_notes_are_derived_from_exact_selected_content(product_override):
    sections = _sections(product_override)
    sections["selection_notes"] = "Model-authored explanation instead of exact IDs."

    sections["selection_notes"] = canonicalize_v2_selection_notes(
        sections,
        product_override,
    )
    result = validate_v2_sections(sections, product_override, {})

    assert result.passed, _messages(result)
    assert "Selected variants: F-ENTERPRISE-amazon-deal-impact" in sections["selection_notes"]
    assert f"Summary: {DEFAULT_SUMMARY_ID}" in sections["selection_notes"]
    assert f"Fluo decision: include with {DEFAULT_FLUO_ID}" in sections["selection_notes"]


def test_one_character_rewrite_is_not_an_exact_reviewed_selection(product_override):
    sections = _sections(product_override)
    exact = _variant_map(product_override)["G-LATENCY-studyfetch-readable-tradeoff"].text
    sections["experience_section"] = sections["experience_section"].replace(
        exact,
        exact.replace("sub-second", "near-instant"),
        1,
    )

    result = validate_v2_sections(sections, product_override, {})

    assert not result.passed
    assert "is not an exact reviewed variant" in _messages(result)


@pytest.mark.parametrize(
    "notes_mutator, expected_error",
    (
        (
            lambda lines: [
                (
                    "Selected variants: "
                    + ", ".join(
                        reversed(
                            lines[1].removeprefix("Selected variants: ").split(", ")
                        )
                    )
                )
                if line.startswith("Selected variants: ")
                else line
                for line in lines
            ],
            "must list exactly the selected reviewed variant IDs in output order",
        ),
        (
            lambda lines: [
                line + ", NOT-A-REVIEWED-ID"
                if line.startswith("Selected variants: ")
                else line
                for line in lines
            ],
            "must list exactly the selected reviewed variant IDs in output order",
        ),
        (
            lambda lines: [
                "Summary: summary/product/marketplace-growth"
                if line.startswith("Summary: ")
                else line
                for line in lines
            ],
            "selection-note Summary must be",
        ),
        (
            lambda lines: [
                line for line in lines if not line.startswith("Fluo decision: ")
            ],
            "must contain exactly one 'Fluo decision' line",
        ),
        (
            lambda lines: [
                "Fluo decision: include with fluo-credit-adverse-selection-ladder"
                if line.startswith("Fluo decision: ")
                else line
                for line in lines
            ],
            "Fluo selection note must record only the included reviewed variant",
        ),
    ),
)
def test_selection_notes_are_an_exact_ordered_contract(
    product_override,
    notes_mutator,
    expected_error,
):
    sections = _sections(product_override)
    sections["selection_notes"] = "\n".join(
        notes_mutator(sections["selection_notes"].splitlines())
    )

    result = validate_v2_sections(sections, product_override, {})

    assert not result.passed
    assert expected_error in _messages(result)


def test_summary_is_rejected_when_its_required_story_evidence_is_absent(product_override):
    selection = dict(DEFAULT_SELECTION)
    selection["FLAIRX AI"] = (
        "f-ceipal-pull-first-account-retention",
        "f-avatar-low-spec-antifraud-tradeoff",
    )

    result = validate_v2_sections(
        _sections(product_override, selection=selection), product_override, {}
    )

    assert not result.passed
    assert (
        "summary summary/product/general-scaled-evidence lacks required page evidence: "
        "['F-ENTERPRISE']"
    ) in result.errors


def test_company_order_is_exact_not_a_bag_of_five_companies(product_override):
    wrong_order = (
        "GOJEK",
        "FLAIRX AI",
        "HEVO DATA",
        "INTUIT",
        "OPTUM",
    )

    result = validate_v2_sections(
        _sections(product_override, company_order=wrong_order), product_override, {}
    )

    assert not result.passed
    assert "Experience company order must be" in _messages(result)


def test_company_allocation_and_total_are_both_enforced(product_override):
    selection = dict(DEFAULT_SELECTION)
    selection["GOJEK"] = selection["GOJEK"][:2]

    result = validate_v2_sections(
        _sections(product_override, selection=selection), product_override, {}
    )

    messages = _messages(result)
    assert not result.passed
    assert "GOJEK: expected 3 bullets, got 2" in messages
    assert "exact-match selection contains 9 bullets, expected 10" in messages


def test_project_only_three_line_fluo_cannot_leak_into_inline_skills(product_override):
    full_bank = load_reviewed_prompt_bank()
    project_only = next(
        variant
        for variant in full_bank.family_map()["FLUO"]
        if variant.variant_id == "FL-FIELD-VALIDATION-studyfetch-closed-loop"
    )
    rows = tuple(
        (family, variants + (project_only,)) if family == "FLUO" else (family, variants)
        for family, variants in product_override.bank.variants_by_family
    )
    tampered_override = replace(
        product_override,
        bank=replace(
            product_override.bank,
            variants=product_override.bank.variants + (project_only,),
            variants_by_family=rows,
        ),
    )
    result = validate_v2_sections(
        _sections(
            tampered_override,
            fluo_id="FL-FIELD-VALIDATION-studyfetch-closed-loop",
        ),
        tampered_override,
        {},
    )

    messages = _messages(result)
    assert not result.passed
    assert "is not admitted for inline assembly" in messages
    assert "costs 3 lines; profile permits 2" in messages


def test_fluo_row_cannot_wrap_reviewed_text_in_unreviewed_copy(product_override):
    result = validate_v2_sections(
        _sections(
            product_override,
            fluo_row_prefix="Fluo, invented positioning copy; ",
        ),
        product_override,
        {},
    )

    assert not result.passed
    assert "must contain only 'Fluo, ' plus the exact reviewed variant" in _messages(result)


def test_skills_rows_must_remain_in_profile_order(product_override):
    labels = list(product_override.profile.skill_rows)
    labels[0], labels[1] = labels[1], labels[0]

    result = validate_v2_sections(
        _sections(product_override, skill_labels=tuple(labels)), product_override, {}
    )

    assert not result.passed
    assert "Skills rows must be" in _messages(result)


def test_skills_values_must_be_exact_profile_bank_entries(product_override):
    sections = _sections(product_override)
    exact = skill_value_candidates_for_profile(
        product_override.profile,
        product_override.bank,
    )["Product Leadership"][0]
    sections["skills_section"] = sections["skills_section"].replace(
        exact,
        exact + ", Blockchain",
        1,
    )

    result = validate_v2_sections(sections, product_override, {})

    assert not result.passed
    assert "Skills row 'Product Leadership' is not an exact profile-funded value" in result.errors


def test_skills_heading_is_case_sensitive_and_exact(product_override):
    sections = _sections(product_override)
    sections["skills_section"] = sections["skills_section"].replace(
        "SKILLS\n",
        "skills\n",
        1,
    )

    result = validate_v2_sections(sections, product_override, {})

    assert not result.passed
    assert "skills heading must be SKILLS, got skills" in result.errors


def test_protected_intuit_incident_cannot_be_replaced_by_keyword_fit(product_override):
    selection = dict(DEFAULT_SELECTION)
    selection["INTUIT"] = (
        "I-BILLING-canonical-renewal-integrity",
        "I-GOVERNANCE-canonical-risk-sequencing",
    )

    result = validate_v2_sections(
        _sections(product_override, selection=selection), product_override, {}
    )

    assert not result.passed
    assert "protected I-INCIDENT story must appear exactly once, got 0" in result.errors


def test_reviewed_archetypes_flow_into_and_trigger_the_assembly_contract(product_override):
    selected_ids = {
        variant_id for variants in DEFAULT_SELECTION.values() for variant_id in variants
    }
    all_diagnostic = tuple(
        replace(variant, archetype="diagnostic")
        if variant.variant_id in selected_ids
        else variant
        for variant in product_override.bank.variants
    )
    override = replace(
        product_override,
        bank=replace(product_override.bank, variants=all_diagnostic),
    )

    result = validate_v2_sections(_sections(override), override, {})

    assert result.passed, _messages(result)
    assert result.document is not None
    codes = _blocker_codes(result.document)
    assert "ARCHETYPE_CEILING_EXCEEDED" in codes
    assert "ACTION_IMPACT_FLOOR_MISSED" in codes
    assert "DIAGNOSTIC_STREAK_EXCEEDED" in codes
