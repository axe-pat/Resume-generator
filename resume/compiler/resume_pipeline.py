#!/usr/bin/env python3
"""
Resume Compiler Pipeline — end-to-end orchestrator
---------------------------------------------------
Takes a JD text file (or a directory of JD text files) and produces a
tailored experience section for each, with zero manual steps.

AI calls:  Step 1 (JD interpretation) + Step 4 (narrative arc check)
           Both on claude-sonnet-4-5 by default (~4000 tokens per JD run)
Compiler:  Steps 2, 3, 5 are fully deterministic — zero AI tokens

Usage:
    Single JD:    python resume/compiler/resume_pipeline.py path/to/jd.txt
    Batch:        python resume/compiler/resume_pipeline.py path/to/jds/

    Options:
      --skip-step4        Skip narrative arc check (saves 1 API call; fine for
                          quick drafts or well-covered archetypes)
      --output-dir DIR    Override output directory (default: runs/)
      --model-step1 M     Model for Step 1 (default: claude-sonnet-4-5)
      --model-step4 M     Model for Step 4 (default: claude-sonnet-4-5)

API key:
    Set ANTHROPIC_API_KEY environment variable, or copy config.example.env
    to .env and fill in the key.

Output:
    runs/YYYY-MM-DD_<company_slug>_<role_slug>.txt   — plain-text resume section
    runs/YYYY-MM-DD_<company_slug>_<role_slug>.json  — full audit trail
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check — friendly message if anthropic not installed
# ---------------------------------------------------------------------------
try:
    import anthropic
except ImportError:
    print("ERROR: 'anthropic' package not found.")
    print("Install it with:  pip install anthropic")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE    = Path(__file__).parent            # resume/compiler/
PROMPTS  = _HERE / "prompts"
RUNS_DIR = _HERE / "runs"

STEP1_PROMPT_FILE = PROMPTS / "step1_jd_interpretation.txt"
STEP4_PROMPT_FILE = PROMPTS / "step4_narrative_arc.txt"

DEFAULT_MODEL_STEP1 = "claude-sonnet-4-5"
DEFAULT_MODEL_STEP4 = "claude-sonnet-4-5"

# ---------------------------------------------------------------------------
# Config / API key loading
# ---------------------------------------------------------------------------

def load_api_key() -> str:
    """
    Load Anthropic API key from:
      1. ANTHROPIC_API_KEY environment variable
      2. .env file in the project directory (KEY=VALUE format)
    Exits with a helpful message if neither is set.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key

    env_path = _HERE.parent.parent / ".env"  # .env lives at ResumeGenerator v1/ root
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key

    print("ERROR: ANTHROPIC_API_KEY not found.")
    print(f"  Option 1: export ANTHROPIC_API_KEY=sk-ant-...")
    print(f"  Option 2: copy config.example.env → .env and fill in your key")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 1 — JD Interpretation (AI)
# ---------------------------------------------------------------------------

def run_step1(jd_text: str, client: anthropic.Anthropic, model: str) -> dict:
    """
    Call the AI with the Step 1 prompt + JD text.
    Returns parsed JD input dict ready for the compiler.
    """
    prompt_template = load_prompt(STEP1_PROMPT_FILE)
    full_prompt = prompt_template.replace("[PASTE JD HERE]", jd_text)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": full_prompt}],
    )

    raw = response.content[0].text.strip()
    jd_dict = _extract_json(raw)

    # Validate and normalise tag_mix
    jd_dict["tag_mix"] = _normalise_tag_mix(jd_dict.get("tag_mix", {}))
    return jd_dict


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from an AI response (handles markdown fences)."""
    # Strip markdown code fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # Find raw JSON object
    raw = re.search(r"\{.*\}", text, re.DOTALL)
    if raw:
        return json.loads(raw.group(0))

    raise ValueError(f"Could not extract JSON from Step 1 response.\nRaw text:\n{text[:400]}")


def _normalise_tag_mix(tag_mix: dict) -> dict:
    """
    Ensure tag_mix sums to exactly 100.
    If it doesn't (due to AI rounding), adjust the largest non-zero tag.
    """
    required_tags = ["GROWTH", "ENTERPRISE", "STRATEGY", "DATA",
                     "AI_ML", "TECHNICAL", "OPS", "GENERAL"]

    # Fill any missing tags with 0
    cleaned = {t: int(tag_mix.get(t, 0)) for t in required_tags}
    total = sum(cleaned.values())

    if total == 100:
        return cleaned

    diff = 100 - total
    if diff == 0:
        return cleaned

    # Apply correction to the largest non-zero tag
    largest = max(cleaned, key=lambda t: cleaned[t])
    cleaned[largest] += diff

    # Sanity check — if correction pushed something negative, clamp
    for t in cleaned:
        if cleaned[t] < 0:
            cleaned[t] = 0

    return cleaned


# ---------------------------------------------------------------------------
# Step 4 — Narrative Arc Check (AI)
# ---------------------------------------------------------------------------

def _format_bullets_for_step4(company_bullets: dict) -> str:
    """Format company_bullets dict into the text block expected by step4 prompt."""
    lines = []
    for company, bullets in company_bullets.items():
        if not bullets:
            continue
        lines.append(company.upper())
        for b in bullets:
            lines.append(f"  Story: {b['story_id']}")
            lines.append(f"  Bullet: \"{b['bullet_text'][:120]}{'...' if len(b['bullet_text']) > 120 else ''}\"")
            lines.append(f"  Framing: {b['framing_type']}")
            lines.append("")
    return "\n".join(lines).strip()


def run_step4(company_bullets: dict, client: anthropic.Anthropic, model: str) -> tuple[str, dict]:
    """
    Call the AI with the Step 4 prompt + selected bullets.
    Returns (raw_text, overrides_dict).
    overrides_dict is empty if action == "proceed".
    """
    prompt_template = load_prompt(STEP4_PROMPT_FILE)
    bullets_text = _format_bullets_for_step4(company_bullets)

    # Replace the placeholder section in the prompt
    full_prompt = re.sub(
        r"\[PASTE THE CONTENTS OF company_bullets FROM THE compiler\.py JSON OUTPUT HERE\]"
        r".*?"
        r"(?=──────────────────────────────────────────────────────────────────────────────\nYOUR TASK)",
        bullets_text + "\n\n",
        prompt_template,
        flags=re.DOTALL,
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": full_prompt}],
    )

    raw = response.content[0].text.strip()
    overrides = _parse_step4_decision(raw)
    return raw, overrides


def _parse_step4_decision(text: str) -> dict:
    """
    Extract the machine-readable JSON decision from the step4 response.
    The prompt instructs the AI to output the JSON on its own line.
    Returns story_overrides dict for compiler.py, or {} if action == "proceed".
    """
    # Scan each line for one that starts with { and contains "action"
    # This is more robust than regex on nested JSON structures.
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and '"action"' in line):
            continue
        try:
            decision = json.loads(line)
        except json.JSONDecodeError:
            continue

        if decision.get("action") != "rerun":
            return {}

        # Build the story_overrides dict expected by compiler.run_compiler()
        overrides = {}
        for item in decision.get("overrides", []):
            company = item.get("company", "")
            remove  = item.get("remove", "")
            add     = item.get("add", "")
            if company and remove and add:
                overrides[company] = {"remove": remove, "add": add}
        return overrides

    # No machine-readable JSON found — default to proceed (safe fallback)
    return {}


# ---------------------------------------------------------------------------
# JD file discovery (batch mode)
# ---------------------------------------------------------------------------

def discover_jd_files(path_arg: str) -> list[Path]:
    """
    Accept a single .txt/.md file or a directory.
    Returns a sorted list of JD file paths.
    """
    p = Path(path_arg)
    if p.is_file():
        return [p]
    if p.is_dir():
        files = sorted(
            f for f in p.iterdir()
            if f.is_file() and f.suffix.lower() in (".txt", ".md")
        )
        if not files:
            print(f"No .txt or .md files found in {p}")
            sys.exit(1)
        return files
    print(f"ERROR: '{path_arg}' is not a file or directory.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Output slug helper
# ---------------------------------------------------------------------------

def make_slug(text: str, max_len: int = 25) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug[:max_len].strip("_")


# ---------------------------------------------------------------------------
# Single JD processing
# ---------------------------------------------------------------------------

def process_jd(jd_path: Path,
               client: anthropic.Anthropic,
               model_step1: str,
               model_step4: str,
               output_dir: Path,
               skip_step4: bool = False) -> Path:
    """
    Full pipeline for one JD file. Returns path to the output .txt file.
    """
    jd_text = jd_path.read_text(encoding="utf-8").strip()
    run_date = str(date.today())

    print(f"\n{'='*60}")
    print(f"Processing: {jd_path.name}")
    print(f"{'='*60}")

    # ── Step 1: JD Interpretation (AI) ───────────────────────────────────────
    print("  [Step 1] JD interpretation (AI)...")
    try:
        jd_dict = run_step1(jd_text, client, model_step1)
    except Exception as e:
        print(f"  ERROR in Step 1: {e}")
        raise

    company_slug = make_slug(jd_dict.get("company", "unknown"))
    role_slug    = make_slug(jd_dict.get("role_title", "pm"))
    base_name    = f"{run_date}_{company_slug}_{role_slug}"

    print(f"  → Archetype: {jd_dict.get('role_archetype')}  "
          f"Context: {jd_dict.get('role_context_fit')}  "
          f"Tags: {jd_dict.get('tag_mix')}")

    # Save JD input JSON for audit
    output_dir.mkdir(parents=True, exist_ok=True)
    jd_json_path = output_dir / f"{base_name}_jd.json"
    with open(jd_json_path, "w", encoding="utf-8") as f:
        json.dump(jd_dict, f, indent=2, ensure_ascii=False)

    # Write to temp file so compiler.py can read it
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(jd_dict, tmp, ensure_ascii=False)
        tmp_jd_path = tmp.name

    # ── Steps 2, 3, 5: Compiler (deterministic) ──────────────────────────────
    print("  [Steps 2/3/5] Compiler (deterministic)...")

    # Import run_compiler from the same directory
    sys.path.insert(0, str(_HERE))
    from compiler import run_compiler

    run_json_path = str(output_dir / f"{base_name}.json")
    run_output = run_compiler(tmp_jd_path, run_json_path, silent=True)

    bullets_summary = "  ".join(
        f"{c}: {run_output['bullet_count'].get(c, 0)}"
        for c in ["Gojek", "Hevo Data", "Intuit", "Optum"]
    )
    print(f"  → Bullets: {run_output['bullet_count']['total']}  ({bullets_summary})")

    # ── Step 4: Narrative Arc Check (AI) ─────────────────────────────────────
    story_overrides = {}
    step4_raw = "(Step 4 skipped)"

    if not skip_step4:
        print("  [Step 4] Narrative arc check (AI)...")
        try:
            step4_raw, story_overrides = run_step4(
                run_output["company_bullets"], client, model_step4
            )
        except Exception as e:
            print(f"  WARN: Step 4 failed ({e}). Proceeding without arc check.")
            step4_raw = f"Step 4 error: {e}"

        if story_overrides:
            print(f"  → Substitutions requested: {story_overrides}")
            print("  [Steps 2/3/5] Re-running compiler with substitutions...")
            run_output = run_compiler(
                tmp_jd_path, run_json_path,
                story_overrides=story_overrides, silent=True
            )
            print(f"  → Rerun complete. Bullets: {run_output['bullet_count']['total']}")
        else:
            print("  → All arcs coherent. No substitutions needed.")

    # Patch narrative arc notes into the run output
    run_output["narrative_arc_notes"] = step4_raw
    with open(run_json_path, "w", encoding="utf-8") as f:
        json.dump(run_output, f, indent=2, ensure_ascii=False)

    # ── Write plain-text output ───────────────────────────────────────────────
    txt_path = output_dir / f"{base_name}.txt"

    gate_summary = []
    for gate, result in run_output["quality_gates"].items():
        symbol = "✓" if result.startswith("pass") else ("⚠" if result.startswith("WARN") or result.startswith("MANUAL") else "✗")
        gate_summary.append(f"{symbol} {gate}")

    txt_content = "\n".join([
        f"Resume Compiler Output",
        f"Run date:  {run_date}",
        f"Company:   {jd_dict.get('company', '')}",
        f"Role:      {jd_dict.get('role_title', '')}",
        f"Archetype: {jd_dict.get('role_archetype', '')}",
        f"Context:   {jd_dict.get('role_context_fit', '')}",
        f"Gates:     {'  '.join(gate_summary)}",
        f"",
        f"{'─' * 60}",
        f"",
        run_output["final_output"],
        f"",
        f"{'─' * 60}",
        f"Audit: {run_json_path}",
    ])

    txt_path.write_text(txt_content, encoding="utf-8")

    # Print quality gate summary (failures and warnings only)
    failures = [
        f"{g}: {r}" for g, r in run_output["quality_gates"].items()
        if not r.startswith("pass")
    ]
    if failures:
        print(f"  ⚠  Gate issues:")
        for f_msg in failures:
            print(f"       {f_msg}")

    print(f"\n  ✓ Output → {txt_path}")

    # Cleanup temp file
    os.unlink(tmp_jd_path)
    return txt_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Resume Compiler Pipeline — paste JD(s), get resume section"
    )
    parser.add_argument(
        "jd_path",
        help="Path to a JD .txt file, or a directory of JD .txt files (batch mode)"
    )
    parser.add_argument(
        "--skip-step4", action="store_true",
        help="Skip narrative arc check (saves 1 API call; good for quick drafts)"
    )
    parser.add_argument(
        "--output-dir", default=str(RUNS_DIR),
        help=f"Directory for output files (default: {RUNS_DIR})"
    )
    parser.add_argument(
        "--model-step1", default=DEFAULT_MODEL_STEP1,
        help=f"Anthropic model for Step 1 (default: {DEFAULT_MODEL_STEP1})"
    )
    parser.add_argument(
        "--model-step4", default=DEFAULT_MODEL_STEP4,
        help=f"Anthropic model for Step 4 (default: {DEFAULT_MODEL_STEP4})"
    )
    args = parser.parse_args()

    api_key = load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)
    output_dir = Path(args.output_dir)

    jd_files = discover_jd_files(args.jd_path)
    total = len(jd_files)
    print(f"Resume Compiler Pipeline — processing {total} JD{'s' if total > 1 else ''}")

    succeeded, failed = [], []
    for jd_file in jd_files:
        try:
            out = process_jd(
                jd_file, client,
                model_step1=args.model_step1,
                model_step4=args.model_step4,
                output_dir=output_dir,
                skip_step4=args.skip_step4,
            )
            succeeded.append((jd_file.name, out))
        except Exception as e:
            print(f"  ERROR processing {jd_file.name}: {e}")
            failed.append((jd_file.name, str(e)))

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Done. {len(succeeded)}/{total} succeeded.")
    for name, out in succeeded:
        print(f"  ✓ {name} → {out.name}")
    for name, err in failed:
        print(f"  ✗ {name} — {err}")


if __name__ == "__main__":
    main()
