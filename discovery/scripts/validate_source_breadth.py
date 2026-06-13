#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "discovery" / "auto" / "logs"
OUT_DIR = ROOT / "discovery" / "source_validation"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.job_eligibility import (  # noqa: E402
    pre_filter_full_time_level,
    pre_filter_immigration,
    pre_filter_role_type,
)


EARLY_SIGNAL_RE = re.compile(
    r"\b("
    r"intern|internship|co-?op|coop|summer|mba|apm|associate product manager|"
    r"new grad|recent grad|entry[- ]level|early career|rotational|leadership program"
    r")\b",
    re.I,
)

TARGET_SIGNAL_PATTERNS = [
    ("product_intern", re.compile(r"\b(product (?:manager|management|owner|ops|operations|strategy|strategist|solutions?)|pm)\b", re.I)),
    ("ai_product", re.compile(r"\b(ai|genai|ml|data)\s+product\b|\bproduct.*\b(ai|genai|ml|data)\b", re.I)),
    ("strategy_ops", re.compile(r"\b(strategy|strategic|business operations|bizops|biz ops|growth|gtm|revenue operations|revops)\b", re.I)),
    ("program_ops", re.compile(r"\b(program manager|technical program manager|operations project|special project)\b", re.I)),
    ("startup_operator", re.compile(r"\b(chief of staff|founder'?s associate|founding operator|business associate|venture|new ventures)\b", re.I)),
]

EARLY_ADJACENT_RE = re.compile(
    r"\b(product|strategy|operations|growth|business|program|market|acquisition|"
    r"customer engagement|loyalty|commercial|partnership|new ventures)\b",
    re.I,
)

SENIORITY_REJECT_RE = re.compile(
    r"\b("
    r"senior|sr\.?|staff|principal|director|head|vp|vice president|lead product manager|"
    r"group product manager|manager ii|product manager ii|7\+ years|5\+ years|4\+ years"
    r")\b",
    re.I,
)

RECRUITER_COMPANY_RE = re.compile(
    r"\b("
    r"jobgether|jobot|motion recruitment|optomi|midtown group|firstpro|hirecapital|"
    r"hackajob|partner group|vlink|net2source|lensa|dice|robert half|tek.?systems|"
    r"insight global|randstad|aquent|kforce|jobright(?:\\.ai)?|our client|confidential"
    r")\b",
    re.I,
)

WEAK_APM_TITLE_RE = re.compile(
    r"\b(apm|associate product manager|entry[- ]level product manager|early career product manager)\b",
    re.I,
)

STRONG_EARLY_SIGNAL_RE = re.compile(
    r"\b(intern|internship|co-?op|coop|summer|mba|student|campus|university|new grad|recent grad|rotational)\b",
    re.I,
)

RELATIONSHIP_COMPANY_RE = re.compile(
    # Validation-only seed list from the 24h sample. The daily engine should replace
    # this with portfolio/funding/source provenance once startup sources are wired.
    r"\b("
    r"anthropic|atticus|fractional ai|daloopa|foundation health|alma|seer|stripe|"
    r"robinhood|mdcalc|luma financial|limbic|early media|spotio|fingercheck|hudl"
    r")\b",
    re.I,
)

RELATIONSHIP_TITLE_SIGNAL_RE = re.compile(
    r"\b("
    r"ai|genai|claude|machine learning|ml|llm|developer tool|devtool|"
    r"healthtech|fintech|robotics|marketplace|forward deployed|terminal device|"
    r"founder|founding"
    r")\b",
    re.I,
)

RELATIONSHIP_BODY_SIGNAL_RE = re.compile(
    r"\b("
    r"early-stage|venture-backed|seed stage|series [abc]|yc|y combinator|a16z|"
    r"founder-led|founding team"
    r")\b",
    re.I,
)

LARGE_COMPANY_GENERIC_RE = re.compile(
    r"\b("
    r"google|amazon|aws|netflix|adobe|nike|toyota|bloomberg|morgan stanley|"
    r"american express|fiserv|global payments|delta air lines|lazard"
    r")\b",
    re.I,
)

NOISE_TITLE_RE = re.compile(
    r"\b("
    r"product marketing manager|marketing manager|sales manager|account executive|"
    r"customer success|recruiter|talent acquisition|software engineer|data scientist|"
    r"solutions architect|legal|counsel|human resources|hr intern"
    r")\b",
    re.I,
)


@dataclass
class ClassifiedJob:
    verdict: str
    source_bucket: str
    company: str
    role_title: str
    url: str
    source: str
    reasons: list[str]


def latest_file(pattern: str) -> Path:
    matches = [
        path
        for path in LOGS_DIR.glob(pattern)
        if "inflight" not in path.name and "repaired" not in path.name
    ]
    matches = sorted(matches, key=lambda path: path.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No files matched {LOGS_DIR / pattern}")
    return matches[-1]


def load_jobs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("jobs") or payload.get("cards") or payload.get("results") or []


def linkedin_job_key(job: dict[str, Any]) -> str:
    url = str(job.get("url") or "").strip()
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return f"li:{match.group(1)}"
    company = normalize(job.get("company"))
    title = normalize(job.get("role_title") or job.get("title"))
    return f"ct:{company}|{title}"


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def target_signals(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in TARGET_SIGNAL_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return hits


def relationship_signals(title: str, company: str, jd_head: str) -> list[str]:
    """Signals that a non-internship role is still useful for startup/company outreach."""
    signals: list[str] = []
    if RELATIONSHIP_COMPANY_RE.search(company):
        signals.append("high-signal company")
    if RELATIONSHIP_TITLE_SIGNAL_RE.search(f"{company}\n{title}"):
        signals.append("startup/AI/domain title signal")
    if RELATIONSHIP_BODY_SIGNAL_RE.search(jd_head):
        signals.append("startup/funding body signal")
    if re.search(r"\bforward deployed product manager\b", title, re.I):
        signals.append("operator-style product role")
    return signals


def classify_job(job: dict[str, Any], source_bucket: str) -> ClassifiedJob:
    title = str(job.get("role_title") or job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    jd_text = str(job.get("jd_text") or "")
    jd_head = jd_text[:1200]
    combined = f"{title}\n{jd_head}"
    reasons: list[str] = []

    if RECRUITER_COMPANY_RE.search(company):
        return _classified("skip_noise", source_bucket, job, ["Recruiter/aggregator posting"])

    role_reject, role_reason = pre_filter_role_type(title)
    if role_reject:
        return _classified("skip_noise", source_bucket, job, [role_reason])

    immigration_reject, immigration_reason = pre_filter_immigration(jd_text)
    if immigration_reject:
        return _classified("skip_noise", source_bucket, job, [immigration_reason])

    full_time_reject, full_time_reason = pre_filter_full_time_level(title, jd_text)
    title_early_signal = bool(EARLY_SIGNAL_RE.search(title))
    body_early_signal = bool(EARLY_SIGNAL_RE.search(jd_head))
    early_signal = title_early_signal or body_early_signal
    title_signals = target_signals(title)
    body_signals = target_signals(jd_head)
    signals = list(dict.fromkeys([*title_signals, *body_signals]))
    outreach_signals = relationship_signals(title, company, jd_head)

    if NOISE_TITLE_RE.search(title):
        return _classified("skip_noise", source_bucket, job, ["Noisy non-target title pattern"])

    if SENIORITY_REJECT_RE.search(title) and not early_signal:
        return _classified("skip_noise", source_bucket, job, ["Senior/full-time level signal without early-career signal"])

    if full_time_reject and not early_signal:
        return _classified("skip_noise", source_bucket, job, [full_time_reason])

    if signals:
        reasons.extend(f"Target signal: {signal}" for signal in signals)
    if title_early_signal:
        reasons.append("Early-career/intern/MBA signal in title")
    elif body_early_signal:
        reasons.append("Early-career/intern/MBA signal in JD body")
    if outreach_signals:
        reasons.extend(f"Relationship signal: {signal}" for signal in outreach_signals)

    if WEAK_APM_TITLE_RE.search(title) and not STRONG_EARLY_SIGNAL_RE.search(combined):
        return _classified(
            "app_review",
            source_bucket,
            job,
            [*reasons, "APM/associate PM title without explicit internship, MBA, student, or new-grad signal"],
        )

    if title_signals and title_early_signal:
        return _classified("app_score_now", source_bucket, job, reasons)

    if early_signal and (body_signals or title_signals or EARLY_ADJACENT_RE.search(combined)):
        detail = (
            "Early-career title with target signal from JD body"
            if title_early_signal and body_signals
            else "Early-career business/product-adjacent signal"
        )
        return _classified("app_review", source_bucket, job, [*reasons, detail])

    if title_signals and outreach_signals:
        if LARGE_COMPANY_GENERIC_RE.search(company) and not RELATIONSHIP_COMPANY_RE.search(company):
            return _classified("skip_noise", source_bucket, job, [*reasons, "Large-company full-time PM signal, not an internship or startup relationship target"])
        return _classified("outreach_signal", source_bucket, job, [*reasons, "Target role, but no explicit early-career signal"])

    if title_signals and not title_early_signal:
        if LARGE_COMPANY_GENERIC_RE.search(company):
            return _classified("skip_noise", source_bucket, job, [*reasons, "Large-company full-time PM signal, not an internship or startup relationship target"])
        return _classified("skip_noise", source_bucket, job, [*reasons, "Generic full-time target role without early-career or relationship signal"])

    return _classified("skip_noise", source_bucket, job, ["No clear target or early-career signal"])


def _classified(verdict: str, source_bucket: str, job: dict[str, Any], reasons: list[str]) -> ClassifiedJob:
    return ClassifiedJob(
        verdict=verdict,
        source_bucket=source_bucket,
        company=str(job.get("company") or "").strip(),
        role_title=str(job.get("role_title") or job.get("title") or "").strip(),
        url=str(job.get("url") or "").strip(),
        source=str(job.get("source") or "").strip(),
        reasons=list(dict.fromkeys(reason for reason in reasons if reason)),
    )


def bucketize(playwright_jobs: list[dict[str, Any]], jobspy_jobs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    playwright_by_key = {linkedin_job_key(job): job for job in playwright_jobs}
    jobspy_by_key = {linkedin_job_key(job): job for job in jobspy_jobs}
    overlap_keys = set(playwright_by_key) & set(jobspy_by_key)
    return {
        "overlap": [playwright_by_key[key] for key in sorted(overlap_keys)],
        "playwright_only": [playwright_by_key[key] for key in sorted(set(playwright_by_key) - overlap_keys)],
        "jobspy_only": [jobspy_by_key[key] for key in sorted(set(jobspy_by_key) - overlap_keys)],
    }


def summarize_classified(items: list[ClassifiedJob]) -> dict[str, Any]:
    verdict_counts = Counter(item.verdict for item in items)
    return {
        "count": len(items),
        "verdict_counts": dict(verdict_counts.most_common()),
        "app_score_now": [asdict(item) for item in items if item.verdict == "app_score_now"],
        "app_review": [asdict(item) for item in items if item.verdict == "app_review"],
        "outreach_signal": [asdict(item) for item in items if item.verdict == "outreach_signal"],
        "skip_noise_count": verdict_counts.get("skip_noise", 0),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Source Breadth Validation",
        "",
        f"Generated: {payload['generated_at']}",
        f"Playwright artifact: `{payload['inputs']['playwright_raw']}`",
        f"JobSpy artifact: `{payload['inputs']['jobspy_raw']}`",
        "",
        "## Raw Coverage",
        "",
        f"- Playwright jobs: {payload['raw_counts']['playwright']}",
        f"- JobSpy jobs: {payload['raw_counts']['jobspy']}",
        f"- Overlap: {payload['raw_counts']['overlap']}",
        f"- Playwright-only: {payload['raw_counts']['playwright_only']}",
        f"- JobSpy-only: {payload['raw_counts']['jobspy_only']}",
        "",
        "## Relevance After Filters",
        "",
    ]

    for bucket in ("playwright_only", "jobspy_only", "overlap"):
        summary = payload["classified"][bucket]
        lines.append(f"### {bucket}")
        lines.append("")
        lines.append(f"- Total: {summary['count']}")
        lines.append(f"- Verdicts: {summary['verdict_counts']}")
        lines.append("")
        for verdict in ("app_score_now", "app_review", "outreach_signal"):
            rows = summary[verdict]
            if not rows:
                continue
            lines.append(f"#### {verdict}")
            lines.append("")
            for item in rows[:30]:
                reason = "; ".join(item["reasons"][:3])
                lines.append(f"- {item['company']} | {item['role_title']} | {item['url']}")
                lines.append(f"  - {reason}")
            lines.append("")

    lines.extend(
        [
            "## Recommendation",
            "",
            "- Keep Playwright as the trusted visual baseline.",
            "- Add JobSpy to the daily lane only after applying these hard relevance filters before Claude scoring.",
            "- Treat `app_score_now` as candidates worth scoring immediately.",
            "- Treat `app_review` as a bounded manual or cheap-review queue.",
            "- Treat `outreach_signal` as relationship/company discovery, not normal application scoring.",
            "- Never spend API calls on `skip_noise`.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Playwright and JobSpy breadth after relevance filters.")
    parser.add_argument("--playwright-raw", type=Path, default=None)
    parser.add_argument("--jobspy-raw", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    playwright_raw = args.playwright_raw or latest_file("linkedin_live_raw_*.json")
    jobspy_raw = args.jobspy_raw or latest_file("jobspy_linkedin_equiv_raw_24h_*.json")
    playwright_jobs = load_jobs(playwright_raw)
    jobspy_jobs = load_jobs(jobspy_raw)
    buckets = bucketize(playwright_jobs, jobspy_jobs)
    classified = {
        bucket: [classify_job(job, bucket) for job in jobs]
        for bucket, jobs in buckets.items()
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "playwright_raw": str(playwright_raw),
            "jobspy_raw": str(jobspy_raw),
        },
        "raw_counts": {
            "playwright": len(playwright_jobs),
            "jobspy": len(jobspy_jobs),
            "overlap": len(buckets["overlap"]),
            "playwright_only": len(buckets["playwright_only"]),
            "jobspy_only": len(buckets["jobspy_only"]),
        },
        "classified": {
            bucket: summarize_classified(items)
            for bucket, items in classified.items()
        },
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = args.out_dir / f"{stamp}-source-breadth-filtered.json"
    md_path = args.out_dir / f"{stamp}-source-breadth-filtered.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    for bucket in ("playwright_only", "jobspy_only", "overlap"):
        print(f"{bucket}: {payload['classified'][bucket]['verdict_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
