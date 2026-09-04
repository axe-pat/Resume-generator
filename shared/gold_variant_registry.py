"""Read and validate the small, reviewed resume-variant shipping overlay.

This module is intentionally isolated from the live generator.  The overlay is
the durable record of wording that survived human review in a named gold
fixture; wiring it into selection is a separate, reversible change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from shared.variant_admission import (
    CANONICAL_VARIANT_RULEBOOK,
    FactStatus,
    OutcomeTier,
    ResumeVariant,
    VariantRulebookStatus,
    check_variant_admission,
)


SCHEMA_VERSION = "2026-09-02.1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "resume" / "variants" / "approved_gold_variants.jsonl"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "resume_gold"

SECTION_KINDS = frozenset({"experience", "project", "skills-inline", "community"})
ARCHETYPES = frozenset({"diagnostic", "action", "context", "impact-first"})
OUTCOME_TIERS = {
    OutcomeTier.USER_OR_BUSINESS.value: 1,
    OutcomeTier.OBSERVED_BEHAVIOR.value: 2,
    OutcomeTier.DECISION_OR_ORGANIZATION.value: 3,
    OutcomeTier.QUALITY_OR_EFFICIENCY.value: 4,
    OutcomeTier.THROUGHPUT_OR_INPUT.value: 5,
    OutcomeTier.ARCHITECTURE_OR_BUILD_COUNT.value: 6,
}
PROOF_CLASSES = frozenset({"career-core", "independent-build", "venture", "community"})
ASSEMBLY_MODES = frozenset({"inline", "project-replacement"})
SHIPPING_RECOMMENDATIONS = frozenset({"promote-now", "hold-wording-decision"})


@dataclass(frozen=True)
class ApprovedGoldVariant:
    schema_version: str
    variant_id: str
    story_id: str
    section_kind: str
    company_or_project: str
    text: str
    archetype: str
    value_signals: tuple[str, ...]
    role_tags: tuple[str, ...]
    fact_status: FactStatus
    variant_rulebook_status: VariantRulebookStatus
    variant_rulebook_version: str
    stakes: int
    difficulty: int
    defensibility: int
    distinctiveness: int
    outcome_tier: OutcomeTier
    line_cost: int
    one_argument: bool
    mechanism_supports_claim: bool
    outcome_closes_claim: bool
    outsider_legible: bool
    best_available_outcome: bool
    proof_class: str
    assembly_modes: tuple[str, ...]
    gold_fixture_ids: tuple[str, ...]
    shipping_recommendation: str
    decision_quality: int | None
    human_presence: int | None
    metric_salience: int | None
    eligible_profiles: tuple[str, ...]
    fact_atoms: tuple[str, ...]
    source_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "ApprovedGoldVariant":
        return cls(
            schema_version=str(record.get("schema_version", "")),
            variant_id=str(record.get("variant_id", "")),
            story_id=str(record.get("story_id", "")),
            section_kind=str(record.get("section_kind", "")),
            company_or_project=str(record.get("company_or_project", "")),
            text=str(record.get("text", "")),
            archetype=str(record.get("archetype", "")),
            value_signals=tuple(record.get("value_signals", ())),
            role_tags=tuple(record.get("role_tags", ())),
            fact_status=FactStatus(str(record.get("fact_status", ""))),
            variant_rulebook_status=VariantRulebookStatus(
                str(record.get("variant_rulebook_status", ""))
            ),
            variant_rulebook_version=str(record.get("variant_rulebook_version", "")),
            stakes=record.get("stakes", -1),
            difficulty=record.get("difficulty", -1),
            defensibility=record.get("defensibility", -1),
            distinctiveness=record.get("distinctiveness", -1),
            outcome_tier=OutcomeTier(str(record.get("outcome_tier", ""))),
            line_cost=record.get("line_cost", 0),
            one_argument=record.get("one_argument"),
            mechanism_supports_claim=record.get("mechanism_supports_claim"),
            outcome_closes_claim=record.get("outcome_closes_claim"),
            outsider_legible=record.get("outsider_legible"),
            best_available_outcome=record.get("best_available_outcome"),
            proof_class=str(record.get("proof_class", "")),
            assembly_modes=tuple(record.get("assembly_modes", ())),
            gold_fixture_ids=tuple(record.get("gold_fixture_ids", ())),
            shipping_recommendation=str(record.get("shipping_recommendation", "")),
            decision_quality=record.get("decision_quality"),
            human_presence=record.get("human_presence"),
            metric_salience=record.get("metric_salience"),
            eligible_profiles=tuple(record.get("eligible_profiles", ())),
            fact_atoms=tuple(record.get("fact_atoms", ())),
            source_refs=tuple(record.get("source_refs", ())),
        )

    @property
    def shipping_ready(self) -> bool:
        return self.shipping_recommendation == "promote-now"

    def to_resume_variant(self) -> ResumeVariant:
        """Convert without losing any field owned by the canonical admission gate."""
        return ResumeVariant(
            variant_id=self.variant_id,
            story_id=self.story_id,
            text=self.text,
            value_signals=self.value_signals,
            role_tags=self.role_tags,
            fact_status=self.fact_status,
            variant_rulebook_status=self.variant_rulebook_status,
            variant_rulebook_version=self.variant_rulebook_version,
            stakes=self.stakes,
            difficulty=self.difficulty,
            defensibility=self.defensibility,
            distinctiveness=self.distinctiveness,
            line_cost=self.line_cost,
            outcome_tier=self.outcome_tier,
            one_argument=self.one_argument,
            mechanism_supports_claim=self.mechanism_supports_claim,
            outcome_closes_claim=self.outcome_closes_claim,
            outsider_legible=self.outsider_legible,
            best_available_outcome=self.best_available_outcome,
            decision_quality=self.decision_quality,
            human_presence=self.human_presence,
            metric_salience=self.metric_salience,
            eligible_profiles=self.eligible_profiles,
            fact_atoms=self.fact_atoms,
            source_refs=self.source_refs,
        )


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> tuple[ApprovedGoldVariant, ...]:
    """Load the JSONL overlay without mutating or consulting legacy pools."""
    variants: list[ApprovedGoldVariant] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            variants.append(ApprovedGoldVariant.from_mapping(record))
    return tuple(variants)


def load_gold_fixtures(directory: Path = DEFAULT_FIXTURE_DIR) -> tuple[dict[str, Any], ...]:
    fixtures: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            fixture = json.load(handle)
        fixture["_fixture_path"] = str(path.relative_to(REPO_ROOT))
        fixtures.append(fixture)
    return tuple(fixtures)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _nonempty_strings(values: Iterable[Any]) -> bool:
    values = tuple(values)
    return bool(values) and all(isinstance(value, str) and value.strip() for value in values)


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def validate_registry(
    variants: Iterable[ApprovedGoldVariant],
    *,
    known_fixture_ids: Iterable[str] = (),
) -> list[str]:
    variants = tuple(variants)
    known_fixture_ids = set(known_fixture_ids)
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_text: dict[str, str] = {}

    for variant in variants:
        prefix = variant.variant_id or "<missing-variant-id>"
        if variant.schema_version != SCHEMA_VERSION:
            errors.append(f"{prefix}: schema_version must be {SCHEMA_VERSION}")
        if not variant.variant_id.strip():
            errors.append(f"{prefix}: variant_id is required")
        elif variant.variant_id in seen_ids:
            errors.append(f"{prefix}: duplicate variant_id")
        seen_ids.add(variant.variant_id)

        if not variant.story_id.strip():
            errors.append(f"{prefix}: story_id is required")
        if not variant.company_or_project.strip():
            errors.append(f"{prefix}: company_or_project is required")
        if not variant.text.strip():
            errors.append(f"{prefix}: text is required")
        elif variant.text in seen_text:
            errors.append(
                f"{prefix}: duplicate exact text already owned by {seen_text[variant.text]}"
            )
        else:
            seen_text[variant.text] = variant.variant_id

        if variant.section_kind not in SECTION_KINDS:
            errors.append(f"{prefix}: unknown section_kind {variant.section_kind!r}")
        if variant.archetype not in ARCHETYPES:
            errors.append(f"{prefix}: unknown archetype {variant.archetype!r}")
        if variant.proof_class not in PROOF_CLASSES:
            errors.append(f"{prefix}: unknown proof_class {variant.proof_class!r}")
        if not _nonempty_strings(variant.value_signals):
            errors.append(f"{prefix}: value_signals must contain non-empty strings")
        if not _nonempty_strings(variant.role_tags):
            errors.append(f"{prefix}: role_tags must contain non-empty strings")
        if not _nonempty_strings(variant.source_refs):
            errors.append(f"{prefix}: source_refs must contain non-empty strings")
        if not _nonempty_strings(variant.gold_fixture_ids):
            errors.append(f"{prefix}: gold_fixture_ids must contain non-empty strings")
        if variant.shipping_recommendation not in SHIPPING_RECOMMENDATIONS:
            errors.append(
                f"{prefix}: unknown shipping_recommendation "
                f"{variant.shipping_recommendation!r}"
            )
        if not _nonempty_strings(variant.eligible_profiles):
            errors.append(f"{prefix}: eligible_profiles must contain non-empty strings")
        if not _nonempty_strings(variant.fact_atoms):
            errors.append(f"{prefix}: fact_atoms must contain non-empty strings")

        admission = check_variant_admission(variant.to_resume_variant())
        errors.extend(f"{prefix}: admission: {error}" for error in admission.errors)
        if variant.variant_rulebook_version != CANONICAL_VARIANT_RULEBOOK:
            errors.append(
                f"{prefix}: overlay requires canonical rulebook {CANONICAL_VARIANT_RULEBOOK}"
            )

        unknown_modes = sorted(set(variant.assembly_modes) - ASSEMBLY_MODES)
        if unknown_modes:
            errors.append(f"{prefix}: unknown assembly_modes {unknown_modes}")
        if not variant.assembly_modes:
            errors.append(f"{prefix}: at least one assembly_mode is required")
        if variant.section_kind == "project" and variant.assembly_modes != (
            "project-replacement",
        ):
            errors.append(
                f"{prefix}: project evidence is admitted only in project-replacement mode"
            )
        if variant.section_kind == "skills-inline" and variant.assembly_modes != ("inline",):
            errors.append(f"{prefix}: skills-inline evidence is admitted only in inline mode")

        if known_fixture_ids:
            unknown = sorted(set(variant.gold_fixture_ids) - known_fixture_ids)
            if unknown:
                errors.append(f"{prefix}: unknown gold_fixture_ids {unknown}")

    return errors


def _variant_ids_from_fixture(fixture: Mapping[str, Any]) -> list[str]:
    variant_ids: list[str] = []
    for block in fixture.get("experience", ()):
        variant_ids.extend(block.get("bullet_variant_ids", ()))
    for block in fixture.get("projects", ()):
        variant_ids.extend(block.get("bullet_variant_ids", ()))
    variant_ids.extend(fixture.get("inline_proof_variant_ids", ()))
    variant_ids.extend(fixture.get("community_variant_ids", ()))
    return variant_ids


def validate_gold_fixtures(
    fixtures: Iterable[Mapping[str, Any]],
    variants: Iterable[ApprovedGoldVariant],
) -> list[str]:
    fixtures = tuple(fixtures)
    variants = tuple(variants)
    by_id = {variant.variant_id: variant for variant in variants}
    errors: list[str] = []
    seen_fixture_ids: set[str] = set()
    referenced_ids: set[str] = set()

    for fixture in fixtures:
        fixture_id = str(fixture.get("fixture_id", ""))
        prefix = fixture_id or str(fixture.get("_fixture_path", "<missing-fixture-id>"))
        if fixture.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{prefix}: schema_version must be {SCHEMA_VERSION}")
        if not fixture_id:
            errors.append(f"{prefix}: fixture_id is required")
        elif fixture_id in seen_fixture_ids:
            errors.append(f"{prefix}: duplicate fixture_id")
        seen_fixture_ids.add(fixture_id)

        source = fixture.get("source_artifact", {})
        if source.get("extracted_from") != "docx":
            errors.append(f"{prefix}: source_artifact.extracted_from must be docx")
        if not str(source.get("path", "")).endswith(".docx"):
            errors.append(f"{prefix}: source_artifact.path must identify a DOCX")
        source_hash = str(source.get("sha256", ""))
        if not _is_sha256(source_hash):
            errors.append(f"{prefix}: source_artifact.sha256 must be lowercase SHA-256")

        layout = fixture.get("layout_reference", {})
        if not str(layout.get("path", "")).endswith(".pdf"):
            errors.append(f"{prefix}: layout_reference.path must identify a PDF")
        if not _is_sha256(layout.get("sha256", "")):
            errors.append(f"{prefix}: layout_reference.sha256 must be lowercase SHA-256")
        if layout.get("approved_page_count") != 1:
            errors.append(f"{prefix}: approved layout reference must be exactly one page")
        if not isinstance(layout.get("bundled_libreoffice_docx_page_count"), int):
            errors.append(
                f"{prefix}: bundled_libreoffice_docx_page_count must be an integer"
            )
        rendered_text_fixture = str(layout.get("rendered_text_fixture", ""))
        if not rendered_text_fixture.endswith("_pdftotext.txt"):
            errors.append(
                f"{prefix}: layout_reference.rendered_text_fixture must identify frozen PDF text"
            )
        elif not (REPO_ROOT / rendered_text_fixture).is_file():
            errors.append(f"{prefix}: rendered text fixture does not exist")
        else:
            actual_text_hash = hashlib.sha256(
                (REPO_ROOT / rendered_text_fixture).read_bytes()
            ).hexdigest()
            if layout.get("rendered_text_sha256") != actual_text_hash:
                errors.append(f"{prefix}: rendered_text_sha256 does not match frozen PDF text")

        expected_lint = fixture.get("expected_lint", {}).get("approved_pdf", {})
        for severity in ("blockers", "warnings"):
            codes = expected_lint.get(severity)
            if not isinstance(codes, list) or any(
                not isinstance(code, str) or not code for code in codes
            ):
                errors.append(
                    f"{prefix}: expected_lint.approved_pdf.{severity} must be a list of codes"
                )
            elif len(codes) != len(set(codes)):
                errors.append(
                    f"{prefix}: expected_lint.approved_pdf.{severity} repeats a code"
                )

        if not str(fixture.get("identity_heading", "")).strip():
            errors.append(f"{prefix}: identity_heading is required")
        if not str(fixture.get("summary_text", "")).strip():
            errors.append(f"{prefix}: summary_text is required")
        if fixture.get("summary_sha256") != sha256_text(str(fixture.get("summary_text", ""))):
            errors.append(f"{prefix}: summary_sha256 does not match summary_text")

        expected = fixture.get("expected_counts", {})
        actual_experience = sum(
            len(block.get("bullet_variant_ids", ()))
            for block in fixture.get("experience", ())
        )
        actual_projects = sum(
            len(block.get("bullet_variant_ids", ()))
            for block in fixture.get("projects", ())
        )
        actual_inline = len(fixture.get("inline_proof_variant_ids", ()))
        actual_community = len(fixture.get("community_variant_ids", ()))
        actual_counts = {
            "experience_bullets": actual_experience,
            "project_bullets": actual_projects,
            "inline_proof_bullets": actual_inline,
            "community_proof_bullets": actual_community,
        }
        for key, actual in actual_counts.items():
            if expected.get(key) != actual:
                errors.append(
                    f"{prefix}: expected_counts.{key}={expected.get(key)!r}, actual={actual}"
                )

        actual_allocation = {
            str(block.get("company", "")): len(block.get("bullet_variant_ids", ()))
            for block in fixture.get("experience", ())
        }
        if fixture.get("expected_company_allocation") != actual_allocation:
            errors.append(
                f"{prefix}: expected_company_allocation does not match Experience blocks"
            )

        supporting_proof = fixture.get("supporting_proof", {})
        if supporting_proof.get("project_bullet_count") != actual_projects:
            errors.append(
                f"{prefix}: supporting_proof.project_bullet_count must equal project bullets"
            )

        fixture_variant_ids = _variant_ids_from_fixture(fixture)
        if len(fixture_variant_ids) != len(set(fixture_variant_ids)):
            errors.append(f"{prefix}: a variant_id is repeated within the fixture")
        for variant_id in fixture_variant_ids:
            variant = by_id.get(variant_id)
            if variant is None:
                errors.append(f"{prefix}: unknown variant_id {variant_id}")
                continue
            referenced_ids.add(variant_id)
            if fixture_id not in variant.gold_fixture_ids:
                errors.append(
                    f"{prefix}: {variant_id} does not list this fixture in gold_fixture_ids"
                )

        for block in fixture.get("experience", ()):
            company = block.get("company")
            for variant_id in block.get("bullet_variant_ids", ()):
                variant = by_id.get(variant_id)
                if variant and variant.section_kind != "experience":
                    errors.append(f"{prefix}: {variant_id} is not experience evidence")
                if variant and variant.company_or_project != company:
                    errors.append(
                        f"{prefix}: {variant_id} belongs to {variant.company_or_project}, not {company}"
                    )
        for block in fixture.get("projects", ()):
            project = block.get("project")
            for variant_id in block.get("bullet_variant_ids", ()):
                variant = by_id.get(variant_id)
                if variant and variant.section_kind != "project":
                    errors.append(f"{prefix}: {variant_id} is not project evidence")
                if variant and variant.company_or_project != project:
                    errors.append(
                        f"{prefix}: {variant_id} belongs to {variant.company_or_project}, not {project}"
                    )

        skill_variant_ids = {
            str(row["variant_id"])
            for row in fixture.get("skills_rows", ())
            if row.get("variant_id")
        }
        expected_skill_variant_ids = set(fixture.get("inline_proof_variant_ids", ())) | set(
            fixture.get("community_variant_ids", ())
        )
        if skill_variant_ids != expected_skill_variant_ids:
            errors.append(
                f"{prefix}: Skills proof rows must exactly match inline/community variant ids"
            )

        mode = fixture.get("supporting_proof", {}).get("mode")
        if mode not in ASSEMBLY_MODES:
            errors.append(f"{prefix}: unknown supporting_proof.mode {mode!r}")
        for variant_id in fixture_variant_ids:
            variant = by_id.get(variant_id)
            if variant and mode not in variant.assembly_modes:
                errors.append(f"{prefix}: {variant_id} is not admitted for {mode} mode")

    unreferenced = sorted(set(by_id) - referenced_ids)
    if unreferenced:
        errors.append(f"registry contains variants outside the two gold fixtures: {unreferenced}")
    return errors
