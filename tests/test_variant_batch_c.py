import json

from resume.variants import challenger_runner
from shared.gold_variant_registry import load_registry


BATCH_PATH = (
    challenger_runner.REPO_ROOT
    / "docs"
    / "resume_generator_reviews"
    / "variant_batches"
    / "BATCH_C_HEVO_INTUIT_OPTUM.json"
)
REVIEW_PATH = BATCH_PATH.with_suffix(".md")
EXPECTED_GROUPS = {
    "H-MONITORING",
    "I-BILLING",
    "I-GOVERNANCE",
    "I-INCIDENT",
    "O-AFFORDABILITY",
    "O-PROVIDER",
}


def _batch():
    return json.loads(BATCH_PATH.read_text(encoding="utf-8"))


def _live_by_id():
    grouped = challenger_runner.group_causal_stories(
        challenger_runner.load_inventory()
    )
    return {
        record.stable_id: record.text
        for family in EXPECTED_GROUPS
        for record in grouped[family]
    }


def test_batch_c_maps_all_50_live_incumbents_exactly_once():
    batch = _batch()
    expected = _live_by_id()
    actual = [
        incumbent["stable_id"]
        for family in batch["families"].values()
        for incumbent in family["incumbents"]
    ]

    assert set(batch["families"]) == EXPECTED_GROUPS
    assert len(expected) == 50
    assert len(actual) == len(set(actual)) == 50
    assert set(actual) == set(expected)


def test_batch_c_replacements_resolve_to_bounded_recommended_slates():
    batch = _batch()
    for family in batch["families"].values():
        recommended = {
            variant["variant_id"]: variant
            for variant in family["recommended_variants"]
        }
        assert 2 <= len(recommended) <= 4
        assert sorted(item["priority"] for item in recommended.values()) == list(
            range(1, len(recommended) + 1)
        )

        for incumbent in family["incumbents"]:
            assert incumbent["verdict"] in {
                "retain_exact",
                "replace",
                "retire_dominated",
                "hold_for_human",
            }
            replacement_id = incumbent["replacement_id"]
            if replacement_id is not None:
                assert replacement_id in recommended
            if incumbent["verdict"] == "replace":
                assert replacement_id is not None
            if incumbent["verdict"] == "retire_dominated":
                assert replacement_id is None


def test_batch_c_every_recommendation_has_an_exact_reviewed_use_case():
    batch = _batch()
    review = REVIEW_PATH.read_text(encoding="utf-8")
    recommended = [
        variant
        for family in batch["families"].values()
        for variant in family["recommended_variants"]
    ]

    assert len(recommended) == 19
    for variant in recommended:
        use_case = variant.get("use_case")
        assert isinstance(use_case, str)
        assert use_case.strip() == use_case
        assert use_case
        assert f"Use: {use_case}." in review


def test_batch_c_preserves_source_text_for_incumbent_and_gold_recommendations():
    batch = _batch()
    live = _live_by_id()
    gold = {variant.variant_id: variant.text for variant in load_registry()}
    recommended = {
        variant["variant_id"]: variant
        for family in batch["families"].values()
        for variant in family["recommended_variants"]
    }

    for variant in recommended.values():
        if variant["status"] == "incumbent":
            assert variant["text"] == live[variant["variant_id"]]
        elif variant["status"] == "approved_gold":
            assert variant["text"] == gold[variant["variant_id"]]

    for family in batch["families"].values():
        for incumbent in family["incumbents"]:
            if incumbent["verdict"] != "retain_exact":
                continue
            retained = recommended[incumbent["replacement_id"]]
            assert retained["text"] == live[incumbent["stable_id"]]
