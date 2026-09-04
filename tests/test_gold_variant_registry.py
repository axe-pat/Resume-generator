import hashlib
import json
import zipfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

import pytest

from shared.gold_variant_registry import (
    ASSEMBLY_MODES,
    DEFAULT_REGISTRY_PATH,
    OUTCOME_TIERS,
    REPO_ROOT,
    SHIPPING_RECOMMENDATIONS,
    load_gold_fixtures,
    load_registry,
    validate_gold_fixtures,
    validate_registry,
)
from shared.resume_lint import (
    RELEASE_POLICY,
    AssembledResume,
    ExperienceBlock,
    ExperienceBullet,
    LintSeverity,
    ProjectBlock,
    SkillRow,
    issue_codes,
    lint_assembled_resume,
)
from shared.resume_profiles import (
    BulletBudgetDecision,
    ExperienceAllocationPlan,
    PageProofPlan,
    SupportingProofMode,
    SupportingProofReason,
)
from shared.variant_admission import OutcomeTier, check_variant_admission


EXPECTED_FIXTURE_IDS = {
    "amazon-product-operator-2026-08-27",
    "studyfetch-builder-discovery-2026-09-01",
}


def _fixture_variant_ids(fixture):
    ids = []
    for block in fixture["experience"]:
        ids.extend(block["bullet_variant_ids"])
    for block in fixture["projects"]:
        ids.extend(block["bullet_variant_ids"])
    ids.extend(fixture["inline_proof_variant_ids"])
    ids.extend(fixture["community_variant_ids"])
    return ids


def _docx_text(path: Path) -> str:
    """Extract paragraph text with standard-library OOXML only."""
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _assembled_resume_from_fixture(fixture, variants, *, page_count=None):
    """Rebuild the post-selection page contract from frozen gold metadata."""
    profile_id = fixture["profile_id"]
    counts = tuple(
        (block["company"].upper(), len(block["bullet_variant_ids"]))
        for block in fixture["experience"]
    )
    proof = fixture["supporting_proof"]
    proof_mode = SupportingProofMode(proof["mode"])
    budget_decision = (
        BulletBudgetDecision.COMPACT_FOR_QUALITY
        if proof_mode is SupportingProofMode.PROJECT_REPLACEMENT
        else BulletBudgetDecision.DEFAULT
    )
    allocation = ExperienceAllocationPlan(profile_id, counts, budget_decision)
    proof_plan = PageProofPlan(
        profile_id=profile_id,
        experience_plan=allocation,
        mode=proof_mode,
        reason=SupportingProofReason(proof["reason"]),
        project_bullet_count=proof["project_bullet_count"],
        replaced_experience_count=proof["replaced_experience_count"],
    )

    def selected(variant_id):
        variant = variants[variant_id]
        return ExperienceBullet(
            text=variant.text,
            archetype=variant.archetype,
            variant_id=variant.variant_id,
            story_id=variant.story_id,
        )

    experience_blocks = tuple(
        ExperienceBlock(
            company=block["company"].upper(),
            title=block["title"],
            date_text=block["date"],
            bullets=tuple(selected(variant_id) for variant_id in block["bullet_variant_ids"]),
        )
        for block in fixture["experience"]
    )
    project_blocks = tuple(
        ProjectBlock(
            name=block["project"],
            descriptor=block["descriptor"],
            bullets=tuple(selected(variant_id) for variant_id in block["bullet_variant_ids"]),
        )
        for block in fixture["projects"]
    )
    skill_rows = tuple(
        SkillRow(
            label=row["label"],
            text=(variants[row["variant_id"]].text if "variant_id" in row else row["text"]),
        )
        for row in fixture["skills_rows"]
    )
    rendered_text_path = REPO_ROOT / fixture["layout_reference"]["rendered_text_fixture"]
    rendered_text = rendered_text_path.read_text(encoding="utf-8")
    if page_count is None:
        page_count = fixture["layout_reference"]["approved_page_count"]

    return AssembledResume(
        profile_id=profile_id,
        identity_heading=fixture["identity_heading"],
        summary_text=fixture["summary_text"],
        experience_blocks=experience_blocks,
        skills_heading=fixture["skills_heading"],
        skill_rows=skill_rows,
        allocation_plan=allocation,
        proof_plan=proof_plan,
        project_blocks=project_blocks,
        fluo_included=bool(
            fixture["inline_proof_variant_ids"]
            or any(block["project"] == "Fluo" for block in fixture["projects"])
        ),
        fluo_story_family=(
            "gtm-partnership"
            if fixture["fixture_id"] == "amazon-product-operator-2026-08-27"
            else "customer-insight"
        ),
        rendered_page_count=page_count,
        rendered_text=rendered_text,
    )


POST_SELECTION_RELEASE_POLICY = replace(
    RELEASE_POLICY,
    require_raw_section_integrity=False,
)


def test_gold_registry_and_fixtures_are_internally_valid():
    variants = load_registry()
    fixtures = load_gold_fixtures()
    fixture_ids = {fixture["fixture_id"] for fixture in fixtures}

    assert fixture_ids == EXPECTED_FIXTURE_IDS
    assert len(variants) == 22
    assert validate_registry(variants, known_fixture_ids=fixture_ids) == []
    assert validate_gold_fixtures(fixtures, variants) == []


def test_registry_uses_the_canonical_variant_admission_outcome_vocabulary():
    assert set(OUTCOME_TIERS) == {tier.value for tier in OutcomeTier}


def test_only_the_explicit_amazon_latency_sibling_is_held_from_shipping():
    variants = load_registry()
    assert SHIPPING_RECOMMENDATIONS == {"promote-now", "hold-wording-decision"}
    assert {variant.variant_id for variant in variants if not variant.shipping_ready} == {
        "G-LATENCY-amazon-accuracy-tradeoff"
    }
    assert sum(variant.shipping_ready for variant in variants) == 21


def test_every_gold_variant_passes_the_five_content_quality_gates():
    for variant in load_registry():
        assert variant.one_argument is True
        assert variant.mechanism_supports_claim is True
        assert variant.outcome_closes_claim is True
        assert variant.outsider_legible is True
        assert variant.best_available_outcome is True


def test_every_gold_record_losslessly_converts_and_passes_canonical_admission():
    for variant in load_registry():
        canonical = variant.to_resume_variant()
        assert canonical.variant_id == variant.variant_id
        assert canonical.story_id == variant.story_id
        assert canonical.text == variant.text
        assert canonical.value_signals == variant.value_signals
        assert canonical.role_tags == variant.role_tags
        assert canonical.outcome_tier is variant.outcome_tier
        assert canonical.eligible_profiles == variant.eligible_profiles
        assert canonical.fact_atoms == variant.fact_atoms
        assert canonical.source_refs == variant.source_refs
        assert check_variant_admission(canonical).admitted


def test_registry_is_only_the_union_of_the_two_gold_fixtures():
    variants = load_registry()
    fixtures = load_gold_fixtures()
    referenced = {
        variant_id
        for fixture in fixtures
        for variant_id in _fixture_variant_ids(fixture)
    }
    assert referenced == {variant.variant_id for variant in variants}
    assert all(set(variant.gold_fixture_ids) <= EXPECTED_FIXTURE_IDS for variant in variants)


def test_studyfetch_fixture_preserves_eight_experience_plus_three_project_bullets():
    fixture = next(
        item
        for item in load_gold_fixtures()
        if item["fixture_id"] == "studyfetch-builder-discovery-2026-09-01"
    )
    assert fixture["supporting_proof"] == {
        "mode": "project-replacement",
        "reason": "top-criterion-evidence",
        "project_bullet_count": 3,
        "replaced_experience_count": 2,
    }
    assert sum(len(block["bullet_variant_ids"]) for block in fixture["experience"]) == 8
    assert sum(len(block["bullet_variant_ids"]) for block in fixture["projects"]) == 3
    assert fixture["expected_company_allocation"] == {
        "FlairX AI": 2,
        "Gojek": 2,
        "Hevo Data": 2,
        "Intuit": 1,
        "Optum": 1,
    }


def test_studyfetch_fixture_captures_the_actual_v4_winning_text():
    variants = {variant.variant_id: variant for variant in load_registry()}
    fixture = next(
        item
        for item in load_gold_fixtures()
        if item["fixture_id"] == "studyfetch-builder-discovery-2026-09-01"
    )
    assert fixture["source_artifact"]["path"].endswith(
        "Akshat_Pathak_StudyFetch_Resume_2026-09-01_v4.docx"
    )
    assert "discovers and scores roles, researches employers" not in fixture["summary_text"]
    assert fixture["summary_text"].endswith(
        "the next application or conversation worth pursuing."
    )
    assert variants["RDE-OUTCOME-studyfetch-end-to-end-results"].text.endswith(
        "yielding 300+ accepted connections and 100+ replies."
    )
    assert "student-housing move-in near USC" in variants[
        "FL-FIELD-VALIDATION-studyfetch-closed-loop"
    ].text
    assert "Lorenzo" not in variants["FL-FIELD-VALIDATION-studyfetch-closed-loop"].text


def test_amazon_fixture_preserves_the_reviewed_two_three_two_two_one_shape():
    fixture = next(
        item
        for item in load_gold_fixtures()
        if item["fixture_id"] == "amazon-product-operator-2026-08-27"
    )
    assert fixture["supporting_proof"]["mode"] == "inline"
    assert fixture["expected_company_allocation"] == {
        "FlairX AI": 2,
        "Gojek": 3,
        "Hevo Data": 2,
        "Intuit": 2,
        "Optum": 1,
    }
    assert sum(len(block["bullet_variant_ids"]) for block in fixture["experience"]) == 10
    assert fixture["projects"] == []
    assert fixture["inline_proof_variant_ids"] == [
        "FL-INSTITUTIONAL-amazon-inline-prearrival"
    ]


def test_supporting_proof_placement_is_explicit_and_bounded():
    variants = load_registry()
    assert all(set(variant.assembly_modes) <= ASSEMBLY_MODES for variant in variants)
    assert all(
        variant.assembly_modes == ("project-replacement",)
        for variant in variants
        if variant.section_kind == "project"
    )
    assert all(
        variant.assembly_modes == ("inline",)
        for variant in variants
        if variant.section_kind == "skills-inline"
    )


@pytest.mark.parametrize("fixture", load_gold_fixtures(), ids=lambda item: item["fixture_id"])
def test_current_source_docx_matches_the_frozen_fixture_when_available(fixture):
    source_path = REPO_ROOT / fixture["source_artifact"]["path"]
    if not source_path.exists():
        pytest.skip("source artifact moved after the fixture was frozen")

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == fixture["source_artifact"][
        "sha256"
    ]
    extracted = _docx_text(source_path)
    assert fixture["summary_text"] in extracted
    for row in fixture["skills_rows"]:
        if row.get("text"):
            assert row["text"] in extracted

    variants = {variant.variant_id: variant for variant in load_registry()}
    for variant_id in _fixture_variant_ids(fixture):
        assert variants[variant_id].text in extracted


def test_registry_file_is_valid_one_record_per_line_jsonl():
    records = []
    for raw_line in DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        if raw_line.strip():
            records.append(json.loads(raw_line))
    assert len(records) == 22
    assert all(record["schema_version"] == "2026-09-02.1" for record in records)


def test_registry_validator_rejects_a_failed_content_quality_gate():
    variants = list(load_registry())
    variants[0] = replace(variants[0], outcome_closes_claim=False)
    errors = validate_registry(variants, known_fixture_ids=EXPECTED_FIXTURE_IDS)
    assert any("outcome_closes_claim must be explicitly approved" in error for error in errors)


def test_registry_validator_rejects_duplicate_gold_wording():
    variants = list(load_registry())
    variants[1] = replace(variants[1], text=variants[0].text)
    errors = validate_registry(variants, known_fixture_ids=EXPECTED_FIXTURE_IDS)
    assert any("duplicate exact text" in error for error in errors)


def test_fixture_validator_rejects_shape_drift():
    variants = load_registry()
    fixtures = [deepcopy(fixture) for fixture in load_gold_fixtures()]
    studyfetch = next(
        fixture
        for fixture in fixtures
        if fixture["fixture_id"] == "studyfetch-builder-discovery-2026-09-01"
    )
    studyfetch["expected_counts"]["experience_bullets"] = 9
    errors = validate_gold_fixtures(fixtures, variants)
    assert any("experience_bullets=9, actual=8" in error for error in errors)


@pytest.mark.parametrize("fixture", load_gold_fixtures(), ids=lambda item: item["fixture_id"])
def test_gold_fixture_reconstructs_to_its_explicit_approved_pdf_lint_contract(fixture):
    variants = {variant.variant_id: variant for variant in load_registry()}
    document = _assembled_resume_from_fixture(fixture, variants)
    report = lint_assembled_resume(document, POST_SELECTION_RELEASE_POLICY)
    expected = fixture["expected_lint"]["approved_pdf"]

    assert issue_codes(report, LintSeverity.BLOCKER) == set(expected["blockers"])
    assert issue_codes(report, LintSeverity.WARNING) == set(expected["warnings"])
    assert report.release_ready is (not expected["blockers"])


def test_amazon_fixture_records_the_libreoffice_two_page_portability_failure():
    fixture = next(
        item
        for item in load_gold_fixtures()
        if item["fixture_id"] == "amazon-product-operator-2026-08-27"
    )
    variants = {variant.variant_id: variant for variant in load_registry()}
    document = _assembled_resume_from_fixture(
        fixture,
        variants,
        page_count=fixture["layout_reference"]["bundled_libreoffice_docx_page_count"],
    )
    report = lint_assembled_resume(document, POST_SELECTION_RELEASE_POLICY)
    expected = fixture["expected_lint"]["bundled_libreoffice_portability_probe"]

    assert issue_codes(report, LintSeverity.BLOCKER) == set(expected["blockers"])
    assert issue_codes(report, LintSeverity.WARNING) == set(expected["warnings"])
    assert not report.release_ready


@pytest.mark.parametrize("fixture", load_gold_fixtures(), ids=lambda item: item["fixture_id"])
def test_frozen_pdf_text_matches_its_documented_hash(fixture):
    text_path = REPO_ROOT / fixture["layout_reference"]["rendered_text_fixture"]
    assert text_path.is_file()
    assert hashlib.sha256(text_path.read_bytes()).hexdigest() == fixture["layout_reference"][
        "rendered_text_sha256"
    ]
