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


INTERNSHIP_RE = re.compile(r"\b(?:intern(?:ship)?|co-?op|coop)\b", re.I)
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
    r"university\s+grad(?:uate)?|early\s+career|entry[- ]level|graduate\s+2027)\b",
    re.I,
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


def classify_title(title: str) -> tuple[bool, str]:
    title = str(title or "").strip()
    if not title:
        return False, "missing_title"
    if INTERNSHIP_RE.search(title):
        return False, "internship_outside_lane_b"
    target_family = ""
    for family, pattern in TARGET_FAMILIES:
        if pattern.search(title):
            target_family = family
            break
    for label, pattern in OBVIOUS_NOISE:
        if pattern.search(title):
            if target_family == "technical_gtm" and label == "software_engineering":
                continue
            return False, f"obvious_noise:{label}"
    if target_family:
        return True, f"target_family:{target_family}"
    if EARLY_CAREER_RE.search(title):
        return True, "early_career_title_review"
    return False, "broad_search_noise_no_target_title_signal"


def main() -> int:
    parser = argparse.ArgumentParser(description="Select plausible Lane B cards from broad LinkedIn raw artifacts.")
    parser.add_argument("raw_artifact", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "discovery" / "source_validation")
    args = parser.parse_args()

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
            selected, reason = classify_title(card.title)
            title_company_key = re.sub(
                r"\s+",
                " ",
                f"{card.company}|{card.title}".strip().casefold(),
            )
            if selected and title_company_key in seen_selected_title_company:
                selected = False
                reason = "duplicate_title_company"
            elif selected:
                seen_selected_title_company.add(title_company_key)
            row = asdict(card)
            row.update({"selected": selected, "selection_reason": reason})
            audit_rows.append(row)
            if selected:
                cards.append(card)

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
    audit_payload = {
        "schema": "resume_generator.linkedin_2027_card_audit",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_raw_artifacts": source_paths,
        "observed_unique_cards": len(audit_rows),
        "selected_for_jd_hydration": len(cards),
        "rejected_as_title_noise": len(audit_rows) - len(cards),
        "reason_counts": dict(reason_counts.most_common()),
        "selected_raw_artifact": str(selected_path),
        "rows": audit_rows,
    }
    selected_path.write_text(json.dumps(selected_payload, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    print(f"Observed unique cards: {len(audit_rows)}")
    print(f"Selected for JD hydration: {len(cards)}")
    print(f"Rejected as obvious title noise: {len(audit_rows) - len(cards)}")
    print(f"Selected raw artifact: {selected_path}")
    print(f"Full card audit: {audit_path}")
    for row in audit_rows:
        if row["selected"]:
            print(f"  [{row['selection_reason']}] {row['company']} | {row['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
