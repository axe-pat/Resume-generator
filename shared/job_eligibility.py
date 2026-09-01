"""
Shared job-eligibility helpers.

These are the existing no-API pre-filters originally used by discovery.
They are intentionally conservative and only catch obvious hard rejects.
"""

from __future__ import annotations

import re
from typing import Any


LANE_A = "A"
LANE_B = "B"
LANE_C = "C"
DISCOVERY_LANES = (LANE_A, LANE_B, LANE_C)
LANE_C_MIN_HOURLY_RATE = 20.0

# ---------------------------------------------------------------------------
# Hard pre-filter — catch obvious immigration rejects without an API call
# ---------------------------------------------------------------------------

HARD_REJECT_PATTERNS = [
    r"us\s+citizen(?:s)?\s+only",
    r"must\s+be\s+a\s+us\s+citizen",
    r"u\.s\.?\s+citizen(?:ship)?\s+(?:is\s+)?required",
    r"green\s+card\s+(?:required|holder)",
    r"permanent\s+resident(?:s)?\s+only",
    r"no\s+(?:cpt|opt)\s+(?:support|sponsorship|accepted)",
    r"cpt\s+(?:is\s+)?not\s+(?:accepted|supported|eligible)",
    r"cannot\s+support\s+(?:cpt|opt)",
    r"including\s+(?:participation\s+in\s+)?(?:curricular\s+practical\s+training|cpt)",
    r"f-?1\s+visa\s+program[s]?\s+(?:are\s+)?not\s+(?:eligible|supported|accepted)",
    r"not\s+open\s+to\s+visa\s+sponsorship.*\bopt\b",
    r"(?:will\s+not|do(?:es)?\s+not|cannot|can't|unable\s+to)"
    r"[^.\n]{0,140}(?:sponsor|provide\s+sponsorship|offer\s+employment)"
    r"[^\n]{0,180}\b(?:f-?1|cpt|(?:stem[- ]?)?opt)\b",
    r"(?:will\s+not|do(?:es)?\s+not|cannot|can't|unable\s+to)"
    r"[^.\n]{0,140}(?:employment\s+authori[sz]ation|immigration[- ]related\s+support)"
    r"[^.\n]{0,180}\b(?:f-?1|cpt|(?:stem[- ]?)?opt)\b",
    r"stem\s+opt.*not\s+(?:eligible|supported|accepted)",
    r"us\s+person.*22\s+c\.?f\.?r",
    r"itar.*us\s+(?:person|citizen)",
    r"permanent(?:ly)?\s+(?:authorized|authorised)\s+to\s+work",
    r"(?:authorized|authorised)\s+to\s+work\s+permanent(?:ly)?(?:\s+without\s+sponsorship)?",
    r"authorized\s+to\s+work.*on\s+a\s+(?:full[- ]time,?\s+)?permanent\s+basis",
    r"security\s+clearance\s+required",
    r"(?:ts|top\s+secret)(?:/sci)?\s+clearance",
    r"must\s+(?:hold|have|possess)\s+(?:an?\s+)?(?:active\s+)?(?:ts|secret|top\s+secret)\s+clearance",
]

COMPILED_HARD_REJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in HARD_REJECT_PATTERNS]

INTERN_SIGNAL = re.compile(
    r"\b(?:intern(?:ship)?|co-op|coop|new\s+grad|associate\s+program"
    r"|recent\s+grad|university\s+grad|entry[- ]level|early\s+career"
    r"|summer\s+program|mba\s+program|rotational\s+program"
    r"|leadership\s+development\s+program)\b",
    re.IGNORECASE,
)
YEARS_REQUIRED = re.compile(
    r"\b([4-9]|\d{2})\+?\s+years?\s+(?:of\s+)?(?:(?:relevant\s+)?experience|PM|product)",
    re.IGNORECASE,
)
INTERNSHIP_TITLE_SIGNAL = re.compile(r"\b(?:intern(?:ship)?|co[- ]?op|coop)\b", re.IGNORECASE)
EXPLICIT_EXPERIENCE_CAP = re.compile(
    r"\b(?P<qualifier>less\s+than|fewer\s+than|under|up\s+to|no\s+more\s+than|"
    r"at\s+most|maximum(?:\s+of)?)\s+"
    r"(?P<years>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"years?\s+(?:of\s+)?(?:professional\s+|full[- ]time\s+|relevant\s+|related\s+)?"
    r"experience\b",
    re.IGNORECASE,
)
CANDIDATE_PROFESSIONAL_EXPERIENCE_YEARS = 5
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

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


# ---------------------------------------------------------------------------
# Discovery-lane metadata and timing policy
# ---------------------------------------------------------------------------

_INTERNSHIP_ROLE_RE = re.compile(r"\b(?:intern(?:ship)?|co-?op|coop)\b", re.I)
_INTERNSHIP_OPENING_RE = re.compile(
    r"\b(?:this|the|our)\s+(?:paid\s+|full[- ]time\s+|part[- ]time\s+)?"
    r"(?:intern(?:ship)?|co-?op)\b|"
    r"\b(?:intern(?:ship)?|co-?op)\s+(?:position|role|program|opportunity)\b|"
    r"\b(?:position|role|opportunity)\s+(?:is\s+|as\s+)?(?:an?\s+)?"
    r"(?:intern(?:ship)?|co-?op)\b",
    re.I,
)
_FULL_TIME_ROLE_RE = re.compile(
    r"\b(?:full[- ]time|permanent\s+(?:role|position)|regular\s+employee)\b",
    re.I,
)
_SUMMER_2027_RE = re.compile(r"\b(?:summer\s+(?:of\s+)?2027|2027\s+summer)\b", re.I)
_SUMMER_INTERNSHIP_RE = re.compile(
    r"\b(?:summer\s+(?:intern(?:ship)?s?|co-?ops?)|"
    r"(?:intern(?:ship)?|co-?op)[^.\n]{0,45}\bsummer\b|"
    r"summer\s+(?:start|program|term|session))\b",
    re.I,
)
_FALL_2026_RE = re.compile(r"\b(?:(?:fall|autumn)\s+2026|2026\s+(?:fall|autumn))\b", re.I)
_FALL_2026_START_RE = re.compile(
    r"\b(?:anticipated\s+)?start(?:ing)?(?:\s+date)?[^.\n]{0,45}"
    r"(?:september|october|november)\s+2026\b|"
    r"\b(?:september|october|november)\s+2026\b[^.\n]{0,45}"
    r"(?:start(?:ing)?|begin(?:s|ning)?|commenc(?:e|es|ing))\b",
    re.I,
)
_OTHER_2027_INTERNSHIP_RE = re.compile(
    r"\b(?:2027[^.\n]{0,45}(?:intern(?:ship)?|co-?op)|"
    r"(?:intern(?:ship)?|co-?op)[^.\n]{0,45}2027)\b",
    re.I,
)
_MID_2027_START_RE = re.compile(
    r"(?:"
    r"(?<!reviewed\s)(?<!applications\s)(?<!interviews\s)\b(?:start(?:ing)?(?:\s+date)?|anticipated\s+start\s+date|begin(?:s|ning)?|commenc(?:e|es|ing)|program\s+start(?:s|ing)?)"
    r"[^.\n]{0,70}\b(?:june|july|august|september|october|november|december|mid[- ]year|fall|autumn)\s+2027\b"
    r"|\b(?:june|july|august|september|october|november|december|fall|autumn)\s+2027\b"
    r"[^.\n]{0,70}\b(?:start(?:ing)?|begin(?:s|ning)?|commenc(?:e|es|ing))\b"
    r"|\b(?:mid|late)[- ]2027\s+(?:start|cohort)\b"
    r")",
    re.I,
)
_PRE_GRADUATION_START_RE = re.compile(
    r"(?:"
    r"(?<!reviewed\s)(?<!applications\s)(?<!interviews\s)\b(?:start(?:ing)?|begin(?:s|ning)?|commenc(?:e|es|ing)|program\s+start(?:s|ing)?)"
    r"[^.\n]{0,70}\b(?:"
    r"(?:january|february|march|april|may)\s+2027|"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+2026"
    r")\b|"
    r"\b(?:"
    r"(?:january|february|march|april|may)\s+2027|"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+2026"
    r")\b[^.\n]{0,70}\b(?:start(?:ing)?|begin(?:s|ning)?|commenc(?:e|es|ing))\b"
    r")",
    re.I,
)
_TITLE_PRE_GRADUATION_COHORT_RE = re.compile(
    r"\b(?:"
    r"2026\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)|"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+2026|"
    r"2027\s+(?:january|february|march|april|may)|"
    r"(?:january|february|march|april|may)\s+2027"
    r")\b",
    re.I,
)
_APPLICATION_ACTIVITY_RE = re.compile(
    r"\b(?:application(?:s)?|interview(?:s|ing)?|review(?:ed|ing)?)\b",
    re.I,
)
_NEW_GRAD_ELIGIBILITY_RE = re.compile(
    r"\b(?:"
    r"new\s+grad(?:uate)?s?|recent\s+grad(?:uate)?s?|"
    r"(?:university|college)\s+grad(?:uate)?s?|"
    r"campus\s+hire|university\s+hires?|entry[- ]level|early\s+career|class\s+of\s+2027|"
    r"graduate\s+program|product\s+management\s+graduate|"
    r"accelerated\s+career\s+development\s+program|"
    r"2027\s+grad(?:uate)?s?|grad(?:uat(?:e|es|ing|ion))[^.\n]{0,120}2027|"
    r"2027[^.\n]{0,120}grad(?:uat(?:e|es|ing|ion))|"
    r"(?:associate|development\s+program|leadership\s+program|rotational\s+program|graduate\s+program)"
    r"[^.\n]{0,60}2027|2027[^.\n]{0,60}"
    r"(?:associate|development\s+program|leadership\s+program|rotational\s+program|graduate\s+program)|"
    r"mba[^.\n]{0,35}(?:leadership\s+development|rotational|graduate)\s+program"
    r")\b",
    re.I,
)
_SUMMER_COHORT_PROGRAM_RE = re.compile(
    r"\bcohorts?\b[^.\n]{0,180}\bsummer\s+start\s+date\b"
    r"[^.\n]{0,45}\b(?:june|july)\b",
    re.I,
)
_IMMEDIATE_START_RE = re.compile(
    r"\b(?:start\s+immediately|immediate\s+start|as\s+soon\s+as\s+possible|"
    r"available\s+to\s+start\s+(?:now|immediately)|hire\s+immediately)\b",
    re.I,
)
_LANE_B_FINANCE_RE = re.compile(
    r"\b(?:finance|financial\s+analyst|investment\s+bank|private\s+equity|"
    r"asset\s+management|wealth\s+management|corporate\s+banking|accounting\s+rotational)\b",
    re.I,
)
_LANE_B_CONSULTING_RE = re.compile(
    r"\b(?:management\s+consultant|strategy\s+consultant|consulting\s+associate|"
    r"associate\s+consultant|business\s+consultant)\b",
    re.I,
)
_TECHNICAL_SOLUTIONS_CONSULTANT_RE = re.compile(
    r"\b(?:(?:associate|technical)\s+)?solutions?\s+consultant\b|"
    r"\b(?:application|delivery)\s+consultant\b",
    re.I,
)
_TECHNICAL_GTM_TITLE_RE = re.compile(
    r"\b(?:forward\s+deployed\s+(?:software\s+)?engineer|solutions?\s+engineer|"
    r"sales\s+engineer|pre[- ]sales\s+engineer|solutions?\s+architect|customer\s+engineer|"
    r"partner\s+engineer|partner\s+solutions?\s+architect|technical\s+account\s+manager|"
    r"implementation\s+(?:engineer|consultant)|deployment\s+(?:engineer|strategist)|"
    r"deployed\s+engineer|(?:application|delivery)\s+consultant|technology\s+seller|"
    r"applied\s+ai\s+engineer|field\s+engineer|value\s+engineer|"
    r"(?:(?:associate|technical)\s+)?solutions?\s+consultant)\b",
    re.I,
)
_INDIVIDUAL_SOFTWARE_ENGINEER_RE = re.compile(
    r"\b(?:software\s+engineer|backend\s+engineer|front[- ]?end\s+engineer|"
    r"full[- ]?stack\s+engineer|software\s+developer)\b",
    re.I,
)

ROLE_FAMILY_TITLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Product",
        re.compile(
            r"\b(?:product\s+manager|associate\s+product\s+manager|apm|technical\s+product\s+manager|"
            r"product\s+management\s+graduate|product\s+pathway|"
            r"product\s+owner|(?:ai|ml|ai/ml|platform|infrastructure|data|developer\s+platform|growth)\s+product\s+manager|"
            r"product\s+analyst|product\s+strategist|strategic\s+product\s+lead|"
            r"product\s+solutions?\s*(?:&|and)\s*operations?|(?:content|creative)\s+product|"
            r"product\s+strategy(?:\s*(?:&|and)\s*operations)?)\b",
            re.I,
        ),
    ),
    (
        "Product Ops / Program",
        re.compile(
            r"\b(?:product\s+operations?\s+(?:manager|associate|intern|graduate)|technical\s+program\s+manager|"
            r"business\s+program\s+manager|program\s+manager)\b",
            re.I,
        ),
    ),
    (
        "Strategy / BizOps",
        re.compile(
            r"\b(?:strategy\s*(?:(?:&|and)\s*)?operations|s&o|business\s+operations|biz\s*ops|"
            r"business\s+planning\s*(?:&|and)\s*operations|bp&o|corporate\s+strategy|"
            r"innovation\s+analyst|"
            r"corporate\s+development|chief\s+of\s+staff|revenue\s+operations|rev\s*ops|"
            r"gtm\s+strategy\s*(?:&|and)\s*operations|growth\s+(?:strategy|ops|operations)|"
            r"(?:operations|ops)\s*(?:&|and)\s*growth|user\s+growth\s+project|special\s+projects|"
            r"strategic\s+partner\s+manager|strategic\s+partnerships?\s+lead|"
            r"(?:ai\s+)?strategy\s+(?:intern|analyst|associate))\b",
            re.I,
        ),
    ),
    ("Technical GTM", _TECHNICAL_GTM_TITLE_RE),
    (
        "Rotational / Leadership",
        re.compile(
            r"\b(?:rotational\s+product\s+manager|leadership\s+development\s+program|"
            r"mba\s+leadership\s+development\s+program|"
            r"product\s+management\s+leadership\s+program|business\s+leadership\s+program|"
            r"technology\s+leadership\s+program|pathways\s+operations\s+manager|"
            r"general\s+management\s+rotational\s+program|graduate\s+rotational\s+program|"
            r"(?:technical|operations|commercial|information\s+technology|it)\s+"
            r"(?:management\s+)?development\s+program|business\s+management\s+associate|"
            r"leadership\s+fellow\s+program)\b",
            re.I,
        ),
    ),
)

ROLE_TITLE_REVIEW_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "broad early-career program",
        re.compile(
            r"\b(?:graduate\s+program|talent\s+accelerator\s+program|"
            r"accelerated\s+career\s+development\s+program|"
            r"early\s+career\s+development\s+program|"
            r"rotational\s+development\s+program|development\s+program\s+associate)\b",
            re.I,
        ),
    ),
)

ROLE_BODY_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "product ownership",
        re.compile(
            r"\b(?:own(?:ership|s|ing)?\s+(?:the\s+)?(?:product|roadmap|feature)|product\s+roadmap|"
            r"product\s+requirements?|\bprd\b|feature\s+prioriti[sz]ation|product\s+decisions?|"
            r"user\s+research|product\s+metrics?|experimentation)\b",
            re.I,
        ),
    ),
    (
        "cross-functional coordination",
        re.compile(
            r"\b(?:cross[- ]functional|partner\s+with\s+(?:engineering|product|design)|"
            r"coordinate\s+(?:across|multiple)\s+(?:engineering|product|business)\s+teams?)\b",
            re.I,
        ),
    ),
    (
        "customer-facing technical work",
        re.compile(
            r"\b(?:customer[- ]facing|work(?:ing)?\s+(?:directly\s+)?with\s+customers?|"
            r"technical\s+discovery|proof\s+of\s+concept|solution\s+design|deploy(?:ment|ing)?\s+(?:for|with)\s+customers?|"
            r"customer\s+implementations?|technical\s+pre[- ]sales)\b",
            re.I,
        ),
    ),
    (
        "data/platform domain",
        re.compile(
            r"\b(?:data\s+platform|developer\s+(?:platform|tools?|experience)|infrastructure\s+platform|"
            r"distributed\s+systems?|backend\s+systems?|apis?|data\s+pipelines?|cloud\s+platform)\b",
            re.I,
        ),
    ),
    (
        "MBA/advanced-degree preference",
        re.compile(r"\b(?:mba|master'?s|advanced\s+degree)\s+(?:preferred|required|candidate|students?)\b", re.I),
    ),
    ("new-grad/2027 timing", _NEW_GRAD_ELIGIBILITY_RE),
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_TOKEN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_TOKEN = (
    rf"(?:{_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,)?\s+20\d{{2}}|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_TOKEN}(?:,)?\s+20\d{{2}}|"
    rf"20\d{{2}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}/\d{{1,2}}/20\d{{2}})"
)
_DEADLINE_RE = re.compile(
    rf"\b(?:application(?:s)?\s+(?:deadline|closure\s+date)|"
    rf"(?:job\s+)?application\s+period\s+closure|"
    rf"application(?:s)?\s+(?:will\s+)?(?:close|closes|due)|apply\s+by|"
    rf"deadline|closing\s+date|accepting\s+applications\s+(?:until|through)|"
    rf"applications?\s+(?:will\s+be\s+)?accepted\s+(?:until|through))"
    rf"\s*(?:is|on|:|-)?\s*({_DATE_TOKEN})",
    re.I,
)
_APPLICATION_WINDOW_RE = re.compile(
    rf"\b(?:application\s+window\s+(?:is\s+)?open|applications?\s+(?:are\s+)?open)"
    rf"\s+(?:from|on)\s+({_DATE_TOKEN})"
    rf"[^.\n]{{0,60}}?\b(?:through|until|to|close(?:s)?(?:\s+on)?)\s+({_DATE_TOKEN})",
    re.I,
)
_KNOWN_PROGRAM_RE = re.compile(
    r"\b(?:apm|associate\s+product\s+manager|rotational\s+program|"
    r"leadership\s+development\s+program|university\s+grad(?:uate)?|"
    r"new\s+grad(?:uate)?\s+program|mba\s+program|rotational\s+product\s+manager|"
    r"product\s+management\s+leadership\s+program|business\s+leadership\s+program|"
    r"technology\s+leadership\s+program|pathways\s+operations\s+manager)\b",
    re.I,
)

_NO_H1B_SPONSORSHIP_RE = re.compile(
    r"\b(?:will\s+not|do(?:es)?\s+not|cannot|can't|unable\s+to)\s+"
    r"(?:(?:provide\s+)?(?:visa|h-?1b|employment)\s+sponsor(?:ship)?|"
    r"sponsor\s+(?:an?\s+)?(?:visa|h-?1b))\b|"
    r"\bno\s+(?:visa|h-?1b)\s+sponsor(?:ship)?\b|"
    r"\b(?:visa|h-?1b)\s+sponsor(?:ship)?\s+(?:is\s+)?not\s+available\b|"
    r"\b(?:this\s+)?(?:role|position|job|opportunity)?\s*(?:is\s+)?not\s+"
    r"(?:eligible|open)\s+for\s+(?:visa|employment|immigration)\s+sponsor(?:ship)?\b",
    re.I,
)
_E_VERIFY_NO_RE = re.compile(
    r"\b(?:not|isn't|is\s+not)\s+(?:an?\s+)?(?:e-?verify|everify)\s+"
    r"(?:employer|participant|enrolled)|\bnot\s+enrolled\s+in\s+e-?verify\b",
    re.I,
)
_E_VERIFY_YES_RE = re.compile(
    r"\b(?:e-?verify|everify)\s+(?:employer|participant|enrolled)|"
    r"\benrolled\s+in\s+e-?verify\b|\bparticipates?\s+in\s+e-?verify\b",
    re.I,
)

_HOURLY_RANGE_RE = re.compile(
    r"\$\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:-|–|—|to)\s*"
    r"\$?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:/\s*|per\s+)?(?:hour|hr)\b",
    re.I,
)
_HOURLY_SINGLE_RE = re.compile(
    r"\$\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:/\s*|per\s+)?(?:hour|hr)\b",
    re.I,
)
_CUSTOMER_SHIFT_RE = re.compile(
    r"\b(?:barista|cashier(?:ing)?|food\s+service|dining\s+(?:hall|services?)|server|"
    r"waitstaff|retail\s+(?:associate|sales)|customer\s+service|front\s+desk|"
    r"recreation\s+attendant|store\s+associate|coffee\s+shop)\b",
    re.I,
)


def _customer_shift_signal(role_title: str, jd_text: str) -> re.Match[str] | None:
    """Return a positive customer-shift signal, ignoring explicit negations."""
    title = role_title or ""
    title_match = _CUSTOMER_SHIFT_RE.search(title)
    if title_match:
        return title_match

    text = (jd_text or "")[:2400]
    for match in _CUSTOMER_SHIFT_RE.finditer(text):
        prefix = text[max(0, match.start() - 90) : match.start()]
        if re.search(
            r"(?:does\s+not|doesn't|will\s+not|won't|not\s+expected\s+to|no)"
            r"[^.!?\n]{0,70}$",
            prefix,
            re.I,
        ):
            continue
        return match
    return None


def normalize_discovery_lane(value: Any, default: str = LANE_A) -> str:
    raw = str(value or "").strip().upper().replace("LANE_", "").replace("LANE ", "")
    return raw if raw in DISCOVERY_LANES else default


def infer_discovery_lane(job: dict[str, Any], default: str = LANE_A) -> str:
    """Infer a lane for legacy rows that predate the explicit ``lane`` column."""
    explicit = str(job.get("lane") or "").strip()
    if explicit:
        return normalize_discovery_lane(explicit, default=default)

    notes = str(job.get("notes") or "")
    legacy_lane = re.search(r"(?:^|\s)lane=([ABC])(?:\s|$)", notes, re.I)
    if legacy_lane:
        return legacy_lane.group(1).upper()
    if re.search(r"(?:^|\s)query_pack=handshake_income_now(?:\s|$)", notes, re.I):
        return LANE_C

    title = str(job.get("role_title") or job.get("title") or "")
    jd_text = str(job.get("jd_text") or job.get("description") or "")
    timing = classify_start_timing(title, jd_text)
    if timing in {
        "summer_2027_internship",
        "summer_internship_unspecified_year",
        "other_2027_internship",
        "fall_2026_internship",
        "internship_unspecified",
    }:
        return LANE_A
    if timing in {
        "immediate_full_time",
        "pre_graduation_full_time",
        "mid_2027_or_later_full_time",
        "new_grad_eligible",
        "full_time_unspecified",
    }:
        return LANE_B
    return normalize_discovery_lane(default)


def classify_start_timing(role_title: str, jd_text: str) -> str:
    text = f"{role_title or ''}\n{jd_text or ''}"
    # Job descriptions routinely list a prior internship as acceptable experience.
    # Treat the posting itself as an internship only when the title says so or the
    # opening explicitly describes this position/program as one.
    opening = (jd_text or "")[:1400]
    timing_opening = (jd_text or "")[:2600]
    is_internship = bool(
        _INTERNSHIP_ROLE_RE.search(role_title or "")
        or _INTERNSHIP_OPENING_RE.search(opening)
    )
    # The JD often lists May 2027 as the candidate's graduation date. Explicit
    # posting season wins over that eligibility text, so a Fall 2026 internship
    # is not accidentally reclassified as a 2027 internship.
    if is_internship and (_FALL_2026_RE.search(text) or _FALL_2026_START_RE.search(text)):
        return "fall_2026_internship"
    if is_internship and _SUMMER_2027_RE.search(text):
        return "summer_2027_internship"
    if is_internship and _SUMMER_INTERNSHIP_RE.search(
        f"{role_title or ''}\n{timing_opening}"
    ):
        return "summer_internship_unspecified_year"
    if is_internship and re.search(r"\b2027\b", role_title or "", re.I):
        return "other_2027_internship"
    if is_internship and _OTHER_2027_INTERNSHIP_RE.search(
        f"{role_title or ''}\n{opening}"
    ):
        return "other_2027_internship"
    if is_internship:
        return "internship_unspecified"
    if _IMMEDIATE_START_RE.search(text):
        return "immediate_full_time"
    mid_start = _MID_2027_START_RE.search(text)
    if mid_start and not _APPLICATION_ACTIVITY_RE.search(
        text[max(0, mid_start.start() - 80) : mid_start.end()]
    ):
        return "mid_2027_or_later_full_time"
    pre_grad_start = _PRE_GRADUATION_START_RE.search(text)
    if (
        pre_grad_start
        and not _APPLICATION_ACTIVITY_RE.search(
            text[max(0, pre_grad_start.start() - 80) : pre_grad_start.end()]
        )
    ) or (
        _TITLE_PRE_GRADUATION_COHORT_RE.search(role_title or "")
        and not re.search(
            r"\b(?:(?:january|february|march|april|may)\s+2027|"
            r"2027\s+(?:january|february|march|april|may))\s+"
            r"(?:grads?|graduates?)\b",
            role_title or "",
            re.I,
        )
    ):
        return "pre_graduation_full_time"
    if _NEW_GRAD_ELIGIBILITY_RE.search(text) or (
        re.search(r"\bprogram\b", role_title or "", re.I)
        and _SUMMER_COHORT_PROGRAM_RE.search(jd_text or "")
    ):
        return "new_grad_eligible"
    if _FULL_TIME_ROLE_RE.search(text):
        return "full_time_unspecified"
    return "unknown"


def pre_filter_discovery_timing(
    role_title: str,
    jd_text: str,
    lane: str,
) -> tuple[bool, str]:
    """Apply start-date rules without treating a bare ``2027`` as eligibility."""
    normalized_lane = normalize_discovery_lane(lane)
    timing = classify_start_timing(role_title, jd_text)

    if timing == "summer_2027_internship":
        return True, "Timing reject — Summer 2027 internship begins after May 2027 graduation"
    if timing == "summer_internship_unspecified_year":
        return True, "Timing reject — Summer internship is outside the Fall 2026 internship lane"
    if timing == "other_2027_internship":
        return True, "Timing reject — 2027 internship is outside the Fall 2026 internship lane"

    if normalized_lane == LANE_B:
        if timing in {"fall_2026_internship", "internship_unspecified"}:
            return True, "Lane B timing reject — internship result is not a 2027 full-time start"
        if timing == "immediate_full_time":
            return True, "Lane B timing reject — immediate-start full-time role"
        if timing == "pre_graduation_full_time":
            return True, "Lane B timing reject — full-time start is before June 2027 graduation availability"
        if timing in {"mid_2027_or_later_full_time", "new_grad_eligible"}:
            return False, ""
        return (
            True,
            "Lane B timing reject — no explicit new-grad eligibility or mid-2027-or-later start",
        )

    if normalized_lane == LANE_A and timing in {
        "immediate_full_time",
        "pre_graduation_full_time",
        "mid_2027_or_later_full_time",
        "new_grad_eligible",
        "full_time_unspecified",
        "unknown",
    }:
        return True, "Lane A timing reject — result is not a Fall 2026 internship"

    return False, ""


def pre_filter_discovery_scope(role_title: str, lane: str) -> tuple[bool, str]:
    """Keep Lane B to the brief's role families: no finance or consulting."""
    if normalize_discovery_lane(lane) != LANE_B:
        return False, ""
    title = role_title or ""
    finance = _LANE_B_FINANCE_RE.search(title)
    if finance:
        return True, f"Lane B scope reject — finance role matched: '{finance.group(0)}'"
    consulting = _LANE_B_CONSULTING_RE.search(title)
    if consulting and not _TECHNICAL_SOLUTIONS_CONSULTANT_RE.search(title):
        return True, f"Lane B scope reject — consulting is campus-channel only: '{consulting.group(0)}'"
    software = _INDIVIDUAL_SOFTWARE_ENGINEER_RE.search(title)
    if software and not _TECHNICAL_GTM_TITLE_RE.search(title):
        return True, f"Lane B scope reject — individual-contributor software engineering: '{software.group(0)}'"
    return False, ""


def classify_role_surface(role_title: str, jd_text: str) -> tuple[str, str, str]:
    """Return (keep/reject/unsure, reason, family) using title hints + body signals."""
    title = role_title or ""
    for family, pattern in ROLE_FAMILY_TITLE_PATTERNS:
        if pattern.search(title):
            return "keep", f"Known role family: {family}", family

    for label, pattern in ROLE_TITLE_REVIEW_PATTERNS:
        if pattern.search(title):
            return "unsure", f"Ambiguous {label}; JD review required", ""

    body_hits = [label for label, pattern in ROLE_BODY_SIGNAL_PATTERNS if pattern.search(jd_text or "")]
    if body_hits:
        reason = "Unknown title with JD signals: " + ", ".join(body_hits)
        return "unsure", reason, ""
    return "reject", "No known role family in title and no target signal in JD body", ""


def _normalize_date_token(value: str) -> str:
    raw = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", str(value or "").strip(), flags=re.I)
    iso_match = re.fullmatch(r"(20\d{2})-(\d{1,2})-(\d{1,2})", raw)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(20\d{2})", raw)
    if slash_match:
        month, day, year = (int(part) for part in slash_match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    month_match = re.fullmatch(
        rf"({_MONTH_TOKEN})\s+(\d{{1,2}}),?\s+(20\d{{2}})",
        raw,
        re.I,
    )
    if month_match:
        month_name, day_text, year_text = month_match.groups()
        month = _MONTHS[month_name.lower()]
        return f"{int(year_text):04d}-{month:02d}-{int(day_text):02d}"
    day_first_match = re.fullmatch(
        rf"(\d{{1,2}})\s+({_MONTH_TOKEN}),?\s+(20\d{{2}})",
        raw,
        re.I,
    )
    if day_first_match:
        day_text, month_name, year_text = day_first_match.groups()
        month = _MONTHS[month_name.lower()]
        return f"{int(year_text):04d}-{month:02d}-{int(day_text):02d}"
    return raw


def extract_application_deadline(jd_text: str) -> tuple[str, str]:
    """Return (normalized deadline/window, matched source text), or empty strings."""
    text = jd_text or ""
    window = _APPLICATION_WINDOW_RE.search(text)
    if window:
        start = _normalize_date_token(window.group(1))
        end = _normalize_date_token(window.group(2))
        return f"{start}/{end}", window.group(0).strip()
    deadline = _DEADLINE_RE.search(text)
    if deadline:
        return _normalize_date_token(deadline.group(1)), deadline.group(0).strip()
    return "", ""


def needs_manual_deadline_lookup(
    role_title: str,
    jd_text: str,
    lane: str,
    application_deadline: str = "",
) -> bool:
    if application_deadline or normalize_discovery_lane(lane) != LANE_B:
        return False
    return bool(_KNOWN_PROGRAM_RE.search(f"{role_title or ''}\n{(jd_text or '')[:1200]}"))


def extract_e_verify_status(jd_text: str, known_status: str = "") -> str:
    known = str(known_status or "").strip().lower()
    if known in {"yes", "no", "unknown"}:
        return known
    text = jd_text or ""
    if _E_VERIFY_NO_RE.search(text):
        return "no"
    if _E_VERIFY_YES_RE.search(text):
        return "yes"
    return "unknown"


def lane_b_soft_flags(jd_text: str, e_verify_status: str = "unknown") -> list[str]:
    flags: list[str] = []
    if _NO_H1B_SPONSORSHIP_RE.search(jd_text or ""):
        flags.append("h1b_sponsorship_unavailable")
    if e_verify_status == "no":
        flags.append("e_verify_not_enrolled")
    elif e_verify_status == "unknown":
        flags.append("e_verify_lookup_needed")
    return flags


def extract_hourly_rate(text: str) -> tuple[float | None, float | None]:
    raw = text or ""
    ranged = _HOURLY_RANGE_RE.search(raw)
    single = _HOURLY_SINGLE_RE.search(raw)
    if ranged and (single is None or ranged.start() <= single.start()):
        low, high = float(ranged.group(1)), float(ranged.group(2))
        return min(low, high), max(low, high)
    if single:
        rate = float(single.group(1))
        return rate, rate
    return None, None


def evaluate_lane_c(
    role_title: str,
    jd_text: str,
    pay_text: str = "",
) -> tuple[bool, str, float | None, float | None]:
    """Thin income-now gate. Weekly hours/duration are deliberately not scored."""
    combined_pay = f"{pay_text or ''}\n{jd_text or ''}"
    low, high = extract_hourly_rate(combined_pay)
    if low is None:
        return False, "Lane C reject — hourly pay rate is not stated", None, None
    if low < LANE_C_MIN_HOURLY_RATE:
        return (
            False,
            f"Lane C reject — hourly floor is ${LANE_C_MIN_HOURLY_RATE:.0f}; stated minimum is ${low:g}",
            low,
            high,
        )
    shift = _customer_shift_signal(role_title, jd_text)
    if shift:
        return (
            False,
            f"Lane C reject — customer-facing shift work matched: '{shift.group(0)}'",
            low,
            high,
        )
    rate_text = f"${low:g}-${high:g}" if high != low else f"${low:g}"
    return True, f"Lane C keep — stated hourly pay is {rate_text}", low, high


_LEGACY_DISCOVERY_NOTE_KEYS = (
    "lane",
    "query_lane",
    "start_timing",
    "application_deadline",
    "deadline_source",
    "deadline_lookup",
    "e_verify",
    "eligibility_flags",
    "discovery_disposition",
    "discovery_reason",
    "role_family",
)


def strip_discovery_note_metadata(notes: str) -> str:
    """Remove only legacy discovery key/value tokens, preserving genuine notes."""
    cleaned = str(notes or "")
    for key in _LEGACY_DISCOVERY_NOTE_KEYS:
        cleaned = re.sub(rf"(?<!\S){re.escape(key)}=\S+", "", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def annotate_discovery_job(job: dict[str, Any], default_lane: str = LANE_A) -> dict[str, Any]:
    """Attach explicit lane/timing/deadline/OPT metadata to a discovery row."""
    lane = infer_discovery_lane(job, default=default_lane)
    title = str(job.get("role_title") or job.get("title") or "")
    jd_text = str(job.get("jd_text") or job.get("description") or "")
    timing = classify_start_timing(title, jd_text)

    provided_deadline = str(job.get("deadline") or job.get("application_deadline") or "").strip()
    if provided_deadline:
        application_deadline = provided_deadline
        deadline_source = str(job.get("deadline_source") or "provided").strip()
    else:
        application_deadline, deadline_match = extract_application_deadline(jd_text)
        deadline_source = "stated" if deadline_match else ""
    manual_deadline = needs_manual_deadline_lookup(
        title,
        jd_text,
        lane,
        application_deadline,
    )
    if manual_deadline and not deadline_source:
        deadline_source = "manual_lookup"

    e_verify_status = ""
    flags: list[str] = []
    if lane == LANE_B:
        e_verify_status = extract_e_verify_status(
            jd_text,
            str(job.get("everify_status") or job.get("e_verify_status") or ""),
        )
        flags = lane_b_soft_flags(jd_text, e_verify_status)
    sponsorship_flag = str(job.get("sponsorship_flag") or "").strip()
    if not sponsorship_flag and "h1b_sponsorship_unavailable" in flags:
        sponsorship_flag = "h1b_sponsorship_unavailable"

    pay_text = str(job.get("pay") or job.get("pay_text") or "")
    hourly_low, hourly_high = extract_hourly_rate(f"{pay_text}\n{jd_text}")

    existing_disposition = str(
        job.get("classification") or job.get("discovery_disposition") or ""
    ).strip().lower()
    if existing_disposition in {"keep", "reject", "unsure"}:
        disposition = existing_disposition
        disposition_reason = str(job.get("discovery_reason") or "").strip()
        role_family = str(job.get("role_family") or "").strip()
    elif lane == LANE_C:
        disposition, disposition_reason, role_family = "keep", "Lane C uses its income-now gate", "Income Now"
    else:
        disposition, disposition_reason, role_family = classify_role_surface(title, jd_text)

    job.update(
        {
            "lane": lane,
            "start_timing": timing,
            "application_deadline": application_deadline,
            "deadline": application_deadline,
            "deadline_source": deadline_source,
            "deadline_lookup": "manual" if manual_deadline else "",
            "e_verify_status": e_verify_status,
            "everify_status": e_verify_status,
            "eligibility_flags": flags,
            "sponsorship_flag": sponsorship_flag,
            "hourly_rate_min": hourly_low,
            "hourly_rate_max": hourly_high,
            "discovery_disposition": disposition,
            "classification": disposition,
            "discovery_reason": disposition_reason,
            "reject_reason": (
                str(job.get("reject_reason") or disposition_reason).strip()
                if disposition in {"reject", "unsure"}
                else ""
            ),
            "role_family": role_family,
        }
    )
    job["notes"] = strip_discovery_note_metadata(str(job.get("notes") or ""))
    return job


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
    if not INTERNSHIP_TITLE_SIGNAL.search(role_title or ""):
        cap_match = EXPLICIT_EXPERIENCE_CAP.search(jd_body)
        if cap_match:
            raw_years = cap_match.group("years").lower()
            stated_years = int(raw_years) if raw_years.isdigit() else _NUMBER_WORDS[raw_years]
            qualifier = re.sub(r"\s+", " ", cap_match.group("qualifier").lower())
            is_exclusive = qualifier in {"less than", "fewer than", "under"}
            exceeds_cap = (
                CANDIDATE_PROFESSIONAL_EXPERIENCE_YEARS >= stated_years
                if is_exclusive
                else CANDIDATE_PROFESSIONAL_EXPERIENCE_YEARS > stated_years
            )
            if exceeds_cap:
                comparator = "<" if is_exclusive else "≤"
                return (
                    True,
                    "Full-time hire has an explicit experience cap "
                    f"({comparator}{stated_years} years; candidate has "
                    f"{CANDIDATE_PROFESSIONAL_EXPERIENCE_YEARS}) — ineligible",
                )
    if (
        not INTERN_SIGNAL.search(role_title or "")
        and not INTERN_SIGNAL.search(jd_body[:600])
        and YEARS_REQUIRED.search(jd_body)
    ):
        return True, "Full-time hire (no internship signal, 4+ years required) — level mismatch"
    return False, ""


def classify_discovery_job_offline(job: dict[str, Any], default_lane: str = LANE_A) -> dict[str, Any]:
    """Replay every deterministic discovery rule without making a model or network call."""
    classified = annotate_discovery_job(dict(job), default_lane=default_lane)
    lane = normalize_discovery_lane(classified.get("lane"), default=default_lane)
    title = str(classified.get("role_title") or classified.get("title") or "")
    jd_text = str(classified.get("jd_text") or classified.get("description") or "")

    if lane == LANE_C:
        eligible, reason, _, _ = evaluate_lane_c(
            title,
            jd_text,
            str(classified.get("pay_text") or classified.get("pay") or ""),
        )
        classification = "keep" if eligible else "reject"
        classified["classification"] = classification
        classified["reject_reason"] = "" if eligible else reason
        return classified

    checks = (
        pre_filter_discovery_timing(title, jd_text, lane),
        pre_filter_discovery_scope(title, lane),
        pre_filter_role_type(title),
        pre_filter_immigration(jd_text),
        pre_filter_full_time_level(title, jd_text),
    )
    for is_reject, reason in checks:
        if is_reject:
            classified["classification"] = "reject"
            classified["reject_reason"] = reason
            return classified

    disposition = str(classified.get("discovery_disposition") or "keep").strip().lower()
    if disposition not in {"keep", "reject", "unsure"}:
        disposition = "unsure"
    classified["classification"] = disposition
    classified["reject_reason"] = (
        str(classified.get("discovery_reason") or "").strip()
        if disposition in {"reject", "unsure"}
        else ""
    )
    return classified


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
