from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import shlex
import signal
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
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


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _ensure_chrome_fixture(
    tmp_path: Path, *, listener_command: str, owner_token: str
) -> tuple[Path, dict[str, str], Path, subprocess.Popen]:
    scripts = tmp_path / "discovery" / "scripts"
    scripts.mkdir(parents=True)
    ensure = scripts / "ensure_chrome_9222.sh"
    ensure.write_text(
        (SCRIPTS / "ensure_chrome_9222.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ensure.chmod(0o755)
    _write_executable(scripts / "check_linkedin_live.sh", "#!/usr/bin/env bash\nexit 0\n")
    profile = tmp_path / "chrome-profile"
    profile.mkdir()
    state_path = tmp_path / "listener.pid"
    command_path = tmp_path / "listener.command"
    listener = subprocess.Popen(["sleep", "60"])
    state_path.write_text(f"{listener.pid}\n", encoding="utf-8")
    command_path.write_text(f"{listener_command}\n", encoding="utf-8")

    _write_executable(
        scripts / "launch_linkedin_browser.sh",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "nohup sleep 60 >/dev/null 2>&1 &",
                f"echo $! > {shlex.quote(str(state_path))}",
                "printf '%s\\n' \"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
                "--user-data-dir=${LINKEDIN_CHROME_USER_DATA_DIR} "
                "--remote-debugging-port=${LINKEDIN_DEBUG_PORT:-9222} "
                "--resume-generator-browser-owner=${RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN}\" "
                f"> {shlex.quote(str(command_path))}",
                "",
            ]
        ),
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "lsof",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"state={shlex.quote(str(state_path))}",
                'pid="$(head -n 1 "$state" 2>/dev/null || true)"',
                '[[ "$pid" =~ ^[0-9]+$ ]] || exit 1',
                'stat="$(/bin/ps -p "$pid" -o stat= 2>/dev/null || true)"',
                'if [[ -n "$stat" && "$stat" != *Z* ]]; then echo "$pid"; exit 0; fi',
                ': > "$state"',
                "exit 1",
                "",
            ]
        ),
    )
    _write_executable(
        fake_bin / "ps",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"cat {shlex.quote(str(command_path))}",
                "",
            ]
        ),
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "LINKEDIN_CHROME_USER_DATA_DIR": str(profile),
        "LINKEDIN_BROWSER_LAUNCH_WAIT": "0",
        "LINKEDIN_BROWSER_CHECK_ATTEMPTS": "1",
        "LINKEDIN_BROWSER_CHECK_RETRY_DELAY": "0",
        "RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN": owner_token,
    }
    return ensure, env, state_path, listener


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def test_canonical_unattended_contract_enables_both_delivery_lanes() -> None:
    module = _load_script("nightly_contract.py", "nightly_contract_unit_test")
    args = list(module.PRODUCTION_NIGHTLY_ARGS)

    assert module.validate_production_nightly_args(args) == []
    assert args[args.index("--cycle-config") + 1] == "offcycle_light"
    assert args[args.index("--target-sends") + 1] == "auto"
    assert "--execute-sends" in args
    assert "--execute-track-2-daily-plan" in args
    assert "--track-2-send-linkedin" in args
    assert "--execute-linkedin-followups" not in args


def test_two_slot_contract_runs_delivery_once_and_zeroes_overnight_drafts() -> None:
    module = _load_script("nightly_contract.py", "nightly_two_slot_contract_test")
    evening = list(
        module.production_slot_args(
            module.EVENING_DELIVERY_SLOT, include_discovery=False
        )
    )
    overnight = list(
        module.production_slot_args(
            module.OVERNIGHT_MAINTENANCE_SLOT, include_discovery=False
        )
    )

    assert "--track-2-send-linkedin" in evening
    assert evening[evening.index("--track-2-email-drafts") + 1] == "auto"
    assert "--track-2-send-linkedin" not in overnight
    for option in (
        "--track-2-linkedin-invites",
        "--track-2-linkedin-followups",
        "--track-2-email-drafts",
    ):
        assert overnight[overnight.index(option) + 1] == "0"
    for contract in (evening, overnight):
        assert "--execute-track-2-daily-plan" in contract
        assert "--skip-daily-engine" in contract
        assert "--skip-shared-discovery" in contract
        assert "--generate" not in contract
        assert "--execute-sends" not in contract


def test_discovery_overlay_is_available_to_either_slot_but_not_maintenance() -> None:
    module = _load_script("nightly_contract.py", "nightly_discovery_overlay_test")

    for slot in module.PRODUCTION_SLOTS:
        discovery = list(module.production_slot_args(slot, include_discovery=True))
        maintenance = list(module.production_slot_args(slot, include_discovery=False))
        assert "--generate" in discovery
        assert "--execute-sends" in discovery
        assert "--skip-daily-engine" not in discovery
        assert "--generate" not in maintenance
        assert "--execute-sends" not in maintenance
        assert "--skip-daily-engine" in maintenance
        assert module.validate_production_slot_args(
            discovery, slot=slot, include_discovery=True
        ) == []
        assert module.validate_production_slot_args(
            maintenance, slot=slot, include_discovery=False
        ) == []


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("--cycle-config offcycle_light --target-sends 0", "--target-sends"),
        (
            "--cycle-config offcycle_light --prepare-outreach --execute-sends "
            "--target-sends auto --execute-track-2-daily-plan",
            "--track-2-send-linkedin",
        ),
    ],
)
def test_unattended_contract_rejects_silent_no_send_regressions(
    candidate: str, expected: str
) -> None:
    module = _load_script("nightly_contract.py", f"nightly_contract_reject_{expected}")

    errors = module.validate_production_nightly_args(shlex.split(candidate))

    assert any(expected in error for error in errors)


def test_installer_writes_two_isolated_slots_with_shared_guards(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "RESUMEGEN_NIGHTLY_LOAD": "0"}
    env.pop("RESUMEGEN_NIGHTLY_ARGS", None)

    subprocess.run(
        [str(SCRIPTS / "install_nightly_launch_agent.sh")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    plist_paths = [
        home
        / "Library"
        / "LaunchAgents"
        / "com.akshat.resumegenerator.nightly.plist",
        home
        / "Library"
        / "LaunchAgents"
        / "com.akshat.resumegenerator.nightly.overnight.plist",
    ]
    plists = []
    for plist_path in plist_paths:
        with plist_path.open("rb") as handle:
            plists.append(plistlib.load(handle))

    def option(plist: dict, name: str) -> str:
        argv = plist["ProgramArguments"]
        return argv[argv.index(name) + 1]

    assert [option(plist, "--scheduled-time") for plist in plists] == [
        "20:00",
        "01:00",
    ]
    assert [option(plist, "--production-slot") for plist in plists] == [
        "evening_delivery",
        "overnight_maintenance",
    ]
    assert option(plists[0], "--state-path") != option(plists[1], "--state-path")
    assert option(plists[0], "--lock-path") == option(plists[1], "--lock-path")
    assert option(plists[0], "--discovery-state-path") == option(
        plists[1], "--discovery-state-path"
    )
    for plist in plists:
        assert plist["StartInterval"] == 300
        assert "StartCalendarInterval" not in plist
        assert option(plist, "--timezone") == "Asia/Kolkata"
        assert option(plist, "--discovery-cadence-hours") == "48"
        assert "--require-production-slot-contract" in plist["ProgramArguments"]
        assert plist["EnvironmentVariables"]["TZ"] == "Asia/Kolkata"
        assert "RESUMEGEN_NIGHTLY_ARGS" not in plist["EnvironmentVariables"]
    assert not (
        home
        / "Library"
        / "Application Support"
        / "ResumeGenerator"
        / "nightly_discovery_cadence.json"
    ).exists()


def test_installer_refuses_unattended_no_send_override(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "RESUMEGEN_NIGHTLY_LOAD": "0",
        "RESUMEGEN_NIGHTLY_ARGS": "--cycle-config offcycle_light --target-sends 0",
    }

    result = subprocess.run(
        [str(SCRIPTS / "install_nightly_launch_agent.sh")],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "RESUMEGEN_NIGHTLY_ARGS is not supported" in result.stderr


def test_discovery_attempt_gate_uses_a_shared_48_hour_interval() -> None:
    module = _load_script("nightly_prompt.py", "nightly_discovery_gate_test")
    now = datetime.fromisoformat("2026-07-13T20:00:00+05:30")

    assert module._discovery_due({}, now=now) == (
        True,
        "no_previous_discovery_attempt",
    )
    is_due, reason = module._discovery_due(
        {"last_attempt_at": (now - timedelta(hours=47, minutes=59)).isoformat()},
        now=now,
    )
    assert not is_due
    assert reason.startswith("discovery_due_in_")
    assert module._discovery_due(
        {"last_attempt_at": (now - timedelta(hours=48)).isoformat()},
        now=now,
    ) == (True, "discovery_cadence_elapsed")


def test_track_2_nested_partial_failure_is_non_green() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_nested_health_test")
    payload = {
        "phase_results": [
            {"phase": "1_2_linkedin_followups", "status": "sent"},
            {"phase": "4_contact_mapping", "status": "partial_failed"},
            {"phase": "5_send_linkedin_invites", "status": "sent"},
        ]
    }

    health = module._track_2_artifact_health(payload)

    assert health == {
        "status": "partial_failed",
        "phase_failures": [
            {"phase": "4_contact_mapping", "status": "partial_failed"}
        ],
    }
    assert module._outreach_maintenance_failures(
        {"track_2_daily_run_returncode": 0, "track_2_daily_run_status": "partial_failed"}
    ) == ["track_2_daily_run:partial_failed"]


@pytest.mark.parametrize(
    "terminal_status",
    ["send_unknown_reserved", "partial_send_unknown_reserved", "unknown"],
)
def test_track_2_delivery_uncertain_terminal_status_is_non_green(
    terminal_status: str,
) -> None:
    module = _load_script(
        "run_nightly_pipeline.py", f"nightly_uncertain_{terminal_status}"
    )

    health = module._track_2_artifact_health(
        {
            "execute": True,
            "send_linkedin": True,
            "phase_results": [
                {
                    "phase": "5_send_linkedin_invites",
                    "status": terminal_status,
                    "send_enabled": True,
                }
            ],
        }
    )

    assert health["status"] == "failed"
    assert health["phase_failures"] == [
        {"phase": "5_send_linkedin_invites", "status": terminal_status}
    ]


def test_track_2_nested_unknown_reservation_cannot_hide_under_sent_phase() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_nested_unknown_test")

    health = module._track_2_artifact_health(
        {
            "execute": True,
            "send_linkedin": True,
            "phase_results": [
                {
                    "phase": "5_send_linkedin_invites",
                    "status": "sent",
                    "send_enabled": True,
                    "runs": [
                        {
                            "company": "ExampleCo",
                            "status": "send_completed",
                            "status_counts": {"send_unknown_reserved": 1},
                        }
                    ],
                }
            ],
        }
    )

    assert health["status"] == "partial_failed"
    assert health["phase_failures"] == [
        {
            "phase": "5_send_linkedin_invites/run:ExampleCo",
            "status": "send_unknown_reserved",
        }
    ]


@pytest.mark.parametrize("pending_status", ["planned", "queued", "prepared"])
def test_track_2_pending_delivery_status_fails_when_delivery_was_requested(
    pending_status: str,
) -> None:
    module = _load_script(
        "run_nightly_pipeline.py", f"nightly_pending_delivery_{pending_status}"
    )

    health = module._track_2_artifact_health(
        {
            "execute": True,
            "send_linkedin": True,
            "phase_results": [
                {
                    "phase": "5_send_linkedin_invites",
                    "status": pending_status,
                    "send_enabled": True,
                }
            ],
        }
    )

    assert health["status"] == "failed"
    assert health["phase_failures"][0]["status"] == pending_status


def test_track_2_preview_modes_preserve_expected_planned_and_prepared_states() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_preview_health_test")

    pure_preview = module._track_2_artifact_health(
        {
            "execute": False,
            "send_linkedin": False,
            "phase_results": [
                {"phase": "4_contact_mapping", "status": "planned"},
                {"phase": "5_send_linkedin_invites", "status": "queued"},
            ],
        }
    )
    no_send_execution = module._track_2_artifact_health(
        {
            "execute": True,
            "send_linkedin": False,
            "phase_results": [
                {
                    "phase": "5_send_linkedin_invites",
                    "status": "prepared",
                    "send_enabled": False,
                    "runs": [{"company": "ExampleCo", "status": "prepared"}],
                }
            ],
        }
    )

    assert pure_preview == {"status": "completed", "phase_failures": []}
    assert no_send_execution == {"status": "completed", "phase_failures": []}


def test_track_2_non_delivery_queue_is_incomplete_when_execution_was_requested() -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_execution_queue_test")

    health = module._track_2_artifact_health(
        {
            "execute": True,
            "send_linkedin": False,
            "phase_results": [
                {"phase": "4_contact_mapping", "status": "queued"},
            ],
        }
    )

    assert health["status"] == "failed"
    assert health["phase_failures"] == [
        {"phase": "4_contact_mapping", "status": "queued"}
    ]


def test_manifest_propagates_nested_track_2_partial_failure(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_nested_manifest_test")
    outreach = tmp_path / "Outreach"
    artifact_dir = outreach / "artifacts"
    artifact_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "OUTREACH_ROOT", outreach)
    track_artifact = artifact_dir / "track-2.json"
    track_artifact.write_text(
        json.dumps(
            {
                "used": {"total_actions": 2},
                "phase_results": [
                    {"phase": "1_2_linkedin_followups", "status": "sent", "count": 1},
                    {
                        "phase": "5_send_linkedin_invites",
                        "status": "partial_failed",
                        "count": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"source_families": {}}), encoding="utf-8")
    summary = {
        "daily_engine_manifest": str(manifest),
        "outreach_maintenance": {
            "track_2_daily_run_returncode": 0,
            "track_2_daily_run_artifact": str(track_artifact),
        },
    }

    module._augment_daily_engine_manifest(summary)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["track_2"]["status"] == "partial_failed"
    assert payload["source_families"]["track_2"]["status"] == "partial_failed"
    assert module._source_family_failures(summary) == [
        "source_family:track_2:partial_failed"
    ]


def test_partial_track_2_mapping_preserves_completed_child_count() -> None:
    module = _load_script(
        "run_nightly_pipeline.py", "nightly_partial_mapping_count_test"
    )

    counts = module._track_2_phase_counts(
        [
            {
                "phase": "4_contact_mapping",
                "status": "partial_failed",
                "budget": 15,
                "completed_count": 14,
                "failed_count": 1,
                "runs": [
                    *[{"status": "completed"} for _ in range(14)],
                    {"status": "failed"},
                ],
            }
        ]
    )

    assert counts == [
        {
            "phase": "4_contact_mapping",
            "status": "partial_failed",
            "planned_count": 15,
            "actual_count": 14,
        }
    ]


def test_scheduler_binds_success_to_exact_terminal_summary(tmp_path: Path) -> None:
    module = _load_script("nightly_prompt.py", "nightly_summary_outcome_test")
    summary = tmp_path / "summary.json"
    log = tmp_path / "run.log"
    summary.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
    log.write_text(f"Nightly summary: {summary}\n", encoding="utf-8")

    assert module._pipeline_outcome(log, 0) == (
        1,
        "failed_or_incomplete",
        summary,
    )
    summary.write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    assert module._pipeline_outcome(log, 0) == (0, "completed", summary)


def test_start_interval_check_is_not_recorded_as_an_actual_run(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("nightly_prompt.py", "nightly_interval_check_test")
    now = datetime(2026, 7, 12, 2, 0, 0)
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "last_attempt_date": "2026-07-12",
                "last_run_status": "failed_or_incomplete",
                "last_run_was_actual_pipeline": True,
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        scheduled_time="01:00",
        state_path=str(state_path),
        force=False,
        prompt=False,
        production_check_only=False,
        check_only=False,
        verbose=False,
        require_live_delivery_contract=True,
        require_production_attestation=True,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "scheduler.lock")
    monkeypatch.setattr(module, "_now", lambda: now)
    monkeypatch.setattr(
        module, "_run_pipeline", lambda *_: pytest.fail("not-due check must not run pipeline")
    )
    before = state_path.read_text(encoding="utf-8")

    assert module.main() == 0
    assert state_path.read_text(encoding="utf-8") == before


def test_browser_cleanup_kills_only_exact_run_owner(monkeypatch) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_browser_cleanup_test")
    summary = {
        "linkedin_browser_lifecycle": {
            "preexisting_listener_pids": [111],
            "cleanup_status": "pending",
        }
    }
    responses = iter([[222], [], []])
    monkeypatch.setattr(module, "_owned_linkedin_browser_pids", lambda *_: next(responses))
    monkeypatch.setattr(module, "_listener_pids", lambda *_: [111])
    killed: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(module.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setenv(module.LINKEDIN_BROWSER_OWNER_ENV, "run-token")

    assert module._finish_linkedin_browser_lifecycle(summary, "run-token", None)

    assert killed == [(222, signal.SIGTERM)]
    lifecycle = summary["linkedin_browser_lifecycle"]
    assert lifecycle["cleanup_status"] == "closed_run_owned_browser"
    assert lifecycle["post_cleanup_listener_pids"] == [111]
    assert module.LINKEDIN_BROWSER_OWNER_ENV not in os.environ


def test_browser_owner_match_excludes_normal_and_unrelated_chrome(monkeypatch) -> None:
    module = _load_script("run_nightly_pipeline.py", "nightly_browser_owner_match_test")
    process_table = "\n".join(
        [
            "101 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "102 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222",
            "103 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222 --resume-generator-browser-owner=exact-token",
        ]
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, process_table, ""),
    )

    assert module._owned_linkedin_browser_pids("exact-token", "9222") == [103]


def test_daily_engine_refuses_to_reset_unowned_debug_session(monkeypatch) -> None:
    module = _load_script("run_daily_engine.py", "daily_browser_ownership_test")
    monkeypatch.delenv(module.LINKEDIN_BROWSER_OWNER_ENV, raising=False)
    monkeypatch.delenv("RESUMEGEN_ALLOW_UNOWNED_LINKEDIN_BROWSER_RESET", raising=False)

    assert not module._browser_is_owned_by_current_run(
        "/Applications/Google Chrome --remote-debugging-port=9222", "9222"
    )
    monkeypatch.setenv(module.LINKEDIN_BROWSER_OWNER_ENV, "exact-token")
    assert module._browser_is_owned_by_current_run(
        "/Applications/Google Chrome --remote-debugging-port=9222 "
        "--resume-generator-browser-owner=exact-token",
        "9222",
    )


def test_launcher_tags_only_run_owned_chrome() -> None:
    launcher = (SCRIPTS / "launch_linkedin_browser.sh").read_text(encoding="utf-8")
    assert "RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN" in launcher
    assert "--resume-generator-browser-owner=${OWNER_TOKEN}" in launcher
    assert '"--disable-extensions"' in launcher


def test_nightly_ensure_accepts_current_token_listener(tmp_path: Path) -> None:
    token = "current-token"
    profile = tmp_path / "chrome-profile"
    command = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"--user-data-dir={profile} --remote-debugging-port=9222 "
        f"--resume-generator-browser-owner={token}"
    )
    ensure, env, _, listener = _ensure_chrome_fixture(
        tmp_path, listener_command=command, owner_token=token
    )
    try:
        result = subprocess.run(
            [str(ensure)], cwd=tmp_path, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert listener.poll() is None
    finally:
        _terminate_process(listener)


def test_nightly_ensure_refuses_unowned_cdp_listener(tmp_path: Path) -> None:
    profile = tmp_path / "chrome-profile"
    command = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"--user-data-dir={profile} --remote-debugging-port=9222"
    )
    ensure, env, _, listener = _ensure_chrome_fixture(
        tmp_path, listener_command=command, owner_token="current-token"
    )
    try:
        result = subprocess.run(
            [str(ensure)], cwd=tmp_path, env=env, capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "Refusing to reuse unowned CDP listener" in result.stderr
        assert listener.poll() is None
    finally:
        _terminate_process(listener)


def test_nightly_ensure_replaces_sound_stale_owned_listener(tmp_path: Path) -> None:
    profile = tmp_path / "chrome-profile"
    command = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"--user-data-dir={profile} --remote-debugging-port=9222 "
        "--resume-generator-browser-owner=stale-token"
    )
    ensure, env, state_path, stale_listener = _ensure_chrome_fixture(
        tmp_path, listener_command=command, owner_token="current-token"
    )
    replacement_pid = 0
    try:
        result = subprocess.run(
            [str(ensure)], cwd=tmp_path, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        stale_listener.wait(timeout=2)
        replacement_pid = int(state_path.read_text(encoding="utf-8").strip())
        assert replacement_pid != stale_listener.pid
        os.kill(replacement_pid, 0)
        assert "Closing stale ResumeGenerator-owned LinkedIn Chrome" in result.stderr
    finally:
        _terminate_process(stale_listener)
        if replacement_pid:
            try:
                os.kill(replacement_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_nightly_ensure_refuses_unsound_stale_owned_listener(tmp_path: Path) -> None:
    command = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        "--user-data-dir=/wrong/profile --remote-debugging-port=9222 "
        "--resume-generator-browser-owner=stale-token"
    )
    ensure, env, _, listener = _ensure_chrome_fixture(
        tmp_path, listener_command=command, owner_token="current-token"
    )
    try:
        result = subprocess.run(
            [str(ensure)], cwd=tmp_path, env=env, capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "unsound or unrelated CDP listener" in result.stderr
        assert listener.poll() is None
    finally:
        _terminate_process(listener)
