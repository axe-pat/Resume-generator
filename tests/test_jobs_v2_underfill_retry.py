import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import pytest

import jobs
from shared.llm_provider import CURSOR_TRANSIENT_EXIT_CODE
from shared.resume_runtime import (
    RUNTIME_MODE_ENV,
    V2_BULLET_BUDGET_ENV,
    V2_PAGE_UNDERFILLED_EXIT_CODE,
)


def _completed(cmd, returncode):
    return subprocess.CompletedProcess(cmd, returncode)


def test_default_v2_resume_only_underfill_retries_once_with_isolated_11_proof_env(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "strategy.json").write_text("{}", encoding="utf-8")
    calls = []
    results = iter((V2_PAGE_UNDERFILLED_EXIT_CODE, 0))

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs))
        return _completed(cmd, next(results))

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    notices = []
    base = {RUNTIME_MODE_ENV: "v2", "UNCHANGED": "yes"}

    result, attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example", "--resume-only"],
        app_dir=tmp_path,
        timeout=100,
        silent=False,
        resume_only=True,
        base_environment=base,
        on_retry=lambda: notices.append("retry"),
    )

    assert result.returncode == 0
    assert attempted is True
    assert notices == ["retry"]
    assert len(calls) == 2
    first_cmd, first_kwargs = calls[0]
    second_cmd, second_kwargs = calls[1]
    assert "--no-strategy" not in first_cmd
    assert "--no-strategy" in second_cmd
    assert V2_BULLET_BUDGET_ENV not in first_kwargs["env"]
    assert second_kwargs["env"][V2_BULLET_BUDGET_ENV] == "11"
    assert first_kwargs["env"] is not second_kwargs["env"]
    assert base == {RUNTIME_MODE_ENV: "v2", "UNCHANGED": "yes"}
    assert 0 < second_kwargs["timeout"] <= first_kwargs["timeout"] == 100


def test_second_underfill_is_returned_without_a_third_attempt(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _completed(cmd, V2_PAGE_UNDERFILLED_EXIT_CODE)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    result, attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example", "--resume-only", "--no-strategy"],
        app_dir=tmp_path,
        timeout=100,
        silent=True,
        resume_only=True,
        base_environment={RUNTIME_MODE_ENV: "v2"},
    )

    assert attempted is True
    assert result.returncode == V2_PAGE_UNDERFILLED_EXIT_CODE
    assert len(calls) == 2


def test_cursor_provider_interruption_resumes_once_with_same_environment(
    monkeypatch,
    tmp_path,
):
    calls = []
    results = iter((CURSOR_TRANSIENT_EXIT_CODE, 0))

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs))
        return _completed(cmd, next(results))

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    notices = []
    base = {RUNTIME_MODE_ENV: "v2", "RESUME_LLM_PROVIDER": "cursor"}

    result, underfill_attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example", "--resume-only"],
        app_dir=tmp_path,
        timeout=100,
        silent=True,
        resume_only=True,
        base_environment=base,
        on_provider_retry=lambda: notices.append("provider-retry"),
    )

    assert result.returncode == 0
    assert underfill_attempted is False
    assert notices == ["provider-retry"]
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert calls[0][1]["env"] == calls[1][1]["env"] == base
    assert calls[0][1]["env"] is not calls[1][1]["env"]


def test_cursor_provider_interruption_has_only_one_process_retry(
    monkeypatch,
    tmp_path,
):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _completed(cmd, CURSOR_TRANSIENT_EXIT_CODE)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    result, underfill_attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example", "--resume-only"],
        app_dir=tmp_path,
        timeout=100,
        silent=True,
        resume_only=True,
        base_environment={RUNTIME_MODE_ENV: "v2"},
    )

    assert result.returncode == CURSOR_TRANSIENT_EXIT_CODE
    assert underfill_attempted is False
    assert len(calls) == 2


def test_provider_resume_can_still_use_distinct_underfill_recovery(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "strategy.json").write_text("{}", encoding="utf-8")
    calls = []
    results = iter((CURSOR_TRANSIENT_EXIT_CODE, V2_PAGE_UNDERFILLED_EXIT_CODE, 0))

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs))
        return _completed(cmd, next(results))

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    result, underfill_attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example", "--resume-only"],
        app_dir=tmp_path,
        timeout=100,
        silent=True,
        resume_only=True,
        base_environment={RUNTIME_MODE_ENV: "v2"},
    )

    assert result.returncode == 0
    assert underfill_attempted is True
    assert len(calls) == 3
    assert V2_BULLET_BUDGET_ENV not in calls[0][1]["env"]
    assert V2_BULLET_BUDGET_ENV not in calls[1][1]["env"]
    assert calls[2][1]["env"][V2_BULLET_BUDGET_ENV] == "11"
    assert "--no-strategy" in calls[2][0]


@pytest.mark.parametrize(
    ("returncode", "environment", "resume_only"),
    [
        (1, {RUNTIME_MODE_ENV: "v2"}, True),
        (0, {RUNTIME_MODE_ENV: "v2"}, True),
        (V2_PAGE_UNDERFILLED_EXIT_CODE, {}, True),
        (V2_PAGE_UNDERFILLED_EXIT_CODE, {RUNTIME_MODE_ENV: "legacy"}, True),
        (V2_PAGE_UNDERFILLED_EXIT_CODE, {RUNTIME_MODE_ENV: "shadow"}, True),
        (
            V2_PAGE_UNDERFILLED_EXIT_CODE,
            {RUNTIME_MODE_ENV: "v2", V2_BULLET_BUDGET_ENV: "10"},
            True,
        ),
        (
            V2_PAGE_UNDERFILLED_EXIT_CODE,
            {RUNTIME_MODE_ENV: "v2", V2_BULLET_BUDGET_ENV: "11"},
            True,
        ),
        (V2_PAGE_UNDERFILLED_EXIT_CODE, {RUNTIME_MODE_ENV: "v2"}, False),
    ],
)
def test_non_retryable_child_results_run_exactly_once(
    monkeypatch,
    tmp_path,
    returncode,
    environment,
    resume_only,
):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _completed(cmd, returncode)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    result, attempted = jobs._run_professional_child_with_v2_fill_recovery(
        ["python", "run_app.py", "Example"],
        app_dir=tmp_path,
        timeout=100,
        silent=False,
        resume_only=resume_only,
        base_environment=environment,
    )

    assert result.returncode == returncode
    assert attempted is False
    assert len(calls) == 1


def test_v2_underfill_retry_respects_one_total_timeout(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return _completed(cmd, V2_PAGE_UNDERFILLED_EXIT_CODE)

    times = iter((10.0, 111.0))
    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    monkeypatch.setattr(jobs.time, "monotonic", lambda: next(times))

    with pytest.raises(subprocess.TimeoutExpired):
        jobs._run_professional_child_with_v2_fill_recovery(
            ["python", "run_app.py", "Example"],
            app_dir=tmp_path,
            timeout=100,
            silent=False,
            resume_only=True,
            base_environment={RUNTIME_MODE_ENV: "v2"},
        )

    assert len(calls) == 1


def test_parallel_children_cannot_leak_11_proof_environment(monkeypatch, tmp_path):
    lock = Lock()
    calls = []
    attempts = {"retry-me": 0, "normal": 0}

    def fake_run(cmd, **kwargs):
        name = cmd[2]
        with lock:
            attempts[name] += 1
            calls.append((name, attempts[name], kwargs["env"]))
            if name == "retry-me" and attempts[name] == 1:
                return _completed(cmd, V2_PAGE_UNDERFILLED_EXIT_CODE)
        return _completed(cmd, 0)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    base = {RUNTIME_MODE_ENV: "v2"}

    def run(name):
        return jobs._run_professional_child_with_v2_fill_recovery(
            ["python", "run_app.py", name],
            app_dir=Path(tmp_path) / name,
            timeout=100,
            silent=True,
            resume_only=True,
            base_environment=base,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        retry_future = executor.submit(run, "retry-me")
        normal_future = executor.submit(run, "normal")
        retry_result = retry_future.result()
        normal_result = normal_future.result()

    assert retry_result[1] is True
    assert normal_result[1] is False
    normal_envs = [env for name, _attempt, env in calls if name == "normal"]
    retry_envs = [env for name, _attempt, env in calls if name == "retry-me"]
    assert len(normal_envs) == 1
    assert V2_BULLET_BUDGET_ENV not in normal_envs[0]
    assert V2_BULLET_BUDGET_ENV not in retry_envs[0]
    assert retry_envs[1][V2_BULLET_BUDGET_ENV] == "11"
    assert base == {RUNTIME_MODE_ENV: "v2"}
