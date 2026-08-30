from dataclasses import replace

from shared.resume_lint import (
    ASSEMBLY_POLICY,
    RELEASE_POLICY,
    ArchetypeContract,
    AssembledResume,
    ExperienceBlock,
    ExperienceBullet,
    LintSeverity,
    SkillRow,
    issue_codes,
    lint_assembled_resume,
)
from shared.resume_profiles import (
    BulletBudgetDecision,
    ExperienceAllocationPlan,
)


def _bullet(text: str, archetype: str) -> ExperienceBullet:
    return ExperienceBullet(text=text, archetype=archetype)


def _rendered_text(document: AssembledResume) -> str:
    lines = [document.identity_heading, document.summary_text, "EXPERIENCE"]
    for block in document.experience_blocks:
        lines.append(f"{block.company} | {block.title} | {block.date_text}")
        lines.extend(f"• {bullet.text}" for bullet in block.bullets)
    lines.append(document.skills_heading)
    lines.extend(f"{row.label}: {row.text}" for row in document.skill_rows)
    return "\n".join(lines)


def _good_resume() -> AssembledResume:
    summary = (
        "Product manager and engineer who turns customer constraints into technical "
        "roadmaps, operating mechanisms, and measurable business outcomes."
    )
    blocks = (
        ExperienceBlock(
            "FLAIRX AI",
            "AI Product Manager Intern",
            "Jun 2026 – Aug 2026",
            (
                _bullet(
                    "Built an enterprise interview workflow that secured $1.2M in qualified pilots.",
                    "action",
                ),
                _bullet(
                    "Negotiated multi-provider avatar routing after vendor limits threatened long-form interviews, reducing cost per minute 70%.",
                    "context",
                ),
            ),
        ),
        ExperienceBlock(
            "GOJEK",
            "Product Owner, Marketplace Platforms",
            "Jan 2025 – Jul 2025",
            (
                _bullet(
                    "Diagnosed willingness-to-pay through 20+ customer interviews and translated the finding into a tiered marketplace offer.",
                    "diagnostic",
                ),
                _bullet(
                    "Generated $3.2M in incremental revenue and a 9% conversion lift through a pricing launch.",
                    "impact-first",
                ),
                _bullet(
                    "Cut fare-quote latency by pre-caching high-demand corridors, enabling 28K+ additional monthly rides.",
                    "action",
                ),
            ),
        ),
        ExperienceBlock(
            "HEVO DATA",
            "Product Owner, Enterprise Data Platform",
            "Nov 2023 – Jan 2025",
            (
                _bullet(
                    "Shifted the platform roadmap from streaming speed to verifiable correctness, enabling onboarding of 8 enterprise customers.",
                    "diagnostic",
                ),
                _bullet(
                    "Established a shared release mechanism across engineering teams, cutting release cycles from 14 to 4 days.",
                    "action",
                ),
            ),
        ),
        ExperienceBlock(
            "INTUIT",
            "Software Engineer 2",
            "Aug 2022 – Oct 2023",
            (
                _bullet(
                    "Restored accurate billing for 80K+ businesses through a cross-system reconciliation framework.",
                    "impact-first",
                ),
                _bullet(
                    "Caught a billing failure affecting 1,500+ businesses and coordinated parallel remediation across functions.",
                    "diagnostic",
                ),
            ),
        ),
        ExperienceBlock(
            "OPTUM",
            "Software Engineer",
            "Jul 2020 – Aug 2022",
            (
                _bullet(
                    "Designed a claims workflow that reduced manual review time 12% for operations teams.",
                    "context",
                ),
            ),
        ),
    )
    skill_rows = (
        SkillRow("Product Leadership", "Roadmaps, discovery, experimentation"),
        SkillRow("Data & Analytics", "SQL, Python, Tableau"),
        SkillRow("Technical", "APIs, AWS, Docker"),
        SkillRow("AI & Automation", "LLM workflows, evaluation"),
        SkillRow("Startup Product", "Fluo international-student planning product"),
    )
    allocation = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 3),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
    )
    raw = f"""SECTION 0 — PROFESSIONAL SUMMARY
{summary}
SECTION 1 — JD SIGNALS
customer judgment
SECTION 2 — SELECTION NOTES
approved variants only
SECTION 3 — EXPERIENCE
paste-ready content
SECTION 4 — SKILLS
paste-ready skills
"""
    document = AssembledResume(
        profile_id="product-general",
        identity_heading="PRODUCT MANAGEMENT",
        summary_text=summary,
        experience_blocks=blocks,
        skills_heading="SKILLS",
        skill_rows=skill_rows,
        allocation_plan=allocation,
        archetype_contract=ArchetypeContract(
            minimum_counts=(("diagnostic", 3), ("impact-first", 2), ("context", 2)),
            maximum_counts=(("diagnostic", 5),),
            minimum_action_plus_impact=5,
        ),
        raw_model_output=raw,
        fluo_included=True,
        fluo_story_family="product-system",
        rendered_page_count=1,
    )
    return replace(document, rendered_text=_rendered_text(document))


def _replace_block(
    document: AssembledResume,
    company: str,
    bullets: tuple[ExperienceBullet, ...],
) -> AssembledResume:
    blocks = tuple(
        replace(block, bullets=bullets) if block.company == company else block
        for block in document.experience_blocks
    )
    return replace(document, experience_blocks=blocks)


def test_known_good_release_contract_has_no_blockers():
    report = lint_assembled_resume(_good_resume(), RELEASE_POLICY)
    assert report.release_ready
    assert report.blockers == ()


def test_pre_render_success_is_not_mislabeled_release_ready():
    report = lint_assembled_resume(_good_resume(), ASSEMBLY_POLICY)
    assert report.passed
    assert not report.release_ready


def test_duplicate_section_zero_and_reasoning_leak_are_blockers():
    document = _good_resume()
    bad_raw = document.raw_model_output.replace(
        "SECTION 0 — PROFESSIONAL SUMMARY\n",
        "SECTION 0 — PROFESSIONAL SUMMARY\n"
        "Variant selection: wait, re-read the rules.\n"
        "SECTION 0 — PROFESSIONAL SUMMARY\n",
    )
    report = lint_assembled_resume(replace(document, raw_model_output=bad_raw), RELEASE_POLICY)
    codes = issue_codes(report, LintSeverity.BLOCKER)
    assert "MODEL_SECTION_DUPLICATED" in codes


def test_single_overlong_reasoning_block_cannot_pose_as_summary():
    document = _good_resume()
    bad_raw = document.raw_model_output.replace(
        document.summary_text,
        "Variant selection: selected because the action-first tally needs another story. "
        "Story ordering then follows the monotony check.",
    )
    report = lint_assembled_resume(replace(document, raw_model_output=bad_raw), RELEASE_POLICY)
    assert "SUMMARY_ANALYSIS_LEAK" in issue_codes(report, LintSeverity.BLOCKER)


def test_allocation_plan_is_compared_with_the_assembled_company_counts():
    document = _good_resume()
    gojek = next(block for block in document.experience_blocks if block.company == "GOJEK")
    document = _replace_block(document, "GOJEK", gojek.bullets[:2])
    report = lint_assembled_resume(document, RELEASE_POLICY)
    codes = issue_codes(report, LintSeverity.BLOCKER)
    assert "COMPANY_BULLET_COUNT_MISMATCH" in codes
    assert "TOTAL_BULLET_COUNT_MISMATCH" in codes


def test_quality_compact_nine_bullet_plan_does_not_backfill_a_tenth():
    document = _good_resume()
    gojek = next(block for block in document.experience_blocks if block.company == "GOJEK")
    document = _replace_block(document, "GOJEK", gojek.bullets[:2])
    plan = ExperienceAllocationPlan(
        profile_id="product-general",
        company_counts=(
            ("FLAIRX AI", 2),
            ("GOJEK", 2),
            ("HEVO DATA", 2),
            ("INTUIT", 2),
            ("OPTUM", 1),
        ),
        budget_decision=BulletBudgetDecision.COMPACT_FOR_QUALITY,
    )
    document = replace(document, allocation_plan=plan, rendered_text=_rendered_text(document))
    report = lint_assembled_resume(document, RELEASE_POLICY)
    assert "COMPANY_BULLET_COUNT_MISMATCH" not in issue_codes(report)
    assert "TOTAL_BULLET_COUNT_MISMATCH" not in issue_codes(report)


def test_summary_metric_reuse_is_surfaced_without_rejecting_a_deliberate_flagship():
    document = _good_resume()
    summary = "Product manager who converted customer evidence into $1.2M in qualified pilots."
    document = replace(
        document,
        summary_text=summary,
        raw_model_output=document.raw_model_output.replace(document.summary_text, summary),
    )
    document = replace(document, rendered_text=_rendered_text(document))
    report = lint_assembled_resume(document, RELEASE_POLICY)
    assert "SUMMARY_FIGURE_REUSED" in issue_codes(
        report, LintSeverity.WARNING
    )
    assert "SUMMARY_FIGURE_REUSED" not in issue_codes(report, LintSeverity.BLOCKER)


def test_same_company_figure_repetition_blocks_but_cross_company_repetition_warns():
    document = _good_resume()
    flairx = next(block for block in document.experience_blocks if block.company == "FLAIRX AI")
    same_company = _replace_block(
        document,
        "FLAIRX AI",
        (
            flairx.bullets[0],
            replace(flairx.bullets[1], text=flairx.bullets[1].text + " Protected $1.2M in pilots."),
        ),
    )
    same_report = lint_assembled_resume(same_company, RELEASE_POLICY)
    assert "FIGURE_REPEATED_IN_COMPANY" in issue_codes(
        same_report, LintSeverity.BLOCKER
    )

    optum = next(block for block in document.experience_blocks if block.company == "OPTUM")
    cross_company = _replace_block(
        document,
        "OPTUM",
        (replace(optum.bullets[0], text=optum.bullets[0].text + " The program secured $1.2M."),),
    )
    cross_report = lint_assembled_resume(cross_company, RELEASE_POLICY)
    assert "FIGURE_REPEATED_ACROSS_COMPANIES" in issue_codes(
        cross_report, LintSeverity.WARNING
    )
    assert "FIGURE_REPEATED_ACROSS_COMPANIES" not in issue_codes(
        cross_report, LintSeverity.BLOCKER
    )


def test_opening_verb_repetition_is_not_hidden_by_a_mean_score():
    document = _good_resume()
    flairx = next(block for block in document.experience_blocks if block.company == "FLAIRX AI")
    document = _replace_block(
        document,
        "FLAIRX AI",
        (
            flairx.bullets[0],
            replace(flairx.bullets[1], text="Built multi-provider routing for long-form interviews."),
        ),
    )
    report = lint_assembled_resume(document, RELEASE_POLICY)
    assert "OPENING_VERB_REPEATED_IN_COMPANY" in issue_codes(
        report, LintSeverity.BLOCKER
    )


def test_repeated_content_phrase_is_a_warning_not_an_automatic_rejection():
    document = _good_resume()
    flairx = next(block for block in document.experience_blocks if block.company == "FLAIRX AI")
    optum = next(block for block in document.experience_blocks if block.company == "OPTUM")
    document = _replace_block(
        document,
        "FLAIRX AI",
        (replace(flairx.bullets[0], text=flairx.bullets[0].text + " Built an enterprise operating system."), flairx.bullets[1]),
    )
    document = _replace_block(
        document,
        "OPTUM",
        (replace(optum.bullets[0], text=optum.bullets[0].text + " Extended the enterprise operating system."),),
    )
    report = lint_assembled_resume(document, RELEASE_POLICY)
    assert "PHRASE_REPEATED" in issue_codes(report, LintSeverity.WARNING)


def test_archetype_metadata_and_route_owned_bounds_are_hard_contracts():
    document = _good_resume()
    gojek = next(block for block in document.experience_blocks if block.company == "GOJEK")
    document = _replace_block(
        document,
        "GOJEK",
        tuple(replace(bullet, archetype="diagnostic") for bullet in gojek.bullets),
    )
    hevo = next(block for block in document.experience_blocks if block.company == "HEVO DATA")
    document = _replace_block(
        document,
        "HEVO DATA",
        tuple(replace(bullet, archetype="diagnostic") for bullet in hevo.bullets),
    )
    report = lint_assembled_resume(document, RELEASE_POLICY)
    codes = issue_codes(report, LintSeverity.BLOCKER)
    assert "DIAGNOSTIC_STREAK_EXCEEDED" in codes
    assert "ARCHETYPE_CEILING_EXCEEDED" in codes

    missing = _good_resume()
    flairx = next(block for block in missing.experience_blocks if block.company == "FLAIRX AI")
    missing = _replace_block(
        missing,
        "FLAIRX AI",
        (replace(flairx.bullets[0], archetype=None), flairx.bullets[1]),
    )
    missing_report = lint_assembled_resume(missing, RELEASE_POLICY)
    assert "ARCHETYPE_METADATA_MISSING" in issue_codes(
        missing_report, LintSeverity.BLOCKER
    )


def test_fluo_is_fixed_outside_experience_with_profile_gated_story_family():
    document = _good_resume()
    missing = replace(document, fluo_included=False)
    assert "FLUO_REQUIRED_MISSING" in issue_codes(
        lint_assembled_resume(missing, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    wrong_family = replace(document, fluo_story_family="unapproved-frame")
    assert "FLUO_STORY_FAMILY_INVALID" in issue_codes(
        lint_assembled_resume(wrong_family, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    fluo_block = ExperienceBlock(
        "FLUO",
        "Chief of Staff",
        "Aug 2026 – Present",
        (_bullet("Built a founder operating cadence.", "action"),),
    )
    in_experience = replace(
        document,
        experience_blocks=(fluo_block,) + document.experience_blocks,
    )
    assert "FLUO_IN_EXPERIENCE" in issue_codes(
        lint_assembled_resume(in_experience, RELEASE_POLICY), LintSeverity.BLOCKER
    )


def test_skills_heading_reflects_an_explicit_interests_row_only():
    document = _good_resume()
    wrong = replace(document, skills_heading="SKILLS & INTERESTS")
    assert "SKILLS_HEADING_INACCURATE" in issue_codes(
        lint_assembled_resume(wrong, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    with_interests = replace(
        document,
        skills_heading="SKILLS & INTERESTS",
        skill_rows=document.skill_rows + (SkillRow("Interests", "DJing and trekking"),),
    )
    with_interests = replace(with_interests, rendered_text=_rendered_text(with_interests))
    assert "SKILLS_HEADING_INACCURATE" not in issue_codes(
        lint_assembled_resume(with_interests, RELEASE_POLICY)
    )


def test_release_requires_observed_one_page_pdf_and_rendered_text_parity():
    document = _good_resume()
    missing = replace(document, rendered_page_count=None, rendered_text="")
    missing_codes = issue_codes(lint_assembled_resume(missing, RELEASE_POLICY), LintSeverity.BLOCKER)
    assert "PAGE_COUNT_UNVERIFIED" in missing_codes
    assert "RENDERED_TEXT_UNVERIFIED" in missing_codes

    two_pages = replace(document, rendered_page_count=2)
    assert "PAGE_COUNT_INVALID" in issue_codes(
        lint_assembled_resume(two_pages, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    changed_render = replace(document, rendered_text=document.rendered_text.replace("$3.2M", "$3.1M"))
    assert "RENDERED_TEXT_MISMATCH" in issue_codes(
        lint_assembled_resume(changed_render, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    extra_render = replace(
        document,
        rendered_text=document.rendered_text.replace(
            "\nSKILLS\n",
            "\n• Stale extra experience bullet.\nSKILLS\n",
        ),
    )
    assert "RENDERED_BULLET_COUNT_MISMATCH" in issue_codes(
        lint_assembled_resume(extra_render, RELEASE_POLICY), LintSeverity.BLOCKER
    )

    wingdings_render = replace(
        document,
        rendered_text=document.rendered_text.replace("•", "\uf0b7"),
    )
    assert "RENDERED_BULLET_COUNT_MISMATCH" not in issue_codes(
        lint_assembled_resume(wingdings_render, RELEASE_POLICY), LintSeverity.BLOCKER
    )


def test_contextual_density_date_and_scale_signals_warn_instead_of_false_blocking():
    document = _good_resume()
    flairx = next(block for block in document.experience_blocks if block.company == "FLAIRX AI")
    long_text = "Built " + "a technically defensible customer workflow " * 8
    document = _replace_block(
        document,
        "FLAIRX AI",
        (
            replace(flairx.bullets[0], text=long_text.strip()),
            flairx.bullets[1],
        ),
    )
    optum = next(block for block in document.experience_blocks if block.company == "OPTUM")
    blocks = tuple(
        replace(block, date_text="July 2020 - Aug 2022") if block.company == "OPTUM" else block
        for block in document.experience_blocks
    )
    document = replace(document, experience_blocks=blocks)
    document = _replace_block(
        document,
        "OPTUM",
        (replace(optum.bullets[0], text="Designed a claims workflow that protected $20K"),),
    )
    report = lint_assembled_resume(document, RELEASE_POLICY)
    warning_codes = issue_codes(report, LintSeverity.WARNING)
    assert "BULLET_DENSITY_HIGH" in warning_codes
    assert "DATE_FORMAT_INCONSISTENT" in warning_codes
    assert "BULLET_PUNCTUATION_INCONSISTENT" in warning_codes
    assert "CURRENCY_SCALE_INCOHERENT" in warning_codes
