"""Regression tests for explicit, Step-0, and cheap-router track ownership."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import run_app
from resume.freeform import freeform_runner as runner


def test_explicit_pm_track_overrides_strategy_consulting_role_family():
    strategy = {
        "role_family": "strategy-consulting",
        "nonpm_subtype": "commercial-gtm",
        "archetype": "general_pm",
        "top_signals": ["product strategy", "user research"],
    }

    resolved = runner._strategy_for_resolved_track(
        strategy,
        track="pm",
        track_source="explicit",
    )

    assert resolved["role_family"] == "pm"
    assert resolved["nonpm_subtype"] == ""
    assert resolved["archetype"] == "general_pm"
    assert resolved["top_signals"] == ["product strategy", "user research"]
    assert strategy["role_family"] == "strategy-consulting"
    assert strategy["nonpm_subtype"] == "commercial-gtm"


def test_complete_step0_strategy_is_not_overwritten_by_cheap_router():
    strategy = {
        "role_family": "strategy-consulting",
        "nonpm_subtype": "commercial-gtm",
        "archetype": "general_pm",
    }

    routed = runner._strategy_for_resolved_track(
        strategy,
        track="pm",
        track_source="cheap-router",
    )

    assert routed == strategy
    assert routed is not strategy


def test_cheap_router_supplies_minimum_role_family_when_step0_is_unusable():
    assert runner._strategy_for_resolved_track(
        {},
        track="pm",
        track_source="cheap-router",
    )["role_family"] == "pm"
    assert runner._strategy_for_resolved_track(
        {},
        track="nonpm",
        track_source="cheap-router",
    )["role_family"] == "ops-execution"


def test_step0_can_correct_a_cheap_nonpm_guess_back_to_pm(tmp_path):
    (tmp_path / "metadata.json").write_text(
        '{"role_title":"Corporate Strategy Intern"}', encoding="utf-8"
    )
    provisional = run_app._infer_role_track(tmp_path, "", "", "auto")

    resolved = run_app._resolve_role_track_after_strategy(
        provisional,
        {"role_family": "pm", "archetype": "generalist"},
    )

    assert provisional["effective_track"] == "nonpm"
    assert resolved["effective_track"] == "pm"
    assert resolved["source"] == "strategy"


def test_explicit_nonpm_is_not_reversed_by_pm_step0(tmp_path):
    explicit = run_app._infer_role_track(tmp_path, "Product Manager", "", "nonpm")

    resolved = run_app._resolve_role_track_after_strategy(
        explicit,
        {"role_family": "pm", "archetype": "generalist"},
    )

    assert resolved["effective_track"] == "nonpm"
    assert resolved["source"] == "explicit"


def test_run_app_lets_cached_step0_supersede_cheap_product_title_route(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "jd.txt").write_text(
        "Join the product team, run user research and usability tests, then inform "
        "product decisions and the roadmap.",
        encoding="utf-8",
    )
    (tmp_path / "metadata.json").write_text(
        '{"role_title": "Intern - Product Strategy"}',
        encoding="utf-8",
    )
    (tmp_path / "strategy.json").write_text(
        '{"role_title":"Intern - Product Strategy",'
        '"role_family":"strategy-consulting",'
        '"nonpm_subtype":"research-intelligence",'
        '"archetype":"strategy_pm",'
        '"top_signals":["user research","competitive analysis"]}',
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def capture_run_single(**kwargs):
        captured.update(kwargs)
        return False

    pipeline = SimpleNamespace(run_single=capture_run_single)
    monkeypatch.setattr(run_app, "_import_pipelines", lambda: (pipeline, None, None))

    with pytest.raises(RuntimeError, match="failed release checks"):
        run_app.run_app(
            company="Product Strategy Fixture",
            model="test-model",
            run_resume=True,
            run_cl=False,
            run_strategy=False,
            run_rewrite=False,
            run_score=False,
            run_qc=False,
            make_docx=False,
            track="auto",
            app_dir_override=str(tmp_path),
            smart_cost=False,
        )

    assert captured["track"] == "nonpm"
    assert captured["track_source"] == "strategy"


def test_run_app_explicit_pm_still_overrides_cached_nonpm_step0(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "jd.txt").write_text("Corporate strategy and research role", encoding="utf-8")
    (tmp_path / "metadata.json").write_text(
        '{"role_title":"Corporate Strategy Intern"}', encoding="utf-8"
    )
    (tmp_path / "strategy.json").write_text(
        '{"role_family":"strategy-consulting",'
        '"nonpm_subtype":"research-intelligence",'
        '"archetype":"strategy_pm"}',
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def capture_run_single(**kwargs):
        captured.update(kwargs)
        return False

    monkeypatch.setattr(
        run_app,
        "_import_pipelines",
        lambda: (SimpleNamespace(run_single=capture_run_single), None, None),
    )

    with pytest.raises(RuntimeError, match="failed release checks"):
        run_app.run_app(
            company="Explicit PM Fixture",
            model="test-model",
            run_resume=True,
            run_cl=False,
            run_strategy=False,
            run_rewrite=False,
            run_score=False,
            run_qc=False,
            make_docx=False,
            track="pm",
            app_dir_override=str(tmp_path),
            smart_cost=False,
        )

    assert captured["track"] == "pm"
    assert captured["track_source"] == "explicit"
