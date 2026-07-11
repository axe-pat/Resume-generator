from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
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
        "target": 5,
        "sent": 2,
        "companies_attempted": 1,
        "company_runs": [{"company": "Acme", "sent_count": 2}],
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
                        "note_qc": {"verdict": "send"},
                    },
                    {
                        "name": "Two",
                        "linkedin_url": "https://linkedin.example/two",
                        "score": 75,
                        "company": "Acme",
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
        "daily_engine_manifest": str(manifest),
        "outreach_maintenance": {
            "track_2_daily_run_returncode": 0,
            "track_2_daily_run_artifact": "artifacts/track-2-run.json",
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
    report_calls: list[Path] = []

    def fake_report(summary_path: Path, since: str):
        report_calls.append(summary_path)
        return {"returncode": 0, "html_report": "/tmp/report.html"}

    monkeypatch.setattr(module, "_write_outreach_daily_report", fake_report)

    assert module.main() == 9
    summaries = list((tmp_path / "validation").glob("*-nightly-pipeline-summary.json"))
    assert len(summaries) == 1
    payload = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["pipeline_exception"]["returncode"] == 9
    assert "pipeline_exception:CalledProcessError:9" in payload["failures"]
    assert report_calls == summaries


def test_nightly_argument_failure_still_writes_summary_and_attempts_report(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(
        "run_nightly_pipeline.py", "nightly_argument_finalization_test"
    )
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    monkeypatch.setattr(
        module, "parse_args", lambda: (_ for _ in ()).throw(SystemExit(2))
    )
    report_calls: list[Path] = []

    def fake_report(summary_path: Path, since: str):
        report_calls.append(summary_path)
        return {"returncode": 0, "html_report": "/tmp/report.html"}

    monkeypatch.setattr(module, "_write_outreach_daily_report", fake_report)

    assert module.main() == 2
    summaries = list((tmp_path / "validation").glob("*-nightly-pipeline-summary.json"))
    assert len(summaries) == 1
    payload = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["argument_parse_failure"]["returncode"] == 2
    assert payload["failures"] == ["argument_parse:2"]
    assert report_calls == summaries


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
