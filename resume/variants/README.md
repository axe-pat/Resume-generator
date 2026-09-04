# Resume variant workbench

This directory contains the isolated v2 variant registry and its review tooling.
Nothing here is selected by the live PM/NONPM generator until it is explicitly
promoted through shadow validation.

- `approved_gold_variants.jsonl` preserves exact variants from reviewed gold
  resumes as regression candidates.
- `live_prompt_variants.jsonl` is the deterministic snapshot of all 152 records
  the current PM/NONPM prompts permit the model to select.
- `prompt_reference_variants.jsonl` separately snapshots the 21 prohibited
  legacy/reference bullets and 5 reference-only PM summaries that remain visible
  in prompt text but are not selectable by contract.
- `prompts/material_variant_challenger_v1.txt` audits one complete story family.
  It selects a claim spine before writing, challenges incumbents pairwise, and
  retains the incumbent whenever a challenger is not materially better.

The challenger prompt is intentionally group-level. It may consolidate same-proof
paraphrases and may preserve multiple siblings when they answer different hiring
questions. It must never edit the live prompt banks directly.

The transferable rendering rule is not limited to the four legacy opener labels.
`tradeoff` is a first-class archetype, and `ownership` may be the scarce causal
atom when the material signal is the decision or operating change that would not
otherwise exist.

Refresh or verify the prompt-derived snapshots from the repository root:

```bash
PYTHONPATH=. venv/bin/python -m shared.prompt_variant_inventory --write
PYTHONPATH=. venv/bin/python -m shared.prompt_variant_inventory --check
```

The extractor records only prompt-derived fields: stable ID, track, story, label,
source line, selectability, exact text, and text hash. It does not infer facts,
quality scores, role tags, or admission status. The checked-in snapshots make any
future prompt-bank drift explicit in tests.

## Whole-bank material challenger

`challenger_runner.py` is an inert, story-level audit runner over the frozen
selectable snapshot. It groups PM and NONPM siblings that use the same proof
surface, excludes summaries and skills rows, preserves every original ID and exact
text, and writes review artifacts only. It never promotes output or edits either
live prompt. A model is always explicit; concurrency is capped at four workers and
retries at three.

Inspect requests without calling Anthropic:

```bash
PYTHONPATH=. venv/bin/python resume/variants/challenger_runner.py \
  --model claude-sonnet-4-6 --story G-PRICING --story H-MONITORING --dry-run
```

Run a bounded calibration after reviewing the dry-run requests:

```bash
PYTHONPATH=. venv/bin/python resume/variants/challenger_runner.py \
  --model claude-sonnet-4-6 --story G-PRICING --story H-MONITORING \
  --workers 2 --retries 2
```

`--all` targets all causal story families. `--resume PATH` conservatively selects
only stories identified by exact live/gold IDs or exact incumbent text; it refuses
to guess from company names. The API key is loaded from the environment or the
repository `.env` without being printed. Each run is written atomically under
`resume/variants/audits/<run-id>/` with request/response/error artifacts, per-story
side-by-side reviews, one `HUMAN_REVIEW.md` batch index, and a manifest containing
the inventory and challenger-prompt hashes. Cross-track value differences are
always surfaced as human decisions; the runner never silently chooses between
inconsistent siblings.

The complete local whole-bank review is indexed at
`docs/resume_generator_reviews/variant_batches/REVIEW_INDEX_2026-09-03.md`.
Its A/B/C JSON companions cover all 135 live causal proof variants exactly once.
They remain inert review artifacts; they are not selector inputs.
