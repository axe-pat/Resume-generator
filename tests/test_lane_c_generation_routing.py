import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import jobs
import run_app
from shared.generation_routing import (
    GenerationMetadataError,
    GenerationPath,
    LaneCGenerationRequest,
    LaneCGenerationResult,
    LaneCGeneratorNotRegistered,
    clear_lane_c_generator,
    dispatch_lane_c_generation,
    read_generation_metadata,
    register_lane_c_generator,
    resolve_generation_path,
)


@pytest.fixture(autouse=True)
def _empty_lane_c_registry():
    clear_lane_c_generator()
    yield
    clear_lane_c_generator()


def _healthy_jd() -> str:
    block = """
About the role
This role supports students through research, analytics, and service delivery.
What you'll do
You will interview students, analyze requests, build reports, coordinate with
campus partners, document decisions, and measure whether the service improved.
Qualifications
Strong written communication, analytical judgment, and ability to work across
multiple teams while handling sensitive information carefully.
"""
    return (block + "\n" + block + "\n" + block).strip()


def _app_dir(tmp_path: Path, *, lane: str = "C") -> Path:
    app_dir = tmp_path / "application"
    app_dir.mkdir()
    (app_dir / "jd.txt").write_text(_healthy_jd(), encoding="utf-8")
    (app_dir / "metadata.json").write_text(
        json.dumps(
            {
                "id": "lane-c-1",
                "company": "USC Unit",
                "role_title": "Student Services Assistant",
                "lane": lane,
            }
        ),
        encoding="utf-8",
    )
    return app_dir


@pytest.mark.parametrize("lane", ["A", "B", "", None])
def test_a_b_or_blank_lane_selects_professional_path(lane):
    assert resolve_generation_path({"lane": lane}) is GenerationPath.PROFESSIONAL


def test_lane_c_resolution_is_normalized_but_not_inferred():
    assert resolve_generation_path({"lane": " c "}) is GenerationPath.LANE_C
    assert (
        resolve_generation_path(
            {"role_title": "USC Student Services Assistant"}
        )
        is GenerationPath.PROFESSIONAL
    )


@pytest.mark.parametrize("lane", ["campus", "D", "lane-c", "typo"])
def test_explicit_unknown_lane_fails_closed(lane):
    with pytest.raises(GenerationMetadataError, match="metadata lane=.* is invalid"):
        resolve_generation_path({"lane": lane})


def test_present_malformed_metadata_fails_closed(tmp_path):
    app_dir = tmp_path / "bad-metadata"
    app_dir.mkdir()
    (app_dir / "metadata.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(GenerationMetadataError, match="Cannot safely select"):
        read_generation_metadata(app_dir)


def test_missing_metadata_preserves_legacy_professional_route(tmp_path):
    assert read_generation_metadata(tmp_path) == {}
    assert resolve_generation_path({}) is GenerationPath.PROFESSIONAL


def test_lane_c_dispatch_fails_closed_until_adapter_is_registered(tmp_path):
    app_dir = _app_dir(tmp_path)
    request = LaneCGenerationRequest(
        company="USC Unit",
        app_dir=app_dir,
        jd_path=app_dir / "jd.txt",
        metadata={"lane": "C"},
    )

    with pytest.raises(
        LaneCGeneratorNotRegistered,
        match=r"Refusing to send metadata lane=C through the generic PM/NONPM generator",
    ):
        dispatch_lane_c_generation(request)


def test_registered_lane_c_adapter_receives_request_and_returns_typed_result(tmp_path):
    app_dir = _app_dir(tmp_path)
    captured = []

    def adapter(request):
        captured.append(request)
        return LaneCGenerationResult(
            success=True,
            artifacts=(request.app_dir / "resume.docx",),
        )

    register_lane_c_generator(adapter)
    request = LaneCGenerationRequest(
        company="USC Unit",
        app_dir=app_dir,
        jd_path=app_dir / "jd.txt",
        metadata={"lane": "C"},
        options={"mode": "generate"},
    )

    result = dispatch_lane_c_generation(request)

    assert result.success
    assert result.artifacts == (app_dir / "resume.docx",)
    assert captured == [request]


def test_direct_run_app_blocks_lane_c_before_pm_nonpm_router(monkeypatch, tmp_path):
    app_dir = _app_dir(tmp_path)
    monkeypatch.setattr(
        run_app,
        "_infer_role_track",
        lambda *_args, **_kwargs: pytest.fail("PM/NONPM router must not see Lane C"),
    )
    monkeypatch.setattr(
        run_app,
        "_import_pipelines",
        lambda: pytest.fail("generic pipelines must not load for Lane C"),
    )

    with pytest.raises(LaneCGeneratorNotRegistered):
        run_app.run_app(
            company="USC Unit",
            model="test-model",
            run_resume=True,
            run_cl=False,
            run_strategy=False,
            run_rewrite=False,
            run_score=False,
            run_qc=False,
            make_docx=False,
            app_dir_override=str(app_dir),
            smart_cost=False,
        )


def test_docx_only_cannot_fall_through_to_professional_renderer(tmp_path):
    app_dir = _app_dir(tmp_path)

    with pytest.raises(LaneCGeneratorNotRegistered):
        run_app.docx_only_app(
            company="USC Unit",
            app_dir_override=str(app_dir),
        )


def test_jobs_generate_blocks_lane_c_before_run_app_subprocess(monkeypatch, tmp_path):
    app_dir = _app_dir(tmp_path)
    monkeypatch.setattr(
        jobs.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("jobs.py must not launch generic run_app.py"),
    )
    args = SimpleNamespace(
        dry_run=False,
        with_cl=False,
        timeout=5,
        parallel=1,
        no_docx=True,
        model="test-model",
        no_rewrite=False,
        no_score=False,
        no_qc=False,
        no_strategy=False,
        budget_mode=False,
        run_name=None,
    )

    results = jobs.cmd_generate(
        args,
        promoted_jobs=[
            {"id": "lane-c-1", "company": "USC Unit", "app_dir": str(app_dir)}
        ],
    )

    assert len(results) == 1
    assert results[0]["success"] is False
    assert results[0]["generation_path"] == "lane-c"
    assert results[0]["generation_route_blocked"] is True
    assert "Lane C generation is not configured" in results[0]["error"]


def test_unreadable_jd_becomes_preflight_block_instead_of_crashing(monkeypatch, tmp_path):
    app_dir = _app_dir(tmp_path, lane="B")
    target = {"id": "lane-b-1", "company": "Example", "app_dir": str(app_dir)}
    original_read_text = Path.read_text

    def controlled_read_text(path, *args, **kwargs):
        if path.name == "jd.txt":
            raise OSError("permission denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", controlled_read_text)

    queue_input = jobs._generation_target_input(target)
    report = jobs._preflight_generation_targets([target])

    assert queue_input is not None
    assert queue_input.jd_text is None
    assert report.status.value == "block"
    assert {record.code for record in report.blockers} == {"JD_MISSING"}


def test_jobs_lane_c_adapter_gets_batch_generation_options(monkeypatch, tmp_path):
    app_dir = _app_dir(tmp_path)
    captured = []

    def adapter(request):
        captured.append(request)
        return LaneCGenerationResult(success=True)

    register_lane_c_generator(adapter)
    monkeypatch.setattr(
        jobs.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("registered Lane C still must not use run_app.py"),
    )
    args = SimpleNamespace(
        dry_run=False,
        with_cl=True,
        timeout=5,
        parallel=1,
        no_docx=False,
        model="test-model",
        no_rewrite=False,
        no_score=False,
        no_qc=False,
        no_strategy=False,
        budget_mode=False,
        run_name="test-run",
    )

    results = jobs.cmd_generate(
        args,
        promoted_jobs=[
            {"id": "lane-c-1", "company": "USC Unit", "app_dir": str(app_dir)}
        ],
    )

    assert results[0]["success"] is True
    assert results[0]["generation_path"] == "lane-c"
    assert len(captured) == 1
    assert captured[0].options == {
        "mode": "generate",
        "run_resume": True,
        "run_cover_letter": True,
        "make_docx": True,
        "model": "test-model",
        "run_name": "test-run",
    }
