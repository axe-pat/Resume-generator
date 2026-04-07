# Project Instructions for Claude

This file is read automatically at the start of every session. Follow these rules without being asked.

---

## Documentation maintenance

**Update the relevant README whenever you make a code change.**

This is not optional and does not require the user to ask. Any time you modify a file, check whether the change affects something documented and update the README before finishing.

Specifically:

- `README.md` (root) — update if you change: any command or flag, the pipeline flow, the status lifecycle, the xlsx schema, the scraper query list, the cost table, cron schedule, or any top-level behaviour.
- `discovery/README.md` — update if you change: scraper.py queries or results logic, scorer.py pre-filters or retry logic, pipeline.py flags or flow, score_screenshots.py behaviour, source taxonomy, log format, or any dedup logic.
- `resume/README.md` — update if you change: freeform_runner.py passes, the QC checks, the prompt files, or the known limitations section.
- `cover_letters/README.md` — update if you change: cl_pipeline.py steps, prompts, or QC behaviour.
- `apps/README.md` — update if you change: the directory layout, jobs.py promote/generate/mark behaviour, or run_app.py flags.

If you add a **new file or script**, create a README entry for it (or a new README if the directory lacks one).

If you rename, move, or delete a file, find and update every README that references the old path.

---

## Code change rules

- **Never change DEFAULT_MODEL** in scorer.py, freeform_runner.py, or cl_pipeline.py without confirming with the user. Model choices have significant cost implications.
- **Never bump RESULTS_WANTED or RETRY_ATTEMPTS** in scraper.py or scorer.py without confirming with the user.
- When adding a new scraper query to `QUERIES` in scraper.py, also update the query count in the scraper.py module docstring and in the README tables.
- When adding a new pre-filter pattern to `_ROLE_TYPE_REJECT_TITLE_PATTERNS` in scorer.py, add a test case in the pattern list comment and verify it with a quick `python -c` test before finishing.

---

## Key facts about this project

- **Run from project root**: all scripts expect to be run from `ResumeGenerator v1/`. Relative paths break if you cd into a subdirectory.
- **Mac terminal only for API calls**: `score_screenshots.py` and any script making Anthropic API calls must be run from the user's Mac terminal, not the Cowork VM. The VM has SSL certificate issues that break the API.
- **jobs.xlsx is the source of truth**: it lives at `discovery/jobs.xlsx`. There is also a root-level `jobs.xlsx` — that one is a backup/archive and should not be written to.
- **API key**: stored in `.env` at the project root (`ANTHROPIC_API_KEY=...`). Never commit or print this.
- **Default scoring model**: `claude-haiku-4-5-20251001` for discovery pipeline (cheap, fast). `claude-sonnet-4-6` for resume + CL generation (quality matters more).

---

## Current project state (update this when major milestones change)

Last updated: 2026-03-29

- Discovery pipeline: operational, running every 3h via cron
- jobs.xlsx: ~1,470+ rows, source taxonomy = linkedin / indeed / screenshot / seeded / manual; columns include date_posted (added 2026-03-21)
- 9 scraper query clusters (added ai_pm_intern 2026-03-21)
- Screenshot scoring: operational, run manually from Mac terminal
- Resume pipeline: operational (freeform variant system, Pass 0–4 + QC + docx; node_modules installed locally at resume/node_modules/)
  - Pass 4 (targeted fix loop): MAX_FIX_ATTEMPTS=1, PASS4_THRESHOLD=8.0
  - QC-13 auto-trim: only fires for bullets ≥260 chars (_AUTO_TRIM_CHARS); regular 3-liners (200-259 chars) are informational only
  - Expansion pass: fires when fill_pct < 85% before docx generation
  - Story bank: freeform_master_v2.txt, fully rewritten 2026-03-26 targeting 130-185 char 2-liners
  - Parse robustness: all 4 parse sites use 3-pattern cascade + trailing-reasoning truncation
  - Non-PM track: operational — `--track nonpm` uses freeform_master_nonpm.txt (Cluster A: Strategy/Consulting, Cluster B: Ops/Execution); QC-07 and docx header are track-aware; track auto-detected from role_family if --track not passed; test run pending (requires Mac terminal)
- CL pipeline: operational (Steps 0–3 + QC)
- jobs.py: built, not yet in cron (promote/generate loop not fully automated)
- Pending: TikTok-specific query, dedup between pipeline/screenshot sources, promote script automation, nonpm test run

## Resume pipeline pass flow (for reference)

Pass 0 → strategy (haiku via scorer.py, stored in strategy.json); emits role_family ("pm" | "strategy-consulting" | "ops-execution")
Pass 1 → variant selection + section generation (freeform_master_v2.txt [pm] or freeform_master_nonpm.txt [nonpm] → sonnet)
Pass 2 → voice rewrite (freeform_voice_rewrite.txt → sonnet)
Pass 3 → scoring (freeform_scorer.txt → sonnet, threshold 8.0; nonpm track prepends scorer preamble)
Pass 4 → targeted fix loop, 1 attempt max (freeform_targeted_swap.txt → sonnet)
QC     → structural checks QC-01 through QC-13; QC-03 retry if fails; QC-07 track-aware; QC-13 auto-trim if >2 bullets ≥260 chars
Expand → expansion pass if fill_pct < 85% (_estimate_page_fill)
Docx   → generate_docx (pandoc via Node.js); summary header track-aware (PRODUCT MANAGEMENT [pm] / PROFILE [nonpm])

## Known issues / technical notes

- All resume pipeline API calls use claude-sonnet-4-6 (DEFAULT_MODEL) including scoring
- score_only_app() in run_app.py runs score+pass4+QC-13+expansion on existing .txt files
- QC-03 auto-retry only on intuit_incident protected story (1,500+ businesses)
- The "rather than" contrast phrase cap is 1 per section (QC-12); story bank variants avoid it
- H-GENAI bullets will often score 7 (WEAK_MECHANISM/VAGUE_OUTCOME) — no concrete metric exists; Pass 4 cannot fix this
- Nonpm summary pool: Fixed 2026-03-29 to add CRITICAL VERBATIM enforcement (model was generating custom summaries instead of picking pool variant); also fixed O1 cluster-a variants to replace "supported" (forbidden opener) with "analyzed" + mechanism
