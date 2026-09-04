"""Run isolated, story-level challenges against the frozen live variant bank.

This runner writes audit artifacts only.  It never imports or edits the live
resume prompts and never promotes a challenger into a selectable pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from xml.etree import ElementTree

from shared.gold_variant_registry import load_registry
from shared.prompt_variant_inventory import (
    REPO_ROOT,
    SELECTABLE,
    SELECTABLE_SNAPSHOT,
    PromptVariantRecord,
)
from shared.resume_profiles import PROFILE_REGISTRY
from shared.variant_rule_catalog import STRUCTURED_CHALLENGER_DIMENSIONS
from shared.variant_text_lint import lint_candidate_variant_text


PROMPT_PATH = (
    REPO_ROOT / "resume" / "variants" / "prompts" / "material_variant_challenger_v1.txt"
)
AUDIT_ROOT = REPO_ROOT / "resume" / "variants" / "audits"
MAX_WORKERS = 4
MAX_RETRIES = 3
DEFAULT_WORKERS = 2
DEFAULT_RETRIES = 2
MAX_EVIDENCE_CHARS = 80_000

# Only aliases that are the same underlying proof surface belong here.  They do
# not alter source IDs: original record IDs and story labels remain in requests.
SEMANTIC_FAMILY = {
    "H-MONITORING-AI": "H-MONITORING",
    "I-RECONCILIATION": "I-BILLING",
}

EXCLUDED_AUDIT_STORIES = frozenset(
    {"SUMMARY", "SKILLS-ANALYTICS", "SKILLS-COMMUNITY"}
)

CANONICAL_STORY_FILES: dict[str, tuple[str, ...]] = {
    "F-ENTERPRISE": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_enterprise_wedge.md",
    ),
    "F-AVATAR": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_vendor_infra.md",
    ),
    "F-OPS": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_sales_ops.md",
    ),
    "F-CEIPAL": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_ceipal_integration.md",
    ),
    "F-SOURCING": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_sourcing_build_vs_rent.md",
    ),
    "G-SUPPLY": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_gojek_fleet_liquidity_os.md",
    ),
    "G-PRICING": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_gojek_pricing_tier.md",
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_gojek_peak_flattening.md",
    ),
    "G-LATENCY": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_gojek_fare_latency.md",
    ),
    "H-BATCHSHIFT": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_hevo_enterprise_trust_pivot.md",
    ),
    "H-MONITORING": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_hevo_incident_intelligence.md",
        "docs/career_workbench/story_engine/stories/hevo_ai_monitoring.md",
    ),
    "I-INCIDENT": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_intuit_recovery_control_plane.md",
    ),
    "O-PROVIDER": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_optum_provider_integration_factory.md",
    ),
    "O-AFFORDABILITY": (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_optum_affordability_navigation.md",
    ),
    "FLUO": (
        "docs/career_workbench/story_engine/FLUO_STORY_POOL_V1.md",
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_fluo_market_entry.md",
    ),
}

GOLD_STORY_ALIASES: dict[str, frozenset[str]] = {
    "H-MONITORING": frozenset({"H-MONITORING", "H-MONITORING-AI"}),
    "I-BILLING": frozenset({"I-BILLING", "I-RECONCILIATION"}),
    "FLUO": frozenset({"FLUO", "FL-INSTITUTIONAL", "FL-FIELD-VALIDATION"}),
}

TOP_LEVEL_KEYS = frozenset(
    {
        "story_id",
        "story_level_findings",
        "claim_spines",
        "incumbent_decisions",
        "challengers",
        "surviving_variant_ids",
        "human_decisions",
    }
)
FINDING_KEYS = frozenset(
    {
        "highest_stakes_fact",
        "most_non_replicable_fact",
        "strongest_attributable_outcome",
        "facts_that_look_impressive_but_should_not_lead",
    }
)
CLAIM_KEYS = frozenset(
    {
        "claim_id",
        "hiring_question",
        "path",
        "scarce_atom",
        "counterfactual_ownership",
        "excluded_adjacent_atoms",
        "eligible_profiles",
        "incumbent_ids",
    }
)
PATH_KEYS = frozenset(
    {
        "trigger_or_observation",
        "judgment",
        "decision_or_artifact",
        "attributable_consequence",
    }
)
DECISION_KEYS = frozenset(
    {
        "incumbent_id",
        "claim_id",
        "verdict",
        "material_reason",
        "critical_vetoes",
        "material_loss_if_replaced",
        "replacement_candidate_id",
    }
)
VETO_KEYS = frozenset(
    {
        "materiality",
        "same_story_edge_integrity",
        "criterion_proof",
        "counterfactual_ownership",
        "mechanism_fit",
        "outcome_closure",
        "outsider_legibility",
        "fact_containment",
    }
)
CHALLENGER_KEYS = frozenset(
    {
        "candidate_id",
        "claim_id",
        "text",
        "archetype",
        "one_earned_detail",
        "matched_outcome",
        "material_win_over_incumbent",
        "material_loss_vs_incumbent",
        "source_fact_atoms",
        "estimated_line_cost",
        "recommendation",
        "rulebook_checks",
    }
)
RULEBOOK_CHECK_KEYS = frozenset({"verdict", "reason"})


@dataclass(frozen=True)
class StoryBundle:
    story_id: str
    incumbents: tuple[PromptVariantRecord, ...]
    evidence: str
    evidence_sources: tuple[str, ...]
    known_gold: tuple[dict[str, str], ...]
    consistency_warnings: tuple[str, ...]


@dataclass(frozen=True)
class StoryRunResult:
    story_id: str
    status: str
    request_path: str
    response_path: str = ""
    review_path: str = ""
    error_path: str = ""
    attempts: int = 0


def semantic_story_id(story_id: str) -> str:
    return SEMANTIC_FAMILY.get(story_id, story_id)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def load_inventory(path: Path = SELECTABLE_SNAPSHOT) -> tuple[PromptVariantRecord, ...]:
    records: list[PromptVariantRecord] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            try:
                record = PromptVariantRecord(**json.loads(raw))
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid inventory record: {exc}") from exc
            if record.selectability != SELECTABLE:
                raise ValueError(
                    f"{path}:{line_number}: non-selectable record in selectable snapshot"
                )
            records.append(record)
    ids = [record.stable_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate stable IDs")
    return tuple(records)


def group_causal_stories(
    records: Iterable[PromptVariantRecord],
) -> dict[str, tuple[PromptVariantRecord, ...]]:
    grouped: dict[str, list[PromptVariantRecord]] = {}
    for record in records:
        if record.story in EXCLUDED_AUDIT_STORIES:
            continue
        story_id = semantic_story_id(record.story)
        grouped.setdefault(story_id, []).append(record)
    return {
        story_id: tuple(items)
        for story_id, items in sorted(grouped.items())
    }


def _prompt_context(records: Sequence[PromptVariantRecord]) -> tuple[str, ...]:
    """Recover prompt-owned core facts when no canonical story source exists."""
    contexts: list[str] = []
    by_source: dict[str, list[PromptVariantRecord]] = {}
    for record in records:
        by_source.setdefault(record.source_path, []).append(record)
    boundary = re.compile(
        r"(?:─── STORY|\bOption [A-Z]|^[A-Z]\d+\s+—|PROFESSIONAL SUMMARY POOL|"
        r"VENTURE PRODUCT POOL|STORY POOL —|STRATEGY PROJECT ROW|"
        r"Rules for using proof units:|"
        r"^\s*P-[A-Z]+\s+\[[^]]+\])"
    )
    for source_path, source_records in sorted(by_source.items()):
        path = REPO_ROOT / source_path
        lines = path.read_text(encoding="utf-8").splitlines()
        first = min(record.source_line for record in source_records) - 1
        last = max(record.source_line for record in source_records) - 1
        start = first
        while start > 0 and not boundary.search(lines[start]):
            start -= 1
        end = last + 1
        while end < len(lines) and not boundary.search(lines[end]):
            end += 1
        excerpt = "\n".join(lines[start:end]).strip()
        contexts.append(f"SOURCE: {source_path} (prompt-owned context)\n{excerpt}")
    return tuple(contexts)


def _canonical_sources(story_id: str) -> tuple[Path, ...]:
    paths = tuple(REPO_ROOT / item for item in CANONICAL_STORY_FILES.get(story_id, ()))
    for path in paths:
        if "profile_maxing_lab" in path.parts:
            raise ValueError(f"Counterfactual source is forbidden: {path}")
        if not path.exists():
            raise ValueError(f"Canonical story source is missing: {path}")
    return paths


def _known_gold(story_id: str) -> tuple[dict[str, str], ...]:
    accepted_story_ids = GOLD_STORY_ALIASES.get(story_id, frozenset({story_id}))
    rows = []
    for variant in load_registry():
        if variant.story_id in accepted_story_ids:
            rows.append(
                {
                    "variant_id": variant.variant_id,
                    "story_id": variant.story_id,
                    "text": variant.text,
                    "shipping_recommendation": variant.shipping_recommendation,
                }
            )
    return tuple(rows)


_VALUE_ATOM = re.compile(
    r"(?<![A-Za-z])(?:[$~±])?\d+(?:[.,]\d+)*(?:%|[KMBkmb+]*)?"
    r"(?:\s*(?:minutes?|days?|weeks?|months?|clients?|businesses?|pipelines?|"
    r"teams?|riders?|users?|accounts?|issues?))?",
    re.IGNORECASE,
)


def cross_track_consistency_warnings(
    incumbents: Sequence[PromptVariantRecord],
) -> tuple[str, ...]:
    """Surface track-level value differences for human resolution, never auto-pick."""
    by_track: dict[str, set[str]] = {}
    for record in incumbents:
        by_track.setdefault(record.track, set()).update(
            match.group(0).strip() for match in _VALUE_ATOM.finditer(record.text)
        )
    if set(by_track) != {"pm", "nonpm"}:
        return ()
    pm_only = sorted(by_track["pm"] - by_track["nonpm"])
    nonpm_only = sorted(by_track["nonpm"] - by_track["pm"])
    if not pm_only and not nonpm_only:
        return ()
    return (
        "Cross-track value atoms differ. Confirm that each number is attributable "
        "to the same causal story before accepting a replacement. "
        f"PM-only: {pm_only or ['none']}; NONPM-only: {nonpm_only or ['none']}.",
    )


def build_story_bundle(
    story_id: str,
    grouped: Mapping[str, tuple[PromptVariantRecord, ...]],
) -> StoryBundle:
    if story_id not in grouped:
        raise ValueError(f"Unknown or excluded story {story_id!r}")
    incumbents = grouped[story_id]
    canonical = _canonical_sources(story_id)
    if canonical:
        evidence_parts = tuple(
            f"SOURCE: {path.relative_to(REPO_ROOT)}\n{path.read_text(encoding='utf-8').strip()}"
            for path in canonical
        )
        evidence_sources = tuple(str(path.relative_to(REPO_ROOT)) for path in canonical)
    else:
        evidence_parts = _prompt_context(incumbents)
        evidence_sources = tuple(
            f"{record.source_path}#L{record.source_line}"
            for record in incumbents
        )
    warnings = cross_track_consistency_warnings(incumbents)
    evidence = "\n\n".join(evidence_parts)
    if warnings:
        evidence += "\n\nCROSS-TRACK CONSISTENCY REVIEW — HUMAN DECISION REQUIRED\n"
        evidence += "\n".join(f"- {warning}" for warning in warnings)
    if len(evidence) > MAX_EVIDENCE_CHARS:
        raise ValueError(
            f"{story_id}: evidence is {len(evidence)} chars, above safe bound "
            f"{MAX_EVIDENCE_CHARS}; curate the canonical source instead of truncating it"
        )
    return StoryBundle(
        story_id=story_id,
        incumbents=incumbents,
        evidence=evidence,
        evidence_sources=evidence_sources,
        known_gold=_known_gold(story_id),
        consistency_warnings=warnings,
    )


def _profile_context() -> list[dict[str, Any]]:
    return [
        {
            "profile_id": profile.profile_id,
            "family": profile.family.value,
            "selection_priorities": list(profile.selection_priorities),
            "experience_allocation": profile.slots_dict(),
        }
        for profile in PROFILE_REGISTRY.values()
    ]


def _criterion_catalog() -> list[str]:
    return sorted(
        {
            criterion
            for profile in PROFILE_REGISTRY.values()
            for criterion in profile.selection_priorities
        }
    )


def build_prompt(bundle: StoryBundle, template_path: Path = PROMPT_PATH) -> str:
    template = template_path.read_text(encoding="utf-8")
    incumbents = [asdict(record) for record in bundle.incumbents]
    replacements = {
        "{{STORY_ID}}": bundle.story_id,
        "{{STORY_EVIDENCE}}": bundle.evidence,
        "{{INCUMBENT_VARIANTS}}": json.dumps(incumbents, ensure_ascii=False, indent=2),
        "{{KNOWN_GOLD_VARIANTS}}": json.dumps(bundle.known_gold, ensure_ascii=False, indent=2),
        "{{CRITERION_CATALOG}}": json.dumps(_criterion_catalog(), ensure_ascii=False, indent=2),
        "{{PROFILE_CONTEXT}}": json.dumps(_profile_context(), ensure_ascii=False, indent=2),
    }
    for marker, value in replacements.items():
        if marker not in template:
            raise ValueError(f"Challenger template missing marker {marker}")
        template = template.replace(marker, value)
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", template)
    if leftovers:
        raise ValueError(f"Unresolved challenger template markers: {leftovers}")
    return template


def load_api_key(environment: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environment is None else environment
    key = str(environment.get("ANTHROPIC_API_KEY", "")).strip()
    if key:
        return key
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    raise RuntimeError("ANTHROPIC_API_KEY is not set")


class AnthropicCaller:
    """Small bounded wrapper matching the generator's 429/529 retry behavior."""

    def __init__(
        self,
        model: str,
        retries: int,
        *,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model.strip():
            raise ValueError("model is required")
        if not 0 <= retries <= MAX_RETRIES:
            raise ValueError(f"retries must be between 0 and {MAX_RETRIES}")
        self.model = model
        self.retries = retries
        self.sleep = sleep
        if client is None:
            import anthropic
            import httpx

            # Match the existing resume generator's host behavior.  The local
            # Anthropic path may sit behind a self-signed proxy chain.
            client = anthropic.Anthropic(
                api_key=load_api_key(),
                http_client=httpx.Client(verify=False),
            )
        self.client = client
        self._lock = threading.Lock()
        self.attempts: dict[str, int] = {}

    def __call__(self, prompt: str, story_id: str) -> str:
        import anthropic

        for attempt in range(self.retries + 1):
            with self._lock:
                self.attempts[story_id] = attempt + 1
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                return message.content[0].text
            except anthropic.RateLimitError as exc:
                retryable = True
                caught: Exception = exc
            except anthropic.APIStatusError as exc:
                retryable = getattr(exc, "status_code", None) == 529
                if not retryable:
                    raise
                caught = exc
            if not retryable or attempt >= self.retries:
                raise caught
            self.sleep(min(20 * (2**attempt), 60))
        raise RuntimeError("unreachable")


def _require_exact_keys(value: Any, keys: frozenset[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return
    actual = set(value)
    missing = sorted(keys - actual)
    extra = sorted(actual - keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
    if extra:
        errors.append(f"{path} has extra keys: {extra}")


def _require_string(value: Any, path: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        errors.append(f"{path} must be a {'string' if allow_empty else 'non-empty string'}")


def _require_string_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{path} must be a list of strings")


def validate_response(payload: Any, bundle: StoryBundle) -> list[str]:
    """Validate the prompt's exact response schema and referential integrity."""
    errors: list[str] = []
    _require_exact_keys(payload, TOP_LEVEL_KEYS, "$", errors)
    if not isinstance(payload, dict):
        return errors
    if payload.get("story_id") != bundle.story_id:
        errors.append(f"$.story_id must equal {bundle.story_id!r}")

    findings = payload.get("story_level_findings")
    _require_exact_keys(findings, FINDING_KEYS, "$.story_level_findings", errors)
    if isinstance(findings, dict):
        for key in FINDING_KEYS - {"facts_that_look_impressive_but_should_not_lead"}:
            _require_string(findings.get(key), f"$.story_level_findings.{key}", errors)
        _require_string_list(
            findings.get("facts_that_look_impressive_but_should_not_lead"),
            "$.story_level_findings.facts_that_look_impressive_but_should_not_lead",
            errors,
        )

    claims = payload.get("claim_spines")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 4:
        errors.append("$.claim_spines must contain 1-4 objects")
        claims = []
    claim_ids: set[str] = set()
    incumbent_ids = {record.stable_id for record in bundle.incumbents}
    gold_by_id = {item["variant_id"]: item for item in bundle.known_gold}
    known_evidence_ids = incumbent_ids | set(gold_by_id)
    for index, claim in enumerate(claims):
        base = f"$.claim_spines[{index}]"
        _require_exact_keys(claim, CLAIM_KEYS, base, errors)
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("claim_id")
        _require_string(claim_id, f"{base}.claim_id", errors)
        if isinstance(claim_id, str):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", claim_id):
                errors.append(f"{base}.claim_id must be stable kebab-case")
            if claim_id in claim_ids:
                errors.append(f"{base}.claim_id is duplicated")
            claim_ids.add(claim_id)
        for key in ("hiring_question", "counterfactual_ownership"):
            _require_string(claim.get(key), f"{base}.{key}", errors)
        if claim.get("scarce_atom") not in {
            "insight", "tradeoff", "artifact", "ownership", "impact"
        }:
            errors.append(f"{base}.scarce_atom has an invalid value")
        path = claim.get("path")
        _require_exact_keys(path, PATH_KEYS, f"{base}.path", errors)
        if isinstance(path, dict):
            for key in PATH_KEYS:
                _require_string(path.get(key), f"{base}.path.{key}", errors)
        for key in ("excluded_adjacent_atoms", "eligible_profiles", "incumbent_ids"):
            _require_string_list(claim.get(key), f"{base}.{key}", errors)
        if isinstance(claim.get("eligible_profiles"), list):
            unknown = sorted(set(claim["eligible_profiles"]) - set(PROFILE_REGISTRY))
            if unknown:
                errors.append(f"{base}.eligible_profiles contains unknown profiles: {unknown}")
        if isinstance(claim.get("incumbent_ids"), list):
            unknown = sorted(set(claim["incumbent_ids"]) - known_evidence_ids)
            if unknown:
                errors.append(f"{base}.incumbent_ids contains unknown IDs: {unknown}")

    decisions = payload.get("incumbent_decisions")
    if not isinstance(decisions, list):
        errors.append("$.incumbent_decisions must be a list")
        decisions = []
    seen_decisions: set[str] = set()
    candidate_ids: set[str] = set()
    challengers = payload.get("challengers")
    if not isinstance(challengers, list):
        errors.append("$.challengers must be a list")
        challengers = []
    for index, challenger in enumerate(challengers):
        base = f"$.challengers[{index}]"
        _require_exact_keys(challenger, CHALLENGER_KEYS, base, errors)
        if not isinstance(challenger, dict):
            continue
        candidate_id = challenger.get("candidate_id")
        _require_string(candidate_id, f"{base}.candidate_id", errors)
        if isinstance(candidate_id, str):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", candidate_id):
                errors.append(f"{base}.candidate_id must be stable kebab-case")
            if candidate_id in candidate_ids or candidate_id in known_evidence_ids:
                errors.append(f"{base}.candidate_id is duplicated or collides with an incumbent")
            candidate_ids.add(candidate_id)
        if challenger.get("claim_id") not in claim_ids:
            errors.append(f"{base}.claim_id does not reference a claim spine")
        for key in (
            "text", "one_earned_detail", "matched_outcome",
            "material_win_over_incumbent", "material_loss_vs_incumbent",
        ):
            _require_string(challenger.get(key), f"{base}.{key}", errors)
        if challenger.get("archetype") not in {
            "diagnostic",
            "action",
            "context",
            "impact",
            "tradeoff",
        }:
            errors.append(f"{base}.archetype has an invalid value")
        _require_string_list(challenger.get("source_fact_atoms"), f"{base}.source_fact_atoms", errors)
        line_cost = challenger.get("estimated_line_cost")
        if not isinstance(line_cost, int) or not 1 <= line_cost <= 4:
            errors.append(f"{base}.estimated_line_cost must be an integer from 1 to 4")
        if challenger.get("recommendation") not in {
            "accept_challenger", "keep_incumbent", "human_review"
        }:
            errors.append(f"{base}.recommendation has an invalid value")

        rulebook_checks = challenger.get("rulebook_checks")
        if not isinstance(rulebook_checks, dict):
            errors.append(f"{base}.rulebook_checks must be an object")
        else:
            missing_dimensions = sorted(
                STRUCTURED_CHALLENGER_DIMENSIONS - set(rulebook_checks)
            )
            extra_dimensions = sorted(
                set(rulebook_checks) - STRUCTURED_CHALLENGER_DIMENSIONS
            )
            if missing_dimensions:
                errors.append(
                    f"{base}.rulebook_checks missing dimensions: {missing_dimensions}"
                )
            if extra_dimensions:
                errors.append(
                    f"{base}.rulebook_checks has unknown dimensions: {extra_dimensions}"
                )
            failed_dimensions: list[str] = []
            for dimension in sorted(STRUCTURED_CHALLENGER_DIMENSIONS):
                result = rulebook_checks.get(dimension)
                result_path = f"{base}.rulebook_checks.{dimension}"
                _require_exact_keys(result, RULEBOOK_CHECK_KEYS, result_path, errors)
                if not isinstance(result, dict):
                    continue
                if result.get("verdict") not in {"pass", "fail", "not_applicable"}:
                    errors.append(f"{result_path}.verdict has an invalid value")
                elif result.get("verdict") == "fail":
                    failed_dimensions.append(dimension)
                _require_string(result.get("reason"), f"{result_path}.reason", errors)
            if (
                challenger.get("recommendation") == "accept_challenger"
                and failed_dimensions
            ):
                errors.append(
                    f"{base} cannot accept a challenger with failed rulebook "
                    f"dimensions: {failed_dimensions}"
                )

        text = challenger.get("text")
        if isinstance(text, str) and text.strip():
            text_report = lint_candidate_variant_text(
                text,
                declared_archetype=challenger.get("archetype"),
            )
            for issue in text_report.blockers:
                errors.append(
                    f"{base}.text fails deterministic rule {issue.code}: {issue.message}"
                )

    for index, decision in enumerate(decisions):
        base = f"$.incumbent_decisions[{index}]"
        _require_exact_keys(decision, DECISION_KEYS, base, errors)
        if not isinstance(decision, dict):
            continue
        incumbent_id = decision.get("incumbent_id")
        if incumbent_id not in incumbent_ids:
            errors.append(f"{base}.incumbent_id is unknown")
        elif incumbent_id in seen_decisions:
            errors.append(f"{base}.incumbent_id is duplicated")
        else:
            seen_decisions.add(incumbent_id)
        if decision.get("claim_id") not in claim_ids:
            errors.append(f"{base}.claim_id does not reference a claim spine")
        if decision.get("verdict") not in {
            "retain_exact", "replace", "retire_dominated", "hold_for_human"
        }:
            errors.append(f"{base}.verdict has an invalid value")
        for key in ("material_reason", "material_loss_if_replaced"):
            _require_string(decision.get(key), f"{base}.{key}", errors)
        replacement = decision.get("replacement_candidate_id")
        _require_string(replacement, f"{base}.replacement_candidate_id", errors, allow_empty=True)
        if decision.get("verdict") == "replace" and replacement not in candidate_ids | set(gold_by_id):
            errors.append(
                f"{base}.replacement_candidate_id must name a challenger or known gold sibling"
            )
        if decision.get("verdict") != "replace" and replacement:
            errors.append(f"{base}.replacement_candidate_id must be empty unless verdict is replace")
        vetoes = decision.get("critical_vetoes")
        _require_exact_keys(vetoes, VETO_KEYS, f"{base}.critical_vetoes", errors)
        if isinstance(vetoes, dict):
            for key in VETO_KEYS:
                if vetoes.get(key) not in {"pass", "fail"}:
                    errors.append(f"{base}.critical_vetoes.{key} must be pass or fail")

    if seen_decisions != incumbent_ids:
        missing = sorted(incumbent_ids - seen_decisions)
        if missing:
            errors.append(f"$.incumbent_decisions missing incumbents: {missing}")

    surviving = payload.get("surviving_variant_ids")
    _require_string_list(surviving, "$.surviving_variant_ids", errors)
    if isinstance(surviving, list):
        valid_survivors = known_evidence_ids | candidate_ids
        unknown = sorted(set(surviving) - valid_survivors)
        if unknown:
            errors.append(f"$.surviving_variant_ids contains unknown IDs: {unknown}")
        if len(surviving) != len(set(surviving)):
            errors.append("$.surviving_variant_ids contains duplicate IDs")
    _require_string_list(payload.get("human_decisions"), "$.human_decisions", errors)
    return errors


def parse_response(raw: str, bundle: StoryBundle) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output is not bare valid JSON: {exc}") from exc
    errors = validate_response(payload, bundle)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def _markdown_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_human_review(bundle: StoryBundle, payload: Mapping[str, Any]) -> str:
    candidates = {item["candidate_id"]: item for item in payload["challengers"]}
    candidates.update(
        {
            item["variant_id"]: {
                "candidate_id": item["variant_id"],
                "claim_id": "known-gold",
                "recommendation": item["shipping_recommendation"],
                "text": item["text"],
            }
            for item in bundle.known_gold
        }
    )
    incumbents = {record.stable_id: record for record in bundle.incumbents}
    lines = [
        f"# Material challenge review — {bundle.story_id}",
        "",
        "Audit only. Nothing in this file is promoted into the live generator.",
        "",
        "## Source evidence",
        "",
    ]
    lines.extend(f"- `{source}`" for source in bundle.evidence_sources)
    if bundle.consistency_warnings:
        lines.extend(["", "## Cross-track consistency — human decision required", ""])
        lines.extend(f"- [ ] {warning}" for warning in bundle.consistency_warnings)
    if bundle.known_gold:
        lines.extend(["", "## Known gold siblings", ""])
        for item in bundle.known_gold:
            lines.extend(
                [
                    f"### `{item['variant_id']}`",
                    "",
                    item["text"],
                    "",
                ]
            )
    lines.extend(["", "## Incumbent decisions", ""])
    for decision in payload["incumbent_decisions"]:
        incumbent = incumbents[decision["incumbent_id"]]
        replacement = candidates.get(decision["replacement_candidate_id"])
        lines.extend(
            [
                f"### `{incumbent.stable_id}` — {decision['verdict']}",
                "",
                f"**Incumbent, exact:** {incumbent.text}",
                "",
                (
                    f"**Proposed challenger:** {replacement['text']}"
                    if replacement
                    else "**Proposed challenger:** None"
                ),
                "",
                f"**Material reason:** {decision['material_reason']}",
                "",
                f"**Loss if replaced:** {decision['material_loss_if_replaced']}",
                "",
            ]
        )
    lines.extend(["## Challenger slate", "", "| ID | Claim | Recommendation | Exact text |", "|---|---|---|---|"])
    for candidate in payload["challengers"]:
        lines.append(
            "| `{}` | `{}` | {} | {} |".format(
                candidate["candidate_id"],
                candidate["claim_id"],
                candidate["recommendation"],
                _markdown_escape(candidate["text"]),
            )
        )
    lines.extend(["", "## Rulebook cards and deterministic review proxies", ""])
    for candidate in payload["challengers"]:
        lines.extend([f"### `{candidate['candidate_id']}`", ""])
        checks = candidate["rulebook_checks"]
        for dimension in sorted(STRUCTURED_CHALLENGER_DIMENSIONS):
            result = checks[dimension]
            lines.append(
                f"- **{dimension}: {result['verdict']}** — {result['reason']}"
            )
        text_report = lint_candidate_variant_text(
            candidate["text"],
            declared_archetype=candidate["archetype"],
        )
        if text_report.review_items:
            lines.extend(["", "Deterministic review proxies:", ""])
            lines.extend(
                f"- `{issue.code}` — {issue.message}"
                for issue in text_report.review_items
            )
        else:
            lines.extend(["", "Deterministic review proxies: none."])
        lines.append("")
    lines.extend(["", "## Human decisions", ""])
    if payload["human_decisions"]:
        lines.extend(f"- [ ] {item}" for item in payload["human_decisions"])
    else:
        lines.append("- None requested.")
    lines.extend(["", "## Surviving IDs", ""])
    lines.extend(f"- `{item}`" for item in payload["surviving_variant_ids"])
    return "\n".join(lines) + "\n"


def _request_payload(bundle: StoryBundle, prompt: str, model: str) -> dict[str, Any]:
    return {
        "story_id": bundle.story_id,
        "model": model,
        "evidence_sources": list(bundle.evidence_sources),
        "incumbents": [asdict(record) for record in bundle.incumbents],
        "known_gold_variants": list(bundle.known_gold),
        "consistency_warnings": list(bundle.consistency_warnings),
        "prompt": prompt,
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _run_story(
    bundle: StoryBundle,
    *,
    run_dir: Path,
    model: str,
    dry_run: bool,
    api_call: Callable[[str, str], str] | None,
) -> StoryRunResult:
    slug = _slug(bundle.story_id)
    prompt = build_prompt(bundle)
    request_path = run_dir / f"{slug}.request.json"
    _atomic_write(request_path, _json_text(_request_payload(bundle, prompt, model)))
    if dry_run:
        return StoryRunResult(
            story_id=bundle.story_id,
            status="dry-run",
            request_path=_display_path(request_path),
        )
    if api_call is None:
        raise ValueError("api_call is required for a live challenger run")
    try:
        raw = api_call(prompt, bundle.story_id)
        payload = parse_response(raw, bundle)
        response_path = run_dir / f"{slug}.response.json"
        review_path = run_dir / f"{slug}.review.md"
        _atomic_write(response_path, _json_text(payload))
        _atomic_write(review_path, render_human_review(bundle, payload))
        attempts = getattr(api_call, "attempts", {}).get(bundle.story_id, 1)
        return StoryRunResult(
            story_id=bundle.story_id,
            status="complete",
            request_path=_display_path(request_path),
            response_path=_display_path(response_path),
            review_path=_display_path(review_path),
            attempts=attempts,
        )
    except Exception as exc:
        error_path = run_dir / f"{slug}.error.json"
        _atomic_write(
            error_path,
            _json_text(
                {
                    "story_id": bundle.story_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            ),
        )
        attempts = getattr(api_call, "attempts", {}).get(bundle.story_id, 1)
        return StoryRunResult(
            story_id=bundle.story_id,
            status="failed",
            request_path=_display_path(request_path),
            error_path=_display_path(error_path),
            attempts=attempts,
        )


def _docx_text(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return "\n".join(
        "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        for paragraph in root.findall(".//w:p", namespace)
    )


def _all_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def stories_for_resume(
    path: Path,
    grouped: Mapping[str, tuple[PromptVariantRecord, ...]],
) -> tuple[str, ...]:
    """Conservatively resolve stories represented by exact IDs or exact text."""
    if not path.exists():
        raise ValueError(f"Resume selector path does not exist: {path}")
    if path.suffix.casefold() == ".json":
        strings = tuple(_all_strings(json.loads(path.read_text(encoding="utf-8"))))
        text = "\n".join(strings)
    elif path.suffix.casefold() == ".docx":
        strings = ()
        text = _docx_text(path)
    elif path.suffix.casefold() in {".txt", ".md"}:
        strings = ()
        text = path.read_text(encoding="utf-8")
    else:
        raise ValueError("--resume supports .json, .docx, .txt, or .md")

    matched: set[str] = set()
    inventory_ids = {
        record.stable_id: story_id
        for story_id, records in grouped.items()
        for record in records
    }
    for value in strings:
        if value in inventory_ids:
            matched.add(inventory_ids[value])
    for story_id, records in grouped.items():
        if any(record.text in text for record in records):
            matched.add(story_id)
    gold_by_id = {variant.variant_id: semantic_story_id(variant.story_id) for variant in load_registry()}
    for value in strings:
        if value in gold_by_id and gold_by_id[value] in grouped:
            matched.add(gold_by_id[value])
    if not matched:
        raise ValueError(
            f"No exact inventory/gold IDs or incumbent texts were found in {path}; "
            "refusing to guess from company names"
        )
    return tuple(sorted(matched))


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def render_run_review(
    run_dir: Path,
    bundles: Sequence[StoryBundle],
    results: Sequence[StoryRunResult],
) -> str:
    """Create one bounded entry point for reviewing a multi-story audit run."""
    bundle_by_id = {bundle.story_id: bundle for bundle in bundles}
    lines = [
        f"# Whole-bank challenge run — {run_dir.name}",
        "",
        "Audit only. No result in this directory changes a live prompt or registry.",
        "",
        "| Story | Status | Review |",
        "|---|---|---|",
    ]
    for result in results:
        link = result.review_path or result.error_path or result.request_path
        label = "review" if result.review_path else ("error" if result.error_path else "request")
        lines.append(f"| `{result.story_id}` | {result.status} | [{label}]({Path(link).name}) |")
    lines.extend(["", "## Decisions requiring attention", ""])
    decision_count = 0
    for result in results:
        bundle = bundle_by_id[result.story_id]
        for warning in bundle.consistency_warnings:
            lines.append(f"- [ ] **{result.story_id}:** {warning}")
            decision_count += 1
        if result.response_path:
            response_path = REPO_ROOT / result.response_path
            if not response_path.exists():
                response_path = Path(result.response_path)
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            for decision in payload["human_decisions"]:
                lines.append(f"- [ ] **{result.story_id}:** {decision}")
                decision_count += 1
        if result.status == "failed":
            lines.append(f"- [ ] **{result.story_id}:** inspect failed audit before any promotion.")
            decision_count += 1
    if decision_count == 0:
        lines.append("- None surfaced.")
    return "\n".join(lines) + "\n"


def run_challenges(
    story_ids: Sequence[str],
    *,
    model: str,
    dry_run: bool,
    workers: int = DEFAULT_WORKERS,
    retries: int = DEFAULT_RETRIES,
    run_id: str | None = None,
    api_call: Callable[[str, str], str] | None = None,
) -> tuple[Path, tuple[StoryRunResult, ...]]:
    if not model.strip():
        raise ValueError("model is required")
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    if not 0 <= retries <= MAX_RETRIES:
        raise ValueError(f"retries must be between 0 and {MAX_RETRIES}")
    inventory = load_inventory()
    grouped = group_causal_stories(inventory)
    normalized_ids = tuple(dict.fromkeys(semantic_story_id(item) for item in story_ids))
    unknown = sorted(set(normalized_ids) - set(grouped))
    if unknown:
        raise ValueError(f"Unknown or excluded stories: {unknown}")
    if not normalized_ids:
        raise ValueError("At least one story is required")

    bundles = [build_story_bundle(story_id, grouped) for story_id in normalized_ids]
    run_id = run_id or new_run_id()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError("run_id may contain only letters, numbers, dot, underscore, or dash")
    run_dir = AUDIT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()

    if not dry_run and api_call is None:
        api_call = AnthropicCaller(model, retries)

    results: list[StoryRunResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_story,
                bundle,
                run_dir=run_dir,
                model=model,
                dry_run=dry_run,
                api_call=api_call,
            ): bundle.story_id
            for bundle in bundles
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda result: result.story_id)
    completed_at = datetime.now(timezone.utc).isoformat()
    run_review_path = run_dir / "HUMAN_REVIEW.md"
    _atomic_write(run_review_path, render_run_review(run_dir, bundles, results))
    manifest = {
        "run_id": run_id,
        "mode": "dry-run" if dry_run else "challenge",
        "model": model,
        "workers": workers,
        "retries": retries,
        "inventory_path": str(SELECTABLE_SNAPSHOT.relative_to(REPO_ROOT)),
        "inventory_sha256": _sha256(SELECTABLE_SNAPSHOT),
        "prompt_template_path": str(PROMPT_PATH.relative_to(REPO_ROOT)),
        "prompt_template_sha256": _sha256(PROMPT_PATH),
        "requested_story_ids": list(normalized_ids),
        "started_at": started_at,
        "completed_at": completed_at,
        "human_review_path": _display_path(run_review_path),
        "results": [asdict(result) for result in results],
    }
    _atomic_write(run_dir / "manifest.json", _json_text(manifest))
    return run_dir, tuple(results)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Anthropic model; no implicit default")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--story", action="append", help="semantic story ID; repeatable")
    target.add_argument("--all", action="store_true", help="challenge every causal story")
    target.add_argument("--resume", type=Path, help="challenge stories exactly identified in a resume/fixture")
    parser.add_argument("--dry-run", action="store_true", help="write requests without calling Anthropic")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--run-id", help="optional deterministic audit directory name")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    grouped = group_causal_stories(load_inventory())
    if args.all:
        story_ids = tuple(grouped)
    elif args.resume:
        story_ids = stories_for_resume(args.resume, grouped)
    else:
        story_ids = tuple(args.story)
    run_dir, results = run_challenges(
        story_ids,
        model=args.model,
        dry_run=args.dry_run,
        workers=args.workers,
        retries=args.retries,
        run_id=args.run_id,
    )
    failed = sum(result.status == "failed" for result in results)
    print(f"audit artifacts: {run_dir.relative_to(REPO_ROOT)}")
    print(f"stories: {len(results)}, failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
