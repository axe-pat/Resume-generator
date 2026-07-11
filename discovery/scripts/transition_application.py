#!/usr/bin/env python3
"""Safely transition one current-queue application to applied or closed.

This is the only supported status-transition surface for ``applied`` and
``closed``.  It archives the complete application directory before changing
the tracker, removes the job from the derived current-queue indexes, and keeps
a rollback journal until the filesystem, queue, and workbook all agree.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import sys
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jobs  # noqa: E402


APPS_DIR = ROOT / "apps"
APPLY_QUEUES_DIR = APPS_DIR / "Apply queues"
QUEUE_DIR = APPLY_QUEUES_DIR / "current_apply_queue"
QUEUE_LOCK_PATH = APPLY_QUEUES_DIR / ".current_apply_queue.lock"
TRANSACTION_DIR = APPLY_QUEUES_DIR / ".application_transition_transaction"
JOBS_XLSX = ROOT / "discovery" / "jobs.xlsx"
NIGHTLY_LOCK_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "ResumeGenerator"
    / "nightly_pipeline.lock"
)
OPERATOR_LOCK_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "ResumeGenerator"
    / "operator_mutation.lock"
)

LOCK_BUSY_EXIT_CODE = 75
VALID_SOURCE_STATUSES = {"queued", "promoted", "generated", "review"}
VALID_TARGET_STATUSES = {"applied", "closed"}
AUDIT_FILENAME = "application_transition.json"
QUEUE_MUTATION_FILES = (
    "priority_order.json",
    "manifest.json",
    "priority_order.txt",
    "latest_run_jobs.txt",
    "carry_over_jobs.txt",
    "manual_review.txt",
    "generation_shortlist.json",
    "generation_shortlist.md",
)


class LifecycleError(RuntimeError):
    """The requested transition is unsafe or ambiguous."""


class LifecycleLockBusy(LifecycleError):
    """A producer owns one of the required mutation locks."""


def _atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.transition-{os.getpid()}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            temp.chmod(mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        mode=0o600,
    )


@contextmanager
def _advisory_lock(
    path: Path, *, label: str, shared: bool = False
) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            os.fchmod(handle.fileno(), 0o600)
        except OSError:
            pass
        operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        try:
            fcntl.flock(handle, operation | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LifecycleLockBusy(f"{label} lock is busy: {path}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def _operator_guard(*, external_lock: bool) -> Iterator[None]:
    """Own the shared operator lock, or verify that a trusted parent owns it."""
    OPERATOR_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OPERATOR_LOCK_PATH.open("a+") as handle:
        try:
            os.fchmod(handle.fileno(), 0o600)
        except OSError:
            pass
        if external_lock:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # The companion process retains the exclusive lock for the
                # complete child lifetime.  This probe proves there is a real
                # external owner instead of trusting the CLI flag alone.
                yield
                return
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
                raise LifecycleError(
                    "--external-operator-lock was supplied, but no external "
                    "operator mutation lock is held"
                )

        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LifecycleLockBusy(
                f"operator mutation lock is busy: {OPERATOR_LOCK_PATH}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _read_json(path: Path, expected_type: type) -> Any:
    if path.is_symlink() or not path.is_file():
        raise LifecycleError(f"required queue file is unavailable or unsafe: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid queue JSON: {path}") from exc
    if not isinstance(payload, expected_type):
        raise LifecycleError(
            f"queue JSON has the wrong shape ({expected_type.__name__} required): {path}"
        )
    return payload


def _entry_id(entry: Any) -> str:
    return str(entry.get("id") or "").strip() if isinstance(entry, dict) else ""


def _matching_entries(entries: list[Any], job_id: str, *, label: str) -> list[dict]:
    matches = [entry for entry in entries if _entry_id(entry) == job_id]
    if len(matches) > 1:
        raise LifecycleError(f"job {job_id} appears more than once in {label}")
    return matches


def _load_queue_state(job_id: str) -> dict[str, Any]:
    priority_path = QUEUE_DIR / "priority_order.json"
    manifest_path = QUEUE_DIR / "manifest.json"
    priority = _read_json(priority_path, list)
    manifest = _read_json(manifest_path, dict)
    ready = manifest.get("ready_jobs")
    manual = manifest.get("manual_review_jobs")
    if not isinstance(ready, list) or not isinstance(manual, list):
        raise LifecycleError("current queue manifest is missing ready/manual job lists")

    priority_ids = [_entry_id(entry) for entry in priority]
    ready_ids = [_entry_id(entry) for entry in ready]
    if any(not value for value in priority_ids + ready_ids):
        raise LifecycleError("current queue contains an entry without an id")
    if len(priority_ids) != len(set(priority_ids)):
        raise LifecycleError("priority_order.json contains duplicate ids")
    if len(ready_ids) != len(set(ready_ids)):
        raise LifecycleError("manifest ready_jobs contains duplicate ids")
    if set(priority_ids) != set(ready_ids):
        raise LifecycleError("priority order and manifest ready jobs disagree")

    matches = []
    matches.extend(_matching_entries(priority, job_id, label="priority order"))
    matches.extend(_matching_entries(ready, job_id, label="manifest ready jobs"))
    matches.extend(
        _matching_entries(manual, job_id, label="manifest manual-review jobs")
    )
    if not matches:
        raise LifecycleError(f"job {job_id} is not in the current apply queue")
    if len(matches) not in {1, 2}:
        raise LifecycleError(f"job {job_id} has ambiguous current-queue references")
    if len(matches) == 2 and not (
        any(_entry_id(entry) == job_id for entry in priority)
        and any(_entry_id(entry) == job_id for entry in ready)
    ):
        raise LifecycleError(f"job {job_id} has inconsistent current-queue references")

    return {
        "priority": priority,
        "manifest": manifest,
        "ready": ready,
        "manual": manual,
        "matches": matches,
    }


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_any_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    return any(part.is_symlink() for part in (absolute, *absolute.parents))


def _has_symlink_component(path: Path, root: Path) -> bool:
    current = path
    while current != root:
        if current.is_symlink():
            return True
        if current.parent == current:
            return True
        current = current.parent
    return root.is_symlink()


def _candidate_source_dirs(
    row: dict[str, Any], queue_state: dict[str, Any], job_id: str
) -> list[Path]:
    candidates: list[Path] = []

    def add(raw: Any) -> None:
        value = str(raw or "").strip()
        if not value:
            return
        path = Path(value).expanduser()
        if not path.exists():
            return
        if _has_any_symlink_component(path):
            raise LifecycleError(
                f"application artifact path contains a symlink component: {path}"
            )
        resolved = path.resolve()
        if resolved not in candidates:
            candidates.append(resolved)

    add(row.get("folder_path"))
    for entry in queue_state["matches"]:
        add(entry.get("folder_path"))

    for metadata_path in QUEUE_DIR.rglob("metadata.json"):
        if metadata_path.is_symlink() or not metadata_path.is_file():
            raise LifecycleError(f"unsafe metadata path in current queue: {metadata_path}")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LifecycleError(f"invalid current-queue metadata: {metadata_path}") from exc
        if isinstance(metadata, dict) and str(metadata.get("id") or "").strip() == job_id:
            add(metadata_path.parent)
    return candidates


def _validate_source(source: Path, job_id: str) -> int:
    apps_root = APPS_DIR.resolve(strict=True)
    queue_root = QUEUE_DIR.resolve(strict=True)
    if not source.is_dir() or source.is_symlink():
        raise LifecycleError("application artifact source is not a safe directory")
    if not _inside(source, queue_root):
        raise LifecycleError("application artifact source is outside current_apply_queue")
    if _has_symlink_component(source, apps_root):
        raise LifecycleError("application artifact source contains a symlink component")
    metadata_path = source / "metadata.json"
    metadata = _read_json(metadata_path, dict)
    if str(metadata.get("id") or "").strip() != job_id:
        raise LifecycleError("application folder metadata does not match the requested job")
    if (source / AUDIT_FILENAME).exists():
        raise LifecycleError("live application folder unexpectedly contains a transition audit")

    artifact_count = 0
    for child in source.rglob("*"):
        if child.is_symlink():
            raise LifecycleError(f"application artifact tree contains a symlink: {child}")
        if child.is_file():
            artifact_count += 1
    if artifact_count == 0:
        raise LifecycleError("application artifact folder is empty")
    return artifact_count


def _archive_target(source: Path, target_status: str, transition_date: str) -> Path:
    apps_root = APPS_DIR.resolve(strict=True)
    rel = source.relative_to(apps_root)
    target = APPS_DIR / "archive" / target_status / transition_date / rel
    # Inspect the lexical target ancestry before resolving anything. Otherwise
    # `archive/applied -> /tmp/outside` makes both archive_root and target.parent
    # resolve outside and a resolved containment comparison incorrectly passes.
    if _has_any_symlink_component(target.parent):
        raise LifecycleError("application archive target ancestry contains a symlink")
    archive_root = (APPS_DIR / "archive" / target_status).resolve()
    resolved_parent = target.parent.resolve()
    if not _inside(resolved_parent, archive_root):
        raise LifecycleError("computed archive target escapes its durable archive")
    return target


def _queue_line(entry: dict[str, Any]) -> str:
    bucket = "NEW" if entry.get("in_latest_run") else "CARRY"
    return (
        f"{entry['priority_rank']}. [{bucket}] {entry.get('company', '')} | "
        f"{entry.get('role_title', '')} | score={entry.get('fit_score', '')} | "
        f"priority={entry.get('priority_score', '')} | status={entry.get('status', '')}"
    )


def _queue_updates(
    queue_state: dict[str, Any], job_id: str, target_status: str, timestamp: str
) -> dict[Path, bytes | None]:
    priority = [entry.copy() for entry in queue_state["priority"] if _entry_id(entry) != job_id]
    ready = [entry.copy() for entry in queue_state["ready"] if _entry_id(entry) != job_id]
    manual = [entry.copy() for entry in queue_state["manual"] if _entry_id(entry) != job_id]
    for rank, entry in enumerate(priority, start=1):
        entry["priority_rank"] = rank
    ready_by_id = {_entry_id(entry): entry for entry in priority}
    ready = [ready_by_id[_entry_id(entry)] for entry in ready]
    for rank, entry in enumerate(manual, start=1):
        entry["priority_rank"] = rank

    manifest = dict(queue_state["manifest"])
    manifest["ready_jobs"] = ready
    manifest["manual_review_jobs"] = manual
    manifest["ready_count"] = len(ready)
    manifest["manual_review_count"] = len(manual)
    manifest["updated_at"] = timestamp
    manifest["last_application_transition"] = {
        "job_id": job_id,
        "status": target_status,
        "at": timestamp,
    }

    def encoded(payload: Any) -> bytes:
        return (json.dumps(payload, indent=2) + "\n").encode("utf-8")

    def lines(entries: list[dict[str, Any]]) -> bytes:
        value = "\n".join(_queue_line(entry) for entry in entries)
        return (value + ("\n" if value else "")).encode("utf-8")

    manual_text = "\n".join(
        f"{entry['priority_rank']}. {entry.get('company', '')} | "
        f"{entry.get('role_title', '')} | score={entry.get('fit_score', '')} | "
        f"reason={entry.get('reason', '')}"
        for entry in manual
    )
    return {
        QUEUE_DIR / "priority_order.json": encoded(priority),
        QUEUE_DIR / "manifest.json": encoded(manifest),
        QUEUE_DIR / "priority_order.txt": lines(priority),
        QUEUE_DIR / "latest_run_jobs.txt": lines(
            [entry for entry in priority if entry.get("in_latest_run")]
        ),
        QUEUE_DIR / "carry_over_jobs.txt": lines(
            [entry for entry in priority if not entry.get("in_latest_run")]
        ),
        QUEUE_DIR / "manual_review.txt": (
            manual_text + ("\n" if manual_text else "")
        ).encode("utf-8"),
        # A cost-gated shortlist is a snapshot of the old queue.  Removing it is
        # safer than retaining a stale generation instruction; nightly rebuilds
        # both files before using them.
        QUEUE_DIR / "generation_shortlist.json": None,
        QUEUE_DIR / "generation_shortlist.md": None,
    }


def _snapshot_file(path: Path, backup: Path) -> dict[str, Any]:
    record = {"path": str(path), "backup": str(backup), "existed": path.exists()}
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise LifecycleError(f"cannot snapshot unsafe file: {path}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    return record


def _begin_transaction(
    *, source: Path, target: Path, job_id: str, target_status: str
) -> dict[str, Any]:
    if TRANSACTION_DIR.exists():
        raise LifecycleError(
            f"an application transition journal already exists: {TRANSACTION_DIR}"
        )
    TRANSACTION_DIR.mkdir(parents=True, mode=0o700)
    try:
        snapshots = [
            _snapshot_file(JOBS_XLSX, TRANSACTION_DIR / "jobs.xlsx"),
            _snapshot_file(
                JOBS_XLSX.with_suffix(".xlsx.bak"),
                TRANSACTION_DIR / "jobs.xlsx.bak",
            ),
        ]
        for index, name in enumerate(QUEUE_MUTATION_FILES):
            snapshots.append(
                _snapshot_file(
                    QUEUE_DIR / name,
                    TRANSACTION_DIR / "queue" / f"{index:02d}-{name}",
                )
            )
        journal = {
            "schema_version": 1,
            "phase": "planned",
            "job_id": job_id,
            "target_status": target_status,
            "source": str(source),
            "target": str(target),
            "snapshots": snapshots,
        }
        _write_json(TRANSACTION_DIR / "journal.json", journal)
        return journal
    except BaseException:
        shutil.rmtree(TRANSACTION_DIR, ignore_errors=True)
        raise


def _set_phase(journal: dict[str, Any], phase: str) -> None:
    journal["phase"] = phase
    _write_json(TRANSACTION_DIR / "journal.json", journal)


def _validated_journal_path(raw: Any, *, root: Path, label: str) -> Path:
    path = Path(str(raw or "")).expanduser()
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise LifecycleError(f"transaction {label} path is unavailable") from exc
    if not _inside(resolved, root.resolve(strict=False)):
        raise LifecycleError(f"transaction {label} escapes the configured root")
    return resolved


def _recover_incomplete_transaction() -> bool:
    """Rollback a previous interrupted transition before considering new work."""
    if not TRANSACTION_DIR.exists():
        return False
    if TRANSACTION_DIR.is_symlink() or not TRANSACTION_DIR.is_dir():
        raise LifecycleError(f"unsafe application transition journal: {TRANSACTION_DIR}")
    journal = _read_json(TRANSACTION_DIR / "journal.json", dict)
    if journal.get("phase") == "committed":
        shutil.rmtree(TRANSACTION_DIR)
        return True

    source = _validated_journal_path(
        journal.get("source"), root=QUEUE_DIR, label="source"
    )
    target = _validated_journal_path(
        journal.get("target"), root=APPS_DIR / "archive", label="target"
    )
    snapshots = journal.get("snapshots")
    if not isinstance(snapshots, list):
        raise LifecycleError("transaction journal has no valid snapshots")
    for record in snapshots:
        if not isinstance(record, dict):
            raise LifecycleError("transaction snapshot record is invalid")
        destination = Path(str(record.get("path") or ""))
        allowed = destination in {
            JOBS_XLSX,
            JOBS_XLSX.with_suffix(".xlsx.bak"),
            *(QUEUE_DIR / name for name in QUEUE_MUTATION_FILES),
        }
        if not allowed:
            raise LifecycleError("transaction snapshot destination is not allowlisted")
        backup = Path(str(record.get("backup") or ""))
        if not _inside(backup, TRANSACTION_DIR):
            raise LifecycleError("transaction backup escapes the journal directory")
        if bool(record.get("existed")):
            if backup.is_symlink() or not backup.is_file():
                raise LifecycleError(f"transaction backup is unavailable: {backup}")
            _atomic_write(destination, backup.read_bytes())
        elif destination.exists():
            if destination.is_symlink() or not destination.is_file():
                raise LifecycleError(f"cannot remove unsafe rollback destination: {destination}")
            destination.unlink()

    if target.exists() and source.exists():
        raise LifecycleError("rollback found both source and archive target; refusing to merge")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise LifecycleError("rollback archive target is unsafe")
        audit_path = target / AUDIT_FILENAME
        if audit_path.exists():
            if audit_path.is_symlink() or not audit_path.is_file():
                raise LifecycleError("rollback transition audit is unsafe")
            audit_path.unlink()
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(source))
    elif not source.exists():
        raise LifecycleError("rollback found neither source nor archive target")
    shutil.rmtree(TRANSACTION_DIR)
    return True


def _prune_empty_queue_ancestors(source: Path) -> None:
    queue_root = QUEUE_DIR.resolve()
    current = source.parent
    while current != queue_root and _inside(current.resolve(), queue_root):
        try:
            next(current.iterdir())
            return
        except StopIteration:
            parent = current.parent
            current.rmdir()
            current = parent


def _load_unique_tracker_row(job_id: str) -> tuple[Any, Any, dict[str, Any]]:
    dataframe = jobs.load_jobs()
    matches = dataframe[dataframe["id"].astype(str).str.strip().eq(job_id)]
    if matches.empty:
        raise LifecycleError(f"job {job_id} does not exist in jobs.xlsx")
    if len(matches) != 1:
        raise LifecycleError(f"job {job_id} is duplicated in jobs.xlsx")
    index = matches.index[0]
    return dataframe, index, matches.iloc[0].to_dict()


def _idempotent_result(
    *, row: dict[str, Any], job_id: str, target_status: str
) -> dict[str, Any] | None:
    current_status = str(row.get("status") or "").strip().lower()
    if current_status != target_status:
        return None
    folder = Path(str(row.get("folder_path") or "")).expanduser()
    if not folder.exists() or folder.is_symlink() or not folder.is_dir():
        raise LifecycleError(
            f"job {job_id} already says {target_status}, but its archive folder is unavailable"
        )
    resolved = folder.resolve()
    archive_root = (APPS_DIR / "archive" / target_status).resolve()
    if not _inside(resolved, archive_root):
        raise LifecycleError(
            f"job {job_id} already says {target_status}, but still points outside its archive"
        )
    audit = _read_json(resolved / AUDIT_FILENAME, dict)
    if (
        str(audit.get("job_id") or "") != job_id
        or str(audit.get("status") or "") != target_status
    ):
        raise LifecycleError("existing transition audit does not match the tracker row")
    queue_state = _load_queue_state_if_available(job_id)
    if queue_state is not None:
        raise LifecycleError(
            f"job {job_id} is archived but still appears in the current queue"
        )
    return {
        "job_id": int(job_id),
        "status": target_status,
        "result": "already_transitioned",
        "archive_path": str(resolved.relative_to(ROOT.resolve())),
    }


def _load_queue_state_if_available(job_id: str) -> dict[str, Any] | None:
    try:
        return _load_queue_state(job_id)
    except LifecycleError as exc:
        if str(exc) == f"job {job_id} is not in the current apply queue":
            return None
        raise


def _transition_locked(
    *, job_id: str, target_status: str, dry_run: bool, today: date
) -> dict[str, Any]:
    if dry_run and TRANSACTION_DIR.exists():
        raise LifecycleError(
            "an interrupted transition requires rollback before a read-only preview"
        )
    recovered = _recover_incomplete_transaction()
    dataframe, index, row = _load_unique_tracker_row(job_id)
    idempotent = _idempotent_result(
        row=row, job_id=job_id, target_status=target_status
    )
    if idempotent is not None:
        idempotent["recovered_interrupted_transaction"] = recovered
        return idempotent

    source_status = str(row.get("status") or "").strip().lower()
    if source_status not in VALID_SOURCE_STATUSES:
        raise LifecycleError(
            f"job {job_id} cannot transition from status '{source_status or 'blank'}'"
        )
    queue_state = _load_queue_state(job_id)
    candidates = _candidate_source_dirs(row, queue_state, job_id)
    if len(candidates) != 1:
        raise LifecycleError(
            f"job {job_id} has {len(candidates)} live artifact folders; exactly one is required"
        )
    source = candidates[0]
    artifact_count = _validate_source(source, job_id)
    transition_date = today.isoformat()
    target = _archive_target(source, target_status, transition_date)
    if target.exists() or target.is_symlink():
        raise LifecycleError(f"archive target already exists: {target}")

    result = {
        "job_id": int(job_id),
        "from_status": source_status,
        "status": target_status,
        "result": "preview" if dry_run else "transitioned",
        "artifact_count": artifact_count,
        "source_path": str(source.relative_to(ROOT.resolve())),
        "archive_path": str(target.relative_to(ROOT)),
        "date_applied": transition_date if target_status == "applied" else "",
        "recovered_interrupted_transaction": recovered,
    }
    if dry_run:
        return result

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    updates = _queue_updates(queue_state, job_id, target_status, timestamp)
    journal = _begin_transaction(
        source=source,
        target=target,
        job_id=job_id,
        target_status=target_status,
    )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        _set_phase(journal, "artifacts_archived")
        _write_json(
            target / AUDIT_FILENAME,
            {
                "schema_version": 1,
                "job_id": job_id,
                "previous_status": source_status,
                "status": target_status,
                "transitioned_at": timestamp,
                "source_path": str(source.relative_to(ROOT.resolve())),
                "archive_path": str(target.relative_to(ROOT)),
            },
        )
        _prune_empty_queue_ancestors(source)

        for path, data in updates.items():
            if data is None:
                if path.exists():
                    if path.is_symlink() or not path.is_file():
                        raise LifecycleError(f"cannot invalidate unsafe shortlist: {path}")
                    path.unlink()
                continue
            _atomic_write(path, data)
        _set_phase(journal, "queue_updated")

        dataframe.loc[index, "status"] = target_status
        dataframe.loc[index, "date_applied"] = (
            transition_date if target_status == "applied" else ""
        )
        dataframe.loc[index, "folder_path"] = str(target)
        jobs.save_jobs(dataframe)
        _set_phase(journal, "tracker_updated")

        verify_df, _, verify_row = _load_unique_tracker_row(job_id)
        del verify_df
        if str(verify_row.get("status") or "").strip().lower() != target_status:
            raise LifecycleError("tracker verification failed after save")
        if Path(str(verify_row.get("folder_path") or "")).resolve() != target.resolve():
            raise LifecycleError("tracker archive path verification failed after save")
        if not target.is_dir() or source.exists():
            raise LifecycleError("artifact archive verification failed after save")
        if _load_queue_state_if_available(job_id) is not None:
            raise LifecycleError("queue verification failed after transition")

        _set_phase(journal, "committed")
        shutil.rmtree(TRANSACTION_DIR)
        return result
    except BaseException as original:
        try:
            _recover_incomplete_transaction()
        except BaseException as rollback_error:
            raise LifecycleError(
                "transition failed and automatic rollback also failed; preserve the "
                f"journal at {TRANSACTION_DIR}: {rollback_error}"
            ) from original
        raise


def transition_application(
    job_id: int,
    target_status: str,
    *,
    dry_run: bool = False,
    external_operator_lock: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    """API-safe lifecycle operation for one positive numeric tracker id."""
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise LifecycleError("job id must be one positive integer")
    normalized = "closed" if target_status == "not-applied" else target_status
    if normalized not in VALID_TARGET_STATUSES:
        raise LifecycleError("target status must be applied, closed, or not-applied")

    # Match nightly's lock ordering.  The companion already owns operator_lock;
    # direct CLI calls take it here after excluding an active nightly run.
    with _advisory_lock(
        NIGHTLY_LOCK_PATH, label="nightly pipeline", shared=True
    ):
        with _operator_guard(external_lock=external_operator_lock):
            with _advisory_lock(
                QUEUE_LOCK_PATH, label="current apply queue"
            ):
                try:
                    with jobs.XlsxLock(timeout=0):
                        return _transition_locked(
                            job_id=str(job_id),
                            target_status=normalized,
                            dry_run=dry_run,
                            today=today or date.today(),
                        )
                except TimeoutError as exc:
                    raise LifecycleLockBusy(
                        f"jobs workbook lock is busy: {jobs.LOCK_FILE}"
                    ) from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive one current-queue application and transactionally mark it "
            "applied or closed."
        )
    )
    parser.add_argument("--id", type=int, required=True, help="One positive numeric job id")
    parser.add_argument(
        "--status",
        choices=("applied", "closed", "not-applied"),
        required=True,
        help="Terminal application outcome (not-applied is stored as closed)",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help="Required exact phrase: APPLY <id> or CLOSE <id>",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without writing"
    )
    parser.add_argument("--json", action="store_true", help="Emit one JSON result")
    parser.add_argument(
        "--external-operator-lock",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    normalized = "closed" if args.status == "not-applied" else args.status
    phrase = f"APPLY {args.id}" if normalized == "applied" else f"CLOSE {args.id}"
    if not args.dry_run and args.confirm != phrase:
        print(
            f"[invalid] Exact confirmation required: {phrase}",
            file=sys.stderr,
        )
        return 2
    try:
        result = transition_application(
            args.id,
            normalized,
            dry_run=args.dry_run,
            external_operator_lock=args.external_operator_lock,
        )
    except LifecycleLockBusy as exc:
        print(f"[busy] Transition not started: {exc}", file=sys.stderr)
        return LOCK_BUSY_EXIT_CODE
    except LifecycleError as exc:
        print(f"[invalid] Transition not started: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[failed] Transition rolled back: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        verb = "Would transition" if args.dry_run else "Transitioned"
        print(
            f"{verb} job {result['job_id']} -> {result['status']} "
            f"({result.get('artifact_count', 0)} artifacts)"
        )
        print(f"Archive: {result['archive_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
