import json
from pathlib import Path

from shared.gold_variant_registry import DEFAULT_REGISTRY_PATH, REPO_ROOT, load_registry


BATCH_PATH = (
    REPO_ROOT
    / "docs"
    / "resume_generator_reviews"
    / "variant_batches"
    / "BATCH_B_GOJEK_HEVO_BATCH.json"
)
REVIEW_PATH = BATCH_PATH.with_suffix(".md")
LIVE_SNAPSHOT = REPO_ROOT / "resume" / "variants" / "live_prompt_variants.jsonl"
FAMILIES = {"G-SUPPLY", "G-PRICING", "G-LATENCY", "H-BATCHSHIFT"}
EXPECTED_SLATE_SIZES = {
    "G-SUPPLY": 4,
    "G-PRICING": 3,
    "G-LATENCY": 3,
    "H-BATCHSHIFT": 2,
}
EXPECTED_HOLDS = set()
CANONICAL_DISTINCT_IDS = {
    "canonical-v4/g-supply/ecosystem-GTM",
    "canonical-v4/g-supply/API-launch",
    "canonical-v4/g-supply/platform-led",
    "canonical-v4/g-latency/throughput-engineering",
}


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_batch_b_maps_every_live_gold_and_distinct_canonical_incumbent_once():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    live_ids = {
        record["stable_id"]
        for record in _jsonl(LIVE_SNAPSHOT)
        if record["story"] in FAMILIES
    }
    gold_ids = {
        record["variant_id"]
        for record in _jsonl(DEFAULT_REGISTRY_PATH)
        if record["story_id"] in FAMILIES
    }
    expected = live_ids | gold_ids | CANONICAL_DISTINCT_IDS

    actual = [
        incumbent["stable_id"]
        for family in batch["families"].values()
        for incumbent in family["incumbents"]
    ]
    assert len(actual) == len(set(actual))
    assert set(actual) == expected


def test_batch_b_replacements_resolve_and_recommended_slates_are_bounded():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    for family_name, family in batch["families"].items():
        recommended = {
            variant["variant_id"]: variant
            for variant in family["recommended_variants"]
        }
        assert len(recommended) == EXPECTED_SLATE_SIZES[family_name]
        assert 2 <= len(recommended) <= 4
        assert sorted(item["priority"] for item in recommended.values()) == list(
            range(1, len(recommended) + 1)
        )
        for incumbent in family["incumbents"]:
            assert incumbent["verdict"] in {"retain", "replace", "retire", "hold"}
            if incumbent["verdict"] == "replace":
                assert incumbent["replacement_id"] in recommended
            elif incumbent["verdict"] in {"retire", "hold"}:
                assert incumbent["replacement_id"] is None


def test_batch_b_preserves_exact_gold_text_and_is_reviewable_in_markdown():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    gold = {variant.variant_id: variant.text for variant in load_registry()}
    review = REVIEW_PATH.read_text(encoding="utf-8")
    for family in batch["families"].values():
        for variant in family["recommended_variants"]:
            if variant["variant_id"] in gold:
                assert variant["text"] == gold[variant["variant_id"]]
        for incumbent in family["incumbents"]:
            assert f"`{incumbent['stable_id']}`" in review


def test_batch_b_holds_only_real_conflicts_or_material_tradeoffs():
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    actual = {
        incumbent["stable_id"]
        for family in batch["families"].values()
        for incumbent in family["incumbents"]
        if incumbent["verdict"] == "hold"
    }
    assert actual == EXPECTED_HOLDS
