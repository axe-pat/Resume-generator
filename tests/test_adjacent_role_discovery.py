from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_daily_jobspy_has_explicit_full_time_adjacent_queries() -> None:
    scraper = _load(ROOT / "discovery" / "auto" / "scraper.py", "adjacent_scraper")
    daily = _load(
        ROOT / "discovery" / "scripts" / "run_daily_engine.py",
        "adjacent_daily_engine",
    )
    by_id = {item["id"]: (index, item) for index, item in enumerate(scraper.QUERIES)}

    strategy_index, strategy = by_id["strategy_ops_new_grad"]
    bizops_index, bizops = by_id["bizops_analyst_new_grad"]

    assert strategy["search_term"] == "Strategy Operations New Grad"
    assert bizops["search_term"] == "Business Operations Analyst New Grad"
    assert strategy_index in daily.DAILY_JOBSPY_QUERY_INDICES
    assert bizops_index in daily.DAILY_JOBSPY_QUERY_INDICES
    weekly_ids = {scraper.QUERIES[i]['id'] for i in daily.WEEKLY_JOBSPY_QUERY_INDICES}
    assert {'gtm_strategy_ops_new_grad', 'product_strategy_ops_new_grad'} <= weekly_ids


@pytest.mark.parametrize(
    "title",
    [
        "Product Strategist Intern - Spring 2027",
        "Growth Strategy Intern - Spring 2027",
        "Growth Operations Intern - Spring 2027",
        "Startup Operations & Growth Intern - Spring 2027",
        "Category User Growth Project Intern - Spring 2027",
    ],
)
def test_source_breadth_surfaces_conservative_adjacent_intern_titles(title: str) -> None:
    breadth = _load(
        ROOT / "discovery" / "scripts" / "validate_source_breadth.py",
        "adjacent_source_breadth",
    )

    result = breadth.classify_job(
        {
            "company": "Focused Startup",
            "role_title": title,
            "url": "https://jobs.example/adjacent-role",
            "jd_text": "This Spring 2027 internship includes cross-functional product and business metrics work.",
            "source": "linkedin",
        },
        "jobspy_only",
    )

    assert result.verdict == "app_score_now"


@pytest.mark.parametrize(
    "title",
    [
        "Business Growth Intern - Spring 2027",
        "Startup Growth Fellow",
        "Growth Marketing Intern",
        "Sales Growth Strategy Intern - Spring 2027",
        "Marketing Product Manager - Digital Growth",
    ],
)
def test_source_breadth_rejects_generic_growth_sales_and_marketing(title: str) -> None:
    breadth = _load(
        ROOT / "discovery" / "scripts" / "validate_source_breadth.py",
        "adjacent_source_breadth_noise",
    )

    result = breadth.classify_job(
        {
            "company": "Noisy Company",
            "role_title": title,
            "url": "https://jobs.example/noisy-role",
            "jd_text": "This Spring 2027 internship is general commercial execution.",
            "source": "linkedin",
        },
        "jobspy_only",
    )

    assert result.verdict == "skip_noise"


def test_startup_sources_include_growth_ops_but_not_generic_growth() -> None:
    startup = _load(
        ROOT / "discovery" / "auto" / "startup_apply_pipeline.py",
        "adjacent_startup_apply",
    )

    assert startup._is_target_startup_role("Growth Operations Intern")
    assert startup._is_target_startup_role("Operations & Growth Associate")
    assert startup._is_target_startup_role("Category User Growth Project Intern")
    assert not startup._is_target_startup_role("Business Growth Intern")
    assert not startup._is_target_startup_role("Growth Marketing Intern")
    assert not startup._is_target_startup_role("Sales Growth Strategy Intern")


def test_a16z_current_next_page_payload_is_normalized_for_target_filtering() -> None:
    startup = _load(
        ROOT / "discovery" / "auto" / "startup_apply_pipeline.py",
        "a16z_current_startup_apply",
    )
    current_job = {
        "title": "Associate Product Manager, New Grad",
        "company_name": "Portfolio Co",
        "apply_url": "https://jobs.example/apm",
        "locations": ["San Francisco, California"],
        "seniorities": ["Junior"],
        "company_stage": "Venture",
        "company_markets": ["AI"],
        "posted_at": "2026-09-02T12:00:00Z",
    }
    streamed = json.dumps([1, f'0:["$",{{"initialData":{{"jobs":[{json.dumps(current_job)}],"total":1}}}}]'])
    html = f"<html><body><script>self.__next_f.push({streamed})</script></body></html>"

    initial = startup._a16z_initial_data_from_html(html)
    normalized = startup._normalize_current_a16z_job(initial["jobs"][0])

    assert normalized["applyUrl"] == "https://jobs.example/apm"
    assert normalized["companyName"] == "Portfolio Co"
    assert normalized["jobSeniorities"] == [{"label": "Junior", "value": "junior"}]
    assert startup._a16z_is_target_job(normalized)
