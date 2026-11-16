#!/usr/bin/env python3
"""Reconcile every saved capture with JDs, current rules, scores, and the tracker.

This is local-only: no browser, model, API calls, or tracker writes. An unresolved
card stays in the ledger and recovery inputs until it has an explicit outcome.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.job_eligibility import classify_discovery_job_offline, pre_filter_discovery_scope
from discovery.scripts.select_linkedin_2027_candidates import classify_title
from shared.discovery_identity import canonical_listing_url, national_recruitment_templates, role_group_key
from discovery.auto.scorer import _jd_quality_issue

UNFINISHED = {"needs_jd", "needs_score", "needs_review"}


def listing_key(row: dict) -> str:
    url = str(row.get("url") or row.get("source_url") or "").strip()
    match = re.search(r"/jobs/view/(\d+)", url)
    if match:
        return "li:" + match.group(1)
    if url:
        return canonical_listing_url(url)
    # Locations and distinct posting IDs must not collapse into a company/title.
    return "|".join(str(row.get(k) or "").casefold().strip()
                    for k in ("company", "role_title", "location"))


def _dated(path: Path, since: str) -> bool:
    match = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", path.name)
    return bool(match and "-".join(match.groups()) >= since)


def _rows(payload: dict) -> list[dict]:
    return [r for field in ("cards", "jobs", "results")
            for r in payload.get(field, []) if isinstance(r, dict)]


def usable_jd(row: dict) -> bool:
    text = str(row.get("jd_text") or row.get("description") or "").strip()
    return len(text) >= 200 and not _jd_quality_issue(text)

def completed_review(score: dict) -> bool:
    response = str(score.get("_raw_response") or "")
    if str(score.get('review_method') or '').startswith('direct saved-JD review'):
        return score.get('decision') in {'Proceed', 'Reject', 'Deprioritize', 'Unsure'}
    if score.get("status") == "cached_skip" and "cache=review_cache" in str(score.get("notes") or ""):
        return score.get("decision") in {"Reject", "Deprioritize"}
    if response.startswith(("Pre-filter", "Discovery", "Timing", "Error:")):
        return False
    return bool(response.strip()) and score.get("decision") in {
        "Proceed", "Reject", "Deprioritize", "Unsure"
    }

def current_prefilter_rejection(job: dict, score: dict) -> str:
    """Recheck deterministic rejections locally instead of requesting paid scoring again."""
    if score.get('decision') != 'Reject' or not str(score.get('_raw_response') or '').startswith('Pre-filter'):
        return ''
    from discovery.auto.scorer import score_job
    checked = score_job(dict(job), None, '', '', verbose=False)
    return str(checked.get('fit_rationale') or '') if checked.get('decision') == 'Reject' else ''


def _current_classification(row: dict) -> dict:
    fresh = dict(row)
    for key in ("classification", "discovery_disposition", "discovery_reason",
                "reject_reason", "role_family"):
        fresh.pop(key, None)
    fresh["role_title"] = row.get("role_title") or row.get("title") or ""
    return classify_discovery_job_offline(fresh, default_lane="B")


def build_audit(since: str, out_dir: Path | None = None) -> Path:
    logs = ROOT / "discovery/auto/logs"
    validation = ROOT / "discovery/source_validation"
    raw_paths = sorted(set(
        p for pattern in ("linkedin_live_raw*.json", "jobspy_breadth_raw*.json")
        for p in logs.glob(pattern) if _dated(p, since)
    ))
    # These derived inputs can contain a card from an interrupted capture that
    # did not get a final raw artifact. Merge them, never use only the latest.
    raw_paths += sorted(p for p in validation.glob("*linkedin-2027-selected-raw.json")
                        if _dated(p, since))
    records: dict[str, dict] = {}
    for path in raw_paths:
        payload = json.loads(path.read_text())
        for raw in _rows(payload):
            row = dict(raw)
            row["role_title"] = row.get("role_title") or row.get("title") or ""
            key = listing_key(row)
            if not key or not row["role_title"]:
                continue
            entry = records.setdefault(key, {"job": row, "artifacts": set(),
                                             "queries": set(), "score": None})
            entry["artifacts"].add(str(path))
            query = row.get("search_term") or row.get("jobspy_search_term")
            if query:
                entry["queries"].add(query)
            if row.get("retrieval_status") == "retrieved":
                entry["availability"] = row.get("listing_availability")
            if usable_jd(row) and (not usable_jd(entry["job"]) or
                                  len(str(row.get("jd_text", ""))) >
                                  len(str(entry["job"].get("jd_text", "")))):
                entry["job"] = row
    score_paths = sorted((p for p in logs.glob("*scored*.json") if _dated(p, since)),
                         key=lambda path: path.stat().st_mtime)
    for path in score_paths:
        payload = json.loads(path.read_text())
        for score in payload.get("jobs", []):
            keys = {listing_key(score)}
            # A recovered employer JD may link back to the original LinkedIn ID.
            match = re.search(r"LinkedIn job (\d+)", str(score.get("notes") or ""))
            if match:
                keys.add("li:" + match.group(1))
            for key in keys:
                entry = records.get(key)
                if entry is None:
                    continue
                if usable_jd(score) and not usable_jd(entry["job"]):
                    entry["job"] = {**score, "url": entry["job"].get("url")}
                if not payload.get("dry_run") and (
                    completed_review(score) or not completed_review(entry["score"] or {})
                ):
                    entry["score"] = {**score, "artifact": str(path)}
    import jobs as tracker
    tracked = {listing_key(dict(r)): dict(r) for _, r in tracker.load_jobs().iterrows()}
    tracked_titles = {
        (str(r.get("company", "")).casefold(), str(r.get("role_title", "")).casefold()): dict(r)
        for _, r in tracker.load_jobs().iterrows()
    }
    blocklist = tracker._load_blocklist()
    # Reposted cards often already have a JD from an earlier run. Reuse only
    # exact posting identities; never substitute a different city by title.
    missing = {key for key, entry in records.items() if not usable_jd(entry["job"])}
    for key in list(missing):
        existing = tracked.get(key, {})
        folder = str(existing.get("folder_path") or "")
        if folder and (Path(folder) / "jd.txt").is_file():
            text = (Path(folder) / "jd.txt").read_text(errors="replace")
            candidate = {**records[key]["job"], "jd_text": text}
            if usable_jd(candidate):
                records[key]["job"] = candidate
                records[key]["artifacts"].add(str(Path(folder) / "jd.txt"))
                missing.remove(key)
    history = sorted(set(
        p for pattern in ("*raw*.json", "*scored*.json")
        for p in logs.glob(pattern) if not _dated(p, since)
    ), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in history:
        if not missing:
            break
        try:
            payload = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        for old in _rows(payload):
            key = listing_key(old)
            if key in missing and usable_jd(old):
                records[key]["job"] = {**records[key]["job"],
                                       "jd_text": old.get("jd_text") or old.get("description")}
                records[key]["artifacts"].add(str(path))
                missing.remove(key)
    templates = national_recruitment_templates(
        entry["job"] for entry in records.values() if usable_jd(entry["job"])
    )
    for key, template in templates.items():
        template["advertised_postings"] = [
            {"url": entry["job"].get("url"), "advertised_location": entry["job"].get("location")}
            for entry in records.values() if role_group_key(entry["job"]) == key
        ]
    rows, score_input, hydrate_input = [], [], []
    for key, entry in sorted(records.items()):
        job = entry["job"]
        title = job["role_title"]
        selected, title_reason = classify_title(title, next(iter(entry["queries"]), ""))
        plausible = selected or title_reason.startswith("unsure_")
        full_jd = usable_jd(job)
        score = entry["score"] or {}
        existing = tracked.get(key, {})
        related = tracked_titles.get((str(job.get("company", "")).casefold(), title.casefold()), {})
        model_reviewed = completed_review(score)
        template = templates.get(role_group_key(job))
        grouped_variant = template and canonical_listing_url(job.get("url", "")) != canonical_listing_url(template["representative_url"])
        if grouped_variant:
            state, reason = "grouped_location_variant", (
                f"National recruitment ad: identical JD verified on "
                f"{template['identical_description_count']} posting IDs; "
                f"review representative {template['representative_url']}. "
                "Advertised location and original URL retained."
            )
        elif entry.get("availability") == "closed":
            state, reason = "listing_closed", "Public listing explicitly says no longer accepting applications"
        elif existing.get("status") in {"generated", "promoted"}:
            state, reason = "tracked_prepared", str(existing.get("status"))
        elif existing.get("status") in {"applied", "closed", "parked", "skipped"}:
            state, reason = "tracked_terminal", str(existing.get("status"))
        elif not full_jd:
            excluded, scope_reason = pre_filter_discovery_scope(title, "B")
            if excluded or not plausible:
                state, reason = "title_excluded", scope_reason or title_reason
            else:
                state, reason = "needs_jd", "Captured card has no usable JD"
        else:
            current = _current_classification(job)
            disposition = current.get("classification")
            reason = current.get("reject_reason") or current.get("discovery_reason") or ""
            if disposition == "reject":
                state = "rule_rejected"
            elif prefilter_reason := current_prefilter_rejection(current, score):
                state, reason = "rule_rejected", prefilter_reason
            elif existing.get("status") in {"applied", "closed", "parked", "skipped"}:
                state, reason = "tracked_terminal", str(existing.get("status"))
            elif model_reviewed:
                state = "needs_review" if score.get("decision") == "Unsure" else "scored"
                reason = score.get("fit_rationale") or ""
            elif existing.get("status") == "queued" and existing.get("fit_score"):
                state, reason = "tracked_queued", "Already in canonical tracker"
            elif tracker._is_blocklisted(str(job.get("company") or ""), blocklist):
                state, reason = "needs_review", "Company is on the user's blocklist"
            elif related:
                state, reason = "needs_review", (
                    "Different posting ID matches an existing tracker title; check distinct location/requisition. "
                    f"Existing status: {related.get('status')}, score: {related.get('fit_score')}"
                )
            elif disposition == "keep":
                state = "needs_score"
                score_input.append(current)
            else:
                state = "needs_review"
        if state == "needs_jd":
            hydrate_input.append({
                **job, "title": title,
                "search_term": next(iter(entry["queries"]), ""),
                "time_filter": job.get("time_filter") or "r604800",
            })
        rows.append({
            "listing_key": key, "company": job.get("company", ""),
            "role_title": title, "location": job.get("location", ""),
            "url": job.get("url", ""), "state": state, "reason": reason,
            "has_jd": full_jd, "score": score.get("fit_score"),
            "previous_decision": score.get("decision", ""),
            "queries": sorted(entry["queries"]), "artifacts": sorted(entry["artifacts"]),
        })
    counts = dict(Counter(r["state"] for r in rows))
    query_attempts = {}
    for path in sorted((ROOT / "discovery/auto/checkpoints").glob("*/manifest.json"),
                       key=lambda p: p.stat().st_mtime):
        payload = json.loads(path.read_text())
        if str(payload.get("started_at", ""))[:10] < since:
            continue
        for query in payload.get("queries", []):
            query_attempts[query.get("query_id")] = {"artifact": str(path), **query}
    source_gaps = [q for q in query_attempts.values() if q.get("status") != "completed"]
    source_attempts = {}
    for path in sorted(validation.glob("*daily-engine-run-manifest.json"),
                       key=lambda p: p.stat().st_mtime):
        if not _dated(path, since):
            continue
        manifest = json.loads(path.read_text())
        for source, stage in (manifest.get("stage_metrics") or {}).items():
            if source in {"linkedin", "twelvetwenty", "handshake", "jobspy", "startup_apply"} and stage.get("status") != "skipped":
                source_attempts[source] = {"source": source, "artifact": str(path), **stage}
    source_gaps.extend(s for s in source_attempts.values()
                       if s.get("status") not in {"ran", "completed"})
    for path in sorted(logs.glob("linkedin_live_progress_*.json")):
        if not _dated(path, since):
            continue
        progress = json.loads(path.read_text())
        if progress.get("status") != "complete" or (
            progress.get("ui_observed_count") is None and
            int(progress.get("current_page_index") or 0) >= 9
        ):
            source_gaps.append({
                "source": "LinkedIn", "artifact": str(path),
                "status": "unverified_end_of_results",
                "reason": "Interrupted/capped search or no verified end of results",
            })
    out_dir = out_dir or validation
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = out_dir / f"{stamp}-discovery-coverage"
    json_path = prefix.with_suffix(".json")
    pending = sum(counts.get(state, 0) for state in UNFINISHED)
    payload = {"since": since, "generated_at": datetime.now().isoformat(),
               "status": "incomplete" if pending or source_gaps else "reconciled",
               "unique_captured_listings": len(rows), "capture_artifacts": len(raw_paths),
               "counts": counts, "unfinished": pending, "source_gaps": source_gaps,
               "national_recruitment_groups": list(templates.values()),
               "rows": rows}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    with prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as stream:
        columns = ["state", "company", "role_title", "location", "url", "reason",
                   "has_jd", "score", "previous_decision", "queries", "artifacts"]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    Path(str(prefix) + "-score-input.json").write_text(json.dumps(
        {"jobs": score_input, "coverage_audit": str(json_path)}, indent=2))
    Path(str(prefix) + "-hydrate-input.json").write_text(json.dumps(
        {"cards": hydrate_input, "count": len(hydrate_input),
         "coverage_audit": str(json_path)}, indent=2))
    lines = ["# Discovery coverage", "", f"Captured since {since}: {len(rows)} unique listings.",
             f"Status: **{payload['status']}**. {pending} listings still need work.",
             "", *[f"- {key}: {value}" for key, value in sorted(counts.items())],
             "", "## Eligible listings awaiting a score", ""]
    lines += [f"- [{r['company']} — {r['role_title']}]({r['url']})"
              for r in rows if r["state"] == "needs_score"]
    lines += ["", "The CSV contains every captured listing and its reason. "
              "Source failures and unprocessed cards are unresolved coverage, not zero results."]
    prefix.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=(datetime.now() - timedelta(days=7)).date().isoformat())
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    path = build_audit(args.since, args.out_dir)
    summary = json.loads(path.read_text())
    print(f"Coverage audit: {path}")
    print(json.dumps({k: summary[k] for k in ("status", "unique_captured_listings",
                                             "counts", "unfinished")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
