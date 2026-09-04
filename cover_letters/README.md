# Cover Letter Layer

Generates tailored, paste-ready cover letters. Uses a 3-step pipeline: JD analysis → generation → AI quality check.

---

## Files

```
cover_letters/
├── cl_pipeline.py              Main pipeline (Steps 0–3 + QC + optional docx)
├── cl_docx.py                  Generates a clean .docx CL ([Company] Product Team / Best, Akshat)
├── jds/                        JD text files
├── runs/                       Output files
├── story_bank/                 Raw story material (source of truth for CL narratives)
└── prompts/
    ├── step1_cl_jd_analysis.txt Legacy JD analysis (fallback only — Step 0 strategy replaces this)
    ├── step2_cl_generation.txt  Step 2: CL generation prompt
    └── step3_cl_qc.txt          Step 3: AI quality check rubric
```

---

## How the system works

**Step 0 — Strategy** (shared with resume)
Reads the JD + any intel.txt, produces a positioning brief (strategy.json) that both the resume and CL use. Generated once per run by `shared/strategy.py`.

**Step 1 — JD Analysis**
Extracts key signals, company context, and what the hiring team most cares about.

**Step 2 — CL Generation**
Writes the cover letter using the strategy brief and JD analysis. Adapts tone and emphasis to the specific role. A salutation (`Dear <Company> <Team>,`) is automatically prepended and a signoff (`Sincerely,`) is inserted before the signature line for the .txt audit output. The .docx version uses a simpler format (see below).

Voice fingerprint enforces: **0 em dashes** (fully forbidden — all auto-replaced with `; ` in code), full forbidden words list (leveraged, utilized, spearheaded, synergy, actionable, successfully, effectively, streamlined, various, multiple), readability anti-patterns (no and/and chains, no late-arriving subjects). Em dash replacement is a hard post-processing constraint applied before rule checks run.

**Step 3 — QC** (skippable with `--no-qc`)
An AI pass checks the letter against a rubric: relevance to JD signals, voice consistency, length, no forbidden phrases, opening strength.

**Runtime logging**
Each AI call now prints an elapsed time line in the terminal/log (for example `Step 2 complete (48.7s)`), so slow CL runs can be traced to a specific API step instead of inferred indirectly from output timestamps.
The shared provider layer also writes non-sensitive call metadata to
`logs/llm_calls.jsonl` without storing prompts.

**Rule-based QC (always runs):**
- RQC-01: Forbidden phrases (full list matching resume's forbidden words)
- RQC-07: Em dash count — WARN if more than 2 em dashes in the entire letter (excess are auto-trimmed before this check, so a WARN here means the trimmer produced unexpected output)
- RQC-08: Markdown artifacts — FAIL if `**`, `##`, or `[text](url)` found in output

**Docx generation (optional, `--docx` flag):**
`cl_docx.py` generates a clean paste-ready .docx alongside the .txt. Format:
```
[Company] Product Team,

[body paragraphs]

Best,
Akshat
```
No audit trail, no research flags — just the letter.

---

## Usage

In practice, the CL is almost always generated through `run_app.py`, not cl_pipeline.py directly:

```bash
python run_app.py Stripe               # full pipeline (strategy + resume + CL)
python run_app.py Stripe --cl-only     # CL only
python run_app.py Stripe --no-qc       # skip Step 3 QC
python run_app.py Stripe --docx        # also generate .docx resume + .docx CL
python run_app.py Stripe --cl-only --provider cursor --cursor-routing hybrid
```

To run cl_pipeline.py standalone (for debugging or regenerating a CL):

```bash
python cover_letters/cl_pipeline.py Stripe
python cover_letters/cl_pipeline.py Stripe --no-qc
python cover_letters/cl_pipeline.py Stripe --provider cursor --cursor-routing hybrid
```

Anthropic remains the default. Cursor hybrid routing uses Auto for JD analysis
and QC, and non-Fast Grok 4.6 High for the actual cover-letter draft. Cursor failure
stops the run; it never silently consumes Anthropic API credits.

Outputs per application (`apps/<Company>/`):
- `cl_YYYY-MM-DD.txt` — paste-ready cover letter (with full salutation + audit notes)
- `cl_YYYY-MM-DD.json` — audit trail (step analysis + QC data + generation metadata)
- `cl_YYYY-MM-DD_r<score>.docx` — clean letter doc (generated with `--docx` flag); score tag reflects the AI QC overall_score (e.g. `r8.5`). Omitted if `--no-qc` is used.

---

## Cost reference

| Step       | Model  | Cost/job |
|------------|--------|----------|
| Step 1+2   | Sonnet | ~$0.05   |
| Step 3 QC  | Sonnet | ~$0.01   |
| **CL total** |      | **~$0.06** |

This table applies to the Anthropic incumbent. Cursor-provider runs consume the
signed-in Cursor plan allowance rather than per-call Anthropic spend.
