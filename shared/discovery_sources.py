from __future__ import annotations

STARTUP_APPLY_SOURCES = {
    "yc_startup_jobs",
    "builtin_startup_jobs",
    "a16z_startup_jobs",
}

HANDSHAKE_APPLY_SOURCES = {
    "handshake_jobs_v1",
}

APPLY_QUEUE_SOURCES = {
    "linkedin_live_jobs_v1",
    *HANDSHAKE_APPLY_SOURCES,
    *STARTUP_APPLY_SOURCES,
}

APPLY_QUEUE_MIN_SCORE_BY_SOURCE = {
    "handshake_jobs_v1": 4.5,
}


def min_apply_queue_score(source: str, default: float) -> float:
    return APPLY_QUEUE_MIN_SCORE_BY_SOURCE.get(source.strip().lower(), default)


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
