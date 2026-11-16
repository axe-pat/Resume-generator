import json
import argparse
from pathlib import Path

import pandas as pd

from discovery.scripts import audit_discovery_coverage as audit
from discovery.scripts.select_linkedin_2027_candidates import classify_title
from discovery.scripts.validate_source_breadth import linkedin_job_key
from shared.job_eligibility import classify_discovery_job_offline, classify_start_timing
from shared.discovery_search_policy import linkedin_search_terms
from shared.discovery_identity import national_recruitment_templates


JD = (
    "The product manager owns the roadmap and customer requirements, working "
    "with engineering on launches. Candidates must be graduating from an MBA "
    "program in 2027. A technical undergraduate degree and three years of "
    "experience are required. We sponsor employment visas for this position."
)


def test_public_description_is_scoped_to_requested_posting():
    from discovery.auto.public_job_description import parse_public_listing
    text = 'Responsibilities: ' + JD * 5
    html = f'<h1>Product Manager</h1><div class="show-more-less-html__markup">{text}</div>'
    result = parse_public_listing(html, requested_url='https://www.linkedin.com/jobs/view/123/',
                                  final_url='https://www.linkedin.com/jobs/view/product-manager-at-example-123')
    assert result['retrieval_status'] == 'retrieved'
    assert result['jd_text'] == text
    assert parse_public_listing(html, requested_url='https://www.linkedin.com/jobs/view/123/',
                                final_url='https://www.linkedin.com/jobs/view/456/')['jd_text'] == ''


def test_public_page_does_not_turn_login_or_closed_listing_into_open_job():
    from discovery.auto.public_job_description import parse_public_listing
    kwargs = dict(requested_url='https://www.linkedin.com/jobs/view/123/',
                  final_url='https://www.linkedin.com/jobs/view/123/')
    assert parse_public_listing('<h1>Sign in</h1>', **kwargs)['jd_text'] == ''
    html = '<p>No longer accepting applications</p><div class="show-more-less-html__markup">Responsibilities: ' + JD * 5 + '</div>'
    assert parse_public_listing(html, **kwargs)['listing_availability'] == 'closed'


def test_signed_in_description_heading_excludes_page_footer():
    from discovery.auto.public_job_description import parse_public_listing
    text = 'Responsibilities: ' + JD * 5
    html = '<main><h1>Product Manager</h1><section><div><h2>About the job</h2></div><div>' + text + '</div></section></main><footer>Looking for talent? LinkedIn Corporation</footer>'
    result = parse_public_listing(html, requested_url='https://www.linkedin.com/jobs/view/123/',
                                  final_url='https://www.linkedin.com/jobs/view/123/')
    assert result['jd_text'] == text


def test_rotational_and_technical_project_titles_do_not_get_stranded():
    from shared.job_eligibility import classify_role_surface, pre_filter_candidate_education
    for title in ['Rotational Associate Manager 2027', 'Spring 2027: Technical Project Management Co-op',
                  'Co-op, Operations Customer Center (OCC) Product Management (Spring 2027)',
                  'Technical Project/Program Management I', 'Product Line Management II']:
        assert classify_role_surface(title, '')[0] == 'keep'
    assert classify_role_surface('BuiLD Associate', 'Join our BuiLD (MBA) rotational development program.')[0] == 'keep'
    assert pre_filter_candidate_education('2027 University Graduate', "Currently enrolled full time and pursuing a Bachelor's degree graduating in 2027.")[0]


def test_blocklisted_proceed_score_cannot_enter_tracker_write_gate(monkeypatch):
    import jobs
    from discovery.auto.linkedin_live import filter_jobs_for_write
    monkeypatch.setattr(jobs, '_load_blocklist', lambda: ['ibm'])
    role = {'company': 'IBM', 'decision': 'Proceed', 'jd_text': JD}
    accepted, dropped = filter_jobs_for_write([role])
    assert not accepted
    assert dropped[0]['__report_gate'] == 'blocklisted'


def test_explicit_future_visa_bar_cannot_enter_tracker_write_gate(monkeypatch):
    import jobs
    from discovery.auto.linkedin_live import filter_jobs_for_write
    monkeypatch.setattr(jobs, '_load_blocklist', lambda: [])
    role = {
        'company': 'Example',
        'decision': 'Proceed',
        'jd_text': 'Must have authorization to work in the U.S., and not require current or future work visa sponsorship to retain authorization to work in the U.S.',
    }
    accepted, dropped = filter_jobs_for_write([role])
    assert not accepted
    assert dropped[0]['__report_gate'] == 'immigration-hard-reject'


def test_future_sponsorship_bar_in_honeywell_wording_is_rejected():
    from shared.job_eligibility import pre_filter_immigration
    jd = 'We are unable to consider applicants who would require current or future sponsorship for employment authorization.'
    assert pre_filter_immigration(jd)[0]
    assert pre_filter_immigration('Applicants must work without current or future sponsorship requirements.')[0]


def test_may_mba_graduation_is_eligible_for_june_2027_full_time_cohort():
    from shared.job_eligibility import pre_filter_candidate_education
    title = '2027 MBA Program'
    assert not pre_filter_candidate_education(title, 'Expected graduation date of June 2027. Full-time role begins after graduation.')[0]
    assert pre_filter_candidate_education(title, 'Expected graduation date of December 2027.')[0]


def test_saved_scoring_can_explicitly_disable_queue_publication(tmp_path, monkeypatch):
    from discovery.auto import linkedin_live as live
    path = tmp_path / 'raw.json'
    path.write_text(json.dumps({'jobs': [{'company': 'Example', 'role_title': 'Product Manager',
        'url': 'https://example.com/jobs/123', 'jd_text': JD, 'source': 'linkedin', 'jobspy_query_id': 'product_manager'}]}))
    calls = []
    monkeypatch.setattr(live, '_run_post_extract_pipeline', lambda **kwargs: calls.append(kwargs) or 0)
    live.score_from_raw_artifacts([str(path)], dry_run=False, model='test', quiet=True, refresh_queue=False)
    assert calls[0]['refresh_queue'] is False
    assert calls[0]['jobs'][0]['url_hash']
    assert calls[0]['jobs'][0]['source'] == 'jobspy_filtered_v1'


def test_spring_internship_is_not_hard_rejected_for_generic_no_sponsorship():
    from types import SimpleNamespace
    from discovery.auto.scorer import score_job
    replies = [
        'Decision: Reject\nCategory: N/A\nfit_score: 0\nRationale: No sponsorship excludes CPT.\nrole_type: PM',
        'Decision: Proceed\nCategory: High Priority\nfit_score: 8.2\nRationale: Product ownership; verify work authorization before applying.\nrole_type: PM',
    ]
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text=replies[len(calls)-1])])
    job = {'company': 'Example', 'role_title': 'Product Management Intern - Spring 2027',
           'lane': 'A', 'jd_text': 'Responsibilities: ' + JD * 5 + ' No visa sponsorship available.'}
    result = score_job(job, SimpleNamespace(messages=SimpleNamespace(create=create)), '', '', verbose=False)
    assert len(calls) == 2
    assert result['decision'] == 'Proceed'


def test_adjacent_program_titles_require_supporting_description_evidence():
    from shared.job_eligibility import classify_role_surface
    assert classify_role_surface('Technology Analyst Program', 'Work in product delivery and business operations.')[0] == 'keep'
    assert classify_role_surface('Technology Analyst Program', 'Provide IT support.')[0] != 'keep'
    assert classify_role_surface('Consumer Insights Co-op', 'Support product development through consumer research.')[0] == 'keep'
    assert classify_role_surface('Consumer Insights Co-op', 'Prepare market advertising reports.')[0] != 'keep'


def test_replay_reconsiders_old_machine_rejection():
    row = classify_discovery_job_offline({
        "role_title": "MBA Full-Time Hire - Product", "lane": "B",
        "jd_text": JD, "classification": "reject",
        "discovery_reason": "Old title matcher did not recognize this role",
    })
    assert row["classification"] == "keep"
    assert row["role_family"] == "Product"


def test_benefit_date_is_not_employment_start_but_real_start_is():
    title = "MBA Full-Time Hire - Product"
    benefits = JD + "\nStarting January 2027, the company matches 401(k) contributions."
    assert classify_start_timing(title, benefits) == "new_grad_eligible"
    assert classify_start_timing(title, JD + "\nThis position starts January 2027.") == "pre_graduation_full_time"


def test_comma_in_explicit_start_date_does_not_bypass_graduation_gate():
    assert classify_start_timing(
        "Market Operations Leadership Development Program - New Graduate",
        "New Graduate: JANUARY, 2027 START DATE\nA graduate leadership program.",
    ) == "pre_graduation_full_time"


def test_explicit_internship_after_company_preamble_is_still_an_internship():
    description = ("Company background. " * 100 +
                   "This is an MBA internship taking place in summer 2027. "
                   "Applicants must graduate in December 2027.")
    assert classify_start_timing(
        "2027 MBA Summer Associate - Strategy & Operations", description
    ) == "summer_2027_internship"


def test_description_expansion_does_not_toggle_back_to_collapsed():
    from discovery.auto.linkedin_live import _expand_job_description
    class Button:
        expanded = False
        clicks = 0
        def count(self): return 1
        def nth(self, index): return self
        def inner_text(self, **kwargs): return "Show less" if self.expanded else "Show more"
        def get_attribute(self, name):
            return ("true" if self.expanded else "false") if name == "aria-expanded" else ""
        def click(self, **kwargs):
            self.clicks += 1
            self.expanded = not self.expanded
    button = Button()
    class Page:
        def get_by_role(self, *args, **kwargs): return button
        def locator(self, *args, **kwargs): return button
        def wait_for_timeout(self, *args): pass
    _expand_job_description(Page())
    assert button.expanded
    assert button.clicks == 1


def test_identical_incomplete_description_is_not_reloaded_repeatedly(monkeypatch):
    from discovery.auto import linkedin_live as live
    preview = "Company background and business introduction. " * 28 + "Your responsibilities will evolve"
    class Page:
        url = "https://www.linkedin.com/jobs/view/123/"
        navigations = 0
        reads = 0
        def set_default_timeout(self, *args): pass
        def goto(self, *args, **kwargs): self.navigations += 1
        def wait_for_timeout(self, *args): pass
        def evaluate(self, *args):
            self.reads += 1
            return {"jdText": preview, "insightText": ""}
    page = Page()
    monkeypatch.setattr(live, "_wait_for_job_description", lambda *a, **k: None)
    monkeypatch.setattr(live, "_expand_job_description", lambda *a, **k: None)
    monkeypatch.setattr(live, "_company_from_job_detail_page", lambda *a, **k: "Example")
    result = live._open_job_details(page, page.url, detail_page=page)
    assert result[0] == ""
    assert page.navigations == 1
    assert page.reads == 2


def test_incomplete_preview_is_not_counted_as_usable_jd():
    preview = "Company background and business introduction. " * 28 + "Your responsibilities will evolve"
    assert not audit.usable_jd({"jd_text": preview})


def test_restart_reuses_full_descriptions_but_retries_previews(tmp_path, monkeypatch):
    from discovery.scripts import recover_discovery_coverage as recovery
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    logs = tmp_path / "discovery/auto/logs"
    logs.mkdir(parents=True)
    (logs / "linkedin_live_raw_hydrated_2026-11-04_100000.json").write_text(json.dumps({
        "cards": [
            {"url": "https://www.linkedin.com/jobs/view/123/", "jd_text": JD},
            {"url": "https://www.linkedin.com/jobs/view/456/", "jd_text":
             "Company background and business introduction. " * 28 + "Your responsibilities will evolve"},
        ]
    }))
    assert recovery.saved_jd_keys("2026-11-02") == {"li:123"}


def test_relevant_titles_get_jd_review_without_new_grad_title_words():
    for title in ("Product Manager", "Strategic Product Lead",
                  "Strategic Partner Manager", "Product Manager, Developer Tools"):
        assert classify_title(title, "Product Manager New Grad")[0], title
    assert not classify_title("Financial Analyst", "Business Operations New Grad")[0]


def test_distinct_employer_listings_do_not_collapse_by_title():
    common = {"company": "Employer", "role_title": "Associate Product Manager"}
    first = {**common, "url": "https://careers.example/jobs/one", "location": "Austin"}
    second = {**common, "url": "https://careers.example/jobs/two", "location": "Santa Clara"}
    assert linkedin_job_key(first) != linkedin_job_key(second)
    assert audit.listing_key(first) != audit.listing_key(second)
    assert audit.listing_key({"url": "https://www.linkedin.com/jobs/view/123/?ref=abc"}) == audit.listing_key({"url": "https://www.linkedin.com/jobs/view/123"})


def test_verified_national_city_ads_share_one_role_with_all_links_retained():
    text = (
        "This position is based on our campus in Madison, WI and requires relocation. "
        "We recruit nationally. " + JD
    )
    rows = [{"company": "Example", "title": "Solutions Engineer",
             "url": f"https://www.linkedin.com/jobs/view/{i}/",
             "location": location, "jd_text": text}
            for i, location in [(1, "Austin"), (2, "Seattle")]]
    groups = national_recruitment_templates(rows)
    assert len(groups) == 1
    group = next(iter(groups.values()))
    assert group["identical_description_count"] == 2
    assert len(group["verified_posting_urls"]) == 2
    rows.append({**rows[0], "url": "https://www.linkedin.com/jobs/view/3/",
                 "jd_text": text + "Different local work authorization requirements."})
    assert not national_recruitment_templates(rows)


def test_same_title_without_verified_national_relocation_is_not_grouped():
    rows = [{"company": "Example", "title": "Product Manager",
             "url": f"https://careers.example/jobs/{i}", "jd_text": JD}
            for i in (1, 2)]
    assert not national_recruitment_templates(rows)


def test_actual_deprioritization_is_completed_but_machine_gate_is_not():
    assert audit.completed_review({"decision": "Deprioritize", "fit_score": 4.2,
                                   "_raw_response": "Decision: Deprioritize\nBreakdown: ..."})
    assert not audit.completed_review({"decision": "Reject", "fit_score": 0,
                                       "_raw_response": "Pre-filter: obsolete rule"})


def test_linkedin_tracking_variants_match_existing_even_if_title_changed():
    from discovery.auto.linkedin_live import _split_existing_jobs
    rows = pd.DataFrame([{
        "id": "1", "company": "Example", "role_title": "Original Product Manager",
        "url": "https://www.linkedin.com/jobs/view/123/", "url_hash": "old-hash",
        "source": "linkedin_live_jobs_v1", "status": "generated", "fit_score": "9.2",
    }])
    pending, existing = _split_existing_jobs([{
        "company": "Example", "role_title": "Renamed Product Manager",
        "url": "https://www.linkedin.com/jobs/view/123?ref=search",
        "url_hash": "new-hash", "tc_hash": "different-title-hash",
    }], rows)
    assert not pending
    assert len(existing) == 1


def test_replay_keeps_distinct_requisitions_with_same_title():
    from discovery.auto.linkedin_live import _dedupe_jobs_for_replay
    rows = [{"url": f"https://careers.example/jobs/{i}", "tc_hash": "same-title"}
            for i in (1, 2)]
    assert len(_dedupe_jobs_for_replay(rows)) == 2


def test_provenance_fields_do_not_silently_discard_recovery_cards():
    from discovery.auto.linkedin_live import _cards_from_payload
    cards = _cards_from_payload({"cards": [{
        "role_title": "Associate Product Manager", "company": "Example",
        "url": "https://www.linkedin.com/jobs/view/123/",
        "classification": "unsure", "coverage_audit": "capture.json",
    }]})
    assert len(cards) == 1
    assert cards[0].title == "Associate Product Manager"


def test_weekly_linkedin_search_reaches_roles_daily_pack_omits():
    weekly = linkedin_search_terms("7d")
    for term in ("Rotational Product Manager 2027", "Solutions Architect Graduate 2027",
                 "Business Operations New Grad 2027"):
        assert term in weekly
    assert len(weekly) > len(linkedin_search_terms("24h"))


def test_partial_fetch_persists_query_health_in_its_exact_raw_artifact(tmp_path, monkeypatch):
    from discovery.scripts import fetch_jobspy_breadth as fetch
    monkeypatch.setattr(fetch, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(fetch, "parse_args", lambda: argparse.Namespace(
        hours_old=168, results=60, query_index=[43], quiet=True))
    def scrape(**kwargs):
        kwargs["run_report"].update({"status": "partial", "query_status_counts": {"timed_out": 1}})
        return []
    monkeypatch.setattr(fetch, "scrape", scrape)
    assert fetch.main() == 0  # Parent still processes successfully saved results.
    artifact = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert artifact["status"] == "partial"
    assert artifact["query_health"]["query_status_counts"] == {"timed_out": 1}


def test_interrupted_jobspy_fetch_publishes_completed_query_checkpoints(tmp_path, monkeypatch):
    from discovery.scripts import run_daily_engine as engine
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path / "logs")
    checkpoint_dir = tmp_path / "run-1"
    checkpoint_dir.mkdir()
    jobs = [{"company": "Example", "role_title": "Product Manager 2027",
             "url": "https://example.com/1", "url_hash": "one", "tc_hash": "example-pm",
             "jd_text": JD}]
    (checkpoint_dir / "query_13.json").write_text(json.dumps({
        "status": "completed", "query_index": 13, "jobs": jobs,
    }))
    (checkpoint_dir / "manifest.json").write_text(json.dumps({
        "schema": "resume_generator.discovery_query_checkpoint",
        "hours_old": 168, "requested_query_indices": [13, 14],
        "queries": [{"status": "completed", "query_index": 13,
                     "checkpoint_file": "query_13.json"}],
    }))
    path = engine._salvage_jobspy_checkpoint(
        checkpoint_dir, hours_old=168, results=60, query_indices=[13, 14],
        reason="timeout",
    )
    assert path and path.is_file()
    payload = json.loads(path.read_text())
    assert payload["count"] == 1
    assert payload["status"] == "partial"
    assert payload["query_health"]["completed_query_indices"] == [13]
    assert payload["query_health"]["remaining_query_indices"] == [14]


def test_weekly_parent_timeout_outlasts_scraper_cap():
    from discovery.scripts import run_daily_engine as engine
    from discovery.auto.scraper import DEFAULT_RUN_TIMEOUT_SECONDS
    args = argparse.Namespace(jobspy_fetch_timeout=0, window="7d")
    assert engine._effective_jobspy_fetch_timeout(args) > DEFAULT_RUN_TIMEOUT_SECONDS


def test_parent_reports_partial_run_instead_of_success(monkeypatch, tmp_path):
    from discovery.scripts import run_daily_engine as engine
    monkeypatch.setattr(engine, "parse_args", lambda: argparse.Namespace(run_id="coverage-test"))
    def run(args, manifest):
        manifest["stage_metrics"] = {"jobspy": {"status": "partial"}}
        return 0
    captured = {}
    monkeypatch.setattr(engine, "_run_daily_engine", run)
    def save(manifest):
        captured.update(manifest)
        return tmp_path / "manifest.json"
    monkeypatch.setattr(engine, "write_daily_engine_manifest", save)
    assert engine.main() == 2
    assert captured["status"] == "incomplete"


def test_ledger_merges_saved_jd_by_job_id_and_keeps_unfinished_cards(tmp_path, monkeypatch):
    import jobs
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "load_jobs", lambda: pd.DataFrame())
    monkeypatch.setattr(jobs, "_load_blocklist", lambda: [])
    logs = tmp_path / "discovery/auto/logs"
    logs.mkdir(parents=True)
    validation = tmp_path / "discovery/source_validation"
    validation.mkdir(parents=True)
    cards = [
        {"title": "Associate Product Manager", "company": "One", "url": "https://www.linkedin.com/jobs/view/123/"},
        {"title": "Product Manager", "company": "Two", "url": "https://www.linkedin.com/jobs/view/456/"},
    ]
    (logs / "linkedin_live_raw_2026-11-04_100000.json").write_text(json.dumps({"cards": cards}))
    (logs / "jobspy_breadth_raw_168h_2026-11-04_110000.json").write_text(json.dumps({
        "jobs": [{"role_title": "Associate Product Manager", "company": "One",
                  "url": "https://www.linkedin.com/jobs/view/123?ref=jobspy",
                  "jd_text": JD, "lane": "B"}]
    }))
    path = audit.build_audit("2026-11-02")
    payload = json.loads(path.read_text())
    assert payload["unique_captured_listings"] == 2
    assert payload["counts"] == {"needs_score": 1, "needs_jd": 1}
    assert payload["status"] == "incomplete"
    recovery = json.loads(Path(str(path.with_suffix("")) + "-score-input.json").read_text())
    assert len(recovery["jobs"]) == 1
    assert recovery["jobs"][0]["jd_text"] == JD
