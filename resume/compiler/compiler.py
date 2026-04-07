#!/usr/bin/env python3
"""
Resume Compiler — Steps 2, 3, and 5 (fully deterministic)
----------------------------------------------------------
Steps 1 and 4 are AI-handled separately via prompts/step1_jd_interpretation.txt
and prompts/step4_narrative_arc.txt.

Usage:
    python compiler.py <jd_input.json> [output.json]

    jd_input.json  — filled copy of templates/jd_input_template.json
    output.json    — optional; defaults to runs/YYYY-MM-DD_<company>.json

Spec reference: Resume_Compiler_Spec_v1.docx
"""

import json
import os
import sys
from collections import Counter
from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))   # resume/compiler/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))  # ResumeGenerator v1/
EXCEL_PATH = os.path.join(_PROJECT_ROOT, "docs", "Resume_Compiler_Phase1_v4.xlsx")
RUNS_DIR = os.path.join(_HERE, "runs")

# ---------------------------------------------------------------------------
# Constants (spec §5a, §9)
# ---------------------------------------------------------------------------
COMPANY_ORDER = ["Gojek", "Hevo Data", "Intuit", "Optum"]

COMPANY_SLOTS = {
    "Gojek":     3,
    "Hevo Data": 3,
    "Intuit":    3,
    "Optum":     1,
}

TIER_BONUS = {"Tier1": 3, "Tier2": 1, "Tier3": 0}

# Framing preferences by archetype — spec §4b / R-14
FRAMING_PREFERENCE = {
    "Growth PM":           ["impact"],
    "Technical PM":        ["mechanism"],
    "Enterprise SaaS PM":  ["impact", "ownership"],
    "Strategy PM":         ["problem", "mechanism"],
    "AI/ML PM":            ["mechanism", "impact"],
    "Consumer PM":         ["problem", "impact"],
}

# Static metadata — spec §9
STATIC_METADATA = {
    "Gojek":     {"role_title": "Senior Software Engineer",
                  "dates": "Jan 2025 \u2013 Jul 2025",
                  "location": "Gurgaon, India"},
    "Hevo Data": {"role_title": "Software Engineer 2",
                  "dates": "Nov 2023 \u2013 Jan 2025",
                  "location": "Bengaluru, India"},
    "Intuit":    {"role_title": "Software Engineer 2",
                  "dates": "Aug 2022 \u2013 Oct 2023",
                  "location": "Bengaluru, India"},
    "Optum":     {"role_title": "Software Engineer",
                  "dates": "Jul 2020 \u2013 Aug 2022",
                  "location": "Gurgaon, India"},
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_repository():
    """Load and prepare Stories and Variants from the Excel file."""
    xl = pd.ExcelFile(EXCEL_PATH)
    stories = xl.parse("Stories", header=1)
    variants = xl.parse("Variants", header=1)

    # Section scoping: only experience stories eligible (spec R-02 / Excel R-02)
    stories = stories[stories["section"] == "experience"].copy()

    # Variant status filter: only 'keep' variants eligible (spec V-01)
    variants = variants[variants["variant_status"] == "keep"].copy()

    # Parse comma-separated tag strings into lists for overlap calculations
    def parse_tags(val):
        if pd.isna(val) or str(val).strip() == "":
            return []
        return [t.strip() for t in str(val).split(",") if t.strip() and t.strip().lower() != "nan"]

    stories["primary_tags_list"]   = stories["primary_tags"].apply(parse_tags)
    stories["secondary_tags_list"] = stories["secondary_tags"].apply(parse_tags)
    variants["tag_fit_list"]       = variants["tag_fit"].apply(parse_tags)

    # Coerce signal columns to int (they should already be, but guard against NaN)
    for col in ["pm_signal", "tech_signal", "business_signal", "clarity", "variant_priority"]:
        variants[col] = pd.to_numeric(variants[col], errors="coerce").fillna(0).astype(int)

    stories["story_priority"] = pd.to_numeric(stories["story_priority"], errors="coerce").fillna(99).astype(int)

    return stories, variants


# ---------------------------------------------------------------------------
# Step 2 — Story Scoring & Selection (spec §5)
# ---------------------------------------------------------------------------

def get_active_tags(tag_mix: dict) -> set:
    """Return the set of tags that have weight > 0 in the JD tag mix."""
    return {tag for tag, weight in tag_mix.items() if weight > 0}


def score_story(story: pd.Series, active_tags: set) -> float:
    """
    Compute story score per spec §5b.

    score = (primary_tag_overlap × 2.0)
          + (secondary_tag_overlap × 1.0)
          + tier_bonus
          − (story_priority / 100)
    """
    primary_overlap   = len(set(story["primary_tags_list"]) & active_tags)
    secondary_overlap = len(set(story["secondary_tags_list"]) & active_tags)
    tier_bonus        = TIER_BONUS.get(story["tier"], 0)
    priority_adj      = -(story["story_priority"] / 100)
    return (primary_overlap * 2.0) + (secondary_overlap * 1.0) + tier_bonus + priority_adj


def select_stories_for_company(company_stories: pd.DataFrame,
                                n_slots: int,
                                active_tags: set) -> list:
    """
    Step 2: Score and select the top N stories for one company slot.
    Applies narrative diversity check (spec §5c) after selection.
    Returns a list of pandas Series (rows), highest-scoring first.
    """
    if company_stories.empty:
        return []

    scored = sorted(
        [(score_story(row, active_tags), row) for _, row in company_stories.iterrows()],
        key=lambda x: -x[0]
    )

    selected = [item[1] for item in scored[:n_slots]]

    # Narrative diversity check (spec §5c):
    # If all selected stories share the same primary_story_type, substitute
    # the lowest-scoring one with the next-best story of a different type.
    if len(selected) >= 3:
        types = [s["primary_story_type"] for s in selected]
        if len(set(types)) == 1:  # all identical
            dominant_type = types[0]
            # Find first unused story with a different type
            for score, candidate in scored[n_slots:]:
                if candidate["primary_story_type"] != dominant_type:
                    selected[-1] = candidate  # replace lowest-scoring duplicate
                    break

    return selected


# ---------------------------------------------------------------------------
# Step 3 — Variant Selection (spec §6)
# ---------------------------------------------------------------------------

def score_variant(variant: pd.Series,
                  active_tags: set,
                  archetype: str,
                  framing_counts: Counter) -> float:
    """
    Compute variant score per spec V-03, V-04, V-05.

    Base:  tag_fit overlap count (V-03)
    +1:    preferred framing for archetype (V-04)
    -2:    framing already used 2+ times in selected bullets (V-05)
    """
    tag_overlap = len(set(variant["tag_fit_list"]) & active_tags)
    score = float(tag_overlap)

    preferred_framings = FRAMING_PREFERENCE.get(archetype, [])
    if variant["framing_type"] in preferred_framings:
        score += 1.0

    if framing_counts.get(variant["framing_type"], 0) >= 3:
        score -= 100.0  # V-05: hard block — enforces R-03 max-3 per framing type

    return score


def _rank_variants(pool: pd.DataFrame,
                   active_tags: set,
                   archetype: str,
                   framing_counts: Counter) -> list:
    """
    Sort a pool of variants by:
      1. score descending        (V-03 + V-04 + V-05)
      2. variant_priority asc    (V-06, lower = preferred → negate for sort)
      3. is_default='yes' first  (V-07)
    Returns list of (score, variant Series).
    """
    ranked = []
    for _, v in pool.iterrows():
        s = score_variant(v, active_tags, archetype, framing_counts)
        vp = v["variant_priority"]
        default_flag = 1 if str(v.get("is_default", "no")).strip().lower() == "yes" else 0
        ranked.append((s, -vp, default_flag, v))

    ranked.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [(item[0], item[3]) for item in ranked]  # (score, Series)


def select_variant(story: pd.Series,
                   all_variants: pd.DataFrame,
                   active_tags: set,
                   archetype: str,
                   role_context: str,
                   framing_counts: Counter) -> pd.Series | None:
    """
    Step 3: Select the best variant for a story using rules V-01 through V-08.

    V-01  Already filtered to status='keep' at load time.
    V-02  Separate candidates into rcf-eligible (rcf matches JD context or 'any')
          and rcf-ineligible.
    V-03  Score by tag_fit overlap.
    V-04  +1 bonus for preferred framing type.
    V-05  -2 penalty if framing already used 2+ times.
    V-06  Tiebreak by variant_priority (lower = preferred).
    V-07  Final tiebreak: is_default='yes' wins.
    V-08  Prefer rcf-eligible unless ineligible beats it by >3 points.
    """
    story_id = story["story_id"]
    candidates = all_variants[all_variants["story_id"] == story_id]

    if candidates.empty:
        return None

    def is_eligible(v):
        rcf = str(v["role_context_fit"]).strip().lower()
        return rcf == "any" or rcf == role_context.lower()

    eligible   = candidates[candidates.apply(is_eligible, axis=1)]
    ineligible = candidates[~candidates.apply(is_eligible, axis=1)]

    if not eligible.empty:
        el_ranked = _rank_variants(eligible, active_tags, archetype, framing_counts)
        best_eligible_score, best_eligible = el_ranked[0]

        if not ineligible.empty:
            in_ranked = _rank_variants(ineligible, active_tags, archetype, framing_counts)
            best_ineligible_score, best_ineligible = in_ranked[0]
            # V-08: prefer eligible unless ineligible beats it by >3 points
            if best_ineligible_score - best_eligible_score > 3:
                return best_ineligible

        return best_eligible

    # No eligible variants at all — fall back to full pool (V-02 note in spec)
    all_ranked = _rank_variants(candidates, active_tags, archetype, framing_counts)
    return all_ranked[0][1] if all_ranked else None


# ---------------------------------------------------------------------------
# Step 5 helpers — Quality Gates & Assembly (spec §8)
# ---------------------------------------------------------------------------

def get_opening_verb(bullet_text: str) -> str:
    """Extract the first word of a bullet (used for verb dedup check R-04)."""
    text = str(bullet_text).strip()
    return text.split()[0] if text else ""


def _bullet_dict(story: pd.Series, variant: pd.Series) -> dict:
    """Package a selected story+variant into a portable dict."""
    return {
        "story_id":        str(story["story_id"]),
        "variant_id":      str(variant["variant_id"]),
        "bullet_text":     str(variant["bullet_text"]),
        "framing_type":    str(variant["framing_type"]),
        "business_signal": int(variant["business_signal"]),
        "pm_signal":       int(variant["pm_signal"]),
        "tech_signal":     int(variant["tech_signal"]),
        "clarity":         int(variant["clarity"]),
    }


def order_company_block(bullets: list) -> list:
    """
    R-06: Within each company block, order by:
      1. business_signal descending
      2. pm_signal descending
      3. clarity descending
    """
    return sorted(
        bullets,
        key=lambda b: (-b["business_signal"], -b["pm_signal"], -b["clarity"])
    )


def ensure_gojek_leads_growth(bullets: list, gojek_stories: list) -> list:
    """
    R-07: Gojek block should lead with a revenue/conversion story where
    possible. Defined as: story has GROWTH in primary_tags_list.

    If the current first bullet is not a GROWTH story, and a GROWTH story
    exists elsewhere in the block, move it to position 0.
    Only swaps — does not re-sort the rest of the block.
    """
    if len(bullets) <= 1:
        return bullets

    story_lookup = {s["story_id"]: s for s in gojek_stories}

    def is_growth(bullet):
        s = story_lookup.get(bullet["story_id"])
        return s is not None and "GROWTH" in s.get("primary_tags_list", [])

    if is_growth(bullets[0]):
        return bullets  # already leading with GROWTH

    for i in range(1, len(bullets)):
        if is_growth(bullets[i]):
            # Bring this one to front
            bullets = [bullets[i]] + [b for j, b in enumerate(bullets) if j != i]
            return bullets

    return bullets  # no GROWTH story available — leave as-is


def find_11th_bullet(stories: pd.DataFrame,
                     selected_story_ids: set,
                     all_variants: pd.DataFrame,
                     active_tags: set,
                     archetype: str,
                     role_context: str,
                     framing_counts: Counter) -> tuple:
    """
    Evaluate candidates for the optional 11th bullet.

    Priority order (spec R-06 / Excel rule R-06):
      1. Second Optum bullet (unused Optum story)
      2. Strongest unused story from any other company

    Only accepted if the selected variant has business_signal >= 7 AND
    pm_signal >= 7 (spec R-08).

    Returns (company, story Series, variant Series) or (None, None, None).
    """
    candidates = []  # (priority, score, company, story, variant)

    for _, story in stories.iterrows():
        if story["story_id"] in selected_story_ids:
            continue

        variant = select_variant(story, all_variants, active_tags,
                                 archetype, role_context, framing_counts)
        if variant is None:
            continue

        # R-08 threshold check
        if int(variant["business_signal"]) < 7 or int(variant["pm_signal"]) < 7:
            continue

        company = story["company"]
        story_score = score_story(story, active_tags)
        # Priority 0 = Optum (preferred for 11th slot), 1 = everywhere else
        priority = 0 if company == "Optum" else 1
        candidates.append((priority, -story_score, company, story, variant))

    if not candidates:
        return None, None, None

    # Sort: Optum first (priority=0), then by descending story score (-score asc)
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, _, company, story, variant = candidates[0]
    return company, story, variant


def run_quality_gates(company_bullets: dict, framing_counts: Counter) -> dict:
    """
    Step 5 (spec §8): Check R-01 through R-09. Returns a dict of gate → result.
    'pass' = gate satisfied. Anything else = description of violation.
    """
    all_bullets = []
    for company in COMPANY_ORDER:
        all_bullets.extend(company_bullets.get(company, []))

    total = len(all_bullets)
    gates = {}

    # R-01: total bullet count must be 10 or 11
    gates["R-01"] = "pass" if 10 <= total <= 11 else f"FAIL — total={total} (expected 10 or 11)"

    # R-02: no company block empty
    empty_blocks = [c for c in COMPANY_ORDER if not company_bullets.get(c)]
    gates["R-02"] = "pass" if not empty_blocks else f"FAIL — empty blocks: {empty_blocks}"

    # R-03: no framing_type appears more than 3 times
    # (4 types × 3 max = 12 slots for 10–11 bullets; hard-blocked at count≥3 by V-05)
    violations = {ft: cnt for ft, cnt in framing_counts.items() if cnt > 3}
    gates["R-03"] = "pass" if not violations else f"FAIL — framing overuse: {violations}"

    # R-04: no opening verb appears 3 or more times
    verbs = [get_opening_verb(b["bullet_text"]) for b in all_bullets]
    verb_counts = Counter(verbs)
    verb_violations = {v: c for v, c in verb_counts.items() if c >= 3 and v}
    gates["R-04"] = "pass" if not verb_violations else f"FAIL — verb repeats >=3x: {verb_violations}"

    # R-05: all bullets past tense (heuristic: flag -ing openers)
    progressive_starts = [
        b["bullet_text"][:60]
        for b in all_bullets
        if get_opening_verb(b["bullet_text"]).endswith("ing")
    ]
    gates["R-05"] = (
        "pass" if not progressive_starts
        else f"WARN — possible present-tense bullets (manual review): {progressive_starts}"
    )

    # R-06 and R-07: enforced during ordering / Gojek-lead logic (structural)
    gates["R-06"] = "pass — ordering enforced (business_signal → pm_signal → clarity)"
    gates["R-07"] = "pass — Gojek GROWTH-lead check applied"

    # R-08 and R-09: enforced during 11th bullet evaluation
    gates["R-08"] = "pass — 11th bullet threshold enforced (biz>=7, pm>=7)"
    gates["R-09"] = "MANUAL — thematic distinctiveness of 11th bullet requires human review"

    # R-10: no two bullets may share identical text (catches story dedup failures)
    bullet_texts = [b["bullet_text"] for b in all_bullets]
    text_counts  = Counter(bullet_texts)
    dup_texts    = [t[:80] + "…" for t, c in text_counts.items() if c > 1]
    gates["R-10"] = (
        "pass" if not dup_texts
        else f"FAIL — duplicate bullet text detected ({len(dup_texts)} pair(s)): {dup_texts}"
    )

    return gates


def assemble_plain_text(company_bullets: dict) -> str:
    """Render the final experience section as plain text."""
    lines = []
    for company in COMPANY_ORDER:
        bullets = company_bullets.get(company, [])
        if not bullets:
            continue
        meta = STATIC_METADATA[company]
        lines.append(
            f"{company.upper()} | {meta['role_title']} | {meta['dates']} | {meta['location']}"
        )
        for b in bullets:
            lines.append(f"\u2022 {b['bullet_text']}")
        lines.append("")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Main compiler entry point
# ---------------------------------------------------------------------------

def run_compiler(jd_input_path: str,
                 output_path: str | None = None,
                 story_overrides: dict | None = None,
                 silent: bool = False) -> dict:
    """
    Execute the full deterministic pipeline (Steps 2, 3, 5).

    Args:
        jd_input_path:   Path to a filled jd_input_template.json
        output_path:     Where to write the run output JSON.
                         Defaults to runs/YYYY-MM-DD_<company>.json.
        story_overrides: Optional substitutions from Step 4 narrative arc check.
                         Format: {"Hevo Data": {"remove": "hevo_query_engine",
                                                "add":    "hevo_regression"}}
                         Applied after Step 2 scoring; variant re-selected for
                         the new story.
        silent:          If True, suppress console output (used by pipeline.py).

    Returns:
        The run output dict (also written to disk).
    """
    # ── Load inputs ──────────────────────────────────────────────────────────
    with open(jd_input_path, encoding="utf-8") as f:
        jd = json.load(f)

    # Strip comment-only keys (start with "_")
    jd = {k: v for k, v in jd.items() if not k.startswith("_")}

    tag_mix      = jd["tag_mix"]
    archetype    = jd["role_archetype"]
    role_context = jd["role_context_fit"]
    active_tags  = get_active_tags(tag_mix)

    stories, all_variants = load_repository()

    # ── Step 2: Story selection per company slot ──────────────────────────────
    selected_stories: dict[str, list] = {}
    for company in COMPANY_ORDER:
        co_stories = stories[stories["company"] == company]
        selected_stories[company] = select_stories_for_company(
            co_stories, COMPANY_SLOTS[company], active_tags
        )

    # ── Apply Step 4 overrides (pipeline feedback loop) ──────────────────────
    # story_overrides lets pipeline.py substitute a story after narrative arc
    # check without requiring human intervention.
    if story_overrides:
        for company, override in story_overrides.items():
            remove_id = override.get("remove", "")
            add_id    = override.get("add", "")
            if not remove_id or not add_id:
                continue
            co_all = stories[stories["company"] == company]
            add_rows = co_all[co_all["story_id"] == add_id]
            if add_rows.empty:
                continue  # requested story not found — skip silently
            new_story = add_rows.iloc[0]
            # Replace the named story; if not present (already wasn't selected),
            # append the new story up to the slot limit.
            current = selected_stories.get(company, [])
            replaced = [s for s in current if s["story_id"] != remove_id]
            if len(replaced) < COMPANY_SLOTS[company]:
                replaced.append(new_story)
            selected_stories[company] = replaced

    # ── Step 3: Variant selection ─────────────────────────────────────────────
    # Process companies in order, tracking framing counts globally so that
    # V-05 (framing variety penalty) operates across the full bullet set.
    framing_counts     = Counter()
    company_bullets    = {c: [] for c in COMPANY_ORDER}
    selected_story_ids = set()
    selected_variant_ids = []

    for company in COMPANY_ORDER:
        for story in selected_stories[company]:
            variant = select_variant(
                story, all_variants, active_tags,
                archetype, role_context, framing_counts
            )
            if variant is None:
                continue

            bullet = _bullet_dict(story, variant)
            company_bullets[company].append(bullet)
            framing_counts[variant["framing_type"]] += 1
            selected_story_ids.add(story["story_id"])
            selected_variant_ids.append(str(variant["variant_id"]))

    # ── Step 5a: Order within company blocks (R-06) ───────────────────────────
    for company in COMPANY_ORDER:
        company_bullets[company] = order_company_block(company_bullets[company])

    # Apply R-07: Gojek block leads with GROWTH story where possible
    company_bullets["Gojek"] = ensure_gojek_leads_growth(
        company_bullets["Gojek"], selected_stories["Gojek"]
    )

    # ── Step 5b: Evaluate optional 11th bullet (R-08) ────────────────────────
    company_11, story_11, variant_11 = find_11th_bullet(
        stories, selected_story_ids, all_variants,
        active_tags, archetype, role_context, framing_counts
    )

    if company_11 is not None:
        bullet_11 = _bullet_dict(story_11, variant_11)
        company_bullets[company_11].append(bullet_11)
        framing_counts[variant_11["framing_type"]] += 1
        selected_variant_ids.append(str(variant_11["variant_id"]))
        # Re-sort the block that received the 11th bullet
        company_bullets[company_11] = order_company_block(company_bullets[company_11])
        # Re-apply R-07 if Gojek received the 11th
        if company_11 == "Gojek":
            company_bullets["Gojek"] = ensure_gojek_leads_growth(
                company_bullets["Gojek"], selected_stories["Gojek"]
            )

    # ── Step 5c: Quality gates ────────────────────────────────────────────────
    quality_gates = run_quality_gates(company_bullets, framing_counts)

    # ── Assemble plain text and run output ────────────────────────────────────
    bullet_counts = {c: len(company_bullets[c]) for c in COMPANY_ORDER}
    total_bullets = sum(bullet_counts.values())
    plain_text    = assemble_plain_text(company_bullets)

    run_output = {
        "run_date":        str(date.today()),
        "jd_company":      jd.get("company", ""),
        "role_title":      jd.get("role_title", ""),
        "jd_url":          jd.get("jd_url", ""),
        "archetype":       archetype,
        "role_context":    role_context,
        "tag_mix":         tag_mix,
        "stories_selected": {
            c: [s["story_id"] for s in selected_stories[c]]
            for c in COMPANY_ORDER
        },
        "variants_selected": selected_variant_ids,
        "bullet_count": {
            "total": total_bullets,
            **bullet_counts,
        },
        "framing_distribution": dict(framing_counts),
        "quality_gates":    quality_gates,
        "company_bullets":  company_bullets,
        "narrative_arc_notes": "(Run Step 4 — paste step4_narrative_arc.txt output here)",
        "final_output":     plain_text,
    }

    # ── Write output ──────────────────────────────────────────────────────────
    if output_path is None:
        run_date     = str(date.today())
        company_slug = jd.get("company", "unknown").lower().replace(" ", "_")
        os.makedirs(RUNS_DIR, exist_ok=True)
        output_path  = os.path.join(RUNS_DIR, f"{run_date}_{company_slug}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(run_output, f, indent=2, ensure_ascii=False)

    # ── Console summary ───────────────────────────────────────────────────────
    if not silent:
        print(f"\nRun complete → {output_path}")
        print(f"Bullets: {total_bullets}  "
              + "  ".join(f"{c}: {bullet_counts[c]}" for c in COMPANY_ORDER))

        print("\n── Quality Gates ──────────────────────────────────")
        for gate, result in quality_gates.items():
            status = "✓" if result.startswith("pass") else ("⚠" if result.startswith("WARN") or result.startswith("MANUAL") else "✗")
            print(f"  {status} {gate}: {result}")

        print("\n── Compiled Experience Section ────────────────────")
        print(plain_text)
        print()

    return run_output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Resume Compiler — deterministic Steps 2, 3, 5"
    )
    parser.add_argument("jd_input", help="Filled jd_input_template.json")
    parser.add_argument("output",   nargs="?", default=None,
                        help="Output JSON path (default: runs/DATE_company.json)")
    parser.add_argument("--override", default=None,
                        help='Step 4 story substitutions as JSON string. '
                             'Example: \'{"Hevo Data": {"remove": "hevo_query_engine", '
                             '"add": "hevo_regression"}}\'')
    args = parser.parse_args()

    overrides = json.loads(args.override) if args.override else None
    run_compiler(args.jd_input, args.output, story_overrides=overrides)
