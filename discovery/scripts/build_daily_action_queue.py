#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE_VALIDATION_DIR = ROOT / "discovery" / "source_validation"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"
CURRENT_APPLY_QUEUE_JSON = ROOT / "apps" / "Apply queues" / "current_apply_queue" / "priority_order.json"
OUTREACH_WORKSPACE = ROOT.parent / "Outreach" / "workspace"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs as resume_jobs  # noqa: E402
from discovery.scripts.build_daily_source_dashboard import (  # noqa: E402
    _collect_jobs,
    _collect_relationship_targets,
    _latest_file,
    _load_json,
)


TERMINAL_STATUSES = {"applied", "closed", "parked", "rejected", "skip", "skipped"}
ACTIVE_APP_STATUSES = {"queued", "promoted", "generated"}
RELATIONSHIP_DOMAIN_RE = re.compile(
    r"\b(ai|genai|data|developer|devtool|platform|infra|fintech|health|healthtech|"
    r"robotics|marketplace|productivity|b2b|saas|security|analytics|automation)\b",
    re.I,
)
ENTERPRISE_COMPANY_RE = re.compile(
    r"\b(bank|credit union|wells fargo|square|sofi|toast|taboola|magnite)\b",
    re.I,
)


@dataclass(frozen=True)
class ExistingJobState:
    company: str
    role_title: str
    status: str
    fit_score: str
    row_id: str
    url: str
    source: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _norm_url(value: Any) -> str:
    return str(value or "").strip().lower().rstrip("/")


def _url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode()).hexdigest()


def _parse_int(value: Any) -> int | None:
    match = re.search(r"([\d,]+)", str(value or ""))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_batch_year(value: Any) -> int | None:
    match = re.search(r"(20\d{2})", str(value or ""))
    return int(match.group(1)) if match else None


def _latest_daily_artifacts() -> tuple[Path, Path]:
    return (
        _latest_file("*source-breadth-filtered.json", SOURCE_VALIDATION_DIR),
        _latest_file("*startup-source-report.json", SOURCE_VALIDATION_DIR),
    )


def _load_jobs_state() -> tuple[dict[str, ExistingJobState], dict[str, ExistingJobState], dict[str, ExistingJobState]]:
    df = resume_jobs.load_jobs()
    by_hash: dict[str, ExistingJobState] = {}
    by_url: dict[str, ExistingJobState] = {}
    by_company_role: dict[str, ExistingJobState] = {}
    for _, row in df.fillna("").iterrows():
        state = ExistingJobState(
            company=_clean(row.get("company")),
            role_title=_clean(row.get("role_title")),
            status=_norm(row.get("status")),
            fit_score=_clean(row.get("fit_score")),
            row_id=_clean(row.get("id")),
            url=_clean(row.get("url")),
            source=_clean(row.get("source")),
        )
        url_hash = _clean(row.get("url_hash"))
        if url_hash:
            by_hash[url_hash.lower()] = state
        if state.url:
            by_url[_norm_url(state.url)] = state
        if state.company and state.role_title:
            by_company_role[f"{_norm(state.company)}|{_norm(state.role_title)}"] = state
    return by_hash, by_url, by_company_role


def _find_existing_job(item: dict[str, Any], indexes: tuple[dict[str, ExistingJobState], ...]) -> ExistingJobState | None:
    by_hash, by_url, by_company_role = indexes
    url = _clean(item.get("url"))
    if url:
        state = by_hash.get(_url_hash(url))
        if state:
            return state
        state = by_url.get(_norm_url(url))
        if state:
            return state
    key = f"{_norm(item.get('company'))}|{_norm(item.get('role_title'))}"
    return by_company_role.get(key)


def _load_current_apply_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_outreach_csv(name: str) -> list[dict[str, str]]:
    path = OUTREACH_WORKSPACE / name
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _outreach_state() -> dict[str, dict[str, Any]]:
    orgs = _load_outreach_csv("organizations.csv")
    contacts = _load_outreach_csv("contacts.csv")
    touchpoints = _load_outreach_csv("touchpoints.csv")
    org_by_id: dict[str, dict[str, Any]] = {}
    by_company: dict[str, dict[str, Any]] = {}
    for org in orgs:
        org_id = _clean(org.get("organization_id"))
        company = _clean(org.get("name"))
        if not org_id or not company:
            continue
        record = {
            "organization_id": org_id,
            "company": company,
            "organization_type": _clean(org.get("organization_type")),
            "target_lists": _clean(org.get("target_lists")),
            "contact_count": 0,
            "linkedin_contact_count": 0,
            "touchpoint_count": 0,
        }
        org_by_id[org_id] = record
        by_company[_norm(company)] = record

    for contact in contacts:
        org_id = _clean(contact.get("organization_id"))
        record = org_by_id.get(org_id)
        if not record:
            continue
        record["contact_count"] += 1
        if _clean(contact.get("source_kind")).lower() == "linkedin":
            record["linkedin_contact_count"] += 1

    for touchpoint in touchpoints:
        org_id = _clean(touchpoint.get("organization_id"))
        record = org_by_id.get(org_id)
        if record:
            record["touchpoint_count"] += 1
    return by_company


def _is_blocklisted(company: str, blocklist: list[str]) -> bool:
    return resume_jobs._is_blocklisted(company, blocklist)


def _company_relationship_score(item: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons = list(item.get("reasons") or [])
    text = " ".join(
        [
            _clean(item.get("organization_name")),
            _clean(item.get("signal_title")),
            _clean(item.get("description")),
            " ".join(_clean(tag) for tag in item.get("tags") or []),
        ]
    )
    source_id = _clean(item.get("source_id") or item.get("lane_source"))
    company = _clean(item.get("organization_name"))
    jobs_url = _clean(item.get("jobs_url"))
    team_size = _parse_int(item.get("team_size"))
    batch_year = _parse_batch_year(item.get("batch"))

    if source_id.startswith("yc_") or "yc_" in source_id:
        score += 2.3
    elif "builtin" in source_id:
        score += 1.2
    elif "linkedin_breadth" in source_id:
        score += 1.2

    if jobs_url or any("active hiring" in reason.lower() for reason in reasons):
        score += 2.0
    if any("high-signal company" in reason.lower() for reason in reasons):
        score += 3.0
    if any("target role" in reason.lower() for reason in reasons):
        score += 1.0
    if any("operator-style product role" in reason.lower() for reason in reasons):
        score += 1.2
    if any("target geography" in reason.lower() for reason in reasons):
        score += 1.2
    if RELATIONSHIP_DOMAIN_RE.search(text):
        score += 1.7
        reasons.append("domain/profile fit")
    if _clean(item.get("signal_title")):
        score += 0.4
        reasons.append("job-signal adjacency")

    if team_size is not None:
        if team_size <= 50:
            score += 1.7
            reasons.append("very small-team access")
        elif team_size <= 250:
            score += 1.2
        elif team_size <= 1000:
            score += 0.4
            reasons.append("larger startup but still reachable")
        else:
            score -= 2.5
            reasons.append("enterprise-size penalty")

    if batch_year is not None:
        if batch_year >= date.today().year - 1:
            score += 1.1
            reasons.append("recent YC batch")
        elif batch_year <= date.today().year - 8:
            score -= 0.5
            reasons.append("older YC batch")

    if ENTERPRISE_COMPANY_RE.search(company):
        score -= 1.2
        reasons.append("less founder-led relationship fit")

    return max(0.0, min(10.0, round(score, 1))), list(dict.fromkeys(reasons))


def _dedupe_app_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        company = _norm(item.get("company"))
        role = _norm(item.get("role_title"))
        url = _norm_url(item.get("url"))
        key = f"{company}|{role}" if company and role else url
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _choose_relationship_today(
    actionable: list[dict[str, Any]],
    today_limit: int,
    max_per_source: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if today_limit <= 0:
        return [], actionable

    picked: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for row in actionable:
        source = _clean(row.get("source"))
        if max_per_source > 0 and source_counts[source] >= max_per_source:
            continue
        picked.append(row)
        source_counts[source] += 1
        if len(picked) >= today_limit:
            break

    if len(picked) < today_limit:
        picked_ids = {id(row) for row in picked}
        for row in actionable:
            if id(row) in picked_ids:
                continue
            picked.append(row)
            if len(picked) >= today_limit:
                break

    picked_ids = {id(row) for row in picked}
    buffer = [row for row in actionable if id(row) not in picked_ids]
    return picked, buffer


def _relationship_quality_ok(row: dict[str, Any]) -> bool:
    if row["relationship_score"] < 5.0:
        return False
    reasons = " ".join(row.get("reasons") or []).lower()
    return "enterprise-size penalty" not in reasons or row["relationship_score"] >= 6.5


def _source_label_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(_clean(item.get("source")) for item in items if _clean(item.get("source"))).most_common())


def _dedupe_relationship_targets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = _norm(item.get("company") or item.get("organization_name"))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _app_item(company: str, role: str, url: str, source: str, reasons: list[str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "company": company,
        "role_title": role,
        "url": url,
        "source": source,
        "reasons": reasons,
    }
    if extra:
        item.update(extra)
    return item


def _bucket_source_app_candidates(
    *,
    app_candidates: list[dict[str, Any]],
    job_indexes: tuple[dict[str, ExistingJobState], ...],
    outreach_by_company: dict[str, dict[str, Any]],
    blocklist: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    score_for_application: list[dict[str, Any]] = []
    application_plus_outreach: list[dict[str, Any]] = []
    follow_up: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in app_candidates:
        company = _clean(item.get("company"))
        role = _clean(item.get("role_title"))
        url = _clean(item.get("url"))
        lane_source = _clean(item.get("lane_source"))
        if _is_blocklisted(company, blocklist):
            skipped.append(_app_item(company, role, url, lane_source, ["blocklisted_company"], {"skip_reason": "blocklisted_company"}))
            continue
        existing = _find_existing_job(item, job_indexes)
        outreach_state = outreach_by_company.get(_norm(company), {})
        has_touchpoint = int(outreach_state.get("touchpoint_count") or 0) > 0
        has_linkedin_contacts = int(outreach_state.get("linkedin_contact_count") or 0) > 0
        if existing:
            extra = {
                "existing_job_id": existing.row_id,
                "existing_status": existing.status,
                "existing_fit_score": existing.fit_score,
            }
            if existing.status == "applied":
                bucket = follow_up if has_touchpoint else application_plus_outreach
                bucket.append(_app_item(company, role, url, lane_source, ["already_applied", *item.get("reasons", [])], extra))
            elif existing.status in ACTIVE_APP_STATUSES:
                bucket = follow_up if has_touchpoint else application_plus_outreach
                reason = "already_in_apply_flow"
                if has_linkedin_contacts:
                    reason = "contacts_exist_for_active_application"
                bucket.append(_app_item(company, role, url, lane_source, [reason, *item.get("reasons", [])], extra))
            elif existing.status in TERMINAL_STATUSES:
                skipped.append(_app_item(company, role, url, lane_source, [f"existing_terminal_status={existing.status}"], extra))
            else:
                follow_up.append(_app_item(company, role, url, lane_source, [f"existing_status={existing.status}"], extra))
            continue
        score_for_application.append(_app_item(company, role, url, lane_source, list(item.get("reasons") or []), {"recommended_action": "score_then_route"}))
    return score_for_application, application_plus_outreach, follow_up, skipped


def _bucket_current_apply_queue(
    *,
    current_queue: list[dict[str, Any]],
    outreach_by_company: dict[str, dict[str, Any]],
    blocklist: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    application_only: list[dict[str, Any]] = []
    application_plus_outreach: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in current_queue:
        company = _clean(item.get("company"))
        role = _clean(item.get("role_title"))
        url = _clean(item.get("url"))
        if _is_blocklisted(company, blocklist):
            skipped.append(_app_item(company, role, url, "current_apply_queue", ["blocklisted_company"], {"skip_reason": "blocklisted_company"}))
            continue
        outreach_state = outreach_by_company.get(_norm(company), {})
        touchpoints = int(outreach_state.get("touchpoint_count") or 0)
        linkedin_contacts = int(outreach_state.get("linkedin_contact_count") or 0)
        extra = {
            "queue_rank": item.get("priority_rank"),
            "fit_score": item.get("fit_score"),
            "status": item.get("status"),
            "folder_path": item.get("folder_path"),
            "outreach_contact_count": outreach_state.get("contact_count", 0),
            "outreach_touchpoint_count": touchpoints,
        }
        if touchpoints == 0:
            application_plus_outreach.append(
                _app_item(company, role, url, "current_apply_queue", ["active_application_needs_outreach"], extra)
            )
        elif linkedin_contacts == 0:
            application_plus_outreach.append(
                _app_item(company, role, url, "current_apply_queue", ["non_linkedin_history_but_no_linkedin_contacts"], extra)
            )
        else:
            application_only.append(_app_item(company, role, url, "current_apply_queue", ["application_ready"], extra))
    return application_only, application_plus_outreach, skipped


def _bucket_relationship_targets(
    *,
    relationship_targets: list[dict[str, Any]],
    outreach_by_company: dict[str, dict[str, Any]],
    blocklist: list[str],
    today_limit: int,
    max_per_source: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    actionable: list[dict[str, Any]] = []
    follow_up: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in relationship_targets:
        company = _clean(item.get("organization_name"))
        if not company:
            continue
        if _is_blocklisted(company, blocklist):
            skipped.append({"company": company, "skip_reason": "blocklisted_company", "source": item.get("lane_source")})
            continue
        score, reasons = _company_relationship_score(item)
        state = outreach_by_company.get(_norm(company), {})
        touchpoints = int(state.get("touchpoint_count") or 0)
        linkedin_contacts = int(state.get("linkedin_contact_count") or 0)
        row = {
            "company": company,
            "relationship_score": score,
            "company_url": _clean(item.get("company_url") or item.get("source_item_url") or item.get("url")),
            "city": _clean(item.get("city") or item.get("location")),
            "source": _clean(item.get("lane_source")),
            "signal_title": _clean(item.get("signal_title")),
            "reasons": reasons,
            "existing_contacts": state.get("contact_count", 0),
            "existing_linkedin_contacts": linkedin_contacts,
            "existing_touchpoints": touchpoints,
            "recommended_people_to_find": 15,
            "recommended_channel": "linkedin_first_email_second",
        }
        if touchpoints > 0:
            row["recommended_action"] = "follow_up_or_skip_recent"
            follow_up.append(row)
            continue
        if not _relationship_quality_ok(row):
            row["skip_reason"] = "low_relationship_fit"
            skipped.append(row)
            continue
        actionable.append(row)
    actionable = _dedupe_relationship_targets(actionable)
    actionable.sort(key=lambda row: (row["relationship_score"], row["company"].lower()), reverse=True)
    today, buffer = _choose_relationship_today(actionable, today_limit, max_per_source)
    for row in today:
        row["recommended_action"] = "run_linkedin_company_pipeline"
    for row in buffer:
        row["recommended_action"] = "buffer_for_later"
    return today, buffer, [*follow_up, *skipped]


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Daily Action Queue",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Source Mix", ""])
    for key, counts in payload.get("source_counts", {}).items():
        lines.append(f"- {key}: {counts}")

    sections = [
        ("Score For Application", "score_for_application"),
        ("Application Plus Outreach", "application_plus_outreach"),
        ("Application Only", "application_only"),
        ("Outreach Only Today", "outreach_only_today"),
        ("Follow Up", "follow_up"),
        ("Relationship Buffer", "relationship_buffer"),
        ("Skipped/Internal", "skipped_internal"),
    ]
    for title, key in sections:
        items = payload[key]
        lines.extend(["", f"## {title}", ""])
        if not items:
            lines.append("- None")
            continue
        for item in items[:40]:
            if key in {"outreach_only_today", "relationship_buffer"}:
                lines.append(
                    f"- [{item.get('relationship_score', '-')}/10] {item.get('company')} | {item.get('source')} | {item.get('company_url')}"
                )
                lines.append(f"  - {', '.join(item.get('reasons') or [])}")
                continue
            lines.append(f"- {item.get('company')} | {item.get('role_title', '')} | {item.get('url', '')}")
            reason = ", ".join(item.get("reasons") or [])
            if reason:
                lines.append(f"  - {reason}")

    lines.extend(["", "## Suggested Commands", ""])
    for command in payload["suggested_commands"]:
        lines.append(f"```bash\n{command}\n```")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _link(url: Any, label: str = "Open") -> str:
    clean = _clean(url)
    if not clean:
        return ""
    return f'<a href="{_esc(clean)}">{_esc(label)}</a>'


def _reason_chips(reasons: list[str]) -> str:
    if not reasons:
        return ""
    chips = "".join(f'<span class="chip">{_esc(reason)}</span>' for reason in reasons[:8])
    return f'<div class="chips">{chips}</div>'


def _app_card(item: dict[str, Any]) -> str:
    meta = [
        _esc(item.get("source")),
        f"rank {item.get('queue_rank')}" if item.get("queue_rank") else "",
        f"fit {item.get('fit_score')}" if item.get("fit_score") else "",
        f"contacts {item.get('outreach_contact_count')}" if item.get("outreach_contact_count") not in (None, "") else "",
        f"touches {item.get('outreach_touchpoint_count')}" if item.get("outreach_touchpoint_count") not in (None, "") else "",
    ]
    meta_text = " / ".join(value for value in meta if value)
    return f"""
      <article class="item app-item">
        <div class="item-main">
          <h3>{_esc(item.get('company'))}</h3>
          <p class="role">{_esc(item.get('role_title'))}</p>
          <p class="meta">{meta_text}</p>
          {_reason_chips(item.get('reasons') or [])}
        </div>
        <div class="item-actions">{_link(item.get('url'), 'Job')}</div>
      </article>
    """


def _relationship_card(item: dict[str, Any]) -> str:
    score = item.get("relationship_score", "-")
    meta = " / ".join(value for value in [_esc(item.get("source")), _esc(item.get("city"))] if value)
    return f"""
      <article class="item relationship-item">
        <div class="score">{_esc(score)}<span>/10</span></div>
        <div class="item-main">
          <h3>{_esc(item.get('company'))}</h3>
          <p class="meta">{meta}</p>
          {_reason_chips(item.get('reasons') or [])}
        </div>
        <div class="item-actions">{_link(item.get('company_url'), 'Company')}</div>
      </article>
    """


def _render_items(payload: dict[str, Any], key: str) -> str:
    relationship = key in {"outreach_only_today", "relationship_buffer"}
    renderer = _relationship_card if relationship else _app_card
    items = payload.get(key) or []
    if not items:
        return '<p class="empty">None</p>'
    return "\n".join(renderer(item) for item in items)


def _source_mix(payload: dict[str, Any]) -> str:
    rows: list[str] = []
    for bucket, counts in (payload.get("source_counts") or {}).items():
        for source, count in counts.items():
            rows.append(
                f"<tr><td>{_esc(bucket)}</td><td>{_esc(source)}</td><td>{_esc(count)}</td></tr>"
            )
    return "\n".join(rows) or '<tr><td colspan="3">No source counts</td></tr>'


def _write_html(path: Path, payload: dict[str, Any]) -> None:
    counts = payload.get("counts") or {}
    sections = [
        ("Score For Application", "score_for_application"),
        ("Application Plus Outreach", "application_plus_outreach"),
        ("Application Only", "application_only"),
        ("Outreach Only Today", "outreach_only_today"),
        ("Follow Up", "follow_up"),
        ("Relationship Buffer", "relationship_buffer"),
        ("Skipped/Internal", "skipped_internal"),
    ]
    count_cards = "\n".join(
        f'<div class="stat"><span>{_esc(value)}</span><small>{_esc(key.replace("_", " "))}</small></div>'
        for key, value in counts.items()
    )
    nav = "\n".join(
        f'<a href="#{_esc(key)}">{_esc(title)} <span>{_esc(counts.get(key, 0))}</span></a>'
        for title, key in sections
    )
    section_html = "\n".join(
        f"""
        <section id="{_esc(key)}">
          <div class="section-head">
            <h2>{_esc(title)}</h2>
            <span>{_esc(counts.get(key, 0))}</span>
          </div>
          <div class="items">{_render_items(payload, key)}</div>
        </section>
        """
        for title, key in sections
    )
    commands = "\n".join(f"<code>{_esc(command)}</code>" for command in payload.get("suggested_commands") or [])

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Action Queue</title>
  <style>
    :root {{
      --paper: #fbfaf7;
      --panel: #ffffff;
      --ink: #1d2525;
      --muted: #66706d;
      --line: #d9dfda;
      --teal: #0f766e;
      --gold: #9a6700;
      --rose: #b4235a;
      --blue: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 28px clamp(18px, 4vw, 48px) 18px;
      border-bottom: 1px solid var(--line);
      background: #fffefa;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 30px; line-height: 1.1; letter-spacing: 0; }}
    .generated {{ color: var(--muted); margin-top: 8px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 10px;
      margin-top: 22px;
      max-width: 1180px;
    }}
    .stat {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px;
    }}
    .stat span {{ display: block; font-size: 24px; font-weight: 750; }}
    .stat small {{ color: var(--muted); text-transform: capitalize; }}
    nav {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 10px clamp(18px, 4vw, 48px);
      border-bottom: 1px solid var(--line);
      background: rgba(251, 250, 247, .96);
      backdrop-filter: blur(10px);
    }}
    nav a {{
      white-space: nowrap;
      color: var(--ink);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 11px;
      background: var(--panel);
    }}
    nav span {{ color: var(--teal); font-weight: 700; }}
    main {{ padding: 22px clamp(18px, 4vw, 48px) 48px; }}
    section {{ max-width: 1180px; margin: 0 auto 30px; }}
    .section-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 10px;
    }}
    .section-head h2 {{ font-size: 20px; }}
    .section-head span {{ color: var(--muted); font-weight: 700; }}
    .items {{ display: grid; gap: 10px; }}
    .item {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
      border: 1px solid var(--line);
      border-left: 4px solid var(--teal);
      border-radius: 8px;
      background: var(--panel);
      padding: 14px;
    }}
    .relationship-item {{ grid-template-columns: 72px minmax(0, 1fr) auto; border-left-color: var(--gold); }}
    #skipped_internal .item {{ border-left-color: var(--rose); }}
    #score_for_application .item {{ border-left-color: var(--blue); }}
    .score {{
      font-size: 22px;
      font-weight: 800;
      color: var(--gold);
      line-height: 1;
    }}
    .score span {{ font-size: 12px; color: var(--muted); font-weight: 650; }}
    h3 {{ font-size: 16px; line-height: 1.25; }}
    .role {{ margin-top: 3px; color: var(--ink); }}
    .meta {{ margin-top: 5px; color: var(--muted); font-size: 12px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
    .chip {{
      border: 1px solid #dfe6e0;
      background: #f5f7f2;
      color: #35413d;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
    }}
    .item-actions a {{
      display: inline-flex;
      min-width: 74px;
      justify-content: center;
      color: #0f5f57;
      text-decoration: none;
      border: 1px solid #abcfc8;
      border-radius: 7px;
      padding: 7px 10px;
      font-weight: 700;
    }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      color: var(--muted);
      background: rgba(255, 255, 255, .55);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); }}
    th {{ color: var(--muted); font-size: 12px; }}
    .commands {{ display: grid; gap: 8px; }}
    code {{
      display: block;
      white-space: pre-wrap;
      word-break: break-word;
      background: #eff3ee;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      color: #21302d;
    }}
    @media (max-width: 720px) {{
      h1 {{ font-size: 24px; }}
      .item, .relationship-item {{ grid-template-columns: 1fr; }}
      .score {{ font-size: 18px; }}
      .item-actions a {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Daily Action Queue</h1>
    <p class="generated">Generated {_esc(payload.get('generated_at'))}</p>
    <div class="stats">{count_cards}</div>
  </header>
  <nav>{nav}</nav>
  <main>
    {section_html}
    <section id="source-mix">
      <div class="section-head"><h2>Source Mix</h2></div>
      <table>
        <thead><tr><th>Bucket</th><th>Source</th><th>Count</th></tr></thead>
        <tbody>{_source_mix(payload)}</tbody>
      </table>
    </section>
    <section id="commands">
      <div class="section-head"><h2>Suggested Commands</h2></div>
      <div class="commands">{commands}</div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the gated daily action queue from source artifacts and live state.")
    parser.add_argument("--source-breadth", type=Path)
    parser.add_argument("--startup-source-report", type=Path)
    parser.add_argument("--current-apply-queue", type=Path, default=CURRENT_APPLY_QUEUE_JSON)
    parser.add_argument("--relationship-today", type=int, default=8)
    parser.add_argument("--relationship-max-per-source", type=int, default=4)
    parser.add_argument("--out-dir", type=Path, default=SOURCE_VALIDATION_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_breadth_path, startup_report_path = (
        (args.source_breadth, args.startup_source_report)
        if args.source_breadth and args.startup_source_report
        else _latest_daily_artifacts()
    )
    source_breadth = _load_json(source_breadth_path)
    startup_report = _load_json(startup_report_path)
    app_candidates = _collect_jobs(source_breadth, startup_report, ("app_score_now",))
    relationship_targets = _collect_relationship_targets(source_breadth, startup_report)
    current_queue = _load_current_apply_queue(args.current_apply_queue)
    job_indexes = _load_jobs_state()
    outreach_by_company = _outreach_state()
    blocklist = resume_jobs._load_blocklist()

    source_score_for_application, source_app_plus_outreach, source_follow_up, source_skipped = _bucket_source_app_candidates(
        app_candidates=app_candidates,
        job_indexes=job_indexes,
        outreach_by_company=outreach_by_company,
        blocklist=blocklist,
    )
    application_only, queue_app_plus_outreach, queue_skipped = _bucket_current_apply_queue(
        current_queue=current_queue,
        outreach_by_company=outreach_by_company,
        blocklist=blocklist,
    )
    outreach_today, relationship_buffer, relationship_not_now = _bucket_relationship_targets(
        relationship_targets=relationship_targets,
        outreach_by_company=outreach_by_company,
        blocklist=blocklist,
        today_limit=max(args.relationship_today, 0),
        max_per_source=max(args.relationship_max_per_source, 0),
    )

    application_plus_outreach = _dedupe_app_items([*queue_app_plus_outreach, *source_app_plus_outreach])
    follow_up = [*source_follow_up, *[item for item in relationship_not_now if item.get("recommended_action") == "follow_up_or_skip_recent"]]
    skipped_internal = [
        *source_skipped,
        *queue_skipped,
        *[item for item in relationship_not_now if item.get("skip_reason")],
    ]

    suggested_outreach_companies = [item["company"] for item in outreach_today[:3]]
    suggested_commands = [
        "./discovery/scripts/run_linkedin_discovery.sh 24h",
        "venv/bin/python discovery/auto/startup_apply_pipeline.py",
        "python jobs.py --no-color generate --queue --parallel 3",
        "cd ../Outreach && ./.venv/bin/python main.py import-resume-jobs --jobs-xlsx \"../ResumeGenerator v1/discovery/jobs.xlsx\"",
        "cd ../Outreach && ./.venv/bin/python main.py build-linkedin-company-queue --limit 8",
    ]
    for company in suggested_outreach_companies:
        suggested_commands.append(
            f"cd ../Outreach && ./.venv/bin/python main.py run --company {json.dumps(company)} --company-mode startup"
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "source_breadth": str(source_breadth_path),
            "startup_source_report": str(startup_report_path),
            "current_apply_queue": str(args.current_apply_queue),
            "outreach_workspace": str(OUTREACH_WORKSPACE),
            "relationship_today_limit": args.relationship_today,
            "relationship_max_per_source": args.relationship_max_per_source,
        },
        "counts": {
            "score_for_application": len(source_score_for_application),
            "application_plus_outreach": len(application_plus_outreach),
            "application_only": len(application_only),
            "outreach_only_today": len(outreach_today),
            "relationship_buffer": len(relationship_buffer),
            "follow_up": len(follow_up),
            "skipped_internal": len(skipped_internal),
        },
        "source_counts": {
            "score_for_application": _source_label_counts(source_score_for_application),
            "application_plus_outreach": _source_label_counts(application_plus_outreach),
            "outreach_only_today": _source_label_counts(outreach_today),
            "relationship_buffer": _source_label_counts(relationship_buffer),
        },
        "score_for_application": source_score_for_application,
        "application_plus_outreach": application_plus_outreach,
        "application_only": application_only,
        "outreach_only_today": outreach_today,
        "relationship_buffer": relationship_buffer,
        "follow_up": follow_up,
        "skipped_internal": skipped_internal,
        "suggested_commands": suggested_commands,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = args.out_dir / f"{stamp}-daily-action-queue.json"
    md_path = args.out_dir / f"{stamp}-daily-action-queue.md"
    html_path = args.out_dir / f"{stamp}-daily-action-queue.html"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(md_path, payload)
    _write_html(html_path, payload)

    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    print(f"Wrote HTML: {html_path}")
    print(f"counts: {payload['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
