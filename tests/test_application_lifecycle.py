from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "discovery" / "scripts" / "transition_application.py"


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _held_lock(path: Path):
    script = """
import fcntl
import os
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a+") as handle:
    os.fchmod(handle.fileno(), 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX)
    print("READY", flush=True)
    sys.stdin.readline()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "READY"
    try:
        yield
    finally:
        assert process.stdin is not None
        process.stdin.write("\n")
        process.stdin.flush()
        process.communicate(timeout=5)


def _job_row(folder: Path, *, status: str = "generated") -> dict[str, str]:
    return {
        "id": "42",
        "date_found": "2026-07-10",
        "date_posted": "2026-07-09",
        "company": "Acme",
        "role_title": "Product Manager Intern",
        "role_type": "PM",
        "location": "Los Angeles, CA",
        "url": "https://example.com/jobs/42",
        "url_hash": "hash-42",
        "source": "linkedin_live_jobs_v1",
        "fit_score": "8.4",
        "fit_rationale": "Strong fit",
        "status": status,
        "date_applied": "",
        "folder_path": str(folder),
        "resume_run": "run-1",
        "jd_text": "Own the roadmap.",
        "notes": "",
    }


def _queue_entry(folder: Path) -> dict[str, object]:
    return {
        "id": "42",
        "company": "Acme",
        "role_title": "Product Manager Intern",
        "fit_score": "8.4",
        "priority_score": "92.0",
        "status": "generated",
        "url": "https://example.com/jobs/42",
        "queue_bucket": "new",
        "in_latest_run": True,
        "latest_run": "run-1",
        "origin_runs": ["run-1"],
        "priority_meta": {},
        "folder_path": str(folder),
        "reason": "",
        "priority_rank": 1,
    }


def _configure(module, tmp_path: Path, monkeypatch, *, status: str = "generated"):
    root = tmp_path / "ResumeGenerator"
    apps = root / "apps"
    queues = apps / "Apply queues"
    queue = queues / "current_apply_queue"
    folder = queue / "jobs" / "01_Acme" / "Product_Manager_Intern"
    discovery = root / "discovery"
    discovery.mkdir(parents=True)
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(
        json.dumps({"id": "42", "company": "Acme", "status": status}),
        encoding="utf-8",
    )
    (folder / "jd.txt").write_text("Own the roadmap.", encoding="utf-8")
    (folder / "resume_2026-07-10.docx").write_bytes(b"resume")

    frame = pd.DataFrame([_job_row(folder, status=status)], columns=module.jobs.COLUMNS)
    jobs_xlsx = discovery / "jobs.xlsx"
    frame.to_excel(jobs_xlsx, sheet_name="Jobs", index=False)

    entry = _queue_entry(folder)
    (queue / "priority_order.json").write_text(
        json.dumps([entry], indent=2), encoding="utf-8"
    )
    (queue / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": "2026-07-11T12:00:00",
                "ready_count": 1,
                "manual_review_count": 0,
                "ready_jobs": [entry],
                "manual_review_jobs": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for name in (
        "priority_order.txt",
        "latest_run_jobs.txt",
        "carry_over_jobs.txt",
        "manual_review.txt",
    ):
        (queue / name).write_text(f"old-{name}\n", encoding="utf-8")
    (queue / "generation_shortlist.json").write_text(
        json.dumps([entry]), encoding="utf-8"
    )
    (queue / "generation_shortlist.md").write_text(
        "# Old shortlist\n", encoding="utf-8"
    )

    paths = {
        "ROOT": root,
        "APPS_DIR": apps,
        "APPLY_QUEUES_DIR": queues,
        "QUEUE_DIR": queue,
        "QUEUE_LOCK_PATH": queues / ".current_apply_queue.lock",
        "TRANSACTION_DIR": queues / ".application_transition_transaction",
        "JOBS_XLSX": jobs_xlsx,
        "NIGHTLY_LOCK_PATH": root / "runtime" / "nightly.lock",
        "OPERATOR_LOCK_PATH": root / "runtime" / "operator.lock",
    }
    for key, value in paths.items():
        monkeypatch.setattr(module, key, value)
    monkeypatch.setattr(module.jobs, "ROOT_DIR", root)
    monkeypatch.setattr(module.jobs, "APPS_DIR", apps)
    monkeypatch.setattr(module.jobs, "APPLY_QUEUES_DIR", queues)
    monkeypatch.setattr(module.jobs, "CURRENT_APPLY_QUEUE_DIR", queue)
    monkeypatch.setattr(module.jobs, "JOBS_XLSX", jobs_xlsx)
    monkeypatch.setattr(module.jobs, "LOCK_FILE", discovery / ".jobs.lock")
    monkeypatch.setattr(module.jobs, "BLOCKLIST_PATH", discovery / "blocklist.txt")
    for lock_path in (
        paths["NIGHTLY_LOCK_PATH"],
        paths["OPERATOR_LOCK_PATH"],
        paths["QUEUE_LOCK_PATH"],
        module.jobs.LOCK_FILE,
    ):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()
    return {**paths, "folder": folder, "entry": entry}


def _tracker_row(path: Path) -> dict[str, str]:
    frame = pd.read_excel(path, sheet_name="Jobs", dtype=str).fillna("")
    return frame[frame["id"].astype(str).eq("42")].iloc[0].to_dict()


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize(
    ("target_status", "expected_date"),
    [("applied", "2026-07-12"), ("closed", "")],
)
def test_transition_archives_every_artifact_and_updates_all_surfaces(
    tmp_path: Path,
    monkeypatch,
    target_status: str,
    expected_date: str,
) -> None:
    module = _load_module(f"application_transition_{target_status}")
    paths = _configure(module, tmp_path, monkeypatch)

    result = module.transition_application(
        42, target_status, today=date(2026, 7, 12)
    )

    assert result["result"] == "transitioned"
    assert result["artifact_count"] == 3
    assert not paths["folder"].exists()
    archive = paths["ROOT"] / result["archive_path"]
    assert (archive / "metadata.json").is_file()
    assert (archive / "jd.txt").is_file()
    assert (archive / "resume_2026-07-10.docx").read_bytes() == b"resume"
    audit = json.loads((archive / module.AUDIT_FILENAME).read_text(encoding="utf-8"))
    assert audit["job_id"] == "42"
    assert audit["status"] == target_status

    row = _tracker_row(paths["JOBS_XLSX"])
    assert row["status"] == target_status
    assert row["date_applied"] == expected_date
    assert Path(row["folder_path"]).resolve() == archive.resolve()
    assert json.loads((paths["QUEUE_DIR"] / "priority_order.json").read_text()) == []
    manifest = json.loads((paths["QUEUE_DIR"] / "manifest.json").read_text())
    assert manifest["ready_count"] == 0
    assert manifest["ready_jobs"] == []
    assert manifest["last_application_transition"]["job_id"] == "42"
    assert not (paths["QUEUE_DIR"] / "generation_shortlist.json").exists()
    assert not (paths["QUEUE_DIR"] / "generation_shortlist.md").exists()
    assert not paths["TRANSACTION_DIR"].exists()


def test_not_applied_alias_is_stored_as_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_closed_alias")
    paths = _configure(module, tmp_path, monkeypatch)

    result = module.transition_application(
        42, "not-applied", today=date(2026, 7, 12)
    )

    assert result["status"] == "closed"
    assert _tracker_row(paths["JOBS_XLSX"])["status"] == "closed"


def test_dry_run_is_byte_for_byte_read_only(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_dry_run")
    paths = _configure(module, tmp_path, monkeypatch)
    before = _tree_bytes(paths["ROOT"])

    result = module.transition_application(
        42, "applied", dry_run=True, today=date(2026, 7, 12)
    )

    assert result["result"] == "preview"
    assert _tree_bytes(paths["ROOT"]) == before
    assert not paths["TRANSACTION_DIR"].exists()


def test_completed_transition_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_idempotent")
    paths = _configure(module, tmp_path, monkeypatch)
    first = module.transition_application(42, "applied", today=date(2026, 7, 12))
    before = _tree_bytes(paths["ROOT"])

    second = module.transition_application(42, "applied", today=date(2026, 7, 13))

    assert first["result"] == "transitioned"
    assert second["result"] == "already_transitioned"
    assert _tree_bytes(paths["ROOT"]) == before


def test_tracker_failure_rolls_back_artifacts_queue_and_workbook(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_rollback")
    paths = _configure(module, tmp_path, monkeypatch)
    before = _tree_bytes(paths["ROOT"])
    original_save = module.jobs.save_jobs
    calls = 0

    def fail_first_save(frame):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated workbook failure")
        return original_save(frame)

    monkeypatch.setattr(module.jobs, "save_jobs", fail_first_save)
    with pytest.raises(OSError, match="simulated workbook failure"):
        module.transition_application(42, "applied", today=date(2026, 7, 12))

    assert paths["folder"].is_dir()
    assert _tree_bytes(paths["ROOT"]) == before
    assert not paths["TRANSACTION_DIR"].exists()


def test_next_write_recovers_an_interrupted_archive_then_transitions(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_interrupted_recovery")
    paths = _configure(module, tmp_path, monkeypatch)
    source = paths["folder"].resolve()
    target = module._archive_target(source, "applied", "2026-07-12")
    journal = module._begin_transaction(
        source=source,
        target=target,
        job_id="42",
        target_status="applied",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    module.shutil.move(str(source), str(target))
    module._set_phase(journal, "artifacts_archived")

    result = module.transition_application(
        42, "applied", today=date(2026, 7, 12)
    )

    assert result["result"] == "transitioned"
    assert result["recovered_interrupted_transaction"] is True
    assert target.is_dir()
    assert not source.exists()
    assert not paths["TRANSACTION_DIR"].exists()


def test_dry_run_never_recovers_an_interrupted_transaction(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_dry_run_recovery")
    paths = _configure(module, tmp_path, monkeypatch)
    source = paths["folder"].resolve()
    target = module._archive_target(source, "applied", "2026-07-12")
    module._begin_transaction(
        source=source,
        target=target,
        job_id="42",
        target_status="applied",
    )
    before = _tree_bytes(paths["ROOT"])

    with pytest.raises(module.LifecycleError, match="read-only preview"):
        module.transition_application(42, "applied", dry_run=True)

    assert _tree_bytes(paths["ROOT"]) == before
    assert paths["TRANSACTION_DIR"].is_dir()


@pytest.mark.parametrize("lock_name", ["NIGHTLY_LOCK_PATH", "QUEUE_LOCK_PATH"])
def test_producer_lock_contention_fails_before_mutation(
    tmp_path: Path, monkeypatch, lock_name: str
) -> None:
    module = _load_module(f"application_transition_busy_{lock_name}")
    paths = _configure(module, tmp_path, monkeypatch)
    before = _tree_bytes(paths["ROOT"])

    with _held_lock(paths[lock_name]):
        with pytest.raises(module.LifecycleLockBusy):
            module.transition_application(42, "applied")

    assert _tree_bytes(paths["ROOT"]) == before


def test_jobs_workbook_lock_contention_fails_before_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_busy_jobs")
    paths = _configure(module, tmp_path, monkeypatch)
    before = _tree_bytes(paths["ROOT"])

    with _held_lock(module.jobs.LOCK_FILE):
        with pytest.raises(module.LifecycleLockBusy):
            module.transition_application(42, "applied")

    assert _tree_bytes(paths["ROOT"]) == before


def test_direct_call_respects_busy_operator_lock(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_busy_operator")
    paths = _configure(module, tmp_path, monkeypatch)

    with _held_lock(paths["OPERATOR_LOCK_PATH"]):
        with pytest.raises(module.LifecycleLockBusy):
            module.transition_application(42, "applied", dry_run=True)


def test_companion_mode_requires_and_accepts_real_external_operator_lock(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_external_operator")
    paths = _configure(module, tmp_path, monkeypatch)

    with pytest.raises(module.LifecycleError, match="no external operator"):
        module.transition_application(
            42, "applied", dry_run=True, external_operator_lock=True
        )
    with _held_lock(paths["OPERATOR_LOCK_PATH"]):
        result = module.transition_application(
            42, "applied", dry_run=True, external_operator_lock=True
        )
    assert result["result"] == "preview"


def test_multiple_live_artifact_folders_fail_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_ambiguous")
    paths = _configure(module, tmp_path, monkeypatch)
    duplicate = paths["QUEUE_DIR"] / "jobs" / "02_Acme" / "Product_Manager_Intern"
    duplicate.mkdir(parents=True)
    (duplicate / "metadata.json").write_text(json.dumps({"id": "42"}), encoding="utf-8")
    before = _tree_bytes(paths["ROOT"])

    with pytest.raises(module.LifecycleError, match="2 live artifact folders"):
        module.transition_application(42, "closed")

    assert _tree_bytes(paths["ROOT"]) == before


def test_symlinked_artifact_folder_fails_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_symlink")
    paths = _configure(module, tmp_path, monkeypatch)
    original = paths["folder"]
    real_folder = paths["ROOT"] / "private-artifacts"
    real_folder.parent.mkdir(parents=True, exist_ok=True)
    original.rename(real_folder)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.symlink_to(real_folder, target_is_directory=True)
    before_tracker = paths["JOBS_XLSX"].read_bytes()

    with pytest.raises(module.LifecycleError, match="symlink component"):
        module.transition_application(42, "applied")

    assert original.is_symlink()
    assert real_folder.is_dir()
    assert paths["JOBS_XLSX"].read_bytes() == before_tracker


@pytest.mark.parametrize("symlink_level", ["status", "descendant"])
def test_symlink_in_archive_target_ancestry_fails_before_preview(
    tmp_path: Path, monkeypatch, symlink_level: str
) -> None:
    module = _load_module(f"application_transition_archive_symlink_{symlink_level}")
    paths = _configure(module, tmp_path, monkeypatch)
    outside = tmp_path / "outside-archive"
    outside.mkdir()
    archive = paths["APPS_DIR"] / "archive"
    archive.mkdir()
    if symlink_level == "status":
        (archive / "applied").symlink_to(outside, target_is_directory=True)
    else:
        descendant = (
            archive
            / "applied"
            / "2026-07-12"
            / "Apply queues"
            / "current_apply_queue"
            / "jobs"
        )
        descendant.mkdir(parents=True)
        (descendant / "01_Acme").symlink_to(outside, target_is_directory=True)
    before_tracker = paths["JOBS_XLSX"].read_bytes()

    with pytest.raises(module.LifecycleError, match="target ancestry contains a symlink"):
        module.transition_application(
            42, "applied", dry_run=True, today=date(2026, 7, 12)
        )

    assert paths["folder"].is_dir()
    assert paths["JOBS_XLSX"].read_bytes() == before_tracker
    assert list(outside.iterdir()) == []


def test_existing_archive_target_fails_closed(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("application_transition_existing_target")
    paths = _configure(module, tmp_path, monkeypatch)
    target = module._archive_target(paths["folder"].resolve(), "applied", "2026-07-12")
    target.mkdir(parents=True)
    before = _tree_bytes(paths["ROOT"])

    with pytest.raises(module.LifecycleError, match="archive target already exists"):
        module.transition_application(42, "applied", today=date(2026, 7, 12))

    assert _tree_bytes(paths["ROOT"]) == before


def test_different_terminal_status_cannot_be_overwritten(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_terminal_conflict")
    paths = _configure(module, tmp_path, monkeypatch, status="rejected")

    with pytest.raises(module.LifecycleError, match="cannot transition from status 'rejected'"):
        module.transition_application(42, "applied")

    assert _tracker_row(paths["JOBS_XLSX"])["status"] == "rejected"


def test_cli_confirmation_is_exact(monkeypatch, capsys) -> None:
    module = _load_module("application_transition_confirmation")
    monkeypatch.setattr(
        module,
        "transition_application",
        lambda *args, **kwargs: pytest.fail("invalid confirmation must stop first"),
    )

    assert module.main(["--id", "42", "--status", "applied", "--confirm", "yes"]) == 2
    assert "APPLY 42" in capsys.readouterr().err


def test_legacy_mark_rejects_applied_and_closed() -> None:
    import jobs

    for status in ("applied", "closed"):
        with pytest.raises(SystemExit, match="transition_application.py"):
            jobs.cmd_mark(
                SimpleNamespace(id="42", status=status, dry_run=True)
            )


@pytest.mark.parametrize("status", ["parked", "rejected", "skip", "skipped"])
def test_legacy_mark_rejects_terminal_status_for_live_queue_folder(
    tmp_path: Path, monkeypatch, status: str
) -> None:
    module = _load_module(f"application_transition_mark_live_{status}")
    paths = _configure(module, tmp_path, monkeypatch)
    before = paths["JOBS_XLSX"].read_bytes()

    with pytest.raises(SystemExit, match="live current-queue job id.*42"):
        module.jobs.cmd_mark(
            SimpleNamespace(id="42", status=status, dry_run=True)
        )

    assert paths["folder"].is_dir()
    assert paths["JOBS_XLSX"].read_bytes() == before


def _append_non_live_job(module, jobs_xlsx: Path) -> None:
    frame = pd.read_excel(jobs_xlsx, sheet_name="Jobs", dtype=str).fillna("")
    row = _job_row(Path(""), status="queued")
    row["id"] = "99"
    row["company"] = "No Artifacts Inc"
    row["folder_path"] = ""
    frame = pd.concat(
        [frame, pd.DataFrame([row], columns=module.jobs.COLUMNS)],
        ignore_index=True,
    )
    frame.to_excel(jobs_xlsx, sheet_name="Jobs", index=False)


def test_legacy_mark_retains_terminal_status_for_proven_non_live_row(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_module("application_transition_mark_non_live")
    paths = _configure(module, tmp_path, monkeypatch)
    _append_non_live_job(module, paths["JOBS_XLSX"])

    module.jobs.cmd_mark(
        SimpleNamespace(id="99", status="skip", dry_run=True)
    )

    output = capsys.readouterr().out
    assert "[99]" in output
    assert "→ skip" in output
    assert _tracker_row(paths["JOBS_XLSX"])["status"] == "generated"


def test_legacy_mark_fails_closed_when_queue_indexes_are_unreadable(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module("application_transition_mark_broken_queue")
    paths = _configure(module, tmp_path, monkeypatch)
    _append_non_live_job(module, paths["JOBS_XLSX"])
    (paths["QUEUE_DIR"] / "manifest.json").write_text("not-json", encoding="utf-8")
    before = paths["JOBS_XLSX"].read_bytes()

    with pytest.raises(SystemExit, match="cannot be proven safe"):
        module.jobs.cmd_mark(
            SimpleNamespace(id="99", status="rejected", dry_run=True)
        )

    assert paths["JOBS_XLSX"].read_bytes() == before
