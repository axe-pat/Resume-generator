import sys

import pytest

import jobs


def _run_generate_main(monkeypatch, results, *extra_args):
    monkeypatch.setattr(jobs, "cmd_generate", lambda _args: results)
    monkeypatch.setattr(
        sys,
        "argv",
        ["jobs.py", "generate", "--company", "Example", *extra_args],
    )
    return jobs.main()


def test_generate_main_exits_nonzero_when_any_live_target_fails(monkeypatch):
    results = [
        {"company": "Good", "success": True},
        {"company": "Bad", "success": False, "error": "release blocked"},
    ]

    with pytest.raises(SystemExit) as exc:
        _run_generate_main(monkeypatch, results)

    assert exc.value.code == 1


def test_generate_main_keeps_zero_exit_for_all_successes(monkeypatch):
    assert _run_generate_main(
        monkeypatch,
        [{"company": "Good", "success": True}],
    ) is None


def test_generate_main_does_not_treat_dry_run_preview_as_failure(monkeypatch):
    assert _run_generate_main(
        monkeypatch,
        [{"company": "Preview", "success": False, "dry_run": True}],
        "--dry-run",
    ) is None


def test_pipeline_propagates_generation_results(monkeypatch):
    args = type("Args", (), {"min_score": 8.0, "top": 1, "dry_run": False})()
    promoted = [{"company": "Example"}]
    expected = [{"company": "Example", "success": False}]
    monkeypatch.setattr(jobs, "cmd_promote", lambda _args: promoted)
    monkeypatch.setattr(
        jobs,
        "cmd_generate",
        lambda _args, promoted_jobs=None: expected,
    )

    assert jobs.cmd_pipeline(args) is expected
