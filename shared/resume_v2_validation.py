"""Validate and assemble one v2 Pass-1 response without rewriting its bullets.

The v2 selector may choose only from the completed A/B/C review bank.  This
module turns that promise into a release gate: every Experience bullet must be
an exact reviewed string, must belong to the employer block that owns its story,
and may appear only once.  Summary, allocation, skills shape, protected-story,
and Fluo decisions are checked against the resolved profile before the normal
page-level linter runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from shared.resume_lint import (
    ArchetypeContract,
    AssembledResume,
    ExperienceBlock,
    ExperienceBullet,
    SkillRow,
)
from shared.resume_profiles import FluoPlacement, ProfileFamily, skills_section_heading
from shared.resume_v2_prompt import (
    Pass1PromptOverride,
    ReviewedBullet,
    ReviewedSummary,
    company_headers_for_profile,
    skill_value_candidates_for_profile,
)


_BULLET_RE = re.compile(r"^[\u2022\u25cf\-\*●•]\s+(.+?)\s*$")
_COMPANY_FOR_PREFIX = {
    "F-": "FLAIRX AI",
    "G-": "GOJEK",
    "H-": "HEVO DATA",
    "I-": "INTUIT",
    "O-": "OPTUM",
}


@dataclass(frozen=True)
class SelectedExperienceVariant:
    company: str
    index: int
    reviewed: ReviewedBullet
    archetype: str


@dataclass(frozen=True)
class V2SectionValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    selected: tuple[SelectedExperienceVariant, ...]
    summary: ReviewedSummary | None
    fluo_variant: ReviewedBullet | None
    document: AssembledResume | None

    @property
    def passed(self) -> bool:
        return not self.errors and self.document is not None


def _company_for_story(story_family: str) -> str | None:
    for prefix, company in _COMPANY_FOR_PREFIX.items():
        if story_family.startswith(prefix):
            return company
    return None


def _parse_experience(
    text: str,
    override: Pass1PromptOverride,
) -> tuple[list[tuple[str, str, str, list[str]]], list[str]]:
    headers = company_headers_for_profile(override.profile)
    header_to_company = {value: key for key, value in headers.items()}
    parsed: list[tuple[str, str, str, list[str]]] = []
    errors: list[str] = []
    current: tuple[str, str, str, list[str]] | None = None

    for raw in text.splitlines():
        line = raw.strip().strip("*").strip()
        if not line:
            continue
        # Model formatting dividers carry no resume content. The authoritative
        # exact-string checks still apply to every header and bullet.
        if re.fullmatch(r"[-─═=]{3,}", line):
            continue
        company = header_to_company.get(line)
        if company:
            parts = [part.strip() for part in line.split("|")]
            if current is not None:
                parsed.append(current)
            current = (company, parts[1], parts[2], [])
            continue
        bullet = _BULLET_RE.match(line)
        if bullet and current is not None:
            current[3].append(bullet.group(1).strip())
            continue
        errors.append(f"unexpected Experience line: {line}")

    if current is not None:
        parsed.append(current)
    expected_order = tuple(override.allocation_plan.counts_dict())
    actual_order = tuple(row[0] for row in parsed)
    if actual_order != expected_order:
        errors.append(f"Experience company order must be {expected_order}, got {actual_order}")
    return parsed, errors


def _parse_skills(text: str) -> tuple[str, tuple[SkillRow, ...], list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", (), ["Skills section is empty"]
    heading = lines[0]
    rows: list[SkillRow] = []
    errors: list[str] = []
    for line in lines[1:]:
        match = _BULLET_RE.match(line)
        if not match:
            errors.append(f"unexpected Skills line: {line}")
            continue
        body = match.group(1).strip()
        if ":" not in body:
            errors.append(f"Skills row has no label: {body}")
            continue
        label, value = body.split(":", 1)
        rows.append(SkillRow(label.strip(), value.strip()))
    return heading, tuple(rows), errors


def _repeated_substantive_skill_tokens(rows: tuple[SkillRow, ...]) -> dict[str, tuple[str, ...]]:
    owners: dict[str, list[str]] = {}
    for row in rows:
        for raw_token in re.split(r"[,;]", row.text):
            token = re.sub(r"[^a-z0-9+#]+", " ", raw_token.casefold()).strip()
            if len(token.split()) < 2:
                continue
            labels = owners.setdefault(token, [])
            if row.label not in labels:
                labels.append(row.label)
    return {
        token: tuple(labels)
        for token, labels in owners.items()
        if len(labels) > 1
    }


def _selection_note_value(
    notes: str,
    label: str,
    errors: list[str],
) -> str | None:
    matches = re.findall(rf"(?im)^{re.escape(label)}:\s*(.*?)\s*$", notes)
    if len(matches) != 1:
        errors.append(
            f"selection notes must contain exactly one {label!r} line, got {len(matches)}"
        )
        return None
    value = matches[0].strip()
    if not value:
        errors.append(f"selection-notes {label!r} value is empty")
        return None
    return value


def _archetype_contract(family: ProfileFamily) -> ArchetypeContract:
    if family is ProfileFamily.PRODUCT:
        return ArchetypeContract(
            # The rulebook's four-archetype figures are distribution guidance,
            # not permission to mislabel a bullet or select weaker evidence just
            # to fill a quota. The reviewed bank currently has no genuine
            # context-first B/C recommendation, so hard floors cover only the
            # funded diagnostic and action signals.
            minimum_counts=(("diagnostic", 2), ("action", 1)),
            maximum_counts=(("diagnostic", 5), ("impact-first", 2)),
            minimum_action_plus_impact=3,
            maximum_consecutive_diagnostic=2,
        )
    return ArchetypeContract(
        minimum_counts=(("action", 1),),
        maximum_counts=(("diagnostic", 6), ("impact-first", 2)),
        minimum_action_plus_impact=2,
        maximum_consecutive_diagnostic=2,
    )


def validate_v2_sections(
    sections: Mapping[str, str],
    override: Pass1PromptOverride,
    score_data: Mapping[str, object],
) -> V2SectionValidation:
    """Return the exact selection audit and structured page for assembly lint."""

    errors: list[str] = []
    warnings: list[str] = []
    parsed, parse_errors = _parse_experience(
        str(sections.get("experience_section", "")), override
    )
    errors.extend(parse_errors)

    by_text = {variant.text: variant for variant in override.bank.variants}
    selected: list[SelectedExperienceVariant] = []
    selected_ids: set[str] = set()
    selected_families: set[str] = set()
    experience_blocks: list[ExperienceBlock] = []
    expected_counts = override.allocation_plan.counts_dict()

    for company, title, date_text, bullets in parsed:
        if len(bullets) != expected_counts.get(company):
            errors.append(
                f"{company}: expected {expected_counts.get(company)} bullets, got {len(bullets)}"
            )
        structured_bullets: list[ExperienceBullet] = []
        for index, text in enumerate(bullets, start=1):
            reviewed = by_text.get(text)
            if reviewed is None:
                errors.append(f"{company} bullet {index} is not an exact reviewed variant: {text}")
                continue
            owner = _company_for_story(reviewed.story_family)
            if owner != company:
                errors.append(
                    f"{company} bullet {index} uses {reviewed.story_family}, owned by {owner}"
                )
            if reviewed.variant_id in selected_ids:
                errors.append(f"reviewed variant repeated: {reviewed.variant_id}")
            if reviewed.story_family in selected_families:
                errors.append(
                    f"story family repeated on one page: {reviewed.story_family}"
                )
            selected_ids.add(reviewed.variant_id)
            selected_families.add(reviewed.story_family)
            archetype = reviewed.archetype
            if not archetype:
                errors.append(f"{reviewed.variant_id} has no admitted archetype metadata")
            selected.append(SelectedExperienceVariant(company, index, reviewed, archetype))
            structured_bullets.append(
                ExperienceBullet(
                    text=text,
                    archetype=archetype,
                    variant_id=reviewed.variant_id,
                    story_id=reviewed.story_family,
                )
            )
        experience_blocks.append(
            ExperienceBlock(company, title, date_text, tuple(structured_bullets))
        )

    if len(selected) != override.bullet_total:
        errors.append(
            f"exact-match selection contains {len(selected)} bullets, expected {override.bullet_total}"
        )
    incident_count = sum(item.reviewed.story_family == "I-INCIDENT" for item in selected)
    if incident_count != 1:
        errors.append(f"protected I-INCIDENT story must appear exactly once, got {incident_count}")

    notes = str(sections.get("selection_notes", ""))
    selected_note = _selection_note_value(notes, "Selected variants", errors)
    expected_note_ids = tuple(item.reviewed.variant_id for item in selected)
    if selected_note is not None:
        actual_note_ids = tuple(
            item.strip() for item in selected_note.split(",") if item.strip()
        )
        if actual_note_ids != expected_note_ids:
            errors.append(
                "selection notes must list exactly the selected reviewed variant IDs in "
                f"output order: expected {expected_note_ids}, got {actual_note_ids}"
            )

    summary_text = str(sections.get("summary_section", "")).strip()
    summary = next(
        (candidate for candidate in override.eligible_summaries if candidate.text == summary_text),
        None,
    )
    if summary is None:
        errors.append("summary is not an exact profile-funded reviewed candidate")
    else:
        missing_evidence = sorted(set(summary.required_page_evidence) - selected_families)
        if missing_evidence:
            errors.append(
                f"summary {summary.candidate_id} lacks required page evidence: {missing_evidence}"
            )
    summary_note = _selection_note_value(notes, "Summary", errors)
    if summary is not None and summary_note is not None and summary_note != summary.candidate_id:
        errors.append(
            f"selection-note Summary must be {summary.candidate_id}, got {summary_note}"
        )

    if str(sections.get("projects_section", "")).strip():
        errors.append("default v2 professional profiles cannot add a Projects section")

    skills_heading, skill_rows, skill_errors = _parse_skills(
        str(sections.get("skills_section", ""))
    )
    errors.extend(skill_errors)
    expected_heading = skills_section_heading(row.label for row in skill_rows)
    if skills_heading != expected_heading:
        errors.append(f"skills heading must be {expected_heading}, got {skills_heading}")

    fluo_candidates = override.bank.family_map().get("FLUO", ())
    fluo_matches = [
        variant
        for variant in fluo_candidates
        if any(variant.text in row.text for row in skill_rows)
    ]
    if len(fluo_matches) > 1:
        errors.append("more than one reviewed Fluo variant appears in Skills")
    fluo_variant = fluo_matches[0] if len(fluo_matches) == 1 else None
    fluo_included = fluo_variant is not None
    placement = override.profile.fluo.placement
    if placement is FluoPlacement.INLINE_REQUIRED and not fluo_included:
        errors.append("profile requires exactly one reviewed Fluo Skills row")
    if placement is FluoPlacement.OMIT and fluo_included:
        errors.append("profile requires Fluo omission")
    fluo_decision = _selection_note_value(notes, "Fluo decision", errors)
    if fluo_decision is not None:
        if fluo_variant is not None:
            valid_include_decisions = {
                fluo_variant.variant_id,
                f"include {fluo_variant.variant_id}",
                f"include with {fluo_variant.variant_id}",
            }
            if fluo_decision not in valid_include_decisions:
                errors.append(
                    "Fluo selection note must record only the included reviewed variant: "
                    f"expected one of {sorted(valid_include_decisions)}, got {fluo_decision}"
                )
        elif fluo_decision.casefold() != "omit":
            errors.append(
                f"Fluo omission must be recorded exactly as 'omit', got {fluo_decision}"
            )
    if fluo_variant is not None and placement in {
        FluoPlacement.INLINE_REQUIRED,
        FluoPlacement.INLINE_RELEVANCE_GATED,
    }:
        matching_rows = [
            row for row in skill_rows if fluo_variant.text in row.text
        ]
        expected_fluo_text = f"Fluo, {fluo_variant.text}"
        if (
            len(matching_rows) != 1
            or matching_rows[0].label != override.profile.fluo.label
            or matching_rows[0].text != expected_fluo_text
        ):
            errors.append(
                f"{fluo_variant.variant_id} must contain only 'Fluo, ' plus the exact "
                f"reviewed variant in the {override.profile.fluo.label} row"
            )
        if "inline" not in fluo_variant.assembly_modes:
            errors.append(
                f"{fluo_variant.variant_id} is not admitted for inline assembly"
            )
        if fluo_variant.line_cost > override.profile.fluo.max_lines:
            errors.append(
                f"{fluo_variant.variant_id} costs {fluo_variant.line_cost} lines; "
                f"profile permits {override.profile.fluo.max_lines}"
            )

    actual_labels = tuple(row.label for row in skill_rows)
    expected_labels = list(override.skills_plan.row_labels)
    if fluo_included and override.profile.fluo.label not in expected_labels:
        if "Additional" in expected_labels:
            expected_labels[expected_labels.index("Additional")] = override.profile.fluo.label
        else:
            errors.append("Fluo inclusion has no funded Skills-row slot")
    if actual_labels != tuple(expected_labels):
        errors.append(
            f"Skills rows must be {tuple(expected_labels)}, got {actual_labels}"
        )
    repeated_skill_tokens = _repeated_substantive_skill_tokens(skill_rows)
    if repeated_skill_tokens:
        errors.append(
            "Skills repeats substantive tokens across rows: "
            + "; ".join(
                f"{token!r} in {list(labels)}"
                for token, labels in sorted(repeated_skill_tokens.items())
            )
        )
    allowed_skill_values = skill_value_candidates_for_profile(
        override.profile,
        override.bank,
        override.skills_plan.row_labels,
    )
    for row in skill_rows:
        candidates = allowed_skill_values.get(row.label, ())
        if row.text not in candidates:
            errors.append(
                f"Skills row {row.label!r} is not an exact profile-funded value"
            )

    document = AssembledResume(
        profile_id=override.profile_id,
        identity_heading=override.profile.identity_heading,
        summary_text=summary_text,
        experience_blocks=tuple(experience_blocks),
        skills_heading=skills_heading,
        skill_rows=skill_rows,
        allocation_plan=override.allocation_plan,
        archetype_contract=_archetype_contract(override.profile.family),
        raw_model_output=str(sections.get("raw", "")),
        projects_text="",
        fluo_included=fluo_included,
        fluo_story_family=(
            fluo_variant.fluo_story_family if fluo_variant is not None else None
        ),
    )
    return V2SectionValidation(
        tuple(errors),
        tuple(warnings),
        tuple(selected),
        summary,
        fluo_variant,
        document,
    )
