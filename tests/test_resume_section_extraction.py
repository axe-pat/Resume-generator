from resume.freeform import freeform_runner as runner
from run_app import _extract_saved_resume_sections


def test_final_summary_section_wins_over_provisional_reasoning_block():
    raw = """\
SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)
Selection reasoning that must never render in the resume.

SECTION 1 — TOP 3 JD SIGNALS
Customer integration

SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)
NONE

---

SECTION 3 — FULL EXPERIENCE SECTION
FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA
• Shipped a customer-facing product.

SECTION 4 — SKILLS
SKILLS
● Tools: SQL
"""

    sections = runner.extract_sections(raw)

    assert sections["summary_section"] == ""
    assert "Selection reasoning" not in sections["summary_section"]


def test_final_skills_block_excludes_saved_qc_and_duplicate_sections():
    raw = """\
SECTION 4 — SKILLS & INTERESTS
SKILLS & INTERESTS
● Tools: SQL, Python
● Interests: Hiking

QUALITY CHECKS
[PASS] Skills present

SECTION 0 — PROFESSIONAL SUMMARY
NONE

SECTION 4 — SKILLS & INTERESTS
SKILLS & INTERESTS
● Tools: SQL, Python, AWS
● Community: Mobile-school volunteer
"""

    sections = runner.extract_sections(raw)

    assert sections["skills_section"] == (
        "SKILLS & INTERESTS\n"
        "● Tools: SQL, Python, AWS\n"
        "● Community: Mobile-school volunteer"
    )
    assert "QUALITY CHECKS" not in sections["skills_section"]


def test_docx_only_uses_final_paste_ready_blocks_from_saved_transcript():
    raw = """\
SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)
------------------------------------------------------------------------
Provisional reasoning that must not render.

SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)
------------------------------------------------------------------------
FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA
• Provisional bullet.

SECTION 4 — SKILLS & INTERESTS (paste-ready)
------------------------------------------------------------------------
SKILLS & INTERESTS
● Tools: SQL

QUALITY CHECKS
Internal report

SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)

NONE

---

SECTION 3 — FULL EXPERIENCE SECTION (paste-ready, no markdown bold)

FLAIRX AI | AI Product Manager Intern | Jun 2026 – Aug 2026 | San Francisco, CA
• Final bullet.

---

SECTION 4 — SKILLS & INTERESTS (paste-ready)

SKILLS & INTERESTS
● Tools: SQL, Python
"""

    sections = _extract_saved_resume_sections(raw)

    assert sections["summary_section"] == "NONE"
    assert "Final bullet" in sections["experience_section"]
    assert "Provisional bullet" not in sections["experience_section"]
    assert sections["skills_section"] == "SKILLS & INTERESTS\n● Tools: SQL, Python"
