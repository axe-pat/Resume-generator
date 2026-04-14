#!/usr/bin/env python3
"""
freeform_runner.py — End-to-end freeform resume generator
=========================================================
Usage:
  Single run:  python freeform_runner.py <jd_file.txt>
               python freeform_runner.py Qualcomm          # matches jds/Qualcomm.txt
  Batch run:   python freeform_runner.py --batch           # all .txt files in jds/
  Options:
    --model MODEL   Anthropic model to use (default: claude-sonnet-4-6)
    --track TRACK   Resume track: 'pm' (default) or 'nonpm' (Strategy/Consulting/Ops/PgM)
    --out DIR       Output directory (default: runs/freeform/)
    --no-color      Disable terminal color output
    --no-rewrite    Skip Pass 2 voice rewrite (faster, saves API cost)
    --no-score      Skip Pass 3 scoring (faster, saves API cost)
    --no-fix        Skip Pass 4 targeted fix loop (implies no re-score)
    --no-strategy   Skip Pass 0 strategy generation (use when re-running quickly)

Pipeline:
  Pass 0 (AI)  — JD + intel → strategy JSON (positioning brief)
  Pass 1 (AI)  — Variant selection + framing (existing freeform_master logic)
  Pass 2 (AI)  — Voice rewrite of 11 bullets + regression guard
  Pass 3 (AI)  — Per-bullet scoring + holistic score
  Pass 4 (AI)  — Targeted fix: surgically rewrites bullets scoring < 8.0
  QC           — Rule-based structural checks
  Output       — runs/YYYY-MM-DD_<slug>.txt + docx (optional)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent            # resume/freeform/
ROOT_DIR      = BASE_DIR.parent.parent           # ResumeGenerator v1/
PROMPT_PATH        = BASE_DIR / "prompts" / "freeform_master_v2.txt"
NONPM_PROMPT_PATH  = BASE_DIR / "prompts" / "freeform_master_nonpm.txt"
REWRITE_PROMPT     = BASE_DIR / "prompts" / "freeform_voice_rewrite.txt"
SCORER_PROMPT      = BASE_DIR / "prompts" / "freeform_scorer.txt"
TARGET_SWAP_PROMPT = BASE_DIR / "prompts" / "freeform_targeted_swap.txt"
JDS_DIR            = BASE_DIR / "jds"
DEFAULT_OUT        = BASE_DIR / "runs"
DEFAULT_MODEL      = "claude-sonnet-4-6"
VALID_TRACKS       = ("pm", "nonpm")
PASS4_THRESHOLD    = 8.0   # bullets scoring below this are sent to Pass 4
PASS4_SKIP_HOLISTIC = 8.0  # skip Pass 4 when holistic score is already at/above this

# Make shared/ importable
sys.path.insert(0, str(ROOT_DIR))

# ANSI colors for terminal output
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

USE_COLOR = True  # toggled by --no-color


def c(color, text):
    return f"{color}{text}{RESET}" if USE_COLOR else text


def _sanitize_summary_section(text: str) -> str:
    """
    Normalize Section 0 summary text.

    We keep this narrower than the experience-section sanitizer because summary
    punctuation wants commas/colons rather than bullet-style rewrites.
    """
    if not text:
        return ""
    clean = text.strip().strip('"')
    # Drop any leaked divider line or section label the model appended on the
    # same line after the summary text.
    clean = re.split(r"\s*[─═\-]{6,}\s*", clean, maxsplit=1)[0]
    clean = re.split(r"\s*SECTION\s+[0-4]\b", clean, maxsplit=1, flags=re.I)[0]
    # Em dashes are forbidden across final resume output. In summaries, a comma
    # reads more naturally than the colon replacement we use for bullets.
    clean = re.sub(r"\s*\u2014\s*", ", ", clean)
    clean = re.sub(r"\s{2,}", " ", clean)
    clean = re.sub(r",\s*,", ", ", clean)
    return clean.strip()


def _title_implies_pm_track(role_title: str, jd_text: str = "") -> bool:
    """
    Conservative PM-track guard for auto-switch logic.

    This is intentionally narrower than "any role with product in the title".
    It protects explicit PM titles and PM-adjacent Product Development roles
    whose JD clearly centers roadmap/research/launch/product-definition work.
    """
    if not role_title:
        return False

    if re.search(
        r"\b(product manager|product management|product intern|product management intern|apm|pm intern|technical product manager|technical program manager|technical pm|tpm)\b",
        role_title,
        re.I,
    ):
        return True

    if re.search(r"\b(program manager|program management)\b", role_title, re.I):
        jd_lower = (jd_text or "").lower()
        pm_program_signals = [
            "product requirements",
            "user stories",
            "backlog grooming",
            "sprint planning",
            "product team",
            "product managers",
            "user research",
            "competitive analysis",
            "product insights",
            "roadmap",
            "product, security",
            "engineering, product",
        ]
        if any(signal in jd_lower for signal in pm_program_signals):
            return True

    if re.search(r"\bproduct development\b", role_title, re.I):
        jd_lower = (jd_text or "").lower()
        pm_adjacent_signals = [
            "product roadmap",
            "product launches",
            "consumer research",
            "consumer insights",
            "competitive landscape",
            "sku",
            "product definition",
            "product development team",
        ]
        if any(signal in jd_lower for signal in pm_adjacent_signals):
            return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Loading
# ─────────────────────────────────────────────────────────────────────────────
def load_prompt(jd_text: str, strategy_block: str = "",
                prompt_path: "Path | None" = None) -> str:
    """Load master prompt and inject JD + strategy.

    Args:
        prompt_path: override which master prompt file to use.
                     Defaults to PROMPT_PATH (freeform_master_v2.txt).
    """
    path = prompt_path or PROMPT_PATH
    if not path.exists():
        sys.exit(f"[ERROR] Prompt not found: {path}")
    template = path.read_text(encoding="utf-8")
    if "{{JOB_DESCRIPTION}}" not in template:
        sys.exit(f"[ERROR] {path.name} missing {{{{JOB_DESCRIPTION}}}} placeholder")
    prompt = template.replace("{{JOB_DESCRIPTION}}", jd_text.strip())
    if "{{STRATEGY}}" in prompt:
        prompt = prompt.replace(
            "{{STRATEGY}}",
            strategy_block.strip() if strategy_block else "No strategy generated — proceed using JD signals only.",
        )
    return prompt


def load_rewrite_prompt(experience_section: str, jd_text: str, strategy_block: str) -> str:
    """Load voice rewrite prompt and inject inputs."""
    if not REWRITE_PROMPT.exists():
        return ""
    template = REWRITE_PROMPT.read_text(encoding="utf-8")
    template = template.replace("{{EXPERIENCE_SECTION}}", experience_section.strip())
    template = template.replace("{{JOB_DESCRIPTION}}", jd_text.strip())
    template = template.replace(
        "{{STRATEGY}}",
        strategy_block.strip() if strategy_block else "No strategy provided.",
    )
    return template


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 regression guard
# ─────────────────────────────────────────────────────────────────────────────
_BULLET_PAT = re.compile(r'^([\u2022\u25cf\-\*●•])\s+(.*)')
_CONTRAST_PAT = re.compile(r'\b(?:rather than|instead of)\b|not\b[^.]{0,80}\bbut\b', re.I)


def _contrast_phrase_count(text: str) -> int:
    if not text:
        return 0
    return len(_CONTRAST_PAT.findall(text))


def _apply_regression_guard(p1_section: str, p2_section: str) -> tuple[str, list[str]]:
    """
    Compare Pass 1 and Pass 2 bullets pairwise.
    Revert any Pass 2 bullet that:
      - Contains 2+ colons (double-colon syntactic error), OR
      - Is more than 60 chars longer than its Pass 1 counterpart (bloat).
    Returns (patched_p2_section, list_of_revert_log_messages).
    """
    # Extract Pass 1 bullet texts (in order)
    p1_bullets = []
    for line in p1_section.splitlines():
        m = _BULLET_PAT.match(line.strip())
        if m:
            p1_bullets.append(m.group(2).strip())

    # Build index of Pass 2 bullet lines (line_index, prefix_char, bullet_text)
    p2_lines = p2_section.splitlines()
    p2_bullet_refs = []
    for i, line in enumerate(p2_lines):
        m = _BULLET_PAT.match(line.strip())
        if m:
            p2_bullet_refs.append((i, m.group(1), m.group(2).strip()))

    reverts = []
    patched = list(p2_lines)
    p1_contrast_total = _contrast_phrase_count(p1_section)
    p2_contrast_total = _contrast_phrase_count(p2_section)
    contrast_overflow = p2_contrast_total > 1 and p2_contrast_total > p1_contrast_total

    for bnum, (line_idx, prefix, p2_text) in enumerate(p2_bullet_refs):
        if bnum >= len(p1_bullets):
            break
        p1_text = p1_bullets[bnum]

        # Detect regression
        colon_count   = p2_text.count(":")
        length_growth = len(p2_text) - len(p1_text)
        p1_len        = len(p1_text)
        p2_len        = len(p2_text)
        # 2-liner → 3-liner: P1 was ≤199 chars (2-liner range) and P2 is ≥230 chars
        is_new_three_liner = (p1_len <= 199 and p2_len >= 230)
        # Extreme bloat on any bullet (catches long-on-long growth)
        is_extreme_bloat   = (length_growth > 80)
        reasons = []
        if colon_count >= 2:
            reasons.append(f"double-colon ({colon_count} colons)")
        if is_new_three_liner:
            reasons.append(f"2-liner→3-liner (P1={p1_len}, P2={p2_len} chars)")
        elif is_extreme_bloat:
            reasons.append(f"extreme bloat (+{length_growth} chars)")
        if contrast_overflow and _contrast_phrase_count(p2_text) > _contrast_phrase_count(p1_text):
            reasons.append("added contrast phrase beyond section cap")
        # H3 metric guard: if Pass 1 had the direct 30% issue-resolution metric,
        # don't let later passes blur it into vague "response time" language.
        p1_lower = p1_text.lower()
        p2_lower = p2_text.lower()
        if ("issue-resolution" in p1_lower or "issue resolution" in p1_lower) and "30%" in p1_text:
            if not (("issue-resolution" in p2_lower or "issue resolution" in p2_lower) and "30%" in p2_text):
                reasons.append("lost direct H3 resolution-time metric")

        if reasons:
            # Preserve original leading whitespace from the p2 line
            orig_line     = p2_lines[line_idx]
            leading_ws    = len(orig_line) - len(orig_line.lstrip())
            patched[line_idx] = " " * leading_ws + prefix + " " + p1_text
            reverts.append(
                f"  [RG] Bullet #{bnum + 1} reverted [{', '.join(reasons)}]:"
                f"\n       P2: {p2_text[:90]}{'…' if len(p2_text) > 90 else ''}"
                f"\n       P1: {p1_text[:90]}{'…' if len(p1_text) > 90 else ''}"
            )

    return "\n".join(patched), reverts


def load_scorer_prompt(experience_section: str, jd_text: str,
                       strategy_block: str = "",
                       role_preamble: str = "",
                       projects_section: str = "") -> str:
    """Load scorer prompt and inject inputs.

    Args:
        role_preamble: optional block prepended before the prompt body.
                       Used for the nonpm track to remind the scorer that
                       'reframed', 'diagnosed', 'synthesized' etc. are
                       appropriate openers for Strategy/Consulting/Ops roles
                       and should NOT be flagged as WRONG_ARCHETYPE.
    """
    if not SCORER_PROMPT.exists():
        return ""
    template = SCORER_PROMPT.read_text(encoding="utf-8")
    template = template.replace("{{EXPERIENCE_SECTION}}", experience_section.strip())
    template = template.replace(
        "{{PROJECTS_SECTION}}",
        projects_section.strip() if projects_section.strip() else "No projects section provided.",
    )
    template = template.replace("{{JOB_DESCRIPTION}}", jd_text.strip())
    template = template.replace(
        "{{STRATEGY}}",
        strategy_block.strip() if strategy_block else "No strategy provided.",
    )
    if role_preamble:
        template = role_preamble.strip() + "\n\n" + template
    return template


# ─────────────────────────────────────────────────────────────────────────────
# API Call
# ─────────────────────────────────────────────────────────────────────────────
def load_api_key() -> str:
    """Load API key from environment or .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    sys.exit("[ERROR] ANTHROPIC_API_KEY not set. Check .env or environment.")


def call_api(prompt: str, model: str, label: str = "", max_tokens: int = 8192) -> str:
    """Call Anthropic API and return full response text.

    Retries up to 3 times on rate-limit (429) and overload (529) errors with
    exponential backoff. max_tokens defaults to 8192 — sufficient for the
    scorer's verbose JSON output.
    """
    import anthropic
    import httpx

    api_key = load_api_key()
    client = anthropic.Anthropic(
        api_key=api_key,
        http_client=httpx.Client(verify=False),
    )
    tag = f" [{label}]" if label else ""
    print(c(CYAN, f"  → Calling {model}{tag}..."), flush=True)
    for attempt in range(4):  # 1 initial + 3 retries
        try:
            started = time.perf_counter()
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.perf_counter() - started
            done_label = label or "API call"
            print(c(GREEN, f"  ✓ {done_label} complete ({elapsed:.1f}s)"), flush=True)
            return message.content[0].text
        except anthropic.RateLimitError as e:
            if attempt == 3:
                raise
            wait = 20 * (2 ** attempt)   # 20s, 40s, 80s
            print(c(YELLOW,
                    f"  [!] Rate limit hit{tag} — waiting {wait}s before retry "
                    f"(attempt {attempt + 1}/3)..."), flush=True)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if getattr(e, "status_code", None) != 529 or attempt == 3:
                raise
            wait = 20 * (2 ** attempt)   # 20s, 40s, 80s
            print(c(YELLOW,
                    f"  [!] Anthropic overloaded{tag} — waiting {wait}s before retry "
                    f"(attempt {attempt + 1}/3)..."), flush=True)
            time.sleep(wait)
    return ""  # unreachable


# ─────────────────────────────────────────────────────────────────────────────
# Pass 0 — Strategy generation
# ─────────────────────────────────────────────────────────────────────────────
def run_strategy_pass(jd_path: Path, jd_text: str, model: str) -> tuple[dict, str]:
    """
    Generate application strategy. Returns (strategy_dict, formatted_block).
    Falls back to ({}, "") on any failure — pipeline continues without strategy.
    """
    intel_path = jd_path.parent / f"{jd_path.stem}_intel.txt"
    intel_text = ""
    if intel_path.exists():
        intel_text = intel_path.read_text(encoding="utf-8").strip()
        print(c(GREEN, f"  ✓ Intel file found: {intel_path.name}"))
    else:
        print(c(YELLOW, "  [i] No intel file — generating strategy without additional context"))

    try:
        from shared.strategy import generate_strategy

        api_key = load_api_key()
        strategy_dict, formatted_block = generate_strategy(
            jd_text=jd_text, intel_text=intel_text, model=model, api_key=api_key,
        )
        return strategy_dict, formatted_block
    except Exception as e:
        print(c(YELLOW, f"  [!] Strategy generation failed: {e} — continuing without strategy"))
        return {}, ""


def print_strategy_summary(d: dict):
    """Print key strategy fields to console."""
    if not d or "parse_error" in d:
        return
    print()
    print(c(BOLD, "  Strategy:"))
    for key in ["primary_framing_axis", "secondary_framing_axis", "archetype", "tone"]:
        val = d.get(key, "—")
        print(f"    {key:<30} {val}")
    signals = d.get("top_signals", [])
    if signals:
        print(f"    {'top_signals':<30} {' | '.join(signals)}")
    primary = (d.get("story_recommendations") or ["—"])[0]
    print(f"    {'primary_story':<30} {primary}")
    narrative = d.get("positioning_narrative", "")
    if narrative:
        # Print first sentence only for console brevity
        first_sentence = narrative.split(".")[0] + "." if "." in narrative else narrative
        print(f"    {'narrative':<30} {first_sentence[:80]}{'...' if len(first_sentence) > 80 else ''}")


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — Variant selection (existing logic, now strategy-aware)
# ─────────────────────────────────────────────────────────────────────────────
def extract_sections(response: str) -> dict:
    """
    Parse the required sections from model output.
    Returns dict with keys: signals, selection_notes, summary_section,
                            experience_section, projects_section,
                            skills_section, raw.
    """
    result = {"signals": "", "selection_notes": "", "summary_section": "",
              "experience_section": "", "projects_section": "",
              "skills_section": "", "raw": response}

    # Section 1
    m = re.search(r"SECTION 1[^\n]*\n(.*?)(?=SECTION 2|\Z)", response, re.S | re.I)
    if m:
        result["signals"] = m.group(1).strip()

    # Section 2
    m = re.search(r"SECTION 2[^\n]*\n(.*?)(?=SECTION 0|SECTION 3|\Z)", response, re.S | re.I)
    if m:
        result["selection_notes"] = m.group(1).strip()

    # Section 0 — Professional Summary.
    # Non-PM prompt now includes Section 1 and Section 2 after Section 0, so stop
    # summary capture before either later section as well as Section 3.
    m = re.search(r"SECTION 0[^\n]*\n[─═\-=\u2500-\u257F]*\n?(.*?)(?=\nSECTION 1|\nSECTION 2|---|\nSECTION 3|\Z)",
                  response, re.S | re.I)
    if m:
        result["summary_section"] = _sanitize_summary_section(m.group(1))

    # Section 3 — from GOJEK header up to the optional Projects section or Skills section.
    m = re.search(
        r"(GOJEK \| Senior Software Engineer.*?)(?=\nSECTION 3B|\nPROJECTS & CONSULTING|\nSKILLS & INTERESTS|\nSECTION 4|\Z)",
                  response, re.S | re.I)
    if m:
        result["experience_section"] = m.group(1).strip()

    # Section 3B — optional Projects & Consulting block (non-PM routes only).
    m = re.search(
        r"SECTION 3B[^\n]*\n[─═\-=\u2500-\u257F]*\n?"
        r"(PROJECTS & CONSULTING.*?)(?=\nSECTION 4|\Z)",
        response,
        re.S | re.I,
    )
    if m:
        result["projects_section"] = m.group(1).strip()

    # Section 4 — SKILLS & INTERESTS block
    m = re.search(r"(SKILLS & INTERESTS\s*\n\s*●.*)", response, re.S | re.I)
    if m:
        result["skills_section"] = m.group(1).strip()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — Voice rewrite
# ─────────────────────────────────────────────────────────────────────────────
def run_voice_rewrite(
    experience_section: str, jd_text: str, strategy_block: str, model: str,
    extra_constraint: str = "", role_preamble: str = "",
) -> tuple[str, str]:
    """
    Run voice rewrite pass.
    Returns (rewritten_experience_section, rewrites_log).
    Falls back to (original, "") on failure.

    extra_constraint: optional hard instruction prepended to the prompt (used by QC-03 retry).
    """
    if not REWRITE_PROMPT.exists():
        print(c(YELLOW, "  [!] Voice rewrite prompt not found — skipping Pass 2."))
        return experience_section, ""

    prompt = load_rewrite_prompt(experience_section, jd_text, strategy_block)
    if not prompt:
        return experience_section, ""

    if role_preamble:
        prompt = role_preamble.strip() + "\n\n" + prompt
    if extra_constraint:
        prompt = f"ADDITIONAL CONSTRAINT:\n{extra_constraint}\n\n{prompt}"

    print()
    print(c(BOLD, "  Pass 2 — Voice Rewrite"))
    raw = call_api(prompt, model, "Pass 2: Voice")

    # ── Extract rewrites log (needed below for trimming raw) ──────────────────
    log = ""
    m_log = re.search(r"REWRITES LOG\s*\n[-─]+\n(.*)", raw, re.S | re.I)
    if m_log:
        log = m_log.group(1).strip()

    # ── Extract rewritten experience section ──────────────────────────────────
    # Strategy: find the LAST occurrence of a GOJEK header in the raw output
    # before the REWRITES LOG.  The model sometimes self-corrects multiple times
    # within the REWRITTEN EXPERIENCE SECTION block, producing intermediate
    # drafts.  Taking the LAST GOJEK block avoids capturing that intermediate
    # deliberation as part of the experience section.
    raw_before_log = raw[:m_log.start()] if m_log else raw

    # All GOJEK-header positions in the pre-log output
    gojek_hits = list(re.finditer(
        r"GOJEK \| Senior Software Engineer", raw_before_log, re.I,
    ))

    rewritten = ""
    if gojek_hits:
        last_start = gojek_hits[-1].start()
        rewritten  = raw_before_log[last_start:].strip()
    else:
        # Fallback: parse via section header (multiple separator styles)
        for _pat in [
            r"REWRITTEN EXPERIENCE SECTION\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*?)(?=\n\s*REWRITES LOG|\Z)",
            r"REWRITTEN EXPERIENCE SECTION\s*\n[^\n]*\n(.*?)(?=\n\s*REWRITES LOG|\Z)",
            r"REWRITTEN EXPERIENCE SECTION[^\n]*\n(.*?)(?=\n\s*REWRITES LOG|\Z)",
        ]:
            _m2 = re.search(_pat, raw, re.S | re.I)
            if _m2:
                _cand = _m2.group(1).strip()
                if len(re.findall(r"^\s*•", _cand, re.MULTILINE)) >= 5:
                    rewritten = _cand
                    break

    if not rewritten:
        print(c(YELLOW, "  [!] Could not parse rewrite output — using Pass 1 bullets."))
        return experience_section, ""

    # Truncate any trailing reasoning the model appended after the last bullet.
    # The model sometimes outputs "Wait: pre-submit holistic checks:" or similar
    # reasoning text AFTER the experience section but BEFORE the REWRITES LOG
    # separator, causing everything from the GOJEK header onwards to be captured
    # as the "rewritten" section (including thousands of chars of non-bullet text).
    _rw_lines = rewritten.splitlines()
    _last_bullet_idx = None
    for _i, _ln in enumerate(_rw_lines):
        if re.match(r"^\s*•", _ln):
            _last_bullet_idx = _i
    if _last_bullet_idx is not None:
        rewritten = "\n".join(_rw_lines[:_last_bullet_idx + 1]).strip()

    # Strip markdown formatting (bold headers, dash bullets, ---  separators)
    # that the model sometimes emits when self-correcting inline.
    rewritten = _sanitize_experience_section(rewritten)

    # Sanity-check: a valid section has 11 bullet lines
    n_bullets = len([l for l in rewritten.splitlines()
                     if re.match(r'^[\u2022\u25cf\-\*●•]\s+\S', l.strip())])
    if n_bullets != 11:
        print(c(YELLOW, f"  [!] Pass 2: expected 11 bullets in rewrite, found {n_bullets} "
                        f"— regression guard + QC will flag structural issues"))

    ok_structure, structure_detail = validate_experience_structure(rewritten)
    if not ok_structure:
        print(c(YELLOW,
                f"  [!] Pass 2: invalid company bullet structure after rewrite "
                f"({structure_detail}) — using Pass 1 bullets."))
        return experience_section, ""

    return rewritten, log


# ─────────────────────────────────────────────────────────────────────────────
# Pass 3 — Scoring
# ─────────────────────────────────────────────────────────────────────────────
def run_scorer(experience_section: str, jd_text: str, model: str,
               strategy_block: str = "",
               role_preamble: str = "",
               projects_section: str = "") -> dict:
    """
    Run scoring pass. Returns scorer JSON dict.
    Returns {} on failure.
    """
    if not SCORER_PROMPT.exists():
        print(c(YELLOW, "  [!] Scorer prompt not found — skipping Pass 3."))
        return {}

    prompt = load_scorer_prompt(
        experience_section,
        jd_text,
        strategy_block,
        role_preamble=role_preamble,
        projects_section=projects_section,
    )
    if not prompt:
        return {}

    print()
    print(c(BOLD, "  Pass 3 — Scoring"))
    raw = call_api(prompt, model, "Pass 3: Score", max_tokens=4096)

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    m = re.search(r"\{.*\}", cleaned, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            print(c(YELLOW, f"  [!] Scorer JSON parse error: {e}"))
            return {"raw": raw, "parse_error": str(e)}
    print(c(YELLOW, "  [!] Could not find JSON in scorer output."))
    return {"raw": raw}


def print_score(score_data: dict):
    """Print scoring summary to console."""
    if not score_data or "holistic_score" not in score_data:
        return
    score   = score_data.get("holistic_score", "?")
    verdict = score_data.get("verdict", "?")
    vcolor  = GREEN if verdict == "SEND" else (YELLOW if verdict == "REVISE" else RED)

    print()
    print(c(BOLD, "  Resume Score:"))
    print(f"    Score:   {c(BOLD + vcolor, str(score))}/10")
    print(f"    Verdict: {c(vcolor, verdict)}")

    top_issue  = score_data.get("top_issue", "")
    strengths  = score_data.get("strengths", "")
    jd_fit     = score_data.get("jd_fit_note", "")
    narrative  = score_data.get("narrative_note", "")
    if strengths:
        print(f"    Strengths: {strengths[:90]}{'...' if len(strengths) > 90 else ''}")
    if top_issue:
        print(f"    Top issue: {top_issue[:90]}{'...' if len(top_issue) > 90 else ''}")
    if jd_fit:
        print(f"    JD fit:    {jd_fit[:90]}{'...' if len(jd_fit) > 90 else ''}")
    if narrative:
        print(f"    Narrative: {narrative[:90]}{'...' if len(narrative) > 90 else ''}")

    bullets = score_data.get("bullets", [])
    if bullets:
        print()
        print("  Bullet scores:")
        for b in bullets:
            bscore   = b.get("score", "?")
            company  = b.get("company", "?")
            idx      = b.get("index", "?")
            fm       = b.get("failure_mode") or ""
            arch     = b.get("archetype_used", "") or ""
            note     = b.get("note", "")
            if isinstance(bscore, (int, float)):
                bcolor = GREEN if bscore >= 8.5 else (YELLOW if bscore >= 7 else RED)
            else:
                bcolor = RESET
            fm_str   = f" [{c(RED, fm)}]" if fm else ""
            arch_str = f" ({arch})" if arch and arch != "forbidden" else ""
            note_str = f"  {note[:50]}{'…' if len(note) > 50 else ''}" if note else ""
            print(f"    {c(bcolor, f'{bscore:4.1f}')}  {company:<10} #{idx}{arch_str}{fm_str}{note_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Pass 4 — Targeted fix loop
# ─────────────────────────────────────────────────────────────────────────────
def _sanitize_experience_section(text: str) -> str:
    """
    Strip markdown formatting the model sometimes emits in Pass 4 output:
      - Remove '---' horizontal-rule separators
      - Strip **bold** markers from company headers
      - Convert '- bullet' to '• bullet'
      - Drop stray sub-headers like '**GOJEK #1**' or 'ORIGINAL: …' lines
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # Drop horizontal rule separators (3+ dashes or box-drawing chars)
        if re.match(r'^[-─]{3,}$', stripped):
            continue
        # Strip **bold** markers
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', stripped)
        clean = re.sub(r'\*([^*]+)\*',   r'\1', clean)
        # Drop stray per-bullet sub-headers ("GOJEK #1", "HEVO DATA #2", etc.)
        if re.match(r'^(GOJEK|HEVO DATA|HEVO|INTUIT|OPTUM)\s*#\d+\s*$', clean, re.I):
            continue
        # Drop log-internal labels ("ORIGINAL:", "FIXED:", "FAILURE:", "FIX:", "CHANGE:")
        if re.match(r'^(ORIGINAL|FIXED|FAILURE|FIX|CHANGE|REWRITTEN)\s*:', clean, re.I):
            continue
        # Convert dash bullets → bullet char
        m_bullet = re.match(r'^-\s+(.*)', clean)
        if m_bullet:
            clean = '\u2022 ' + m_bullet.group(1)
        lines.append(clean)

    result = '\n'.join(lines)
    # Collapse runs of 3+ blank lines to two
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def _extract_bullet_by_ref(experience_section: str, company: str, index: int) -> str:
    """Extract the bullet text for a given company key + 1-based bullet index."""
    current_company = None
    count = 0
    for line in experience_section.splitlines():
        stripped = line.strip().lstrip("*").strip()
        for key in ["GOJEK", "HEVO DATA", "INTUIT", "OPTUM"]:
            if stripped.upper().startswith(key):
                current_company = key
                count = 0
                break
        if current_company and current_company.upper() == company.upper().strip():
            m = _BULLET_PAT.match(stripped)
            if m:
                count += 1
                if count == index:
                    return m.group(2).strip()
    return ""


def _revert_regressed_bullets(
    exp_text: str,
    revert_keys: set,          # {(COMPANY_KEY, bullet_index), ...}
    pre_fix_texts: dict,       # {(COMPANY_KEY, bullet_index): original_bullet_text}
) -> str:
    """
    Walk exp_text line by line. For each bullet whose (company_key, index) is in
    revert_keys, replace the bullet text with the pre-Pass-4 original.
    Preserves company header lines and all non-bullet lines verbatim.
    """
    out_lines   = []
    current_key = None
    bullet_idx  = 0

    for line in exp_text.splitlines():
        stripped    = line.strip().lstrip("*").strip()
        matched_key = next((k for k in _COMPANY_KEYS if stripped.upper().startswith(k)), None)
        if matched_key:
            current_key = matched_key
            bullet_idx  = 0
            out_lines.append(line)
            continue

        if current_key is not None:
            m = re.match(r'^[\u2022\u25cf\-\*]\s+(.*)', stripped)
            if m:
                bullet_idx += 1
                bkey = (current_key, bullet_idx)
                if bkey in revert_keys and bkey in pre_fix_texts:
                    out_lines.append(f"\u2022 {pre_fix_texts[bkey]}")
                    continue

        out_lines.append(line)

    return "\n".join(out_lines)


def _format_scorer_bullets(weak_bullets: list, experience_section: str) -> str:
    """Format weak bullets for the {{SCORER_BULLETS}} template placeholder."""
    lines = []
    for b in weak_bullets:
        company = b.get("company", "?")
        idx     = b.get("index", "?")
        score   = b.get("score", "?")
        fm      = b.get("failure_mode", "") or ""
        note    = b.get("note", "") or ""
        arch    = b.get("archetype_used", "") or ""
        text    = (_extract_bullet_by_ref(experience_section, company, idx)
                   if isinstance(idx, int) else "")
        lines.append(f"{company} #{idx}")
        lines.append(f"  score:        {score}")
        if arch:
            lines.append(f"  archetype:    {arch}")
        if fm:
            lines.append(f"  failure_mode: {fm}")
        if note:
            lines.append(f"  note:         {note}")
        if text:
            lines.append(f"  bullet:       \u2022 {text}")
        lines.append("")
    return "\n".join(lines)


# ── QC-13: Length violation detection + trim ──────────────────────────────────

_THREE_LINE_CHARS = 200        # detection threshold: bullets ≥200 chars are flagged as 3-liners
_AUTO_TRIM_CHARS  = 260        # auto-trim threshold: only trim bullets ≥260 chars (4-liner territory)
_MAX_ALLOWED_THREE_LINERS = 3  # QC-13 warning fires when >3 bullets ≥_THREE_LINE_CHARS
_MAX_ALLOWED_AUTO_TRIM    = 2  # auto-trim fires only when >2 bullets ≥_AUTO_TRIM_CHARS


def _find_length_violations(
    experience_section: str,
    score_data: dict,
    max_auto_trim: int = _MAX_ALLOWED_AUTO_TRIM,
) -> list[dict]:
    """
    Return synthetic scorer-style bullet dicts for bullets that are in 4-liner
    territory (≥ _AUTO_TRIM_CHARS) beyond the allowed maximum.

    Uses _AUTO_TRIM_CHARS (not _THREE_LINE_CHARS) so that regular 3-liners (200-259
    chars) are not auto-trimmed — they're informational only.  Only genuine outliers
    (260+ chars) trigger the trim API call.

    Strategy: keep the `max_auto_trim` longest-but-within-limit bullets as acceptable;
    flag the rest as BULLET_TOO_LONG.
    """
    # Collect all bullets with company + index + char count
    company_blocks = parse_experience_blocks(experience_section)
    all_bullets = []
    for block in company_blocks:
        for i, bullet_text in enumerate(block.get("bullets", []), start=1):
            text = bullet_text.strip()
            all_bullets.append({
                "company": block["key"],
                "index": i,
                "text": text,
                "length": len(text),
            })

    # Filter to over-long bullets only (4-liner territory)
    over_long = [b for b in all_bullets if b["length"] >= _AUTO_TRIM_CHARS]
    if len(over_long) <= max_auto_trim:
        return []  # within allowed count — nothing to do

    # Match to scorer scores so we can keep the highest-scoring ones
    scorer_map = {}
    for sb in (score_data or {}).get("bullets", []):
        key = (str(sb.get("company", "")).upper(), int(sb.get("index", 0)))
        scorer_map[key] = float(sb.get("score", 5.0) or 5.0)

    for b in over_long:
        b["score"] = scorer_map.get((b["company"].upper(), b["index"]), 5.0)

    # Sort by score descending — keep the top-N as acceptable
    over_long.sort(key=lambda b: b["score"], reverse=True)
    to_trim = over_long[max_auto_trim:]   # everything beyond the top-N

    # Build synthetic scorer bullet dicts that run_targeted_fixes can consume
    return [
        {
            "company":      b["company"],
            "index":        b["index"],
            "score":        b["score"],
            "failure_mode": "BULLET_TOO_LONG",
            "note":         (
                f"{b['length']} chars (≥{_AUTO_TRIM_CHARS}). "
                f"Trim to 180–240 chars: keep mechanism verb, artifact, and primary "
                f"metric; cut least-essential elaboration last."
            ),
        }
        for b in to_trim
    ]


def run_length_trim(
    experience_section: str,
    score_data: dict,
    jd_text: str,
    strategy_block: str,
    model: str,
) -> tuple[str, str]:
    """
    QC-13 auto-trim: rewrite only the over-length bullets (3-liners beyond the
    allowed maximum of _MAX_ALLOWED_THREE_LINERS) down to 2-liners (140–195 chars).

    Uses the same targeted_swap prompt as Pass 4 with BULLET_TOO_LONG failure mode.
    Returns (trimmed_experience_section, trim_log).
    Falls back to (original, "") if nothing to trim or on parse failure.
    """
    if not TARGET_SWAP_PROMPT.exists():
        return experience_section, ""

    violations = _find_length_violations(experience_section, score_data)
    if not violations:
        print(c(GREEN, f"  ✓ Bullet lengths OK — ≤{_MAX_ALLOWED_THREE_LINERS} three-liners."))
        return experience_section, ""

    print()
    print(c(BOLD, f"  QC-13 Trim — {len(violations)} bullet(s) over the "
            f"{_MAX_ALLOWED_THREE_LINERS}-three-liner limit:"))
    for v in violations:
        length = next(
            (b["length"] for block in parse_experience_blocks(experience_section)
             for i, b_text in enumerate(block.get("bullets", []), 1)
             if block["key"] == v["company"] and i == v["index"]
             for b in [{"length": len(b_text.strip())}]),
            "?",
        )
        print(c(YELLOW, f"    {v['company']} #{v['index']}: {length} chars "
                f"(score {v['score']:.1f})"))

    scorer_bullets_text = _format_scorer_bullets(violations, experience_section)
    template = TARGET_SWAP_PROMPT.read_text(encoding="utf-8")
    prompt = (
        template
        .replace("{{EXPERIENCE_SECTION}}", experience_section.strip())
        .replace("{{SCORER_BULLETS}}", scorer_bullets_text)
        .replace("{{JOB_DESCRIPTION}}", jd_text.strip())
        .replace("{{STRATEGY}}",
                 strategy_block.strip() if strategy_block else "No strategy provided.")
    )

    raw = call_api(prompt, model, "QC-13 Trim")

    # Parse the REVISED EXPERIENCE SECTION — try multiple header/separator patterns
    # in order of strictness; stop at first match that contains ≥5 bullets.
    revised = ""
    _PARSE_PATS = [
        # P1: exact header + any horizontal-rule chars (─ ═ - = and Unicode box-drawing range)
        r"REVISED EXPERIENCE SECTION\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*?)(?=\n\s*FIX LOG|\Z)",
        # P2: header + optional blank/separator line (handles model omitting separator)
        r"REVISED EXPERIENCE SECTION\s*\n[^\n]*\n(.*?)(?=\n\s*FIX LOG|\Z)",
        # P3: header with no separator — grab everything after it
        r"REVISED EXPERIENCE SECTION[^\n]*\n(.*?)(?=\n\s*FIX LOG|\Z)",
    ]
    for _pat in _PARSE_PATS:
        _m = re.search(_pat, raw, re.S | re.I)
        if _m:
            _candidate = _m.group(1).strip()
            # Must contain at least 5 bullets to be a real experience section
            if len(re.findall(r"^\s*•", _candidate, re.MULTILINE)) >= 5:
                revised = _candidate
                break

    if not revised:
        # Fallback: find the last occurrence of a company header block
        # (GOJEK is always first in the section, so finding GOJEK anchors the whole block)
        _company_matches = list(re.finditer(
            r"((?:GOJEK|HEVO|INTUIT|OPTUM)\s*\|[^\n]+\n.*?)(?=\n\s*FIX LOG|\Z)",
            raw, re.S | re.I,
        ))
        if _company_matches:
            revised = _company_matches[-1].group(1).strip()

    if not revised:
        print(c(YELLOW, "  [!] Could not parse QC-13 Trim output — keeping original."))
        return experience_section, ""

    # Strip any trailing non-bullet reasoning text, then strip markdown artifacts
    _tr_lines = revised.splitlines()
    _last_b = next((i for i in range(len(_tr_lines) - 1, -1, -1)
                    if re.match(r"^\s*•", _tr_lines[i])), None)
    if _last_b is not None:
        revised = "\n".join(_tr_lines[:_last_b + 1]).strip()
    revised = _sanitize_experience_section(revised)

    # Sanity: bullet count must stay at 11
    bullet_count = len(re.findall(r"^\s*•", revised, re.MULTILINE))
    if bullet_count != 11:
        print(c(YELLOW,
                f"  [!] QC-13 Trim produced {bullet_count} bullets (expected 11) — "
                "keeping original."))
        return experience_section, ""

    # Measure improvement
    company_blocks_after = parse_experience_blocks(revised)
    all_after = [
        len(bt.strip())
        for block in company_blocks_after
        for bt in block.get("bullets", [])
    ]
    three_after = sum(1 for ln in all_after if ln >= _THREE_LINE_CHARS)
    print(c(GREEN if three_after <= _MAX_ALLOWED_THREE_LINERS else YELLOW,
            f"  ✓ QC-13 Trim: three-liners {len(violations) + _MAX_ALLOWED_THREE_LINERS} "
            f"→ {three_after} (target ≤{_MAX_ALLOWED_THREE_LINERS})"))

    trim_log = ""
    m_log = re.search(r"FIX LOG\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*)", raw, re.S | re.I)
    if not m_log:
        m_log = re.search(r"FIX LOG[^\n]*\n(.*)", raw, re.S | re.I)
    if m_log:
        trim_log = m_log.group(1).strip()

    return revised, trim_log


def run_targeted_fixes(
    experience_section: str, score_data: dict, jd_text: str,
    strategy_block: str, model: str,
) -> tuple[str, str]:
    """
    Pass 4 — Targeted fix loop.
    Uses Pass 3 scorer output to surgically rewrite only bullets scoring below
    PASS4_THRESHOLD.  Leaves all other bullets verbatim.
    Returns (fixed_experience_section, fix_log_text).
    Falls back to (original, "") if no weak bullets exist or on parse failure.
    """
    if not TARGET_SWAP_PROMPT.exists():
        print(c(YELLOW, "  [!] freeform_targeted_swap.txt not found — skipping Pass 4."))
        return experience_section, ""

    if score_data.get("parse_error"):
        print(c(YELLOW, "  [!] Scorer JSON parse failed — Pass 4 skipped (no bullet scores available)."))
        return experience_section, ""

    bullets = score_data.get("bullets", [])
    weak = [
        b for b in bullets
        if isinstance(b.get("score"), (int, float)) and b["score"] < PASS4_THRESHOLD
    ]

    if not weak:
        print(c(GREEN, f"  \u2713 All bullets \u2265 {PASS4_THRESHOLD} — Pass 4 not needed."))
        return experience_section, ""

    print()
    print(c(BOLD, f"  Pass 4 \u2014 Targeted Fix ({len(weak)} bullet(s) below {PASS4_THRESHOLD})"))
    for b in weak:
        fm_str = f" [{b.get('failure_mode')}]" if b.get("failure_mode") else ""
        print(c(YELLOW, f"    {b.get('company')} #{b.get('index')}: {b.get('score')}{fm_str}"))

    scorer_bullets_text = _format_scorer_bullets(weak, experience_section)

    template = TARGET_SWAP_PROMPT.read_text(encoding="utf-8")
    prompt = (
        template
        .replace("{{EXPERIENCE_SECTION}}", experience_section.strip())
        .replace("{{SCORER_BULLETS}}", scorer_bullets_text)
        .replace("{{JOB_DESCRIPTION}}", jd_text.strip())
        .replace("{{STRATEGY}}",
                 strategy_block.strip() if strategy_block else "No strategy provided.")
    )

    raw = call_api(prompt, model, "Pass 4: Fix")

    # Extract REVISED EXPERIENCE SECTION (now comes FIRST in output)
    # Try multiple header/separator patterns in order of strictness.
    revised = ""
    _PARSE_PATS = [
        r"REVISED EXPERIENCE SECTION\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*?)(?=\n\s*FIX LOG|\Z)",
        r"REVISED EXPERIENCE SECTION\s*\n[^\n]*\n(.*?)(?=\n\s*FIX LOG|\Z)",
        r"REVISED EXPERIENCE SECTION[^\n]*\n(.*?)(?=\n\s*FIX LOG|\Z)",
    ]
    for _pat in _PARSE_PATS:
        _m = re.search(_pat, raw, re.S | re.I)
        if _m:
            _candidate = _m.group(1).strip()
            if len(re.findall(r"^\s*•", _candidate, re.MULTILINE)) >= 5:
                revised = _candidate
                break

    if not revised:
        # Fallback: find the last company-anchored block (GOJEK is always first)
        _company_matches = list(re.finditer(
            r"((?:GOJEK|HEVO|INTUIT|OPTUM)\s*\|[^\n]+\n.*?)(?=\n\s*FIX LOG|\Z)",
            raw, re.S | re.I,
        ))
        if _company_matches:
            revised = _company_matches[-1].group(1).strip()

    # Extract FIX LOG (comes SECOND in output — greedy to end)
    fix_log = ""
    m_log = re.search(r"FIX LOG\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*)", raw, re.S | re.I)
    if not m_log:
        m_log = re.search(r"FIX LOG[^\n]*\n(.*)", raw, re.S | re.I)
    if m_log:
        fix_log = m_log.group(1).strip()

    if not revised:
        print(c(YELLOW, "  [!] Could not parse Pass 4 output — keeping pre-Pass-4 section."))
        return experience_section, ""

    # Strip trailing non-bullet reasoning, then strip markdown artifacts
    _p4_lines = revised.splitlines()
    _p4_last_b = next((i for i in range(len(_p4_lines) - 1, -1, -1)
                       if re.match(r"^\s*•", _p4_lines[i])), None)
    if _p4_last_b is not None:
        revised = "\n".join(_p4_lines[:_p4_last_b + 1]).strip()
    revised = _sanitize_experience_section(revised)

    revised, guard_msgs = _apply_regression_guard(experience_section, revised)
    if guard_msgs:
        print(c(YELLOW, "  [!] Pass 4 regression guard triggered:"))
        for msg in guard_msgs:
            print(c(YELLOW, msg))

    ok_structure, structure_detail = validate_experience_structure(revised)
    if not ok_structure:
        print(c(YELLOW,
                f"  [!] Pass 4 produced invalid company bullet structure "
                f"({structure_detail}) — keeping pre-Pass-4 section."))
        return experience_section, ""

    print(c(GREEN, f"  \u2713 Pass 4 complete — {len(weak)} bullet(s) targeted"))
    return revised, fix_log


# ─────────────────────────────────────────────────────────────────────────────
# Quality Checks (structural — unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def _word_wrap_bullet(text: str, line_chars: int = 100) -> list[str]:
    """
    Simulate docx word-wrap for a bullet at the given line width.
    Uses Times New Roman 10pt, content width 7.5", bullet continuation
    indent = 720 DXA → effective continuation width ≈ 100 chars.
    Returns a list of wrapped line strings.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= line_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [text]


COMPANY_HEADERS = [
    "GOJEK | Senior Software Engineer | Jan 2025 – Jul 2025 | Gurgaon, India",
    "HEVO DATA | Software Engineer 2 | Nov 2023 – Jan 2025 | Bengaluru, India",
    "INTUIT | Software Engineer 2 | Aug 2022 – Oct 2023 | Bengaluru, India",
    "OPTUM | Software Engineer | Jul 2020 – Aug 2022 | Gurgaon, India",
]

_INCIDENT_NUM = re.compile(r"1[,.]?500", re.I)  # unique to the billing-failure story

COMPANY_SLOTS = {"GOJEK": 3, "HEVO DATA": 3, "INTUIT": 3, "OPTUM": 2}
BULLET_RE     = re.compile(r"^[\•\-\*]\s+\S")


def count_bullets_per_company(experience: str) -> dict:
    counts = {}
    current = None
    for line in experience.splitlines():
        stripped = line.strip()
        clean    = stripped.strip("*").strip()
        for company in COMPANY_SLOTS:
            # Require a pipe separator so "GOJEK #1" (from model self-correction
            # headers or FIX LOG references) doesn't reset the bullet count.
            if clean.upper().startswith(company) and "|" in clean:
                current = company
                counts[current] = 0
                break
        if BULLET_RE.match(stripped) and current:
            counts[current] = counts.get(current, 0) + 1
    return counts


def validate_experience_structure(experience: str) -> tuple[bool, str]:
    """Return whether the section still has the required 3/3/3/2 bullet structure."""
    counts = count_bullets_per_company(experience)
    slot_issues = []
    for company, expected in COMPANY_SLOTS.items():
        actual = counts.get(company, 0)
        if actual != expected:
            slot_issues.append(f"{company}: expected {expected}, got {actual}")
    total = sum(counts.values())
    if slot_issues or total != 11:
        detail = f"Total={total}"
        if slot_issues:
            detail += " | " + ", ".join(slot_issues)
        return False, detail
    return True, f"Total={total} | {counts}"


def run_quality_checks(sections: dict, track: str = "pm") -> list[dict]:
    """Run post-generation structural quality checks."""
    exp    = sections["experience_section"]
    checks = []

    # QC-01: All 4 company headers present (verbatim)
    missing = [h for h in COMPANY_HEADERS if h not in exp]
    checks.append({
        "name": "QC-01 Company headers",
        "status": "PASS" if not missing else "FAIL",
        "detail": "All 4 headers present" if not missing else f"Missing: {missing}",
    })

    # QC-02: Bullet counts match slots
    counts      = count_bullets_per_company(exp)
    slot_issues = []
    for company, expected in COMPANY_SLOTS.items():
        actual = counts.get(company, 0)
        if actual != expected:
            slot_issues.append(f"{company}: expected {expected}, got {actual}")
    total = sum(counts.values())
    checks.append({
        "name": "QC-02 Bullet counts",
        "status": "PASS" if not slot_issues and total == 11 else "FAIL",
        "detail": f"Total={total} | {counts}" if not slot_issues
                  else f"Total={total} | Issues: {slot_issues}",
    })

    # QC-03: intuit_incident present (protected story)
    has_incident = False
    for bline in [l.strip() for l in exp.splitlines() if BULLET_RE.match(l.strip())]:
        if _INCIDENT_NUM.search(bline):
            has_incident = True
            break
    checks.append({
        "name": "QC-03 intuit_incident protected",
        "status": "PASS" if has_incident else "FAIL",
        "detail": "Found" if has_incident
                  else "MISSING — bullet mentioning 1,500+ businesses incident not detected",
    })

    # QC-04: Forbidden words (must match Pass 2 forbidden words list)
    _FORBIDDEN_WORDS = [
        "leveraged", "utilized", "spearheaded", "synergies",
        "actionable", "successfully", "effectively", "streamlined",
        "holistic", "various", "multiple",
    ]
    forbidden_words_found = [w for w in _FORBIDDEN_WORDS
                             if re.search(rf"\b{w}\b", exp, re.I)]
    checks.append({
        "name": "QC-04 Forbidden words",
        "status": "FAIL" if forbidden_words_found else "PASS",
        "detail": "Clean" if not forbidden_words_found
                  else f"Forbidden words found: {forbidden_words_found}",
    })

    # QC-05: No opening verb used 3+ times; no two consecutive bullets share the same opener
    bullets     = [re.sub(r"^[\•\-\*]\s*", "", line.strip()).strip()
                   for line in exp.splitlines() if BULLET_RE.match(line.strip())]
    openers     = [b.split()[0].rstrip(",;.").lower() for b in bullets if b]
    verb_counts = {}
    for v in openers:
        verb_counts[v] = verb_counts.get(v, 0) + 1
    triple_verbs = {v: c for v, c in verb_counts.items() if c >= 3}
    consecutive_pairs = [
        f"'{openers[i]}' at bullets {i+1}+{i+2}"
        for i in range(len(openers) - 1)
        if openers[i] == openers[i + 1]
    ]
    qc05_issues = []
    if triple_verbs:
        qc05_issues.append(f"Verbs used 3+ times: {triple_verbs}")
    if consecutive_pairs:
        qc05_issues.append(f"Consecutive same opener: {consecutive_pairs}")
    checks.append({
        "name": "QC-05 Verb diversity",
        "status": "PASS" if not qc05_issues else "WARN",
        "detail": "All verbs ≤2 uses, no consecutive repeats" if not qc05_issues
                  else " | ".join(qc05_issues),
    })

    # QC-06: Experience section present
    checks.append({
        "name": "QC-06 Section 3 extracted",
        "status": "PASS" if exp else "FAIL",
        "detail": f"{len(exp)} chars" if exp else "Section 3 not found in response",
    })

    # QC-07: Skills section present and has required rows (track-dependent)
    skills        = sections.get("skills_section", "")
    skills_issues = []
    if not skills:
        skills_issues.append("SKILLS & INTERESTS block not found")
    else:
        if track == "nonpm":
            # Non-PM resumes use route-specific labels:
            #   Strategy/BizOps:            Domain Expertise:
            #   Research/Intelligence:      Research Focus:
            #   Client-facing/Implementation: Implementation Focus:
            #   Ops/Execution:              Core Competencies:
            # Interests is always present. At least one route opener must exist.
            if "Interests:" not in skills:
                skills_issues.append("Interests: row missing")
            _nonpm_openers = [
                "Domain Expertise:",
                "Operating Focus:",
                "Commercial Focus:",
                "Research Focus:",
                "Workflow & AI Systems:",
                "Implementation Focus:",
                "Core Competencies:",
            ]
            if not any(opener in skills for opener in _nonpm_openers):
                skills_issues.append(
                    "No route opener found — expected one of 'Domain Expertise:', "
                    "'Operating Focus:', 'Commercial Focus:', 'Research Focus:', "
                    "'Workflow & AI Systems:', 'Implementation Focus:', or "
                    "'Core Competencies:'"
                )
            if "Product Focus:" in skills:
                skills_issues.append(
                    "'Product Focus:' row found in nonpm resume — wrong label for this track"
                )
        else:
            # PM track — original checks
            for row in ["Product Focus:", "Tools:", "Interests:"]:
                if row not in skills:
                    skills_issues.append(f"{row} row missing")
            if "Community:" not in skills and "community" not in skills.lower():
                skills_issues.append("Community row missing")
    checks.append({
        "name": "QC-07 Skills section",
        "status": "PASS" if not skills_issues else "FAIL",
        "detail": f"{len(skills.splitlines())} rows" if not skills_issues
                  else f"Issues: {skills_issues}",
    })

    # QC-08: Long bullets (>300 chars ≈ 3+ wrapped lines)
    _LINE_WIDTH     = 100
    _LONG_THRESHOLD = 300
    bullet_texts    = [re.sub(r"^[\u2022\u25cf\-\*●•]\s*", "", line.strip()).strip()
                       for line in exp.splitlines() if BULLET_RE.match(line.strip())]
    long_bullets    = [f"~{len(bt)} chars" for bt in bullet_texts if len(bt) > _LONG_THRESHOLD]
    checks.append({
        "name": "QC-08 Long bullets",
        "status": "WARN" if long_bullets else "PASS",
        "detail": (f"{len(long_bullets)} bullet(s) likely 4+ lines: {long_bullets}"
                   if long_bullets else "All bullets ≤3 estimated lines"),
    })

    # QC-09: Orphan lines — detect bullets whose final wrapped line has ≤ 3 words.
    # Uses actual docx word-wrap simulation (Times New Roman 10pt, 7.0" continuation
    # width ≈ 100 chars) rather than modulo arithmetic, which is unreliable.
    _ORPHAN_MAX_WORDS = 3
    orphan_bullets    = []
    for bt in bullet_texts:
        wrapped   = _word_wrap_bullet(bt, line_chars=100)
        last_line = wrapped[-1] if wrapped else ""
        last_words = last_line.split()
        if len(wrapped) >= 2 and len(last_words) <= _ORPHAN_MAX_WORDS:
            orphan_bullets.append(
                f"last line \u201c{last_line}\u201d ({len(last_words)} word(s))"
            )
    checks.append({
        "name": "QC-09 Orphan lines",
        "status": "WARN" if orphan_bullets else "PASS",
        "detail": (f"{len(orphan_bullets)} bullet(s) have orphan last line: {orphan_bullets}"
                   if orphan_bullets else "No orphan lines detected"),
    })

    # QC-10: Forbidden opener patterns (must match Pass 2 forbidden opener list)
    _FORBIDDEN_OPENERS = [
        r"^led cross-functional",
        r"^led (the |a |an )",        # "Led the migration", "Led a team"
        r"^managed\b",
        r"^partnered with",
        r"^collaborated with",
        r"^supported\b",              # any "Supported X" opener
        r"^worked with",
        r"^coordinated\b",
        r"^drove .+\baligni",         # "Drove X by aligning stakeholders"
    ]
    forbidden_found = []
    for bullet in bullets:
        bl = bullet.lower()
        for pattern in _FORBIDDEN_OPENERS:
            if re.match(pattern, bl):
                forbidden_found.append(bullet[:60])
                break
    checks.append({
        "name": "QC-10 Forbidden opener patterns",
        "status": "WARN" if forbidden_found else "PASS",
        "detail": ("Clean" if not forbidden_found
                   else f"{len(forbidden_found)} bullet(s) use forbidden opener: "
                        f"{[f[:40] for f in forbidden_found]}"),
    })

    # QC-11: No em dashes (—) — explicitly forbidden in Pass 2 output
    has_em_dash = "\u2014" in exp
    checks.append({
        "name": "QC-11 No em dashes",
        "status": "FAIL" if has_em_dash else "PASS",
        "detail": "Clean" if not has_em_dash
                  else "Em dash (\u2014) found — forbidden in all resume output",
    })

    # QC-12: Contrast phrase cap — reframing constructions ("not X but Y",
    # "X rather than Y") may appear AT MOST ONCE across all 11 bullets.
    # Catch both explicit "not...but" AND "rather than" (scorer flags both
    # as FORCED_CONTRAST on a second occurrence).
    _not_but    = re.findall(r'\bnot\b[^.;!?\u2022\n]{0,60}\bbut\b', exp, re.I)
    _rather_than = re.findall(r'\brather than\b', exp, re.I)
    contrast_matches = _not_but + _rather_than
    checks.append({
        "name": "QC-12 Contrast phrase cap (max 1 per section)",
        "status": "FAIL" if len(contrast_matches) > 1 else "PASS",
        "detail": (f"{len(contrast_matches)} contrast phrase(s) ('not\u2026but': {len(_not_but)}, 'rather than': {len(_rather_than)}) — only 1 total allowed"
                   if len(contrast_matches) > 1
                   else f"{len(contrast_matches)} contrast phrase(s) — within cap"),
    })

    # QC-13: Bullet length mix — no one-liners (<90); informational warning for 3-liners
    # (≥200 chars); auto-trim fires only for bullets ≥_AUTO_TRIM_CHARS (260).
    _ONE_LINE_MIN = 90
    one_liners   = [
        f"bullet #{i+1} ({len(bt)} chars)"
        for i, bt in enumerate(bullet_texts)
        if len(bt) < _ONE_LINE_MIN
    ]
    three_liners_all = [bt for bt in bullet_texts if len(bt) >= _THREE_LINE_CHARS]
    over_long_all    = [bt for bt in bullet_texts if len(bt) >= _AUTO_TRIM_CHARS]
    qc13_issues = []
    if one_liners:
        qc13_issues.append(f"One-liner bullet(s) — too thin, expand: {one_liners}")
    if len(three_liners_all) > _MAX_ALLOWED_THREE_LINERS:
        extra = len(three_liners_all) - _MAX_ALLOWED_THREE_LINERS
        trim_note = (f" — auto-trim will run" if len(over_long_all) > _MAX_ALLOWED_AUTO_TRIM
                     else " — informational only (all within 200–259 chars)")
        qc13_issues.append(
            f"{len(three_liners_all)} bullets ≥{_THREE_LINE_CHARS} chars "
            f"({extra} over the ≤{_MAX_ALLOWED_THREE_LINERS} guideline){trim_note}"
        )
    checks.append({
        "name": "QC-13 Bullet length range",
        "status": "WARN" if qc13_issues else "PASS",
        "detail": (f"Mix OK: 0 one-liners, ≤{_MAX_ALLOWED_THREE_LINERS} three-liners"
                   if not qc13_issues else " | ".join(qc13_issues)),
    })

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Output Saving
# ─────────────────────────────────────────────────────────────────────────────
def make_slug(name: str) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return slug[:50]


def save_output(
    sections:      dict,
    checks:        list[dict],
    jd_path:       Path,
    out_dir:       Path,
    model:         str,
    strategy_dict: dict,
    rewrites_log:  str,
    score_data:    dict,
    fix_log:       str = "",
) -> Path:
    """Save full output (all sections + QC + scores) to runs/freeform/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    slug     = make_slug(jd_path.name)
    out_path = out_dir / f"{today}_{slug}.txt"

    lines = []
    lines.append(f"FREEFORM RESUME RUN — {today}")
    lines.append(f"JD: {jd_path}")
    lines.append(f"Model: {model}")
    lines.append("=" * 72)

    # Strategy summary
    if strategy_dict and "parse_error" not in strategy_dict:
        lines.append("")
        lines.append("STRATEGY SUMMARY")
        lines.append("─" * 72)
        for key in ["company", "role_title", "primary_framing_axis",
                    "secondary_framing_axis", "archetype", "tone"]:
            lines.append(f"  {key:<30} {strategy_dict.get(key, '—')}")
        signals = strategy_dict.get("top_signals", [])
        if signals:
            lines.append(f"  {'top_signals':<30} {' | '.join(signals)}")
        narrative = strategy_dict.get("positioning_narrative", "")
        if narrative:
            lines.append(f"\n  Positioning narrative:\n  {narrative}")

    lines.append("")
    lines.append("SECTION 1 — TOP 3 JD SIGNALS")
    lines.append(sections["signals"] or "[not extracted]")

    lines.append("")
    lines.append("SECTION 2 — VARIANT SELECTION NOTES")
    lines.append(sections["selection_notes"] or "[not extracted]")

    lines.append("")
    lines.append("SECTION 0 — PROFESSIONAL SUMMARY (paste-ready)")
    lines.append("-" * 72)
    lines.append(sections.get("summary_section") or "[not extracted — check SECTION 0 in raw output]")

    lines.append("")
    lines.append("SECTION 3 — FULL EXPERIENCE SECTION (paste-ready)")
    lines.append("-" * 72)
    lines.append(sections["experience_section"] or "[not extracted]")

    if sections.get("projects_section"):
        lines.append("")
        lines.append("SECTION 3B — PROJECTS & CONSULTING (paste-ready)")
        lines.append("-" * 72)
        lines.append(sections["projects_section"])

    if sections.get("experience_section_original"):
        lines.append("")
        lines.append("SECTION 3 (PASS 1 — PRE-REWRITE)")
        lines.append("-" * 72)
        lines.append(sections["experience_section_original"])

    lines.append("")
    lines.append("SECTION 4 — SKILLS & INTERESTS (paste-ready)")
    lines.append("-" * 72)
    lines.append(sections["skills_section"] or "[not extracted]")

    lines.append("")
    lines.append("─" * 72)
    lines.append("QUALITY CHECKS")
    lines.append("─" * 72)
    for chk in checks:
        icon = "✓" if chk["status"] == "PASS" else ("⚠" if chk["status"] == "WARN" else "✗")
        lines.append(f"  [{icon}] {chk['name']}: {chk['detail']}")

    if score_data and "holistic_score" in score_data:
        lines.append("")
        lines.append("─" * 72)
        score_label = "RESUME SCORE (Pass 3 + Pass 4 re-score)" if fix_log else "RESUME SCORE (Pass 3)"
        lines.append(score_label)
        lines.append("─" * 72)
        lines.append(f"  Holistic score: {score_data['holistic_score']}/10  |  Verdict: {score_data.get('verdict', '?')}")
        _n_reverted = score_data.get("_regression_reverted", 0)
        if _n_reverted:
            lines.append(f"  * {_n_reverted} bullet(s) reverted by regression guard — "
                         f"per-bullet scores below reflect pre-fix (higher) versions; "
                         f"holistic is the Pass-4 draft score and is conservative")
        lines.append(f"  Strengths:  {score_data.get('strengths', '')}")
        lines.append(f"  Top issue:  {score_data.get('top_issue', '')}")
        lines.append(f"  JD fit:     {score_data.get('jd_fit_note', '')}")
        lines.append(f"  Narrative:  {score_data.get('narrative_note', '')}")
        lines.append("")
        for b in score_data.get("bullets", []):
            fm   = f" [{b.get('failure_mode')}]" if b.get("failure_mode") else ""
            arch = f" ({b.get('archetype_used')})" if b.get("archetype_used") else ""
            lines.append(f"  {b.get('score'):4.1f}  {b.get('company'):<10} #{b.get('index')}{arch}{fm}")
            lines.append(f"       {b.get('note', '')}")

    if rewrites_log:
        lines.append("")
        lines.append("─" * 72)
        lines.append("REWRITES LOG (Pass 2)")
        lines.append("─" * 72)
        lines.append(rewrites_log)

    if fix_log:
        lines.append("")
        lines.append("─" * 72)
        lines.append("FIX LOG (Pass 4)")
        lines.append("─" * 72)
        lines.append(fix_log)

    lines.append("")
    lines.append("─" * 72)
    lines.append("RAW MODEL OUTPUT (Pass 1)")
    lines.append("─" * 72)
    lines.append(sections["raw"])

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────
def print_qc(checks: list[dict]) -> bool:
    print()
    print(c(BOLD, "  Quality Checks:"))
    all_pass = True
    for chk in checks:
        if chk["status"] == "PASS":
            icon = c(GREEN, "✓")
        elif chk["status"] == "WARN":
            icon = c(YELLOW, "⚠")
            all_pass = False
        else:
            icon = c(RED, "✗")
            all_pass = False
        print(f"    [{icon}] {chk['name']}: {chk['detail']}")
    return all_pass


def print_skills(skills: str):
    if not skills:
        print(c(YELLOW, "  [!] Skills & Interests section not found."))
        return
    print()
    print(c(BOLD, "─" * 72))
    print(c(BOLD, "  PASTE-READY SKILLS & INTERESTS"))
    print(c(BOLD, "─" * 72))
    print()
    for line in skills.splitlines():
        print(line)
    print()


def print_experience(exp: str, label: str = "PASTE-READY EXPERIENCE SECTION"):
    if not exp:
        print(c(RED, "  [!] Could not extract experience section."))
        return
    print()
    print(c(BOLD, "─" * 72))
    print(c(BOLD, f"  {label}"))
    print(c(BOLD, "─" * 72))
    print()
    for line in exp.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(co) for co in ["GOJEK", "HEVO", "INTUIT", "OPTUM"]):
            print(c(BOLD, line))
        else:
            print(line)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# DOCX generation helpers (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────
import math as _math

_COMPANY_KEYS   = ["GOJEK", "HEVO DATA", "INTUIT", "OPTUM"]
DOCX_SCRIPT     = BASE_DIR.parent / "resume_docx.js"
NODE_PATH       = str(BASE_DIR.parent / "node_modules")   # resume/node_modules — portable
_CHARS_PER_LINE = 100  # calibrated from resume_docx.js: Times New Roman 10pt,
                       # bullet continuation width = 10080 DXA = 7.0" ≈ 100 chars
                       # (was 95, which was already corrected from the original 125)
_EDU_BULLET_CHARS  = [34, 165, 120, 160]
_EDU_HEADER_LINES  = 4
_LAYOUT_TIERS = [
    dict(line=220, sec_before=320, sec_after=180, margin_bot=720, name="T0"),
    dict(line=215, sec_before=260, sec_after=140, margin_bot=720, name="T1"),
    dict(line=210, sec_before=200, sec_after=100, margin_bot=720, name="T2"),
    dict(line=200, sec_before=140, sec_after=70,  margin_bot=648, name="T3"),
]
_PAGE_H        = 15840
_MARGIN_TOP    = 1080
_LAYOUT_BUFFER = 200


def parse_experience_blocks(exp_text: str) -> list:
    blocks, current_key, current_bullets = [], None, []
    for line in exp_text.splitlines():
        stripped    = line.strip().lstrip("*").strip()
        matched_key = next((k for k in _COMPANY_KEYS if stripped.upper().startswith(k)), None)
        if matched_key:
            if current_key is not None:
                blocks.append({"key": current_key, "bullets": current_bullets})
            current_key, current_bullets = matched_key, []
        elif current_key is not None:
            m = re.match(r'^[\u2022\u25cf\-\*]\s+(.*)', stripped)
            if m:
                current_bullets.append(m.group(1).strip())
    if current_key is not None:
        blocks.append({"key": current_key, "bullets": current_bullets})
    return blocks


def parse_skills_rows(skills_text: str) -> list:
    rows = []
    for line in skills_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in ('\u25cf', '\u2022', '\u25e6', '●', '•', '-', '*'):
            content = re.sub(r'^[\u25cf\u2022\u25e6●•\-\*]\s*', '', stripped).strip()
            if not content:
                continue
            m = re.match(r'^([A-Za-z][^:]{0,40}):\s*(.*)', content)
            if m:
                rows.append({"bold_label": m.group(1).strip(), "text": m.group(2).strip()})
            else:
                rows.append({"bold_label": None, "text": content})
    return rows


def parse_project_rows(projects_text: str) -> list[str]:
    rows = []
    for line in projects_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("PROJECTS & CONSULTING"):
            continue
        m = re.match(r'^[\u2022\u25cf\-\*●•]\s+(.*)', stripped)
        if m:
            rows.append(m.group(1).strip())
    return rows


def _estimate_height(company_blocks: list, skills_rows: list, tier: dict,
                     summary_text: str = "",
                     project_rows: list[str] | None = None) -> tuple[int, int]:
    L, SB, SA, MB = tier['line'], tier['sec_before'], tier['sec_after'], tier['margin_bot']
    available = _PAGE_H - _MARGIN_TOP - MB
    total     = 0
    project_rows = project_rows or []
    total += 320
    total += L + 40
    # Professional summary section (optional — added between contact and EDUCATION)
    if summary_text and summary_text.strip():
        total += SB + L + SA  # section header
        n_sum = max(1, _math.ceil(len(summary_text.strip()) / _CHARS_PER_LINE))
        total += n_sum * L    # body text
    total += SB + L + SA
    total += _EDU_HEADER_LINES * L
    for ch in _EDU_BULLET_CHARS:
        total += max(1, _math.ceil(ch / _CHARS_PER_LINE)) * L
    total += 24
    total += SB + L + SA
    for i, block in enumerate(company_blocks):
        if i > 0:
            total += 24
        total += L
        total += L
        for bullet in block.get('bullets', []):
            n = max(1, _math.ceil(len(bullet) / _CHARS_PER_LINE))
            total += n * L
    if project_rows:
        total += SB + L + SA
        for bullet in project_rows:
            n = max(1, _math.ceil(len(bullet) / _CHARS_PER_LINE))
            total += n * L
    total += SB + L + SA
    for row in skills_rows:
        label    = (row.get('bold_label') or '')
        text     = (row.get('text') or '')
        combined = f"{label}: {text}" if label else text
        n        = max(1, _math.ceil(len(combined) / _CHARS_PER_LINE))
        total += n * L
    return total, available


def _choose_layout_tier(company_blocks: list, skills_rows: list,
                        summary_text: str = "",
                        project_rows: list[str] | None = None) -> tuple[dict, int, int]:
    for tier in _LAYOUT_TIERS:
        est, avail = _estimate_height(company_blocks, skills_rows, tier, summary_text, project_rows)
        if est <= avail - _LAYOUT_BUFFER:
            return tier, est, avail
    # All tiers overflow — use T3 (tightest) and print a clear warning.
    # This usually means 2+ bullets are 300+ chars and should be trimmed.
    last       = _LAYOUT_TIERS[-1]
    est, avail = _estimate_height(company_blocks, skills_rows, last, summary_text, project_rows)
    overage    = est - avail
    print(c(YELLOW,
            f"  [!] PAGE OVERFLOW WARNING: estimated content ({est} twips) exceeds "
            f"page ({avail} twips) by ~{overage} twips even at T3 (tightest tier). "
            f"Resume may spill to page 2. Trim the longest bullet(s)."))
    return last, est, avail


def _estimate_page_fill(
    experience_section: str,
    skills_section: str,
    summary_text: str = "",
    projects_section: str = "",
) -> tuple[float, int, str] | None:
    """
    Quick layout estimate without generating a docx.
    Returns (fill_pct, spare_lines, sparsest_company_key) if parseable, else None.
    Useful for detecting underutilization BEFORE running generate_docx.
    """
    try:
        company_blocks = parse_experience_blocks(experience_section)
        skills_rows    = parse_skills_rows(skills_section)
        project_rows   = parse_project_rows(projects_section)
        if not company_blocks:
            return None
        tier, est_dxa, avail_dxa = _choose_layout_tier(
            company_blocks, skills_rows, summary_text, project_rows
        )
        fill_pct = 100.0 * est_dxa / avail_dxa
        spare_lines = max(0, round((avail_dxa - est_dxa) / tier['line']))
        _sparse = sorted(company_blocks, key=lambda b: sum(len(x) for x in b.get('bullets', [])))
        sparse_company = _sparse[0]['key'] if _sparse else "GOJEK"
        return fill_pct, spare_lines, sparse_company
    except Exception:
        return None


_EXPANSION_PROMPT_TEMPLATE = """\
AKSHAT PATHAK — BULLET EXPANSION PASS
======================================
The formatted resume page has approximately {spare_lines} spare line(s) available.
The company with the shortest average bullet length is {sparse_company}.

Your job: expand the shortest bullet(s) in {sparse_company} (and only those) by
adding one additional line of mechanism detail, earned specificity, or scale context
so the page is better utilised. Do NOT expand bullets that are already 3 lines long.

CURRENT EXPERIENCE SECTION:
{experience_section}

JOB DESCRIPTION:
{jd_text}

STRATEGY:
{strategy_block}

RULES (all mandatory):
- Do NOT change bullet counts (total remains 11).
- Expand at most {spare_lines} bullet(s). Prioritise the shortest bullet(s) first.
- All added content must come from story facts already present in the bullet — no invention.
- Keep expanded bullets at most 3 printed lines (≤230 chars at ~100 chars/line).
- Preserve every other bullet and all company headers verbatim.
- No em dashes. No forbidden words (leveraged, utilized, spearheaded, synergies, etc.).
- No new "not X but Y" contrast phrases — the one allowed contrast phrase, if present,
  stays in whichever bullet already holds it.
- Expanded bullets must still pass the archetype decision chain:
    Diagnostic / Mechanism-first / Impact-first (all with explicit causal chain).

OUTPUT FORMAT (produce exactly these two sections in order):

REVISED EXPERIENCE SECTION
──────────────────────────────────────────────────────────────────────────────
[Complete 11-bullet section. Expanded bullets updated. All other bullets verbatim.
Company headers verbatim. Bullet symbol: •]

EXPANSION LOG
──────────────────────────────────────────────────────────────────────────────
For each expanded bullet (company + index, e.g. "GOJEK #2"):
  ORIGINAL:  [original bullet text]
  EXPANDED:  [new bullet text]
  ADDED:     [one sentence: what content was added and why it earns its place]
"""


def run_expansion_pass(
    experience_section: str,
    skills_section: str,
    jd_text: str,
    strategy_block: str,
    model: str,
    summary_text: str = "",
    projects_section: str = "",
) -> tuple[str, str]:
    """
    Expansion pass — triggered when the page is <85% full after all other passes.
    Expands the shortest bullet(s) in the most-sparse company to fill spare lines.
    Returns (expanded_experience_section, expansion_log_text).
    Falls back to (original, "") on any failure.
    """
    result = _estimate_page_fill(
        experience_section, skills_section, summary_text, projects_section
    )
    if result is None:
        return experience_section, ""
    fill_pct, spare_lines, sparse_company = result
    if fill_pct >= 80.0 or spare_lines < 2:
        return experience_section, ""

    print()
    print(c(BOLD, f"  Expansion Pass — {fill_pct:.0f}% fill, ~{spare_lines} spare lines "
            f"(expanding shortest {sparse_company} bullet(s))"))

    prompt = _EXPANSION_PROMPT_TEMPLATE.format(
        spare_lines=spare_lines,
        sparse_company=sparse_company,
        experience_section=experience_section.strip(),
        jd_text=jd_text.strip(),
        strategy_block=strategy_block.strip() if strategy_block else "No strategy provided.",
    )
    raw = call_api(prompt, model, "Expansion")

    # Parse revised experience section — try multiple separator patterns
    revised = ""
    for _pat in [
        r"REVISED EXPERIENCE SECTION\s*\n[─═\-=\u2500-\u257F]{3,}\n(.*?)(?=\n\s*EXPANSION LOG|\Z)",
        r"REVISED EXPERIENCE SECTION\s*\n[^\n]*\n(.*?)(?=\n\s*EXPANSION LOG|\Z)",
        r"REVISED EXPERIENCE SECTION[^\n]*\n(.*?)(?=\n\s*EXPANSION LOG|\Z)",
    ]:
        _m = re.search(_pat, raw, re.S | re.I)
        if _m:
            _candidate = _m.group(1).strip()
            if len(re.findall(r"^\s*•", _candidate, re.MULTILINE)) >= 5:
                revised = _candidate
                break

    if not revised:
        print(c(YELLOW, "  [!] Could not parse Expansion Pass output — keeping original."))
        return experience_section, ""

    # Basic sanity: must still have 11 bullets
    bullet_count = len(re.findall(r"^\s*•", revised, re.MULTILINE))
    if bullet_count != 11:
        print(c(YELLOW, f"  [!] Expansion Pass produced {bullet_count} bullets (expected 11) "
                "— keeping original."))
        return experience_section, ""

    expansion_log = ""
    m_log = re.search(r"EXPANSION LOG\s*\n[-\u2500]+\n(.*)", raw, re.S | re.I)
    if m_log:
        expansion_log = m_log.group(1).strip()

    # Estimate new fill after expansion
    result2 = _estimate_page_fill(revised, skills_section, summary_text, projects_section)
    if result2:
        new_fill, new_spare, _ = result2
        if new_fill > 105.0:
            print(c(YELLOW, f"  [!] Expansion Pass caused overflow ({new_fill:.0f}%) "
                    "— keeping original."))
            return experience_section, ""
        print(c(GREEN, f"  ✓ Expansion complete: {fill_pct:.0f}% → {new_fill:.0f}% fill"))
    else:
        print(c(GREEN, "  ✓ Expansion Pass applied."))

    return revised, expansion_log


def generate_docx(
    sections:     dict,
    jd_path:      Path,
    out_dir:      Path,
    docx_out_dir: Path | None = None,
    score:        float | None = None,
    track:        str = "pm",
) -> Path | None:
    if not DOCX_SCRIPT.exists():
        print(c(YELLOW, "  [!] resume_docx.js not found — skipping docx generation."))
        return None

    company_blocks = parse_experience_blocks(sections["experience_section"])
    skills_rows    = parse_skills_rows(sections["skills_section"])
    project_rows   = parse_project_rows(sections.get("projects_section", ""))

    if not company_blocks:
        print(c(YELLOW, "  [!] Could not parse company blocks — skipping docx generation."))
        return None

    docx_dir = docx_out_dir if docx_out_dir is not None else out_dir.parent / "docx"
    docx_dir.mkdir(parents=True, exist_ok=True)
    today       = datetime.now().strftime("%Y-%m-%d")
    slug        = make_slug(jd_path.name)
    score_tag   = f"_r{score:.1f}" if score is not None else ""
    output_path = docx_dir / f"{today}_{slug}{score_tag}.docx"

    summary_text = sections.get("summary_section", "")
    tier, est_dxa, avail_dxa = _choose_layout_tier(
        company_blocks, skills_rows, summary_text, project_rows
    )

    # ── Auto-trim: if T3 still overflows, drop the Interests row ─────────────
    # The Interests row is typically ~80 chars and saves ~1 line (~200 DXA at T3).
    # This is a last-resort measure before we give up and print the overflow warning.
    _interests_stripped = False
    if tier['name'] == 'T3' and est_dxa > avail_dxa:
        skills_rows_trimmed = [r for r in skills_rows
                               if not (r.get('bold_label') or '').lower().startswith('interest')]
        if len(skills_rows_trimmed) < len(skills_rows):
            tier2, est2, avail2 = _choose_layout_tier(
                company_blocks, skills_rows_trimmed, summary_text, project_rows
            )
            if est2 <= avail2:
                skills_rows = skills_rows_trimmed
                tier, est_dxa, avail_dxa = tier2, est2, avail2
                _interests_stripped = True
                print(c(YELLOW, "  [i] Page overflow — Interests row auto-stripped to fit."))

    fill_pct  = 100 * est_dxa / avail_dxa
    tier_color = GREEN if tier['name'] == 'T0' else (YELLOW if tier['name'] in ('T1', 'T2') else RED)
    print(c(tier_color, f"  Layout {tier['name']}: est. {est_dxa}/{avail_dxa} DXA "
            f"({fill_pct:.0f}% fill)  line={tier['line']} "
            f"sec={tier['sec_before']}/{tier['sec_after']}"))
    if _interests_stripped:
        print(c(YELLOW, "  [!] Interests omitted from docx — add them back manually if page permits."))

    # ── Underutilization warning ──────────────────────────────────────────────
    # If the page is <85% full at T0, there are 2-3+ spare lines — enough for a
    # meaningful 4th bullet in the most bullet-sparse company block.  Flag it.
    if tier['name'] == 'T0' and fill_pct < 85.0:
        # Find the company with shortest average bullet length (prime candidate for 4th bullet)
        _sparse = sorted(company_blocks, key=lambda b: sum(len(x) for x in b.get('bullets', [])))
        _sparse_name = _sparse[0]['key'] if _sparse else "GOJEK"
        _spare_lines = round((avail_dxa - est_dxa) / tier['line'])
        print(c(YELLOW,
                f"  [i] PAGE UNDERUTILIZED: {fill_pct:.0f}% fill (~{_spare_lines} spare lines). "
                f"Consider a 4th bullet for {_sparse_name} or expanding the shortest bullets "
                f"to carry more mechanism/scale detail."))

    # Track-dependent: the summary section heading differs for PM vs non-PM resumes.
    # PM:    "PRODUCT MANAGEMENT"  (ATS-friendly PM identity signal)
    # NonPM: "PROFILE SUMMARY"     (clearer than bare "PROFILE" while still fitting
    #                               consulting/strategy resume conventions)
    _SUMMARY_HEADERS = {
        "pm":    "PRODUCT MANAGEMENT",
        "nonpm": "PROFILE SUMMARY",
    }
    payload = {
        "company_blocks":         company_blocks,
        "project_rows":           project_rows,
        "skills_rows":            skills_rows,
        "professional_summary":   sections.get("summary_section", ""),
        "summary_section_header": _SUMMARY_HEADERS.get(track, "PROFESSIONAL EXPERIENCE"),
        "output_path":            str(output_path),
        "layout": {
            "line":           tier['line'],
            "section_before": tier['sec_before'],
            "section_after":  tier['sec_after'],
            "margin_bottom":  tier['margin_bot'],
        },
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path = f.name

    try:
        # Resolve node binary — venv PATH often strips /usr/local/bin and
        # /opt/homebrew/bin on macOS.  Try shutil.which first, then known paths.
        import shutil
        node_bin = shutil.which("node")
        if not node_bin:
            for _candidate in [
                "/opt/homebrew/bin/node",   # Homebrew Apple Silicon
                "/usr/local/bin/node",      # Homebrew Intel
                "/usr/bin/node",
            ]:
                if os.path.isfile(_candidate):
                    node_bin = _candidate
                    break
        if not node_bin:
            print(c(RED, "  [✗] node not found — install Node.js or add it to PATH"))
            return None

        env         = os.environ.copy()
        env["NODE_PATH"] = NODE_PATH
        result      = subprocess.run(
            [node_bin, str(DOCX_SCRIPT), tmp_path],
            capture_output=True, text=True, timeout=180, env=env,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0 or stdout.startswith("ERROR:"):
            print(c(RED, f"  [✗] docx generation failed: {stderr or stdout}"))
            return None
        print(c(GREEN, f"  ✓ .docx saved → {output_path}"))
        return output_path
    except subprocess.TimeoutExpired:
        print(c(RED, "  [✗] docx generation timed out."))
        return None
    except Exception as e:
        print(c(RED, f"  [✗] docx generation error: {e}"))
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Core run logic
# ─────────────────────────────────────────────────────────────────────────────
def run_single(
    jd_path:      Path,
    model:        str,
    out_dir:      Path,
    make_docx:    bool        = False,
    run_strategy: bool        = True,
    run_rewrite:  bool        = True,
    run_score:    bool        = True,
    run_fix:      bool        = True,    # Pass 4: targeted fix loop
    pre_strategy: tuple | None = None,   # (strategy_dict, strategy_block) — skips Pass 0
    docx_out_dir: Path  | None = None,   # override docx output dir (default: out_dir.parent/docx)
    track:        str         = "pm",    # "pm" | "nonpm" — selects master prompt + QC rules
) -> bool:
    """Run full pipeline for one JD. Returns True if all structural checks pass."""
    # ── Track setup ───────────────────────────────────────────────────────────
    if track not in VALID_TRACKS:
        print(c(YELLOW, f"  [!] Unknown track '{track}' — defaulting to 'pm'"))
        track = "pm"
    master_prompt_path = NONPM_PROMPT_PATH if track == "nonpm" else PROMPT_PATH

    # Scorer preamble for non-PM track: reminds the scorer that strategy/ops
    # verb openers ('reframed', 'diagnosed', 'synthesized', 'owned a workstream')
    # are correct archetypes for this role family and must not be penalised.
    _NONPM_SCORER_PREAMBLE = """\
ROLE TRACK CONTEXT — NON-PM RESUME (Strategy / Consulting / Ops / PgM):
This resume targets Strategy, Consulting, S&O, PgM, or RevOps roles — NOT PM roles.
Adjust archetype evaluation accordingly:
• "Reframed", "Diagnosed", "Owned a workstream", "Synthesized" are CORRECT
  Strategy/Consulting openers; do NOT flag as WRONG_ARCHETYPE.
• "Generated", "Accelerated", "Established governance", "Delivered against" are
  CORRECT Ops/Execution openers; do NOT flag as WRONG_ARCHETYPE.
• Read the strategy block for "Non-PM subtype" and "Bullet balance" and score
  against that route, not against generic PM instincts.
• Non-PM subtypes matter:
  - strategy-consulting: recommendations, diligence, business cases, executive synthesis
  - bizops-sando: operating cadence, KPI management, planning, internal business decisions
  - commercial-gtm: segmentation, GTM diagnosis, revenue strategy, monetization, ICP work
  - research-intelligence: synthesis, market diagnosis, competitive insight
  - ai-automation: workflow redesign, AI tooling choices, automation operating model
  - client-implementation: rollout, adoption, implementation sequencing,
    translating stakeholder needs into delivered change
  - ops-pgm: governance, milestones, throughput, cross-functional delivery
• Score route identity, not just sentence polish. The clearest 3–4 bullets should
  match the route's expected anchor family:
  - strategy-consulting: G2 / H1 / I2 / O1 (+ H2 or founder proof when present)
  - bizops-sando: G1 / H3 / I2 / I1
  - commercial-gtm: G2 plus O1 / G3 / I1
  - research-intelligence: G2 / G3 / H2 / I1
  - ai-automation: O2 / H2 plus workflow evidence such as L'Oréal proof, G3, or I2
  - client-implementation: H3 / I3 / O1 / G1
  - ops-pgm: G1 / H3 / I2 / I3
• If the route says Commercial, Research, Strategy, or AI-Automation but the
  strongest bullets still read mainly like enterprise engineering delivery,
  score holistic fit down even if the prose is polished.
• If a Projects & Consulting section is provided, treat it as supporting non-
  engineering proof for holistic JD fit and narrative coherence. It may strengthen
  the score modestly when it directly closes a route signal gap, but it does not
  excuse a weak main experience section.
• Penalize generic consulting language when it lacks a named method, operating
  choice, research technique, implementation constraint, or concrete outcome.
• Metric expectations may differ: transformation language ("future-state",
  "operating model") is acceptable only when paired with a visible method or
  decision. Empty strategy filler should still score down.
• Structural penalties to apply at the section level:
  - D_EXCESS: if diagnostic total exceeds route ceiling (Strategy >5, BizOps/others >4,
    Research >6), deduct -0.3 from holistic score.
  - C_MISSING: if context-first total = 0 across all 11 bullets, deduct -0.3.
  - I_MISSING: if impact-first total = 0 across all 11 bullets, deduct -0.3.
  These stack with MONOTONY (-0.5) and ACTION_COUNT_LOW penalties.
• All other scoring criteria (mechanism visibility, attribution accuracy,
  metric placement, no forbidden words, register) apply unchanged.
"""
    _NONPM_REWRITE_PREAMBLE = """\
ROLE TRACK CONTEXT — NON-PM RESUME (Strategy / Research / Client Implementation / Ops):
This is NOT a PM resume rewrite. Preserve the non-PM route signaled in the strategy
block, especially any "Non-PM subtype" and "Bullet balance" fields.
Hard guidance:
• strategy-consulting bullets should sound recommendation-ready, not product-manager-ish.
• bizops-sando bullets should foreground operating cadence, prioritization logic,
  KPI ownership, and business decision quality rather than generic "strategy" filler.
• commercial-gtm bullets should foreground segmentation, GTM diagnosis, funnel or
  monetization logic, and commercial hypothesis quality.
• research-intelligence bullets should foreground synthesis, diagnosis, and named
  research/analysis methods; avoid generic ops language.
• ai-automation bullets should foreground workflow redesign, AI operating choices,
  automation constraints, adoption logic, and human-in-the-loop judgment.
• client-implementation bullets should foreground rollout, adoption,
  sequencing, stakeholder translation, and delivery under real constraints.
• ops-pgm bullets should foreground governance, execution, throughput, and
  ownership; avoid bland consulting abstractions.
• Do NOT flatten everything into generic "strategy / ops / stakeholder" wording.
• Preserve the anchor hierarchy chosen in Pass 1. Let the route-native anchor
  bullets carry the identity; do not inflate supporting bullets into pseudo-
  consulting centerpieces.
• For Strategy / Commercial / Research / AI-Automation routes, do NOT let
  G1 / H1 / H3 / I3 drift into dominant identity bullets unless Pass 1 clearly
  selected them as anchors for the route.
• If Pass 1 selected a support-only variant, preserve its support role. Keep it
  short, concrete, and secondary; do not inflate it into an anchor-style bullet.
• If you change an opener, keep the bullet aligned to the route's intended balance:
  diagnostic-heavy, balanced, or action-heavy as indicated by the strategy block.
• Contrast phrase cap remains in force during rewrite: keep at most ONE contrast
  phrase across the full 11-bullet section. Do NOT introduce a new "not X but Y",
  "rather than X", "X instead of Y", or equivalent construction unless it already
  appears verbatim in the specific Pass 1 bullet being rewritten.
• H1 / H-BATCHSHIFT guard: if the selected Pass 1 H1 bullet is a Non-PM enterprise-
  readiness variant ("Owned a core workstream...", "Shifted Hevo's execution model...",
  or equivalent), do NOT rewrite it into the PM-track "not on features but on
  auditability" language. Preserve the selected Non-PM H1 variant's facts, metrics,
  and framing.
• Short cluster-b bullets are not invitations to embellish. Do NOT add mechanism
  detail that is absent from Pass 1 just to make the bullet sound more specific.
"""
    role_preamble = _NONPM_SCORER_PREAMBLE if track == "nonpm" else ""

    print()
    print(c(BOLD, f"{'─'*72}"))
    print(c(BOLD, f"  JD: {jd_path.name}  [track: {track}]"))
    print(c(BOLD, f"{'─'*72}"))

    if not jd_path.exists():
        print(c(RED, f"  [ERROR] File not found: {jd_path}"))
        return False

    jd_text = jd_path.read_text(encoding="utf-8").strip()
    if not jd_text:
        print(c(RED, f"  [ERROR] JD file is empty: {jd_path}"))
        return False

    # ── Pass 0: Strategy ─────────────────────────────────────────────────────
    strategy_dict  = {}
    strategy_block = ""
    if pre_strategy is not None:
        # Injected from orchestrator — skip API call
        strategy_dict, strategy_block = pre_strategy
        print()
        print(c(BOLD, "  Pass 0 — Strategy (pre-computed, shared)"))
        print_strategy_summary(strategy_dict)
    elif run_strategy:
        print()
        print(c(BOLD, "  Pass 0 — Strategy"))
        strategy_dict, strategy_block = run_strategy_pass(jd_path, jd_text, model)
        print_strategy_summary(strategy_dict)

    # ── Track auto-detection from role_family (post-Pass-0) ──────────────────
    # If the user didn't explicitly pass --track nonpm, check whether the
    # strategy step detected a non-PM role_family and auto-switch the track.
    # This matters most when jobs.py calls run_single() without --track.
    if track == "pm" and strategy_dict:
        _rf = strategy_dict.get("role_family", "")
        _role_title = str(strategy_dict.get("role_title", "") or "")
        _pm_title = _title_implies_pm_track(_role_title, jd_text)
        if _rf and _rf != "pm" and "pm" not in _rf.lower() and not _pm_title:
            # Detected a non-PM role family (e.g. "strategy-consulting",
            # "ops-execution", "consulting", "strategy").
            track = "nonpm"
            master_prompt_path = NONPM_PROMPT_PATH
            role_preamble = _NONPM_SCORER_PREAMBLE
            print(c(YELLOW, f"  [i] Track auto-switched to 'nonpm' "
                            f"(strategy role_family: {_rf!r})"))
        elif _rf and _rf != "pm" and "pm" not in _rf.lower() and _pm_title:
            print(c(YELLOW,
                    f"  [i] Keeping PM track despite strategy role_family={_rf!r} "
                    f"because role title is explicitly PM: {_role_title!r}"))

    # ── Pass 1: Variant selection ─────────────────────────────────────────────
    print()
    print(c(BOLD, "  Pass 1 — Variant Selection"))
    prompt   = load_prompt(jd_text, strategy_block, prompt_path=master_prompt_path)
    response = call_api(prompt, model, "Pass 1: Select")
    sections = extract_sections(response)

    # ── Pass 2: Voice rewrite ─────────────────────────────────────────────────
    rewrites_log = ""
    if run_rewrite and sections["experience_section"]:
        p1_section = sections["experience_section"]
        rewritten, rewrites_log = run_voice_rewrite(
            p1_section, jd_text, strategy_block, model,
            role_preamble=_NONPM_REWRITE_PREAMBLE if track == "nonpm" else "",
        )
        sections["experience_section_original"] = p1_section

        # ── Regression guard: revert any bullet with double-colon or +60-char bloat ─
        rewritten, guard_msgs = _apply_regression_guard(p1_section, rewritten)
        if guard_msgs:
            print()
            print(c(YELLOW, "  [!] Pass 2 regression guard triggered:"))
            for msg in guard_msgs:
                print(c(YELLOW, msg))

        sections["experience_section"] = rewritten

    # ── Post-process: strip forbidden em dashes ───────────────────────────────
    # Em dashes are categorically forbidden in resume output. Strip them here
    # rather than relying solely on model compliance; replaces ' — ' with ': '.
    if sections.get("experience_section"):
        _orig = sections["experience_section"]
        _clean = re.sub(r'\s*\u2014\s*', ': ', _orig)
        if _clean != _orig:
            sections["experience_section"] = _clean
            _em_count = _orig.count("\u2014")
            print(c(YELLOW, f"  [!] {_em_count} em dash(es) auto-stripped from experience section"))

    if sections.get("summary_section"):
        _orig_summary = sections["summary_section"]
        _clean_summary = _sanitize_summary_section(_orig_summary)
        if _clean_summary != _orig_summary:
            sections["summary_section"] = _clean_summary
            _summary_em_count = _orig_summary.count("\u2014")
            print(c(YELLOW,
                    f"  [!] {_summary_em_count} em dash(es) auto-stripped from professional summary"))

    # ── Pass 3: Scoring ──────────────────────────────────────────────────────
    score_data = {}
    if run_score and sections["experience_section"]:
        score_data = run_scorer(sections["experience_section"], jd_text, model,
                                strategy_block, role_preamble=role_preamble,
                                projects_section=sections.get("projects_section", ""))
        print_score(score_data)

    # ── Pass 4: Targeted fix loop (max 2 attempts) ───────────────────────────
    # Runs only when Pass 3 found bullets below PASS4_THRESHOLD; surgically rewrites
    # only those bullets using the scorer's failure_mode + note as directed input.
    # After each attempt, re-scores and checks for remaining weak bullets.
    # Stops early if all bullets reach PASS4_THRESHOLD or no change was made.
    # REGRESSION GUARD: if attempt 2 produces a lower holistic score than attempt 1,
    # we revert to attempt 1's output so the score never goes backward.
    fix_log = ""
    MAX_FIX_ATTEMPTS = 1  # one targeted attempt; regression guard reverts if worse
    if run_fix and run_score and score_data and sections["experience_section"]:
        _pre_pass4_holistic = score_data.get("holistic_score")
        if isinstance(_pre_pass4_holistic, (int, float)) and _pre_pass4_holistic >= PASS4_SKIP_HOLISTIC:
            print(c(GREEN,
                    f"  ✓ Pass 4 skipped — holistic score already "
                    f"{_pre_pass4_holistic:.1f} >= {PASS4_SKIP_HOLISTIC:.1f}"))
        else:
            all_fix_logs: list[str] = []
            # Track the best result across all attempts
            _best_score = score_data.get("holistic_score", 0.0) if score_data else 0.0
            _best_exp   = sections["experience_section"]
            _best_sdata = score_data
            _best_logs: list[str] = []

            # Snapshot pre-Pass-4 bullet texts and scores for per-bullet regression guard
            _pre_fix_bullet_texts:  dict = {}   # {(COMPANY_KEY, index): bullet_text}
            _pre_fix_bullet_scores: dict = {}   # {(COMPANY_KEY, index): score}
            for blk in parse_experience_blocks(sections["experience_section"]):
                for _i, _txt in enumerate(blk["bullets"], start=1):
                    _pre_fix_bullet_texts[(blk["key"], _i)] = _txt
            for _b in score_data.get("bullets", []):
                _ck = next((k for k in _COMPANY_KEYS if k in _b.get("company", "").upper()), "")
                if _ck:
                    _pre_fix_bullet_scores[(_ck, int(_b.get("index", 0)))] = float(
                        _b.get("score", 5.0) or 5.0)

            for fix_attempt in range(1, MAX_FIX_ATTEMPTS + 1):
                fixed_exp, attempt_log = run_targeted_fixes(
                    sections["experience_section"], score_data, jd_text, strategy_block, model,
                )
                if fixed_exp == sections["experience_section"]:
                    break  # no change (all bullets >= threshold or parse failure)
                sections["experience_section"] = fixed_exp
                # Post-process: strip any em dashes Pass 4 may have introduced
                _orig4 = sections["experience_section"]
                _clean4 = re.sub(r'\s*\u2014\s*', ': ', _orig4)
                if _clean4 != _orig4:
                    sections["experience_section"] = _clean4
                    print(c(YELLOW,
                            f"  [!] {_orig4.count(chr(8212))} em dash(es) stripped after Pass 4"))
                if attempt_log:
                    all_fix_logs.append(f"── Attempt {fix_attempt} ──\n{attempt_log}")
                # Re-score to check if more attempts are needed
                print()
                print(c(BOLD, f"  Pass 4 Re-score (attempt {fix_attempt})"))
                score_data = run_scorer(sections["experience_section"], jd_text, model,
                                        strategy_block, role_preamble=role_preamble,
                                        projects_section=sections.get("projects_section", ""))
                print_score(score_data)

                # ── Regression guard ─────────────────────────────────────────────
                _new_score = score_data.get("holistic_score", 0.0) if score_data else 0.0
                if _new_score >= _best_score:
                    # Improvement or equal — keep this as the new best
                    _best_score = _new_score
                    _best_exp   = sections["experience_section"]
                    _best_sdata = score_data
                    _best_logs  = list(all_fix_logs)
                else:
                    # Regression — revert to best-so-far and stop
                    print(c(YELLOW,
                            f"  [!] Pass 4 attempt {fix_attempt} regressed score "
                            f"({_new_score:.1f} < {_best_score:.1f}) "
                            f"— reverting to best attempt and stopping."))
                    sections["experience_section"] = _best_exp
                    score_data                     = _best_sdata
                    all_fix_logs                   = _best_logs
                    break
                # ────────────────────────────────────────────────────────────────

                # ── Per-bullet regression guard ──────────────────────────────────
                # Even when the holistic score held, individual bullets can regress.
                # Compare each bullet's post-fix score to its pre-fix score; revert
                # the text for any bullet that scored LOWER after the fix.
                _revert_set: set = set()
                for _rb in score_data.get("bullets", []):
                    _rck = next((k for k in _COMPANY_KEYS
                                 if k in _rb.get("company", "").upper()), "")
                    _rbkey = (_rck, int(_rb.get("index", 0)))
                    _new_bscore = float(_rb.get("score", 5.0) or 5.0)
                    _old_bscore = _pre_fix_bullet_scores.get(_rbkey, _new_bscore)
                    if _rck and _new_bscore < _old_bscore:
                        _revert_set.add(_rbkey)
                if _revert_set:
                    sections["experience_section"] = _revert_regressed_bullets(
                        sections["experience_section"], _revert_set, _pre_fix_bullet_texts)
                    print(c(YELLOW,
                            f"  [!] Per-bullet regression guard: {len(_revert_set)} bullet(s) "
                            f"reverted (Pass 4 made them worse)"))
                    for _rbkey in sorted(_revert_set):
                        _new_bs = next((float(_rb.get("score", "?")) for _rb in
                                        score_data.get("bullets", [])
                                        if next((k for k in _COMPANY_KEYS if k in
                                                 _rb.get("company","").upper()),"") == _rbkey[0]
                                        and int(_rb.get("index", 0)) == _rbkey[1]), "?")
                        _old_bs = _pre_fix_bullet_scores.get(_rbkey, "?")
                        print(c(YELLOW, f"      {_rbkey[0]} #{_rbkey[1]}: "
                                        f"{_old_bs} → {_new_bs} (reverted to pre-fix text)"))
                    # Patch score_data bullets so:
                    #   (a) still_weak check treats reverted bullets at their correct (pre-fix) score
                    #   (b) score display shows per-bullet scores matching actual resume content
                    # Without this, a reverted bullet's post-fix (lower) score stays in score_data,
                    # making the displayed scores and holistic verdict pessimistic.
                    for _rb in score_data.get("bullets", []):
                        _rck2 = next((k for k in _COMPANY_KEYS
                                      if k in _rb.get("company", "").upper()), "")
                        _rbkey2 = (_rck2, int(_rb.get("index", 0)))
                        if _rbkey2 in _revert_set and _rbkey2 in _pre_fix_bullet_scores:
                            _rb["score"] = _pre_fix_bullet_scores[_rbkey2]
                    score_data["_regression_reverted"] = len(_revert_set)
                # ─────────────────────────────────────────────────────────────────

                # Check if any bullets still below threshold
                still_weak = [
                    b for b in score_data.get("bullets", [])
                    if isinstance(b.get("score"), (int, float)) and b["score"] < PASS4_THRESHOLD
                ]
                if not still_weak:
                    break  # all bullets at threshold — done
                if fix_attempt < MAX_FIX_ATTEMPTS:
                    print(c(YELLOW,
                            f"  [i] {len(still_weak)} bullet(s) still below {PASS4_THRESHOLD} "
                            f"— attempt {fix_attempt + 1} of {MAX_FIX_ATTEMPTS}..."))
            fix_log = "\n\n".join(all_fix_logs)

    # ── Quality checks ────────────────────────────────────────────────────────
    checks = run_quality_checks(sections, track=track)

    # ── QC-03 auto-retry ─────────────────────────────────────────────────────
    # If the intuit_incident bullet was dropped during Pass 2 rewrite, retry
    # Pass 2 with a hard constraint forcing its preservation, then re-check.
    _QC03_CONSTRAINT = (
        "HARD CONSTRAINT (non-negotiable): The Intuit experience section MUST contain "
        "a bullet that mentions '1,500+' businesses or SMBs affected by the billing failure. "
        "Do NOT rephrase away or remove this bullet — preserve its core facts verbatim."
    )
    qc03 = next((ch for ch in checks if ch["name"].startswith("QC-03")), None)
    if run_rewrite and qc03 and qc03["status"] == "FAIL" and sections["experience_section"]:
        print()
        print(c(YELLOW,
                "  [!] QC-03 FAIL — intuit_incident missing. "
                "Retrying Pass 2 with hard constraint..."))
        # Rewrite from the original Pass-1 output, not the already-rewritten text
        p1_original = sections.get("experience_section_original",
                                   sections["experience_section"])
        rewritten2, rewrites_log2 = run_voice_rewrite(
            p1_original, jd_text, strategy_block, model,
            extra_constraint=_QC03_CONSTRAINT,
        )
        if rewritten2 and rewritten2 != p1_original:
            rewritten2, guard_msgs2 = _apply_regression_guard(p1_original, rewritten2)
            if guard_msgs2:
                print(c(YELLOW, "  [!] Pass 2 retry regression guard triggered:"))
                for msg in guard_msgs2:
                    print(c(YELLOW, msg))
            sections["experience_section"] = rewritten2
            rewrites_log = rewrites_log2
            # Re-score so the saved file reflects the retry output
            if run_score:
                score_data = run_scorer(sections["experience_section"], jd_text, model,
                                        strategy_block, role_preamble=role_preamble,
                                        projects_section=sections.get("projects_section", ""))
                print_score(score_data)
            checks = run_quality_checks(sections, track=track)

    all_pass = print_qc(checks)

    # ── QC-13 auto-trim: enforce ≤3 three-liners ─────────────────────────────
    # Runs AFTER all other passes and QC retries so trim does not conflict with
    # content changes from QC-03 retry or Pass 4.  Applies a regression guard:
    # if scorer drops after trim, revert.
    # QC-13 auto-trim: only fires for genuinely over-long bullets (≥_AUTO_TRIM_CHARS),
    # not regular 3-liners (200-259 chars) — those are informational only.
    qc13 = next((ch for ch in checks if ch["name"].startswith("QC-13")), None)
    _qc13_over_long_count = sum(
        1 for line in sections["experience_section"].splitlines()
        if re.match(r"^\s*•", line) and len(line.strip().lstrip("• ")) >= _AUTO_TRIM_CHARS
    )
    if run_score and qc13 and _qc13_over_long_count > _MAX_ALLOWED_AUTO_TRIM:
        _trim_exp, _trim_log = run_length_trim(
            sections["experience_section"], score_data, jd_text, strategy_block, model,
        )
        if _trim_exp != sections["experience_section"]:
            # Re-score to guard against regression
            print()
            print(c(BOLD, "  QC-13 Re-score after trim:"))
            _trim_score_data = run_scorer(_trim_exp, jd_text, model, strategy_block,
                                         role_preamble=role_preamble,
                                         projects_section=sections.get("projects_section", ""))
            print_score(_trim_score_data)
            _old_h = score_data.get("holistic_score", 0.0) if score_data else 0.0
            _new_h = _trim_score_data.get("holistic_score", 0.0) if _trim_score_data else 0.0
            if _new_h >= _old_h:
                sections["experience_section"] = _trim_exp
                score_data = _trim_score_data
                if _trim_log:
                    fix_log = (fix_log + "\n\n" + _trim_log).strip() if fix_log else _trim_log
                checks = run_quality_checks(sections, track=track)
                all_pass = print_qc(checks)
                print(c(GREEN, f"  ✓ QC-13 trim accepted ({_old_h:.1f} → {_new_h:.1f})"))
            else:
                print(c(YELLOW,
                        f"  [!] QC-13 trim regressed score ({_new_h:.1f} < {_old_h:.1f}) "
                        "— reverting to pre-trim section."))

    # ── Save output ──────────────────────────────────────────────────────────
    out_path = save_output(
        sections, checks, jd_path, out_dir, model,
        strategy_dict, rewrites_log, score_data, fix_log,
    )
    print()
    print(c(GREEN if all_pass else YELLOW,
            f"  {'✓' if all_pass else '⚠'} Saved → {out_path}"))

    # ── Print paste-ready sections ───────────────────────────────────────────
    print_experience(sections["experience_section"])
    print_skills(sections["skills_section"])

    # ── Expansion pass (runs only when docx requested + page < 85% full) ──────
    if make_docx:
        _summary = sections.get("summary_section", "")
        _projects = sections.get("projects_section", "")
        _fill_result = _estimate_page_fill(
            sections["experience_section"], sections["skills_section"], _summary, _projects,
        )
        if _fill_result and _fill_result[0] < 85.0:
            _exp_section, _exp_log = run_expansion_pass(
                sections["experience_section"],
                sections["skills_section"],
                jd_text, strategy_block, model,
                summary_text=_summary,
                projects_section=_projects,
            )
            if _exp_section != sections["experience_section"]:
                sections["experience_section"] = _exp_section
                # Append expansion log to saved txt file (best-effort)
                if _exp_log and out_path and out_path.exists():
                    with out_path.open("a", encoding="utf-8") as _f:
                        _f.write(f"\n\n{'═'*72}\n"
                                 f"EXPANSION LOG\n{'─'*72}\n{_exp_log}\n")

    # ── Optionally generate .docx ────────────────────────────────────────────
    if make_docx:
        print()
        print(c(BOLD, "  Generating .docx..."))
        _resume_score = score_data.get("holistic_score") if score_data else None
        generate_docx(sections, jd_path, out_dir, docx_out_dir, score=_resume_score,
                      track=track)

    return all_pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────
def resolve_jd_path(target: str) -> Path:
    p = Path(target)
    if p.exists():
        return p.resolve()
    for f in JDS_DIR.glob("*.txt"):
        if f.stem.lower() == target.lower():
            return f
    matches = [f for f in JDS_DIR.glob("*.txt") if target.lower() in f.stem.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        sys.exit(f"[ERROR] Ambiguous target '{target}' matches: {[m.name for m in matches]}\n"
                 f"       Please be more specific.")
    sys.exit(f"[ERROR] Could not find JD for '{target}'.\n"
             f"       Looked in: {JDS_DIR}\n"
             f"       Available: {[f.name for f in JDS_DIR.glob('*.txt')]}")


def main():
    global USE_COLOR

    parser = argparse.ArgumentParser(
        description="Freeform resume generator — single or batch mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", nargs="?",
                        help="JD file path or company name (omit for --batch)")
    parser.add_argument("--batch",       action="store_true",
                        help="Process all .txt files in jds/ directory")
    parser.add_argument("--model",       default=DEFAULT_MODEL,
                        help=f"Anthropic model (default: {DEFAULT_MODEL})")
    parser.add_argument("--out",         default=str(DEFAULT_OUT),
                        help=f"Output directory (default: {DEFAULT_OUT})")
    parser.add_argument("--docx",        action="store_true",
                        help="Also generate a formatted .docx resume after each run")
    parser.add_argument("--track",       default="pm", choices=list(VALID_TRACKS),
                        help="Resume track: 'pm' (default) or 'nonpm' (Strategy/Consulting/Ops/PgM)")
    parser.add_argument("--no-strategy", action="store_true",
                        help="Skip Pass 0 strategy generation")
    parser.add_argument("--no-rewrite",  action="store_true",
                        help="Skip Pass 2 voice rewrite")
    parser.add_argument("--no-score",    action="store_true",
                        help="Skip Pass 3 scoring")
    parser.add_argument("--no-fix",      action="store_true",
                        help="Skip Pass 4 targeted fix loop (implies no re-score)")
    parser.add_argument("--no-color",    action="store_true",
                        help="Disable ANSI color output")
    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    out_dir      = Path(args.out)
    model        = args.model
    make_docx    = args.docx
    track        = args.track
    run_strategy = not args.no_strategy
    run_rewrite  = not args.no_rewrite
    run_score    = not args.no_score
    run_fix      = not args.no_fix

    passes = []
    passes.append("strategy" if run_strategy else "no-strategy")
    passes.append("rewrite"  if run_rewrite  else "no-rewrite")
    passes.append("score"    if run_score    else "no-score")
    passes.append("fix"      if run_fix      else "no-fix")

    print(c(BOLD + CYAN, "\n  ╔══════════════════════════════════════╗"))
    print(c(BOLD + CYAN,   "  ║   Freeform Resume Generator v2.1    ║"))
    print(c(BOLD + CYAN,   "  ╚══════════════════════════════════════╝"))
    print(f"  Model: {c(CYAN, model)}  |  Track: {c(CYAN, track)}  |  Output: {out_dir}  |  DOCX: {make_docx}")
    print(f"  Passes: {c(CYAN, ' | '.join(passes))}")

    if args.batch:
        jd_files = sorted(JDS_DIR.glob("*.txt"))
        if not jd_files:
            sys.exit(f"[ERROR] No .txt files found in {JDS_DIR}")
        print(f"\n  Batch mode — {len(jd_files)} JD(s) found:")
        for f in jd_files:
            print(f"    • {f.name}")

        results = {}
        for jd_path in jd_files:
            ok = run_single(jd_path, model, out_dir, make_docx,
                            run_strategy, run_rewrite, run_score, run_fix,
                            track=track)
            results[jd_path.name] = "PASS" if ok else "WARN/FAIL"

        print()
        print(c(BOLD, "═" * 72))
        print(c(BOLD, "  BATCH SUMMARY"))
        print(c(BOLD, "═" * 72))
        for name, status in results.items():
            color = GREEN if status == "PASS" else YELLOW
            print(f"    {c(color, status):6}  {name}")
        n_pass = sum(1 for s in results.values() if s == "PASS")
        print()
        print(f"  {c(GREEN, str(n_pass))}/{len(results)} runs passed all structural checks.")

    elif args.target:
        jd_path = resolve_jd_path(args.target)
        run_single(jd_path, model, out_dir, make_docx,
                   run_strategy, run_rewrite, run_score, run_fix,
                   track=track)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
