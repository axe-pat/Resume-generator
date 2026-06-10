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

HANDSHAKE_APPLY_FLOW_MIN_SCORE = {
    "internal": 4.0,
    "external": 5.5,
    "unknown": 4.5,
}


def _note_value(notes: str, key: str) -> str:
    prefix = f"{key}="
    for token in str(notes or "").split():
        if token.startswith(prefix):
            return token[len(prefix) :].strip().lower()
    return ""


def min_apply_queue_score(source: str, default: float) -> float:
    return APPLY_QUEUE_MIN_SCORE_BY_SOURCE.get(source.strip().lower(), default)


def min_apply_queue_score_for_row(source: str, notes: str, default: float) -> float:
    source_key = source.strip().lower()
    if source_key == "handshake_jobs_v1":
        apply_flow = _note_value(notes, "handshake_apply_flow") or "unknown"
        return HANDSHAKE_APPLY_FLOW_MIN_SCORE.get(apply_flow, HANDSHAKE_APPLY_FLOW_MIN_SCORE["unknown"])
    return min_apply_queue_score(source, default)


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
