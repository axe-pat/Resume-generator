from __future__ import annotations

STARTUP_APPLY_SOURCES = {
    "yc_startup_jobs",
    "builtin_startup_jobs",
    "a16z_startup_jobs",
}

APPLY_QUEUE_SOURCES = {
    "linkedin_live_jobs_v1",
    *STARTUP_APPLY_SOURCES,
}


def is_startup_apply_source(source: str) -> bool:
    return source.strip().lower() in STARTUP_APPLY_SOURCES


def is_apply_queue_source(source: str) -> bool:
    return source.strip().lower() in APPLY_QUEUE_SOURCES


def queue_company_label(company: str, source: str) -> str:
    label = (company or "").strip()
    if not label:
        return label
    if is_startup_apply_source(source):
        return f"ST_{label}"
    return label
