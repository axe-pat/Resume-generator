from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "discovery" / "auto" / "twelvetwenty_live.py"
SPEC = importlib.util.spec_from_file_location("twelvetwenty_live", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_time_filter_labels_cover_daily_weekly_and_poc() -> None:
    assert MODULE.TIME_FILTER_LABELS == {
        "24h": "Today",
        "7d": "Last 7 days",
        "30d": "Last 30 days",
    }


def test_active_search_terms_are_full_time_first_with_one_spring_lane() -> None:
    assert "product manager intern Spring 2027" in MODULE.SEARCH_TERMS
    assert "Fall 2026" not in MODULE.SEARCH_TERMS
    assert "product manager intern" not in MODULE.SEARCH_TERMS
    assert not ({"student worker", "research assistant", "teaching assistant", "part-time", "on-campus"} & set(MODULE.SEARCH_TERMS))
    assert len(MODULE.SEARCH_TERMS) == 20


def test_canonical_url_dedupes_featured_query_variant() -> None:
    left = "https://marshall-usc.12twenty.com/jobPostings#/jobPostings/123?p=true"
    right = "https://marshall-usc.12twenty.com/jobPostings#/jobPostings/123?p=false"
    assert MODULE.canonical_url(left) == MODULE.canonical_url(right)
    assert MODULE.url_hash(left) == MODULE.url_hash(right)


def test_infer_lane_prefers_fall_internship_over_part_time_wording() -> None:
    jd = "This fall 2026 internship is a part-time opportunity from September 2026 to March 2027."
    assert MODULE.infer_lane("Marketing Apprentice (Fall/Spring)", jd, "Internship") == "A"


def test_infer_lane_recognizes_september_2027_full_time_start() -> None:
    jd = "Full-time cohort. Anticipated Job Start Date: 09/01/2027"
    assert MODULE.infer_lane("Young Professionals Program", jd, "Job") == "B"


def test_parse_search_row_extracts_portal_fields() -> None:
    row = """Associate Product Manager\nExample Co\n Los Angeles - CA  Job\n 2 days ago  Apply By: 09/30/2026, 11:59pm PDT\n --\n APPLICATION OPEN\n Not Applied"""
    company, location, role_type, listed, deadline = MODULE._parse_search_row(row)
    assert company == "Example Co"
    assert location == "Los Angeles - CA"
    assert role_type == "Job"
    assert listed == "2 days ago"
    assert deadline.startswith("Apply By: 09/30/2026")


def test_source_is_registered_for_apply_queue() -> None:
    from shared.discovery_sources import APPLY_QUEUE_SOURCES

    assert MODULE.SOURCE_TAG in APPLY_QUEUE_SOURCES


def test_daily_engine_runs_twelvetwenty_between_linkedin_and_handshake() -> None:
    source = (Path(__file__).resolve().parents[1] / "discovery" / "scripts" / "run_daily_engine.py").read_text()
    linkedin = source.index('if not args.skip_linkedin:')
    twelvetwenty = source.index("if not args.skip_twelvetwenty:")
    handshake = source.index('if not args.skip_handshake:')
    assert linkedin < twelvetwenty < handshake
