from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.discovery_search_policy import (
    FULL_TIME_SEARCHES,
    LINKEDIN_SEARCH_TERMS,
    OFF_CYCLE_INTERNSHIP_SEARCHES,
    discovery_priority,
    internship_title_rejection,
)
from shared.job_eligibility import classify_start_timing
from discovery.scripts.select_linkedin_2027_candidates import classify_title


@pytest.mark.parametrize("title", [
    "Activision 2027 Summer Internships - MBA",
    "Product Manager Intern (Summer 2027)",
    "Product Management Summer Internship",
])
def test_ineligible_internships_filtered_before_hydration(title):
    assert internship_title_rejection(title)
    assert classify_title(title, "Product Manager Intern")[0] is False


@pytest.mark.parametrize("title", [
    "Associate Product Manager - Summer 2027 Start",
    "Product Manager Intern - Fall 2026",
    "Product Manager Intern - Spring 2027",
])
def test_full_time_summer_start_and_supported_off_cycle_internships_preserved(title):
    assert not internship_title_rejection(title)


@pytest.mark.parametrize(("title", "search_term"), [
    ("Product Manager Intern - Spring 2027", "Product Manager Intern Spring 2027"),
])
def test_supported_off_cycle_titles_enter_hydration(title, search_term):
    assert classify_title(title, search_term) == (True, "off_cycle_internship_title")


@pytest.mark.parametrize(("title", "search_term"), [
    ("Product Management Intern", "Product Manager Intern Fall 2026"),
    ("Product Management Intern", "Product Manager Intern Spring 2027"),
    ("Product Management Intern", "Product Manager Intern"),
    ("MBA Intern", "MBA Intern"),
])
def test_ambiguous_and_legacy_generic_internships_do_not_enter_hydration(title, search_term):
    assert classify_title(title, search_term)[0] is False


def test_graduation_year_does_not_override_fall_internship():
    assert classify_start_timing(
        "Product Management Intern - Fall 2026",
        "Applicants graduate in May 2027. This fall 2026 internship starts in September.",
    ) == "fall_2026_internship"


def test_explicit_spring_2027_internship_is_supported_off_cycle():
    assert classify_start_timing(
        "Product Management Intern - Spring 2027",
        "This part-time internship runs during the Spring 2027 semester.",
    ) == "spring_2027_internship"


def test_capture_and_hydration_prioritize_full_time():
    priorities = [discovery_priority(term) for term in LINKEDIN_SEARCH_TERMS]
    assert priorities == sorted(priorities)
    assert priorities.count(0) > priorities.count(1) > 0
    assert len(FULL_TIME_SEARCHES) == 14
    assert len(OFF_CYCLE_INTERNSHIP_SEARCHES) == 6
    assert "Product Manager Intern Fall 2026" not in LINKEDIN_SEARCH_TERMS
    assert "Product Manager Intern" not in LINKEDIN_SEARCH_TERMS
    assert "MBA Intern" not in LINKEDIN_SEARCH_TERMS
    from discovery.auto.linkedin_live import DEFAULT_SEARCHES
    assert [term for term, _ in DEFAULT_SEARCHES] == list(LINKEDIN_SEARCH_TERMS)


def test_handshake_active_lane_requires_explicit_spring_title():
    from discovery.auto.import_handshake_csv import (
        CsvJob,
        HANDSHAKE_QUERY_PACKS,
        _handshake_title_prefilter_reason,
    )

    def job(title):
        return CsvJob("1", "Example", title, "Technology", "", "", "", "")

    assert HANDSHAKE_QUERY_PACKS["A"] == ("product manager intern Spring 2027",)
    assert _handshake_title_prefilter_reason(job("Product Manager Intern")) == (
        "lane_a_not_explicit_spring_2027"
    )
    assert _handshake_title_prefilter_reason(
        job("Product Manager Intern - Spring 2027")
    ) == ""


def test_startup_active_sources_do_not_request_internship_feeds():
    from discovery.auto import startup_apply_pipeline as startup

    assert "intern" not in startup.A16Z_FALLBACK_SEARCH_TERMS
    assert all(
        "internship" not in url.casefold()
        for source in startup.SOURCE_REGISTRY
        for url in source.seed_urls
    )


def test_targeted_runner_never_scores_unhydrated_capture(tmp_path, monkeypatch):
    from discovery.scripts import run_linkedin_targeted as runner
    raw = tmp_path / "raw.json"
    selected = tmp_path / "selected.json"
    hydrated = tmp_path / "hydrated.json"
    selected.write_text('{"count": 1}')
    stages = []
    outputs = iter([raw, selected, hydrated])
    def stage(arguments, marker):
        stages.append(arguments)
        return next(outputs)
    monkeypatch.setattr(runner, "stage", stage)
    monkeypatch.setattr(sys, "argv", ["runner", "--window", "7d", "--extract-only"])
    assert runner.main() == 0
    assert "--count-only" in stages[0]
    assert "--exclude-workbook" in stages[1]
    assert stages[2][stages[2].index("--hydrate-from-raw") + 1] == str(selected)
    assert stages[2][stages[2].index("--max-hydrate") + 1] == "75"
    assert "--hydrate-from-raw" in stages[2]


def test_targeted_runner_zero_candidates_skips_hydration(tmp_path, monkeypatch):
    from discovery.scripts import run_linkedin_targeted as runner
    empty = tmp_path / "empty.json"
    empty.write_text('{"count": 0}')
    stages = []
    def stage(arguments, marker):
        stages.append(arguments)
        return empty
    monkeypatch.setattr(runner, "stage", stage)
    monkeypatch.setattr(sys, "argv", ["runner", "--extract-only"])
    assert runner.main() == 0
    assert len(stages) == 2

def test_capture_only_saves_cards_without_hydration(tmp_path, monkeypatch):
    from discovery.scripts import run_linkedin_targeted as runner
    selected=tmp_path/'selected.json'
    selected.write_text('{"count": 1}')
    calls=[]
    monkeypatch.setattr(runner,'stage',lambda arguments,marker: calls.append(arguments) or selected)
    monkeypatch.setattr(sys,'argv',['runner','--capture-only','--pages','1','--limit-per-search','25'])
    assert runner.main()==0
    assert len(calls)==2
    assert calls[0][calls[0].index('--pages')+1]=='1'
