# Career Workbench

This is the human-facing layer for interview prep, story mining, and reusable positioning notes.

It belongs inside ResumeGenerator because the same material feeds:

- interview answers and TMAY drafts
- cover letter angles
- resume story selection
- company-specific positioning
- future versions of `profile/profile.md` and the resume/cover-letter story bank

## Where Things Live

```
docs/career_workbench/
├── README.md
├── interview_prep/
│   ├── README.md
│   ├── prep_template.md
│   └── private/
│       ├── active/
│       │   └── 2026-05-29_FlairX_Product_Manager_Intern_AI_Products/
│       └── archive/
│           └── 2026-04_Hypertherm_Momentum/
├── profile_sources/
│   └── README.md
└── story_sources/
    └── README.md
```

## Operating Rule

Use `interview_prep/private/active/<date>_<company>_<role>/` for today's prep.

After the interview cycle is done, move the folder to `interview_prep/private/archive/`. If a story, line, or angle is reusable, copy the distilled version into one of the durable sources:

- `cover_letters/story_bank/` for cover-letter narrative material
- `resume/freeform/prompts/freeform_master_v2.txt` or `freeform_master_nonpm.txt` for resume bullets
- `profile/profile.md` for stable background facts and preferences
- `docs/career_workbench/story_sources/README.md` for human-readable story inventory

Keep raw personal prep private; keep durable distilled material tracked.
