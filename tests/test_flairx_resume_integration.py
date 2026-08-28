import re
from pathlib import Path

from resume.freeform import freeform_runner as runner


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "resume" / "freeform" / "prompts" / "freeform_master_v2.txt"
SCORER = ROOT / "resume" / "freeform" / "prompts" / "freeform_scorer.txt"


def _experience(headers, slots):
    lines = []
    for header in headers:
        key = next(key for key in slots if header.startswith(key))
        lines.append(header)
        lines.extend(f"• Built distinct product artifact {i}." for i in range(slots[key]))
        lines.append("")
    return "\n".join(lines).strip()


def test_flairx_pool_has_five_stories_with_five_clean_variants_each():
    prompt = PROMPT.read_text(encoding="utf-8")
    pool = prompt.split("STORY POOL — FLAIRX AI", 1)[1].split(
        "STORY POOL — GOJEK", 1
    )[0]
    story_ids = ["F-ENTERPRISE", "F-AVATAR", "F-OPS", "F-CEIPAL", "F-SOURCING"]

    starts = [pool.index(f"STORY {story_id}:") for story_id in story_ids]
    starts.append(len(pool))
    forbidden = {
        "leveraged", "utilized", "spearheaded", "synergies", "actionable",
        "successfully", "effectively", "streamlined", "holistic", "various", "multiple",
    }

    for index, story_id in enumerate(story_ids):
        story = pool[starts[index]:starts[index + 1]]
        variants = re.findall(r'^"(.+)"$', story, re.MULTILINE)
        assert len(variants) == 5, story_id
        for bullet in variants:
            assert 90 <= len(bullet) <= 199, (story_id, len(bullet), bullet)
            assert "—" not in bullet
            assert "(" not in bullet and ")" not in bullet
            assert len(re.findall(r"\band\b", bullet, re.I)) <= 1
            assert not forbidden.intersection(re.findall(r"[A-Za-z]+", bullet.lower()))


def test_pm_and_nonpm_company_contracts_remain_independent():
    runner._configure_track_contract("pm")
    pm_exp = _experience(runner.PM_COMPANY_HEADERS, runner.PM_COMPANY_SLOTS)
    assert runner.validate_experience_structure(pm_exp)[0]
    assert "FLAIRX AI" in runner.count_bullets_per_company(pm_exp)
    assert "OPTUM" not in runner.count_bullets_per_company(pm_exp)

    runner._configure_track_contract("nonpm")
    nonpm_exp = _experience(runner.NONPM_COMPANY_HEADERS, runner.NONPM_COMPANY_SLOTS)
    assert runner.validate_experience_structure(nonpm_exp)[0]
    assert "OPTUM" in runner.count_bullets_per_company(nonpm_exp)
    assert "FLAIRX AI" not in runner.count_bullets_per_company(nonpm_exp)

    runner._configure_track_contract("pm")


def test_pm_section_extraction_starts_at_flairx():
    runner._configure_track_contract("pm")
    experience = _experience(runner.PM_COMPANY_HEADERS, runner.PM_COMPANY_SLOTS)
    raw = f"SECTION 3 — FULL EXPERIENCE SECTION\n{experience}\nSECTION 4\n"
    extracted = runner.extract_sections(raw)["experience_section"]
    assert extracted.startswith("FLAIRX AI |")
    assert extracted.count("• ") == 11


def test_scorer_schema_is_track_agnostic():
    scorer = SCORER.read_text(encoding="utf-8")
    assert "Return exactly one JSON object per bullet" in scorer
    assert '"company": "GOJEK"' not in scorer
    assert '"company": "OPTUM"' not in scorer


def test_pm_prompt_requires_one_truth_bounded_fluo_venture_row():
    prompt = PROMPT.read_text(encoding="utf-8")
    pool = prompt.split("VENTURE PRODUCT POOL — FLUO", 1)[1].split(
        "PROFESSIONAL SUMMARY POOL", 1
    )[0]
    variants = re.findall(r'^\[fluo-[^]]+\]\n"(.+)"$', pool, re.MULTILINE)
    assert len(variants) == 4
    assert "● Venture Product: Fluo —" in prompt
    assert "USC partnership is confirmed" in pool
    assert "Never upgrade" in pool


def test_pm_qc_requires_compact_fluo_venture_row_and_rejects_outcome_inflation():
    runner._configure_track_contract("pm")
    experience = _experience(runner.PM_COMPANY_HEADERS, runner.PM_COMPANY_SLOTS)
    sections = {
        "experience_section": experience,
        "skills_section": (
            "SKILLS & INTERESTS\n"
            "● Product Focus: Platform Strategy\n"
            "● Tools: SQL, Python\n"
            "● Venture Product: Fluo — Secured a USC partnership after concluding Fluo could not win students post-arrival, when they trust peers over an app; reset the roadmap around pre-arrival acquisition and long-term retention.\n"
            "● Community: Volunteer\n"
            "● Interests: Fitness"
        ),
        "projects_section": "",
    }
    checks = runner.run_quality_checks(sections, track="pm")
    qc14 = next(check for check in checks if check["name"].startswith("QC-14"))
    assert qc14["status"] == "PASS"

    sections["skills_section"] = sections["skills_section"].replace(
        "Secured a USC partnership after concluding Fluo could not win students post-arrival, when they trust peers over an app; reset the roadmap around pre-arrival acquisition and long-term retention.",
        "Validated adoption and generated $1M revenue.",
    )
    checks = runner.run_quality_checks(sections, track="pm")
    qc14 = next(check for check in checks if check["name"].startswith("QC-14"))
    assert qc14["status"] == "FAIL"


def test_pm_prompt_uses_recent_flairx_title_instead_of_summary_block():
    prompt = PROMPT.read_text(encoding="utf-8")
    output_contract = prompt.split("OUTPUT FORMAT — produce exactly five sections", 1)[1]
    assert "SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)\n\nNONE" in output_contract
    assert runner._sanitize_summary_section("NONE") == ""


def test_pm_flairx_location_and_team_framing_are_current():
    prompt = PROMPT.read_text(encoding="utf-8")
    assert "FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA" in prompt
    assert "4 engineers and 2 designers" not in prompt
    assert "4-engineer and 2-designer" not in prompt
