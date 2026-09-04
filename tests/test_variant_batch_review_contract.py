"""Cross-batch non-regression contract for the inert variant-bank reviews.

The batch files are review artifacts, not live selector inputs.  These tests keep
that boundary explicit while proving that the causal audit did not omit or
double-count anything in the live prompt inventory.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from resume.variants import challenger_runner
from shared import prompt_variant_inventory
from shared.gold_variant_registry import ARCHETYPES, ASSEMBLY_MODES, load_registry
from shared.resume_profiles import PROFILE_REGISTRY


BATCH_DIR = (
    challenger_runner.REPO_ROOT
    / "docs"
    / "resume_generator_reviews"
    / "variant_batches"
)
CAUSAL_BATCH_PATHS = {
    "A": BATCH_DIR / "BATCH_A_FLAIRX_FLUO_PROJECTS.json",
    "B": BATCH_DIR / "BATCH_B_GOJEK_HEVO_BATCH.json",
    "C": BATCH_DIR / "BATCH_C_HEVO_INTUIT_OPTUM.json",
}
SUMMARY_SKILLS_BATCH_PATH = BATCH_DIR / "BATCH_D_SUMMARIES_SKILLS.json"

KEEPING_VERDICTS = frozenset({"retain", "retain_exact", "replace"})
MAX_RECOMMENDED_VARIANTS_PER_FAMILY = 4
FLUO_STORY_FAMILIES = frozenset(
    story_family
    for profile in PROFILE_REGISTRY.values()
    for story_family in profile.fluo.allowed_story_families
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _causal_batches() -> dict[str, dict]:
    return {name: _load_json(path) for name, path in CAUSAL_BATCH_PATHS.items()}


def _live_causal_records():
    grouped = challenger_runner.group_causal_stories(
        challenger_runner.load_inventory()
    )
    return {
        record.stable_id: (family, record.text)
        for family, records in grouped.items()
        for record in records
    }


def _source_text_by_id() -> dict[str, str]:
    live = {
        record.stable_id: record.text
        for record in challenger_runner.load_inventory()
    }
    gold = {variant.variant_id: variant.text for variant in load_registry()}
    overlap = set(live) & set(gold)
    assert not overlap, f"live and gold IDs unexpectedly overlap: {sorted(overlap)}"
    return live | gold


def _normalized_replacement_target(decision: dict) -> str | None:
    replacement = decision.get("replacement_id") or None
    if replacement is not None:
        return replacement
    if decision["verdict"] in {"retain", "retain_exact"}:
        return decision["stable_id"]
    return None


def test_batches_a_b_c_cover_every_live_causal_variant_once_in_its_family():
    expected = _live_causal_records()
    occurrences: list[tuple[str, str, str]] = []

    for batch_name, batch in _causal_batches().items():
        for family_name, family in batch["families"].items():
            for incumbent in family["incumbents"]:
                stable_id = incumbent["stable_id"]
                if stable_id in expected:
                    occurrences.append((stable_id, family_name, batch_name))

    counts = Counter(stable_id for stable_id, _, _ in occurrences)
    missing = sorted(set(expected) - set(counts))
    duplicated = sorted(
        stable_id for stable_id, count in counts.items() if count != 1
    )
    misplaced = sorted(
        (stable_id, actual_family, expected[stable_id][0])
        for stable_id, actual_family, _ in occurrences
        if actual_family != expected[stable_id][0]
    )

    assert len(expected) == 135
    assert not missing, f"live causal variants missing from A+B+C: {missing}"
    assert not duplicated, f"live causal variants reviewed more than once: {duplicated}"
    assert not misplaced, f"variants filed under the wrong semantic family: {misplaced}"


def test_batches_a_b_c_do_not_duplicate_any_reviewed_incumbent_id():
    reviewed = [
        (incumbent["stable_id"], batch_name, family_name)
        for batch_name, batch in _causal_batches().items()
        for family_name, family in batch["families"].items()
        for incumbent in family["incumbents"]
    ]
    counts = Counter(stable_id for stable_id, _, _ in reviewed)
    duplicates = sorted(
        stable_id for stable_id, count in counts.items() if count > 1
    )

    # The 135 live variants plus 11 separately reviewed gold/canonical records.
    assert len(reviewed) == 146
    assert not duplicates, f"duplicate incumbent decisions across batches: {duplicates}"


def test_retain_and_replace_targets_resolve_without_silent_rewording():
    source_text = _source_text_by_id()

    for batch_name, batch in _causal_batches().items():
        for family_name, family in batch["families"].items():
            recommended = {
                variant["variant_id"]: variant
                for variant in family["recommended_variants"]
            }
            assert len(recommended) == len(family["recommended_variants"]), (
                f"Batch {batch_name} {family_name} repeats a recommended variant ID"
            )

            for variant_id, variant in recommended.items():
                text = variant.get("text", "").strip()
                assert text, (
                    f"Batch {batch_name} {family_name} {variant_id} has no explicit text"
                )
                if variant_id in source_text:
                    assert text == source_text[variant_id], (
                        f"Batch {batch_name} {family_name} silently rewrites source "
                        f"variant {variant_id}; use a new challenger ID instead"
                    )

            for decision in family["incumbents"]:
                if decision["verdict"] not in KEEPING_VERDICTS:
                    continue
                target = _normalized_replacement_target(decision)
                assert target in recommended, (
                    f"Batch {batch_name} {family_name} decision for "
                    f"{decision['stable_id']} does not resolve to its recommended slate: "
                    f"{target!r}"
                )


def test_recommended_slates_are_bounded_and_use_case_labeled():
    missing_use_cases: list[str] = []

    for batch_name, batch in _causal_batches().items():
        for family_name, family in batch["families"].items():
            slate = family["recommended_variants"]
            assert len(slate) <= MAX_RECOMMENDED_VARIANTS_PER_FAMILY, (
                f"Batch {batch_name} {family_name} has {len(slate)} variants; "
                f"maximum is {MAX_RECOMMENDED_VARIANTS_PER_FAMILY}"
            )
            for variant in slate:
                if not str(variant.get("use_case", "")).strip():
                    missing_use_cases.append(
                        f"{batch_name}/{family_name}/{variant['variant_id']}"
                    )

    assert not missing_use_cases, (
        "recommended variants need role/use-case labels, not universal ranking: "
        + ", ".join(missing_use_cases)
    )


def test_every_recommendation_has_controlled_assembly_metadata():
    missing_or_invalid_archetypes: list[str] = []
    invalid_fluo_metadata: list[str] = []

    for batch_name, batch in _causal_batches().items():
        for family_name, family in batch["families"].items():
            for variant in family["recommended_variants"]:
                label = f"{batch_name}/{family_name}/{variant['variant_id']}"
                if variant.get("archetype") not in ARCHETYPES:
                    missing_or_invalid_archetypes.append(label)
                if family_name != "FLUO":
                    continue

                line_cost = variant.get("line_cost")
                modes = variant.get("assembly_modes")
                if (
                    variant.get("fluo_story_family") not in FLUO_STORY_FAMILIES
                    or not isinstance(line_cost, int)
                    or line_cost < 1
                    or not isinstance(modes, list)
                    or not modes
                    or set(modes) - ASSEMBLY_MODES
                    or ("inline" in modes and line_cost > 2)
                ):
                    invalid_fluo_metadata.append(label)

    assert not missing_or_invalid_archetypes, (
        "recommended variants require a controlled archetype: "
        + ", ".join(missing_or_invalid_archetypes)
    )
    assert not invalid_fluo_metadata, (
        "Fluo recommendations require profile-funded story family, line cost, and "
        "assembly mode metadata: "
        + ", ".join(invalid_fluo_metadata)
    )


def test_all_review_batches_remain_inert_and_unwired():
    for batch_name, batch in _causal_batches().items():
        wiring_flag = batch.get(
            "live_wiring", batch.get("live_prompts_modified")
        )
        assert wiring_flag is False, f"Batch {batch_name} is no longer inert"
        assert str(batch.get("mode", batch.get("status", ""))).replace(
            "_", "-"
        ) == "review-only"

    batch_d = _load_json(SUMMARY_SKILLS_BATCH_PATH)
    assert batch_d["live_wiring"] is False
    assert batch_d["mode"] == "review-only"


def test_batch_d_covers_current_summary_and_skill_surfaces_once():
    batch = _load_json(SUMMARY_SKILLS_BATCH_PATH)
    records = prompt_variant_inventory.extract_prompt_inventory()

    expected = {
        record.stable_id: record.selectability
        for record in records
        if record.story in {"SUMMARY", "SKILLS-ANALYTICS", "SKILLS-COMMUNITY"}
        and record.selectability
        in {
            prompt_variant_inventory.SELECTABLE,
            prompt_variant_inventory.REFERENCE_ONLY,
        }
    }

    reviewed = batch["prompt_incumbents"]
    reviewed_ids = [row["stable_id"] for row in reviewed]

    assert len(expected) == 22
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 22
    assert set(reviewed_ids) == set(expected)
    assert {
        row["stable_id"]: row["selectability"] for row in reviewed
    } == expected


def test_batch_d_replacement_ids_resolve_to_explicit_candidates():
    batch = _load_json(SUMMARY_SKILLS_BATCH_PATH)
    candidates = batch["summary_candidates"] + batch["community_candidates"]
    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}

    assert len(candidate_ids) == len(set(candidate_ids))
    for candidate in candidates:
        assert str(candidate.get("text", "")).strip(), (
            f"Batch D candidate {candidate['candidate_id']} has no explicit text"
        )
        assert str(candidate.get("use_case", "")).strip(), (
            f"Batch D candidate {candidate['candidate_id']} has no use-case label"
        )

    unresolved = sorted(
        replacement_id
        for incumbent in batch["prompt_incumbents"]
        for replacement_id in incumbent["replacement_ids"]
        if replacement_id not in by_id
    )
    assert not unresolved, f"Batch D has unresolved replacement IDs: {unresolved}"

    replacement_verdicts = {
        "supersede_reference",
        "challenger_review",
        "replace_split_argument",
    }
    for incumbent in batch["prompt_incumbents"]:
        if incumbent["verdict"] in replacement_verdicts:
            assert incumbent["replacement_ids"], (
                f"Batch D {incumbent['stable_id']} promises a replacement but "
                "does not name one"
            )
        elif incumbent["verdict"] == "retain_exact":
            assert incumbent["replacement_ids"] == []
        else:
            raise AssertionError(
                f"Batch D {incumbent['stable_id']} has unknown verdict "
                f"{incumbent['verdict']!r}"
            )
