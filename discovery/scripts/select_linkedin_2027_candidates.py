#!/usr/bin/env python3
"""Audit broad LinkedIn card captures and retain plausible Lane B candidates.

This is intentionally a recall-first, no-network stage. It removes obvious noise
from catch-all searches such as ``2027`` while preserving target role families and
ambiguous early-career titles for JD hydration and deterministic timing checks.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from discovery.auto.linkedin_live import (  # noqa: E402
    LinkedInJobCard,
    _cards_from_payload,
    _searches_from_payload,
    cards_to_jobs,
)
import jobs as jobs_tracker  # noqa: E402
from shared.discovery_search_policy import (  # noqa: E402
    OFF_CYCLE_INTERNSHIP_SEARCHES,
    discovery_priority,
    internship_title_rejection,
)
from shared.job_eligibility import classify_start_timing, classify_role_surface  # noqa: E402


INTERNSHIP_RE = re.compile(r"\b(?:intern(?:ship)?s?|co-?ops?|coops?)\b", re.I)
LANE_A_SEARCH_TERMS = {term.casefold() for term in OFF_CYCLE_INTERNSHIP_SEARCHES}
TARGET_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "product",
        re.compile(
            r"\b(?:associate\s+product\s+manager|product\s+manager|product\s+management|"
            r"product\s+owner|product\s+operations?|product\s+strategy|product\s+analyst|"
            r"product\s+solutions?\s*(?:&|and)\s*operations?|"
            r"(?:content|global|creative)\s+product\s+[^\n]{0,45}\s+graduate|"
            r"rotational\s+product\s+manager|apm)\b",
            re.I,
        ),
    ),
    (
        "program",
        re.compile(
            r"\b(?:technical\s+program\s+manager|business\s+program\s+manager|"
            r"product\s+program\s+manager|program\s+manager)\b",
            re.I,
        ),
    ),
    (
        "strategy_ops",
        re.compile(
            r"\b(?:strategy\s*(?:&|and)\s*operations|business\s+operations|biz\s*ops|"
            r"business\s+strategy|corporate\s+strategy|gtm\s+strategy|revenue\s+operations|"
            r"growth\s+strategy|strategy\s+operations?|innovation\s+analyst|"
            r"technology[^\n]{0,35}operations\s+track|chief\s+of\s+staff|special\s+projects)\b",
            re.I,
        ),
    ),
    (
        "technical_gtm",
        re.compile(
            r"\b(?:forward\s+deployed|solutions?\s+engineer|solutions?\s+architect|"
            r"customer\s+engineer|partner\s+engineer|implementation\s+(?:engineer|consultant)|"
            r"deployment\s+(?:engineer|strategist)|solutions?\s+consultant|application\s+consultant|"
            r"delivery\s+consultant|technology\s+seller|sales\s+engineer|"
            r"technical\s+sales|applied\s+ai\s+engineer|field\s+engineer|value\s+engineer)\b",
            re.I,
        ),
    ),
    (
        "rotational_leadership",
        re.compile(
            r"\b(?:leadership\s+development|rotational\s+(?:program|associate|manager)|"
            r"graduate\s+(?:program|rotational|scheme)|development\s+program|"
            r"digital\s+rotational|business\s+management\s+associate|leadership\s+fellow|"
            r"management\s+trainee)\b",
            re.I,
        ),
    ),
)

EARLY_CAREER_RE = re.compile(
    r"\b(?:2027\s+graduates?|class\s+of\s+2027|new\s+grad(?:uate)?|college\s+grad(?:uate)?|"
    r"university\s+grad(?:uate)?|early\s+career|entry[- ]level|graduate\s+2027|"
    r"mba\s+full[- ]time\s+hire|full[- ]time\s+mba\s+hire)\b",
    re.I,
)
LATE_CAREER_RE = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|lead|director|vice\s+president|vp|head\s+of|group\s+product\s+manager)\b",
    re.I,
)
ENTRY_PRODUCT_RE = re.compile(
    r"\b(?:associate\s+product\s+manager|junior\s+product\s+manager|"
    r"product\s+management\s+graduate|entry[- ]level\s+(?:technical\s+)?product\s+manager|"
    r"product\s+manager\s*,?\s+associate)\b",
    re.I,
)
ENTRY_ASSOCIATE_RE = re.compile(
    r"\b(?:associate|analyst|entry[- ]level|engineer\s+i|consultant\s+i)\b",
    re.I,
)
EARLY_PROGRAM_RE = re.compile(
    r"\b(?:mba\s+development\s+program|leadership\s+development\s+program|"
    r"rotational\s+(?:development\s+)?program|graduate\s+(?:program|scheme)|"
    r"development\s+program|career\s+development\s+program)\b",
    re.I,
)
MBA_FULL_TIME_HIRE_RE = re.compile(
    r"\b(?:mba\s+full[- ]time\s+hire|full[- ]time\s+mba\s+hire)\b", re.I
)
OBVIOUS_NOISE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("finance", re.compile(r"\b(?:finance|financial|accounting|accountant|audit|tax|investment|banking|private\s+equity|asset\s+management|wealth\s+management|trading|trader|quant(?:itative)?|treasury|credit\s+analyst)\b", re.I)),
    ("consulting", re.compile(r"\b(?:management|strategy|business)\s+consultant\b|\b(?:consulting\s+associate|associate\s+consultants?|consulting\s+analyst|associates?\s+and\s+consultants?)\b", re.I)),
    ("software_engineering", re.compile(r"\b(?:software|backend|front[- ]?end|full[- ]?stack|firmware|machine\s+learning|ml\s+infra|data|systems?|research|test|vehicle)[^\n]{0,24}\s+engineer\b|\bdeveloper\b", re.I)),
    ("data_science", re.compile(r"\b(?:data\s+scientist|research\s+scientist|applied\s+scientist|quant\s+researcher)\b", re.I)),
    ("healthcare", re.compile(r"\b(?:nurse|physician|therapist|pharmacist|clinical\s+fellow|medical\s+assistant)\b", re.I)),
    ("legal", re.compile(r"\b(?:attorney|lawyer|paralegal|legal\s+counsel)\b", re.I)),
    ("education", re.compile(r"\b(?:teacher|teaching\s+assistant|professor|school\s+counselor)\b", re.I)),
    ("skilled_trade", re.compile(r"\b(?:electrician|plumber|mechanic|technician|warehouse|driver)\b", re.I)),
    ("hr_legal", re.compile(r"\b(?:human\s+resources|talent\s+acquisition|benefits\s+partner|attorney|lawyer|paralegal|legal\s+counsel|corporate\s*&\s+securities\s+associate|entry[- ]level\s+associate)\b", re.I)),
    ("sales_marketing", re.compile(r"\b(?:marketing\s+(?:associate|analyst|trainee)|sales\s+(?:associate|development)|brand\s+sales|client\s+service\s+associate|creator\s+manager|category\s+manager)\b", re.I)),
    ("supply_chain", re.compile(r"\b(?:supply\s+chain|procurement|sourcing\s+specialist|logistics\s+specialist|real\s+estate|site\s+acquisition)\b", re.I)),
    ("it_support", re.compile(r"\b(?:it\s+analyst|information\s+technology\s+analyst|help\s*desk|technical\s+support)\b", re.I)),
)


def classify_title(title: str, search_term: str = "") -> tuple[bool, str]:
    title = str(title or "").strip()
    if not title:
        return False, "missing_title"
    if internship_title_rejection(title):
        if str(search_term or "").strip().casefold() in LANE_A_SEARCH_TERMS and re.search(r"\b2027\b", title):
            return False, "lane_a_2027_internship_title"
        return False, "ineligible_internship_title:" + internship_title_rejection(title)
    if INTERNSHIP_RE.search(title):
        # The off-cycle lane is intentionally strict: only titles that state an
        # eligible term proceed to JD hydration. Semantic search otherwise
        # floods this stage with generic and Summer 2027 internships.
        if str(search_term or "").strip().casefold() in LANE_A_SEARCH_TERMS:
            timing = classify_start_timing(title, "")
            if timing in {"fall_2026_internship", "spring_2027_internship"}:
                return True, "off_cycle_internship_title"
            return False, "off_cycle_internship_timing_not_explicit"
        return False, "internship_outside_lane_b"
    target_family = ""
    for family, pattern in TARGET_FAMILIES:
        if pattern.search(title):
            target_family = family
            break
    if not target_family:
        disposition, _, canonical_family = classify_role_surface(title, "")
        if disposition == "keep":
            target_family = canonical_family
    if (
        not target_family
        and MBA_FULL_TIME_HIRE_RE.search(title)
        and re.search(r"(?:[-–—:]\s*)product\s*$", title, re.I)
    ):
        target_family = "product"
    for label, pattern in OBVIOUS_NOISE:
        if pattern.search(title):
            if target_family in {"technical_gtm", "product"} and label == "software_engineering":
                continue
            return False, f"obvious_noise:{label}"
    if target_family == "rotational_leadership" and EARLY_PROGRAM_RE.search(title):
        return True, f"target_family:{target_family}"
    # MBA-specific full-time hiring titles are early-career signals for this
    # candidate even when the title omits "new grad" or "2027". Preserve the
    # role for JD hydration and downstream graduation/work-authorization checks.
    if target_family and MBA_FULL_TIME_HIRE_RE.search(title):
        return True, f"mba_full_time_target_family:{target_family}"
    if LATE_CAREER_RE.search(title) and not re.search(
        r"\bstrategic\s+(?:product|partnerships?)\s+lead\b", title, re.I
    ):
        return False, "late_career_title"
    if target_family and EARLY_CAREER_RE.search(title):
        return True, f"target_family:{target_family}"
    if target_family == "product" and ENTRY_PRODUCT_RE.search(title):
        return True, f"target_family:{target_family}"
    if target_family in {"program", "strategy_ops", "technical_gtm"} and ENTRY_ASSOCIATE_RE.search(title):
        return True, f"target_family:{target_family}"
    if target_family:
        # Missing graduation wording in a card is not evidence of ineligibility.
        # Fetch the JD, then apply timing and experience rules to its requirements.
        return True, f"target_family_jd_review:{target_family}"
    if EARLY_CAREER_RE.search(title):
        return True, "early_career_title_review"
    return False, "broad_search_noise_no_target_title_signal"


def _url_key(value: str) -> str:
    return re.sub(r"[?#].*$", "", str(value or "").strip()).rstrip("/").casefold()


def has_cohort_signal(title: str, insight: str = "") -> bool:
    """Require card evidence, not the search query's year, before daily JD spend."""
    return bool(re.search(
        r"\b(?:2027|mba|graduates?|new[ -]grad(?:uate)?|university|rotational|"
        r"entry[ -]level|early[ -]career|pathways)\b", f"{title} {insight}", re.I))


def _title_company_key(company: str, title: str) -> str:
    return re.sub(r"\s+", " ", f"{company}|{title}".strip().casefold())


def main() -> int:
    parser = argparse.ArgumentParser(description="Select plausible Lane B cards from broad LinkedIn raw artifacts.")
    parser.add_argument("raw_artifact", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "discovery" / "source_validation")
    parser.add_argument("--exclude-artifact", action="append", type=Path, default=[])
    parser.add_argument("--exclude-workbook", action="store_true")
    parser.add_argument("--require-cohort-signal", action="store_true",
                        help="Park undated generic roles in the audit before spending on JDs.")
    args = parser.parse_args()

    excluded_urls: set[str] = set()
    excluded_title_company: set[str] = set()
    for excluded_path_arg in args.exclude_artifact:
        excluded_path = excluded_path_arg.expanduser().resolve()
        payload = json.loads(excluded_path.read_text(encoding="utf-8"))
        for row in [*(payload.get("cards") or []), *(payload.get("jobs") or [])]:
            excluded_urls.add(_url_key(row.get("url") or ""))
            excluded_title_company.add(
                _title_company_key(
                    row.get("company") or "",
                    row.get("title") or row.get("role_title") or "",
                )
            )
    if args.exclude_workbook:
        tracker = jobs_tracker.load_jobs()
        for _, row in tracker.iterrows():
            excluded_urls.add(_url_key(row.get("url") or ""))
            excluded_title_company.add(
                _title_company_key(row.get("company") or "", row.get("role_title") or "")
            )

    cards: list[LinkedInJobCard] = []
    searches: list[tuple[str, str]] = []
    search_runs: list[dict] = []
    source_paths: list[str] = []
    seen_urls: set[str] = set()
    seen_selected_title_company: set[str] = set()
    audit_rows: list[dict] = []

    for raw_path in args.raw_artifact:
        path = raw_path.expanduser().resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_paths.append(str(path))
        searches.extend(_searches_from_payload(payload))
        search_runs.extend(payload.get("search_runs", []))
        for card in _cards_from_payload(payload):
            if not card.url or card.url in seen_urls:
                continue
            seen_urls.add(card.url)
            selected, reason = classify_title(card.title, card.search_term)
            if selected and args.require_cohort_signal and not has_cohort_signal(card.title, card.insight):
                selected, reason = False, "unsure_missing_cohort_signal_deferred"
            title_company_key = _title_company_key(card.company, card.title)
            url_key = _url_key(card.url)
            if selected and (
                url_key in excluded_urls or title_company_key in excluded_title_company
            ):
                selected = False
                reason = "excluded_previous_artifact_or_workbook"
            elif selected and title_company_key in seen_selected_title_company:
                selected = False
                reason = "duplicate_title_company"
            elif selected:
                seen_selected_title_company.add(title_company_key)
            row = asdict(card)
            review_state = (
                "selected_for_jd_hydration"
                if selected
                else "unsure"
                if reason.startswith("unsure_")
                else "rejected"
            )
            row.update(
                {
                    "selected": selected,
                    "review_state": review_state,
                    "selection_reason": reason,
                }
            )
            audit_rows.append(row)
            if selected:
                cards.append(card)

    cards.sort(key=lambda card: discovery_priority(card.title))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected_path = args.output_dir / f"{stamp}-linkedin-2027-selected-raw.json"
    audit_path = args.output_dir / f"{stamp}-linkedin-2027-card-audit.json"

    selected_payload = {
        "schema": "resume_generator.linkedin_2027_selected_raw",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(cards),
        "source_raw_artifacts": source_paths,
        "searches": [
            {"search_term": search_term, "time_filter": time_filter}
            for search_term, time_filter in searches
        ],
        "search_runs": search_runs,
        "cards": [asdict(card) for card in cards],
        "jobs": cards_to_jobs(cards),
    }
    reason_counts = Counter(row["selection_reason"] for row in audit_rows)
    state_counts = Counter(row["review_state"] for row in audit_rows)
    audit_payload = {
        "schema": "resume_generator.linkedin_2027_card_audit",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_raw_artifacts": source_paths,
        "observed_unique_cards": len(audit_rows),
        "selected_for_jd_hydration": len(cards),
        "unsure_needs_review": state_counts["unsure"],
        "rejected_as_title_noise": state_counts["rejected"],
        "review_state_counts": dict(state_counts),
        "reason_counts": dict(reason_counts.most_common()),
        "selected_raw_artifact": str(selected_path),
        "rows": audit_rows,
    }
    selected_path.write_text(json.dumps(selected_payload, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    print(f"Observed unique cards: {len(audit_rows)}")
    print(f"Selected for JD hydration: {len(cards)}")
    print(f"Unsure and preserved for review: {state_counts['unsure']}")
    print(f"Rejected as obvious title noise: {state_counts['rejected']}")
    print(f"Selected raw artifact: {selected_path}")
    print(f"Full card audit: {audit_path}")
    for row in audit_rows:
        if row["selected"]:
            print(f"  [{row['selection_reason']}] {row['company']} | {row['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
