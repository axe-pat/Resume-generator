import pytest

from shared.queue_preflight import (
    PreflightStatus,
    QueueInput,
    preflight_queue,
)


def _role_jd(*, domain: str = "product", extra: str = "") -> str:
    core = f"""
About the role

This role joins a cross-functional {domain} team that owns customer discovery,
prioritization, delivery, and measurement. You will interview customers, analyze
usage data, define requirements, build prototypes, and partner with engineering
and design to ship improvements. You will also establish success metrics, review
results with stakeholders, and adapt the roadmap when evidence contradicts the
initial plan.

What you'll do

Lead structured discovery, translate findings into clear decisions, coordinate
execution, and measure adoption after launch. Work with partners across product,
engineering, design, analytics, sales, and customer success. Document tradeoffs,
surface risks early, and communicate progress to senior leaders.

Qualifications

Strong analytical judgment, written communication, customer empathy, and the
ability to operate independently in ambiguous environments. Experience building
or launching a product, service, process, or technical system is preferred.
{extra}
"""
    # Keep the default fixture comfortably above the thin-JD thresholds so a
    # test aimed at another check is not accidentally testing length too.
    return (core + "\n" + core).strip()


NETIC_PATTERN_JD = (
    "The company is the AI revenue engine for essential services that are the backbone "
    "of the economy. With funding from leading investors, it has helped customers book "
    "hundreds of thousands of jobs across service categories through automation and "
    "software built for modern operators."
)


NUVO_PATTERN_JD = _role_jd(
    domain="go-to-market operations",
    extra="""
The role

This role is designed for a current full-time MBA student who wants to help a
fast-growing startup build a scalable internal operating system across Sales,
Marketing, and Customer Success. The internship will take place over the summer.
Candidates should be seeking summer internship experience between the first and
second year of their MBA program.
""",
)


MOMENTUM_PATTERN_JD = _role_jd(
    domain="business transformation",
    extra="""
The opportunity

We're creating our first-ever MBA Summer Internship. This is a substantive,
high-visibility role working with senior leadership on process redesign and
AI-enabled operating improvements. The intern will be based in Dallas for the
summer and work full-time on site.
""",
)


def _codes(report, key):
    return {record.code for record in report.records_for(key)}


def test_missing_jd_is_a_blocker():
    report = preflight_queue([QueueInput("missing", "Product Manager", "  ")])

    assert report.status is PreflightStatus.BLOCK
    assert _codes(report, "missing") == {"JD_MISSING"}
    assert report.passes == ()


def test_netic_pattern_company_intro_only_is_blocked_as_truncated():
    report = preflight_queue(
        [QueueInput("netic-pattern", "Forward Deployed Engineer - New Grad", NETIC_PATTERN_JD)]
    )

    assert "JD_TRUNCATED" in _codes(report, "netic-pattern")
    issue = report.records_for("netic-pattern")[0]
    assert issue.status is PreflightStatus.BLOCK
    assert issue.details["role_content_detected"] is False


def test_short_role_specific_summary_warns_instead_of_blocking():
    jd = (
        "About the role. This role supports reporting and student services. "
        "What you'll do: analyze weekly data, update dashboards, coordinate with "
        "campus partners, document requirements, and present findings. "
        "Qualifications: strong Excel skills, communication, and attention to detail. "
        "You will work independently and prioritize requests from several teams."
    )
    report = preflight_queue([QueueInput("thin", "Business Intelligence Assistant", jd)])

    assert report.status is PreflightStatus.WARN
    assert "JD_THIN" in _codes(report, "thin")
    assert "JD_TRUNCATED" not in _codes(report, "thin")


def test_nuvo_pattern_nonintern_title_with_summer_internship_jd_is_blocked():
    report = preflight_queue(
        [QueueInput("nuvo-pattern", "New Grad Forward Deployed Engineer", NUVO_PATTERN_JD)]
    )

    assert "TITLE_EMPLOYMENT_TYPE_MISMATCH" in _codes(report, "nuvo-pattern")
    assert report.status is PreflightStatus.BLOCK


def test_prior_internship_experience_does_not_create_false_mismatch():
    jd = _role_jd(
        extra=(
            "Prior internship experience is welcome but not required. This is a "
            "full-time graduate role beginning after degree completion."
        )
    )
    report = preflight_queue(
        [QueueInput("graduate-role", "Graduate Product Manager", jd)]
    )

    assert "TITLE_EMPLOYMENT_TYPE_MISMATCH" not in _codes(report, "graduate-role")
    assert report.status is PreflightStatus.PASS


def test_internship_language_in_late_scraped_page_noise_does_not_block():
    appended_feed = (
        "\n" * 3
        + "X" * 8200
        + "\nEmployee update: This internship was an excellent summer experience."
    )
    report = preflight_queue(
        [
            QueueInput(
                "scraped-page",
                "Client Service Manager",
                _role_jd(domain="client service management") + appended_feed,
            )
        ]
    )

    assert "TITLE_EMPLOYMENT_TYPE_MISMATCH" not in _codes(report, "scraped-page")
    assert report.status is PreflightStatus.PASS


def test_momentum_pattern_duplicate_body_under_different_titles_is_blocked():
    jobs = [
        QueueInput(
            "momentum-mba",
            "2027 MBA Full Time Associate - Strategy & Operations and Business Transformation",
            MOMENTUM_PATTERN_JD,
        ),
        QueueInput(
            "momentum-strategy",
            "2027 Launch Graduate Program: Associate Strategy & Operations Analyst",
            MOMENTUM_PATTERN_JD,
        ),
        QueueInput(
            "momentum-systems",
            "2027 Launch Graduate Program: Associate Enterprise Systems Analyst",
            MOMENTUM_PATTERN_JD,
        ),
    ]

    report = preflight_queue(jobs)

    duplicate_records = [
        record
        for record in report.blockers
        if record.code == "JD_DUPLICATE_DIFFERENT_TITLES"
    ]
    assert len(duplicate_records) == 1
    assert set(duplicate_records[0].job_keys) == {job.key for job in jobs}
    for job in jobs:
        assert "TITLE_EMPLOYMENT_TYPE_MISMATCH" in _codes(report, job.key)


def test_same_role_and_body_with_location_suffixes_is_not_a_duplicate_mismatch():
    jd = _role_jd(domain="operations leadership")
    jobs = [
        QueueInput(
            "dallas",
            "Operations Leadership Development Program | Dallas, TX",
            jd,
        ),
        QueueInput(
            "miramar",
            "Operations Leadership Development Program | Miramar, FL",
            jd,
        ),
    ]

    report = preflight_queue(jobs)

    assert "JD_DUPLICATE_DIFFERENT_TITLES" not in {
        record.code for record in report.records
    }
    assert report.status is PreflightStatus.PASS
    assert len(report.passes) == 2


def test_no_title_token_overlap_is_warning_not_blocker():
    report = preflight_queue(
        [
            QueueInput(
                "pairing-check",
                "Supplier Quality Analyst",
                _role_jd(domain="digital marketing and brand campaigns"),
            )
        ]
    )

    assert report.status is PreflightStatus.WARN
    assert _codes(report, "pairing-check") == {"TITLE_JD_LOW_OVERLAP"}


def test_metadata_constructor_and_json_ready_report_shape():
    queue_input = QueueInput.from_metadata(
        key="metadata-role",
        metadata={"company": "Example", "role_title": "Product Manager", "lane": "B"},
        jd_text=_role_jd(),
    )

    report = preflight_queue([queue_input])
    payload = report.as_dict()

    assert queue_input.role_title == "Product Manager"
    assert payload["status"] == "pass"
    assert payload["records"][0]["status"] == "pass"
    assert payload["records"][0]["job_keys"] == ["metadata-role"]


def test_duplicate_queue_keys_are_rejected():
    with pytest.raises(ValueError, match="must be unique"):
        preflight_queue(
            [
                QueueInput("same", "Product Manager", _role_jd()),
                QueueInput("same", "Operations Manager", _role_jd()),
            ]
        )
