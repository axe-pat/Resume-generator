# TODO — ResumeGenerator v1

Last updated: 2026-03-26

---

## Pending runs

### Re-run (failed from prior sessions)
- [ ] StockX
- [ ] Walt Disney
- [ ] Nasdaq
- [ ] Novartis

### Batch score-only (March 24 dirs — existing .txt files, no full re-run needed)
- [ ] FlairX
- [ ] Galaxy
- [ ] Lincoln Electric
- [ ] MeeBoss
- [ ] Modisoft

---

## Pipeline / code

- [ ] **PM summary signal extraction review** — revisit Step 0 / summary-safe signal compression if PM summary qualifiers consistently miss important signals like cross-functional execution in generalist PM JDs
- [ ] **Consumer / market-research JD anti-monotony review** — Lasko-style PM runs can still feel over-diagnostic even when the score recovers; revisit action-vs-diagnostic balance and opener diversity for category-analysis / market-intelligence JDs when we do the deeper resume-tone pass
- [ ] **Dedup between pipeline/screenshot sources** — jobs added via screenshot scoring can duplicate pipeline-sourced rows; need a dedup pass keyed on (company, role_title) or URL
- [ ] **TikTok-specific scraper query** — add a query cluster targeting TikTok PM/APM roles in `scraper.py` QUERIES; update query count in docstring + discovery/README
- [ ] **Docx section gap formatting** — improve spacing between resume sections in the generated .docx output
- [ ] **`jobs.py` promote/generate loop** — automation of the promote → generate → mark-applied flow is built but not yet in cron

---

## Nice-to-have / longer term

- [ ] Score-only mode docs — document `score_only_app()` in `apps/README.md`
- [ ] Source taxonomy cleanup — "seeded" vs "manual" distinction is fuzzy; consider merging
