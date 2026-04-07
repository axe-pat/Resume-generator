"""
shared/strategy.py — Step 0 strategy generator
================================================
Generates an application positioning strategy from a JD + optional intel.
The output JSON is a superset of the former Step 1 CL analysis — it includes
all CL Step 1 fields PLUS positioning fields (target_persona, resume_framing_axis,
first_90_day_bet, positioning_narrative) that drive both the resume and CL pipelines.

Usage:
    from shared.strategy import generate_strategy

    strategy_dict, formatted_block = generate_strategy(
        jd_text   = "...",
        intel_text= "",       # optional
        model     = "claude-sonnet-4-6",
        api_key   = "sk-...",
    )
    # strategy_dict   → full JSON dict (inject as {{STEP1_ANALYSIS}} in CL Step 2)
    # formatted_block → human-readable positioning brief (inject as {{STRATEGY}})
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
import httpx

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
_SHARED_DIR   = Path(__file__).parent               # shared/
_ROOT_DIR     = _SHARED_DIR.parent                  # ResumeGenerator v1/
_PROMPT_PATH  = _SHARED_DIR / "prompts" / "step0_strategy.txt"


# ─────────────────────────────────────────────────────────────────────────────
# API key loader (looks in env, then .env at project root)
# ─────────────────────────────────────────────────────────────────────────────
def _load_api_key_from_root() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = _ROOT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_prompt(jd_text: str, intel_text: str) -> str:
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Strategy prompt not found: {_PROMPT_PATH}")
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    if "{{JOB_DESCRIPTION}}" not in template:
        raise ValueError("step0_strategy.txt missing {{JOB_DESCRIPTION}} placeholder")
    prompt = template.replace("{{JOB_DESCRIPTION}}", jd_text.strip())
    prompt = prompt.replace(
        "{{INTEL}}",
        intel_text.strip() if intel_text else "No additional intel provided.",
    )
    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# JSON parser
# ─────────────────────────────────────────────────────────────────────────────
def _parse_strategy_json(response: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", response).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    m = re.search(r"\{.*\}", cleaned, re.S)
    if not m:
        return {"raw": response, "parse_error": "No JSON found in strategy response"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"raw": response, "parse_error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Formatted block builder — human-readable brief for prompt injection
# ─────────────────────────────────────────────────────────────────────────────
def _format_strategy_block(d: dict) -> str:
    """
    Build a lean positioning block for resume prompt injection (Pass 1 + Pass 2).
    Only includes fields that actually influence variant selection and bullet framing.
    CL pipeline has full JSON via {{STEP1_ANALYSIS}} and doesn't need this to be verbose.
    """
    # Map story IDs (from step0_strategy.txt) to story pool labels (used in freeform_master_v2.txt)
    _STORY_ID_MAP = {
        "gojek_supply":        "G-SUPPLY",
        "gojek_pricing":       "G-PRICING",
        "gojek_latency":       "G-LATENCY",
        "hevo_batch_platform": "H-BATCHSHIFT",
        "hevo_job_monitoring": "H-MONITORING",
        "intuit_billing":      "I-BILLING",
        "intuit_incident":     "I-INCIDENT",
        "optum_provider":      "O-PROVIDER",
        "optum_affordability": "O-AFFORDABILITY",
    }

    lines = []

    # support both old field name and new split fields
    framing  = d.get("primary_framing_axis", d.get("resume_framing_axis", "?"))
    framing2 = d.get("secondary_framing_axis", framing)
    signals  = d.get("top_signals", [])
    gaps     = d.get("gaps", [])
    narrative = d.get("positioning_narrative", "")
    story_recs     = d.get("story_recommendations", [])
    story_reasoning = d.get("story_reasoning", "")
    # role_family: "pm" | "strategy-consulting" | "ops-execution"
    # Emitted by step0_strategy.txt when role_family detection is added.
    # freeform_runner.py reads this to auto-select the resume track when --track
    # is not explicitly passed (future: auto-detect from strategy JSON).
    role_family = d.get("role_family", "")
    nonpm_subtype = d.get("nonpm_subtype", "")
    bullet_balance = d.get("bullet_balance", "")

    lines.append(f"Resume framing (primary):   {framing}")
    if framing2 != framing:
        lines.append(f"Resume framing (secondary): {framing2}")
    if role_family:
        lines.append(f"Role family:                {role_family}")
    if nonpm_subtype:
        lines.append(f"Non-PM subtype:             {nonpm_subtype}")
    if bullet_balance:
        lines.append(f"Bullet balance:             {bullet_balance}")
    if signals:
        lines.append(f"Top JD signals:             {' | '.join(signals)}")
    if gaps:
        lines.append(f"Known gaps:                 {'; '.join(gaps)}")
    if story_recs:
        mapped = [_STORY_ID_MAP.get(s, s) for s in story_recs]
        lines.append(f"Priority stories:           {' > '.join(mapped)}")
        if story_reasoning:
            lines.append(f"Story priority reason:      {story_reasoning}")
    if narrative:
        lines.append("")
        lines.append("Positioning narrative:")
        lines.append(narrative)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def generate_strategy(
    jd_text:    str,
    intel_text: str  = "",
    model:      str  = "claude-sonnet-4-6",
    api_key:    str  = "",
) -> tuple[dict, str]:
    """
    Generate application strategy from JD + optional intel.

    Returns:
        (strategy_dict, formatted_block)

        strategy_dict   — full JSON dict; inject as {{STEP1_ANALYSIS}} in CL Step 2
        formatted_block — human-readable brief; inject as {{STRATEGY}} in
                          freeform_master_v2.txt and step2_cl_generation.txt
    """
    if not api_key:
        api_key = _load_api_key_from_root()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your .env or environment."
        )

    prompt = _build_prompt(jd_text, intel_text)

    client = anthropic.Anthropic(
        api_key=api_key,
        http_client=httpx.Client(verify=False),
    )
    started = time.perf_counter()
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.perf_counter() - started
    print(f"  ✓ Strategy API complete ({elapsed:.1f}s)", flush=True)
    raw = message.content[0].text

    strategy_dict   = _parse_strategy_json(raw)
    formatted_block = _format_strategy_block(strategy_dict)

    return strategy_dict, formatted_block
