#!/usr/bin/env python3
"""
startup_apply_pipeline.py
-------------------------
Separate startup-apply discovery lane for ResumeGenerator v1.

Purpose:
  - discover apply-ready startup roles from startup-focused public sources
  - score them with the same fit-score system used by discovery
  - write them into discovery/jobs.xlsx with startup-specific source tags

This intentionally stays separate from linkedin_live.py for now:
  - same jobs.xlsx
  - same fit score + status model
  - different source adapters and failure modes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup

_HERE = Path(__file__).parent
_ROOT = _HERE.parent
_REPO_ROOT = _ROOT.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO_ROOT))

import jobs  # noqa: E402
from shared.job_eligibility import pre_filter_role_type  # noqa: E402

from scorer import _load_api_key, score_batch  # noqa: E402

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not found. Run: pip install anthropic")
    sys.exit(1)


LOGS_DIR = _HERE / "logs"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_LIMIT_COMPANIES = 12
DEFAULT_LIMIT_JOBS = 30
A16Z_PAGE_SIZE = 50
A16Z_MAX_PAGES = 6
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 ResumeGeneratorStartupApply/0.1"
)

_TARGET_ROLE_PATTERNS = [
    re.compile(r"\b(?:associate\s+)?product\s+manager\b", re.I),
    re.compile(r"\bapm\b", re.I),
    re.compile(r"\bproduct\s+ops?\b", re.I),
    re.compile(r"\bproduct\s+operations\b", re.I),
    re.compile(r"\bproduct\s+owner\b", re.I),
    re.compile(r"\bgrowth\s+product\b", re.I),
    re.compile(
        r"\b(?:growth\s+(?:strateg(?:y|ic)|ops|operations)|"
        r"user\s+growth\s+(?:strateg(?:y|ic)|ops|operations|project)|"
        r"(?:strateg(?:y|ic)|ops|operations)\s*(?:&|and)\s*growth|"
        r"growth\s*(?:&|and)\s*(?:strateg(?:y|ic)|ops|operations))\b",
        re.I,
    ),
    re.compile(r"\bstrategy\b", re.I),
    re.compile(r"\bstrategic\s+operations\b", re.I),
    re.compile(r"\bstrategic\s+finance\b", re.I),
    re.compile(r"\bbusiness\s+operations\b", re.I),
    re.compile(r"\bbiz\s*ops\b", re.I),
    re.compile(r"\bbizops\b", re.I),
    re.compile(r"\bprogram\s+manager\b", re.I),
    re.compile(r"\bprogram\s+lead\b", re.I),
    re.compile(r"\bchief\s+of\s+staff\b", re.I),
    re.compile(r"\bfounder'?s?\s+associate\b", re.I),
    re.compile(r"\bfounding\s+operator\b", re.I),
]

_SENIORITY_SKIP_PATTERNS = [
    re.compile(r"\b(?:staff|principal|director|vp|head)\b", re.I),
]

_EXTRA_SKIP_TITLE_PATTERNS = [
    re.compile(r"\bsoftware\s+engineer\b", re.I),
    re.compile(r"\bdata\s+scientist\b", re.I),
    re.compile(r"\bmachine\s+learning\b", re.I),
    re.compile(r"\bresearch\s+engineer\b", re.I),
    re.compile(r"\bdeveloper\s+advocate\b", re.I),
    re.compile(r"\bsolutions?\s+architect\b", re.I),
    re.compile(r"\b(?:sales|account\s+executive|customer\s+success)\b", re.I),
    re.compile(r"\bmarketing\b", re.I),
    re.compile(r"\blegal\b", re.I),
    re.compile(r"\brecruit(?:er|ing)\b", re.I),
    re.compile(r"\bfinance\b", re.I),
    re.compile(r"\bcounsel\b", re.I),
]

_EARLY_CAREER_PATTERNS = [
    re.compile(r"\b(intern|internship|co-?op|coop)\b", re.I),
    re.compile(r"\b(new grad|graduate|recent grad|early career)\b", re.I),
    re.compile(r"\b(entry level|internship)\b", re.I),
    re.compile(r"\bassociate product manager\b", re.I),
    re.compile(r"\bapm\b", re.I),
    re.compile(r"\bproduct manager i\b", re.I),
    re.compile(r"\bpm i\b", re.I),
    re.compile(r"\bleadership program\b", re.I),
    re.compile(r"\brotational\b", re.I),
]


@dataclass(frozen=True)
class StartupApplySourceDefinition:
    source_id: str
    label: str
    source_tag: str
    adapter: str
    seed_urls: tuple[str, ...]


@dataclass(frozen=True)
class YcCompanyCard:
    name: str
    company_url: str
    jobs_url: str
    description: str = ""
    batch: str = ""
    location: str = ""


@dataclass(frozen=True)
class BuiltInCompanyCard:
    name: str
    company_url: str
    jobs_url: str
    description: str = ""
    categories: str = ""
    location_or_offices: str = ""
    employee_count: str = ""


@dataclass(frozen=True)
class BuiltInJobCard:
    company: str
    company_url: str
    detail_url: str
    title: str
    list_url: str = ""
    location: str = ""
    posted_text: str = ""
    seniority: str = ""
    summary: str = ""


@dataclass(frozen=True)
class StartupJobCandidate:
    company: str
    role_title: str
    location: str
    url: str
    source: str
    source_id: str
    jd_text: str
    notes: str
    date_posted: str = ""
    list_url: str = ""


@dataclass(frozen=True)
class A16zBoardJob:
    company: str
    role_title: str
    location: str
    url: str
    source_id: str
    date_posted: str = ""
    min_years_exp: int | None = None
    seniorities: tuple[str, ...] = ()
    company_stage: str = ""


SOURCE_REGISTRY = [
    StartupApplySourceDefinition(
        source_id="yc_sf_bay_hiring",
        label="YC SF Bay Area hiring startups",
        source_tag="yc_startup_jobs",
        adapter="yc_company_directory",
        seed_urls=("https://www.ycombinator.com/companies/location/san-francisco-bay-area/hiring",),
    ),
    StartupApplySourceDefinition(
        source_id="yc_los_angeles",
        label="YC Los Angeles startups",
        source_tag="yc_startup_jobs",
        adapter="yc_company_directory",
        seed_urls=("https://www.ycombinator.com/companies/location/los-angeles",),
    ),
    StartupApplySourceDefinition(
        source_id="builtin_la_job_lists",
        label="Built In LA startup job lists",
        source_tag="builtin_startup_jobs",
        adapter="builtin_job_lists",
        seed_urls=(
            "https://www.builtinla.com/jobs/product/entry-level",
            "https://www.builtinla.com/jobs/product",
            "https://www.builtinla.com/jobs/internships",
        ),
    ),
    StartupApplySourceDefinition(
        source_id="builtin_sf_job_lists",
        label="Built In SF startup job lists",
        source_tag="builtin_startup_jobs",
        adapter="builtin_job_lists",
        seed_urls=(
            "https://www.builtinsf.com/jobs/product/entry-level",
            "https://www.builtinsf.com/jobs/product",
            "https://www.builtinsf.com/jobs/internships",
        ),
    ),
    StartupApplySourceDefinition(
        source_id="a16z_job_board",
        label="a16z portfolio jobs",
        source_tag="a16z_startup_jobs",
        adapter="a16z_job_board",
        seed_urls=("https://jobs.a16z.com/jobs",),
    ),
]


def _fetch_text(url: str, timeout_seconds: int = 20) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _post_json(url: str, payload: dict, timeout_seconds: int = 25) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _canonicalize_builtin_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.netloc in {"www.builtinsf.com", "www.builtinla.com"} and parsed.path.startswith("/job/"):
        return urlunsplit((parsed.scheme or "https", "builtin.com", parsed.path, parsed.query, parsed.fragment))
    return url


def _parse_employee_count(value: str) -> int | None:
    raw = _clean_text(value)
    if not raw:
        return None
    match = re.search(r"([\d,]+)", raw)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _text_segments(html: str) -> list[dict[str, str]]:
    from html.parser import HTMLParser

    class _SegmentParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self._current_href: str | None = None
            self._current_link_text: list[str] = []
            self._ignored_depth = 0
            self.segments: list[dict[str, str]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            name = tag.lower()
            if name in {"script", "style"}:
                self._ignored_depth += 1
                return
            if self._ignored_depth:
                return
            if name == "a":
                self._current_href = dict(attrs).get("href")
                self._current_link_text = []

        def handle_endtag(self, tag: str) -> None:
            name = tag.lower()
            if name in {"script", "style"} and self._ignored_depth:
                self._ignored_depth -= 1
                return
            if self._ignored_depth:
                return
            if name == "a" and self._current_href is not None:
                text = _clean_text(" ".join(self._current_link_text))
                self.segments.append({"kind": "link", "text": text, "href": self._current_href})
                self._current_href = None
                self._current_link_text = []

        def handle_data(self, data: str) -> None:
            if self._ignored_depth:
                return
            text = _clean_text(data)
            if not text:
                return
            if self._current_href is not None:
                self._current_link_text.append(text)
                return
            self.segments.append({"kind": "text", "text": text})

    parser = _SegmentParser()
    parser.feed(html)
    return parser.segments


def _url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode()).hexdigest()


def _next_row_id(df: pd.DataFrame) -> int:
    try:
        numeric_ids = pd.to_numeric(df["id"], errors="coerce").dropna()
        return int(numeric_ids.max() + 1) if not numeric_ids.empty else 1
    except Exception:
        return 1


def _rows_from_jobs(candidates: list[dict], start_id: int) -> list[dict]:
    rows: list[dict] = []
    for offset, job_dict in enumerate(candidates):
        row = {column: "" for column in jobs.COLUMNS}
        row.update(
            {
                "id": start_id + offset,
                "date_found": datetime.now().strftime("%Y-%m-%d"),
                "date_posted": str(job_dict.get("date_posted") or ""),
                "company": str(job_dict.get("company") or ""),
                "role_title": str(job_dict.get("role_title") or ""),
                "role_type": str(job_dict.get("role_type") or ""),
                "location": str(job_dict.get("location") or ""),
                "url": str(job_dict.get("url") or ""),
                "url_hash": str(job_dict.get("url_hash") or ""),
                "source": str(job_dict.get("source") or ""),
                "fit_score": job_dict.get("fit_score") if job_dict.get("fit_score") is not None else "",
                "fit_rationale": str(job_dict.get("fit_rationale") or ""),
                "status": str(job_dict.get("status") or ""),
                "jd_text": str(job_dict.get("jd_text") or ""),
                "notes": str(job_dict.get("notes") or ""),
            }
        )
        rows.append(row)
    return rows


def _is_target_startup_role(title: str) -> bool:
    title = (title or "").strip()
    if not title:
        return False
    rejected, _ = pre_filter_role_type(title)
    if rejected:
        return False
    if any(pattern.search(title) for pattern in _SENIORITY_SKIP_PATTERNS):
        return False
    if any(pattern.search(title) for pattern in _EXTRA_SKIP_TITLE_PATTERNS):
        return False
    return any(pattern.search(title) for pattern in _TARGET_ROLE_PATTERNS)


def _has_early_career_signal(*values: str) -> bool:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        if any(pattern.search(text) for pattern in _EARLY_CAREER_PATTERNS):
            return True
    return False


def _generic_page_text(url: str) -> str:
    try:
        html = _fetch_text(url)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    body = soup.body or soup
    text = _clean_text(body.get_text("\n", strip=True))
    if not text:
        return ""
    parts = [part for part in [title, text] if part]
    return "\n\n".join(parts).strip()


def _a16z_structured_job_text(job: dict) -> str:
    def _labels(items) -> str:
        values: list[str] = []
        for item in (items or []):
            if isinstance(item, dict):
                value = _clean_text(str(item.get("label") or item.get("value") or ""))
            else:
                value = _clean_text(str(item))
            if value:
                values.append(value)
        return ", ".join(values)

    salary = job.get("salary") or {}
    salary_min = salary.get("minValue")
    salary_max = salary.get("maxValue")
    salary_currency = ((salary.get("currency") or {}).get("value") or "")
    salary_period = ((salary.get("period") or {}).get("value") or "")
    salary_text = ""
    if salary_min or salary_max:
        salary_text = f"{salary_currency} {salary_min or '?'} - {salary_max or '?'} per {salary_period or 'period'}".strip()

    lines = [
        _clean_text(str(job.get("title") or "")),
        _clean_text(str(job.get("companyName") or "")),
        f"Locations: {_clean_text(', '.join(str(value) for value in (job.get('locations') or []) if str(value).strip()))}",
        f"Departments: {_labels(job.get('departments'))}",
        f"Job Functions: {_labels(job.get('jobFunctions'))}",
        f"Seniority: {_labels(job.get('jobSeniorities'))}",
        f"Experience: min={job.get('minYearsExp')} max={job.get('maxYearsExp')}",
        f"Company Stage: {_labels(job.get('stages'))}",
        f"Markets: {_labels(job.get('markets'))}",
        f"Salary: {salary_text}",
        f"Required Skills: {_labels(job.get('requiredSkills'))}",
        f"Preferred Skills: {_labels(job.get('preferredSkills'))}",
        f"Skills: {_labels(job.get('skills'))}",
        f"Remote: {bool(job.get('remote'))} | Hybrid: {bool(job.get('hybrid'))}",
        f"Apply URL: {_clean_text(str(job.get('applyUrl') or job.get('url') or ''))}",
    ]
    return "\n".join(line for line in lines if _clean_text(line)).strip()


def _post_process_scored_jobs(scored_jobs: list[dict]) -> list[dict]:
    for job_dict in scored_jobs:
        decision = str(job_dict.get("decision") or "").strip().lower()
        fit_score = job_dict.get("fit_score")
        if decision == "reject" or fit_score is None:
            job_dict["status"] = "skipped"
            continue
        if fit_score >= 7.0:
            job_dict["status"] = "queued"
        elif fit_score >= 5.8:
            job_dict["status"] = "review"
        else:
            job_dict["status"] = "skipped"
    return scored_jobs


def _build_notes(
    *,
    track: str,
    source_id: str,
    company_summary: str = "",
    apply_url: str = "",
    company_url: str = "",
    list_url: str = "",
) -> str:
    lines = [f"track={track}", f"startup_source_id={source_id}"]
    if list_url:
        lines.append(f"list_url={list_url}")
    if company_url:
        lines.append(f"company_url={company_url}")
    if apply_url:
        lines.append(f"apply_url={apply_url}")
    if company_summary:
        lines.append(f"company_summary={company_summary}")
    return "\n".join(lines)


def _parse_yc_listing_page(html: str, page_url: str) -> list[YcCompanyCard]:
    metadata_pattern = re.compile(
        r"^(?P<name>.+?) Y Combinator Logo "
        r"(?P<batch>[^•]+)"
        r"(?: • (?P<status>[^•]+))?"
        r"(?: • (?P<team_size>[^•]+? employees))?"
        r"(?: • (?P<location>.+))?$"
    )
    segments = _text_segments(html)
    cards: list[YcCompanyCard] = []
    index = 0
    while index < len(segments):
        segment = segments[index]
        if segment.get("kind") != "link":
            index += 1
            continue
        link_text = segment.get("text", "")
        if link_text.startswith("Image:") or "Y Combinator Logo" not in link_text:
            index += 1
            continue
        match = metadata_pattern.match(link_text)
        if not match:
            index += 1
            continue
        company_url = urljoin(page_url, segment.get("href", ""))
        batch = (match.group("batch") or "").strip()
        location = (match.group("location") or "").strip()
        index += 1
        description_parts: list[str] = []
        jobs_url = ""
        while index < len(segments):
            next_segment = segments[index]
            next_text = next_segment.get("text", "")
            if (
                next_segment.get("kind") == "link"
                and "Y Combinator Logo" in next_text
                and not next_text.startswith("Image:")
            ):
                break
            if next_segment.get("kind") == "link" and next_text == "View jobs →":
                jobs_url = urljoin(page_url, next_segment.get("href", ""))
                index += 1
                continue
            if next_segment.get("kind") == "text" and next_text not in {"company", "jobs", "apply"}:
                description_parts.append(next_text)
            index += 1
        cards.append(
            YcCompanyCard(
                name=(match.group("name") or "").strip(),
                company_url=company_url,
                jobs_url=jobs_url,
                description=_clean_text(" ".join(description_parts)),
                batch=batch,
                location=location,
            )
        )
    return cards


def _find_text_index(segments: list[dict[str, str]], target: str) -> int:
    for index, segment in enumerate(segments):
        if segment.get("text", "").strip() == target:
            return index
    return -1


def _find_prefix_index(segments: list[dict[str, str]], prefix: str) -> int:
    for index, segment in enumerate(segments):
        if segment.get("text", "").strip().startswith(prefix):
            return index
    return -1


def _find_next_section_index(segments: list[dict[str, str]], start: int, prefixes: set[str]) -> int:
    for index in range(start, len(segments)):
        text = segments[index].get("text", "").strip()
        if any(text.startswith(prefix) for prefix in prefixes):
            return index
    return len(segments)


def _looks_like_job_location(value: str) -> bool:
    lowered = value.lower()
    return "," in value or "remote" in lowered or lowered.endswith(" us")


def _yc_extract_jobs_page_url(segments: list[dict[str, str]]) -> str:
    for segment in segments:
        if segment.get("kind") != "link":
            continue
        text = segment.get("text", "").strip()
        href = segment.get("href", "").strip()
        if text not in {"Jobs", "View all jobs"}:
            continue
        if "/companies/" in href and href.endswith("/jobs"):
            return href
    return ""


def _yc_extract_job_rows(segments: list[dict[str, str]], page_url: str) -> list[dict]:
    start = _find_text_index(segments, "Jobs at")
    if start < 0:
        start = _find_prefix_index(segments, "Jobs at ")
    if start < 0:
        return []
    end = _find_next_section_index(segments, start + 1, {"Founded:", "Footer", "Company Launches"})
    opportunities: list[dict] = []
    index = start + 1
    while index < end:
        segment = segments[index]
        text = segment.get("text", "").strip()
        if segment.get("kind") == "link" and text and text not in {"View all jobs", "Apply Now ›"}:
            href = segment.get("href", "")
            if "account.ycombinator.com" in href:
                index += 1
                continue
            title = text
            detail_url = urljoin(page_url, href)
            location = ""
            compensation = ""
            experience = ""
            apply_url = ""
            inner = index + 1
            while inner < end:
                next_segment = segments[inner]
                next_text = next_segment.get("text", "").strip()
                if next_segment.get("kind") == "link":
                    if next_text == "View all jobs":
                        inner += 1
                        continue
                    if next_text == "Apply Now ›":
                        apply_url = next_segment.get("href", "")
                        inner += 1
                        break
                    if next_text and next_text not in {"Jobs"}:
                        break
                elif next_text:
                    if not location and _looks_like_job_location(next_text):
                        location = next_text
                    elif "$" in next_text and not compensation:
                        compensation = next_text
                    elif ("year" in next_text.lower() or "new grads" in next_text.lower() or "intern" in next_text.lower()) and not experience:
                        experience = next_text
                inner += 1
            if detail_url or apply_url:
                opportunities.append(
                    {
                        "title": title,
                        "location": location,
                        "detail_url": detail_url,
                        "apply_url": apply_url,
                        "compensation": compensation,
                        "experience": experience,
                    }
                )
            index = inner
            continue
        index += 1
    return opportunities


def _merge_opportunities(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in [*primary, *secondary]:
        key = (
            _clean_text(str(item.get("title") or "")).lower(),
            _clean_text(str(item.get("detail_url") or item.get("apply_url") or "")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _fetch_yc_job_detail(detail_url: str) -> tuple[str, str, str]:
    html = _fetch_text(detail_url)
    soup = BeautifulSoup(html, "html.parser")
    page_root = soup.find(attrs={"data-page": True})
    if not page_root:
        return "", "", ""
    payload = json.loads(unescape(str(page_root["data-page"])))
    company = payload.get("props", {}).get("company", {})
    job = payload.get("props", {}).get("job", {})
    company_name = _clean_text(str(company.get("name") or ""))
    company_summary = _clean_text(str(company.get("one_liner") or company.get("long_description") or ""))
    lines = [
        company_name,
        company_summary,
        f"Location: {_clean_text(str(job.get('location') or ''))}",
        f"Type: {_clean_text(str(job.get('type') or ''))}",
        f"Role: {_clean_text(str(job.get('prettyRole') or ''))}",
        f"Role Specific Type: {_clean_text(str(job.get('roleSpecificType') or ''))}",
        f"Compensation: {_clean_text(str(job.get('salaryRange') or ''))}",
        f"Equity: {_clean_text(str(job.get('equityRange') or ''))}",
        f"Experience: {_clean_text(str(job.get('minExperience') or ''))}",
        f"Visa: {_clean_text(str(job.get('visa') or ''))}",
        "",
        _clean_text(str(job.get("description") or "")),
    ]
    interview_process = _clean_text(str(job.get("interview_process") or ""))
    hiring_description = _clean_text(str(company.get("hiring_description") or ""))
    if interview_process:
        lines.extend(["", "Interview Process:", interview_process])
    if hiring_description:
        lines.extend(["", "Hiring Notes:", hiring_description])
    return "\n".join(line for line in lines if line is not None).strip(), company_name, company_summary


def _discover_yc_source_jobs(source: StartupApplySourceDefinition, limit_companies: int) -> list[StartupJobCandidate]:
    discovered: list[StartupJobCandidate] = []
    seen_companies: set[str] = set()
    for url in source.seed_urls:
        cards = _parse_yc_listing_page(_fetch_text(url), url)
        for card in cards:
            company_key = card.name.strip().lower()
            if not company_key or company_key in seen_companies:
                continue
            seen_companies.add(company_key)
            detail_html = _fetch_text(card.company_url)
            detail_segments = _text_segments(detail_html)
            jobs_url = _yc_extract_jobs_page_url(detail_segments) or card.jobs_url
            opportunities = _yc_extract_job_rows(detail_segments, card.company_url)
            if jobs_url:
                jobs_html = _fetch_text(urljoin(card.company_url, jobs_url))
                opportunities = _merge_opportunities(
                    opportunities,
                    _yc_extract_job_rows(_text_segments(jobs_html), card.company_url),
                )
            for opportunity in opportunities:
                title = str(opportunity.get("title") or "")
                if not _is_target_startup_role(title):
                    continue
                experience = str(opportunity.get("experience") or "")
                if not _has_early_career_signal(title, experience):
                    continue
                detail_url = str(opportunity.get("detail_url") or "")
                if not detail_url:
                    continue
                jd_text, company_name, company_summary = _fetch_yc_job_detail(detail_url)
                if not jd_text:
                    continue
                if not _has_early_career_signal(title, experience, jd_text):
                    continue
                discovered.append(
                    StartupJobCandidate(
                        company=company_name or card.name,
                        role_title=title,
                        location=_clean_text(str(opportunity.get("location") or card.location)),
                        url=detail_url,
                        source=source.source_tag,
                        source_id=source.source_id,
                        date_posted="",
                        jd_text=jd_text,
                        notes=_build_notes(
                            track="startup_apply",
                            source_id=source.source_id,
                            company_summary=company_summary or card.description,
                            apply_url=str(opportunity.get("apply_url") or ""),
                            company_url=card.company_url,
                            list_url=jobs_url or source.seed_urls[0],
                        ),
                        list_url=jobs_url or source.seed_urls[0],
                    )
                )
            if len(seen_companies) >= limit_companies:
                break
    return discovered


def _parse_builtin_listing_page(html: str, page_url: str) -> list[BuiltInCompanyCard]:
    listing_start_pattern = re.compile(r"^Top Tech Companies in .+")
    employee_pattern = re.compile(r"^(?P<count>[\d,]+)\s+Employees?$")
    offices_pattern = re.compile(r"^(?P<count>[\d,]+)\s+Offices?$")
    segments = _text_segments(html)
    start = -1
    for index, segment in enumerate(segments):
        if listing_start_pattern.match(segment.get("text", "").strip()):
            start = index
            break
    if start < 0:
        return []
    cards: list[BuiltInCompanyCard] = []
    index = start
    while index < len(segments):
        segment = segments[index]
        text = segment.get("text", "")
        href = segment.get("href", "")
        if segment.get("kind") == "link" and text and href.startswith("/company/"):
            if text in {"Hiring Now", "See Our Teams", "View Website", "View all jobs"} or text.endswith("Benefits"):
                index += 1
                continue
            card = BuiltInCompanyCard(name=text.strip(), company_url=urljoin(page_url, href), jobs_url="")
            index += 1
            jobs_url = ""
            categories = ""
            location_or_offices = ""
            employee_count = ""
            description = ""
            while index < len(segments):
                next_segment = segments[index]
                next_text = next_segment.get("text", "").strip()
                next_href = next_segment.get("href", "")
                if (
                    next_segment.get("kind") == "link"
                    and next_text
                    and next_href.startswith("/company/")
                    and next_text not in {"Hiring Now", "See Our Teams", "View Website", "View all jobs"}
                    and not next_text.endswith("Benefits")
                ):
                    break
                if next_segment.get("kind") == "link":
                    if next_text == "Hiring Now":
                        jobs_url = urljoin(page_url, next_href)
                elif next_text and next_text not in {"Save", "Saved", "CREATE JOB ALERT", "ADD COMPANY PROFILE", "•"}:
                    if not categories and "•" in next_text:
                        categories = next_text
                    elif not location_or_offices and (
                        next_text == "Fully Remote"
                        or offices_pattern.match(next_text)
                        or "," in next_text
                    ):
                        location_or_offices = next_text
                    elif not employee_count and employee_pattern.match(next_text):
                        employee_count = next_text
                    elif not description and len(next_text) > 80:
                        description = next_text
                index += 1
            cards.append(
                BuiltInCompanyCard(
                    name=card.name,
                    company_url=card.company_url,
                    jobs_url=jobs_url,
                    description=description,
                    categories=categories,
                    location_or_offices=location_or_offices,
                    employee_count=employee_count,
                )
            )
            continue
        index += 1
    return cards


def _builtin_extract_recent_jobs(html: str, page_url: str) -> list[dict]:
    segments = _text_segments(html)
    start = _find_text_index(segments, "Recently Posted Jobs")
    if start < 0:
        start = _find_prefix_index(segments, "Recently Posted Jobs at ")
    if start < 0:
        return []
    end = len(segments)
    for index in range(start + 1, len(segments)):
        text = segments[index].get("text", "").strip()
        if text.endswith(" Offices") or text in {"Offices", "Perks + Benefits", "Articles", "FAQs"}:
            end = index
            break
    opportunities: list[dict] = []
    index = start + 1
    while index < end:
        segment = segments[index]
        text = segment.get("text", "").strip()
        href = segment.get("href", "")
        if segment.get("kind") == "link" and text and href.startswith("/job/"):
            title = text
            detail_url = urljoin(page_url, href)
            mode = ""
            location = ""
            inner = index + 1
            while inner < end:
                next_segment = segments[inner]
                next_text = next_segment.get("text", "").strip()
                next_href = next_segment.get("href", "")
                if next_segment.get("kind") == "link" and next_href.startswith("/job/"):
                    break
                if next_text in {"Hybrid", "Remote"}:
                    mode = next_text
                elif "," in next_text or "Locations" in next_text:
                    location = next_text
                inner += 1
            opportunities.append(
                {
                    "title": title,
                    "location": f"{mode} | {location}".strip(" |"),
                    "detail_url": detail_url,
                }
            )
            index = inner
            continue
        index += 1
    return opportunities


def _fetch_builtin_job_detail(detail_url: str) -> tuple[str, str, str]:
    detail_url = _canonicalize_builtin_url(detail_url)
    try:
        html = _fetch_text(detail_url)
    except Exception:
        return "", "", ""
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    body = soup.find(id=re.compile(r"^job-post-body-\d+$"))
    if body is None:
        return "", "", ""
    jd_text = body.get_text("\n", strip=True)
    company_name = ""
    company_anchor = soup.find(attrs={"data-id": "company-title"})
    if company_anchor is not None:
        company_name = _clean_text(company_anchor.get_text(" ", strip=True))
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta is not None:
        description = _clean_text(str(meta.get("content") or ""))
    lines = [title, description, jd_text]
    return "\n\n".join(part for part in lines if part).strip(), company_name, description


def _builtin_extract_job_list_cards(html: str, page_url: str) -> list[BuiltInJobCard]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[BuiltInJobCard] = []
    for title_anchor in soup.find_all("a", attrs={"data-id": "job-card-title"}, href=True):
        title = _clean_text(title_anchor.get_text(" ", strip=True))
        detail_url = _canonicalize_builtin_url(urljoin(page_url, str(title_anchor.get("href") or "")))
        if not title or not detail_url:
            continue
        card_root = title_anchor
        while card_root is not None:
            classes = {cls for cls in (card_root.get("class") or []) if cls}
            if "job-bounded-responsive" in classes:
                break
            card_root = card_root.parent
        if card_root is None:
            continue

        company_anchor = card_root.find("a", attrs={"data-id": "company-title"}, href=True)
        company = _clean_text(company_anchor.get_text(" ", strip=True)) if company_anchor else ""
        company_url = urljoin(page_url, str(company_anchor.get("href") or "")) if company_anchor else ""
        tokens = _dedupe_preserving_order([text for text in card_root.stripped_strings if text.strip() != "Saved"])

        posted_text = ""
        location = ""
        seniority = ""
        summary = ""
        for token in tokens:
            lowered = token.lower()
            if not posted_text and (
                lowered == "today"
                or lowered == "yesterday"
                or " ago" in lowered
                or lowered.startswith("reposted ")
            ):
                posted_text = token
                continue
            if not location and (
                " bay area, " in lowered
                or ", ca" in lowered
                or ", usa" in lowered
                or lowered.endswith(" united states")
            ):
                location = token
                continue
            if not location and token in {"Remote", "Hybrid", "In-Office", "Remote or Hybrid"}:
                location = token
                continue
            if not seniority and (
                lowered == "internship"
                or lowered.endswith(" level")
                or lowered == "management"
            ):
                seniority = token
                continue
            if not summary and len(token) >= 90 and "•" not in token and not token.startswith("Top Skills"):
                summary = token

        cards.append(
            BuiltInJobCard(
                company=company,
                company_url=company_url,
                detail_url=detail_url,
                title=title,
                list_url=page_url,
                location=location,
                posted_text=posted_text,
                seniority=seniority,
                summary=summary,
            )
        )
    return cards


def _discover_builtin_job_list_source_jobs(
    source: StartupApplySourceDefinition,
    _limit_companies: int,
) -> list[StartupJobCandidate]:
    discovered: list[StartupJobCandidate] = []
    seen_urls: set[str] = set()
    for url in source.seed_urls:
        page_cards = _builtin_extract_job_list_cards(_fetch_text(url), url)
        for card in page_cards:
            detail_key = _url_hash(card.detail_url)
            if detail_key in seen_urls:
                continue
            seen_urls.add(detail_key)
            seniority_lower = (card.seniority or "").strip().lower()
            if seniority_lower in {"senior level", "mid level", "management"}:
                continue
            if not _is_target_startup_role(card.title):
                continue
            if not _has_early_career_signal(card.title):
                continue
            jd_text, company_name, detail_summary = _fetch_builtin_job_detail(card.detail_url)
            if not jd_text:
                continue
            if not _has_early_career_signal(card.title, jd_text):
                continue
            discovered.append(
                StartupJobCandidate(
                    company=company_name or card.company,
                    role_title=card.title,
                    location=card.location,
                    url=card.detail_url,
                    source=source.source_tag,
                    source_id=source.source_id,
                    date_posted=card.posted_text,
                    jd_text=jd_text,
                    notes=_build_notes(
                        track="startup_apply",
                        source_id=source.source_id,
                        company_summary=detail_summary or card.summary,
                        company_url=card.company_url,
                        list_url=card.list_url,
                    ),
                    list_url=card.list_url,
                )
            )
    return discovered


def _startup_candidate_priority(item: StartupJobCandidate) -> tuple[int, int, int, str]:
    title = _clean_text(item.role_title).lower()
    list_url = (item.list_url or "").lower()
    score = 0

    if "/entry-level" in list_url:
        score += 40
    elif "/internships" in list_url:
        score += 35
    elif "/jobs/product" in list_url:
        score += 10

    if re.search(r"\b(intern|internship|co-?op)\b", title):
        score += 40
    if re.search(r"\b(new grad|graduate|associate|apm)\b", title):
        score += 35
    if re.search(r"\bproduct manager i\b", title):
        score += 25
    if re.search(r"\bproduct manager\b", title):
        score += 10
    if re.search(r"\b(strategy|operations|bizops|chief of staff|founder'?s associate)\b", title):
        score += 8

    if re.search(r"\bfounding\b", title):
        score -= 50
    if re.search(r"\b(group|lead|senior|staff|principal|director|head|vp)\b", title):
        score -= 45
    if re.search(r"\b(ii|iii|iv)\b", title):
        score -= 20

    recency_bonus = 0
    posted = (item.date_posted or "").lower()
    if "today" in posted:
        recency_bonus = 3
    elif "yesterday" in posted or "hour" in posted:
        recency_bonus = 2
    elif "day" in posted:
        recency_bonus = 1

    return (score, recency_bonus, -len(title), item.url)


def _a16z_is_target_job(job: dict) -> bool:
    title = _clean_text(str(job.get("title") or ""))
    if not _is_target_startup_role(title):
        return False

    seniorities = tuple(
        _clean_text(str(item.get("value") or item.get("label") or ""))
        for item in (job.get("jobSeniorities") or [])
        if _clean_text(str(item.get("value") or item.get("label") or ""))
    )
    min_years = job.get("minYearsExp")
    try:
        min_years_int = int(min_years) if min_years is not None else None
    except (TypeError, ValueError):
        min_years_int = None

    if any(value in {"manager", "director", "vp", "executive", "senior", "expert"} for value in seniorities):
        return False

    if min_years_int is not None and min_years_int > 2:
        return False

    if _has_early_career_signal(title):
        return True

    if any(value in {"intern", "junior"} for value in seniorities):
        return True

    if min_years_int is not None and min_years_int <= 2:
        return True

    return False


def _discover_a16z_source_jobs(source: StartupApplySourceDefinition, limit_pages: int) -> list[StartupJobCandidate]:
    discovered: list[StartupJobCandidate] = []
    seen_urls: set[str] = set()
    sequence: str | None = None
    pages_to_scan = max(1, min(limit_pages, A16Z_MAX_PAGES))

    for _ in range(pages_to_scan):
        payload = {
            "meta": {"size": A16Z_PAGE_SIZE},
            "board": {"id": "andreessen-horowitz", "isParent": True},
            "query": {},
            "grouped": False,
        }
        if sequence:
            payload["meta"]["sequence"] = sequence
        response = _post_json("https://jobs.a16z.com/api-boards/search-jobs", payload)
        jobs_page = response.get("jobs") or []
        sequence = str((response.get("meta") or {}).get("sequence") or "").strip() or None
        if not jobs_page:
            break
        for job in jobs_page:
            if not _a16z_is_target_job(job):
                continue
            apply_url = _clean_text(str(job.get("applyUrl") or job.get("url") or ""))
            if not apply_url:
                continue
            url_key = _url_hash(apply_url)
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)

            jd_text = _generic_page_text(apply_url)
            if len(jd_text) < 400:
                jd_text = _a16z_structured_job_text(job)
            title = _clean_text(str(job.get("title") or ""))
            company = _clean_text(str(job.get("companyName") or ""))
            location = _clean_text(", ".join(str(value) for value in (job.get("locations") or []) if str(value).strip()))
            posted = _clean_text(str(job.get("timeStamp") or ""))
            seniorities = ", ".join(
                _clean_text(str(item.get("label") or item.get("value") or ""))
                for item in (job.get("jobSeniorities") or [])
                if _clean_text(str(item.get("label") or item.get("value") or ""))
            )
            company_stage = ", ".join(
                _clean_text(str(item.get("label") or item.get("value") or ""))
                for item in (job.get("stages") or [])
                if _clean_text(str(item.get("label") or item.get("value") or ""))
            )
            notes = _build_notes(
                track="startup_apply",
                source_id=source.source_id,
                company_summary=f"seniority={seniorities}; stage={company_stage}; minYearsExp={job.get('minYearsExp')}",
                apply_url=apply_url,
                company_url=source.seed_urls[0],
                list_url=source.seed_urls[0],
            )
            discovered.append(
                StartupJobCandidate(
                    company=company,
                    role_title=title,
                    location=location,
                    url=apply_url,
                    source=source.source_tag,
                    source_id=source.source_id,
                    jd_text=jd_text,
                    notes=notes,
                    date_posted=posted,
                    list_url=source.seed_urls[0],
                )
            )
        if not sequence:
            break

    return discovered


def _discover_builtin_source_jobs(source: StartupApplySourceDefinition, limit_companies: int) -> list[StartupJobCandidate]:
    discovered: list[StartupJobCandidate] = []
    seen_companies: set[str] = set()
    for url in source.seed_urls:
        cards = _parse_builtin_listing_page(_fetch_text(url), url)
        for card in cards:
            company_key = card.name.strip().lower()
            if not company_key or company_key in seen_companies:
                continue
            seen_companies.add(company_key)
            employee_count = _parse_employee_count(card.employee_count)
            categories_lower = card.categories.lower()
            if employee_count is not None and employee_count > 5000:
                if len(seen_companies) >= limit_companies:
                    break
                continue
            if any(tag in categories_lower for tag in {"professional services", "consulting", "banking"}):
                if len(seen_companies) >= limit_companies:
                    break
                continue
            if not card.jobs_url:
                if len(seen_companies) >= limit_companies:
                    break
                continue
            company_html = _fetch_text(card.company_url)
            opportunities = _builtin_extract_recent_jobs(company_html, card.company_url)
            for opportunity in opportunities:
                title = str(opportunity.get("title") or "")
                if not _is_target_startup_role(title):
                    continue
                detail_url = str(opportunity.get("detail_url") or "")
                if not detail_url:
                    continue
                jd_text, company_name, detail_summary = _fetch_builtin_job_detail(detail_url)
                if not jd_text:
                    continue
                discovered.append(
                    StartupJobCandidate(
                        company=company_name or card.name,
                        role_title=title,
                        location=_clean_text(str(opportunity.get("location") or card.location_or_offices)),
                        url=detail_url,
                        source=source.source_tag,
                        source_id=source.source_id,
                        jd_text=jd_text,
                        notes=_build_notes(
                            track="startup_apply",
                            source_id=source.source_id,
                            company_summary=detail_summary or card.description or card.categories,
                            company_url=card.company_url,
                        ),
                    )
                )
            if len(seen_companies) >= limit_companies:
                break
    return discovered


def _discover_startup_jobs(
    limit_companies: int,
    include_sources: set[str] | None = None,
    verbose: bool = True,
) -> tuple[list[StartupJobCandidate], dict[str, int]]:
    all_jobs: list[StartupJobCandidate] = []
    raw_counts: dict[str, int] = {}
    for source in SOURCE_REGISTRY:
        if include_sources and source.source_id not in include_sources:
            continue
        if verbose:
            print(f"  Discovering source: {source.label}")
        if source.adapter == "yc_company_directory":
            discovered = _discover_yc_source_jobs(source, limit_companies=limit_companies)
        elif source.adapter == "builtin_companies":
            discovered = _discover_builtin_source_jobs(source, limit_companies=limit_companies)
        elif source.adapter == "builtin_job_lists":
            discovered = _discover_builtin_job_list_source_jobs(source, _limit_companies=limit_companies)
        elif source.adapter == "a16z_job_board":
            discovered = _discover_a16z_source_jobs(source, limit_pages=limit_companies)
        else:
            discovered = []
        raw_counts[source.source_id] = len(discovered)
        if verbose:
            print(f"    kept {len(discovered)} apply-worthy candidates")
        all_jobs.extend(discovered)
    deduped: dict[str, StartupJobCandidate] = {}
    for item in all_jobs:
        deduped[_url_hash(item.url)] = item
    return list(deduped.values()), raw_counts


def _source_label_map() -> dict[str, str]:
    return {source.source_id: source.label for source in SOURCE_REGISTRY}


def _group_counts_by_source(items: list, getter) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source_id = str(getter(item) or "").strip()
        if not source_id:
            continue
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def _score_float(value) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric


def _source_score_summary(scored_jobs: list[dict]) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for job in scored_jobs:
        source_id = str(job.get("source_id") or "").strip()
        if not source_id:
            continue
        bucket = grouped.setdefault(
            source_id,
            {
                "scored": 0,
                "queued": 0,
                "review": 0,
                "skipped": 0,
                "scores": [],
                "top_jobs": [],
            },
        )
        bucket["scored"] += 1
        status = str(job.get("status") or "").strip().lower()
        if status in {"queued", "review", "skipped"}:
            bucket[status] += 1
        score = _score_float(job.get("fit_score"))
        if score is not None:
            bucket["scores"].append(score)
        bucket["top_jobs"].append(job)

    for bucket in grouped.values():
        scores = list(bucket["scores"])
        bucket["avg_fit"] = round(sum(scores) / len(scores), 2) if scores else None
        bucket["fit_ge_7"] = len([score for score in scores if score >= 7.0])
        bucket["top_jobs"] = sorted(
            bucket["top_jobs"],
            key=lambda item: (_score_float(item.get("fit_score")) or -1.0, str(item.get("role_title") or "")),
            reverse=True,
        )[:3]
    return grouped


def _print_source_summary(
    *,
    discovered_counts: dict[str, int],
    new_counts: dict[str, int],
    scored_jobs: list[dict],
) -> None:
    label_map = _source_label_map()
    score_summary = _source_score_summary(scored_jobs)
    source_ids = sorted(set(label_map) | set(discovered_counts) | set(new_counts) | set(score_summary))
    if not source_ids:
        return
    print("\n  Source summary:")
    for source_id in source_ids:
        row = score_summary.get(source_id, {})
        avg_fit = row.get("avg_fit")
        avg_text = f"{avg_fit:.2f}" if isinstance(avg_fit, float) else "-"
        print(
            "   - "
            f"{label_map.get(source_id, source_id)} [{source_id}] | "
            f"discovered={discovered_counts.get(source_id, 0)} | "
            f"new={new_counts.get(source_id, 0)} | "
            f"scored={row.get('scored', 0)} | "
            f"queued={row.get('queued', 0)} | "
            f"review={row.get('review', 0)} | "
            f"skipped={row.get('skipped', 0)} | "
            f"avg_fit={avg_text} | "
            f"fit>=7={row.get('fit_ge_7', 0)}"
        )
        top_jobs = row.get("top_jobs") or []
        for item in top_jobs:
            print(
                "      "
                f"[{item.get('fit_score', '?')}/10] {item.get('company')} — {item.get('role_title')}"
            )


def _write_run_log(
    scored_jobs: list[dict],
    run_start: datetime,
    dry_run: bool,
    skip_score: bool,
    *,
    discovered_counts: dict[str, int],
    new_counts: dict[str, int],
) -> Path:
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = run_start.strftime("%Y-%m-%d_%H%M")
    log_path = LOGS_DIR / f"startup_apply_{timestamp}.txt"
    elapsed = (datetime.now() - run_start).seconds
    queued = [job for job in scored_jobs if job.get("status") == "queued"]
    review = [job for job in scored_jobs if job.get("status") == "review"]
    skipped = [job for job in scored_jobs if job.get("status") == "skipped"]
    score_summary = _source_score_summary(scored_jobs)
    label_map = _source_label_map()
    lines = [
        "Startup Apply Run Log",
        "=" * 60,
        f"Run time:  {run_start.strftime('%Y-%m-%d %H:%M')}",
        f"Elapsed:   {elapsed}s",
        f"Dry run:   {dry_run}",
        f"Skip score:{skip_score}",
        "",
        f"Queued:    {len(queued)}",
        f"Review:    {len(review)}",
        f"Skipped:   {len(skipped)}",
        "",
    ]
    source_ids = sorted(set(label_map) | set(discovered_counts) | set(new_counts) | set(score_summary))
    if source_ids:
        lines.append("── Source Summary ───────────────────────────────────────")
        for source_id in source_ids:
            row = score_summary.get(source_id, {})
            avg_fit = row.get("avg_fit")
            avg_text = f"{avg_fit:.2f}" if isinstance(avg_fit, float) else "-"
            lines.append(
                f"{label_map.get(source_id, source_id)} [{source_id}] | "
                f"discovered={discovered_counts.get(source_id, 0)} | "
                f"new={new_counts.get(source_id, 0)} | "
                f"scored={row.get('scored', 0)} | "
                f"queued={row.get('queued', 0)} | "
                f"review={row.get('review', 0)} | "
                f"skipped={row.get('skipped', 0)} | "
                f"avg_fit={avg_text} | "
                f"fit>=7={row.get('fit_ge_7', 0)}"
            )
            top_jobs = row.get("top_jobs") or []
            for item in top_jobs:
                lines.append(
                    f"  [{item.get('fit_score', '?')}/10] {item.get('company')} — {item.get('role_title')}"
                )
            lines.append("")
    for bucket_name, bucket in [("Queued", queued), ("Review", review)]:
        if not bucket:
            continue
        lines.append(f"── {bucket_name} ─────────────────────────────────────────────")
        for item in bucket:
            lines.extend(
                [
                    f"[{item.get('fit_score', '?')}/10] {item.get('company')} — {item.get('role_title')}",
                    f"  {item.get('source')} | {item.get('location')}",
                    f"  {item.get('url')}",
                    f"  {item.get('fit_rationale', '')}",
                    "",
                ]
            )
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def run(
    *,
    dry_run: bool,
    skip_score: bool,
    model: str,
    limit_companies: int,
    limit_jobs: int | None,
    include_sources: set[str] | None,
    ignore_existing: bool,
    verbose: bool,
) -> list[dict]:
    run_start = datetime.now()
    if verbose:
        print(f"\n{'═' * 60}")
        print(f"  Startup Apply Pipeline — {run_start.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═' * 60}")

    df_existing = jobs.load_jobs()
    existing_hashes = set(df_existing["url_hash"].dropna().astype(str).tolist())
    next_id = _next_row_id(df_existing)
    discovered, discovered_counts = _discover_startup_jobs(limit_companies, include_sources=include_sources, verbose=verbose)
    if ignore_existing:
        new_items = list(discovered)
    else:
        new_items = [item for item in discovered if _url_hash(item.url) not in existing_hashes]
    new_counts = _group_counts_by_source(new_items, lambda item: item.source_id)
    filtered = list(new_items)
    filtered = sorted(filtered, key=_startup_candidate_priority, reverse=True)
    if limit_jobs is not None:
        filtered = filtered[:limit_jobs]
    if not filtered:
        if verbose:
            print("  No new startup apply jobs found.")
        return []

    candidate_dicts = [
        {
            "company": item.company,
            "role_title": item.role_title,
            "location": item.location,
            "url": item.url,
            "url_hash": _url_hash(item.url),
            "source": item.source,
            "source_id": item.source_id,
            "date_posted": item.date_posted,
            "jd_text": item.jd_text,
            "notes": item.notes,
            "status": "",
        }
        for item in filtered
    ]

    if verbose:
        print(f"  New startup candidates before scoring: {len(candidate_dicts)}")

    if skip_score:
        scored_jobs = []
        for candidate in candidate_dicts:
            candidate["fit_score"] = ""
            candidate["fit_rationale"] = "[Skipped scoring] Discovery smoke test run"
            candidate["role_type"] = ""
            candidate["status"] = "review"
            scored_jobs.append(candidate)
    else:
        api_key = _load_api_key()
        client = anthropic.Anthropic(api_key=api_key)
        scored_jobs = score_batch(candidate_dicts, client=client, model=model, verbose=verbose)
        scored_jobs = _post_process_scored_jobs(scored_jobs)

    rows = _rows_from_jobs(scored_jobs, start_id=next_id)
    df_new = pd.DataFrame(rows, columns=jobs.COLUMNS)
    df_all = pd.concat([df_existing, df_new], ignore_index=True)
    jobs.save_jobs(df_all, dry_run=dry_run)

    log_path = _write_run_log(
        scored_jobs,
        run_start,
        dry_run=dry_run,
        skip_score=skip_score,
        discovered_counts=discovered_counts,
        new_counts=new_counts,
    )
    if verbose:
        _print_source_summary(
            discovered_counts=discovered_counts,
            new_counts=new_counts,
            scored_jobs=scored_jobs,
        )
        queued = len([job for job in scored_jobs if job.get("status") == "queued"])
        review = len([job for job in scored_jobs if job.get("status") == "review"])
        skipped = len([job for job in scored_jobs if job.get("status") == "skipped"])
        print(f"\n  Queued: {queued} | Review: {review} | Skipped: {skipped}")
        print(f"  Log: {log_path}")
        if not dry_run:
            print(f"  ✓ jobs.xlsx updated ({len(df_all)} total rows)")

    return scored_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Startup apply discovery pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Discover and score but do not write jobs.xlsx")
    parser.add_argument("--skip-score", action="store_true", help="Skip Anthropic scoring for a discovery smoke test")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--limit-companies",
        type=int,
        default=DEFAULT_LIMIT_COMPANIES,
        help=f"Maximum companies to inspect per source (default: {DEFAULT_LIMIT_COMPANIES})",
    )
    parser.add_argument(
        "--limit-jobs",
        type=int,
        default=DEFAULT_LIMIT_JOBS,
        help=f"Maximum new startup jobs to keep before scoring (default: {DEFAULT_LIMIT_JOBS})",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Optional source_id filter, repeatable (e.g. yc_sf_bay_hiring)",
    )
    parser.add_argument(
        "--ignore-existing",
        action="store_true",
        help="Ignore existing jobs.xlsx dedupe and analyze all currently discovered startup jobs",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose per-source output")
    args = parser.parse_args()

    include_sources = {value.strip() for value in args.source if value.strip()} or None
    run(
        dry_run=args.dry_run,
        skip_score=args.skip_score,
        model=args.model,
        limit_companies=max(args.limit_companies, 1),
        limit_jobs=max(args.limit_jobs, 1) if args.limit_jobs is not None else None,
        include_sources=include_sources,
        ignore_existing=args.ignore_existing,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
