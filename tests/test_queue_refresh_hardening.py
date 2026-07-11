from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "discovery" / "scripts"


def _load_script(filename: str, name: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _held_lock(path: Path, payload: str = ""):
    script = """
import fcntl
import os
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = sys.argv[2]
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w") as fh:
    os.fchmod(fh.fileno(), 0o600)
    fh.write(payload)
    fh.flush()
    fcntl.flock(fh, fcntl.LOCK_EX)
    print("READY", flush=True)
    sys.stdin.readline()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(path), payload],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    ready = process.stdout.readline().strip()
    if ready != "READY":
        stderr = process.stderr.read() if process.stderr is not None else ""
        process.kill()
        raise AssertionError(f"lock holder did not start: {ready!r} {stderr}")
    try:
        yield
    finally:
        if process.stdin is not None:
            process.stdin.write("\n")
            process.stdin.flush()
        process.communicate(timeout=5)


def _configure_isolated_repo(module, tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path / "ResumeGenerator"
    apps_dir = root / "apps"
    apply_queues = apps_dir / "Apply queues"
    queue_dir = apply_queues / "current_apply_queue"
    queue_tmp = apply_queues / ".current_apply_queue_tmp"
    archive_dir = apps_dir / "archive"
    runs_dir = apps_dir / "runs"
    discovery_dir = root / "discovery"
    jobs_xlsx = discovery_dir / "jobs.xlsx"

    queue_dir.mkdir(parents=True)
    (queue_dir / "existing-marker.txt").write_text("keep", encoding="utf-8")
    archive_dir.mkdir(parents=True)
    runs_dir.mkdir(parents=True)
    discovery_dir.mkdir(parents=True)

    tracker = pd.DataFrame(
        [
            {
                "id": "1",
                "date_found": "2026-07-11",
                "date_posted": "2026-07-11",
                "company": "Acme",
                "role_title": "Product Manager Intern",
                "role_type": "PM",
                "location": "Los Angeles, CA",
                "url": "https://example.com/jobs/1",
                "url_hash": "hash-1",
                "source": "linkedin_live_jobs_v1",
                "fit_score": "8.2",
                "fit_rationale": "Proceed",
                "status": "queued",
                "date_applied": "",
                "folder_path": "",
                "jd_text": "Own a product roadmap and customer research.",
                "notes": "",
            }
        ]
    )
    tracker.to_excel(jobs_xlsx, sheet_name="Jobs", index=False)

    values = {
        "ROOT": root,
        "APPS_DIR": apps_dir,
        "RUNS_DIR": runs_dir,
        "APPLY_QUEUES_DIR": apply_queues,
        "ARCHIVE_DIR": archive_dir,
        "DISCOVERY_ARCHIVE_DIR": archive_dir / "discovery_runs",
        "QUEUE_DIR": queue_dir,
        "QUEUE_TMP_DIR": queue_tmp,
        "QUEUE_LOCK_PATH": apply_queues / ".current_apply_queue.lock",
        "JOBS_DIR": queue_dir / "jobs",
        "MANUAL_DIR": queue_dir / "manual_review",
        "JOBS_XLSX": jobs_xlsx,
        "NIGHTLY_LOCK_PATH": root / ".nightly.lock",
    }
    for name, value in values.items():
        monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(module, "APPLY_QUEUE_SOURCES", {"linkedin_live_jobs_v1"})
    monkeypatch.setattr(module, "EXCLUDED_COMPANIES", set())
    monkeypatch.setattr(module, "_load_blocklist", lambda: [])
    monkeypatch.setattr(module.jobs, "LOCK_FILE", discovery_dir / ".jobs.lock")
    monkeypatch.setattr(module.jobs, "JOBS_XLSX", jobs_xlsx)
    monkeypatch.setattr(module.jobs, "APPS_DIR", apps_dir)
    return {**values, "jobs_lock": discovery_dir / ".jobs.lock"}


def test_help_exits_before_any_refresh_side_effect(monkeypatch) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_help_contract_test"
    )
    assert not hasattr(module, "_sync_applied_pdfs")
    monkeypatch.setattr(
        module,
        "_run_refresh",
        lambda args: pytest.fail("--help must not build a queue"),
    )

    with pytest.raises(SystemExit) as exc:
        module.main(["--help"])

    assert exc.value.code == 0


def test_dry_run_leaves_tracker_and_live_queue_unchanged(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_dry_run_test"
    )
    paths = _configure_isolated_repo(module, tmp_path, monkeypatch)
    workbook_before = paths["JOBS_XLSX"].read_bytes()
    queue_marker = paths["QUEUE_DIR"] / "existing-marker.txt"
    company_dir = paths["APPS_DIR"] / "Acme"
    company_dir.mkdir()
    (company_dir / "user-file.txt").write_text("keep", encoding="utf-8")
    assert not hasattr(module, "_sync_applied_pdfs")
    monkeypatch.setattr(
        module.jobs,
        "save_jobs",
        lambda df: pytest.fail("dry-run must not write jobs.xlsx"),
    )

    assert module.main(["--dry-run"]) == 0

    assert paths["JOBS_XLSX"].read_bytes() == workbook_before
    assert queue_marker.read_text(encoding="utf-8") == "keep"
    assert not paths["QUEUE_TMP_DIR"].exists()
    assert (company_dir / "user-file.txt").is_file()
    assert "No applied-PDF sync, tracker write, queue swap" in capsys.readouterr().out


def test_tracker_read_modify_write_stays_inside_one_jobs_lock(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_tracker_lock_test"
    )
    paths = _configure_isolated_repo(module, tmp_path, monkeypatch)
    held = False
    events: list[str] = []

    class TrackingLock:
        def __init__(self, timeout: int = 30):
            self.timeout = timeout

        def __enter__(self):
            nonlocal held
            assert held is False
            held = True
            events.append(f"lock:{self.timeout}:enter")
            return self

        def __exit__(self, *_):
            nonlocal held
            events.append(f"lock:{self.timeout}:exit")
            held = False

    original_read_excel = module.pd.read_excel

    def locked_read_excel(*args, **kwargs):
        assert held is True
        events.append("read")
        return original_read_excel(*args, **kwargs)

    def locked_save_jobs(df):
        assert held is True
        events.append("save")

    monkeypatch.setattr(module.jobs, "XlsxLock", TrackingLock)
    monkeypatch.setattr(module.pd, "read_excel", locked_read_excel)
    monkeypatch.setattr(module.jobs, "save_jobs", locked_save_jobs)
    assert not hasattr(module, "_sync_applied_pdfs")

    assert module.main([]) == 0

    assert "read" in events and "save" in events
    assert events.index("read") < events.index("save")
    active_enter = max(
        index for index, event in enumerate(events[: events.index("read") + 1])
        if event.endswith(":enter")
    )
    active_exit = next(
        index for index, event in enumerate(events[events.index("save") :], events.index("save"))
        if event.endswith(":exit")
    )
    assert active_enter < events.index("read") < events.index("save") < active_exit
    manifest_path = paths["QUEUE_DIR"] / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["applied_pdf_sync"] == {
        "status": "skipped_deprecated",
        "reason": (
            "Resume.pdf presence never changes application status; use the "
            "reviewed archive-first lifecycle command"
        ),
    }
    assert (
        paths["APPLY_QUEUES_DIR"]
        / ".current_apply_queue_prev"
        / "existing-marker.txt"
    ).read_text(encoding="utf-8") == "keep"


def test_busy_queue_lock_fails_before_tracker_or_sync(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_busy_queue_test"
    )
    monkeypatch.setattr(module, "NIGHTLY_LOCK_PATH", tmp_path / "nightly.lock")
    queue_lock = tmp_path / "queue.lock"
    monkeypatch.setattr(module, "QUEUE_LOCK_PATH", queue_lock)
    monkeypatch.setattr(
        module,
        "_assert_jobs_lock_available",
        lambda: pytest.fail("busy queue must fail before tracker access"),
    )
    assert not hasattr(module, "_sync_applied_pdfs")

    with _held_lock(queue_lock):
        assert module.main([]) == module.LOCK_BUSY_EXIT_CODE


def test_busy_jobs_lock_fails_before_refresh(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_busy_jobs_test"
    )
    monkeypatch.setattr(module, "NIGHTLY_LOCK_PATH", tmp_path / "nightly.lock")
    monkeypatch.setattr(module, "QUEUE_LOCK_PATH", tmp_path / "queue.lock")
    jobs_lock = tmp_path / "jobs.lock"
    monkeypatch.setattr(module.jobs, "LOCK_FILE", jobs_lock)
    monkeypatch.setattr(
        module,
        "_run_refresh",
        lambda args: pytest.fail("busy jobs lock must fail before refresh"),
    )

    with _held_lock(jobs_lock):
        assert module.main(["--dry-run"]) == module.LOCK_BUSY_EXIT_CODE


def test_busy_nightly_requires_the_exact_inherited_token(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "refresh_current_apply_queue.py", "queue_refresh_nightly_token_test"
    )
    nightly_lock = tmp_path / "nightly.lock"
    token = "nightly-unit-token"
    payload = json.dumps({"pid": 1234, "token": token})
    monkeypatch.setattr(module, "NIGHTLY_LOCK_PATH", nightly_lock)

    with _held_lock(nightly_lock, payload):
        monkeypatch.delenv(module.NIGHTLY_LOCK_TOKEN_ENV, raising=False)
        with pytest.raises(module.RefreshLockBusy):
            with module._nightly_refresh_guard():
                pass

        monkeypatch.setenv(module.NIGHTLY_LOCK_TOKEN_ENV, "wrong-token")
        with pytest.raises(module.RefreshLockBusy):
            with module._nightly_refresh_guard():
                pass

        monkeypatch.setenv(module.NIGHTLY_LOCK_TOKEN_ENV, token)
        with module._nightly_refresh_guard():
            pass


def test_nightly_lock_exports_and_restores_the_child_token(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "run_nightly_pipeline.py", "nightly_queue_refresh_token_contract_test"
    )
    lock_path = tmp_path / "nightly.lock"
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _: "unit-token")
    monkeypatch.setenv(module.NIGHTLY_LOCK_TOKEN_ENV, "outer-token")

    with module._pipeline_lock(lock_path):
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["token"] == "unit-token"
        assert os.environ[module.NIGHTLY_LOCK_TOKEN_ENV] == "unit-token"

    assert os.environ[module.NIGHTLY_LOCK_TOKEN_ENV] == "outer-token"
