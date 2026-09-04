"""Deterministic integrity checks for resume-generation queue inputs.

The preflight is deliberately independent of the queue reader and generation
runner.  Callers provide a stable key, the advertised role title, and the JD
text.  The module then reports input-integrity failures without changing queue
state or trying to repair source material.

The checks are conservative by design:

* missing or clearly truncated JDs block generation;
* short but role-specific summaries warn instead of blocking;
* normalized-exact JD bodies block only when their role titles are materially
  different (location-only title suffixes are ignored);
* title/JD mismatch blocks only on an explicit employment-type contradiction;
  low semantic overlap is a warning for human or upstream review.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing import Iterable, Mapping


class PreflightStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


_STATUS_RANK = {
    PreflightStatus.PASS: 0,
    PreflightStatus.WARN: 1,
    PreflightStatus.BLOCK: 2,
}


@dataclass(frozen=True)
class QueueInput:
    """One generation candidate, detached from any queue-file format."""

    key: str
    role_title: str
    jd_text: str | None
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_metadata(
        cls,
        *,
        key: str,
        metadata: Mapping[str, object],
        jd_text: str | None,
    ) -> "QueueInput":
        title = next(
            (
                str(metadata.get(name) or "").strip()
                for name in ("role_title", "title", "job_title")
                if str(metadata.get(name) or "").strip()
            ),
            "",
        )
        return cls(key=key, role_title=title, jd_text=jd_text, metadata=metadata)


@dataclass(frozen=True)
class QueuePreflightPolicy:
    """Thresholds for distinguishing unusable JDs from terse summaries."""

    block_below_chars: int = 300
    block_below_words: int = 35
    require_role_content_below_chars: int = 600
    warn_below_chars: int = 1000
    warn_below_words: int = 110
    materially_different_title_jaccard: float = 0.50


DEFAULT_POLICY = QueuePreflightPolicy()


@dataclass(frozen=True)
class QueuePreflightRecord:
    status: PreflightStatus
    code: str
    message: str
    job_keys: tuple[str, ...]
    details: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "code": self.code,
            "message": self.message,
            "job_keys": list(self.job_keys),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class QueuePreflightReport:
    records: tuple[QueuePreflightRecord, ...]

    @property
    def status(self) -> PreflightStatus:
        return max(
            (record.status for record in self.records),
            key=_STATUS_RANK.__getitem__,
            default=PreflightStatus.PASS,
        )

    @property
    def blockers(self) -> tuple[QueuePreflightRecord, ...]:
        return tuple(record for record in self.records if record.status is PreflightStatus.BLOCK)

    @property
    def warnings(self) -> tuple[QueuePreflightRecord, ...]:
        return tuple(record for record in self.records if record.status is PreflightStatus.WARN)

    @property
    def passes(self) -> tuple[QueuePreflightRecord, ...]:
        return tuple(record for record in self.records if record.status is PreflightStatus.PASS)

    def records_for(self, key: str) -> tuple[QueuePreflightRecord, ...]:
        return tuple(record for record in self.records if key in record.job_keys)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "records": [record.as_dict() for record in self.records],
        }


_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", re.I)

_ROLE_CONTENT_RE = re.compile(
    r"\b(?:"
    r"responsibilit(?:y|ies)|qualifications?|requirements?|what\s+you(?:'|’)ll\s+do|"
    r"what\s+you\s+will\s+do|you(?:'|’)ll\s+(?:own|build|lead|work|manage|design)|"
    r"you\s+will\s+(?:own|build|lead|work|manage|design)|the\s+role|this\s+role|"
    r"the\s+opportunity|what\s+we(?:'|’)re\s+looking\s+for|who\s+we(?:'|’)re\s+looking\s+for|"
    r"work\s+includes?|key\s+(?:activities|duties)|day[- ]to[- ]day|"
    r"responsible\s+for|requires?|supports?\s+(?:the\s+)?(?:sale|delivery|operation|team)"
    r")\b",
    re.I,
)

_TITLE_INTERNSHIP_RE = re.compile(r"\b(?:intern(?:ship)?|co[- ]?op|coop)\b", re.I)
_TITLE_NON_INTERNSHIP_ROLE_RE = re.compile(
    r"\b(?:full[- ]?time|new\s+grad(?:uate)?|graduate\s+program|launch\s+program|"
    r"development\s+program|engineer|analyst|consultant|manager|associate|specialist|"
    r"director|owner|lead)\b",
    re.I,
)
_EXPLICIT_INTERNSHIP_JD_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:this|the|our)\s+(?:first[- ]ever\s+)?(?:mba\s+)?summer\s+internship\b",
        r"\b(?:this|the|our)\s+(?:paid\s+|full[- ]time\s+|part[- ]time\s+)?internship\b",
        r"\binternship\s+will\s+(?:take\s+place|run|begin|start)\b",
        r"\b(?:join|hire|hiring|seeking|looking\s+for)\b[^.\n]{0,80}"
        r"\b(?:summer\s+)?intern(?:ship)?\b",
        r"\bcurrent\s+full[- ]time\s+mba\s+student\b[^.\n]{0,120}"
        r"\bsummer\s+internship\s+experience\b",
    )
)

_TITLE_NOISE = {
    "a",
    "an",
    "and",
    "at",
    "class",
    "development",
    "entry",
    "for",
    "full",
    "graduate",
    "graduates",
    "grad",
    "in",
    "intern",
    "internship",
    "junior",
    "leadership",
    "level",
    "new",
    "of",
    "part",
    "program",
    "programme",
    "rotational",
    "rotation",
    "senior",
    "spring",
    "summer",
    "the",
    "time",
    "to",
    "winter",
    "fall",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.casefold().split())


def _words(value: str) -> tuple[str, ...]:
    return tuple(_WORD_RE.findall(_normalize_text(value)))


def _title_base(value: str) -> str:
    """Drop a conventional location suffix without guessing city names."""
    return value.split("|", 1)[0].strip()


def _title_tokens(value: str) -> frozenset[str]:
    tokens = {
        token
        for token in _words(_title_base(value))
        if token not in _TITLE_NOISE and not token.isdigit()
    }
    return frozenset(tokens)


def _titles_materially_different(
    titles: Iterable[str],
    policy: QueuePreflightPolicy,
) -> bool:
    bases = {_normalize_text(_title_base(title)) for title in titles}
    if len(bases) <= 1:
        return False

    token_sets = [_title_tokens(title) for title in titles]
    for left, right in combinations(token_sets, 2):
        if not left or not right:
            # Different non-empty normalized bases with no usable functional
            # tokens are ambiguous; warn via duplicate detection rather than
            # silently accepting the collision.
            return True
        similarity = len(left & right) / len(left | right)
        if similarity < policy.materially_different_title_jaccard:
            return True
    return False


def _explicit_internship_mismatch(role_title: str, jd_text: str) -> bool:
    if _TITLE_INTERNSHIP_RE.search(role_title or ""):
        return False
    if not _TITLE_NON_INTERNSHIP_ROLE_RE.search(role_title or ""):
        return False
    # Scraped pages can append recommendations, employee posts, and other roles.
    # A late mention of somebody else's internship is not evidence about the
    # advertised job, so only the primary description window can block.
    primary_description = (jd_text or "")[:8000]
    return any(pattern.search(primary_description) for pattern in _EXPLICIT_INTERNSHIP_JD_PATTERNS)


def _record(
    status: PreflightStatus,
    code: str,
    message: str,
    *job_keys: str,
    details: Mapping[str, object] | None = None,
) -> QueuePreflightRecord:
    return QueuePreflightRecord(
        status=status,
        code=code,
        message=message,
        job_keys=tuple(job_keys),
        details=details or {},
    )


def preflight_queue(
    inputs: Iterable[QueueInput],
    policy: QueuePreflightPolicy = DEFAULT_POLICY,
) -> QueuePreflightReport:
    """Validate source integrity and return pass/warn/block records.

    A pass record is emitted only for an input with no warning or blocker.
    The function performs no I/O and never modifies the supplied metadata.
    """

    jobs = tuple(inputs)
    if len({job.key for job in jobs}) != len(jobs):
        raise ValueError("QueueInput.key must be unique within one preflight run")

    records: list[QueuePreflightRecord] = []
    affected: set[str] = set()
    usable_bodies: dict[str, list[QueueInput]] = defaultdict(list)

    for job in jobs:
        text = str(job.jd_text or "").strip()
        if not text:
            records.append(
                _record(
                    PreflightStatus.BLOCK,
                    "JD_MISSING",
                    "Job description is missing or blank.",
                    job.key,
                )
            )
            affected.add(job.key)
            continue

        char_count = len(text)
        word_count = len(_words(text))
        role_specific = bool(_ROLE_CONTENT_RE.search(text))
        truncated = (
            char_count < policy.block_below_chars
            or word_count < policy.block_below_words
            or (
                char_count < policy.require_role_content_below_chars
                and not role_specific
            )
        )
        if truncated:
            records.append(
                _record(
                    PreflightStatus.BLOCK,
                    "JD_TRUNCATED",
                    "Job description is too short or lacks role-specific content.",
                    job.key,
                    details={
                        "characters": char_count,
                        "words": word_count,
                        "role_content_detected": role_specific,
                    },
                )
            )
            affected.add(job.key)
        elif char_count < policy.warn_below_chars or word_count < policy.warn_below_words:
            records.append(
                _record(
                    PreflightStatus.WARN,
                    "JD_THIN",
                    "Job description is usable but unusually short; confirm it is complete.",
                    job.key,
                    details={"characters": char_count, "words": word_count},
                )
            )
            affected.add(job.key)

        # Even a thin-but-usable body can reveal duplicate or title conflicts.
        # A clearly truncated body cannot support those comparisons reliably.
        if not truncated:
            usable_bodies[_normalize_text(text)].append(job)

        employment_mismatch = not truncated and _explicit_internship_mismatch(
            job.role_title,
            text,
        )
        if employment_mismatch:
            records.append(
                _record(
                    PreflightStatus.BLOCK,
                    "TITLE_EMPLOYMENT_TYPE_MISMATCH",
                    "Advertised title is non-internship, but the JD explicitly "
                    "describes an internship.",
                    job.key,
                    details={"role_title": job.role_title},
                )
            )
            affected.add(job.key)

        title_tokens = _title_tokens(job.role_title)
        if (
            not truncated
            and not employment_mismatch
            and len(title_tokens) >= 2
            and not (title_tokens & set(_words(text)))
        ):
            records.append(
                _record(
                    PreflightStatus.WARN,
                    "TITLE_JD_LOW_OVERLAP",
                    "Role title has no meaningful token overlap with the JD; "
                    "verify the source pairing.",
                    job.key,
                    details={"role_title": job.role_title, "title_tokens": sorted(title_tokens)},
                )
            )
            affected.add(job.key)

    for duplicate_jobs in usable_bodies.values():
        if len(duplicate_jobs) < 2:
            continue
        titles = [job.role_title for job in duplicate_jobs]
        if not _titles_materially_different(titles, policy):
            continue
        keys = tuple(job.key for job in duplicate_jobs)
        records.append(
            _record(
                PreflightStatus.BLOCK,
                "JD_DUPLICATE_DIFFERENT_TITLES",
                "Exact JD body is attached to materially different role titles.",
                *keys,
                details={"role_titles": titles},
            )
        )
        affected.update(keys)

    for job in jobs:
        if job.key not in affected:
            records.append(
                _record(
                    PreflightStatus.PASS,
                    "PREFLIGHT_PASS",
                    "JD input passed deterministic integrity checks.",
                    job.key,
                )
            )

    records.sort(
        key=lambda record: (
            -_STATUS_RANK[record.status],
            record.job_keys,
            record.code,
        )
    )
    return QueuePreflightReport(records=tuple(records))


__all__ = [
    "DEFAULT_POLICY",
    "PreflightStatus",
    "QueueInput",
    "QueuePreflightPolicy",
    "QueuePreflightRecord",
    "QueuePreflightReport",
    "preflight_queue",
]
