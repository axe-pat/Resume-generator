#!/usr/bin/env python3
"""
run_app.py — Unified application orchestrator
==============================================
Runs the full pipeline (strategy → resume → cover letter) for a single
company application.  Strategy is generated once and shared between both
pipelines, saving one API call vs running them independently.

Usage:
  python run_app.py <company>             # reads apps/<company>/jd.txt
  python run_app.py Stripe                # example
  python run_app.py Stripe --resume-only
  python run_app.py Stripe --cl-only
  python run_app.py Stripe --no-docx     # skip .docx generation (default is on)
  python run_app.py Stripe --docx-only   # generate .docx from latest resume_*.txt without AI

Options:
  --resume-only   Run only the resume pipeline
  --cl-only       Run only the cover letter pipeline
  --score-only    Re-score the latest saved resume_*.txt and rename the docx
                  with the score tag (skips all generation; fixes missing scores)
  --docx-only     Read latest resume_*.txt and regenerate only the .docx
                  (no AI calls; useful when a run produced txt but no docx)
  --no-strategy   Skip strategy generation (uses strategy.json if it exists,
                  otherwise runs without strategy)
  --no-rewrite    Skip resume Pass 2 (voice rewrite)
  --no-score      Skip resume Pass 3 (scoring)
  --no-qc         Skip CL Step 3 (AI quality check)
  --no-smart-cost Disable score-aware model/pass downgrades for lower-fit jobs
  --no-docx       Skip formatted .docx generation (default: generate docx)
  --model MODEL   Anthropic model (default: claude-sonnet-4-6)
  --no-color      Disable ANSI color output

App directory layout (apps/<company>/):
  jd.txt                ← you provide: paste the full job description here
  intel.txt             ← you provide (optional): insider context, referral notes
  strategy.json         ← generated: positioning brief (overwritten each run)
  resume_YYYY-MM-DD.txt ← generated: paste-ready experience + skills sections
  resume_YYYY-MM-DD.docx← generated: formatted .docx (default; use --no-docx to skip)
  cl_YYYY-MM-DD.txt     ← generated: paste-ready cover letter
  cl_YYYY-MM-DD.json    ← generated: CL audit trail (step analysis + QC data)
  generation_audit_*.json ← generated: machine-readable cost/quality/run audit

Creating a new app directory:
  mkdir apps/Stripe
  # paste JD into apps/Stripe/jd.txt
  # optionally paste intel into apps/Stripe/intel.txt
  python run_app.py Stripe
"""

import argparse
import io
import json
import os
import re
import sys
import threading
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Thread-local stdout capture  (lets resume + CL run in parallel without
# garbling terminal output — each thread writes to its own buffer, then we
# dump them sequentially after both finish)
# ─────────────────────────────────────────────────────────────────────────────
_orig_stdout  = sys.stdout
_thread_local = threading.local()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class _Tee:
    """Write to two streams simultaneously — real stdout + a plain-text log file."""
    def __init__(self, terminal, logfile):
        self._term    = terminal
        self._logfile = logfile

    def write(self, text):
        self._term.write(text)
        # Strip ANSI codes so the log file is readable without a terminal
        self._logfile.write(_ANSI_RE.sub("", text))

    def flush(self):
        self._term.flush()
        try:
            self._logfile.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self._term, "isatty", lambda: False)()

    def fileno(self):
        return self._term.fileno()


class _ThreadLocalStdout:
    """print() calls in child threads go to a per-thread StringIO buffer."""
    def write(self, text):
        buf = getattr(_thread_local, "capture", None)
        if buf is not None:
            buf.write(text)
        else:
            _orig_stdout.write(text)
    def flush(self):
        _orig_stdout.flush()
    def isatty(self):
        return getattr(_orig_stdout, "isatty", lambda: False)()
    def fileno(self):
        return _orig_stdout.fileno()

sys.stdout = _ThreadLocalStdout()

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent        # ResumeGenerator v1/
APPS_DIR  = ROOT_DIR / "apps"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
FULL_QUALITY_SCORE_THRESHOLD = 7.8
LEAN_MODE_SCORE_THRESHOLD = 7.0
PREMIUM_SCORE_MODEL_THRESHOLD = 8.5

# Make shared/ and both pipeline dirs importable
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "resume" / "freeform"))
sys.path.insert(0, str(ROOT_DIR / "cover_letters"))

# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports (so missing deps don't crash on --help)
# ─────────────────────────────────────────────────────────────────────────────
def _import_pipelines():
    import freeform_runner as resume_pipeline
    import cl_pipeline
    from shared.strategy import generate_strategy
    return resume_pipeline, cl_pipeline, generate_strategy


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ─────────────────────────────────────────────────────────────────────────────
# ANSI colors
# ─────────────────────────────────────────────────────────────────────────────
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
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _extract_fit_score(intel_text: str) -> float | None:
    for raw_line in str(intel_text or "").splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("fit_score="):
            continue
        try:
            return float(line.split("=", 1)[1].strip())
        except ValueError:
            return None
    return None


_NONPM_TITLE_PATTERNS = [
    r"\b(strategy|strategic)\b",
    r"\boperations?\b",
    r"\bbizops\b",
    r"\bbusiness\s+operations?\b",
    r"\bchief\s+of\s+staff\b",
    r"\bmarket\s+insights?\b",
    r"\bconsumer\s+insights?\b",
    r"\bmarketing\s+research\b",
    r"\bcorporate\s+development\b",
    r"\bcommercial\b",
    r"\bgtm\b",
    r"\bimplementation\b",
    r"\bprogram\s+manager\b",
]

_PM_TITLE_PATTERNS = [
    r"\bproduct\s+management\b",
    r"\bproduct\s+manager\b",
    r"\bproduct\s+owner\b",
    r"\btechnical\s+product\b",
    r"\bapm\b",
]


def _read_metadata_role_title(app_dir: Path) -> str:
    metadata_path = app_dir / "metadata.json"
    if not metadata_path.exists():
        return ""
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    for key in ("role_title", "title", "job_title"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _infer_role_track(app_dir: Path, jd_text: str, intel_text: str, requested_track: str) -> dict:
    """Cheap deterministic router used before smart-cost can skip strategy."""
    title = _read_metadata_role_title(app_dir)
    if not title:
        for raw_line in str(intel_text or "").splitlines():
            line = raw_line.strip()
            if line.lower().startswith(("role_title=", "title=")):
                title = line.split("=", 1)[1].strip()
                break
    if not title:
        title = next((line.strip() for line in str(jd_text or "").splitlines() if line.strip()), "")

    haystack = title.lower()
    pm_match = any(re.search(pattern, haystack, re.I) for pattern in _PM_TITLE_PATTERNS)
    nonpm_match = any(re.search(pattern, haystack, re.I) for pattern in _NONPM_TITLE_PATTERNS)

    if requested_track == "nonpm":
        track = "nonpm"
        reason = "--track nonpm"
    elif pm_match:
        track = "pm"
        reason = "title implies PM/product"
    elif nonpm_match:
        track = "nonpm"
        reason = "cheap title router matched non-PM lane"
    else:
        track = requested_track
        reason = "default track"

    return {
        "requested_track": requested_track,
        "effective_track": track,
        "title": title,
        "reason": reason,
        "pm_title_match": pm_match,
        "nonpm_title_match": nonpm_match,
    }


def _choose_cost_policy(
    fit_score: float | None,
    requested_strategy: bool,
    requested_rewrite: bool,
    requested_score: bool,
    requested_fix: bool,
    requested_qc: bool,
    default_model: str,
    smart_cost: bool,
    role_track_hint: str = "pm",
) -> dict:
    keep_strategy_for_track = role_track_hint == "nonpm"
    if not smart_cost or fit_score is None:
        return {
            "tier": "full",
            "reason": "smart cost disabled" if not smart_cost else "fit score unavailable",
            "strategy_model": HAIKU_MODEL if smart_cost else default_model,
            "score_model": default_model,
            "run_strategy": requested_strategy,
            "run_rewrite": requested_rewrite,
            "run_score": requested_score,
            "run_fix": requested_fix and requested_score,
            "run_qc": requested_qc,
            "run_trim": requested_score,
        }

    if fit_score >= FULL_QUALITY_SCORE_THRESHOLD:
        return {
            "tier": "full",
            "reason": f"fit_score {fit_score:.1f} >= {FULL_QUALITY_SCORE_THRESHOLD:.1f}",
            "strategy_model": HAIKU_MODEL,
            "score_model": default_model if fit_score >= PREMIUM_SCORE_MODEL_THRESHOLD else HAIKU_MODEL,
            "run_strategy": requested_strategy,
            "run_rewrite": requested_rewrite,
            "run_score": requested_score,
            "run_fix": requested_fix and requested_score,
            "run_qc": requested_qc,
            "run_trim": requested_score,
        }

    if fit_score >= LEAN_MODE_SCORE_THRESHOLD:
        return {
            "tier": "balanced",
            "reason": (
                f"{LEAN_MODE_SCORE_THRESHOLD:.1f} <= fit_score {fit_score:.1f} "
                f"< {FULL_QUALITY_SCORE_THRESHOLD:.1f}"
            ),
            "strategy_model": HAIKU_MODEL,
            "score_model": HAIKU_MODEL,
            "run_strategy": requested_strategy,
            "run_rewrite": requested_rewrite,
            "run_score": requested_score,
            "run_fix": False,
            "run_qc": False,
            "run_trim": False,
        }

    return {
        "tier": "lean",
        "reason": (
            f"fit_score {fit_score:.1f} < {LEAN_MODE_SCORE_THRESHOLD:.1f}"
            + ("; non-PM route keeps cheap strategy" if keep_strategy_for_track else "")
        ),
        "strategy_model": HAIKU_MODEL,
        "score_model": HAIKU_MODEL,
        "run_strategy": requested_strategy and keep_strategy_for_track,
        "run_rewrite": False,
        "run_score": False,
        "run_fix": False,
        "run_qc": False,
        "run_trim": False,
    }


def _rename_latest(directory: Path, old_stem_fragment: str, new_stem: str, ext: str) -> Path | None:
    """
    Rename the most recently created file matching *old_stem_fragment*.<ext>
    in *directory* to *new_stem*.<ext>.  Returns the new path, or None.
    Preserves a trailing _rN.N score tag from the source filename if present
    (e.g. 2026-03-25_jd_r7.9.docx → resume_2026-03-25_r7.9.docx).
    """
    import re as _re
    candidates = sorted(
        directory.glob(f"*{old_stem_fragment}*{ext}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    # Extract trailing score tag from source filename, if any
    score_tag = ""
    m = _re.search(r'(_r\d+(?:\.\d+)?)$', candidates[0].stem)
    if m:
        score_tag = m.group(1)
    target = directory / f"{new_stem}{score_tag}{ext}"
    candidates[0].rename(target)
    return target


def _rel(path: Path | str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        return str(p.relative_to(ROOT_DIR))
    except Exception:
        return str(p)


def _summarize_resume_output(resume_path: Path | None) -> dict:
    if not resume_path or not resume_path.exists():
        return {}
    text = resume_path.read_text(encoding="utf-8", errors="ignore")
    score_match = re.search(r"Holistic score:\s*([0-9.]+)", text)
    qc_warnings = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("[⚠]") or line.strip().startswith("[✗]")
    ]
    no_change_mentions = len(re.findall(
        r"No (?:substantive )?change|already satisfies|Preserved verbatim|Preserved\.",
        text,
        flags=re.I,
    ))
    rewrite_change_lines = len(re.findall(r"^CHANGE:", text, flags=re.M))
    return {
        "holistic_score": float(score_match.group(1)) if score_match else None,
        "qc_warnings": qc_warnings,
        "qc_warning_count": len(qc_warnings),
        "pass2_change_lines": rewrite_change_lines,
        "pass2_no_change_mentions": no_change_mentions,
    }


def _write_generation_audit(
    *,
    app_dir: Path,
    run_stamp: str,
    company: str,
    fit_score: float | None,
    smart_cost: bool,
    role_router: dict,
    cost_policy: dict,
    requested: dict,
    artifacts: dict,
    strategy_dict: dict,
) -> Path:
    audit_path = app_dir / f"generation_audit_{run_stamp}.json"
    resume_path = Path(artifacts["resume_txt"]) if artifacts.get("resume_txt") else None
    strategy_summary = {
        "company": strategy_dict.get("company"),
        "role_title": strategy_dict.get("role_title"),
        "role_family": strategy_dict.get("role_family"),
        "archetype": strategy_dict.get("archetype"),
        "primary_framing_axis": strategy_dict.get("primary_framing_axis", strategy_dict.get("resume_framing_axis")),
        "secondary_framing_axis": strategy_dict.get("secondary_framing_axis"),
        "top_signals": strategy_dict.get("top_signals", []),
    } if strategy_dict else {}
    payload = {
        "run_stamp": run_stamp,
        "company": company,
        "app_dir": _rel(app_dir),
        "fit_score": fit_score,
        "smart_cost": smart_cost,
        "role_router": role_router,
        "requested": requested,
        "cost_policy": cost_policy,
        "strategy_summary": strategy_summary,
        "artifacts": {key: _rel(value) for key, value in artifacts.items()},
        "resume_summary": _summarize_resume_output(resume_path),
        "follow_ups": [
            "Provider adapter for controlled OpenAI experiments",
            "Story/source-material upgrade: named methods, exact decisions, direct customer/research input, attribution-safe metrics",
        ],
    }
    audit_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return audit_path


def resolve_company(target: str, app_dir_override: str | None = None) -> Path:
    """
    Find the app directory for the given company name.
    Accepts an explicit app-dir override, or exact directory name / case-insensitive
    prefix match under apps/.
    """
    if app_dir_override:
        override = Path(app_dir_override).expanduser()
        if not override.is_absolute():
            override = (ROOT_DIR / override).resolve()
        if override.is_dir():
            return override
        sys.exit(f"[ERROR] --app-dir does not exist or is not a directory: {override}")

    if not APPS_DIR.exists():
        sys.exit(
            f"[ERROR] apps/ directory not found at {APPS_DIR}\n"
            f"       Create it with:  mkdir -p apps/<company>  and add jd.txt"
        )

    # Exact match
    exact = APPS_DIR / target
    if exact.is_dir():
        return exact

    # Case-insensitive
    matches = [d for d in APPS_DIR.iterdir()
               if d.is_dir() and d.name.lower() == target.lower()]
    if len(matches) == 1:
        return matches[0]

    # Partial match
    partial = [d for d in APPS_DIR.iterdir()
               if d.is_dir() and target.lower() in d.name.lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        sys.exit(
            f"[ERROR] Ambiguous company '{target}' — matches: "
            f"{[d.name for d in partial]}\nBe more specific."
        )

    available = [d.name for d in APPS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    sys.exit(
        f"[ERROR] No app directory found for '{target}'.\n"
        f"       Looked in: {APPS_DIR}\n"
        f"       Available: {available or '(none yet)'}\n"
        f"       Create one: mkdir apps/{target} && echo 'paste JD here' > apps/{target}/jd.txt"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resume validation — action-first constraints
# ─────────────────────────────────────────────────────────────────────────────
def _categorize_bullet_opener(text: str) -> str:
    """Categorize a bullet opener as 'diagnostic', 'action', or 'impact'."""
    if not text:
        return "unknown"

    words = text.split()[:3]
    first_word = words[0].lower().rstrip(".,;:")

    # Action verbs: execution, doing, creation
    ACTION_VERBS = {
        "led", "own", "owned", "build", "built", "ship", "shipped", "launch",
        "launched", "drove", "drive", "establish", "established", "unblock",
        "unblocked", "cut", "reduced", "improve", "improved", "accelerate",
        "accelerated", "introduced", "unified", "converted", "prototyped",
        "scaled", "expanded", "defined", "designed", "architected",
    }

    # Impact verbs: metrics first, outcome-driven
    IMPACT_VERBS = {
        "won", "increased", "grew", "enabled", "reduced", "cut", "improved",
        "generated", "recovered", "saved", "eliminated", "raised", "restored",
    }

    # Diagnostic verbs: insight first, discovery
    DIAGNOSTIC_VERBS = {
        "identified", "diagnosed", "discovered", "surfaced", "recognized",
        "synthesized", "linked", "profiled", "reshaped", "translated",
        "reframed", "validated", "caught", "made",
    }

    # Categorize (impact > action > diagnostic when overlap)
    if first_word in IMPACT_VERBS:
        if first_word in ACTION_VERBS and len(words) > 1:
            full_2words = " ".join(words[:2]).lower()
            if any(x in full_2words for x in ["by ", "through "]):
                return "action"
            if re.search(r"[\d]+[%MK$]|[\d]+\s*[MK]", text[:40]):
                return "impact"
        return "impact"

    if first_word in ACTION_VERBS:
        return "action"

    if first_word in DIAGNOSTIC_VERBS:
        return "diagnostic"

    return "unknown"


def _validate_resume_constraints(resume_text: str) -> dict:
    """
    Validate resume against action-first constraints:
    1. Min 4 action/impact-first bullets across all 11
    2. No ≥3 consecutive diagnostic openers per company section
    3. At least one strong ownership verb present

    Returns dict with 'valid', 'issues', and 'stats' keys.
    """
    issues = []
    stats = {
        "total_bullets": 0,
        "action_count": 0,
        "impact_count": 0,
        "diagnostic_count": 0,
        "has_ownership_verb": False,
        "company_sections": {},
    }

    # Extract company sections (pattern: COMPANY | Title | Dates)
    company_pattern = r"^([A-Z][A-Z0-9\s\-]+)\s*\|\s*"

    companies = {}
    current_company = None
    current_bullets = []

    for line in resume_text.split("\n"):
        line_stripped = line.strip()

        if re.match(company_pattern, line_stripped):
            if current_company and current_bullets:
                companies[current_company] = current_bullets
            match = re.match(company_pattern, line_stripped)
            current_company = match.group(1).strip()
            current_bullets = []
        elif line_stripped.startswith("•") and current_company:
            bullet_text = line_stripped[1:].strip()
            current_bullets.append(bullet_text)

    if current_company and current_bullets:
        companies[current_company] = current_bullets

    ownership_verbs = {
        "led", "owned", "own", "built", "shipped", "established",
        "unblocked", "drove", "drive", "restored", "won", "converted",
    }

    for company, bullets in companies.items():
        openers = [b.split()[0].lower().rstrip(".,;:") for b in bullets]
        categories = [_categorize_bullet_opener(b) for b in bullets]

        stats["company_sections"][company] = {
            "count": len(bullets),
            "openers": openers,
            "categories": categories,
            "diagnostic_streak": 0,
        }

        # Count categories
        for cat in categories:
            if cat == "action":
                stats["action_count"] += 1
            elif cat == "impact":
                stats["impact_count"] += 1
            elif cat == "diagnostic":
                stats["diagnostic_count"] += 1

        # Check for ≥3 consecutive diagnostic openers
        max_diagnostic_streak = 0
        current_streak = 0
        for cat in categories:
            if cat == "diagnostic":
                current_streak += 1
                max_diagnostic_streak = max(max_diagnostic_streak, current_streak)
            else:
                current_streak = 0

        stats["company_sections"][company]["diagnostic_streak"] = max_diagnostic_streak

        if max_diagnostic_streak >= 3:
            issues.append(
                f"[MONOTONY] {company}: {max_diagnostic_streak} consecutive diagnostic openers "
                f"({' → '.join(openers)})"
            )

        # Check for ownership verbs
        for opener in openers:
            if opener in ownership_verbs:
                stats["has_ownership_verb"] = True

    stats["total_bullets"] = (
        stats["action_count"] + stats["impact_count"] + stats["diagnostic_count"]
    )

    # Check hard constraints
    action_impact_total = stats["action_count"] + stats["impact_count"]
    if action_impact_total < 4:
        issues.append(
            f"[ACTION-FIRST] {action_impact_total}/11 bullets are action/impact-first "
            f"(target: ≥4). Split: {stats['action_count']} action, {stats['impact_count']} impact, "
            f"{stats['diagnostic_count']} diagnostic."
        )

    if not stats["has_ownership_verb"]:
        issues.append(
            "[OWNERSHIP] No strong ownership verb found. "
            "At least one should appear (Led, Owned, Built, Established, Unblocked, Shipped, Drove)."
        )

    return {"valid": len(issues) == 0, "issues": issues, "stats": stats}


# ─────────────────────────────────────────────────────────────────────────────
# Core orchestration
# ─────────────────────────────────────────────────────────────────────────────
def run_app(
    company:      str,
    model:        str,
    run_resume:   bool = True,
    run_cl:       bool = True,
    run_strategy: bool = True,
    run_rewrite:  bool = True,
    run_score:    bool = True,
    run_qc:       bool = True,
    make_docx:    bool = False,
    track:        str  = "pm",  # "pm" | "nonpm" — resume track selection
    app_dir_override: str | None = None,
    smart_cost:   bool = True,
) -> None:
    app_dir  = resolve_company(company, app_dir_override=app_dir_override)
    jd_path  = app_dir / "jd.txt"
    intel_path = app_dir / "intel.txt"

    if not jd_path.exists():
        sys.exit(
            f"[ERROR] jd.txt not found in {app_dir}\n"
            f"       Create it and paste the full job description inside."
        )

    jd_text    = jd_path.read_text(encoding="utf-8").strip()
    intel_text = intel_path.read_text(encoding="utf-8").strip() if intel_path.exists() else ""
    fit_score  = _extract_fit_score(intel_text)
    role_router = _infer_role_track(app_dir, jd_text, intel_text, track)
    if track == "pm" and role_router["effective_track"] == "nonpm":
        track = "nonpm"

    if not jd_text:
        sys.exit(f"[ERROR] jd.txt is empty in {app_dir}")

    resume_pipeline, cl_pipeline, generate_strategy = _import_pipelines()

    requested_strategy = run_strategy
    requested_rewrite  = run_rewrite
    requested_score    = run_score
    requested_fix      = True
    requested_qc       = run_qc
    cost_policy = _choose_cost_policy(
        fit_score=fit_score,
        requested_strategy=requested_strategy,
        requested_rewrite=requested_rewrite,
        requested_score=requested_score,
        requested_fix=requested_fix,
        requested_qc=requested_qc,
        default_model=model,
        smart_cost=smart_cost,
        role_track_hint=track,
    )
    strategy_model = cost_policy["strategy_model"]
    score_model    = cost_policy["score_model"]
    run_strategy   = cost_policy["run_strategy"]
    run_rewrite    = cost_policy["run_rewrite"]
    run_score      = cost_policy["run_score"]
    run_fix        = cost_policy["run_fix"]
    run_qc         = cost_policy["run_qc"]
    run_trim       = cost_policy["run_trim"]

    today = _today()
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifacts = {
        "resume_txt": None,
        "resume_docx": None,
        "cl_txt": None,
        "cl_json": None,
        "cl_docx": None,
    }
    requested = {
        "strategy": requested_strategy,
        "rewrite": requested_rewrite,
        "score": requested_score,
        "fix": requested_fix,
        "qc": requested_qc,
        "resume": run_resume,
        "cl": run_cl,
        "track": role_router["requested_track"],
    }

    # Banner
    print()
    print(c(BOLD + CYAN, "  ╔══════════════════════════════════════════════════╗"))
    print(c(BOLD + CYAN, f"  ║   run_app  ·  {app_dir.name:<36}║"))
    print(c(BOLD + CYAN,  "  ╚══════════════════════════════════════════════════╝"))
    if intel_text:
        print(c(GREEN,  f"  ✓ Intel found ({len(intel_text)} chars)"))
    else:
        print(c(YELLOW,  "  [i] No intel.txt — running without additional context"))
    if fit_score is not None:
        print(f"  Fit score: {c(CYAN, f'{fit_score:.1f}')}")
    if role_router["effective_track"] != role_router["requested_track"] or role_router["effective_track"] == "nonpm":
        print(f"  Role router: {c(CYAN, role_router['effective_track'])} ({role_router['reason']}: {role_router['title'] or 'no title'})")
    print(f"  Model: {c(CYAN, model)}  |  resume={run_resume}  cl={run_cl}")
    print(f"  Cost policy: {c(CYAN, cost_policy['tier'])} ({cost_policy['reason']})")
    print(f"  Strategy model: {c(CYAN, strategy_model)}  |  Score model: {c(CYAN, score_model)}")
    print(f"  Effective passes: strategy={run_strategy}  rewrite={run_rewrite}  score={run_score}  fix={run_fix}  trim={run_trim}  qc={run_qc}")

    # ── Step 0: Strategy (once, shared) ──────────────────────────────────────
    strategy_dict  = {}
    strategy_block = ""
    pre_strategy   = None

    if run_strategy:
        print()
        print(c(BOLD, "  ═══ Step 0 — Strategy (shared) ═══"))
        try:
            from shared.strategy import generate_strategy as _gen_strat
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                env_path = ROOT_DIR / ".env"
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            strategy_dict, strategy_block = _gen_strat(
                jd_text=jd_text, intel_text=intel_text, model=strategy_model, api_key=key,
            )
            pre_strategy = (strategy_dict, strategy_block)

            # Save strategy.json to app dir
            strategy_path = app_dir / "strategy.json"
            strategy_path.write_text(
                json.dumps(strategy_dict, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(c(GREEN, f"  ✓ Strategy saved → {strategy_path}"))

            # Print brief
            print()
            print(f"    {'company':<24} {strategy_dict.get('company', '?')}")
            print(f"    {'role_title':<24} {strategy_dict.get('role_title', '?')}")
            print(f"    {'archetype':<24} {strategy_dict.get('archetype', '?')}")
            print(f"    {'target_persona':<24} {strategy_dict.get('target_persona', '?')}")
            primary = strategy_dict.get("primary_framing_axis", strategy_dict.get("resume_framing_axis", "?"))
            secondary = strategy_dict.get("secondary_framing_axis", primary)
            print(f"    {'primary_framing_axis':<24} {primary}")
            if secondary != primary:
                print(f"    {'secondary_framing_axis':<24} {secondary}")
            sigs = strategy_dict.get("top_signals", [])
            if sigs:
                print(f"    {'top_signals':<24} {' | '.join(sigs)}")
        except Exception as e:
            print(c(YELLOW, f"  [!] Strategy generation failed: {e}"))
            print(c(YELLOW,  "      Continuing without strategy..."))
            # Try loading cached strategy.json if it exists
            cached = app_dir / "strategy.json"
            if cached.exists():
                try:
                    strategy_dict = json.loads(cached.read_text(encoding="utf-8"))
                    # Rebuild the formatted block via the same helper
                    from shared.strategy import _format_strategy_block
                    strategy_block = _format_strategy_block(strategy_dict)
                    pre_strategy   = (strategy_dict, strategy_block)
                    print(c(YELLOW, f"  [i] Loaded cached strategy from {cached}"))
                except Exception:
                    pass
    else:
        # --no-strategy: try loading cached strategy.json
        cached = app_dir / "strategy.json"
        if cached.exists():
            try:
                strategy_dict = json.loads(cached.read_text(encoding="utf-8"))
                from shared.strategy import _format_strategy_block
                strategy_block = _format_strategy_block(strategy_dict)
                pre_strategy   = (strategy_dict, strategy_block)
                print(c(YELLOW, f"  [i] --no-strategy: using cached {cached.name}"))
            except Exception:
                print(c(YELLOW, "  [i] --no-strategy: no cached strategy.json found"))
        else:
            print(c(YELLOW, "  [i] --no-strategy: no cached strategy.json found"))

    # ── Resume + CL pipelines (parallel when both enabled) ───────────────────
    def _run_resume(buf: "io.StringIO | None") -> None:
        if buf is not None:
            _thread_local.capture = buf
        try:
            print()
            print(c(BOLD, "  ═══ Resume Pipeline ═══"))
            resume_pipeline.run_single(
                jd_path      = jd_path,
                model        = model,
                out_dir      = app_dir,
                make_docx    = make_docx,
                run_strategy = False,
                run_rewrite  = run_rewrite,
                run_score    = run_score,
                run_fix      = run_fix,
                pre_strategy = pre_strategy,
                docx_out_dir = app_dir,
                track        = track,
                score_model  = score_model,
                run_trim     = run_trim,
            )
            txt_renamed = _rename_latest(app_dir, "_jd", f"resume_{today}", ".txt")
            if txt_renamed:
                artifacts["resume_txt"] = str(txt_renamed)
                print(c(GREEN, f"  ✓ Resume text  → {txt_renamed.relative_to(ROOT_DIR)}"))
                # Validate action-first constraints
                resume_content = txt_renamed.read_text(encoding="utf-8")
                validation = _validate_resume_constraints(resume_content)
                print()
                print(c(BOLD, "  ═══ Action-First Validation ═══"))
                print(f"  Total bullets: {validation['stats']['total_bullets']}")
                print(f"  Action: {validation['stats']['action_count']} | Impact: {validation['stats']['impact_count']} | Diagnostic: {validation['stats']['diagnostic_count']}")
                print(f"  Ownership verb present: {c(GREEN if validation['stats']['has_ownership_verb'] else YELLOW, str(validation['stats']['has_ownership_verb']))}")
                if validation['issues']:
                    for issue in validation['issues']:
                        print(f"  {c(YELLOW, '⚠')}  {issue}")
                else:
                    print(c(GREEN, "  ✓ All constraints satisfied"))
            if make_docx:
                docx_renamed = _rename_latest(app_dir, "_jd", f"resume_{today}", ".docx")
                if docx_renamed:
                    artifacts["resume_docx"] = str(docx_renamed)
                    print(c(GREEN, f"  ✓ Resume docx  → {docx_renamed.relative_to(ROOT_DIR)}"))
        finally:
            if buf is not None:
                _thread_local.capture = None

    def _run_cl(buf: "io.StringIO | None") -> None:
        if buf is not None:
            _thread_local.capture = buf
        try:
            print()
            print(c(BOLD, "  ═══ Cover Letter Pipeline ═══"))
            cl_pipeline.run_single(
                jd_path        = jd_path,
                model          = model,
                out_dir        = app_dir,
                run_qc         = run_qc,
                run_strategy   = False,
                pre_strategy   = pre_strategy,
                pre_intel_text = intel_text,
                make_docx      = make_docx,
            )
            cl_txt  = _rename_latest(app_dir, "_jd", f"cl_{today}", ".txt")
            cl_json = _rename_latest(app_dir, "_jd", f"cl_{today}", ".json")
            cl_docx = _rename_latest(app_dir, "_jd", f"cl_{today}", ".docx") if make_docx else None
            if cl_txt:
                artifacts["cl_txt"] = str(cl_txt)
                print(c(GREEN, f"  ✓ Cover letter → {cl_txt.relative_to(ROOT_DIR)}"))
            if cl_json:
                artifacts["cl_json"] = str(cl_json)
                print(c(CYAN,  f"       JSON audit → {cl_json.relative_to(ROOT_DIR)}"))
            if cl_docx:
                artifacts["cl_docx"] = str(cl_docx)
                print(c(GREEN, f"  ✓ CL docx      → {cl_docx.relative_to(ROOT_DIR)}"))
        finally:
            if buf is not None:
                _thread_local.capture = None

    sequential_mode = _env_flag("RUN_APP_SEQUENTIAL", default=False)
    if run_resume and run_cl:
        if sequential_mode:
            print(c(YELLOW, "  [i] RUN_APP_SEQUENTIAL=1 — running resume then CL for stability"))
            _run_resume(None)
            _run_cl(None)
        else:
            # Run both pipelines in parallel — saves ~1–1.5 min per app
            resume_buf = io.StringIO()
            cl_buf     = io.StringIO()
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_resume = ex.submit(_run_resume, resume_buf)
                f_cl     = ex.submit(_run_cl,     cl_buf)
                exc_r = f_resume.exception()
                exc_c = f_cl.exception()
            # Dump outputs sequentially: resume first, then CL
            _orig_stdout.write(resume_buf.getvalue())
            _orig_stdout.write(cl_buf.getvalue())
            if exc_r:
                raise exc_r
            if exc_c:
                raise exc_c
    elif run_resume:
        _run_resume(None)   # no buffer — output goes straight to stdout
    elif run_cl:
        _run_cl(None)

    audit_path = _write_generation_audit(
        app_dir=app_dir,
        run_stamp=run_stamp,
        company=company,
        fit_score=fit_score,
        smart_cost=smart_cost,
        role_router=role_router,
        cost_policy=cost_policy,
        requested=requested,
        artifacts=artifacts,
        strategy_dict=strategy_dict,
    )
    print(c(CYAN, f"  ✓ Generation audit → {audit_path.relative_to(ROOT_DIR)}"))

    # ── Final summary ─────────────────────────────────────────────────────────
    print()
    print(c(BOLD, "═" * 72))
    print(c(BOLD, f"  APP COMPLETE — {app_dir.name}"))
    print(c(BOLD, "═" * 72))
    outputs = sorted(app_dir.glob("*.txt")) + sorted(app_dir.glob("*.docx")) + \
              sorted(app_dir.glob("*.json"))
    if outputs:
        print()
        print("  Files in app dir:")
        for f in sorted(outputs, key=lambda p: p.stat().st_mtime, reverse=True):
            size_kb = f.stat().st_size / 1024
            print(f"    {f.name:<45} {size_kb:5.1f} KB")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# --score-only helper
# ─────────────────────────────────────────────────────────────────────────────
def score_only_app(company: str, model: str, track: str = "pm") -> None:
    """
    Read the latest resume_*.txt, extract the experience + skills sections,
    run the scorer, apply Pass 4 if weak bullets are found, then regenerate
    the docx with the final score tag.

    Useful when a previous run produced a good resume but the scorer failed
    (JSON parse error / rate limit) so the docx has no _rN.N tag, OR when
    you want to re-score + fix an existing resume without re-running Pass 1-2.
    """
    app_dir = resolve_company(company)
    jd_path = app_dir / "jd.txt"

    if not jd_path.exists():
        sys.exit(f"[ERROR] jd.txt not found in {app_dir}")

    # ── Find latest resume txt ────────────────────────────────────────────────
    txt_files = sorted(app_dir.glob("resume_*.txt"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    if not txt_files:
        sys.exit(f"[ERROR] No resume_*.txt found in {app_dir}. Run the full pipeline first.")
    txt_path = txt_files[0]

    content = txt_path.read_text(encoding="utf-8")

    m_summary = re.search(
        r"SECTION 0 — (?:PROFESSIONAL SUMMARY|PROFILE) \(paste-ready\)\n[-─]+\n(.*?)"
        r"(?=\nSECTION 3|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    summary_section = m_summary.group(1).strip() if m_summary else ""

    # ── Extract experience section from SECTION 3 ─────────────────────────────
    m_exp = re.search(
        r"SECTION 3 — FULL EXPERIENCE SECTION \(paste-ready[^)]*\)\n[-─]+\n(.*?)"
        r"(?=\nSECTION 3B|\nSECTION 3 \(PASS 1|\nSECTION 4|\Z)",
        content, re.DOTALL,
    )
    if not m_exp:
        sys.exit(f"[ERROR] Could not extract experience section from {txt_path.name}.\n"
                 "       Make sure this is a freeform_runner output file.")
    experience_section = m_exp.group(1).strip()

    m_projects = re.search(
        r"SECTION 3B — PROJECTS & CONSULTING \(paste-ready\)\n[-─]+\n(PROJECTS & CONSULTING.*?)"
        r"(?=\nSECTION 4|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    projects_section = m_projects.group(1).strip() if m_projects else ""

    # ── Extract skills section from SECTION 4 ────────────────────────────────
    m_skills = re.search(
        r"SECTION 4 — SKILLS & INTERESTS \(paste-ready\)\n[-─]+\n(SKILLS & INTERESTS.*?)"
        r"(?=\n(?:SECTION \d|QUALITY CHECKS|QC CHECKS|REWRITES LOG|PASS 4|[─═]{10})|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    skills_section = m_skills.group(1).strip() if m_skills else ""

    # ── Load JD and strategy ──────────────────────────────────────────────────
    jd_text = jd_path.read_text(encoding="utf-8").strip()
    strategy_block = ""
    cached = app_dir / "strategy.json"
    if cached.exists():
        try:
            from shared.strategy import _format_strategy_block
            strategy_block = _format_strategy_block(json.loads(cached.read_text(encoding="utf-8")))
        except Exception:
            pass

    # ── Import pipeline helpers ───────────────────────────────────────────────
    print()
    print(c(BOLD + CYAN, "  ╔══════════════════════════════════════════════════╗"))
    print(c(BOLD + CYAN, f"  ║   score-only  ·  {app_dir.name:<34}║"))
    print(c(BOLD + CYAN,  "  ╚══════════════════════════════════════════════════╝"))
    print(c(CYAN, f"  Scoring: {txt_path.name}"))
    print()

    score_data = _fr.run_scorer(experience_section, jd_text, model, strategy_block)
    _fr.print_score(score_data)

    if not score_data or score_data.get("parse_error") or "holistic_score" not in score_data:
        print(c(YELLOW, "  [!] Scorer did not return a valid score — aborting."))
        return

    # ── Pass 4: apply targeted fixes if weak bullets found ───────────────────
    MAX_FIX_ATTEMPTS = 2
    PASS4_THRESHOLD  = 8.0
    weak = [b for b in score_data.get("bullets", [])
            if isinstance(b.get("score"), (int, float)) and b["score"] < PASS4_THRESHOLD]

    if weak:
        print()
        _best_score = score_data.get("holistic_score", 0.0)
        _best_exp   = experience_section
        _best_sdata = score_data
        for fix_attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            fixed_exp, _ = _fr.run_targeted_fixes(
                experience_section, score_data, jd_text, strategy_block, model,
            )
            if fixed_exp == experience_section:
                break
            experience_section = fixed_exp
            print()
            print(c("\033[1m", f"  Pass 4 Re-score (attempt {fix_attempt})"))
            score_data = _fr.run_scorer(experience_section, jd_text, model, strategy_block)
            _fr.print_score(score_data)
            _new_score = score_data.get("holistic_score", 0.0) if score_data else 0.0
            if _new_score >= _best_score:
                _best_score = _new_score
                _best_exp   = experience_section
                _best_sdata = score_data
            else:
                print(c("\033[33m",
                        f"  [!] Pass 4 attempt {fix_attempt} regressed "
                        f"({_new_score:.1f} < {_best_score:.1f}) — reverting."))
                experience_section = _best_exp
                score_data         = _best_sdata
                break
            still_weak = [b for b in score_data.get("bullets", [])
                          if isinstance(b.get("score"), (int, float)) and b["score"] < PASS4_THRESHOLD]
            if not still_weak:
                break

    # ── QC-13 auto-trim (after all Pass 4 attempts) ──────────────────────────
    _qc13_three_liner_count = sum(
        1 for line in experience_section.splitlines()
        if re.match(r"^\s*•", line)
        and len(line.strip().lstrip("• ")) >= _fr._THREE_LINE_CHARS
    )
    if score_data and _qc13_three_liner_count > _fr._MAX_ALLOWED_THREE_LINERS:
        _trim_exp, _ = _fr.run_length_trim(
            experience_section, score_data, jd_text, strategy_block, model,
        )
        if _trim_exp != experience_section:
            print()
            print(c("\033[1m", "  QC-13 Re-score after trim:"))
            _trim_sd = _fr.run_scorer(_trim_exp, jd_text, model, strategy_block)
            _fr.print_score(_trim_sd)
            _old_h = score_data.get("holistic_score", 0.0)
            _new_h = _trim_sd.get("holistic_score", 0.0) if _trim_sd else 0.0
            if _new_h >= _old_h:
                experience_section = _trim_exp
                score_data = _trim_sd
                print(c(GREEN, f"  ✓ QC-13 trim accepted ({_old_h:.1f} → {_new_h:.1f})"))
            else:
                print(c(YELLOW,
                        f"  [!] QC-13 trim regressed score ({_new_h:.1f} < {_old_h:.1f})"
                        " — reverting."))

    # ── Regenerate docx ───────────────────────────────────────────────────────
    final_score = score_data.get("holistic_score") if score_data else None
    date_part   = txt_path.stem.replace("resume_", "")   # e.g. "2026-03-26"

    # Delete any old unscored docx to avoid clutter
    unscored = app_dir / f"resume_{date_part}.docx"
    if unscored.exists():
        unscored.unlink()

    # Also delete any old scored docx so generate_docx can name cleanly
    for old in app_dir.glob(f"resume_{date_part}_r*.docx"):
        old.unlink()

    if skills_section:
        sections = {
            "summary_section": _fr._sanitize_summary_section(summary_section),
            "experience_section": experience_section,
            "projects_section": projects_section,
            "skills_section": skills_section,
        }

        # ── Expansion pass (page < 85% full) ─────────────────────────────────
        _fill_result = _fr._estimate_page_fill(
            experience_section, skills_section, projects_section=projects_section
        )
        if _fill_result and _fill_result[0] < 85.0:
            _exp_section, _ = _fr.run_expansion_pass(
                experience_section, skills_section, jd_text, strategy_block, model,
                projects_section=projects_section,
            )
            if _exp_section != experience_section:
                experience_section = _exp_section
                sections["experience_section"] = _exp_section

        print()
        print(c("\033[1m", "  Generating .docx..."))
        _fr.generate_docx(sections, jd_path, app_dir, app_dir, score=final_score,
                          track=track)
        # Rename from DATE_jd_rSCORE.docx → resume_DATE_rSCORE.docx
        docx_renamed = _rename_latest(app_dir, "_jd", f"resume_{date_part}", ".docx")
        if docx_renamed:
            print(c("\033[32m", f"  ✓ Resume docx  → {docx_renamed.relative_to(ROOT_DIR)}"))
    else:
        # No skills section parseable — just rename any existing docx
        score_tag = f"_r{final_score:.1f}" if final_score is not None else ""
        unscored  = app_dir / f"resume_{date_part}.docx"
        if unscored.exists():
            target = app_dir / f"resume_{date_part}{score_tag}.docx"
            unscored.rename(target)
            print(c("\033[32m", f"  ✓ Renamed → {target.relative_to(ROOT_DIR)}"))
        else:
            print(c("\033[33m",
                    f"  [!] No unscored docx found and skills section not parseable "
                    f"— cannot regenerate. Run --resume-only --no-strategy --no-rewrite instead."))
    print()


def docx_only_app(company: str, track: str = "pm") -> None:
    """
    Read the latest resume_*.txt, extract summary/experience/skills sections,
    and regenerate only the .docx with no AI calls.
    """
    app_dir = resolve_company(company)
    jd_path = app_dir / "jd.txt"

    if not jd_path.exists():
        sys.exit(f"[ERROR] jd.txt not found in {app_dir}")

    txt_files = sorted(app_dir.glob("resume_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txt_files:
        sys.exit(f"[ERROR] No resume_*.txt found in {app_dir}. Run the full pipeline first.")
    txt_path = txt_files[0]
    content = txt_path.read_text(encoding="utf-8")

    m_summary = re.search(
        r"SECTION 0 — (?:PROFESSIONAL SUMMARY|PROFILE) \(paste-ready\)\n[-─]+\n(.*?)"
        r"(?=\nSECTION 3|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    summary_section = m_summary.group(1).strip() if m_summary else ""

    m_exp = re.search(
        r"SECTION 3 — FULL EXPERIENCE SECTION \(paste-ready[^)]*\)\n[-─]+\n(.*?)"
        r"(?=\nSECTION 3B|\nSECTION 3 \(PASS 1|\nSECTION 4|\Z)",
        content, re.DOTALL,
    )
    if not m_exp:
        sys.exit(f"[ERROR] Could not extract experience section from {txt_path.name}.")
    experience_section = m_exp.group(1).strip()

    m_projects = re.search(
        r"SECTION 3B — PROJECTS & CONSULTING \(paste-ready\)\n[-─]+\n(PROJECTS & CONSULTING.*?)"
        r"(?=\nSECTION 4|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    projects_section = m_projects.group(1).strip() if m_projects else ""

    m_skills = re.search(
        r"SECTION 4 — SKILLS & INTERESTS \(paste-ready\)\n[-─]+\n(SKILLS & INTERESTS.*?)"
        r"(?=\n(?:SECTION \d|QUALITY CHECKS|QC CHECKS|REWRITES LOG|PASS 4|[─═]{10})|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if not m_skills:
        sys.exit(f"[ERROR] Could not extract skills section from {txt_path.name}.")
    skills_section = m_skills.group(1).strip()

    final_score = None
    stem_match = re.search(r"_r(\d+(?:\.\d+)?)$", txt_path.stem)
    if stem_match:
        final_score = float(stem_match.group(1))
    else:
        score_line = re.search(r"Score:\s+([0-9]+(?:\.[0-9])?)/10", content)
        if score_line:
            final_score = float(score_line.group(1))

    sections = {
        'summary_section': _sanitize_summary_section_local(summary_section),
        'experience_section': experience_section,
        'projects_section': projects_section,
        'skills_section': skills_section,
    }

    print()
    print(c(BOLD + CYAN, "  ╔══════════════════════════════════════════════════╗"))
    print(c(BOLD + CYAN, f"  ║   docx-only   ·  {app_dir.name:<33}║"))
    print(c(BOLD + CYAN,  "  ╚══════════════════════════════════════════════════╝"))
    print(c(CYAN, f"  Source: {txt_path.name}"))
    print()
    print(c(BOLD, "  Generating .docx..."))
    _generate_docx_local(sections, jd_path, app_dir, score=final_score, track=track)

    date_part = txt_path.stem.replace("resume_", "")
    date_part = re.sub(r"_r\d+(?:\.\d+)?$", "", date_part)
    docx_renamed = _rename_latest(app_dir, "_jd", f"resume_{date_part}", ".docx")
    if docx_renamed:
        print(c(GREEN, f"  ✓ Resume docx  → {docx_renamed.relative_to(ROOT_DIR)}"))
    print()


def _sanitize_summary_section_local(text: str) -> str:
    if not text:
        return ""
    clean = text.strip().strip('"')
    clean = re.sub(r"\s*\u2014\s*", ", ", clean)
    clean = re.sub(r"\s{2,}", " ", clean)
    clean = re.sub(r",\s*,", ", ", clean)
    return clean.strip()


def _parse_experience_blocks_local(exp_text: str) -> list[dict]:
    company_keys = ["GOJEK", "HEVO DATA", "INTUIT", "OPTUM"]
    blocks, current_key, current_bullets = [], None, []
    for line in exp_text.splitlines():
        stripped = line.strip().lstrip("*").strip()
        matched_key = next((k for k in company_keys if stripped.upper().startswith(k)), None)
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


def _parse_skills_rows_local(skills_text: str) -> list[dict]:
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


def _parse_project_rows_local(projects_text: str) -> list[dict]:
    rows = []
    current = None
    for line in projects_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("PROJECTS & CONSULTING"):
            continue
        m_bullet = re.match(r'^[\u2022\u25cf\-\*●•]\s+(.*)', stripped)
        if m_bullet:
            bullet = m_bullet.group(1).strip()
            if current is None:
                current = {"company": "", "title": "", "date": "", "bullets": []}
                rows.append(current)
            current["bullets"].append(bullet)
            continue
        if "|" in stripped:
            parts = [p.strip() for p in stripped.split("|")]
            company = parts[0] if len(parts) >= 1 else ""
            title = parts[1] if len(parts) >= 2 else ""
            date = parts[2] if len(parts) >= 3 else ""
            current = {"company": company, "title": title, "date": date, "bullets": []}
            rows.append(current)
            continue
        current = {"company": stripped, "title": "", "date": "", "bullets": []}
        rows.append(current)
    return rows


def _generate_docx_local(sections: dict, jd_path: Path, out_dir: Path, score: float | None = None, track: str = 'pm') -> Path | None:
    docx_script = ROOT_DIR / 'resume' / 'resume_docx.js'
    node_path = str(ROOT_DIR / 'resume' / 'node_modules')
    if not docx_script.exists():
        print(c(YELLOW, '  [!] resume_docx.js not found — skipping docx generation.'))
        return None

    company_blocks = _parse_experience_blocks_local(sections['experience_section'])
    skills_rows = _parse_skills_rows_local(sections['skills_section'])
    project_rows = _parse_project_rows_local(sections.get('projects_section', ''))
    if not company_blocks:
        print(c(YELLOW, '  [!] Could not parse company blocks — skipping docx generation.'))
        return None

    today = datetime.now().strftime('%Y-%m-%d')
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', jd_path.stem).strip('_').lower()[:50]
    score_tag = f'_r{score:.1f}' if score is not None else ''
    output_path = out_dir / f'{today}_{slug}{score_tag}.docx'

    payload = {
        'company_blocks': company_blocks,
        'project_rows': project_rows,
        'skills_rows': skills_rows,
        'professional_summary': sections.get('summary_section', ''),
        'summary_section_header': 'PRODUCT MANAGEMENT' if track == 'pm' else 'PROFILE SUMMARY',
        'output_path': str(output_path),
        'layout': {
            'line': 200,
            'section_before': 140,
            'section_after': 70,
            'margin_bottom': 648,
        },
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path = f.name

    try:
        import shutil
        node_bin = shutil.which('node')
        if not node_bin:
            for candidate in ['/opt/homebrew/bin/node', '/usr/local/bin/node', '/usr/bin/node']:
                if os.path.isfile(candidate):
                    node_bin = candidate
                    break
        if not node_bin:
            print(c(RED, '  [✗] node not found — install Node.js or add it to PATH'))
            return None

        env = os.environ.copy()
        env['NODE_PATH'] = node_path
        result = subprocess.run([node_bin, str(docx_script), tmp_path], capture_output=True, text=True, timeout=180, env=env)
        stdout = (result.stdout or '').strip()
        stderr = (result.stderr or '').strip()
        if result.returncode != 0 or stdout.startswith('ERROR:'):
            print(c(RED, f'  [✗] docx generation failed: {stderr or stdout}'))
            return None
        print(c(GREEN, f'  ✓ .docx saved → {output_path}'))
        return output_path
    except subprocess.TimeoutExpired:
        print(c(RED, '  [✗] docx generation timed out.'))
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global USE_COLOR

    parser = argparse.ArgumentParser(
        description="Unified application orchestrator — strategy + resume + CL in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("company",
                        help="Company label used for logs. By default this matches a directory under apps/.")
    parser.add_argument("--app-dir",     default=None,
                        help="Explicit app directory to operate on (supports run-folder-native generation)")
    parser.add_argument("--resume-only",  action="store_true",
                        help="Run only the resume pipeline (skip CL)")
    parser.add_argument("--cl-only",      action="store_true",
                        help="Run only the cover letter pipeline (skip resume)")
    parser.add_argument("--score-only",   action="store_true",
                        help="Re-score latest resume_*.txt and rename the docx with score tag")
    parser.add_argument("--docx-only",    action="store_true",
                        help="Regenerate only the .docx from latest resume_*.txt (no AI calls)")
    parser.add_argument("--no-strategy",  action="store_true",
                        help="Skip strategy API call (use cached strategy.json if present)")
    parser.add_argument("--no-rewrite",   action="store_true",
                        help="Skip resume Pass 2 (voice rewrite)")
    parser.add_argument("--no-score",     action="store_true",
                        help="Skip resume Pass 3 (scoring)")
    parser.add_argument("--no-qc",        action="store_true",
                        help="Skip CL Step 3 (AI quality check)")
    parser.add_argument("--no-smart-cost", action="store_true",
                        help="Disable score-aware model/pass downgrades for lower-fit jobs")
    parser.add_argument("--docx",         action="store_true",
                        help="Deprecated no-op: .docx is now generated by default")
    parser.add_argument("--no-docx",      action="store_true",
                        help="Skip formatted .docx generation")
    parser.add_argument("--model",        default="claude-sonnet-4-6",
                        help="Anthropic model (default: claude-sonnet-4-6)")
    parser.add_argument("--track",        default="pm", choices=["pm", "nonpm"],
                        help="Resume track: 'pm' (default) or 'nonpm' (Strategy/Consulting/Ops/PgM)")
    parser.add_argument("--no-color",     action="store_true",
                        help="Disable ANSI color output")
    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    if args.resume_only and args.cl_only:
        sys.exit("[ERROR] Cannot use --resume-only and --cl-only together.")
    if args.score_only and (args.resume_only or args.cl_only or args.docx_only):
        sys.exit("[ERROR] --score-only cannot be combined with --resume-only, --cl-only, or --docx-only.")
    if args.docx_only and (args.resume_only or args.cl_only):
        sys.exit("[ERROR] --docx-only cannot be combined with --resume-only or --cl-only.")

    # ── Auto-logging: tee all output to logs/run_app_<company>_HHMMSS.txt ────
    global _orig_stdout
    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"run_app_{args.company}_{ts}.txt"
    log_file = open(log_path, "w", encoding="utf-8")
    _orig_stdout = _Tee(_orig_stdout, log_file)

    try:
        if args.score_only:
            score_only_app(company=args.company, model=args.model, track=args.track)
        elif args.docx_only:
            docx_only_app(company=args.company, track=args.track)
        else:
            run_app(
                company      = args.company,
                model        = args.model,
                run_resume   = not args.cl_only,
                run_cl       = not args.resume_only,
                run_strategy = not args.no_strategy,
                run_rewrite  = not args.no_rewrite,
                run_score    = not args.no_score,
                run_qc       = not args.no_qc,
                make_docx    = not args.no_docx,
                track        = args.track,
                app_dir_override = args.app_dir,
                smart_cost   = not args.no_smart_cost,
            )
    finally:
        log_file.close()
        # Print log path directly to the real terminal (bypass the Tee)
        real_term = _orig_stdout._term if isinstance(_orig_stdout, _Tee) else sys.__stdout__
        real_term.write(f"\n  Log saved → {log_path.relative_to(ROOT_DIR)}\n")


if __name__ == "__main__":
    main()
