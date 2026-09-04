"""Non-regression checks for the user-resolved cross-variant fact choices."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = (
    REPO_ROOT
    / "docs"
    / "resume_generator_reviews"
    / "variant_batches"
    / "CANONICAL_STORY_DECISIONS_2026-09-03.json"
)
BATCH_PATHS = (
    DECISIONS_PATH.with_name("BATCH_B_GOJEK_HEVO_BATCH.json"),
    DECISIONS_PATH.with_name("BATCH_C_HEVO_INTUIT_OPTUM.json"),
)

EXPECTED_TEXT = {
    "G-SUPPLY": "Led Gojek's fleet integration platform and partner operating model; replaced bespoke builds with a standardized API and validation workflow, enabling 18% supply growth and cutting pickup ETAs by 1.5 minutes across Singapore and Bali.",
    "G-PRICING": "Separated price-sensitive abandonment from quote-latency drop-off through funnel analysis and 20+ rider interviews; validated a lower-cost ride tier through A/B tests, lifting conversion 9% and generating $3.2M in incremental revenue.",
    "G-LATENCY": "Traded live fare recalculation for sub-second quotes by pre-caching pricing across 12 high-demand corridors; held fare variance within 4%, cut latency 70%, and recovered ~28K monthly rides.",
    "H-BATCHSHIFT": "Drove Hevo 2.0's batch-first shift after Fortune 500 trials stalled on auditability; traded streaming speed for verifiable correctness and clear failure boundaries, improving stability 45% and onboarding 8 enterprise customers in 90 days.",
    "H-MONITORING": "Shipped an AI monitoring surface that turned alert storms into single incident cards; kept detection deterministic and used GenAI over a 20+ failure taxonomy to rank recovery actions, cutting diagnosis from 45 to under 5 minutes across 120K+ pipelines.",
    "I-BILLING": "Traced silent SMB cancellations to billing mismatches across five systems; built a reconciliation model for 80K+ businesses and a financial case that shifted the roadmap from feature delivery to billing integrity, lifting renewals 10%.",
    "I-INCIDENT": "Led recovery after billing-state errors canceled subscriptions for 1,500+ businesses; ran fix-writing and QA validation in parallel, cutting resolution from days to hours.",
    "I-GOVERNANCE": "Reframed delivery drag as a sequencing problem across 8 teams; built a risk-tiered prioritization model for 20K+ issues that improved throughput 25%.",
}

EXPECTED_CHOICES = {
    "G-SUPPLY": "1.5-minute pickup-ETA reduction",
    "G-PRICING": "20+ rider interviews, A/B validation, 9% conversion lift, and $3.2M incremental revenue",
    "G-LATENCY": "approximately 28K recovered monthly rides",
    "H-BATCHSHIFT": "8 enterprise customers within 90 days",
    "H-MONITORING": "diagnosis reduced from 45 to under 5 minutes across 120K+ pipelines",
    "I-BILLING": "five systems, 80K+ businesses, and a 10% renewal lift",
    "I-INCIDENT": "fix-writing and validation cycle cut from days to hours, with no 8-team claim",
    "I-GOVERNANCE": "8 teams belongs exclusively to the 20K+ backlog governance story",
}

ALLOWED_OPENERS = {
    "Led",
    "Separated",
    "Traded",
    "Drove",
    "Shipped",
    "Traced",
    "Reframed",
}


def _payload() -> dict:
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _by_story() -> dict[str, dict]:
    return {item["story_id"]: item for item in _payload()["decisions"]}


def test_eight_choices_and_preferred_copy_are_exactly_locked():
    payload = _payload()
    decisions = payload["decisions"]
    by_story = _by_story()

    assert payload["mode"] == "review-only"
    assert payload["live_wiring"] is False
    assert len(decisions) == len({item["decision_id"] for item in decisions}) == 8
    assert set(by_story) == set(EXPECTED_TEXT) == set(EXPECTED_CHOICES)

    for story_id, expected_text in EXPECTED_TEXT.items():
        assert by_story[story_id]["preferred_text"] == expected_text
        assert by_story[story_id]["chosen_representation"] == EXPECTED_CHOICES[story_id]


def test_each_preferred_bullet_uses_required_and_avoids_retired_literals():
    for decision in _payload()["decisions"]:
        text = decision["preferred_text"]
        for literal in decision["required_literals"]:
            assert literal in text, f"{decision['story_id']} lost required {literal!r}"
        for literal in decision["excluded_literals"]:
            assert literal not in text, (
                f"{decision['story_id']} revived retired {literal!r}"
            )


def test_eight_team_scope_is_exclusive_to_governance():
    decisions = _payload()["decisions"]
    owners = [
        decision["story_id"]
        for decision in decisions
        if "8 teams" in decision["preferred_text"]
    ]
    assert owners == ["I-GOVERNANCE"]

    scope_lock = _by_story()["I-GOVERNANCE"]["scope_lock"]
    assert scope_lock == {
        "literal": "8 teams",
        "exclusive_story_id": "I-GOVERNANCE",
    }


def test_gojek_stories_use_only_one_revenue_currency():
    by_story = _by_story()
    assert "$3.2M" in by_story["G-PRICING"]["preferred_text"]
    assert "$" not in by_story["G-SUPPLY"]["preferred_text"]
    assert "$" not in by_story["G-LATENCY"]["preferred_text"]


def test_preferred_bullets_meet_variant_level_readability_contract():
    for story_id, decision in _by_story().items():
        text = decision["preferred_text"]
        assert 130 <= len(text) <= 260, (story_id, len(text))
        assert text.endswith(".")
        assert "—" not in text
        assert "(" not in text and ")" not in text
        assert text.count(";") == 1
        assert text.split(maxsplit=1)[0] in ALLOWED_OPENERS


def test_every_decision_names_existing_source_files():
    for decision in _payload()["decisions"]:
        assert len(decision["source_refs"]) >= 2
        for source_ref in decision["source_refs"]:
            assert (REPO_ROOT / source_ref).is_file(), (
                decision["story_id"],
                source_ref,
            )


def test_batch_reviews_use_the_locked_default_id_and_text():
    reviewed_families = {}
    for batch_path in BATCH_PATHS:
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        assert batch["canonical_decisions_file"] == DECISIONS_PATH.name
        reviewed_families.update(batch["families"])

    for story_id, decision in _by_story().items():
        family = reviewed_families[story_id]
        assert family["canonical_default_id"] == decision["preferred_variant_id"]
        preferred = {
            variant["variant_id"]: variant
            for variant in family["recommended_variants"]
        }[family["canonical_default_id"]]
        assert preferred["text"] == decision["preferred_text"]
