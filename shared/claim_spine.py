"""Deterministic non-regression decisions for resume claim-spine challengers.

This module is intentionally inert: the live resume generator does not import it.
It compares already-authored incumbent and challenger variants using explicit
human-reviewed metadata.  It never generates, rewrites, or merges bullet text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_PAIR_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "resume_quality_pairs" / "known_pairs.json"
)

SCORE_MIN = 0
SCORE_MAX = 4
SCARCE_ATOMS = frozenset(
    {"insight", "tradeoff", "artifact", "ownership", "impact"}
)


class PairwiseVerdict(str, Enum):
    KEEP_INCUMBENT = "keep-incumbent"
    ACCEPT_CHALLENGER = "accept-challenger"
    KEEP_BOTH = "keep-both"
    HUMAN_REVIEW = "human-review"


@dataclass(frozen=True)
class ClaimSpine:
    """One connected path through a richer source story."""

    trigger: str
    judgment: str
    mechanism: str
    outcome: str

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "ClaimSpine":
        return cls(
            trigger=str(record.get("trigger", "")),
            judgment=str(record.get("judgment", "")),
            mechanism=str(record.get("mechanism", "")),
            outcome=str(record.get("outcome", "")),
        )


@dataclass(frozen=True)
class CriticalVetoes:
    """Non-averaged gates.  One false value makes a candidate unsafe."""

    materiality: bool
    causal_edge_integrity: bool
    ownership: bool
    mechanism_fit: bool
    outcome_closure: bool
    outsider_legibility: bool

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "CriticalVetoes":
        return cls(
            materiality=record.get("materiality"),
            causal_edge_integrity=record.get("causal_edge_integrity"),
            ownership=record.get("ownership"),
            mechanism_fit=record.get("mechanism_fit"),
            outcome_closure=record.get("outcome_closure"),
            outsider_legibility=record.get("outsider_legibility"),
        )

    @property
    def passed(self) -> bool:
        return all(
            value is True
            for value in (
                self.materiality,
                self.causal_edge_integrity,
                self.ownership,
                self.mechanism_fit,
                self.outcome_closure,
                self.outsider_legibility,
            )
        )

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in self.__dict__.items()
            if value is not True
        )


@dataclass(frozen=True)
class MaterialRank:
    """Material dimensions used for Pareto comparison after critical vetoes."""

    criterion_strength: int
    marginal_page_value: int
    stakes_nonreplicability: int
    counterfactual_ownership: int
    outcome_quality: int

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "MaterialRank":
        return cls(
            criterion_strength=record.get("criterion_strength", -1),
            marginal_page_value=record.get("marginal_page_value", -1),
            stakes_nonreplicability=record.get("stakes_nonreplicability", -1),
            counterfactual_ownership=record.get("counterfactual_ownership", -1),
            outcome_quality=record.get("outcome_quality", -1),
        )

    def as_tuple(self) -> tuple[int, ...]:
        return (
            self.criterion_strength,
            self.marginal_page_value,
            self.stakes_nonreplicability,
            self.counterfactual_ownership,
            self.outcome_quality,
        )


@dataclass(frozen=True)
class ClaimCandidate:
    candidate_id: str
    story_id: str
    claim_id: str
    text: str
    spine: ClaimSpine
    scarce_atom: str
    criterion_proof: frozenset[str]
    counterfactual_ownership: str
    decision_rationale: str
    excluded_adjacent_atoms: tuple[str, ...]
    critical: CriticalVetoes
    material_rank: MaterialRank
    line_cost: int

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "ClaimCandidate":
        return cls(
            candidate_id=str(record.get("candidate_id", "")),
            story_id=str(record.get("story_id", "")),
            claim_id=str(record.get("claim_id", "")),
            text=str(record.get("text", "")),
            spine=ClaimSpine.from_mapping(record.get("spine", {})),
            scarce_atom=str(record.get("scarce_atom", "")),
            criterion_proof=frozenset(record.get("criterion_proof", ())),
            counterfactual_ownership=str(record.get("counterfactual_ownership", "")),
            decision_rationale=str(record.get("decision_rationale", "")),
            excluded_adjacent_atoms=tuple(record.get("excluded_adjacent_atoms", ())),
            critical=CriticalVetoes.from_mapping(record.get("critical", {})),
            material_rank=MaterialRank.from_mapping(record.get("material_rank", {})),
            line_cost=record.get("line_cost", 0),
        )


@dataclass(frozen=True)
class PairwiseCase:
    case_id: str
    target: str
    slot_question: str
    incumbent: ClaimCandidate
    challenger: ClaimCandidate
    source_refs: tuple[str, ...] = ()
    expected_verdict: PairwiseVerdict | None = None
    request_keep_both: bool = False
    page_can_fund_both: bool = False

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "PairwiseCase":
        expected = record.get("expected_verdict")
        return cls(
            case_id=str(record.get("case_id", "")),
            target=str(record.get("target", "")),
            slot_question=str(record.get("slot_question", "")),
            incumbent=ClaimCandidate.from_mapping(record.get("incumbent", {})),
            challenger=ClaimCandidate.from_mapping(record.get("challenger", {})),
            source_refs=tuple(record.get("source_refs", ())),
            expected_verdict=PairwiseVerdict(expected) if expected else None,
            request_keep_both=bool(record.get("request_keep_both", False)),
            page_can_fund_both=bool(record.get("page_can_fund_both", False)),
        )


@dataclass(frozen=True)
class PairwiseDecision:
    case_id: str
    verdict: PairwiseVerdict
    reason: str
    incumbent_failures: tuple[str, ...] = ()
    challenger_failures: tuple[str, ...] = ()


def validate_candidate(candidate: ClaimCandidate) -> list[str]:
    errors: list[str] = []
    prefix = candidate.candidate_id or "<missing-candidate-id>"
    for field_name in ("candidate_id", "story_id", "claim_id", "text", "scarce_atom"):
        if not str(getattr(candidate, field_name)).strip():
            errors.append(f"{prefix}: {field_name} is required")
    if candidate.scarce_atom not in SCARCE_ATOMS:
        errors.append(
            f"{prefix}: scarce_atom must be one of {sorted(SCARCE_ATOMS)}"
        )
    for field_name in ("trigger", "mechanism", "outcome"):
        if not str(getattr(candidate.spine, field_name)).strip():
            errors.append(f"{prefix}: spine.{field_name} is required")
    if not candidate.spine.judgment.strip() and not candidate.decision_rationale.strip():
        errors.append(
            f"{prefix}: spine.judgment or decision_rationale is required"
        )
    if not candidate.criterion_proof:
        errors.append(f"{prefix}: criterion_proof is required")
    elif not all(value.strip() for value in candidate.criterion_proof):
        errors.append(f"{prefix}: criterion_proof values must be non-empty")
    if not candidate.counterfactual_ownership.strip():
        errors.append(f"{prefix}: counterfactual_ownership is required")
    for field_name, score in candidate.material_rank.__dict__.items():
        if not isinstance(score, int) or not SCORE_MIN <= score <= SCORE_MAX:
            errors.append(
                f"{prefix}: material_rank.{field_name} must be {SCORE_MIN}-{SCORE_MAX}"
            )
    if not isinstance(candidate.line_cost, int) or candidate.line_cost < 1:
        errors.append(f"{prefix}: line_cost must be a positive integer")
    for field_name, value in candidate.critical.__dict__.items():
        if not isinstance(value, bool):
            errors.append(f"{prefix}: critical.{field_name} must be boolean")
    return errors


def validate_case(case: PairwiseCase) -> list[str]:
    errors: list[str] = []
    prefix = case.case_id or "<missing-case-id>"
    if not case.case_id.strip():
        errors.append("case_id is required")
    if not case.target.strip():
        errors.append(f"{prefix}: target is required")
    if not case.slot_question.strip():
        errors.append(f"{prefix}: slot_question is required")
    if not case.source_refs or not all(ref.strip() for ref in case.source_refs):
        errors.append(f"{prefix}: source_refs must contain non-empty paths")
    errors.extend(validate_candidate(case.incumbent))
    errors.extend(validate_candidate(case.challenger))
    if case.incumbent.candidate_id == case.challenger.candidate_id:
        errors.append(f"{prefix}: incumbent and challenger ids must differ")
    return errors


def validate_cases(cases: tuple[PairwiseCase, ...]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for case in cases:
        errors.extend(validate_case(case))
        if case.case_id in seen_ids:
            errors.append(f"{case.case_id}: duplicate case_id")
        seen_ids.add(case.case_id)
        if case.expected_verdict is None:
            errors.append(f"{case.case_id}: expected_verdict is required for a fixture")
    return errors


def _genuinely_distinct_criterion_proof(case: PairwiseCase) -> bool:
    incumbent_only = case.incumbent.criterion_proof - case.challenger.criterion_proof
    challenger_only = case.challenger.criterion_proof - case.incumbent.criterion_proof
    return bool(incumbent_only and challenger_only)


def decide_pairwise(case: PairwiseCase) -> PairwiseDecision:
    """Choose without averaging away a critical regression.

    Material dimensions use Pareto non-regression: automatic replacement needs
    at least one improvement and no material loss.  Line cost cannot independently
    displace an incumbent except on an exact material tie for the same claim.
    KEEP_BOTH requires explicit request, available page budget, and mutually
    distinct criterion proof.
    """
    errors = validate_case(case)
    if errors:
        raise ValueError("; ".join(errors))

    incumbent_failures = case.incumbent.critical.failures
    challenger_failures = case.challenger.critical.failures
    incumbent_rank = case.incumbent.material_rank.as_tuple()
    challenger_rank = case.challenger.material_rank.as_tuple()
    improves = tuple(
        challenger > incumbent
        for challenger, incumbent in zip(challenger_rank, incumbent_rank)
    )
    regresses = tuple(
        challenger < incumbent
        for challenger, incumbent in zip(challenger_rank, incumbent_rank)
    )
    if incumbent_failures and challenger_failures:
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.HUMAN_REVIEW,
            "both candidates fail at least one critical veto",
            incumbent_failures,
            challenger_failures,
        )
    if challenger_failures:
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.KEEP_INCUMBENT,
            "challenger fails a critical veto",
            incumbent_failures,
            challenger_failures,
        )
    if incumbent_failures:
        if any(regresses):
            return PairwiseDecision(
                case.case_id,
                PairwiseVerdict.HUMAN_REVIEW,
                "incumbent is critically unsafe but challenger creates a material regression",
                incumbent_failures,
                challenger_failures,
            )
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.ACCEPT_CHALLENGER,
            "incumbent fails a critical veto and challenger passes all",
            incumbent_failures,
            challenger_failures,
        )

    if (
        case.request_keep_both
        and case.page_can_fund_both
        and _genuinely_distinct_criterion_proof(case)
    ):
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.KEEP_BOTH,
            "both pass and each uniquely proves a funded criterion",
        )

    if any(regresses) and any(improves):
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.HUMAN_REVIEW,
            "challenger creates a material tradeoff; incumbent remains shipping default",
        )
    if any(regresses):
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.KEEP_INCUMBENT,
            "challenger regresses at least one material dimension",
        )
    if any(improves):
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.ACCEPT_CHALLENGER,
            "challenger Pareto-improves at least one material dimension with no regression",
        )
    if (
        case.challenger.claim_id == case.incumbent.claim_id
        and case.challenger.line_cost < case.incumbent.line_cost
    ):
        return PairwiseDecision(
            case.case_id,
            PairwiseVerdict.ACCEPT_CHALLENGER,
            "material value and claim are tied; challenger uses less page space",
        )
    return PairwiseDecision(
        case.case_id,
        PairwiseVerdict.KEEP_INCUMBENT,
        "challenger has no material win; incumbent wins ties and style-only gains",
    )


def load_pairwise_cases(path: Path = DEFAULT_GOLDEN_PAIR_PATH) -> tuple[PairwiseCase, ...]:
    with path.open(encoding="utf-8") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError(f"{path}: top-level value must be a list")
    return tuple(PairwiseCase.from_mapping(record) for record in records)
