from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_jobspy_query_packs_preserve_lane_a_and_add_all_lane_b_families() -> None:
    from discovery.auto import scraper

    assert len(scraper.LANE_A_QUERIES) == 13
    assert all(query["lane"] == "A" for query in scraper.LANE_A_QUERIES)
    assert all("intern" in query["search_term"].lower() for query in scraper.LANE_A_QUERIES)
    assert all(query["lane"] == "B" for query in scraper.LANE_B_QUERIES)
    assert scraper.QUERIES == [*scraper.LANE_A_QUERIES, *scraper.LANE_B_QUERIES]

    search_terms = {query["search_term"].lower() for query in scraper.LANE_B_QUERIES}
    expected = {
        "new grad product manager",
        "apm 2027",
        "associate product manager new grad",
        "product manager university graduate",
        "mba leadership development program",
        "rotational program",
        "strategy operations new grad",
        "business operations analyst new grad",
        "technical program manager new grad",
        "forward deployed engineer",
        "solutions engineer",
        "applied ai engineer",
        "solutions architect",
        "deployment engineer",
        "technical solutions consultant",
        "partner engineer",
        "product analyst new grad",
        "business program manager new grad",
        "business planning operations new grad",
        "corporate development new grad",
        "revenue operations new grad",
        "gtm strategy operations new grad",
        "technical account manager",
        "implementation engineer",
        "deployment strategist",
        "rotational product manager 2027",
        "product management leadership program",
        "pathways operations manager mba",
        "strategic product lead",
        "strategic partner manager",
        "strategic partnerships lead",
        "data platform product manager new grad",
    }
    assert expected.issubset(search_terms)
    assert not any("consulting associate" in term for term in search_terms)
    assert {query["role_type"] for query in scraper.LANE_B_QUERIES} >= {
        "PM",
        "Ops",
        "Strategy",
        "TPM",
        "Solutions",
    }


def test_scheduled_jobspy_lane_is_demoted_to_lane_a_without_deleting_lane_b() -> None:
    from discovery.auto import scraper
    from discovery.scripts import run_daily_engine

    lane_a_indices = {
        index for index, query in enumerate(scraper.QUERIES) if query["lane"] == "A"
    }
    lane_b_indices = {
        index for index, query in enumerate(scraper.QUERIES) if query["lane"] == "B"
    }
    assert set(run_daily_engine.DAILY_JOBSPY_QUERY_INDICES) == lane_a_indices
    assert set(run_daily_engine.WEEKLY_JOBSPY_QUERY_INDICES) == lane_a_indices
    assert lane_b_indices
    assert lane_b_indices.isdisjoint(run_daily_engine.DAILY_JOBSPY_QUERY_INDICES)
    assert lane_b_indices.isdisjoint(run_daily_engine.WEEKLY_JOBSPY_QUERY_INDICES)
    assert run_daily_engine.WEEKLY_JOBSPY_RESULTS == 60


def test_profile_and_scorer_make_lane_b_primary_equivalent() -> None:
    profile = (ROOT / "profile" / "profile.md").read_text(encoding="utf-8")
    scorer_prompt = (ROOT / "discovery" / "auto" / "scorer_prompt.md").read_text(
        encoding="utf-8"
    )
    lane_b = profile.split("### Lane B", 1)[1].split("---", 1)[0]
    lane_b_primary = lane_b.split("#### Primary Targets", 1)[1].split(
        "#### Secondary Targets", 1
    )[0]

    assert "same scoring priority" in profile
    assert "Technical Program Manager — New Grad" in lane_b_primary
    assert "Data / Platform / Infrastructure / Developer-Tools Product Manager" in lane_b_primary
    assert "Forward-Deployed Engineer" in lane_b_primary
    assert "Management consulting" in lane_b
    assert "Lane B Primary targets are equivalent priority" in scorer_prompt
    assert "PM / Strategy / Ops / TPM / Solutions / Other" in scorer_prompt


def test_start_timing_rejects_2027_internships_and_bare_years() -> None:
    from shared.job_eligibility import classify_start_timing, pre_filter_discovery_timing

    assert pre_filter_discovery_timing(
        "Product Manager Intern", "Fall 2026 internship", "A"
    ) == (False, "")
    assert pre_filter_discovery_timing(
        "Product Manager Intern",
        "Fall 2026 internship. Eligible candidates graduate in May 2027.",
        "A",
    ) == (False, "")

    rejected, reason = pre_filter_discovery_timing(
        "Product Manager Intern", "Summer 2027 internship", "A"
    )
    assert rejected
    assert "Summer 2027" in reason

    rejected, reason = pre_filter_discovery_timing(
        "Product Manager Intern", "2027 internship program", "A"
    )
    assert rejected
    assert "2027 internship" in reason

    assert pre_filter_discovery_timing(
        "Associate Product Manager", "Open to the Class of 2027 and new graduates.", "B"
    ) == (False, "")
    assert pre_filter_discovery_timing(
        "Product Manager (2027 Graduates)",
        "Applications for the full-time role will be reviewed starting August 2026.",
        "B",
    ) == (False, "")
    assert pre_filter_discovery_timing(
        "Product Manager (2027 Graduates)",
        "We will officially begin reviewing applications and scheduling interviews starting August 2026.",
        "B",
    ) == (False, "")
    assert pre_filter_discovery_timing(
        "Solutions Engineer", "The cohort starts in July 2027.", "B"
    ) == (False, "")
    assert classify_start_timing(
        "Product Manager Graduate (Sales and Operations Management Platform) - 2027 Start",
        "As a graduate, state your availability and graduation date.",
    ) == "new_grad_eligible"
    assert classify_start_timing(
        "Technical Management Development Program 2027",
        "Anticipated Start Date: January & July 2027. Applications will be reviewed in October.",
    ) == "mid_2027_or_later_full_time"
    assert classify_start_timing(
        "Associate Application Consultant 2027",
        "IBM Associate Program for university hires.",
    ) == "new_grad_eligible"
    assert classify_start_timing(
        "Business Management Associate 2027 - Multiple US Locations",
        "Full-time role.",
    ) == "new_grad_eligible"
    assert classify_start_timing(
        "Digital Rotational Analyst - May 2027 Grads",
        "Full-time role.",
    ) == "new_grad_eligible"

    rejected, reason = pre_filter_discovery_timing(
        "Solutions Engineer", "Copyright 2027. This is a full-time role.", "B"
    )
    assert rejected
    assert "no explicit new-grad" in reason

    rejected, reason = pre_filter_discovery_timing(
        "Solutions Engineer", "Immediate start; full-time.", "B"
    )
    assert rejected
    assert "immediate-start" in reason

    rejected, reason = pre_filter_discovery_timing(
        "2026 June - Associate Product Manager (New Grad)",
        "Full-time early-career product role.",
        "B",
    )
    assert rejected
    assert "before June 2027" in reason

    rejected, reason = pre_filter_discovery_timing(
        "Associate Product Manager - New Grad",
        "The cohort starts in March 2027.",
        "B",
    )
    assert rejected
    assert "before June 2027" in reason


def test_prior_internship_experience_does_not_turn_full_time_role_into_internship() -> None:
    from shared.job_eligibility import classify_start_timing, pre_filter_discovery_timing

    title = "Technical Sales Engineer - Entry-Level Sales Program 2027"
    jd = (
        "This full-time entry-level sales program begins in 2027. "
        "Preferred experience includes an internship, co-op, research, project, or extracurricular work."
    )
    assert classify_start_timing(title, jd) == "new_grad_eligible"
    assert pre_filter_discovery_timing(title, jd, "B") == (False, "")

    assert classify_start_timing(
        "Solution Architect Intern - Entry Level Sales Program 2027",
        jd,
    ) == "other_2027_internship"


def test_linkedin_live_repairs_stale_error_and_upgrades_raw_jobspy_provenance() -> None:
    import pandas as pd

    from discovery.auto.linkedin_live import (
        _split_existing_jobs,
        append_new_jobs,
        title_company_hash,
        url_hash,
    )
    from discovery.auto.pipeline import COLUMNS

    existing = pd.DataFrame(
        [
            {
                "id": "2558",
                "date_found": "2026-08-02",
                "company": "Databricks",
                "role_title": "Associate Product Manager, New Grad (2027 Start)",
                "url": "https://builtin.example/databricks-apm",
                "url_hash": url_hash("https://builtin.example/databricks-apm"),
                "source": "builtin_startup_jobs",
                "status": "error",
                "fit_score": None,
            },
            {
                "id": "2965",
                "date_found": "2026-08-18",
                "company": "IXL Learning",
                "role_title": "IXL Associate Product Manager",
                "url": "https://linkedin.example/ixl-jobspy",
                "url_hash": url_hash("https://linkedin.example/ixl-jobspy"),
                "source": "linkedin",
                "status": "queued",
                "fit_score": 7.6,
            },
        ],
        columns=COLUMNS,
    )
    live_jobs = []
    for company, title, live_url in (
        (
            "Databricks",
            "Associate Product Manager, New Grad (2027 Start)",
            "https://linkedin.example/databricks-live",
        ),
        ("IXL Learning", "IXL Associate Product Manager", "https://linkedin.example/ixl-live"),
    ):
        live_jobs.append(
            {
                "company": company,
                "role_title": title,
                "url": live_url,
                "url_hash": url_hash(live_url),
                "tc_hash": title_company_hash(title, company),
                "source": "linkedin_live_jobs_v1",
                "status": "queued",
                "fit_score": 8.0,
                "jd_text": "Full-time new-grad role for 2027 graduates.",
            }
        )

    repairable, existing_hits = _split_existing_jobs(live_jobs, existing)
    assert len(repairable) == 2
    assert not existing_hits

    merged, written = append_new_jobs(existing.copy(), repairable)
    assert len(written) == 2
    assert len(merged) == 2
    assert set(merged["source"]) == {"linkedin_live_jobs_v1"}
    assert set(merged["id"]) == {"2558", "2965"}


def test_scraper_routes_cross_query_results_by_actual_timing_before_dedup() -> None:
    import pandas as pd

    from discovery.auto.scraper import LANE_A_QUERIES, _normalise_row

    job = _normalise_row(
        pd.Series(
            {
                "title": "Product Manager - New Grad",
                "company": "Example",
                "description": "Open to Class of 2027 new graduates.",
                "job_url": "https://example.com/new-grad",
                "site": "linkedin",
            }
        ),
        LANE_A_QUERIES[0],
    )
    assert job["query_lane"] == "A"
    assert job["lane"] == "B"
    assert job["classification"] == "keep"
    assert job["notes"] in {"", None}


def test_lane_b_h1b_language_is_a_soft_flag_and_everify_is_captured() -> None:
    from shared.job_eligibility import annotate_discovery_job, pre_filter_immigration

    jd = "New grad role for the Class of 2027. We will not sponsor H-1B. We are an E-Verify employer."
    assert pre_filter_immigration(jd) == (False, "")
    job = annotate_discovery_job(
        {
            "lane": "B",
            "role_title": "Technical Program Manager - New Grad",
            "jd_text": jd,
            "notes": "",
        }
    )
    assert job["e_verify_status"] == "yes"
    assert job["everify_status"] == "yes"
    assert "h1b_sponsorship_unavailable" in job["eligibility_flags"]
    assert job["sponsorship_flag"] == "h1b_sponsorship_unavailable"
    assert "e_verify=" not in job["notes"]

    rejected, reason = pre_filter_immigration(
        "Candidates must be authorized to work on a permanent basis."
    )
    assert rejected
    assert "Immigration hard reject" in reason
    assert pre_filter_immigration(
        "You must be authorised to work permanently without sponsorship."
    )[0]


def test_model_cannot_hard_reject_lane_b_for_generic_no_sponsorship() -> None:
    from discovery.auto import scorer

    class Messages:
        def create(self, **kwargs):
            del kwargs

            class Response:
                class Item:
                    text = """Decision: Reject
Category: N/A
fit_score: 0.0
Breakdown: PM Fit: 0 | Tech: 0 | Brand: 0 | Quality: 0 | Conversion: 0 | Total: 0/25
Rationale: This role is not eligible for visa sponsorship, so the candidate cannot pursue it.
role_type: Solutions"""

                content = [Item()]

            return Response()

    class Client:
        messages = Messages()

    result = scorer.score_job(
        {
            "company": "Example",
            "role_title": "Technical Sales Engineer - Graduate Rotational Program",
            "lane": "B",
            "jd_text": (
                "This is a full-time graduate rotational program for 2027 graduates. "
                "This role is not eligible for visa sponsorship."
            ),
        },
        client=Client(),
        profile_text="profile",
        scorer_text="rubric",
        verbose=False,
    )
    assert result["decision"] == "Unsure"
    assert result["status"] == "review"
    assert "does not explicitly exclude F-1" in result["fit_rationale"]


def test_model_rechecks_canonical_technical_gtm_role_type_reject() -> None:
    from discovery.auto import scorer

    responses = iter(
        [
            """Decision: Reject
Category: N/A
fit_score: 0.0
Breakdown: PM Fit: 0 | Tech: 0 | Brand: 0 | Quality: 0 | Conversion: 0 | Total: 0/25
Rationale: Technical Sales Engineer is sales execution without product ownership and outside the target scope.
role_type: Solutions""",
            """Decision: Proceed
Category: High Priority
fit_score: 8.2
Breakdown: PM Fit: 4 | Tech: 5 | Brand: 5 | Quality: 3 | Conversion: 3 | Total: 20/25
Rationale: Graduate Technical Sales Engineer program combines customer discovery, technical solution design, demos, and strong engineering leverage at AMD.
role_type: Solutions""",
        ]
    )

    class Messages:
        def create(self, **kwargs):
            del kwargs

            class Response:
                class Item:
                    text = next(responses)

                content = [Item()]

            return Response()

    class Client:
        messages = Messages()

    result = scorer.score_job(
        {
            "company": "AMD",
            "role_title": "Technical Sales Engineer - Graduate Rotational Program",
            "lane": "B",
            "jd_text": (
                "Entry-level graduate rotational program. Engage directly with customers to identify "
                "their challenges, propose technical solutions, and deliver demos."
            ),
        },
        client=Client(),
        profile_text="profile",
        scorer_text="rubric",
        verbose=False,
    )

    assert result["decision"] == "Proceed"
    assert result["fit_score"] == 8.2
    assert result["role_type"] == "Solutions"


def test_technical_gtm_correction_cannot_reject_generic_sponsorship() -> None:
    from discovery.auto import scorer

    responses = iter(
        [
            """Decision: Reject
Category: N/A
fit_score: 0.0
Breakdown: PM Fit: 0 | Tech: 0 | Brand: 0 | Quality: 0 | Conversion: 0 | Total: 0/25
Rationale: Technical Sales Engineer is outside the target scope because it lacks product ownership.
role_type: Solutions""",
            """Decision: Reject
Category: N/A
fit_score: 0.0
Breakdown: PM Fit: 0 | Tech: 0 | Brand: 0 | Quality: 0 | Conversion: 0 | Total: 0/25
Rationale: The JD states no visa sponsorship, which is a hard F-1 and OPT rejection.
role_type: Solutions""",
        ]
    )

    class Messages:
        def create(self, **kwargs):
            del kwargs

            class Response:
                class Item:
                    text = next(responses)

                content = [Item()]

            return Response()

    class Client:
        messages = Messages()

    result = scorer.score_job(
        {
            "company": "AMD",
            "role_title": "Technical Sales Engineer - Graduate Rotational Program",
            "lane": "B",
            "jd_text": (
                "Entry-level graduate rotational program for driven graduates, with customer "
                "discovery and technical demos. "
                "This role is not eligible for visa sponsorship."
            ),
        },
        client=Client(),
        profile_text="profile",
        scorer_text="rubric",
        verbose=False,
    )

    assert result["decision"] == "Unsure"
    assert "does not explicitly exclude F-1" in result["fit_rationale"]


def test_deadline_capture_and_manual_program_lookup_do_not_invent_dates() -> None:
    from shared.job_eligibility import annotate_discovery_job, extract_application_deadline

    deadline, source = extract_application_deadline(
        "Applications close on September 8, 2026."
    )
    assert deadline == "2026-09-08"
    assert source == "Applications close on September 8, 2026"

    window, _ = extract_application_deadline(
        "Applications are open from August 20, 2026 through September 5, 2026."
    )
    assert window == "2026-08-20/2026-09-05"
    accepted_until, _ = extract_application_deadline(
        "Applications will be accepted until October 15, 2026."
    )
    assert accepted_until == "2026-10-15"

    job = annotate_discovery_job(
        {
            "lane": "B",
            "role_title": "MBA Leadership Development Program",
            "jd_text": "For graduating MBA students in the Class of 2027.",
            "notes": "",
        }
    )
    assert job["application_deadline"] == ""
    assert job["deadline"] == ""
    assert job["deadline_lookup"] == "manual"
    assert job["deadline_source"] == "manual_lookup"
    assert "deadline_lookup=" not in job["notes"]


def test_lane_c_uses_pay_and_shift_gate_without_pm_scoring() -> None:
    from discovery.auto.scorer import score_job

    kept = score_job(
        {
            "company": "USC",
            "role_title": "Research Assistant",
            "lane": "C",
            "pay_text": "$24/hour",
            "jd_text": "Independent research support with flexible hours.",
            "notes": "",
        },
        client=None,
        profile_text="unused",
        scorer_text="unused",
        verbose=False,
    )
    assert kept["decision"] == "Proceed"
    assert kept["status"] == "review"
    assert kept["fit_score"] is None
    assert kept["category"] == "Income Now"

    below_floor = score_job(
        {
            "company": "USC",
            "role_title": "Teaching Assistant",
            "lane": "C",
            "pay_text": "$19-$25/hour",
            "jd_text": "Assist a course.",
            "notes": "",
        },
        client=None,
        profile_text="unused",
        scorer_text="unused",
        verbose=False,
    )
    assert below_floor["decision"] == "Reject"
    assert "hourly floor" in below_floor["rejection_reason"]

    shift = score_job(
        {
            "company": "USC",
            "role_title": "Coffee Shop Barista",
            "lane": "C",
            "pay_text": "$25/hour",
            "jd_text": "Customer-facing shifts.",
            "notes": "",
        },
        client=None,
        profile_text="unused",
        scorer_text="unused",
        verbose=False,
    )
    assert shift["decision"] == "Reject"
    assert "customer-facing shift" in shift["rejection_reason"]


def test_lane_c_prefers_explicit_pay_before_neighboring_job_ranges() -> None:
    from shared.job_eligibility import evaluate_lane_c

    eligible, reason, low, high = evaluate_lane_c(
        "Student Services Assistant",
        "Selected job details.\nSimilar Jobs\nStudent Assistant $15-$20/hr",
        "$20/hr",
    )

    assert eligible is True
    assert reason == "Lane C keep — stated hourly pay is $20"
    assert (low, high) == (20.0, 20.0)


def test_lane_c_ignores_negated_shift_language_but_catches_later_positive_scope() -> None:
    from shared.job_eligibility import evaluate_lane_c

    eligible, reason, _, _ = evaluate_lane_c(
        "Hospitality Administrative Assistant",
        "This administrative role does not involve front-line food service.",
        "$20/hour",
    )
    assert eligible is True
    assert reason == "Lane C keep — stated hourly pay is $20"

    eligible, reason, _, _ = evaluate_lane_c(
        "Hospitality Administrative Assistant",
        (
            "This administrative role does not involve front-line food service. "
            "The role may later support cashiering or kitchen responsibilities."
        ),
        "$20/hour",
    )
    assert eligible is False
    assert "cashiering" in reason


def test_linkedin_cache_invalidates_timing_reject_from_the_wrong_lane() -> None:
    from discovery.auto.linkedin_live import _cached_decision_is_stale

    job = {
        "role_title": "Associate Product Manager",
        "lane": "B",
        "jd_text": "Full-time product role with no explicit cohort timing.",
    }
    cached = {
        "decision": "Reject",
        "fit_rationale": "[Reject | N/A] Lane A timing reject — result is not a Fall 2026 internship",
    }

    assert _cached_decision_is_stale(job, cached) is True


def test_linkedin_cache_invalidates_stale_technical_gtm_reject() -> None:
    from discovery.auto.linkedin_live import _cached_decision_is_stale

    job = {
        "role_title": "Technical Sales Engineer - Graduate Rotational Program",
        "lane": "B",
        "jd_text": (
            "Entry-level graduate rotational program. Engage directly with customers, "
            "identify their challenges, and propose technical solutions."
        ),
    }
    cached = {
        "decision": "Reject",
        "fit_rationale": "Role is outside the target scope and does not meet the Technical GTM exception.",
    }

    assert _cached_decision_is_stale(job, cached) is True


def test_linkedin_cache_rechecks_new_hard_f1_exclusion() -> None:
    from discovery.auto.linkedin_live import _cached_decision_is_stale

    job = {
        "role_title": "Technology Rotational Analyst 2027",
        "lane": "B",
        "jd_text": (
            "We will not offer immigration-related support for this position, "
            "including F-1 OPT, F-1 STEM OPT, or F-1 CPT."
        ),
    }
    cached = {
        "decision": "Unsure",
        "fit_rationale": "Unknown title with JD signals: new-grad/2027 timing",
    }

    assert _cached_decision_is_stale(job, cached) is True


def test_innovation_analyst_is_a_strategy_bizops_surface() -> None:
    from shared.job_eligibility import classify_role_surface

    decision, _, family = classify_role_surface(
        "Innovation Analyst - Early Talent 2027",
        "Graduate programme starting Fall 2027.",
    )

    assert decision == "keep"
    assert family == "Strategy / BizOps"


def test_september_2026_intern_start_is_lane_a_eligible() -> None:
    from shared.job_eligibility import pre_filter_discovery_timing

    rejected, reason = pre_filter_discovery_timing(
        "AI Product Manager Intern",
        "Anticipated Start Date: September 2026. Contract duration: 6 months.",
        "A",
    )

    assert rejected is False
    assert reason == ""


def test_cohorted_program_with_june_july_start_is_lane_b_eligible() -> None:
    from shared.job_eligibility import pre_filter_discovery_timing

    rejected, reason = pre_filter_discovery_timing(
        "Associate Value Engineer - Orbit Program",
        (
            "The program is structured into classes and cohorts. You'll likely join a cohort "
            "with a summer start date (June/July) or a winter start date (January/February)."
        ),
        "B",
    )

    assert rejected is False
    assert reason == ""


def test_lane_c_keep_reaches_queue_without_fabricated_fit_score() -> None:
    import pandas as pd

    from discovery.scripts.refresh_current_apply_queue import _lane_c_ready_mask

    frame = pd.DataFrame(
        [
            {
                "source": "handshake_jobs_v1",
                "lane": "C",
                "classification": "keep",
                "status": "review",
                "fit_score": None,
            },
            {
                "source": "handshake_jobs_v1",
                "lane": "C",
                "classification": "reject",
                "status": "skipped",
                "fit_score": 0,
            },
        ]
    )
    assert _lane_c_ready_mask(frame).tolist() == [True, False]


def test_forward_deployed_lane_b_survives_breadth_filter_only_with_timing() -> None:
    from discovery.scripts.validate_source_breadth import classify_job

    kept = classify_job(
        {
            "company": "AI Co",
            "role_title": "Forward Deployed Software Engineer",
            "lane": "B",
            "url": "https://example.com/fde-2027",
            "source": "linkedin",
            "jd_text": "New graduate role for the Class of 2027 with customer deployment ownership.",
        },
        "jobspy_only",
    )
    assert kept.lane == "B"
    assert kept.verdict == "app_score_now"

    rejected = classify_job(
        {
            "company": "AI Co",
            "role_title": "Forward Deployed Engineer",
            "lane": "B",
            "url": "https://example.com/fde-now",
            "source": "linkedin",
            "jd_text": "Full-time role with an immediate start.",
        },
        "jobspy_only",
    )
    assert rejected.verdict == "skip_noise"
    assert any("immediate-start" in reason for reason in rejected.reasons)


def test_unknown_title_with_body_signals_is_unsure_not_silently_rejected() -> None:
    from discovery.auto.scorer import score_job
    from discovery.scripts.validate_source_breadth import classify_job

    job = {
        "company": "Novel AI Co",
        "role_title": "Customer Systems Builder",
        "lane": "B",
        "url": "https://example.com/novel-title",
        "source": "linkedin",
        "jd_text": (
            "Class of 2027 new graduates will work directly with customers, own technical "
            "discovery, and coordinate cross-functional engineering and product teams."
        ),
        "notes": "",
    }
    classified = classify_job(dict(job), "jobspy_only")
    assert classified.verdict == "unsure"
    assert any("Unknown title with JD signals" in reason for reason in classified.reasons)

    scored = score_job(
        dict(job),
        client=None,
        profile_text="unused",
        scorer_text="unused",
        verbose=False,
    )
    assert scored["decision"] == "Unsure"
    assert scored["status"] == "review"
    assert scored["fit_score"] is None


def test_generic_software_engineering_stays_out_but_technical_gtm_is_in() -> None:
    from shared.job_eligibility import classify_role_surface, pre_filter_discovery_scope
    from discovery.scripts.select_linkedin_2027_candidates import classify_title

    rejected, reason = pre_filter_discovery_scope("Backend Software Engineer - New Grad", "B")
    assert rejected
    assert "software engineering" in reason

    assert pre_filter_discovery_scope("Forward Deployed Software Engineer - New Grad", "B") == (
        False,
        "",
    )
    assert pre_filter_discovery_scope("Associate Solutions Consultant (2027 Graduates)", "B") == (
        False,
        "",
    )
    assert classify_title("Forward Deployed Software Engineer, New Grad 2027") == (
        True,
        "target_family:technical_gtm",
    )
    assert classify_title("Software Engineer, New Grad 2027")[0] is False
    assert classify_title("Associate Product Manager, 2027 Graduates")[0] is True
    for title in (
        "Associate Application Consultant 2027",
        "Delivery Consultant - Entry Level Sales Program 2027",
        "Ecosystem Governance Strategy Operations Graduate",
        "Operations Management Development Program 2027",
        "Commercial Development Program (July 2027 Start)",
    ):
        assert classify_role_surface(title, "")[0] == "keep"


def test_custom_2027_linkedin_search_carries_lane_b_metadata() -> None:
    from discovery.auto.linkedin_live import LinkedInJobCard, cards_to_jobs

    card = LinkedInJobCard(
        search_term="2027",
        time_filter="r2592000",
        title="Product Manager Graduate - 2027 Start",
        company="Example",
        location="New York, NY",
        url="https://www.linkedin.com/jobs/view/123/",
        listed_at="1 day ago",
        insight="",
        jd_text="Full-time graduate role.",
    )
    assert cards_to_jobs([card])[0]["lane"] == "B"
    card.search_term = "Product Manager Intern"
    assert cards_to_jobs([card])[0]["lane"] == "A"


def test_pipeline_appends_discovery_columns_and_reports_lane_reject_reasons(capsys) -> None:
    import jobs
    from discovery.auto import pipeline

    assert pipeline.COLUMNS == jobs.COLUMNS
    assert len(pipeline.COLUMNS) == 25
    assert pipeline.COLUMNS[-7:] == [
        "lane",
        "deadline",
        "deadline_source",
        "everify_status",
        "sponsorship_flag",
        "classification",
        "reject_reason",
    ]

    pipeline.print_digest(
        [
            {
                "lane": "A",
                "decision": "Proceed",
                "category": "High Priority",
                "fit_score": 8.0,
                "company": "A Co",
                "role_title": "PM Intern",
            },
            {
                "lane": "B",
                "decision": "Reject",
                "category": "N/A",
                "rejection_reason": "Lane B timing reject — immediate-start full-time role",
                "fit_rationale": "[Reject | N/A] Lane B timing reject — immediate-start full-time role",
                "company": "B Co",
                "role_title": "Solutions Engineer",
            },
        ],
        datetime.now(),
    )
    output = capsys.readouterr().out
    assert "Lane A: 1 found" in output
    assert "Lane B: 1 found" in output
    assert "Lane C: 0 found" in output
    assert "Rejects by reason" in output
    assert "immediate-start full-time role" in output


def test_offline_replay_rejects_named_summer_2027_rows() -> None:
    from shared.job_eligibility import classify_discovery_job_offline

    rows = [
        {
            "company": "Salesforce",
            "role_title": "Summer 2027 Intern - Associate Product Manager (APM)",
            "jd_text": "Summer 2027 internship",
            "notes": "genuine note",
        },
        {
            "company": "Amazon",
            "role_title": "2027 MBA Leadership Development Program (MLDP) Intern",
            "jd_text": "The internship takes place in Summer 2027.",
            "notes": "",
        },
    ]
    for row in rows:
        classified = classify_discovery_job_offline(row)
        assert classified["classification"] == "reject"
        assert "Summer 2027 internship" in classified["reject_reason"]


def test_scraper_checkpoints_each_query_and_skips_timeout(tmp_path, monkeypatch) -> None:
    from discovery.auto import scraper

    def fake_runner(query_index, *, checkpoint_path, log_path, **kwargs):
        query = scraper.QUERIES[query_index]
        if query_index == 0:
            return {
                "status": "completed",
                "query_index": query_index,
                "query_id": query["id"],
                "lane": query["lane"],
                "search_term": query["search_term"],
                "elapsed_seconds": 0.1,
                "result_count": 1,
                "jobs": [{
                    "url_hash": "url-1",
                    "tc_hash": "tc-1",
                    "lane": "A",
                    "role_type": "PM",
                }],
                "error": "",
                "throttle_events": 0,
                "checkpoint_file": str(checkpoint_path),
                "log_file": str(log_path),
            }
        return {
            "status": "timed_out",
            "query_index": query_index,
            "query_id": query["id"],
            "lane": query["lane"],
            "search_term": query["search_term"],
            "elapsed_seconds": 1.0,
            "result_count": 0,
            "jobs": [],
            "error": "Hard query timeout after 1.0s",
            "throttle_events": 0,
            "checkpoint_file": str(checkpoint_path),
            "log_file": str(log_path),
        }

    monkeypatch.setattr(scraper, "run_query_with_timeout", fake_runner)
    monkeypatch.setattr(scraper.time, "sleep", lambda _: None)
    report = {}
    jobs = scraper.scrape(
        query_indices=[0, 1],
        checkpoint_dir=tmp_path,
        per_query_timeout_seconds=1,
        total_timeout_seconds=30,
        run_report=report,
        verbose=False,
    )

    assert len(jobs) == 1
    assert report["query_status_counts"] == {"completed": 1, "timed_out": 1}
    assert report["status"] == "partial"
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert [record["status"] for record in manifest["queries"]] == ["completed", "timed_out"]


def test_query_worker_is_terminated_and_checkpointed_on_hard_timeout(tmp_path, monkeypatch) -> None:
    import subprocess

    from discovery.auto import scraper

    class HungProcess:
        args = ["jobspy-worker"]

        def __init__(self) -> None:
            self.terminated = False

        def wait(self, timeout):
            if not self.terminated:
                raise subprocess.TimeoutExpired(cmd="jobspy-worker", timeout=timeout)
            return 124

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    process = HungProcess()
    monkeypatch.setattr(scraper.subprocess, "Popen", lambda *args, **kwargs: process)

    checkpoint = tmp_path / "query.json"
    outcome = scraper.run_query_with_timeout(
        0,
        hours_old=24,
        results_override=1,
        timeout_seconds=0.1,
        checkpoint_path=checkpoint,
        log_path=tmp_path / "query.log",
    )

    assert process.terminated
    assert outcome["status"] == "timed_out"
    assert outcome["jobs"] == []
    assert "Hard query timeout" in outcome["error"]
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["status"] == "timed_out"


def test_api_scoring_request_is_bounded_by_epoch_deadline(monkeypatch) -> None:
    from discovery.auto import scorer

    captured = {}

    class Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("simulated API failure")

    class Client:
        messages = Messages()

    monkeypatch.setattr(scorer, "RETRY_ATTEMPTS", 1)
    result = scorer.score_job(
        {
            "company": "Example",
            "role_title": "Product Manager Graduate - 2027 Start",
            "lane": "B",
            "jd_text": "2027 new-grad full-time role owning a product roadmap and cross-functional delivery.",
        },
        client=Client(),
        profile_text="profile",
        scorer_text="rubric",
        verbose=False,
        deadline_epoch=time.time() + 0.5,
    )

    assert 0 < captured["timeout"] <= 0.5
    assert result["decision"] == "Error"


def test_pipeline_supervisor_uses_epoch_wall_clock(monkeypatch) -> None:
    import subprocess

    from discovery.auto import pipeline

    class StillRunning:
        args = ["pipeline-worker"]

        def wait(self, timeout):
            raise subprocess.TimeoutExpired(self.args, timeout)

    ticks = iter([100.0, 100.0, 102.0])
    monkeypatch.setattr(pipeline.time, "time", lambda: next(ticks))

    try:
        pipeline._wait_process_wall_clock(StillRunning(), 1.0)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("epoch deadline should stop the worker")


def test_full_time_explicit_experience_caps_are_hard_rejects() -> None:
    from shared.job_eligibility import pre_filter_full_time_level

    for jd in (
        "Less than 2 years of professional experience; this role is for early-career candidates.",
        "Up to 2 years of experience in product management or software development.",
        "Applicants must have no more than three years of professional experience.",
    ):
        rejected, reason = pre_filter_full_time_level("Associate Product Manager", jd)
        assert rejected
        assert "explicit experience cap" in reason
        assert "candidate has 5" in reason


def test_experience_cap_rule_stays_conservative_and_preserves_internships() -> None:
    from shared.job_eligibility import pre_filter_full_time_level

    # A level range is not automatically a hard maximum unless the posting says so.
    assert pre_filter_full_time_level(
        "Associate Value Engineer - Orbit Program",
        "Extensive internship experience or 1-3 years of full-time work experience.",
    ) == (False, "")
    assert pre_filter_full_time_level(
        "Product Manager Intern",
        "Applicants should have up to 1 year of related experience.",
    ) == (False, "")
