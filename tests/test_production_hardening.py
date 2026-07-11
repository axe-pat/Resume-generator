from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

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


def _completed(args: list[object], returncode: int = 0, stdout: str = ""):
    return subprocess.CompletedProcess(
        [str(item) for item in args], returncode, stdout, ""
    )


def test_track_2_parser_prefers_top_level_run_artifact() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_artifact_parser_test")

    assert (
        module._artifact_from_output(
            "Artifact: artifacts/nested-pass.json\n"
            "Run artifact: artifacts/exact-track-2-run.json\n"
        )
        == "artifacts/exact-track-2-run.json"
    )


def test_track_2_outer_timeout_terminates_the_subprocess_group(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_timeout_process_test")
    popen_kwargs: dict[str, object] = {}

    class FakeProcess:
        pid = 4242
        returncode = -15

        def __init__(self):
            self.communicate_calls = 0

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["track-2"], timeout)
            return "partial stdout\n", "partial stderr\n"

        def terminate(self):
            raise AssertionError("killpg should be used for the isolated process group")

        def kill(self):
            raise AssertionError(
                "SIGKILL should not be needed after graceful group termination"
            )

    process = FakeProcess()

    def fake_popen(cmd, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    signals: list[tuple[int, object]] = []
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        module.os, "killpg", lambda pid, sig: signals.append((pid, sig))
    )

    result = module._run_capture_print(
        ["track-2"],
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result.returncode == 124
    assert result.timed_out is True
    assert result.stdout == "partial stdout\n"
    assert popen_kwargs["start_new_session"] is True
    assert signals == [(4242, module.signal.SIGTERM)]


def test_track_2_timeout_is_an_explicit_maintenance_failure() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_timeout_failure_test")

    assert module._outreach_maintenance_failures(
        {
            "track_2_daily_run_returncode": 124,
            "track_2_daily_run_status": "timed_out",
            "track_2_timeout_seconds": 14400,
        }
    ) == [
        "track_2_daily_run_returncode:124",
        "track_2_daily_run:timed_out:14400s",
    ]


def test_track_2_timeout_defaults_to_four_hours_and_zero_disables(monkeypatch) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_timeout_args_test")

    monkeypatch.setattr(sys, "argv", ["run_nightly_pipeline.py"])
    assert module.parse_args().track_2_timeout_seconds == 14400

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_nightly_pipeline.py", "--track-2-timeout-seconds", "0"],
    )
    assert module.parse_args().track_2_timeout_seconds == 0


def test_scheduled_daily_engine_always_disables_the_direct_followup_lane(
    monkeypatch,
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_lane_owner_test")
    monkeypatch.setattr(sys, "argv", ["run_nightly_pipeline.py"])
    args = module.parse_args()
    # Even an older programmatic caller carrying this legacy value must not
    # forward it into the scheduled daily-engine subprocess.
    args.execute_linkedin_followups = True

    command = [str(part) for part in module._daily_engine_cmd(args, run_id="run-1")]

    assert command.count("--skip-linkedin-followups") == 1
    assert "--execute-linkedin-followups" not in command


def test_nightly_rejects_legacy_direct_followup_execution_before_side_effects(
    monkeypatch,
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_legacy_lane_test")
    monkeypatch.setattr(
        module,
        "run",
        lambda *args, **kwargs: pytest.fail("nightly side effects must not start"),
    )

    with pytest.raises(SystemExit, match="Track 2 owns inbox reconciliation"):
        module._run_pipeline_body(
            SimpleNamespace(execute_linkedin_followups=True),
            summary={"run_id": "run-1"},
            failures=[],
        )


def test_track_2_is_the_scheduled_refresh_and_followup_owner(monkeypatch) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_track2_owner_test")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_nightly_pipeline.py",
            "--skip-linkedin",
            "--skip-company-news",
            "--execute-track-2-daily-plan",
            "--outreach-resolve-limit",
            "0",
            "--outreach-enrich-limit",
            "0",
        ],
    )
    args = module.parse_args()
    captured: list[list[str]] = []

    def fake_capture(command, **kwargs):
        normalized = [str(part) for part in command]
        captured.append(normalized)
        result = _completed(command)
        setattr(result, "timed_out", False)
        return result

    monkeypatch.setattr(module, "_run_capture_print", fake_capture)

    summary = module._run_outreach_maintenance(args, run_id="run-1")

    track_2 = next(command for command in captured if "run-track-2-daily-plan" in command)
    assert "--refresh-linkedin" in track_2
    assert "--send-linkedin" in track_2
    assert track_2[track_2.index("--max-linkedin-followups") + 1] == "25"
    assert summary["track_2_daily_run_status"] == "failed_missing_artifact"
    assert summary["track_2_artifact_validation_returncode"] == 1
    assert "did not emit a readable" in summary["track_2_daily_run_failure"]


def test_daily_timeout_terminates_the_subprocess_group(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("run_daily_engine.py", "daily_timeout_process_test")
    popen_kwargs: dict[str, object] = {}

    class FakeProcess:
        pid = 4343
        returncode = -15

        def __init__(self):
            self.communicate_calls = 0

        def communicate(self, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["daily-stage"], timeout)
            return "partial stdout\n", "partial stderr\n"

        def kill(self):
            raise AssertionError("SIGKILL should not be needed after SIGTERM")

    process = FakeProcess()

    def fake_popen(command, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    signals: list[tuple[int, object]] = []
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        module.os, "killpg", lambda pid, sig: signals.append((pid, sig))
    )

    result = module.run_capture(["daily-stage"], cwd=tmp_path, timeout=1)

    assert result.returncode == 124
    assert result.stdout == "partial stdout\n"
    assert popen_kwargs["start_new_session"] is True
    assert signals == [(4343, module.signal.SIGTERM)]


def test_chrome_preflight_resets_only_after_failure(monkeypatch) -> None:
    module = _load_script("run_daily_engine.py", "daily_chrome_recovery_test")
    reset_reasons: list[str] = []
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: _completed(args[0]))
    monkeypatch.setattr(
        module,
        "reset_linkedin_chrome_session",
        lambda reason: reset_reasons.append(reason) or True,
    )

    assert module.ensure_linkedin_chrome_session("healthy") is True
    assert reset_reasons == []

    monkeypatch.setattr(
        module,
        "run",
        lambda *args, **kwargs: _completed(args[0], returncode=1),
    )
    assert module.ensure_linkedin_chrome_session("failed") is True
    assert reset_reasons == ["failed"]


def test_chrome_retry_wrapper_preserves_the_failed_check_status(tmp_path: Path) -> None:
    scripts = tmp_path / "discovery" / "scripts"
    scripts.mkdir(parents=True)
    wrapper = scripts / "ensure_chrome_9222.sh"
    wrapper.write_text(
        (SCRIPTS / "ensure_chrome_9222.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    check = scripts / "check_linkedin_live.sh"
    check.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    check.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    lsof.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "LINKEDIN_BROWSER_CHECK_ATTEMPTS": "2",
        "LINKEDIN_BROWSER_CHECK_RETRY_DELAY": "0",
    }

    result = subprocess.run([str(wrapper)], cwd=tmp_path, env=env, check=False)

    assert result.returncode == 7

    env["LINKEDIN_BROWSER_CHECK_ATTEMPTS"] = "0"
    invalid = subprocess.run([str(wrapper)], cwd=tmp_path, env=env, check=False)
    assert invalid.returncode == 2


def test_direct_followup_pull_is_resumable_and_resolves_exact_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_followup_pull_test")
    outreach = tmp_path / "Outreach"
    artifact = outreach / "artifacts" / "followup-drafts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    captured: list[str] = []

    def fake_capture(command, **kwargs):
        captured.extend(str(part) for part in command)
        return _completed(command, stdout="Draft artifact: artifacts/followup-drafts.json\n")

    monkeypatch.setattr(module, "run_capture", fake_capture)
    args = SimpleNamespace(
        linkedin_followup_limit=75,
        linkedin_followup_draft_limit=50,
        linkedin_followup_timeout=180,
    )

    result = module.run_linkedin_followup_pull(args)

    assert result.status == "completed"
    assert result.artifact == artifact.resolve()
    assert "--update-offset" in captured
    assert "--no-include-seen" not in captured


def test_direct_followup_send_requires_a_real_result_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_followup_send_test")
    outreach = tmp_path / "Outreach"
    outreach.mkdir()
    draft = outreach / "artifacts" / "draft.json"
    draft.parent.mkdir()
    draft.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    captured: list[str] = []

    def fake_capture(command, **kwargs):
        captured.extend(str(part) for part in command)
        return _completed(command, stdout="Artifact: artifacts/missing-send.json\n")

    monkeypatch.setattr(module, "run_capture", fake_capture)
    args = SimpleNamespace(
        linkedin_followup_send_limit=10,
        linkedin_followup_recommendation=[],
        execute_linkedin_followups=True,
        linkedin_followup_send_timeout=240,
    )

    result = module.run_linkedin_followup_send(args, draft)

    assert result.status == "failed_missing_artifact"
    assert result.returncode == 1
    assert result.artifact is None
    assert "--execute" in captured


def test_failed_direct_send_does_not_erase_the_draft_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_failed_send_manifest_test")
    outreach = tmp_path / "Outreach"
    draft = outreach / "artifacts" / "draft.json"
    draft.parent.mkdir(parents=True)
    draft.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")

    path = module.write_daily_engine_manifest(
        {
            "run_id": "failed-send-1",
            "artifacts": {
                "linkedin_followup_drafts": draft,
                "linkedin_followup_send": {
                    "status": "failed_missing_artifact",
                    "returncode": 1,
                    "artifact": "",
                },
                "linkedin_followup_send_results": None,
            },
        }
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["linkedin_followup_draft_artifacts"] == [str(draft)]
    assert payload["linkedin_followup_send_artifacts"] == []
    assert payload["artifacts"]["linkedin_followup_send"]["status"] == (
        "failed_missing_artifact"
    )


def test_direct_followup_execution_cannot_be_silently_skipped(monkeypatch) -> None:
    module = _load_script("run_daily_engine.py", "daily_followup_flag_guard_test")
    monkeypatch.setattr(
        module,
        "sync_applied_pdfs",
        lambda: pytest.fail("guard must run before pipeline side effects"),
    )
    args = SimpleNamespace(
        execute_sends=False,
        parallel_generation_outreach=False,
        execute_linkedin_followups=True,
        prepare_outreach=False,
    )

    with pytest.raises(SystemExit, match="requires --prepare-outreach"):
        module._run_daily_engine(
            args,
            {"run_started_at": "2026-07-11T01:00:00"},
        )


def test_daily_manifest_records_exact_typed_action_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_manifest_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    reconcile = tmp_path / "reconcile.json"
    reconcile.write_text("{}", encoding="utf-8")
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"source_artifact": str(reconcile)}), encoding="utf-8")
    followup_send = tmp_path / "followup-send.json"
    followup_send.write_text("{}", encoding="utf-8")
    invite = tmp_path / "invite-batch.json"
    invite.write_text("{}", encoding="utf-8")
    source_metrics = tmp_path / "source-metrics.json"
    action_queue = tmp_path / "action-queue.json"
    source_metrics.write_text(
        json.dumps(
            {
                "sources": {
                    "linkedin": {
                        "status": "ran",
                        "raw_count": 40,
                        "accepted_for_write": 3,
                    },
                    "handshake": {"status": "skipped"},
                    "jobspy": {
                        "status": "ran",
                        "raw_count": 100,
                        "accepted_for_write": 5,
                    },
                    "startup_apply": {
                        "status": "ran",
                        "raw_count": 5,
                        "accepted_for_write": 2,
                    },
                    "startup_relationship": {
                        "status": "ran",
                        "relationship_targets": 60,
                        "source_counts": {"yc": 30, "builtin": 30},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    action_queue.write_text(
        json.dumps({"counts": {"application_plus_outreach": 4, "follow_up": 2}}),
        encoding="utf-8",
    )

    path = module.write_daily_engine_manifest(
        {
            "run_id": "release-1",
            "run_started_at": "2026-07-11T01:00:00",
            "status": "completed",
            "artifacts": {
                "linkedin_followup_drafts": draft,
                "linkedin_followup_send_results": followup_send,
            },
            "outreach_execution": {
                "target_sends": 5,
                "sent_total": 2,
                "companies_attempted": 1,
                "invite_send_artifacts": [str(invite)],
                "company_runs": [{"company": "Acme", "sent_count": 2}],
            },
            "source_metrics": str(source_metrics),
            "action_queue": str(action_queue),
        }
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["invite_send_artifacts"] == [str(invite)]
    assert payload["linkedin_followup_draft_artifacts"] == [str(draft)]
    assert payload["linkedin_followup_send_artifacts"] == [str(followup_send)]
    assert payload["linkedin_reconcile_artifacts"] == [str(reconcile)]
    assert payload["source_metrics"] == str(source_metrics)
    assert payload["action_queue"] == str(action_queue)
    assert payload["app_invites"] == {
        "status": "completed",
        "target": 5,
        "sent": 2,
        "companies_attempted": 1,
        "company_runs": [{"company": "Acme", "sent_count": 2}],
        "failed_companies": [],
        "skipped_companies": [],
        "unresolved_companies": [],
    }
    assert payload["manifest_schema"] == "resume_generator.daily_engine_run_manifest"
    assert payload["manifest_version"] == 1
    assert payload["source_families"]["linkedin"]["raw_count"] == 40
    assert payload["source_families"]["handshake"] == {
        "status": "skipped",
        "raw_count": 0,
        "kept_count": 0,
        "details": {},
    }
    assert payload["source_families"]["startup_sources"]["raw_count"] == 65
    assert payload["source_families"]["resume_generator_app_queue"]["raw_count"] == 6
    assert payload["source_families"]["track_2"]["status"] == "skipped"
    assert payload["track_2_daily_run_artifacts"] == []
    assert payload["track_2_email_draft_artifacts"] == []
    assert payload["track_2_email_send_artifacts"] == []
    assert payload["email_channel"]["status"] == "skipped_track_2_not_run"


def test_manifest_normalizes_relative_reconcile_pointer_against_outreach(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_relative_pointer_test")
    validation = tmp_path / "validation"
    outreach = tmp_path / "Outreach"
    artifacts = outreach / "artifacts"
    artifacts.mkdir(parents=True)
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", validation)
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    reconcile = artifacts / "reconcile.json"
    reconcile.write_text("{}", encoding="utf-8")
    draft = artifacts / "draft.json"
    draft.write_text(
        json.dumps({"source_artifact": "artifacts/reconcile.json"}),
        encoding="utf-8",
    )

    path = module.write_daily_engine_manifest(
        {
            "run_id": "relative-1",
            "artifacts": {"linkedin_followup_drafts": "artifacts/draft.json"},
        }
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["linkedin_followup_draft_artifacts"] == [str(draft.resolve())]
    assert payload["linkedin_reconcile_artifacts"] == [str(reconcile.resolve())]


def test_source_metrics_and_manifest_share_the_normalized_run_id(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_normalized_run_id_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path)
    args = SimpleNamespace(
        run_id="nightly / run 1",
        window="24h",
        jobspy_score_limit=10,
    )

    source_metrics = module.write_source_run_metrics(
        args=args,
        run_started_at="2026-07-11T01:00:00",
        stage_metrics={},
        artifacts={},
        action_queue_path=None,
    )
    normalized = module._manifest_run_id(args.run_id)
    manifest_path = module.write_daily_engine_manifest(
        {"run_id": normalized, "source_metrics": str(source_metrics)}
    )
    source_payload = json.loads(source_metrics.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert normalized == "nightly-run-1"
    assert source_payload["run_id"] == normalized
    assert manifest_payload["run_id"] == normalized
    assert manifest_path.name == f"{normalized}-daily-engine-run-manifest.json"


def test_targeted_outreach_returns_exact_company_and_batch_counts(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_daily_engine.py", "daily_invite_manifest_test")
    outreach_root = tmp_path / "Outreach"
    artifacts_dir = outreach_root / "artifacts"
    artifacts_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach_root)
    monkeypatch.setattr(module, "OUTREACH_PYTHON", Path("python"))
    monkeypatch.setattr(module, "run", lambda cmd, **kwargs: _completed(cmd))

    prep_artifact = artifacts_dir / "prep.json"
    prep_artifact.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "name": "One",
                        "linkedin_url": "https://linkedin.example/one",
                        "score": 80,
                        "company": "Acme",
                        "target_company_match": True,
                        "target_company_evidence_company": "acme",
                        "note_qc": {"verdict": "send"},
                    },
                    {
                        "name": "Two",
                        "linkedin_url": "https://linkedin.example/two",
                        "score": 75,
                        "company": "Acme",
                        "target_company_match": True,
                        "target_company_evidence_company": "acme",
                        "note_qc": {"verdict": "send"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    invite_artifact = artifacts_dir / "invite-send-batch.json"
    invite_artifact.write_text(
        json.dumps({"results": [{"status": "sent"}, {"status": "sent"}]}),
        encoding="utf-8",
    )

    def fake_capture(cmd, **kwargs):
        normalized = [str(item) for item in cmd]
        if "send-invites" in normalized:
            return _completed(
                cmd, stdout="Artifact: artifacts/invite-send-batch.json\n"
            )
        return _completed(cmd, stdout="Artifact: artifacts/prep.json\n")

    monkeypatch.setattr(module, "run_capture", fake_capture)
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps({"application_plus_outreach": [{"company": "Acme"}]}),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        max_outreach_companies=5,
        target_sends=5,
        send_limit=0,
        per_company_send_limit=5,
        send_min_score=20,
        company_prep_timeout=30,
        send_timeout=30,
    )

    result = module.run_targeted_outreach_from_action_queue(args, queue)

    assert result["sent_total"] == 2
    assert result["invite_send_artifacts"] == [str(invite_artifact)]
    assert result["company_runs"][0]["company"] == "Acme"
    assert result["company_runs"][0]["safe_candidate_count"] == 2
    assert result["company_runs"][0]["sent_count"] == 2


def test_app_queue_target_send_blocks_failed_julia_company_filter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script("run_daily_engine.py", "daily_julia_send_safety_test")
    outreach_root = tmp_path / "Outreach"
    artifacts_dir = outreach_root / "artifacts"
    artifacts_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach_root)
    monkeypatch.setattr(module, "OUTREACH_PYTHON", Path("python"))
    monkeypatch.setattr(module, "run", lambda cmd, **kwargs: _completed(cmd))
    prep_artifact = artifacts_dir / "julia-failed-filter.json"
    prep_artifact.write_text(
        json.dumps(
            {
                "company": "Julia",
                "company_mode": "startup",
                "company_filter_status": "failed_exact_company_suggestion",
                "company_filter_error": (
                    "Could not find an exact company suggestion for 'Julia'."
                ),
                "startup_pool": {
                    "raw_count": 1,
                    "kept_count": 1,
                    "pool_mode": "micro",
                    "adaptive_send_min_score": -5,
                    "coverage_only": True,
                },
                "pass_summaries": [
                    {
                        "pass_name": "startup_company_coverage",
                        "fallback_used": True,
                        "coverage_only": True,
                        "alias_errors": [
                            "Julia: Could not find an exact company suggestion for 'Julia'."
                        ],
                    }
                ],
                "results": [
                    {
                        "name": "Julia (Gromis) Feuer",
                        "title": "MBA Candidate at UCLA Anderson Class of 2025",
                        "subtitle": "Julia (Gromis) Feuer",
                        "raw_text": (
                            "Julia (Gromis) Feuer MBA Candidate at UCLA Anderson "
                            "Class of 2025"
                        ),
                        "linkedin_url": "https://www.linkedin.com/in/juliagromis/",
                        "connection_degree": "2nd",
                        "score": 20,
                        "passes": ["startup_company_coverage"],
                        "target_company_match": True,
                        "target_company_evidence_company": "julia",
                        "note_qc": {"verdict": "send"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    capture_calls: list[list[str]] = []

    def fake_capture(cmd, **_kwargs):
        normalized = [str(item) for item in cmd]
        capture_calls.append(normalized)
        if "send-invites" in normalized:
            raise AssertionError("failed-filter Julia candidate reached live send")
        return _completed(cmd, stdout="Artifact: artifacts/julia-failed-filter.json\n")

    monkeypatch.setattr(module, "run_capture", fake_capture)
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps({"application_plus_outreach": [{"company": "Julia"}]}),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        max_outreach_companies=5,
        target_sends=1,
        send_limit=0,
        per_company_send_limit=1,
        send_min_score=-5,
        company_prep_timeout=30,
        send_timeout=30,
    )

    result = module.run_targeted_outreach_from_action_queue(args, queue)

    assert result["sent_total"] == 0
    assert result["skipped_companies"] == ["Julia"]
    assert result["company_runs"][0]["safe_candidate_count"] == 0
    assert result["company_runs"][0]["status"] == "no_safe_candidates"
    assert not any("send-invites" in call for call in capture_calls)
    assert module._candidate_mentions_company(
        "Julia",
        json.loads(prep_artifact.read_text(encoding="utf-8"))["results"][0],
    ) is False


def test_unattended_send_requires_company_bound_evidence_even_at_high_score() -> None:
    module = _load_script("run_daily_engine.py", "daily_company_binding_test")
    base = {
        "name": "Julia Person",
        "linkedin_url": "https://linkedin.example/julia",
        "score": 100,
        "company": "Julia",
        "connection_degree": "2nd",
        "note_qc": {"verdict": "send"},
    }

    assert not module._safe_unattended_candidate("Julia", base, min_score=20)
    assert not module._safe_unattended_candidate(
        "Julia",
        {
            **base,
            "target_company_match": True,
            "target_company_evidence_company": "Mattel",
        },
        min_score=20,
    )
    assert module._safe_unattended_candidate(
        "Julia",
        {
            **base,
            "target_company_match": True,
            "target_company_evidence_company": "Julia",
        },
        min_score=20,
    )


def test_manifest_surfaces_partial_app_invite_failure(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("run_daily_engine.py", "daily_app_failure_manifest_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path)
    action_queue = tmp_path / "queue.json"
    action_queue.write_text(
        json.dumps({"counts": {"application_plus_outreach": 2}}),
        encoding="utf-8",
    )
    source_metrics = tmp_path / "metrics.json"
    source_metrics.write_text(json.dumps({"sources": {}}), encoding="utf-8")

    manifest = module.write_daily_engine_manifest(
        {
            "run_id": "partial-app",
            "action_queue": str(action_queue),
            "source_metrics": str(source_metrics),
            "outreach_execution": {
                "mode": "targeted_execute",
                "target_sends": 5,
                "sent_total": 1,
                "companies_attempted": 2,
                "failed_companies": ["Justinian"],
                "company_runs": [
                    {
                        "company": "Julia",
                        "status": "sent",
                        "sent_count": 1,
                    },
                    {
                        "company": "Justinian",
                        "status": "prep_failed",
                        "prep_returncode": 1,
                        "prep_error": "No exact LinkedIn company suggestion",
                    },
                ],
            },
        }
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["app_invites"]["status"] == "partial_failed"
    assert payload["app_invites"]["failed_companies"] == ["Justinian"]
    assert payload["source_families"]["resume_generator_app_queue"]["status"] == "partial_failed"
    assert payload["source_families"]["resume_generator_app_queue"]["details"][
        "app_invite_status"
    ] == "partial_failed"


def test_nightly_binds_summary_to_exact_daily_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_manifest_binding_test")
    validation = tmp_path / "validation"
    validation.mkdir()
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", validation)
    shortlist = tmp_path / "generation_shortlist.json"
    shortlist.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(module, "CURRENT_SHORTLIST_JSON", shortlist)

    source_metrics = validation / "exact-source.json"
    source_metrics.write_text("{}", encoding="utf-8")
    action_queue = validation / "exact-actions.json"
    action_queue.write_text("{}", encoding="utf-8")
    created_at = "2026-07-11T01:00:00"
    run_id = module._run_id(created_at)

    def fake_run(cmd, **kwargs):
        normalized = [str(item) for item in cmd]
        if any(item.endswith("run_daily_engine.py") for item in normalized):
            assert normalized[normalized.index("--run-id") + 1] == run_id
            module.daily_engine_manifest_path(run_id).write_text(
                json.dumps(
                    {
                        "source_metrics": str(source_metrics),
                        "action_queue": str(action_queue),
                    }
                ),
                encoding="utf-8",
            )
        return _completed(cmd)

    monkeypatch.setattr(module, "run", fake_run)
    args = SimpleNamespace(
        skip_daily_engine=False,
        archive_generated_before_run=False,
        skip_clear_generated_queue=False,
        generate=False,
        skip_outreach_maintenance=True,
        cycle_config="offcycle_light",
        target_sends="auto",
        generation_dry_run=False,
        window="24h",
        skip_linkedin=False,
        skip_handshake=False,
        skip_jobspy=False,
        skip_startup_apply=False,
        skip_relationship_discovery=False,
        skip_linkedin_preflight=False,
        relationship_today="8",
        startup_limit_companies="20",
        startup_limit_jobs="50",
        jobspy_fetch_timeout="0",
        jobspy_results="0",
        linkedin_discovery_timeout="900",
        jobspy_query_index=[],
        prepare_outreach=True,
        execute_sends=True,
        per_company_send_limit="5",
        send_min_score="20",
        execute_linkedin_followups=False,
        generation_cap="10",
        non_handshake_generation_min="7.0",
        handshake_internal_generation_min="6.0",
        handshake_external_generation_min="6.5",
        handshake_unknown_generation_min="6.5",
    )
    summary = module._initial_summary(args, created_at=created_at, run_id=run_id)
    failures: list[str] = []

    module._run_pipeline_body(args, summary=summary, failures=failures)

    assert failures == []
    assert summary["daily_engine_manifest"] == str(
        module.daily_engine_manifest_path(run_id)
    )
    assert summary["source_metrics"] == str(source_metrics)
    assert summary["action_queue"] == str(action_queue)


def test_nightly_augments_manifest_with_exact_track_2_run_and_phases(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_track2_manifest_test")
    outreach = tmp_path / "Outreach"
    artifacts = outreach / "artifacts"
    artifacts.mkdir(parents=True)
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    phase_artifact = artifacts / "followup-send.json"
    phase_artifact.write_text("{}", encoding="utf-8")
    email_draft_artifact = artifacts / "track-2-email-drafts.json"
    email_draft_artifact.write_text("{}", encoding="utf-8")
    company_news_artifact = artifacts / "company-news.json"
    company_news_artifact.write_text("{}", encoding="utf-8")
    company_discovery_artifact = artifacts / "company-discovery.json"
    company_discovery_artifact.write_text("{}", encoding="utf-8")
    shared_json = outreach / "workspace" / "shared_discovery" / "queue.json"
    shared_json.parent.mkdir(parents=True)
    shared_json.write_text("{}", encoding="utf-8")
    shared_csv = shared_json.with_suffix(".csv")
    shared_csv.write_text("company\nAcme\n", encoding="utf-8")
    track_artifact = artifacts / "track-2-run.json"
    track_artifact.write_text(
        json.dumps(
            {
                "used": {
                    "total_actions": 3,
                    "linkedin_followups": 2,
                    "linkedin_invites": 1,
                },
                "summary": {"follow_up_connected_contact": 2},
                "phase_summary": {"1_2_linkedin_followups": 2},
                "phase_results": [
                    {
                        "phase": "1_2_linkedin_followups",
                        "status": "sent",
                        "budget": 2,
                        "touchpoints_added": 2,
                        "artifacts": [str(phase_artifact)],
                    },
                    {
                        "phase": "6_draft_email_touch",
                        "status": "drafted",
                        "budget": 1,
                        "draft_count": 1,
                        "artifact": str(email_draft_artifact),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "daily-engine-run-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_schema": "resume_generator.daily_engine_run_manifest",
                "manifest_version": 1,
                "source_families": {
                    "linkedin": {"status": "ran", "raw_count": 1, "kept_count": 1}
                },
            }
        ),
        encoding="utf-8",
    )
    summary = {
        "run_id": "nightly-1",
        "daily_engine_manifest": str(manifest),
        "shared_discovery_queue": {
            "status": "completed",
            "returncode": 0,
            "json": str(shared_json.relative_to(outreach)),
            "csv": str(shared_csv.relative_to(outreach)),
        },
        "outreach_maintenance": {
            "track_2_daily_run_returncode": 0,
            "track_2_daily_run_artifact": "artifacts/track-2-run.json",
            "company_news_status": "completed",
            "company_news_returncode": 0,
            "company_news_artifact": "artifacts/company-news.json",
            "company_discovery_returncode": 0,
            "company_discovery_artifact": "artifacts/company-discovery.json",
        },
    }

    module._augment_daily_engine_manifest(summary)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["track_2_daily_run_artifacts"] == [str(track_artifact)]
    assert payload["track_2_phase_artifacts"] == [
        str(phase_artifact),
        str(email_draft_artifact),
    ]
    assert payload["track_2_phase_results"][0]["status"] == "sent"
    assert payload["track_2"]["planned_action_count"] == 3
    assert payload["track_2"]["actual_action_count"] == 3
    assert payload["source_families"]["track_2"]["status"] == "ran"
    assert payload["source_families"]["track_2"]["raw_count"] == 3
    assert payload["source_families"]["track_2"]["kept_count"] == 3
    assert payload["track_2_email_draft_artifacts"] == [str(email_draft_artifact)]
    assert payload["track_2_email_send_artifacts"] == []
    assert payload["email_channel"]["status"] == "drafted_review_needed"
    assert payload["email_channel"]["smtp_configured"] is False
    assert payload["email_channel"]["draft_count"] == 1
    assert payload["email_channel"]["sent_count"] == 0
    assert len(payload["email_channel"]["blockers"]) == 2
    assert payload["nightly_extensions"]["run_id"] == "nightly-1"
    assert payload["nightly_extensions"]["linkedin_followup_owner"] == "track_2"
    assert payload["company_news_artifacts"] == [str(company_news_artifact)]
    assert payload["company_discovery_artifacts"] == [
        str(company_discovery_artifact)
    ]
    assert payload["shared_discovery_artifacts"] == [
        str(shared_json),
        str(shared_csv),
    ]


def test_nightly_manifest_records_track_2_timeout_without_claiming_completion(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_timeout_manifest_test")
    outreach = tmp_path / "Outreach"
    outreach.mkdir()
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    manifest = tmp_path / "daily-engine-run-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_schema": "resume_generator.daily_engine_run_manifest",
                "manifest_version": 1,
                "source_families": {},
            }
        ),
        encoding="utf-8",
    )
    summary = {
        "daily_engine_manifest": str(manifest),
        "outreach_maintenance": {
            "track_2_daily_run_returncode": 124,
            "track_2_daily_run_status": "timed_out",
            "track_2_timeout_seconds": 14400,
            "track_2_daily_run_failure": "outer timeout",
            "track_2_daily_run_artifact": "",
        },
    }

    module._augment_daily_engine_manifest(summary)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["track_2"]["status"] == "timed_out"
    assert payload["track_2"]["returncode"] == 124
    assert payload["track_2"]["timeout_seconds"] == 14400
    assert payload["track_2"]["failure"] == "outer timeout"
    assert payload["source_families"]["track_2"]["status"] == "timed_out"
    assert payload["source_families"]["track_2"]["kept_count"] == 0
    assert payload["email_channel"]["status"] == "skipped_track_2_failed"


def test_nightly_failure_still_writes_summary_and_attempts_report(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_finalization_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "nightly.lock")
    monkeypatch.setattr(
        module, "OPERATOR_MUTATION_LOCK_PATH", tmp_path / "operator_mutation.lock"
    )
    args = SimpleNamespace(
        skip_daily_engine=False,
        generation_dry_run=False,
        cycle_config="offcycle_light",
        target_sends="auto",
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(
        module,
        "_run_pipeline_body",
        lambda *a, **kw: (_ for _ in ()).throw(
            subprocess.CalledProcessError(9, ["boom"])
        ),
    )
    report_calls: list[tuple[Path, str, str]] = []

    def fake_report(summary_path: Path, since: str, run_id: str):
        report_calls.append((summary_path, since, run_id))
        return {"returncode": 0, "html_report": "/tmp/report.html"}

    monkeypatch.setattr(module, "_write_outreach_daily_report", fake_report)

    assert module.main() == 9
    summaries = list((tmp_path / "validation").glob("*-nightly-pipeline-summary.json"))
    assert len(summaries) == 1
    payload = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["pipeline_exception"]["returncode"] == 9
    assert "pipeline_exception:CalledProcessError:9" in payload["failures"]
    assert [call[0] for call in report_calls] == summaries
    assert report_calls[0][1] == payload["created_at"]
    assert report_calls[0][2] == payload["run_id"]


def test_nightly_report_writer_passes_run_id_and_accepts_only_exact_binding(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_report_binding_test")
    outreach = tmp_path / "Outreach"
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    run_id = "20260711-150851"
    since = "2026-07-11T15:08:51"
    summary_path = tmp_path / f"{run_id}-nightly-pipeline-summary.json"
    summary_path.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    report_dir = outreach / "workspace" / "reports"
    html_dir = report_dir / "daily_html"
    report_dir.mkdir(parents=True)
    html_dir.mkdir(parents=True)
    summary_artifact = report_dir / f"{run_id}-daily-run-report.json"
    markdown = report_dir / f"{run_id}-daily-run-report.md"
    html = html_dir / f"{run_id}-daily-run-report.html"
    summary_artifact.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "report_mode": "run_scoped",
                "since": since,
                "nightly_summary": str(summary_path),
                "run_status": "failed_or_incomplete",
                "track_2_execution": {"status": "partial_failed"},
            }
        ),
        encoding="utf-8",
    )
    markdown.write_text(f"# Daily report\n\nRun ID: `{run_id}`\n", encoding="utf-8")
    html.write_text(f"<p>Run ID {run_id}</p>", encoding="utf-8")
    latest_html = html_dir / "daily_run_report.html"
    latest_html.write_text("latest mirror", encoding="utf-8")
    stdout = "\n".join(
        [
            f"Latest HTML report: {latest_html}",
            f"Summary artifact: {summary_artifact}",
            f"Daily report: {markdown}",
            f"HTML report artifact: {html}",
            f"HTML report: {html}",
        ]
    )
    captured: list[list[object]] = []

    def fake_run(cmd: list[object], *, cwd: Path):
        captured.append(cmd)
        assert cwd == outreach
        return _completed(cmd, stdout=stdout)

    monkeypatch.setattr(module, "_run_capture_print", fake_run)

    result = module._write_outreach_daily_report(summary_path, since, run_id)

    assert result["returncode"] == 0
    assert result["html_report"] == str(html.resolve())
    assert result["summary_artifact"] == str(summary_artifact.resolve())
    assert captured[0][captured[0].index("--run-id") + 1] == run_id
    assert result.get("binding_error") is None


def test_nightly_report_writer_rejects_timestamp_named_report(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_report_rejection_test")
    outreach = tmp_path / "Outreach"
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    run_id = "20260711-150851"
    since = "2026-07-11T15:08:51"
    summary_path = tmp_path / f"{run_id}-nightly-pipeline-summary.json"
    summary_path.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    report_dir = outreach / "workspace" / "reports"
    html_dir = report_dir / "daily_html"
    report_dir.mkdir(parents=True)
    html_dir.mkdir(parents=True)
    old_stem = "20260711-173446-daily-run-report"
    summary_artifact = report_dir / f"{old_stem}.json"
    markdown = report_dir / f"{old_stem}.md"
    html = html_dir / f"{old_stem}.html"
    summary_artifact.write_text(
        json.dumps(
            {
                "report_mode": "run_scoped",
                "since": since,
                "nightly_summary": str(summary_path),
            }
        ),
        encoding="utf-8",
    )
    markdown.write_text("old timestamp report", encoding="utf-8")
    html.write_text("old timestamp report", encoding="utf-8")
    stdout = "\n".join(
        [
            f"Summary artifact: {summary_artifact}",
            f"Daily report: {markdown}",
            f"HTML report artifact: {html}",
            f"HTML report: {html}",
        ]
    )
    monkeypatch.setattr(
        module,
        "_run_capture_print",
        lambda cmd, *, cwd: _completed(cmd, stdout=stdout),
    )

    result = module._write_outreach_daily_report(summary_path, since, run_id)

    assert result["producer_returncode"] == 0
    assert result["returncode"] == 2
    assert "expected_filename=20260711-150851-daily-run-report.json" in result["binding_error"]
    assert "run_id_mismatch" in result["binding_error"]


def test_nightly_argument_failure_still_writes_summary_and_attempts_report(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "run_nightly_pipeline.py", "nightly_argument_finalization_test"
    )
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "nightly.lock")
    monkeypatch.setattr(
        module, "OPERATOR_MUTATION_LOCK_PATH", tmp_path / "operator_mutation.lock"
    )
    monkeypatch.setattr(
        module, "parse_args", lambda: (_ for _ in ()).throw(SystemExit(2))
    )
    report_calls: list[tuple[Path, str, str]] = []

    def fake_report(summary_path: Path, since: str, run_id: str):
        report_calls.append((summary_path, since, run_id))
        return {"returncode": 0, "html_report": "/tmp/report.html"}

    monkeypatch.setattr(module, "_write_outreach_daily_report", fake_report)

    assert module.main() == 2
    summaries = list((tmp_path / "validation").glob("*-nightly-pipeline-summary.json"))
    assert len(summaries) == 1
    payload = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["argument_parse_failure"]["returncode"] == 2
    assert payload["failures"] == ["argument_parse:2"]
    assert [call[0] for call in report_calls] == summaries
    assert report_calls[0][1] == payload["created_at"]
    assert report_calls[0][2] == payload["run_id"]


def test_nightly_holds_operator_mutation_lock_inside_pipeline_lock(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_lock_order_test")
    assert module.OPERATOR_MUTATION_LOCK_PATH == (
        module.APP_SUPPORT / "operator_mutation.lock"
    )
    nightly_lock = tmp_path / "nightly_pipeline.lock"
    operator_lock = tmp_path / "operator_mutation.lock"
    monkeypatch.setattr(module, "LOCK_PATH", nightly_lock)
    monkeypatch.setattr(module, "OPERATOR_MUTATION_LOCK_PATH", operator_lock)
    args = SimpleNamespace(
        skip_daily_engine=True,
        generation_dry_run=False,
        cycle_config="offcycle_light",
        target_sends="auto",
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(
        module,
        "_initial_summary",
        lambda *a, **kw: {"created_at": kw["created_at"], "run_id": kw["run_id"]},
    )
    events: list[str] = []

    @contextmanager
    def fake_pipeline_lock(path: Path):
        assert path == nightly_lock
        events.append("pipeline_enter")
        try:
            yield
        finally:
            events.append("pipeline_exit")

    @contextmanager
    def fake_operator_lock(path: Path):
        assert path == operator_lock
        assert events == ["pipeline_enter"]
        events.append("operator_enter")
        try:
            yield
        finally:
            events.append("operator_exit")

    monkeypatch.setattr(module, "_pipeline_lock", fake_pipeline_lock)
    monkeypatch.setattr(module, "_operator_mutation_lock", fake_operator_lock)
    monkeypatch.setattr(
        module,
        "_run_pipeline_body",
        lambda *a, **kw: events.append("pipeline_body"),
    )
    monkeypatch.setattr(
        module,
        "_finalize_summary_and_report",
        lambda **kw: events.append("finalize"),
    )

    assert module.main() == 0
    assert events == [
        "pipeline_enter",
        "operator_enter",
        "pipeline_body",
        "finalize",
        "operator_exit",
        "pipeline_exit",
    ]


def test_scheduler_is_unattended_by_default_and_records_timestamped_log(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("nightly_prompt.py", "nightly_unattended_test")
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "nightly_pipeline_20260711-010000.log"
    args = SimpleNamespace(
        scheduled_time="01:00",
        state_path=str(state_path),
        pipeline_args="--generate",
        force=True,
        prompt=False,
        require_production_attestation=False,
        production_attestation=str(tmp_path / "attestation.json"),
        production_check_only=False,
        check_only=False,
        verbose=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "scheduler.lock")
    monkeypatch.setattr(
        module, "_prompt_choice", lambda *a, **kw: pytest.fail("prompt must be opt-in")
    )
    monkeypatch.setattr(module, "_run_pipeline", lambda _args: (0, log_path))

    assert module.main() == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_attempt_date"]
    assert state["last_run_exit_code"] == 0
    assert state["last_run_log"] == str(log_path)


def test_scheduler_release_guard_fails_before_marking_a_live_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("nightly_prompt.py", "nightly_guard_test")
    state_path = tmp_path / "state.json"
    args = SimpleNamespace(
        scheduled_time="01:00",
        state_path=str(state_path),
        pipeline_args="--generate",
        force=True,
        prompt=False,
        require_production_attestation=True,
        production_attestation=str(tmp_path / "missing.json"),
        production_check_only=False,
        check_only=False,
        verbose=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "scheduler.lock")
    monkeypatch.setattr(
        module,
        "validate_attestation",
        lambda **kwargs: (_ for _ in ()).throw(
            module.ProductionReleaseError("untested HEAD")
        ),
    )
    monkeypatch.setattr(
        module, "_run_pipeline", lambda _args: pytest.fail("must not run")
    )

    assert module.main() == 78
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_guard_failure"] == "untested HEAD"
    assert "last_attempt_date" not in state


def test_production_check_only_validates_without_reading_or_mutating_scheduler_state(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_script("nightly_prompt.py", "nightly_production_check_test")
    state_path = tmp_path / "state.json"
    state_path.write_text('{"sentinel": true}\n', encoding="utf-8")
    args = SimpleNamespace(
        state_path=str(state_path),
        production_check_only=True,
        production_attestation=str(tmp_path / "attestation.json"),
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(
        module,
        "validate_attestation",
        lambda **kwargs: {
            "status": "valid",
            "repositories": {
                "resume_generator": {"head": "resume-sha"},
                "outreach": {"head": "outreach-sha"},
            },
        },
    )
    monkeypatch.setattr(
        module, "_run_pipeline", lambda _args: pytest.fail("must not run")
    )

    assert module.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "valid"
    assert output["check"] == "production_release_and_desktop_access"
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"sentinel": True}


def _init_repo(path: Path, filename: str) -> None:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"], cwd=path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=path, check=True)
    target = path / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("release\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release"], cwd=path, check=True, capture_output=True
    )


def test_production_attestation_requires_clean_main_and_exact_tested_heads(
    tmp_path: Path,
) -> None:
    module = _load_script("production_release.py", "production_release_test")
    resume = tmp_path / "resume"
    outreach = tmp_path / "outreach"
    _init_repo(resume, "jobs.py")
    _init_repo(outreach, "main.py")
    attestation = tmp_path / "production_release.json"

    module.record_attestation(
        path=attestation,
        resume_root=resume,
        outreach_root=outreach,
        test_evidence=["resume tests passed", "outreach tests passed"],
    )
    assert (
        module.validate_attestation(
            path=attestation,
            resume_root=resume,
            outreach_root=outreach,
        )["status"]
        == "valid"
    )

    (resume / "jobs.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(module.ProductionReleaseError, match="dirty"):
        module.validate_attestation(
            path=attestation,
            resume_root=resume,
            outreach_root=outreach,
        )
    subprocess.run(["git", "add", "jobs.py"], cwd=resume, check=True)
    subprocess.run(
        ["git", "commit", "-m", "untested"], cwd=resume, check=True, capture_output=True
    )
    with pytest.raises(
        module.ProductionReleaseError, match="does not match tested SHA"
    ):
        module.validate_attestation(
            path=attestation,
            resume_root=resume,
            outreach_root=outreach,
        )


def test_launch_agent_installer_defaults_to_unattended_guarded_mode(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "RESUMEGEN_NIGHTLY_LOAD": "0",
        "RESUMEGEN_NIGHTLY_ARGS": "--generate",
    }
    script = SCRIPTS / "install_nightly_launch_agent.sh"
    subprocess.run(
        [str(script)], cwd=ROOT, env=env, check=True, capture_output=True, text=True
    )
    plist_path = (
        home / "Library" / "LaunchAgents" / "com.akshat.resumegenerator.nightly.plist"
    )
    subprocess.run(
        ["plutil", "-lint", str(plist_path)], check=True, capture_output=True
    )
    plist = plist_path.read_text(encoding="utf-8")

    assert "<integer>1</integer>" in plist
    assert "--require-production-attestation" in plist
    assert "--prompt" not in plist
    assert "Library/Logs/ResumeGenerator" in plist

    env["RESUMEGEN_NIGHTLY_MODE"] = "prompt"
    subprocess.run(
        [str(script)], cwd=ROOT, env=env, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["plutil", "-lint", str(plist_path)], check=True, capture_output=True
    )
    prompt_plist = plist_path.read_text(encoding="utf-8")
    assert "--prompt" in prompt_plist

    env["RESUMEGEN_NIGHTLY_MODE"] = "check"
    subprocess.run(
        [str(script)], cwd=ROOT, env=env, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["plutil", "-lint", str(plist_path)], check=True, capture_output=True
    )
    check_plist = plist_path.read_text(encoding="utf-8")
    assert "--production-check-only" in check_plist
    assert "--prompt" not in check_plist
