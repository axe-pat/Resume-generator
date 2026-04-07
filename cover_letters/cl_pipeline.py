#!/usr/bin/env python3
"""
cl_pipeline.py — End-to-end cover letter generator
====================================================
Usage:
  Single run:  python cl_pipeline.py <jd_file.txt>
               python cl_pipeline.py Stripe          # matches jds/Stripe.txt
  Batch run:   python cl_pipeline.py --batch         # all .txt files in jds/
  Options:
    --no-qc          Skip Step 3 quality check (faster, saves API cost)
    --no-strategy    Skip Step 0 strategy (use legacy Step 1 JD analysis only)
    --model MODEL    Anthropic model (default: claude-sonnet-4-6)
    --out DIR        Output directory (default: runs/)
    --no-color       Disable terminal color output

Intel files:
  Place a file named <JD_name>_intel.txt alongside the JD file in jds/.
  The pipeline auto-detects it and injects it into Step 0 (strategy) and Step 2.
  Example: jds/Stripe.txt + jds/Stripe_intel.txt

Pipeline steps:
  Step 0 (AI)   — JD + intel → strategy JSON (positioning brief) [NEW]
                  Replaces Step 1. Output is a superset of former Step 1 JSON.
  Step 2 (AI)   — Cover letter generation using story bank prompt + strategy
  Step 3 (AI)   — Quality check against 5 recipe principles (optional)
  Output        — runs/YYYY-MM-DD_<slug>.txt + .json audit trail
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
import httpx

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent              # cover_letters/
ROOT_DIR      = BASE_DIR.parent                    # ResumeGenerator v1/
PROMPTS_DIR   = BASE_DIR / "prompts"
JDS_DIR       = BASE_DIR / "jds"
DEFAULT_OUT   = BASE_DIR / "runs"
DEFAULT_MODEL = "claude-sonnet-4-6"

STEP1_PROMPT  = PROMPTS_DIR / "step1_cl_jd_analysis.txt"  # legacy fallback
STEP2_PROMPT  = PROMPTS_DIR / "step2_cl_generation.txt"
STEP3_PROMPT  = PROMPTS_DIR / "step3_cl_qc.txt"

# Make shared/ importable
sys.path.insert(0, str(ROOT_DIR))
from shared.strategy import generate_strategy  # noqa: E402

# ANSI colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

USE_COLOR = True


def c(color, text):
    return f"{color}{text}{RESET}" if USE_COLOR else text


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────
def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = BASE_DIR.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    sys.exit("[ERROR] ANTHROPIC_API_KEY not set. Check .env or environment.")


def call_api(prompt: str, model: str, step_label: str = "", max_tokens: int = 8192) -> str:
    """Call Anthropic API and return response text.

    Retries up to 3 times on rate-limit (429) errors with exponential backoff.
    max_tokens defaults to 8192 — sufficient for verbose scorer/QC JSON output.
    """
    api_key = load_api_key()
    client = anthropic.Anthropic(
        api_key=api_key,
        http_client=httpx.Client(verify=False),
    )
    label = f" [{step_label}]" if step_label else ""
    print(c(CYAN, f"  → Calling {model}{label}..."), flush=True)
    for attempt in range(4):  # 1 initial + 3 retries
        try:
            started = time.perf_counter()
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.perf_counter() - started
            done_label = step_label or "API call"
            print(c(GREEN, f"  ✓ {done_label} complete ({elapsed:.1f}s)"), flush=True)
            return message.content[0].text
        except anthropic.RateLimitError as e:
            if attempt == 3:
                raise
            wait = 20 * (2 ** attempt)   # 20s, 40s, 80s
            print(c(YELLOW,
                    f"  [!] Rate limit hit{label} — waiting {wait}s before retry "
                    f"(attempt {attempt + 1}/3)..."), flush=True)
            time.sleep(wait)
    return ""  # unreachable


# ─────────────────────────────────────────────────────────────────────────────
# Em dash enforcement
# ─────────────────────────────────────────────────────────────────────────────
def _trim_cl_em_dashes(text: str, max_count: int = 0) -> str:
    """Keep the first max_count em dashes; replace any beyond that with '; '.

    The CL allows 0 em dashes — all em dashes are auto-replaced.
    """
    parts = text.split("\u2014")
    if len(parts) <= max_count + 1:   # within cap — nothing to do
        return text
    result = parts[0]
    for i, part in enumerate(parts[1:], 1):
        if i <= max_count:
            result += "\u2014" + part
        else:
            result += "; " + part.lstrip()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Docx generation
# ─────────────────────────────────────────────────────────────────────────────
def _generate_cl_docx(cl_body_raw: str, out_dir: Path, slug: str, company: str,
                      score: float | None = None) -> Path | None:
    """Generate a clean .docx CL. Returns path on success, None on failure.
    Never raises — all errors are caught and printed as WARNs."""
    try:
        # Try direct import first (works when cover_letters/ is on sys.path)
        try:
            from cl_docx import generate_cl_docx as _gen
        except ImportError:
            # Fall back to loading cl_docx.py by file path
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cl_docx",
                Path(__file__).parent / "cl_docx.py",
            )
            if spec is None:
                print(c(YELLOW, "  [!] cl_docx.py not found — skipping .docx generation"))
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _gen = mod.generate_cl_docx

        today     = datetime.now().strftime("%Y-%m-%d")
        score_tag = f"_r{score:.1f}" if score is not None else ""
        docx_path = out_dir / f"{today}_{slug}{score_tag}.docx"
        _gen(cl_body_raw, docx_path, company=company)
        return docx_path

    except ModuleNotFoundError as e:
        print(c(YELLOW, f"  [!] CL docx skipped — missing dependency: {e}"))
        print(c(YELLOW,  "      Install with:  pip install python-docx"))
        return None
    except Exception as e:
        print(c(YELLOW, f"  [!] CL docx generation failed: {e}"))
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading
# ─────────────────────────────────────────────────────────────────────────────
def load_step1_prompt(jd_text: str) -> str:
    if not STEP1_PROMPT.exists():
        sys.exit(f"[ERROR] Prompt not found: {STEP1_PROMPT}")
    template = STEP1_PROMPT.read_text(encoding="utf-8")
    if "[PASTE JD HERE]" not in template:
        sys.exit("[ERROR] step1_cl_jd_analysis.txt missing [PASTE JD HERE] placeholder")
    return template.replace("[PASTE JD HERE]", jd_text.strip())


def load_step2_prompt(
    jd_text:         str,
    step1_json:      str,
    intel_text:      str,
    strategy_block:  str = "",
) -> str:
    if not STEP2_PROMPT.exists():
        sys.exit(f"[ERROR] Prompt not found: {STEP2_PROMPT}")
    template = STEP2_PROMPT.read_text(encoding="utf-8")
    for placeholder in ["{{STEP1_ANALYSIS}}", "{{INTEL}}", "{{JOB_DESCRIPTION}}"]:
        if placeholder not in template:
            sys.exit(f"[ERROR] step2_cl_generation.txt missing {placeholder} placeholder")
    template = template.replace("{{STEP1_ANALYSIS}}", step1_json.strip())
    template = template.replace("{{INTEL}}", intel_text.strip() if intel_text else "No additional intel provided.")
    template = template.replace("{{JOB_DESCRIPTION}}", jd_text.strip())
    if "{{STRATEGY}}" in template:
        template = template.replace(
            "{{STRATEGY}}",
            strategy_block.strip() if strategy_block
            else "No strategy brief available — use STRATEGY ANALYSIS JSON above.",
        )
    return template


def load_step3_prompt(cl_text: str) -> str:
    if not STEP3_PROMPT.exists():
        sys.exit(f"[ERROR] Prompt not found: {STEP3_PROMPT}")
    template = STEP3_PROMPT.read_text(encoding="utf-8")
    if "{{COVER_LETTER}}" not in template:
        sys.exit("[ERROR] step3_cl_qc.txt missing {{COVER_LETTER}} placeholder")
    return template.replace("{{COVER_LETTER}}", cl_text.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────
def parse_step1_json(response: str) -> dict:
    """Extract and parse JSON from Step 1 response. Returns dict."""
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", response).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    # Find JSON object
    m = re.search(r"\{.*\}", cleaned, re.S)
    if not m:
        print(c(YELLOW, "  [!] Could not find JSON in Step 1 response — using raw output"))
        return {"raw": response}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(c(YELLOW, f"  [!] Step 1 JSON parse error: {e}"))
        return {"raw": response, "parse_error": str(e)}


def extract_cl_body(response: str) -> str:
    """
    Extract the paste-ready cover letter body from Step 2 response.
    Strips any <!-- --> research flags from the paste-ready version.
    Returns clean letter + preserves flags in a separate pass.
    """
    # Remove <!-- comment --> flags for the paste-ready version
    clean = re.sub(r"<!--.*?-->", "", response, flags=re.S).strip()
    # Remove leading/trailing blank lines
    clean = "\n".join(line for line in clean.splitlines()).strip()
    return clean


def add_salutation_signoff(cl_body: str, company: str, role_title: str) -> str:
    """
    Prepend 'Dear <Company> <Team>,' and insert 'Sincerely,' before the
    signature (Akshat Pathak line).  No-ops if salutation already present.
    """
    if cl_body.lstrip().lower().startswith("dear "):
        return cl_body   # already has a salutation

    # Derive team from role title
    rt_lower = role_title.lower()
    if any(w in rt_lower for w in ("engineer", "engineering", "developer", "software")):
        team = "Engineering Team"
    elif any(w in rt_lower for w in ("data", "analytics", "insight")):
        team = "Data Team"
    elif any(w in rt_lower for w in ("design", "ux", "ui")):
        team = "Design Team"
    elif any(w in rt_lower for w in ("strategy", "biz dev", "business development")):
        team = "Strategy Team"
    else:
        team = "Product Team"   # default for PM / generalist roles

    company_clean = company.strip() if company.strip() else "Hiring"
    salutation = f"Dear {company_clean} {team},"

    # Find signature line (Akshat Pathak) to insert Sincerely, before it
    lines = cl_body.rstrip().splitlines()
    sig_idx = next(
        (i for i, ln in enumerate(lines) if "akshat pathak" in ln.lower()), None
    )

    if sig_idx is not None:
        before_sig = "\n".join(lines[:sig_idx]).rstrip()
        sig_block  = "\n".join(lines[sig_idx:])
        return f"{salutation}\n\n{before_sig}\n\nSincerely,\n{sig_block}"
    else:
        return f"{salutation}\n\n{cl_body}\n\nSincerely,\nAkshat Pathak"


def extract_research_flags(response: str) -> list[str]:
    """Extract any <!-- --> research flags from the CL response."""
    flags = re.findall(r"<!--(.*?)-->", response, re.S)
    return [f.strip() for f in flags if f.strip()]


def parse_step3_json(response: str) -> dict:
    """Extract and parse JSON from Step 3 QC response."""
    cleaned = re.sub(r"```(?:json)?\s*", "", response).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    m = re.search(r"\{.*\}", cleaned, re.S)
    if not m:
        return {"raw": response, "parse_error": "No JSON found"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"raw": response, "parse_error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Rule-based QC (runs always, no API cost)
# ─────────────────────────────────────────────────────────────────────────────
FORBIDDEN_PHRASES = [
    r"\bexcited to apply\b",
    r"\bpassionate about\b",
    r"\bthrill(ed)? to\b",
    r"\bearger? to\b",
    r"\beager to apply\b",
    r"\bleveraged\b",
    r"\butilized\b",
    r"\bspearheaded\b",
    r"\bsynerg(y|ies)\b",
    r"\bholistic approach\b",
    r"\bactionable\b",
    r"\bsuccessfully\b",
    r"\beffectively\b",
    r"\bstreamlined\b",
    r"\bvarious\b",
    r"\bmultiple\b",
    r"i look forward to hearing from you",
    r"at your earliest convenience",
]

OPENING_CLAIM_PATTERNS = [
    r"^i am ",
    r"^i have always ",
    r"^my name is ",
    r"^as a ",
    r"^with \d+",
]


def run_rule_checks(cl_text: str) -> list[dict]:
    """Rule-based quality checks. Returns list of {name, status, detail}."""
    checks = []
    text_lower = cl_text.lower()
    first_line = cl_text.splitlines()[0].lower().strip() if cl_text else ""

    # RQC-01: No forbidden phrases
    found_forbidden = [p for p in FORBIDDEN_PHRASES if re.search(p, text_lower, re.I)]
    checks.append({
        "name": "RQC-01 No forbidden phrases",
        "status": "FAIL" if found_forbidden else "PASS",
        "detail": f"Found: {found_forbidden}" if found_forbidden else "Clean",
    })

    # RQC-02: Opening doesn't start with claim about self
    opening_issue = next((p for p in OPENING_CLAIM_PATTERNS
                          if re.match(p, first_line, re.I)), None)
    checks.append({
        "name": "RQC-02 Hook doesn't open with self-claim",
        "status": "FAIL" if opening_issue else "PASS",
        "detail": f"Opens with: '{first_line[:60]}...'" if opening_issue else "OK",
    })

    # RQC-03: Word count
    words = len(cl_text.split())
    checks.append({
        "name": "RQC-03 Word count (320–420)",
        "status": "PASS" if 300 <= words <= 450 else "WARN",
        "detail": f"{words} words",
    })

    # RQC-04: Paragraph count (3–4 paragraphs expected)
    paragraphs = [p.strip() for p in re.split(r"\n\n+", cl_text) if p.strip()]
    # Exclude the signature line (short last paragraph)
    body_paras = [p for p in paragraphs if len(p.split()) > 5]
    checks.append({
        "name": "RQC-04 Paragraph count (3–4)",
        "status": "PASS" if 3 <= len(body_paras) <= 5 else "WARN",
        "detail": f"{len(body_paras)} substantive paragraphs",
    })

    # RQC-05: Numbers not fabricated (check for common approximation patterns)
    approx_patterns = [r"approximately \d", r"~\$", r"over \$\d", r"about \d{2,}"]
    approx_found = [p for p in approx_patterns if re.search(p, text_lower)]
    checks.append({
        "name": "RQC-05 No approximated numbers",
        "status": "WARN" if approx_found else "PASS",
        "detail": f"Possible approximations: {approx_found}" if approx_found else "Clean",
    })

    # RQC-06: Closes with signature
    checks.append({
        "name": "RQC-06 Ends with signature",
        "status": "PASS" if "akshat pathak" in text_lower[-200:] else "WARN",
        "detail": "Signature found" if "akshat pathak" in text_lower[-200:] else "No signature detected",
    })

    # RQC-07: Em dash count — 0 permitted (all should have been auto-replaced)
    total_emdashes = cl_text.count("\u2014")
    checks.append({
        "name": "RQC-07 Em dash count (0 per letter)",
        "status": "FAIL" if total_emdashes > 0 else "PASS",
        "detail": f"{total_emdashes} em dash(es) — not permitted in CLs" if total_emdashes > 0
                  else "0 em dash(es) — clean",
    })

    # RQC-08: No markdown artifacts (**, ##, [text](url))
    md_found = bool(re.search(r"\*\*|^#{1,3} |\[.+\]\(.+\)", cl_text, re.M))
    checks.append({
        "name": "RQC-08 No markdown artifacts",
        "status": "FAIL" if md_found else "PASS",
        "detail": "Markdown formatting detected — check output" if md_found else "Clean",
    })

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
def make_slug(name: str) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return slug[:50]


def save_output(
    jd_path: Path,
    step1_data: dict,
    cl_body: str,
    cl_raw: str,
    research_flags: list[str],
    rule_checks: list[dict],
    qc_data: dict | None,
    model: str,
    out_dir: Path,
) -> tuple[Path, Path]:
    """Save .txt (human-readable run) and .json (audit trail). Returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    slug = make_slug(jd_path.name)
    txt_path  = out_dir / f"{today}_{slug}.txt"
    json_path = out_dir / f"{today}_{slug}.json"

    # ── .txt output ────────────────────────────────────────────────────────────
    lines = []
    lines.append(f"COVER LETTER RUN — {today}")
    lines.append(f"JD:    {jd_path}")
    lines.append(f"Model: {model}")
    lines.append("=" * 72)
    lines.append("")

    lines.append("STEP 1 ANALYSIS")
    lines.append("─" * 72)
    lines.append(json.dumps(step1_data, indent=2))
    lines.append("")

    lines.append("COVER LETTER (paste-ready)")
    lines.append("─" * 72)
    lines.append(cl_body)
    lines.append("")

    if research_flags:
        lines.append("RESEARCH FLAGS (from generator)")
        lines.append("─" * 72)
        for flag in research_flags:
            lines.append(f"  ⚑  {flag}")
        lines.append("")

    lines.append("─" * 72)
    lines.append("RULE-BASED CHECKS")
    lines.append("─" * 72)
    for chk in rule_checks:
        icon = "✓" if chk["status"] == "PASS" else ("⚠" if chk["status"] == "WARN" else "✗")
        lines.append(f"  [{icon}] {chk['name']}: {chk['detail']}")
    lines.append("")

    if qc_data:
        lines.append("─" * 72)
        lines.append("AI QUALITY CHECK (Step 3)")
        lines.append("─" * 72)
        lines.append(json.dumps(qc_data, indent=2))
        lines.append("")

    lines.append("─" * 72)
    lines.append("RAW STEP 2 OUTPUT")
    lines.append("─" * 72)
    lines.append(cl_raw)

    txt_path.write_text("\n".join(lines), encoding="utf-8")

    # ── .json audit trail ─────────────────────────────────────────────────────
    audit = {
        "run_date": today,
        "jd_file": str(jd_path),
        "model": model,
        "step1_analysis": step1_data,
        "cover_letter": cl_body,
        "research_flags": research_flags,
        "rule_checks": rule_checks,
        "ai_qc": qc_data,
    }
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    return txt_path, json_path


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────
def print_step1_summary(data: dict):
    print()
    print(c(BOLD, "  Step 1 Analysis:"))
    for key in ["company", "role_title", "archetype", "tone"]:
        val = data.get(key, "—")
        print(f"    {key:<25} {val}")
    signals = data.get("top_signals", [])
    if signals:
        print(f"    {'top_signals':<25} {' | '.join(signals)}")
    hook = data.get("hook_angle", "")
    if hook:
        print(f"    {'hook_angle':<25} {hook[:80]}{'...' if len(hook) > 80 else ''}")
    recs = data.get("story_recommendations", [])
    if recs:
        print(f"    {'story_recs':<25} {', '.join(recs)}")


def print_cl(cl_body: str):
    print()
    print(c(BOLD, "─" * 72))
    print(c(BOLD, "  COVER LETTER (paste-ready)"))
    print(c(BOLD, "─" * 72))
    print()
    for line in cl_body.splitlines():
        print(line)
    print()


def print_flags(flags: list[str]):
    if not flags:
        return
    print()
    print(c(YELLOW, "  Research Flags:"))
    for flag in flags:
        print(c(YELLOW, f"    ⚑  {flag}"))


def print_rule_checks(checks: list[dict]):
    print()
    print(c(BOLD, "  Rule Checks:"))
    for chk in checks:
        if chk["status"] == "PASS":
            icon = c(GREEN, "✓")
        elif chk["status"] == "WARN":
            icon = c(YELLOW, "⚠")
        else:
            icon = c(RED, "✗")
        print(f"    [{icon}] {chk['name']}: {chk['detail']}")


def print_qc_summary(qc_data: dict):
    if not qc_data:
        return
    print()
    score   = qc_data.get("overall_score", "?")
    tier    = qc_data.get("tier", "?")
    verdict = qc_data.get("verdict", "?")
    vcolor  = GREEN if verdict == "SEND" else (YELLOW if verdict == "REVISE" else RED)
    print(c(BOLD, "  AI Quality Check:"))
    print(f"    Score:   {c(BOLD, str(score))}/10")
    print(f"    Tier:    {tier}")
    print(f"    Verdict: {c(vcolor, verdict)}")

    principles = qc_data.get("principles", {})
    if principles:
        print()
        print("  Principles:")
        for pid, pdata in principles.items():
            status = pdata.get("status", "?")
            note   = pdata.get("note", "") or pdata.get("candidate_line", "")
            icon   = c(GREEN, "✓") if status == "PASS" else c(RED, "✗")
            label  = pid.replace("_", " ")
            note_str = f" — {note[:60]}{'...' if len(note) > 60 else ''}" if note else ""
            print(f"    [{icon}] {label}{note_str}")

    improvements = qc_data.get("improvements", [])
    if improvements:
        print()
        print(c(YELLOW, "  Improvements:"))
        for imp in improvements:
            print(c(YELLOW, f"    • {imp}"))


# ─────────────────────────────────────────────────────────────────────────────
# Core run logic
# ─────────────────────────────────────────────────────────────────────────────
def run_single(
    jd_path:         Path,
    model:           str,
    out_dir:         Path,
    run_qc:          bool        = True,
    run_strategy:    bool        = True,
    pre_strategy:    tuple | None = None,   # (step1_data_dict, strategy_block) — skips Step 0
    pre_intel_text:  str   | None = None,   # inject intel text directly (skips file detection)
    make_docx:       bool        = False,   # generate a clean .docx alongside the .txt
) -> bool:
    """Run full CL pipeline for one JD. Returns True if all checks pass."""
    print()
    print(c(BOLD, "─" * 72))
    print(c(BOLD, f"  JD: {jd_path.name}"))
    print(c(BOLD, "─" * 72))

    if not jd_path.exists():
        print(c(RED, f"  [ERROR] File not found: {jd_path}"))
        return False

    jd_text = jd_path.read_text(encoding="utf-8").strip()
    if not jd_text:
        print(c(RED, f"  [ERROR] JD file is empty: {jd_path}"))
        return False

    # Intel — use injected text or auto-detect alongside JD
    intel_text = ""
    if pre_intel_text is not None:
        intel_text = pre_intel_text
        if intel_text:
            print(c(GREEN, "  ✓ Intel injected by orchestrator"))
    else:
        intel_path = jd_path.parent / f"{jd_path.stem}_intel.txt"
        if intel_path.exists():
            intel_text = intel_path.read_text(encoding="utf-8").strip()
            print(c(GREEN, f"  ✓ Intel file found: {intel_path.name}"))
        else:
            print(c(YELLOW, "  [i] No intel file found — generating without additional context"))
            print(c(YELLOW, f"      (Add {intel_path.name} for richer output)"))

    # ── Step 0: Strategy (replaces Step 1) ───────────────────────────────────
    step1_data     = {}
    strategy_block = ""
    if pre_strategy is not None:
        # Injected from orchestrator — skip API call
        step1_data, strategy_block = pre_strategy
        print()
        print(c(BOLD, "  Step 0 — Strategy (pre-computed, shared)"))
        print_step1_summary(step1_data)
    elif run_strategy:
        print()
        print(c(BOLD, "  Step 0 — Strategy Analysis"))
        try:
            api_key = load_api_key()
            step1_data, strategy_block = generate_strategy(
                jd_text=jd_text, intel_text=intel_text, model=model, api_key=api_key,
            )
            print_step1_summary(step1_data)
        except Exception as e:
            print(c(YELLOW, f"  [!] Strategy generation failed: {e}"))
            print(c(YELLOW, "      Falling back to legacy Step 1 JD analysis..."))
            # Legacy fallback
            step1_prompt = load_step1_prompt(jd_text)
            step1_raw    = call_api(step1_prompt, model, "Step 1 (fallback)")
            step1_data   = parse_step1_json(step1_raw)
            print_step1_summary(step1_data)
    else:
        # --no-strategy: run legacy Step 1
        print()
        print(c(BOLD, "  Step 1 — JD Analysis (legacy, strategy skipped)"))
        step1_prompt = load_step1_prompt(jd_text)
        step1_raw    = call_api(step1_prompt, model, "Step 1")
        step1_data   = parse_step1_json(step1_raw)
        print_step1_summary(step1_data)

    # ── Step 2: CL Generation ─────────────────────────────────────────────────
    print()
    print(c(BOLD, "  Step 2 — Cover Letter Generation"))
    step2_prompt = load_step2_prompt(
        jd_text, json.dumps(step1_data, indent=2), intel_text, strategy_block,
    )
    cl_raw        = call_api(step2_prompt, model, "Step 2")
    company_name  = step1_data.get("company", "")
    cl_body_raw   = extract_cl_body(cl_raw)          # clean body, no salutation yet

    # Enforce em dash cap (0 allowed) — all em dashes replaced with '; '
    _em_count_before = cl_body_raw.count("\u2014")
    cl_body_raw = _trim_cl_em_dashes(cl_body_raw, max_count=0)
    _em_trimmed = _em_count_before - cl_body_raw.count("\u2014")
    if _em_trimmed > 0:
        print(c(YELLOW, f"  [!] {_em_trimmed} em dash(es) auto-replaced with '; ' (em dashes not permitted in CLs)"))

    cl_body       = add_salutation_signoff(
        cl_body_raw,
        company    = company_name,
        role_title = step1_data.get("role_title", ""),
    )
    flags         = extract_research_flags(cl_raw)

    print_cl(cl_body)
    print_flags(flags)

    # ── Rule-based checks ─────────────────────────────────────────────────────
    rule_checks = run_rule_checks(cl_body)
    print_rule_checks(rule_checks)

    # ── Step 3: AI QC (optional) ─────────────────────────────────────────────
    qc_data = None
    if run_qc:
        print()
        print(c(BOLD, "  Step 3 — AI Quality Check"))
        step3_prompt = load_step3_prompt(cl_body)
        step3_raw    = call_api(step3_prompt, model, "Step 3")
        qc_data      = parse_step3_json(step3_raw)
        print_qc_summary(qc_data)

    # ── Save outputs ─────────────────────────────────────────────────────────
    txt_path, json_path = save_output(
        jd_path, step1_data, cl_body, cl_raw, flags,
        rule_checks, qc_data, model, out_dir,
    )

    # ── Docx (optional) ───────────────────────────────────────────────────────
    docx_path = None
    if make_docx:
        print()
        print(c(BOLD, "  Generating CL .docx..."))
        slug      = make_slug(jd_path.name)
        _cl_score = qc_data.get("overall_score") if qc_data else None
        docx_path = _generate_cl_docx(cl_body_raw, out_dir, slug, company=company_name,
                                       score=_cl_score)
        if docx_path:
            print(c(GREEN, f"  ✓ CL docx  → {docx_path}"))

    print()

    all_rule_pass = all(c["status"] in ("PASS", "WARN") for c in rule_checks)
    rule_fails    = [c["name"] for c in rule_checks if c["status"] == "FAIL"]
    ai_verdict    = qc_data.get("verdict", "") if qc_data else ""

    if rule_fails:
        print(c(YELLOW, f"  ⚠ Rule check failures: {rule_fails}"))

    summary_color = GREEN if all_rule_pass and ai_verdict != "REJECT" else YELLOW
    print(c(summary_color, f"  ✓ Saved → {txt_path}"))
    print(c(CYAN,          f"       JSON → {json_path}"))

    return all_rule_pass


# ─────────────────────────────────────────────────────────────────────────────
# JD resolution
# ─────────────────────────────────────────────────────────────────────────────
def resolve_jd_path(target: str) -> Path:
    """Resolve a JD target to a Path. Accepts full path or bare company name."""
    p = Path(target)
    if p.exists():
        return p.resolve()

    # Try jds/<target>.txt (case-insensitive)
    for f in JDS_DIR.glob("*.txt"):
        # Skip intel files
        if f.stem.endswith("_intel"):
            continue
        if f.stem.lower() == target.lower():
            return f

    # Partial match
    matches = [f for f in JDS_DIR.glob("*.txt")
               if not f.stem.endswith("_intel") and target.lower() in f.stem.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        sys.exit(
            f"[ERROR] Ambiguous target '{target}' matches: {[m.name for m in matches]}\n"
            f"       Please be more specific."
        )
    available = [f.name for f in JDS_DIR.glob("*.txt") if not f.stem.endswith("_intel")]
    sys.exit(
        f"[ERROR] Could not find JD for '{target}'.\n"
        f"       Looked in: {JDS_DIR}\n"
        f"       Available: {available}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global USE_COLOR

    parser = argparse.ArgumentParser(
        description="Cover letter generator — single or batch mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", nargs="?",
                        help="JD file path or company name (omit for --batch)")
    parser.add_argument("--batch",        action="store_true",
                        help="Process all .txt files in jds/")
    parser.add_argument("--no-qc",        action="store_true",
                        help="Skip Step 3 AI quality check")
    parser.add_argument("--no-strategy",  action="store_true",
                        help="Skip Step 0 strategy; use legacy Step 1 JD analysis")
    parser.add_argument("--model",        default=DEFAULT_MODEL,
                        help=f"Anthropic model (default: {DEFAULT_MODEL})")
    parser.add_argument("--out",          default=str(DEFAULT_OUT),
                        help=f"Output directory (default: {DEFAULT_OUT})")
    parser.add_argument("--no-color",     action="store_true",
                        help="Disable ANSI color output")
    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    out_dir      = Path(args.out)
    model        = args.model
    run_qc       = not args.no_qc
    run_strategy = not args.no_strategy

    print(c(BOLD + CYAN, "\n  ╔══════════════════════════════════════════╗"))
    print(c(BOLD + CYAN,   "  ║   Cover Letter Generator v2.0            ║"))
    print(c(BOLD + CYAN,   "  ╚══════════════════════════════════════════╝"))
    print(f"  Model: {c(CYAN, model)}  |  Output: {out_dir}  |  QC: {run_qc}  |  Strategy: {run_strategy}")

    if args.batch:
        jd_files = sorted(
            f for f in JDS_DIR.glob("*.txt")
            if not f.stem.endswith("_intel")
        )
        if not jd_files:
            sys.exit(f"[ERROR] No JD .txt files found in {JDS_DIR}")
        print(f"\n  Batch mode — {len(jd_files)} JD(s) found:")
        for f in jd_files:
            intel_exists = (f.parent / f"{f.stem}_intel.txt").exists()
            intel_tag    = c(GREEN, " +intel") if intel_exists else ""
            print(f"    • {f.name}{intel_tag}")

        results = {}
        for jd_path in jd_files:
            ok = run_single(jd_path, model, out_dir, run_qc, run_strategy)
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
        print(f"  {c(GREEN, str(n_pass))}/{len(results)} runs passed all rule checks.")

    elif args.target:
        jd_path = resolve_jd_path(args.target)
        run_single(jd_path, model, out_dir, run_qc, run_strategy)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
