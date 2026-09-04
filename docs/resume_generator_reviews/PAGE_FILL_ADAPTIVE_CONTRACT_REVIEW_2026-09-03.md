# Page-fill audit and adaptive assembly contract

## Live v2 release update

V2 now reads the produced DOCX's actual top/bottom margins and measures the
rendered PDF with `pdftotext -bbox-layout` before either artifact is published.
Observed usable fill below `0.93` blocks release; `0.93–0.95` is a near-floor
warning, `0.95–0.98` is clean, and above `0.98` is a dense-page warning while the
independent one-page gate remains authoritative. Legacy does not opt into this
policy and is unchanged.

The bounded recovery path is rerunning the same generator command with
`RESUME_V2_BULLET_BUDGET=11`. It changes the allocation decision to
`ADD_DISTINCT_SIGNAL` and opens exactly one profile-bounded company slot. Set
`RESUME_V2_ADD_COMPANY='INTUIT'` (or another eligible profile company) only when
the default extra slot is not the intended evidence owner. Exact reviewed-bank
membership and unique story-family validation still apply; no prose is expanded
and no filler is inserted.

## Verdict

The remainder of this document preserves the pre-wiring audit that motivated the
live update above. Fixed bullet counts cannot guarantee a full page. At audit
time, the live legacy generator used
**11 bullets as a structural invariant**, then estimates wrapping from character
counts, while the v2 profile layer permitted 9/10/11 proof units without a live
geometry release check.

The durable fix is not “always add an eleventh bullet.” It is a bounded,
quality-first render loop: select strong evidence first, render the complete page,
adjust approved layout spacing, and only then add an already-admitted,
non-duplicative proof unit. If none exists, accept honest white space rather than
backfill weak evidence.

## What the system does today

| Layer | Current behavior | Consequence |
|---|---|---|
| Legacy PM/NONPM selection | Exact 11-slot shapes (`3/3/3/2`) in `freeform_runner.py:1153-1172`; QC rejects any total other than 11 at `1237-1249`. Prompts repeat the invariant. | Count is fixed before summary, projects, skills, or rendered line cost are known. |
| V2 profile contract (audit snapshot) | Professional profiles target 10 and allow 9–11 (`shared/resume_profiles.py:188-233, 236-280, 634-698`). Project replacement permits 10–11 page-wide proof units (`701-785`). | At audit time this was a count contract without a live geometry gate; the release-floor update above now closes that detection gap. |
| Estimator | Uses `100` characters per line, fixed education constants, magic twip costs, and four tiers (`freeform_runner.py:1704-1719, 1790-1885`). | Proportional font widths, bold labels, tabs, justified text, Word wrapping, and paragraph geometry are approximated. Equal counts can differ by many lines. |
| Layout choice | Selects the first estimated tier that fits (`1840-1856`). T0 is the loosest available tier; there is no relaxed tier for a sparse page. | It can compress projected overflow, but cannot deliberately use excess space. |
| Underfill handling | Prints a warning below estimated 85% and suggests a fourth bullet in the “sparsest” company (`2049-2065`). The old AI expansion pass still exists at `1888-2014` but is no longer called after QC (`2612-2616`). | Warning is not repair. “Shortest block” says nothing about marginal evidence quality and can violate company ceilings. |
| Renderer | Summary, fixed education, every company header/title, optional Projects, and every Skills row all consume geometry (`resume_docx.js:225-319`). | A bullet total alone ignores large variable parts of the page. Five companies also cost more header space than four. |
| Release | LibreOffice render must be exactly one page and preserve canonical text (`shared/resume_artifacts.py:145-227`; `shared/resume_lint.py:1042-1132`). | Catastrophic overflow/content drift is blocked, but a sparse one-page PDF passes. |
| Lane C | Template mode clones fixed paragraph geometry; fallback mode uses fixed margins/spacing (`resume/lane_c_docx.py:84-176, 247-309`). No Lane C adapter is registered by default (`shared/generation_routing.py:8-10, 124-139`). | There is no live adaptive fill path; direct/manual renderer use can bypass the professional release loop. |

### Observed evidence

The submitted artifacts demonstrate the count/geometry disconnect. Using
`pdfinfo` plus `pdftotext -bbox-layout`, all were one page (792 pt high), but the
last visible text ended at materially different positions:

| Artifact | Shape | Last text `yMax` | Raw space below last text |
|---|---:|---:|---:|
| Amazon submitted gold | 10 Experience + inline Fluo/Community | 762.16 pt | 29.84 pt |
| StudyFetch v4 | 8 Experience + 3 Project + 5 Skills rows | 745.96 pt | 46.04 pt |
| Xpansiv | 10 Experience + inline Fluo/Community | 698.96 pt | 93.04 pt |
| Spectrum Reach | same visible marker count as Xpansiv | 698.26 pt | 93.74 pt |

Reproduction command:

```bash
pdfinfo RESUME.pdf | rg 'Pages|Page size'
pdftotext -bbox-layout RESUME.pdf - | rg -o 'yMax="[0-9.]+"' | tail -1
```

The Xpansiv and Amazon pages have the same 10-bullet Experience allocation, yet
their last text positions differ by about 63 pt, roughly five to six body lines.

## Proposed deterministic contract

### 1. Select content before optimizing geometry

Assembly receives one canonical `PageAssemblyPlan` containing:

- funded summary and identity heading;
- Experience allocation and selected admitted variants;
- Fluo placement and any Projects proof;
- required/optional Skills, Community, and Interests rows;
- an ordered list of **already-admitted distinct additions**;
- an ordered list of **unprotected lowest-marginal removals**.

The fill loop cannot write or expand prose. It may only choose a layout or request
one of those pre-approved content-plan alternatives before final QC and save.

Proof units are Experience/Projects bullets. Summary, headings, company rows,
Skills, Community, Interests, and inline Fluo are not interchangeable proof units,
but all count in observed geometry. They cannot be inserted or deleted merely to
fill space.

### 2. Budgets are bounded by profile, not globally fixed

- Professional default: 10; 9 for admission quality or page fit; 11 only for a
  distinct additional signal.
- More than 11 is legal only when a named profile explicitly raises its maximum;
  it is never a generic response to white space.
- Campus uses its own existing bounds (currently 8/9/10), not professional values.
- A page may ship below the preferred fill band when no strong addition exists.
  Admission quality always beats visual fullness.

### 3. Observe rendered geometry

For each isolated LibreOffice candidate, record:

- page count and semantic parity (existing hard gates);
- page height and configured top/bottom margins;
- final meaningful word `yMax` from Poppler bbox output;
- `usable_fill_ratio = (content_bottom - usable_top) / (usable_bottom - usable_top)`.

The four-artifact calibration supports a provisional **0.93–0.98** band: it marks
the visibly sparse Xpansiv/Spectrum pages low, keeps StudyFetch v4 in band, and
marks the zero-buffer Amazon Word render dense. Treat this as a shadow target,
not a new quality score or release blocker, until NONPM/campus fixtures expand the
sample. Frozen observations live in
`page_fill_observed_geometry_2026-09-03.json`.

### 4. Bounded decision order

1. Render the semantic base plan at the standard layout.
2. If it overflows or exceeds the upper band, try approved tighter layouts.
3. If it underfills, try approved looser layouts before changing content.
4. If still underfilled, add the next pre-approved proof only when it cleared
   admission, JD fit, non-duplication, and marginal-value comparison; rerender.
5. If overfull at the tightest acceptable layout, remove only the pre-ranked
   lowest-value unprotected proof, never below the profile minimum; rerender.
6. If no strong addition exists, release one page as
   `READY_UNDERFILLED_QUALITY_PROTECTED`. Never lengthen bullets or add generic
   Skills/Interests as padding.
7. If overflow has no bounded repair, block. Final QC, canonical TXT save, DOCX,
   and PDF release occur only after the chosen content/layout plan is stable.

The render search is bounded: one standard candidate, available layout neighbors,
and at most one addition/removal per profile delta. No free-form best-of-N loop.

## Code-level architecture

1. **Observed geometry:** `shared/resume_fill.py` exposes bbox-derived immutable
   PDF/page geometry using `pdftotext -bbox-layout`; page count/text parity remain
   independent blockers. The observer and calibrated floor are now live for v2;
   the adaptive layout/content planner remains isolated. Do not reuse the
   character estimator as truth.
2. **Renderer API:** make layout an explicit immutable input. Add one or two
   professionally reviewed relaxed tiers above current T0; retain T0–T3 as the
   compact direction. The renderer never edits content.
3. **Assembly candidates:** convert `ExperienceAllocationPlan`/`PageProofPlan` plus
   summary/Fluo/skills decisions into canonical alternatives. Selection owns which
   addition/removal is eligible.
4. **Fill planner:** `shared/resume_fill.py` now includes a pure adaptive assembly
   selector. It accepts the named profile budget/funded criteria, selected variant
   IDs with material ranks and line costs, observed geometry, sanctioned layouts,
   and pre-admitted unselected candidates. It returns an action, stable reason
   code, selected IDs before/after, layout/add/remove ID, and per-candidate rejection
   reasons. It remains isolated and is not imported by live code.
5. **Release audit:** persist selected profile, proof count, content-plan ID, layout
   tier, measured fill, every attempted candidate, and final reason.

## Required tests before wiring live

### Deterministic unit tests

Implemented in `tests/test_resume_fill.py` (12 tests): layout before addition;
approved additions only; weak-evidence underfill accepted; maximum respected;
tightening before removal; no removal below minimum; explicit 12-unit profiles;
invalid policies fail closed.

`tests/test_resume_fill_geometry.py` separately verifies bbox parsing, configured
usable-page math, invalid-input failure, and the four frozen artifact observations.

`tests/test_resume_adaptive_assembly.py` covers 9/10/11 additions, an explicitly
named 12-proof profile, layout-first behavior, candidate rejection reasons,
quality-protected underfill, in-band identity/no-regression behavior, protected
proof, tighter-layout-first overflow repair, and minimum-budget blocking.

### Render/geometry integration tests

- Same 10 bullets, short versus long variants: observed fill must differ.
- A long 9-unit page may be fuller than a short 11-unit page.
- Summary one/two/three lines; Fluo inline versus Projects; Skills with and without
  Community/Interests; four versus five employer blocks.
- Underfilled T0 tries relaxed layout; only then an admitted 11th proof.
- A rejected/duplicate/low-stakes candidate is never used to fill.
- Overflow tries T1–T3, then a pre-ranked removal; saved TXT/DOCX/PDF remain equal.
- Lane C template and fallback renders get their own geometry fixtures before a
  Lane C adapter can ship.

### Non-regression rollout

- **legacy:** no adaptive behavior; existing artifact remains incumbent.
- **shadow:** build and render v2 candidates, write audit only, never rename/release
  them over legacy.
- **v2:** may release only after the challenger has zero blockers, exact parity,
  one page, and wins/does not lose pairwise content comparison on the fixture
  corpus. Fill alone can never make a weaker challenger win.

Use Amazon and StudyFetch golds plus representative legacy product, NONPM, and
campus fixtures. A sparse legacy page is a comparison observation, not automatic
proof that v2 is better.

## Recommended implementation order

1. Add bbox geometry observation and tests.
2. Add reviewed relaxed layout tiers and candidate rendering in shadow only.
3. Feed profile-owned approved additions/removals into the isolated planner.
4. Run the fixture corpus; calibrate the preferred band.
5. Wire v2 release only after non-regression comparison passes.

Do **not** reactivate the AI expansion pass or change the live 11-bullet legacy
contract as part of this work. Those would mix content mutation with page repair
and make rollback/non-regression harder.
