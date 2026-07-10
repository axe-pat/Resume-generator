from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "discovery" / "scripts" / "run_daily_engine.py"
NIGHTLY_SCRIPT = ROOT / "discovery" / "scripts" / "run_nightly_pipeline.py"


def _load_daily_engine():
    spec = importlib.util.spec_from_file_location("run_daily_engine_for_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_daily_jobspy_includes_bizops_and_program_ops_queries() -> None:
    module = _load_daily_engine()

    assert 4 in module.DAILY_JOBSPY_QUERY_INDICES  # Business Operations Intern
    assert 5 in module.DAILY_JOBSPY_QUERY_INDICES  # Program Manager Intern


def test_weekly_jobspy_keeps_adjacent_role_queries() -> None:
    module = _load_daily_engine()

    assert {3, 4, 5, 9, 10, 11}.issubset(module.WEEKLY_JOBSPY_QUERY_INDICES)


def test_nightly_enables_a_bounded_email_draft_lane() -> None:
    module = _load_script(NIGHTLY_SCRIPT, "run_nightly_pipeline_for_test")

    assert module.TRACK_2_EMAIL_DRAFT_TARGET_BY_CYCLE == {
        "offcycle_light": "5",
        "normal": "5",
    }


def test_daily_startup_report_wiring_excludes_skipped_or_stale_relationship_lanes() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'startup_report_cmd.append("--no-startup-apply")' in source
    assert 'startup_report_cmd.append("--no-relationship-artifacts")' in source
    assert '"--relationship-artifact-since-epoch"' in source


def test_nightly_latest_since_rejects_a_stale_source_metrics_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(NIGHTLY_SCRIPT, "run_nightly_pipeline_scope_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path)
    stale = tmp_path / "old-source-run-metrics.json"
    stale.write_text("{}", encoding="utf-8")
    os.utime(stale, (100, 100))

    assert module.latest_since("*source-run-metrics.json", 200) is None

    current = tmp_path / "new-source-run-metrics.json"
    current.write_text("{}", encoding="utf-8")
    os.utime(current, (300, 300))
    assert module.latest_since("*source-run-metrics.json", 200) == current


def test_company_discovery_receives_the_exact_linkedin_capture_artifact(monkeypatch) -> None:
    module = _load_script(NIGHTLY_SCRIPT, "run_nightly_pipeline_capture_test")
    commands: list[list[str]] = []

    def fake_run(cmd, *, cwd):
        normalized = [str(part) for part in cmd]
        commands.append(normalized)
        artifact = "/tmp/current-linkedin-capture.json" if "capture-linkedin-intelligence" in normalized else "/tmp/other.json"
        return subprocess.CompletedProcess(normalized, 0, stdout=f"Artifact: {artifact}\n", stderr="")

    monkeypatch.setattr(module, "_run_capture_print", fake_run)
    args = SimpleNamespace(
        cycle_config="offcycle_light",
        skip_linkedin=False,
        outreach_resolve_limit=0,
        outreach_enrich_limit=0,
        outreach_campaign_limit=5,
        execute_track_2_daily_plan=False,
    )

    module._run_outreach_maintenance(args, run_id="nightly-1")

    company_command = next(
        command for command in commands if "build-company-discovery-review" in command
    )
    assert company_command[company_command.index("--capture-artifact") + 1] == (
        "/tmp/current-linkedin-capture.json"
    )
