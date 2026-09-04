import json
from collections import Counter

from shared import prompt_variant_inventory as inventory
from shared.resume_profiles import validate_summary_identity


PM_SELECTABLE_COUNTS = {
    "F-ENTERPRISE": 5,
    "F-AVATAR": 5,
    "F-OPS": 5,
    "F-CEIPAL": 5,
    "F-SOURCING": 5,
    "G-SUPPLY": 6,
    "G-PRICING": 5,
    "G-LATENCY": 5,
    "H-BATCHSHIFT": 5,
    "H-MONITORING": 5,
    "H-REGRESSION": 2,
    "H-QUERY": 2,
    "H-MONITORING-AI": 2,
    "I-BILLING": 5,
    "I-INCIDENT": 4,
    "FLUO": 4,
    "SKILLS-ANALYTICS": 6,
    "SKILLS-COMMUNITY": 2,
}

NONPM_SELECTABLE_COUNTS = {
    "P-FOUNDER": 3,
    "P-LOREAL": 3,
    "P-GRAB": 1,
    "G-SUPPLY": 5,
    "G-PRICING": 5,
    "G-LATENCY": 4,
    "H-BATCHSHIFT": 6,
    "H-MONITORING": 6,
    "H-SUPPORT-OPS": 4,
    "I-RECONCILIATION": 5,
    "I-GOVERNANCE": 5,
    "I-INCIDENT": 6,
    "O-PROVIDER": 6,
    "O-AFFORDABILITY": 6,
    "SUMMARY": 9,
}

PM_REFERENCE_COUNTS = {
    "I-PRIORITIZATION": 3,
    "I-ROADMAP": 2,
    "I-RECONCILIATION": 2,
    "I-STRATEGIC-NO": 3,
    "O-PROVIDER": 5,
    "O-AFFORDABILITY": 6,
    "SUMMARY": 5,
}


def _records_from_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _batch_d_review():
    path = (
        inventory.REPO_ROOT
        / "docs"
        / "resume_generator_reviews"
        / "variant_batches"
        / "BATCH_D_SUMMARIES_SKILLS.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_inventory_has_current_track_and_story_counts():
    selectable, references = inventory.partition_inventory(
        inventory.extract_prompt_inventory()
    )

    assert len(selectable) == 152
    assert len(references) == 26
    assert Counter(record.track for record in selectable) == {"pm": 78, "nonpm": 74}
    assert Counter(record.track for record in references) == {"pm": 26}

    pm_counts = Counter(
        record.story for record in selectable if record.track == "pm"
    )
    nonpm_counts = Counter(
        record.story for record in selectable if record.track == "nonpm"
    )
    reference_counts = Counter(record.story for record in references)
    assert dict(pm_counts) == PM_SELECTABLE_COUNTS
    assert dict(nonpm_counts) == NONPM_SELECTABLE_COUNTS
    assert dict(reference_counts) == PM_REFERENCE_COUNTS


def test_inventory_ids_are_unique_and_fields_come_from_prompt_text():
    records = inventory.extract_prompt_inventory()
    ids = [record.stable_id for record in records]
    assert len(ids) == len(set(ids))

    record = next(
        item for item in records if item.stable_id == "pm/f-enterprise/zero-to-one"
    )
    assert record.label == "zero-to-one"
    assert record.source_path == "resume/freeform/prompts/freeform_master_v2.txt"
    assert record.source_line == 179
    assert record.selectability == inventory.SELECTABLE
    assert record.text.startswith("Turned Genpact's ban")
    assert len(record.text_sha256) == 64


def test_quoted_label_annotation_is_not_mistaken_for_variant_text():
    records = {record.stable_id: record for record in inventory.extract_prompt_inventory()}
    text = records["pm/g-pricing/funnel-synthesis"].text

    assert text.startswith("Synthesized funnel analytics, pricing elasticity data")
    assert text != "Synthesized [data→insight]"


def test_prohibited_and_reference_only_records_are_separated():
    selectable, references = inventory.partition_inventory(
        inventory.extract_prompt_inventory()
    )

    assert all(record.selectability == inventory.SELECTABLE for record in selectable)
    assert Counter(record.selectability for record in references) == {
        inventory.PROHIBITED_REFERENCE: 21,
        inventory.REFERENCE_ONLY: 5,
    }
    assert {record.story for record in references if record.selectability == inventory.REFERENCE_ONLY} == {
        "SUMMARY"
    }
    assert "pm/o-provider/schema-mechanism" in {
        record.stable_id
        for record in references
        if record.selectability == inventory.PROHIBITED_REFERENCE
    }


def test_checked_in_snapshots_exactly_match_current_prompts():
    assert inventory.check_snapshots() == []

    selectable = _records_from_jsonl(inventory.SELECTABLE_SNAPSHOT)
    references = _records_from_jsonl(inventory.REFERENCE_SNAPSHOT)
    assert len(selectable) == 152
    assert len(references) == 26
    assert all(record["selectability"] == inventory.SELECTABLE for record in selectable)
    assert all(record["selectability"] != inventory.SELECTABLE for record in references)


def test_snapshot_check_reports_drift_without_rewriting(monkeypatch, tmp_path):
    selectable, references = inventory.partition_inventory(
        inventory.extract_prompt_inventory()
    )
    selectable_path = tmp_path / "selectable.jsonl"
    reference_path = tmp_path / "references.jsonl"
    selectable_path.write_text("{}\n", encoding="utf-8")
    reference_path.write_text(inventory.render_jsonl(references), encoding="utf-8")

    monkeypatch.setattr(inventory, "SELECTABLE_SNAPSHOT", selectable_path)
    monkeypatch.setattr(inventory, "REFERENCE_SNAPSHOT", reference_path)

    before = selectable_path.read_text(encoding="utf-8")
    errors = inventory.check_snapshots()
    assert errors == [f"prompt inventory drift: {selectable_path}"]
    assert selectable_path.read_text(encoding="utf-8") == before
    assert inventory.render_jsonl(selectable) != before


def test_batch_d_covers_every_summary_and_support_row_exactly_once():
    prompt_records = [
        record
        for record in inventory.extract_prompt_inventory()
        if record.story in {"SUMMARY", "SKILLS-ANALYTICS", "SKILLS-COMMUNITY"}
    ]
    reviewed = _batch_d_review()["prompt_incumbents"]
    reviewed_ids = [record["stable_id"] for record in reviewed]

    assert len(prompt_records) == 22
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 22
    assert set(reviewed_ids) == {record.stable_id for record in prompt_records}

    prompt_by_id = {record.stable_id: record for record in prompt_records}
    for record in reviewed:
        assert record["selectability"] == prompt_by_id[record["stable_id"]].selectability


def test_batch_d_summary_candidates_are_funded_and_text_metadata_is_exact():
    review = _batch_d_review()
    summaries = review["summary_candidates"]
    candidate_ids = [candidate["candidate_id"] for candidate in summaries]

    assert len(candidate_ids) == len(set(candidate_ids))
    for candidate in summaries:
        assert candidate["character_count"] == len(candidate["text"])
        assert candidate["required_page_evidence"]
        assert "At USC Marshall to" not in candidate["text"]
        for profile_id in candidate["eligible_profiles"]:
            assert validate_summary_identity(profile_id, candidate["text"]) == []

    fixture_dir = inventory.REPO_ROOT / "tests" / "fixtures" / "resume_gold"
    amazon = json.loads(
        (fixture_dir / "amazon_product_operator_2026-08-27.json").read_text(
            encoding="utf-8"
        )
    )
    studyfetch = json.loads(
        (fixture_dir / "studyfetch_builder_discovery_2026-09-01.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {candidate["candidate_id"]: candidate for candidate in summaries}
    summary_replacements = {
        replacement_id
        for incumbent in review["prompt_incumbents"]
        for replacement_id in incumbent["replacement_ids"]
        if replacement_id.startswith("summary/")
    }
    assert summary_replacements <= set(by_id)
    assert by_id["summary/product/general-scaled-evidence"]["text"] == amazon["summary_text"]
    assert by_id["summary/product/independent-builder"]["text"] == studyfetch["summary_text"]


def test_batch_d_nonpm_summaries_preserve_attribution_and_timeline_boundaries():
    summaries = {
        candidate["candidate_id"]: candidate["text"]
        for candidate in _batch_d_review()["summary_candidates"]
    }

    client = summaries["summary/nonpm/client-implementation-value"]
    assert "from 6 months to 10 weeks" in client
    assert "$20M" not in client

    commercial = summaries["summary/nonpm/commercial-growth-decisions"]
    assert "provider-expansion recommendation" in commercial
    assert "$20M+ annual opportunity" in commercial
    assert "$20M+ network expansion" not in commercial

    ai = summaries["summary/nonpm/ai-human-control"]
    assert "recent AI work" not in ai
    assert "human-reviewed affordability actions" in ai

    technical = summaries["summary/nonpm/technical-platform-execution"]
    assert "billing reconciliation for 80K+ businesses" in technical
    assert "incident work spanning eight teams and 80K+ businesses" not in technical


def test_batch_d_product_summaries_do_not_merge_neighboring_outcomes():
    summaries = {
        candidate["candidate_id"]: candidate
        for candidate in _batch_d_review()["summary_candidates"]
    }

    marketplace = summaries["summary/product/marketplace-growth"]["text"]
    assert "independently cut quote latency 70%" in marketplace
    assert "to launch a $3.2M ride tier and recover" not in marketplace

    fintech = summaries["summary/product/fintech-billing-trust"]["text"]
    assert "rebuilt reconciliation for 80K+ businesses" in fintech
    assert "billing errors affecting 80K+ businesses" not in fintech

    bizops = summaries["summary/nonpm/bizops-operating-cadence"]
    assert "a shared release mechanism at Hevo" in bizops["text"]
    assert "H-REGRESSION" in bizops["required_page_evidence"]
    assert "H-BATCHSHIFT" not in bizops["required_page_evidence"]


def test_batch_d_preserves_kpi_row_and_splits_unrelated_community_arguments():
    review = _batch_d_review()
    incumbents = {
        record["stable_id"]: record for record in review["prompt_incumbents"]
    }
    assert incumbents["pm/skills-analytics/analytics-kpi"]["verdict"] == "retain_exact"
    assert (
        incumbents["pm/skills-community/community-full"]["verdict"]
        == "replace_split_argument"
    )
    assert (
        incumbents["pm/skills-community/community-short"]["verdict"]
        == "replace_split_argument"
    )

    community = review["community_candidates"]
    community_ids = {candidate["candidate_id"] for candidate in community}
    all_replacements = {
        replacement_id
        for record in review["prompt_incumbents"]
        for replacement_id in record["replacement_ids"]
        if replacement_id.startswith("community/")
    }
    assert all_replacements == community_ids
    assert all(candidate["character_count"] == len(candidate["text"]) for candidate in community)
    assert all(not ("400+" in candidate["text"] and "$20K" in candidate["text"]) for candidate in community)

    gold = _records_from_jsonl(
        inventory.REPO_ROOT / "resume" / "variants" / "approved_gold_variants.jsonl"
    )
    niveda = next(
        record for record in gold if record["variant_id"] == "NIVEDA-studyfetch-mobile-school"
    )
    by_id = {candidate["candidate_id"]: candidate for candidate in community}
    assert by_id["community/niveda-mobile-school-full"]["text"] == niveda["text"]
