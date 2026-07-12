from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
DAILY_SCRIPT = ROOT / "discovery" / "scripts" / "run_daily_engine.py"
NIGHTLY_SCRIPT = ROOT / "discovery" / "scripts" / "run_nightly_pipeline.py"


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_score_artifact(
    path: Path, *, scored: int, cache_skipped: int, jobs: list[dict]
) -> Path:
    path.write_text(
        json.dumps(
            {
                "extracted": len(jobs),
                "scored": scored,
                "reviewed": len(jobs),
                "cache_skipped": cache_skipped,
                "accepted_for_write": 0,
                "jobs": jobs,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_linkedin_fresh_scoring_errors_make_stage_non_green(tmp_path: Path) -> None:
    daily = _load_script(DAILY_SCRIPT, "daily_linkedin_scoring_health_test")

    all_failed = _write_score_artifact(
        tmp_path / "all-failed.json",
        scored=2,
        cache_skipped=1,
        jobs=[
            {"decision": "Error"},
            {"decision": "Error"},
            {"decision": "Reject", "status": "cached_skip"},
        ],
    )
    partial = _write_score_artifact(
        tmp_path / "partial.json",
        scored=2,
        cache_skipped=1,
        jobs=[
            {"decision": "Error"},
            {"decision": "Proceed"},
            {"decision": "Reject", "status": "cached_skip"},
        ],
    )

    assert daily._linkedin_scoring_stage_status(all_failed) == "failed_scoring"
    assert daily._linkedin_scoring_stage_status(partial) == (
        "partial_failed_scoring"
    )
    metrics = daily._score_artifact_metrics(partial)
    assert metrics["freshly_scored_count"] == 2
    assert metrics["cache_skipped"] == 1
    assert metrics["fresh_decision_counts"] == {"Error": 1, "Proceed": 1}
    assert metrics["decision_counts"] == {"Error": 1, "Proceed": 1, "Reject": 1}
    assert metrics["error_count"] == 1


def test_linkedin_cache_only_artifact_is_not_a_scoring_failure(tmp_path: Path) -> None:
    daily = _load_script(DAILY_SCRIPT, "daily_linkedin_cache_health_test")
    cache_only = _write_score_artifact(
        tmp_path / "cache-only.json",
        scored=0,
        cache_skipped=2,
        jobs=[
            {"decision": "Reject", "status": "cached_skip"},
            {"decision": "Deprioritize", "status": "cached_skip"},
        ],
    )

    assert daily._linkedin_scoring_stage_status(cache_only) == "ran"
    metrics = daily._score_artifact_metrics(cache_only)
    assert metrics["freshly_scored_count"] == 0
    assert metrics["cache_skipped"] == 2
    assert metrics["fresh_decision_counts"] == {}
    assert metrics["error_count"] == 0

    assert daily._linkedin_scoring_stage_status(None) == (
        "failed_missing_scored_artifact"
    )
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"scored": 0, "jobs": []}', encoding="utf-8")
    assert daily._linkedin_scoring_stage_status(invalid) == (
        "failed_invalid_scored_artifact"
    )


def test_source_metrics_and_nightly_preserve_linkedin_scoring_failure(
    tmp_path: Path, monkeypatch
) -> None:
    daily = _load_script(DAILY_SCRIPT, "daily_linkedin_scoring_wiring_test")
    nightly = _load_script(NIGHTLY_SCRIPT, "nightly_linkedin_scoring_health_test")
    monkeypatch.setattr(daily, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    score_artifact = _write_score_artifact(
        tmp_path / "partial.json",
        scored=2,
        cache_skipped=1,
        jobs=[
            {"decision": "Error"},
            {"decision": "Proceed"},
            {"decision": "Reject", "status": "cached_skip"},
        ],
    )
    stage_status = daily._linkedin_scoring_stage_status(score_artifact)
    source_metrics = daily.write_source_run_metrics(
        args=SimpleNamespace(
            run_id="scoring-health-run", window="24h", jobspy_score_limit=10
        ),
        run_started_at="2026-07-13T01:00:00",
        stage_metrics={
            "linkedin": {"status": stage_status, "runtime_seconds": 12.5}
        },
        artifacts={"linkedin_scored": score_artifact},
        action_queue_path=None,
    )
    source_payload = json.loads(source_metrics.read_text(encoding="utf-8"))
    linkedin = source_payload["sources"]["linkedin"]
    assert linkedin["status"] == "partial_failed_scoring"
    assert linkedin["freshly_scored_count"] == 2
    assert linkedin["error_count"] == 1
    assert linkedin["details"]["fresh_decision_counts"] == {
        "Error": 1,
        "Proceed": 1,
    }

    manifest = daily.write_daily_engine_manifest(
        {
            "run_id": "scoring-health-run",
            "source_metrics": str(source_metrics),
            "stage_metrics": {
                "linkedin": {"status": stage_status, "runtime_seconds": 12.5}
            },
        }
    )

    assert nightly._source_family_failures(
        {"daily_engine_manifest": str(manifest)}
    ) == ["source_family:linkedin:partial_failed_scoring"]
