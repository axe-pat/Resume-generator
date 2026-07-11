from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SCRIPT = ROOT / "discovery" / "auto" / "startup_apply_pipeline.py"
REPORT_SCRIPT = ROOT / "discovery" / "scripts" / "build_startup_source_report.py"
DAILY_SCRIPT = ROOT / "discovery" / "scripts" / "run_daily_engine.py"
HANDSHAKE_SCRIPT = ROOT / "discovery" / "auto" / "import_handshake_csv.py"


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_artifact_payload(*, status: str = "completed") -> dict:
    return {
        "schema": "resume_generator.startup_apply_run",
        "version": 1,
        "status": status,
        "run_started_at": "2026-07-11T01:00:00",
        "completed_at": "2026-07-11T01:01:00",
        "runtime_seconds": 60,
        "config": {},
        "counts": {
            "discovered": 9,
            "new": 1,
            "selected": 1,
            "scored": 1,
            "written": 1,
            "discovered_by_source": {
                "yc_sf_bay_hiring": 9,
                "yc_los_angeles": 0,
            },
            "new_by_source": {
                "yc_sf_bay_hiring": 1,
                "yc_los_angeles": 0,
            },
            "selected_by_source": {
                "yc_sf_bay_hiring": 1,
                "yc_los_angeles": 0,
            },
            "status_counts": {"queued": 1},
            "error_count": 0,
            "scoring_error_count": 0,
            "processing_error_count": 0,
            "run_error_count": 0,
            "decision_counts": {"Proceed": 1},
        },
        "candidates": {
            "selected": [
                {
                    "company": "Exact Co",
                    "role_title": "Product Manager Intern",
                    "location": "San Francisco, CA",
                    "url": "https://example.test/exact-role",
                    "url_hash": "exact-hash",
                    "source": "yc_startup_jobs",
                    "source_id": "yc_sf_bay_hiring",
                    "date_posted": "2026-07-11",
                    "jd_text": "MBA product internship building AI data products.",
                    "notes": "track=startup_apply",
                    "list_url": "https://example.test/jobs",
                    "status": "queued",
                }
            ],
            "scored": [
                {
                    "decision": "Proceed",
                    "status": "queued",
                    "fit_score": 8.0,
                }
            ],
        },
        "outputs": {"run_log": "", "jobs_xlsx_updated": True},
        "error": None,
    }


def test_startup_apply_writes_completed_artifact_when_no_jobs_are_new(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(PIPELINE_SCRIPT, "startup_zero_new_artifact_test")
    monkeypatch.setattr(module, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        module.jobs,
        "load_jobs",
        lambda: pd.DataFrame(columns=module.jobs.COLUMNS),
    )
    monkeypatch.setattr(
        module,
        "_discover_startup_jobs",
        lambda *args, **kwargs: (
            [],
            {"yc_sf_bay_hiring": 0, "yc_los_angeles": 0},
        ),
    )
    monkeypatch.setattr(
        module.jobs,
        "save_jobs",
        lambda *args, **kwargs: pytest.fail("zero-new must not rewrite jobs.xlsx"),
    )
    artifact = tmp_path / "exact-zero-new.json"

    result = module.run(
        dry_run=False,
        skip_score=True,
        model="test-model",
        limit_companies=2,
        limit_jobs=5,
        include_sources=None,
        ignore_existing=False,
        verbose=False,
        run_artifact=artifact,
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert result == []
    assert payload["status"] == "completed"
    assert payload["counts"]["discovered"] == 0
    assert payload["counts"]["new"] == 0
    assert payload["counts"]["selected"] == 0
    assert payload["counts"]["discovered_by_source"] == {
        "yc_los_angeles": 0,
        "yc_sf_bay_hiring": 0,
    }
    assert payload["counts"]["new_by_source"] == {
        "yc_los_angeles": 0,
        "yc_sf_bay_hiring": 0,
    }
    assert payload["candidates"]["selected"] == []
    assert Path(payload["outputs"]["run_log"]).is_file()


def test_startup_apply_writes_failed_artifact_when_discovery_raises(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(PIPELINE_SCRIPT, "startup_failed_artifact_test")
    monkeypatch.setattr(module, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        module.jobs,
        "load_jobs",
        lambda: pd.DataFrame(columns=module.jobs.COLUMNS),
    )

    def fail_discovery(*args, **kwargs):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(module, "_discover_startup_jobs", fail_discovery)
    artifact = tmp_path / "exact-failure.json"

    with pytest.raises(RuntimeError, match="source unavailable"):
        module.run(
            dry_run=False,
            skip_score=True,
            model="test-model",
            limit_companies=2,
            limit_jobs=5,
            include_sources=None,
            ignore_existing=False,
            verbose=False,
            run_artifact=artifact,
        )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"] == {
        "type": "RuntimeError",
        "message": "source unavailable",
    }
    assert payload["counts"]["run_error_count"] == 1
    assert payload["counts"]["error_count"] == 1


def test_source_report_consumes_exact_artifact_without_refetch(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(REPORT_SCRIPT, "startup_exact_report_test")
    artifact = tmp_path / "exact-run.json"
    artifact.write_text(
        json.dumps(_run_artifact_payload()),
        encoding="utf-8",
    )
    report = tmp_path / "exact-report.json"

    def refetch_is_forbidden(*args, **kwargs):
        raise AssertionError("exact artifact mode must not fetch startup sources")

    monkeypatch.setattr(module, "_classify_startup_apply", refetch_is_forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(REPORT_SCRIPT),
            "--startup-run-artifact",
            str(artifact),
            "--no-relationship-artifacts",
            "--output-json",
            str(report),
        ],
    )

    assert module.main() == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["inputs"]["startup_apply_mode"] == "exact_run_artifact"
    assert payload["inputs"]["startup_run_artifact"] == str(artifact.resolve())
    assert payload["startup_apply"]["discovered_counts"] == {
        "yc_sf_bay_hiring": 9,
        "yc_los_angeles": 0,
    }
    assert payload["startup_apply"]["new_counts"] == {
        "yc_sf_bay_hiring": 1,
        "yc_los_angeles": 0,
    }
    assert [item["company"] for item in payload["startup_apply"]["items"]] == [
        "Exact Co"
    ]


def test_source_report_fails_closed_for_missing_exact_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(REPORT_SCRIPT, "startup_missing_report_test")
    report = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(REPORT_SCRIPT),
            "--startup-run-artifact",
            str(tmp_path / "missing.json"),
            "--no-relationship-artifacts",
            "--output-json",
            str(report),
        ],
    )

    assert module.main() == 2
    assert not report.exists()


def test_daily_metrics_and_manifest_preserve_exact_startup_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "startup_daily_pointer_test")
    validation = tmp_path / "validation"
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", validation)
    artifact = tmp_path / "exact-run.json"
    artifact.write_text(json.dumps(_run_artifact_payload()), encoding="utf-8")
    report = tmp_path / "exact-report.json"
    report.write_text(
        json.dumps(
            {
                "startup_apply": {
                    "discovered_counts": {"yc_sf_bay_hiring": 9},
                    "new_counts": {"yc_sf_bay_hiring": 1},
                    "verdict_counts": {"app_score_now": 1},
                    "source_verdict_counts": {
                        "yc_sf_bay_hiring": {"app_score_now": 1}
                    },
                    "items": [{"company": "Exact Co"}],
                },
                "relationship_lane": {"source_counts": {}, "items": []},
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        run_id="exact-startup-run",
        window="24h",
        jobspy_score_limit=10,
    )
    stages = {
        "linkedin": {"status": "skipped", "runtime_seconds": 0},
        "handshake": {"status": "skipped", "runtime_seconds": 0},
        "jobspy": {"status": "skipped", "runtime_seconds": 0},
        "startup_apply": {"status": "ran", "runtime_seconds": 60},
        "relationship_discovery": {"status": "skipped", "runtime_seconds": 0},
    }
    artifacts = {
        "startup_apply_run": artifact,
        "startup_report": report,
        "jobspy_query_indices": [],
        "jobspy_results": 0,
        "jobspy_fetch_timeout": 0,
    }

    metrics_path = module.write_source_run_metrics(
        args=args,
        run_started_at="2026-07-11T01:00:00",
        stage_metrics=stages,
        artifacts=artifacts,
        action_queue_path=None,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    startup = metrics["sources"]["startup_apply"]
    assert startup["raw_count"] == 9
    assert startup["selected_count"] == 1
    assert startup["accepted_for_write"] == 1
    assert startup["details"]["artifact"] == str(artifact)

    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "exact-startup-run",
            "stage_metrics": stages,
            "artifacts": artifacts,
            "source_metrics": str(metrics_path),
            "action_queue": "",
            "outreach_execution": {},
        }
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["startup_apply_run_artifact"] == str(artifact.resolve())
    assert manifest["startup_source_report_artifact"] == str(report.resolve())
    assert manifest["source_families"]["startup_sources"]["raw_count"] == 9


def test_daily_engine_wires_exact_startup_artifact_without_latest_selection() -> None:
    source = DAILY_SCRIPT.read_text(encoding="utf-8")

    assert '"--run-artifact"' in source
    assert '"--startup-run-artifact"' in source
    assert "startup_apply_run_artifact_path(args.run_id)" in source
    assert 'latest_since("startup_apply_*.txt"' not in source


def test_failed_exact_startup_report_keeps_manifest_source_non_green(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "startup_failed_report_manifest_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path)

    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "failed-startup-report",
            "stage_metrics": {
                "startup_apply": {"status": "ran", "runtime_seconds": 30},
                "relationship_discovery": {
                    "status": "skipped",
                    "runtime_seconds": 0,
                },
                "startup_source_report": {
                    "status": "failed",
                    "runtime_seconds": 1,
                },
            },
            "artifacts": {},
            "source_metrics": "",
            "action_queue": "",
            "outreach_execution": {},
        }
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_families"]["startup_sources"]["status"] == (
        "partial_failed"
    )


def test_handshake_zero_candidate_run_writes_exact_observed_counts(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(HANDSHAKE_SCRIPT, "handshake_zero_candidate_artifact_test")
    discovered = [
        module.CsvJob(
            row_number=str(index),
            company=f"Company {index}",
            role_title=f"Product Intern {index}",
            industry="",
            pay="",
            deadline="",
            urgency="",
            url=f"https://app.joinhandshake.com/job-search/{1000 + index}",
            origin="search",
        )
        for index in range(25)
    ]

    async def fake_discovery(*args, **kwargs):
        return discovered

    existing = pd.DataFrame(
        [
            {
                "url_hash": module._url_hash(item.url),
                "company": item.company,
                "role_title": item.role_title,
            }
            for item in discovered
        ]
    )
    monkeypatch.setattr(module, "_discover_search_with_cdp", fake_discovery)
    monkeypatch.setattr(module.jobs, "load_jobs", lambda: existing)
    monkeypatch.setattr(module, "_historical_seen_url_hashes", lambda: set())
    artifact = tmp_path / "exact-handshake-zero.json"
    args = SimpleNamespace(
        csv="",
        search_url="https://app.joinhandshake.com/job-search/test",
        cdp_url="http://127.0.0.1:9222",
        delay_ms=0,
        max_pages=1,
        max_search_results=25,
        ignore_handshake_history=False,
        stop_after_existing=11,
        no_title_prefilter=False,
        limit=0,
        write=True,
        run_artifact=artifact,
    )

    assert module.run(args) == 0
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["schema"] == "resume_generator.handshake_import_run"
    assert payload["status"] == "completed"
    assert payload["counts"]["input_rows"] == 25
    assert payload["counts"]["skipped_duplicates"] == 11
    assert payload["counts"]["deduped_candidates"] == 0
    assert len(payload["skipped"]) == 11


def test_handshake_exact_artifact_wires_source_metrics_and_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "handshake_exact_metrics_test")
    validation = tmp_path / "validation"
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", validation)
    artifact = tmp_path / "exact-handshake.json"
    artifact.write_text(
        json.dumps(
            {
                "schema": "resume_generator.handshake_import_run",
                "version": 1,
                "status": "completed",
                "source": "handshake_jobs_v1",
                "write": True,
                "counts": {
                    "input_rows": 25,
                    "deduped_candidates": 0,
                    "skipped_duplicates": 11,
                    "historical_seen_urls": 20,
                    "title_prefilter_skipped": 0,
                    "fetch_ok": 0,
                    "fetch_failed": 0,
                    "scored": 0,
                    "accepted_min_score": 0,
                    "rejected_or_below_min": 0,
                    "error_count": 0,
                    "fetch_error_count": 0,
                    "scoring_error_count": 0,
                    "processing_error_count": 0,
                },
                "skipped": [{"reason": "duplicate_url"} for _ in range(11)],
                "fetch_failed": [],
                "scored": [],
                "accepted": [],
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        run_id="exact-handshake-run",
        window="24h",
        jobspy_score_limit=10,
    )
    stages = {
        "linkedin": {"status": "skipped", "runtime_seconds": 0},
        "handshake": {"status": "ran", "runtime_seconds": 10},
        "jobspy": {"status": "skipped", "runtime_seconds": 0},
        "startup_apply": {"status": "skipped", "runtime_seconds": 0},
        "relationship_discovery": {"status": "skipped", "runtime_seconds": 0},
        "startup_source_report": {"status": "ran", "runtime_seconds": 0},
    }
    artifacts = {
        "handshake_log": artifact,
        "jobspy_query_indices": [],
        "jobspy_results": 0,
        "jobspy_fetch_timeout": 0,
    }

    metrics_path = module.write_source_run_metrics(
        args=args,
        run_started_at="2026-07-11T01:00:00",
        stage_metrics=stages,
        artifacts=artifacts,
        action_queue_path=None,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    handshake = metrics["sources"]["handshake"]
    assert handshake["raw_count"] == 25
    assert handshake["selected_count"] == 0
    assert handshake["details"]["skipped_duplicates"] == 11

    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "exact-handshake-run",
            "stage_metrics": stages,
            "artifacts": artifacts,
            "source_metrics": str(metrics_path),
            "action_queue": "",
            "outreach_execution": {},
        }
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["handshake_run_artifact"] == str(artifact.resolve())
    assert manifest["source_families"]["handshake"]["raw_count"] == 25
    assert manifest["source_families"]["handshake"]["kept_count"] == 0


def test_daily_engine_never_selects_latest_handshake_artifact() -> None:
    source = DAILY_SCRIPT.read_text(encoding="utf-8")

    assert "handshake_run_artifact_path(args.run_id)" in source
    assert 'latest_since(\n            "handshake_import_*.json"' not in source


def test_handshake_health_distinguishes_zero_all_failed_and_partial() -> None:
    module = _load_script(HANDSHAKE_SCRIPT, "handshake_health_test")

    assert module._handshake_health(
        candidate_count=0,
        fetch_ok_count=0,
        fetch_failed_count=0,
        scored=[],
    )["status"] == "completed"
    assert module._handshake_health(
        candidate_count=2,
        fetch_ok_count=0,
        fetch_failed_count=2,
        scored=[],
    ) == {
        "status": "failed",
        "error_count": 2,
        "fetch_error_count": 2,
        "scoring_error_count": 0,
        "processing_error_count": 0,
    }
    assert module._handshake_health(
        candidate_count=2,
        fetch_ok_count=1,
        fetch_failed_count=1,
        scored=[{"decision": "Proceed", "status": "queued"}],
    )["status"] == "partial_failed"


def test_failed_handshake_artifact_propagates_errors_to_source_family(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "handshake_failed_health_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    artifact = tmp_path / "failed-handshake.json"
    artifact.write_text(
        json.dumps(
            {
                "schema": "resume_generator.handshake_import_run",
                "version": 1,
                "status": "failed",
                "counts": {
                    "input_rows": 2,
                    "deduped_candidates": 2,
                    "skipped_duplicates": 0,
                    "historical_seen_urls": 0,
                    "title_prefilter_skipped": 0,
                    "fetch_ok": 0,
                    "fetch_failed": 2,
                    "scored": 0,
                    "accepted_min_score": 0,
                    "rejected_or_below_min": 0,
                    "error_count": 2,
                    "fetch_error_count": 2,
                    "scoring_error_count": 0,
                    "processing_error_count": 0,
                },
                "skipped": [],
                "fetch_failed": [{"error": "blocked"}, {"error": "blocked"}],
                "scored": [],
                "accepted": [],
            }
        ),
        encoding="utf-8",
    )
    assert module._validate_handshake_run_artifact(artifact)["status"] == "failed"
    args = SimpleNamespace(
        run_id="failed-handshake",
        window="24h",
        jobspy_score_limit=1,
    )
    stages = {
        "linkedin": {"status": "skipped", "runtime_seconds": 0},
        "handshake": {"status": "failed", "runtime_seconds": 4},
        "jobspy": {"status": "skipped", "runtime_seconds": 0},
        "startup_apply": {"status": "skipped", "runtime_seconds": 0},
        "relationship_discovery": {"status": "skipped", "runtime_seconds": 0},
        "startup_source_report": {"status": "ran", "runtime_seconds": 0},
    }
    metrics_path = module.write_source_run_metrics(
        args=args,
        run_started_at="2026-07-11T01:00:00",
        stage_metrics=stages,
        artifacts={
            "handshake_log": artifact,
            "jobspy_query_indices": [],
            "jobspy_results": 0,
            "jobspy_fetch_timeout": 0,
        },
        action_queue_path=None,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["sources"]["handshake"]["status"] == "failed"
    assert metrics["sources"]["handshake"]["error_count"] == 2
    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "failed-handshake",
            "stage_metrics": stages,
            "artifacts": {"handshake_log": artifact},
            "source_metrics": str(metrics_path),
            "action_queue": "",
            "outreach_execution": {},
        }
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_families"]["handshake"]["status"] == "failed"
    assert manifest["source_families"]["handshake"]["details"]["error_count"] == 2


def test_startup_scoring_errors_remain_errors_and_drive_health() -> None:
    module = _load_script(PIPELINE_SCRIPT, "startup_scoring_health_test")
    scored = module._post_process_scored_jobs(
        [
            {"decision": "Error", "fit_score": None},
            {"decision": "Proceed", "fit_score": 8.0},
        ]
    )

    assert scored[0]["status"] == "error"
    assert module._startup_scoring_health(0, [])["status"] == "completed"
    assert module._startup_scoring_health(1, [scored[0]]) == {
        "status": "failed",
        "error_count": 1,
        "scoring_error_count": 1,
        "processing_error_count": 0,
    }
    assert module._startup_scoring_health(2, scored)["status"] == "partial_failed"


def test_failed_startup_scoring_artifact_stays_non_green_in_report_and_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    report_module = _load_script(REPORT_SCRIPT, "startup_failed_score_report_test")
    daily_module = _load_script(DAILY_SCRIPT, "startup_failed_score_daily_test")
    monkeypatch.setattr(daily_module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    payload = _run_artifact_payload(status="failed")
    payload["counts"].update(
        {
            "status_counts": {"error": 1},
            "error_count": 1,
            "scoring_error_count": 1,
            "processing_error_count": 0,
            "decision_counts": {"Error": 1},
        }
    )
    payload["candidates"]["scored"] = [
        {"decision": "Error", "status": "error", "fit_score": None}
    ]
    artifact = tmp_path / "failed-startup-score.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    _, _, _, loaded = report_module._classify_startup_run_artifact(artifact)
    assert loaded["status"] == "failed"
    assert daily_module._validate_startup_apply_run_artifact(artifact)["status"] == (
        "failed"
    )
    report = tmp_path / "failed-startup-report.json"
    report.write_text(
        json.dumps(
            {
                "startup_apply": {
                    "status": "failed",
                    "mode": "exact_run_artifact",
                    "run_artifact": str(artifact),
                    "discovered_counts": {"yc_sf_bay_hiring": 9},
                    "new_counts": {"yc_sf_bay_hiring": 1},
                    "verdict_counts": {},
                    "source_verdict_counts": {},
                    "items": [],
                },
                "relationship_lane": {
                    "status": "skipped",
                    "mode": "skipped",
                    "error_count": 0,
                    "artifacts": {},
                    "source_counts": {},
                    "items": [],
                },
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        run_id="failed-startup-score",
        window="24h",
        jobspy_score_limit=1,
    )
    stages = {
        "linkedin": {"status": "skipped", "runtime_seconds": 0},
        "handshake": {"status": "skipped", "runtime_seconds": 0},
        "jobspy": {"status": "skipped", "runtime_seconds": 0},
        "startup_apply": {"status": "failed", "runtime_seconds": 5},
        "relationship_discovery": {"status": "skipped", "runtime_seconds": 0},
        "startup_source_report": {"status": "ran", "runtime_seconds": 1},
    }
    artifacts = {
        "startup_apply_run": artifact,
        "startup_report": report,
        "jobspy_query_indices": [],
        "jobspy_results": 0,
        "jobspy_fetch_timeout": 0,
    }
    metrics_path = daily_module.write_source_run_metrics(
        args=args,
        run_started_at="2026-07-11T01:00:00",
        stage_metrics=stages,
        artifacts=artifacts,
        action_queue_path=None,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["sources"]["startup_apply"]["error_count"] == 1
    assert metrics["sources"]["startup_apply"]["decision_counts"] == {"Error": 1}
    manifest_path = daily_module.write_daily_engine_manifest(
        {
            "run_id": "failed-startup-score",
            "stage_metrics": stages,
            "artifacts": artifacts,
            "source_metrics": str(metrics_path),
            "action_queue": "",
            "outreach_execution": {},
        }
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_families"]["startup_sources"]["status"] == "failed"
    assert manifest["source_families"]["startup_sources"]["details"][
        "startup_apply"
    ]["details"]["error_count"] == 1


def _write_relationship_artifact(
    path: Path,
    source_id: str,
    *,
    status: str | None = None,
) -> None:
    payload = {
        "source": {"source_id": source_id},
        "raw_count": 1,
        "count": 1,
        "results": [
            {
                "organization_name": f"{source_id} Co",
                "source_kind": "yc_directory",
                "company_url": f"https://example.test/{source_id}",
            }
        ],
    }
    if status is not None:
        payload["status"] = status
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_relationship_mapping_validates_identity_and_missing_members(
    tmp_path: Path
) -> None:
    module = _load_script(REPORT_SCRIPT, "exact_relationship_mapping_test")
    first = tmp_path / "first.json"
    mismatched = tmp_path / "mismatched.json"
    non_green = tmp_path / "non-green.json"
    _write_relationship_artifact(first, "source_a")
    _write_relationship_artifact(mismatched, "wrong_source")
    _write_relationship_artifact(non_green, "source_d", status="failed")

    items, artifacts, status, errors = module._load_exact_relationship_targets(
        artifact_paths={
            "source_a": str(first),
            "source_b": str(mismatched),
            "source_d": str(non_green),
        },
        command_statuses={
            "source_a": "completed",
            "source_b": "completed",
            "source_d": "completed",
        },
        source_ids=("source_a", "source_b", "source_c", "source_d"),
        limit_per_source=15,
    )

    assert {item["source_id"] for item in items} == {"source_a", "source_d"}
    assert artifacts["source_a"]["artifact"] == str(first.resolve())
    assert artifacts["source_b"]["status"] == "invalid"
    assert artifacts["source_c"]["status"] == "missing"
    assert artifacts["source_d"]["status"] == "failed"
    assert status == "partial_failed"
    assert errors == 3


def test_report_exact_relationship_mode_never_uses_latest(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(REPORT_SCRIPT, "exact_relationship_report_mode_test")
    artifact = tmp_path / "exact-source.json"
    _write_relationship_artifact(artifact, "source_a")
    report = tmp_path / "relationship-report.json"
    monkeypatch.setattr(
        module,
        "_latest_outreach_artifact",
        lambda *args, **kwargs: pytest.fail("exact mode must not select latest"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(REPORT_SCRIPT),
            "--no-startup-apply",
            "--exact-relationship-artifacts",
            "--required-relationship-source",
            "source_a",
            "--relationship-artifact",
            f"source_a={artifact}",
            "--relationship-artifact-status",
            "source_a=completed",
            "--output-json",
            str(report),
        ],
    )

    assert module.main() == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["relationship_lane"]["status"] == "completed"
    assert payload["relationship_lane"]["mode"] == "exact_run_artifacts"
    assert payload["relationship_lane"]["artifacts"]["source_a"][
        "artifact"
    ] == str(artifact.resolve())


def test_daily_relationship_pointer_parser_and_source_validator_are_exact(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "daily_relationship_pointer_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path / "validation")
    artifact = tmp_path / "source.json"
    _write_relationship_artifact(artifact, "source_a")

    pointer = module._artifact_pointer_from_output(
        f"noise\nArtifact: {artifact}\nmore noise",
        base_dir=tmp_path,
    )
    assert pointer == artifact.resolve()
    _, status = module._validate_relationship_discovery_artifact(
        pointer,
        "source_a",
    )
    assert status == "completed"
    with pytest.raises(ValueError, match="source mismatch"):
        module._validate_relationship_discovery_artifact(pointer, "source_b")
    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "relationship-pointer",
            "stage_metrics": {
                "startup_apply": {"status": "skipped"},
                "relationship_discovery": {"status": "ran"},
                "startup_source_report": {"status": "ran"},
            },
            "artifacts": {
                "relationship_discovery": {
                    "artifacts": {"source_a": pointer},
                    "statuses": {"source_a": "completed"},
                }
            },
            "source_metrics": "",
            "action_queue": "",
            "outreach_execution": {},
        }
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["relationship_discovery_artifacts"] == {
        "source_a": str(pointer)
    }


def test_fully_skipped_startup_lanes_stay_skipped_when_helper_runs(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(DAILY_SCRIPT, "fully_skipped_startup_family_test")
    monkeypatch.setattr(module, "SOURCE_VALIDATION_DIR", tmp_path)

    manifest_path = module.write_daily_engine_manifest(
        {
            "run_id": "all-startup-skipped",
            "stage_metrics": {
                "startup_apply": {"status": "skipped", "runtime_seconds": 0},
                "relationship_discovery": {
                    "status": "skipped",
                    "runtime_seconds": 0,
                },
                "startup_source_report": {"status": "ran", "runtime_seconds": 1},
            },
            "artifacts": {},
            "source_metrics": "",
            "action_queue": "",
            "outreach_execution": {},
        }
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_families"]["startup_sources"]["status"] == "skipped"


def test_handshake_external_run_artifact_path_does_not_require_repo_relative(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script(HANDSHAKE_SCRIPT, "handshake_external_artifact_test")
    discovered = [
        module.CsvJob(
            row_number="1",
            company="External Path Co",
            role_title="Product Manager Intern",
            industry="",
            pay="",
            deadline="",
            urgency="",
            url="https://app.joinhandshake.com/job-search/9999",
            origin="search",
        )
    ]

    async def fake_discovery(*args, **kwargs):
        return discovered

    monkeypatch.setattr(module, "_discover_search_with_cdp", fake_discovery)
    monkeypatch.setattr(
        module.jobs,
        "load_jobs",
        lambda: pd.DataFrame(columns=module.jobs.COLUMNS),
    )
    monkeypatch.setattr(module, "_historical_seen_url_hashes", lambda: set())
    artifact = tmp_path / "outside-repo" / "handshake.json"
    args = SimpleNamespace(
        csv="",
        search_url="https://app.joinhandshake.com/job-search/test",
        cdp_url="http://127.0.0.1:9222",
        delay_ms=0,
        max_pages=1,
        max_search_results=1,
        ignore_handshake_history=False,
        stop_after_existing=8,
        no_title_prefilter=True,
        limit=0,
        no_fetch=True,
        skip_score=True,
        model="test",
        quiet=True,
        max_workers=1,
        include_deprioritized=False,
        min_score=4.5,
        write=False,
        no_refresh_queue=True,
        run_artifact=artifact,
    )

    assert module.run(args) == 0
    assert artifact.is_file()
