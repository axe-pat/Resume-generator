"""Deterministic, single-variant text checks for resume admission.

This module owns checks that can be decided from one candidate bullet's text
without a JD, story source, sibling variant, assembled page, or model judgment.
It is intentionally separate from :mod:`shared.resume_lint`, whose owner is the
assembled document.  The live resume generator does not import this module.

The rules deliberately distinguish blockers from review proxies.  A regular
expression can prove that a bullet starts with ``Saved`` or contains an em dash;
it cannot prove that two clauses belong to the same causal story.  The latter is
surfaced as a review proxy and remains a structured-critic decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


VARIANT_TEXT_LINT_VERSION = "2026-09-03.1"


class VariantTextSeverity(str, Enum):
    BLOCKER = "blocker"
    REVIEW = "review"


@dataclass(frozen=True)
class VariantTextIssue:
    code: str
    severity: VariantTextSeverity
    message: str


@dataclass(frozen=True)
class VariantTextReport:
    issues: tuple[VariantTextIssue, ...]
    version: str = VARIANT_TEXT_LINT_VERSION

    @property
    def blockers(self) -> tuple[VariantTextIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is VariantTextSeverity.BLOCKER
        )

    @property
    def review_items(self) -> tuple[VariantTextIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is VariantTextSeverity.REVIEW
        )

    @property
    def passed(self) -> bool:
        return not self.blockers


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
_WORD_RE = re.compile(r"\b[A-Za-z]+(?:['’][A-Za-z]+)?\b")
_MARKDOWN_RE = re.compile(
    r"(?:\*\*|__|`|^\s{0,3}#{1,6}\s|^\s*[-*+]\s+|\[[^]]+\]\([^)]+\))",
    re.M,
)
_PERSONAL_PRONOUN_RE = re.compile(r"\b(?:I|me|my|mine|we|our|ours)\b", re.I)
_METRIC_FIRST_RE = re.compile(
    r"^\s*(?:[$€£~±]?\d[\d,.]*(?:%|[KMB]|x|×)?)(?=\s|[:;,])", re.I
)
_DECIMAL_MULTIPLIER_RE = re.compile(r"\b\d+\.\d+\s*(?:x|×)\b", re.I)
_IMPROVED_BY_RE = re.compile(r"^\s*improved\b[^.;]{0,100}\bby\b", re.I)
_ACCEPTING_TRADEOFF_RE = re.compile(r"\baccept(?:ed|ing)?\b[^.;]{0,80}\bfor\b", re.I)
_DURATION_PADDING_RE = re.compile(
    r"\b(?:for|within|over)\s+(?:one|a|1)\s+(?:quarter|month|week|year)\b",
    re.I,
)
_LATE_SUBJECT_RE = re.compile(r"\b(?:which|this|it)\b", re.I)
_PASSIVE_RE = re.compile(
    r"\b(?:was|were|is|are|been|being)\s+"
    r"(?:built|created|designed|developed|improved|reduced|launched|implemented|"
    r"delivered|completed|identified|diagnosed|resolved|increased|decreased)\b",
    re.I,
)
_VAGUE_STAKEHOLDER_RE = re.compile(
    r"\b(?:stakeholders|cross-functional teams?)\b", re.I
)
_GENERIC_MECHANISM_RE = re.compile(
    r"^\s*(?:conducted|performed|completed|ran)\s+"
    r"(?:an?\s+)?(?:behavioral\s+)?(?:analysis|review|research)\b",
    re.I,
)
_VAGUE_MECHANISM_PHRASES = (
    re.compile(r"\bbuilt the stakeholder case\b", re.I),
    re.compile(r"\bdrove (?:a|the) roadmap pivot\b", re.I),
    re.compile(r"\bperformed behavioral analysis\b", re.I),
    re.compile(r"\bdrove cross-functional alignment\b", re.I),
)
_FRAGMENT_OUTCOME_RE = re.compile(
    r"[:;]\s*(?:conversion|revenue|retention|throughput|latency|cost|accuracy|"
    r"stability|supply)\s+(?:up|down|higher|lower|faster|slower)\b",
    re.I,
)

# These are operationally forbidden for new candidates by the voice and
# targeted-swap prompts.  ``Saved`` is included explicitly because it states an
# outcome before the reader can see the decision that earned it; the September
# Ceipal review showed the resulting fake-complexity failure in practice.
_FORBIDDEN_OPENER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("saved", re.compile(r"^\s*saved\b", re.I)),
    ("led-cross-functional", re.compile(r"^\s*led\s+cross-functional\b", re.I)),
    ("led-article", re.compile(r"^\s*led\s+(?:the|a|an)\b", re.I)),
    ("managed", re.compile(r"^\s*managed\b", re.I)),
    ("partnered-with", re.compile(r"^\s*partnered\s+with\b", re.I)),
    ("collaborated-with", re.compile(r"^\s*collaborated\s+with\b", re.I)),
    ("supported", re.compile(r"^\s*supported\b", re.I)),
    ("worked-with", re.compile(r"^\s*worked\s+with\b", re.I)),
    ("coordinated", re.compile(r"^\s*coordinated\b", re.I)),
    (
        "drove-by-aligning",
        re.compile(r"^\s*drove\b[^.;]{0,100}\bby\s+aligning\b", re.I),
    ),
)

_SUBORDINATE_OPENERS = re.compile(
    r"^\s*(?:when|while|although|because|before|after|during|by)\b", re.I
)

_FORBIDDEN_WORDS = (
    "leveraged",
    "utilized",
    "spearheaded",
    "synergies",
    "holistic",
    "actionable",
    "successfully",
    "effectively",
    "various",
    "multiple",
)

_DIAGNOSTIC_OPENERS = frozenset(
    {
        "caught",
        "concluded",
        "diagnosed",
        "found",
        "identified",
        "linked",
        "recognized",
        "reframed",
        "separated",
        "surfaced",
        "synthesized",
        "traced",
    }
)

_PREDICATE_WORDS = frozenset(
    {
        "accepted",
        "advanced",
        "aligned",
        "analyzed",
        "built",
        "blocked",
        "caught",
        "closed",
        "converted",
        "created",
        "cut",
        "defined",
        "designed",
        "diagnosed",
        "drove",
        "enabled",
        "established",
        "expanded",
        "found",
        "generated",
        "grew",
        "halted",
        "identified",
        "improved",
        "introduced",
        "launched",
        "led",
        "linked",
        "onboarded",
        "owned",
        "prioritized",
        "profiled",
        "prototyped",
        "recovered",
        "reduced",
        "reframed",
        "replaced",
        "removed",
        "reshaped",
        "restored",
        "saved",
        "scaled",
        "separated",
        "shipped",
        "standardized",
        "surfaced",
        "traced",
        "traded",
        "turned",
        "unblocked",
        "unified",
        "won",
    }
)

_COHESION_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "through",
        "to",
        "with",
        "after",
        "before",
        "then",
        "that",
        "this",
        "which",
    }
)


def _add(
    issues: list[VariantTextIssue],
    code: str,
    severity: VariantTextSeverity,
    message: str,
) -> None:
    issues.append(VariantTextIssue(code, severity, message))


def _content_tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if token.casefold() not in _COHESION_STOPWORDS
        and token.casefold() not in _PREDICATE_WORDS
        and not token[0].isdigit()
    }


def lint_candidate_variant_text(
    text: str,
    *,
    declared_archetype: str | None = None,
) -> VariantTextReport:
    """Run every deterministic one-bullet rule and all safe coherence proxies.

    Review proxies never claim to decide semantic quality.  They exist to force
    the structured critic to inspect the exact failure mode rather than letting
    a fluent but disconnected sentence pass unnoticed.
    """

    issues: list[VariantTextIssue] = []
    clean = text.strip()
    if not clean:
        _add(issues, "TEXT_EMPTY", VariantTextSeverity.BLOCKER, "Candidate text is empty.")
        return VariantTextReport(tuple(issues))

    if _MARKDOWN_RE.search(clean):
        _add(
            issues,
            "MARKDOWN_PRESENT",
            VariantTextSeverity.BLOCKER,
            "Candidate text must be paste-ready prose, not Markdown.",
        )
    if "—" in clean:
        _add(
            issues,
            "EM_DASH_PRESENT",
            VariantTextSeverity.BLOCKER,
            "Em dashes are forbidden in resume variants.",
        )
    if "(" in clean or ")" in clean:
        _add(
            issues,
            "PARENTHESES_PRESENT",
            VariantTextSeverity.BLOCKER,
            "Parentheses are forbidden in resume variants; integrate the context linearly.",
        )
    if _PERSONAL_PRONOUN_RE.search(clean):
        _add(
            issues,
            "PERSONAL_PRONOUN_PRESENT",
            VariantTextSeverity.BLOCKER,
            "Resume register uses an implied subject, not first-person pronouns.",
        )
    forbidden_words = tuple(
        word for word in _FORBIDDEN_WORDS if re.search(rf"\b{re.escape(word)}\b", clean, re.I)
    )
    if forbidden_words:
        _add(
            issues,
            "FORBIDDEN_WORD_PRESENT",
            VariantTextSeverity.BLOCKER,
            f"Forbidden filler word(s): {', '.join(forbidden_words)}.",
        )

    for label, pattern in _FORBIDDEN_OPENER_PATTERNS:
        if pattern.search(clean):
            _add(
                issues,
                "FORBIDDEN_OR_WEAK_OPENER",
                VariantTextSeverity.BLOCKER,
                f"Candidate starts with forbidden or weak opener pattern {label!r}.",
            )
            break
    if _SUBORDINATE_OPENERS.search(clean):
        opener = _WORD_RE.search(clean)
        _add(
            issues,
            "SUBORDINATE_CLAUSE_OPENER",
            VariantTextSeverity.BLOCKER,
            f"Candidate starts with subordinate context {opener.group(0)!r}; lead with the owned insight, action, scope, or impact.",
        )
    if _GENERIC_MECHANISM_RE.search(clean) or any(
        pattern.search(clean) for pattern in _VAGUE_MECHANISM_PHRASES
    ):
        _add(
            issues,
            "GENERIC_MECHANISM_PHRASE",
            VariantTextSeverity.BLOCKER,
            "Candidate uses a documented generic mechanism instead of a decision or artifact.",
        )
    if _IMPROVED_BY_RE.search(clean):
        _add(
            issues,
            "IMPROVED_BY_OPENER",
            VariantTextSeverity.BLOCKER,
            "'Improved X by Y' buries the owned action; lead with Y.",
        )
    if _ACCEPTING_TRADEOFF_RE.search(clean):
        _add(
            issues,
            "PASSIVE_TRADEOFF_WORDING",
            VariantTextSeverity.BLOCKER,
            "Use an intentional trade-off construction such as 'traded X for Y', not 'accepted X for Y'.",
        )
    if _METRIC_FIRST_RE.search(clean):
        _add(
            issues,
            "DECORATIVE_METRIC_OPENER",
            VariantTextSeverity.BLOCKER,
            "A bare metric cannot lead as decoration; name the attributable outcome or action.",
        )
    if _VAGUE_STAKEHOLDER_RE.search(clean):
        _add(
            issues,
            "VAGUE_STAKEHOLDER_NOUN",
            VariantTextSeverity.BLOCKER,
            "Name the actual functions or decision owners instead of vague stakeholders or cross-functional teams.",
        )
    if _FRAGMENT_OUTCOME_RE.search(clean):
        _add(
            issues,
            "FRAGMENT_LIST_OUTCOME",
            VariantTextSeverity.BLOCKER,
            "Outcome is appended as a fragment list; tie it to the mechanism with a verb.",
        )
    if clean[-1:] not in {".", "!", "?"}:
        _add(
            issues,
            "TERMINAL_PUNCTUATION_MISSING",
            VariantTextSeverity.BLOCKER,
            "Candidate must end with terminal punctuation.",
        )

    opening_match = _WORD_RE.search(clean)
    opening_word = opening_match.group(0).casefold() if opening_match else ""
    normalized_archetype = (declared_archetype or "").casefold().replace("-first", "")
    if (
        opening_word in _DIAGNOSTIC_OPENERS
        and normalized_archetype
        and normalized_archetype != "diagnostic"
    ):
        _add(
            issues,
            "ARCHETYPE_METADATA_MISMATCH",
            VariantTextSeverity.BLOCKER,
            f"Opening verb {opening_word!r} is diagnostic but declared archetype is {declared_archetype!r}.",
        )

    length = len(clean)
    if length < 90 or length > 260:
        _add(
            issues,
            "LENGTH_OUTSIDE_PREFERRED_RANGE",
            VariantTextSeverity.REVIEW,
            f"Candidate is {length} characters; preferred operational range is 90-260 before render measurement.",
        )

    and_count = len(re.findall(r"\band\b", clean, re.I))
    if and_count > 1:
        _add(
            issues,
            "CONJUNCTION_LOAD_HIGH",
            VariantTextSeverity.REVIEW,
            f"Candidate contains {and_count} uses of 'and'; verify the reader is not tracking parallel branches.",
        )
    if _LATE_SUBJECT_RE.search(clean):
        _add(
            issues,
            "LATE_SUBJECT_PROXY",
            VariantTextSeverity.REVIEW,
            "Candidate uses which/this/it; verify every referent resolves without backtracking.",
        )
    if _PASSIVE_RE.search(clean):
        _add(
            issues,
            "PASSIVE_CONSTRUCTION_PROXY",
            VariantTextSeverity.REVIEW,
            "Candidate may bury ownership in passive voice.",
        )
    if _DURATION_PADDING_RE.search(clean):
        _add(
            issues,
            "DURATION_AS_CONTEXT_PROXY",
            VariantTextSeverity.REVIEW,
            "Duration may be specificity without signal; retain only if it measures transformation.",
        )
    if _DECIMAL_MULTIPLIER_RE.search(clean):
        _add(
            issues,
            "FALSE_PRECISION_PROXY",
            VariantTextSeverity.REVIEW,
            "Decimal multiplier may imply false precision; keep only when directly measured.",
        )

    words = [word.casefold() for word in _WORD_RE.findall(clean)]
    predicate_count = sum(word in _PREDICATE_WORDS for word in words)
    if predicate_count >= 5:
        _add(
            issues,
            "PREDICATE_LOAD_HIGH",
            VariantTextSeverity.REVIEW,
            f"Candidate contains at least {predicate_count} action/outcome predicates; verify it is one argument, not compressed fake complexity.",
        )

    # A semicolon should join two beats of one story.  Very low content overlap
    # is not proof of a split argument, but it is a cheap trigger for the critic.
    if clean.count(";") == 1:
        left, right = clean.split(";", 1)
        left_tokens = _content_tokens(left)
        right_tokens = _content_tokens(right)
        union = left_tokens | right_tokens
        overlap = (len(left_tokens & right_tokens) / len(union)) if union else 1.0
        if min(len(left_tokens), len(right_tokens)) >= 4 and overlap < 0.07:
            _add(
                issues,
                "LOW_CLAUSE_COHESION_PROXY",
                VariantTextSeverity.REVIEW,
                "The two beats share almost no content anchors; the critic must prove they are one causal path.",
            )
    elif clean.count(";") > 1:
        _add(
            issues,
            "TOO_MANY_PRIMARY_PAUSES",
            VariantTextSeverity.REVIEW,
            "Candidate has more than one semicolon; verify the intended two-beat rhythm.",
        )

    return VariantTextReport(tuple(issues))


def issue_codes(
    report: VariantTextReport,
    severity: VariantTextSeverity | None = None,
) -> set[str]:
    return {
        issue.code
        for issue in report.issues
        if severity is None or issue.severity is severity
    }
