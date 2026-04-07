"""
Shared job-eligibility helpers.

These are the existing no-API pre-filters originally used by discovery.
They are intentionally conservative and only catch obvious hard rejects.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Hard pre-filter — catch obvious immigration rejects without an API call
# ---------------------------------------------------------------------------

HARD_REJECT_PATTERNS = [
    r"us\s+citizen(?:s)?\s+only",
    r"must\s+be\s+a\s+us\s+citizen",
    r"u\.s\.?\s+citizen(?:ship)?\s+required",
    r"green\s+card\s+(?:required|holder)",
    r"permanent\s+resident(?:s)?\s+only",
    r"no\s+(?:cpt|opt)\s+(?:support|sponsorship|accepted)",
    r"cpt\s+(?:is\s+)?not\s+(?:accepted|supported|eligible)",
    r"cannot\s+support\s+(?:cpt|opt)",
    r"including\s+(?:participation\s+in\s+)?(?:curricular\s+practical\s+training|cpt)",
    r"f-?1\s+visa\s+program[s]?\s+(?:are\s+)?not\s+(?:eligible|supported|accepted)",
    r"not\s+open\s+to\s+visa\s+sponsorship.*\bopt\b",
    r"stem\s+opt.*not\s+(?:eligible|supported|accepted)",
    r"us\s+person.*22\s+c\.?f\.?r",
    r"itar.*us\s+(?:person|citizen)",
    r"permanent(?:ly)?\s+(?:authorized|authorised)\s+to\s+work",
    r"authorized\s+to\s+work.*on\s+a\s+(?:full[- ]time,?\s+)?permanent\s+basis",
    r"security\s+clearance\s+required",
    r"(?:ts|top\s+secret)(?:/sci)?\s+clearance",
    r"must\s+(?:hold|have|possess)\s+(?:an?\s+)?(?:active\s+)?(?:ts|secret|top\s+secret)\s+clearance",
]

COMPILED_HARD_REJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in HARD_REJECT_PATTERNS]

INTERN_SIGNAL = re.compile(
    r"\b(?:intern(?:ship)?|co-op|coop|new\s+grad|associate\s+program"
    r"|summer\s+program|mba\s+program|rotational\s+program)\b",
    re.IGNORECASE,
)
YEARS_REQUIRED = re.compile(
    r"\b([4-9]|\d{2})\+?\s+years?\s+(?:of\s+)?(?:(?:relevant\s+)?experience|PM|product)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pre-filter: role-type mismatch — check role_title for obvious non-PM domains
# ---------------------------------------------------------------------------

ROLE_TYPE_REJECT_TITLE_PATTERNS = [
    r"\bsocial\s+media\s+(?:intern|coordinator|specialist|manager|associate)\b",
    r"\b(?:marketing|communications|digital\s+marketing|brand\s+marketing|content\s+marketing|email\s+marketing)\s+(?:intern|coordinator|specialist|associate|assistant)\b",
    r"\bpharmacist\b",
    r"\bpharmacy\s+technician\b",
    r"\b(?:clinical|registered|licensed)\s+(?:nurse|pharmacist|dietitian|therapist)\b",
    r"\bnurse\s+(?:practitioner|manager|coordinator|educator|informatics)\b",
    r"\b(?:physician|surgeon|dentist|optometrist|chiropractor|podiatrist)\b",
    r"\bphysical\s+therapist\b",
    r"\boccupational\s+therapist\b",
    r"\bspeech.language\s+pathologist\b",
    r"\b(?:radiolog|patholog|anesthesiolog|cardiolog|dermatolog|oncolog)(?:y|ist)\b",
    r"\bmedical\s+(?:coder|biller|assistant|transcriptionist|laboratory|records|technician)\b",
    r"\bcertified\s+nursing\s+assistant\b",
    r"\bhealth\s+(?:information|records)\s+(?:technician|specialist|manager)\b",
    r"\b(?:landscape|naval|marine|structural|civil|mechanical|interior|licensed)\s+architect\b",
    r"\barchitect(?:ure)?,?\s+(?:commercial|residential|industrial|mixed.use|urban|campus)\b",
    r"\b(?:facilities|construction|project)\s+(?:architect|superintendent|foreman)\b",
    r"\b(?:electrician|plumber|HVAC\s+technician|welder|machinist|pipefitter)\b",
    r"\bservice\s+technician\b",
    r"\b(?:turfgrass|turf\s+management|landscap(?:er|ing)|grounds(?:keeper|skeeper))\b",
    r"\bhorticult(?:ure|ist|urist)\b",
    r"\b(?:electronics|electrical|mechanical|civil|chemical|aerospace|petroleum|nuclear"
    r"|manufacturing|industrial|validation|process|test)\s+engineer(?:ing)?\b",
    r"\b(?:firmware|embedded|RF|analog|digital|VLSI|ASIC|PCB)\s+engineer(?:ing)?\b",
    r"\b(?:accountant|CPA\b|auditor|tax\s+(?:manager|analyst|associate)|bookkeeper)\b",
    r"\b(?:staff|senior|public)\s+accountant\b",
    r"\b(?:attorney|lawyer|paralegal|legal\s+(?:counsel|associate|secretary|clerk))\b",
    r"\b(?:logistics|freight)\s+(?:coordinator|specialist|broker|analyst\b(?!\s+pm))\b",
    r"\bwarehouse\s+(?:manager|supervisor|associate|operator)\b",
    r"\b(?:inventory|procurement|purchasing)\s+(?:clerk|specialist|associate)\b",
    r"\b(?:recruiter|talent\s+acquisition\s+(?:specialist|coordinator))\b",
    r"\bHR\s+(?:generalist|coordinator|business\s+partner|administrator)\b",
    r"\bhuman\s+resources\s+(?:manager|director|coordinator|specialist)\b",
]

ROLE_TYPE_REJECT_COMPILED = [
    re.compile(p, re.IGNORECASE) for p in ROLE_TYPE_REJECT_TITLE_PATTERNS
]


def pre_filter_role_type(role_title: str) -> tuple[bool, str]:
    if not role_title:
        return False, ""
    for pattern in ROLE_TYPE_REJECT_COMPILED:
        m = pattern.search(role_title)
        if m:
            return True, f"Role-type mismatch — '{m.group(0)}' in title"
    return False, ""


def pre_filter_immigration(jd_text: str) -> tuple[bool, str]:
    if not jd_text:
        return False, ""
    for pattern in COMPILED_HARD_REJECT_PATTERNS:
        match = pattern.search(jd_text)
        if match:
            return True, f"Immigration hard reject — matched: '{match.group(0)}'"
    return False, ""


def infer_role_title_from_jd(jd_text: str) -> str:
    """
    Best-effort role-title extraction for manual jd.txt files.
    Returns the first plausible title-looking non-empty line.
    """
    if not jd_text:
        return ""

    title_signal = re.compile(
        r"\b(?:intern|internship|co-?op|analyst|manager|specialist|coordinator|associate|owner|engineer)\b",
        re.IGNORECASE,
    )
    heading_like = {
        "who we are",
        "what we do",
        "what you'll do",
        "what youll do",
        "what you'll bring",
        "what youll bring",
        "about the job",
        "about us",
        "overview",
        "your impact",
    }

    m = re.search(
        r"(?:seeking|hiring|looking\s+for)\s+(?:an?\s+)?([A-Za-z][A-Za-z0-9&/,+()' .-]{3,120}?"
        r"(?:Intern|Co-?op|Analyst|Manager|Specialist|Coordinator|Associate|Owner|Engineer))\b",
        jd_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" .:-")

    bad_line_starts = (
        "assist ",
        "support ",
        "conduct ",
        "track ",
        "monitor ",
        "prepare ",
        "collaborate ",
        "type of employment",
        "location & schedule",
    )

    for raw in jd_text.splitlines():
        line = raw.strip().strip("#* ").strip()
        if not line:
            continue
        lower = line.lower().rstrip(":")
        if lower in heading_like or lower.startswith(bad_line_starts):
            continue
        if len(line) <= 140 and title_signal.search(line):
            return line

    for raw in jd_text.splitlines():
        line = raw.strip().strip("#* ").strip()
        if not line:
            continue
        lower = line.lower().rstrip(":")
        if lower in heading_like:
            continue
        if len(line) <= 140:
            return line
    return ""


def pre_filter_full_time_level(role_title: str, jd_text: str) -> tuple[bool, str]:
    jd_body = jd_text or ""
    if (
        not INTERN_SIGNAL.search(role_title or "")
        and not INTERN_SIGNAL.search(jd_body[:600])
        and YEARS_REQUIRED.search(jd_body)
    ):
        return True, "Full-time hire (no internship signal, 4+ years required) — level mismatch"
    return False, ""


def evaluate_manual_jd(jd_text: str, role_title: str = "") -> tuple[bool, str, str]:
    """
    Returns (is_reject, reason, inferred_title).
    Used for manual app-dir generation paths that bypass discovery.
    """
    inferred_title = role_title.strip() or infer_role_title_from_jd(jd_text)

    is_reject, reason = pre_filter_role_type(inferred_title)
    if is_reject:
        return True, reason, inferred_title

    is_reject, reason = pre_filter_immigration(jd_text)
    if is_reject:
        return True, reason, inferred_title

    is_reject, reason = pre_filter_full_time_level(inferred_title, jd_text)
    if is_reject:
        return True, reason, inferred_title

    return False, "", inferred_title
