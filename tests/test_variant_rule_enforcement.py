from collections import Counter

import pytest

from resume.variants.rule_coverage import coverage_payload
from shared.variant_admission import (
    CANONICAL_VARIANT_RULEBOOK,
    FactStatus,
    OutcomeTier,
    ResumeVariant,
    VariantRulebookStatus,
    check_new_candidate_admission,
    check_variant_admission,
)
from shared.variant_rule_catalog import (
    RULE_CATALOG,
    STRUCTURED_CHALLENGER_DIMENSIONS,
    STRUCTURED_CRITIC_RULE_GROUPS,
    CoverageStatus,
    RuleOwner,
    validate_rule_catalog,
)
from shared.variant_text_lint import (
    VariantTextSeverity,
    issue_codes,
    lint_candidate_variant_text,
)


def _variant(text: str) -> ResumeVariant:
    return ResumeVariant(
        variant_id="candidate",
        story_id="F-CEIPAL",
        text=text,
        value_signals=("customer-retention",),
        role_tags=("product",),
        fact_status=FactStatus.APPROVED,
        variant_rulebook_status=VariantRulebookStatus.APPROVED,
        variant_rulebook_version=CANONICAL_VARIANT_RULEBOOK,
        stakes=4,
        difficulty=3,
        defensibility=4,
        distinctiveness=3,
        line_cost=2,
        outcome_tier=OutcomeTier.USER_OR_BUSINESS,
        one_argument=True,
        mechanism_supports_claim=True,
        outcome_closes_claim=True,
        outsider_legible=True,
        best_available_outcome=True,
        eligible_profiles=("product-general",),
        fact_atoms=("read-only API", "pull-first workflow", "account retained"),
        source_refs=("fixture",),
    )


def test_rule_catalog_is_exhaustive_owned_and_structured_groups_are_exact():
    assert validate_rule_catalog() == []
    assert len(RULE_CATALOG) == 99
    assert set(STRUCTURED_CRITIC_RULE_GROUPS) == STRUCTURED_CHALLENGER_DIMENSIONS
    grouped = [
        rule_id
        for rule_ids in STRUCTURED_CRITIC_RULE_GROUPS.values()
        for rule_id in rule_ids
    ]
    expected = {
        rule.rule_id
        for rule in RULE_CATALOG
        if rule.owner is RuleOwner.STRUCTURED_CRITIC
        and rule.status in {CoverageStatus.ENFORCED, CoverageStatus.SHADOW}
    }
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == expected


def test_coverage_command_reports_all_rules_and_keeps_gaps_visible():
    payload = coverage_payload()

    assert payload["coverage_gate_passed"] is True
    assert payload["mapped_rules"] == payload["cataloged_rules"] == 99
    assert Counter(rule.owner.value for rule in RULE_CATALOG) == Counter(
        payload["owner_counts"]
    )
    unresolved = {rule["rule_id"] for rule in payload["unresolved_rules"]}
    assert {"V4-04-FACT-BOUNDARY", "ARCH-PROVENANCE"} <= unresolved
    assert {"V4-06-CONTRAST-CAP", "V4-09-IMPACT-CAP"} <= unresolved


def test_ceipal_saved_opener_is_a_hard_candidate_blocker():
    text = (
        "Saved FlairX's highest-volume account after Ceipal's read-only API blocked "
        "score write-back; shipped a pull-first MVP that removed roughly 80% of "
        "duplicate work and launched on Ceipal's marketplace as a new B2B channel."
    )
    report = lint_candidate_variant_text(text)

    assert "FORBIDDEN_OR_WEAK_OPENER" in issue_codes(
        report, VariantTextSeverity.BLOCKER
    )
    assert "PREDICATE_LOAD_HIGH" in issue_codes(report, VariantTextSeverity.REVIEW)
    assert "LOW_CLAUSE_COHESION_PROXY" in issue_codes(
        report, VariantTextSeverity.REVIEW
    )


def test_clean_low_complexity_variant_is_not_penalized():
    text = (
        "Shipped anti-fraud controls that stayed viable on low-spec candidate "
        "devices by combining gaze, face-mesh and voice signals under 8% CPU and "
        "150ms interruption latency."
    )
    report = lint_candidate_variant_text(text)

    assert report.blockers == ()
    assert "PREDICATE_LOAD_HIGH" not in issue_codes(report)
    assert "LOW_CLAUSE_COHESION_PROXY" not in issue_codes(report)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("When the migration broke, built a rollback tool that restored service.", "SUBORDINATE_CLAUSE_OPENER"),
        ("Improved reliability by building a typed retry policy for failed jobs.", "IMPROVED_BY_OPENER"),
        ("Managed the launch and increased activation 20%.", "FORBIDDEN_OR_WEAK_OPENER"),
        ("Built a holistic workflow that cut review time 20%.", "FORBIDDEN_WORD_PRESENT"),
        ("Built a tool — then shipped it to 100 users.", "EM_DASH_PRESENT"),
        ("Built a tool (with retries) that cut review time 20%.", "PARENTHESES_PRESENT"),
        ("Built the stakeholder case and secured approval.", "GENERIC_MECHANISM_PHRASE"),
        ("40% faster: latency down after the migration.", "DECORATIVE_METRIC_OPENER"),
        ("Designed the workflow with stakeholders and cut cycle time 20%.", "VAGUE_STAKEHOLDER_NOUN"),
        ("Built an experiment; conversion up 9%.", "FRAGMENT_LIST_OUTCOME"),
    ],
)
def test_documented_deterministic_failures_are_blocked(text, expected):
    report = lint_candidate_variant_text(text)
    assert expected in issue_codes(report, VariantTextSeverity.BLOCKER)


def test_coherence_proxies_force_review_without_claiming_semantic_failure():
    text = (
        "Diagnosed account risk from write-back failures across the customer base; "
        "launched an ecosystem marketplace channel that expanded partner discovery."
    )
    report = lint_candidate_variant_text(text)

    assert report.blockers == ()
    assert "LOW_CLAUSE_COHESION_PROXY" in issue_codes(
        report, VariantTextSeverity.REVIEW
    )


def test_detection_opener_cannot_be_mislabeled_action():
    report = lint_candidate_variant_text(
        "Caught a hidden billing mismatch; built a reconciliation gate that restored accurate renewals.",
        declared_archetype="action",
    )

    assert "ARCHETYPE_METADATA_MISMATCH" in issue_codes(
        report, VariantTextSeverity.BLOCKER
    )


def test_new_candidate_admission_runs_text_gate_without_retroactively_rejecting_incumbents():
    weak = _variant(
        "Saved a flagship account after a vendor API failed; shipped a pull-first "
        "workflow that retained the customer."
    )

    assert check_variant_admission(weak).admitted
    candidate_result = check_new_candidate_admission(weak)
    assert not candidate_result.admitted
    assert any("FORBIDDEN_OR_WEAK_OPENER" in error for error in candidate_result.errors)
