import json
import re
from pathlib import Path

from resume.variants import challenger_runner
from shared.gold_variant_registry import load_registry


BATCH_PATH = (
    challenger_runner.REPO_ROOT
    / "docs"
    / "resume_generator_reviews"
    / "variant_batches"
    / "BATCH_A_FLAIRX_FLUO_PROJECTS.json"
)

EXPECTED_FAMILIES = {
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
}


def test_batch_a_covers_every_live_incumbent_once_and_preserves_exact_text():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    grouped = challenger_runner.group_causal_stories(
        challenger_runner.load_inventory()
    )
    assert set(batch["families"]) == EXPECTED_FAMILIES

    expected = {
        record.stable_id: record.text
        for family in EXPECTED_FAMILIES
        for record in grouped[family]
    }
    decisions = [
        decision
        for family in batch["families"].values()
        for decision in family["incumbents"]
    ]
    decision_ids = [decision["stable_id"] for decision in decisions]
    assert len(decision_ids) == len(set(decision_ids)) == 44
    assert set(decision_ids) == set(expected)

    recommended = [
        variant
        for family in batch["families"].values()
        for variant in family["recommended_variants"]
    ]
    recommended_by_id = {variant["variant_id"]: variant for variant in recommended}
    assert len(recommended) == 32
    replacement_ids = {
        decision["replacement_id"]
        for decision in decisions
        if decision["replacement_id"]
    }
    assert replacement_ids <= set(recommended_by_id)

    gold = {variant.variant_id: variant.text for variant in load_registry()}
    for variant in recommended:
        assert isinstance(variant["use_case"], str) and variant["use_case"].strip()
        if variant["status"].startswith("incumbent"):
            assert variant["text"] == expected[variant["variant_id"]]
        elif variant["status"] == "known_gold":
            assert variant["text"] == gold[variant["variant_id"]]
        elif variant["status"] == "challenger":
            assert re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", variant["variant_id"]
            )


def test_batch_a_uses_confirmed_flairx_design_and_shipping_facts():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    enterprise = batch["families"]["F-ENTERPRISE"]
    recommended_ids = {
        variant["variant_id"] for variant in enterprise["recommended_variants"]
    }

    assert "F-ENTERPRISE-studyfetch-design-delivery" in recommended_ids
    assert "F-ENTERPRISE-amazon-deal-impact" in recommended_ids
    zero_to_one = next(
        decision
        for decision in enterprise["incumbents"]
        if decision["stable_id"] == "pm/f-enterprise/zero-to-one"
    )
    assert zero_to_one == {
        "stable_id": "pm/f-enterprise/zero-to-one",
        "verdict": "replace",
        "replacement_id": "F-ENTERPRISE-amazon-deal-impact",
    }


def test_batch_a_keeps_sourcing_criterion_conditional_and_challenges_soft_leads():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))

    sourcing = batch["families"]["F-SOURCING"]
    sourcing_by_id = {
        variant["variant_id"]: variant for variant in sourcing["recommended_variants"]
    }
    assert "pm/f-sourcing/unit-economics" in sourcing_by_id
    assert sourcing_by_id["pm/f-sourcing/product-discovery"]["use_case"] == (
        "customer research and recruiter-workflow insight only"
    )

    avatar = batch["families"]["F-AVATAR"]
    avatar_decision = next(
        item
        for item in avatar["incumbents"]
        if item["stable_id"] == "pm/f-avatar/trust-performance"
    )
    assert avatar_decision["replacement_id"] == (
        "f-avatar-low-spec-antifraud-tradeoff"
    )

    ops = batch["families"]["F-OPS"]
    ops_decision = next(
        item
        for item in ops["incumbents"]
        if item["stable_id"] == "pm/f-ops/influence-without-authority"
    )
    assert ops_decision["replacement_id"] == "f-ops-ceo-routing-removal"


def test_batch_a_has_no_provenance_only_holds():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    decisions = [
        decision
        for family in batch["families"].values()
        for decision in family["incumbents"]
    ]
    recommended = [
        variant
        for family in batch["families"].values()
        for variant in family["recommended_variants"]
    ]

    assert not [decision for decision in decisions if decision["verdict"] == "hold"]
    assert not [variant for variant in recommended if "conditional" in variant["status"]]
    assert batch["families"]["P-GRAB"]["incumbents"] == [
        {
            "stable_id": "nonpm/p-grab/mobility-safety",
            "verdict": "retire",
            "replacement_id": "",
        }
    ]


def test_ceipal_repair_is_linear_and_flows_from_constraint_to_account_outcome():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    ceipal = batch["families"]["F-CEIPAL"]
    by_id = {
        variant["variant_id"]: variant
        for variant in ceipal["recommended_variants"]
    }

    general = by_id["f-ceipal-pull-first-account-retention"]["text"]
    assert general == (
        "Re-scoped FlairX's Ceipal integration after its API blocked score "
        "write-back, automating job and candidate imports to eliminate "
        "~80% of recruiters' duplicate entry while retaining FlairX's "
        "highest-volume account."
    )
    assert not general.startswith("Saved ")
    assert len(general) <= 215
    assert general.lower().count(" and ") <= 1
    assert "job and candidate imports" in general
    assert "API blocked score write-back" in general
    assert "~80% of recruiters' duplicate entry" in general
    assert general.endswith("retaining FlairX's highest-volume account.")

    ecosystem = by_id["f-ceipal-marketplace-product-channel"]["text"]
    assert "public Marketplace product" in ecosystem
    assert ecosystem.endswith("FlairX's first ATS-based inbound channel.")


def test_low_stakes_fluo_feed_leaves_core_slate_for_credit_product_judgment():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    fluo = batch["families"]["FLUO"]
    by_id = {
        variant["variant_id"]: variant
        for variant in fluo["recommended_variants"]
    }

    assert "fluo-sponsorship-evidence-calibration" not in by_id
    assert by_id["fluo-credit-adverse-selection-ladder"]["text"] == (
        "Redirected Fluo's proposed $5,000 instant credit line into a "
        "secured-card-to-unsecured-credit ladder after showing demand "
        "concentrated among students with the least repayment capacity under "
        "F-1 work limits."
    )
    data_platform = next(
        decision
        for decision in fluo["incumbents"]
        if decision["stable_id"] == "pm/fluo/fluo-data-platform"
    )
    assert data_platform == {
        "stable_id": "pm/fluo/fluo-data-platform",
        "verdict": "retire",
        "replacement_id": "",
    }


def test_fluo_assembly_metadata_keeps_long_field_validation_out_of_inline_rows():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    by_id = {
        variant["variant_id"]: variant
        for variant in batch["families"]["FLUO"]["recommended_variants"]
    }

    assert {
        variant_id: (variant["line_cost"], tuple(variant["assembly_modes"]))
        for variant_id, variant in by_id.items()
    } == {
        "FL-INSTITUTIONAL-amazon-inline-prearrival": (2, ("inline",)),
        "FL-FIELD-VALIDATION-studyfetch-closed-loop": (
            3,
            ("project-replacement",),
        ),
        "fluo-proprietary-housing-evidence": (2, ("inline",)),
        "fluo-credit-adverse-selection-ladder": (2, ("inline",)),
    }
