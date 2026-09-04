import json
from pathlib import Path
from types import SimpleNamespace

import jobs
import pytest

from shared import llm_provider
from shared import strategy


def _cursor_environment(tmp_path: Path, **overrides: str) -> dict[str, str]:
    environment = {
        llm_provider.PROVIDER_ENV: "cursor",
        llm_provider.CURSOR_ROUTING_ENV: "hybrid",
        llm_provider.CURSOR_CLI_ENV: "/bin/echo",
        llm_provider.TELEMETRY_PATH_ENV: str(tmp_path / "llm.jsonl"),
        llm_provider.CURSOR_CACHE_DIR_ENV: str(tmp_path / "cache"),
        "PATH": "/usr/bin:/bin",
        "ANTHROPIC_API_KEY": "must-not-reach-cursor",
        "OPENAI_API_KEY": "must-not-reach-cursor",
        "GITHUB_TOKEN": "must-not-reach-cursor",
        "CURSOR_API_KEY": "cursor-key-is-required-when-configured",
    }
    environment.update(overrides)
    return environment


def test_anthropic_remains_the_default_incumbent():
    plan = llm_provider.resolve_call_plan(
        "Pass 1: Select",
        "claude-sonnet-4-6",
        environment={},
    )

    assert plan.provider == "anthropic"
    assert plan.model == "claude-sonnet-4-6"
    assert plan.routing_class == "incumbent"


@pytest.mark.parametrize(
    ("label", "expected_model", "expected_class"),
    [
        ("Pass 0: Strategy", "auto", "basic"),
        ("Pass 3: Score", "auto", "basic"),
        ("Step 1", "auto", "basic"),
        ("Step 3", "auto", "basic"),
        ("Pass 0b: Summary tournament", "cursor-grok-4.6-high", "hard"),
        ("Pass 1: Select", "cursor-grok-4.6-high", "hard"),
        ("Pass 1b: Bounded re-select", "cursor-grok-4.6-high", "hard"),
        ("Pass 2: Voice", "cursor-grok-4.6-high", "hard"),
        ("Pass 4: Fix", "cursor-grok-4.6-high", "hard"),
        ("Expansion", "cursor-grok-4.6-high", "hard"),
        ("Step 2", "cursor-grok-4.6-high", "hard"),
        ("Future semantic pass", "cursor-grok-4.6-high", "hard"),
    ],
)
def test_hybrid_cursor_routing_is_stage_deterministic(
    label,
    expected_model,
    expected_class,
):
    plan = llm_provider.resolve_call_plan(
        label,
        "ignored-anthropic-name",
        environment={llm_provider.PROVIDER_ENV: "cursor"},
    )

    assert plan.model == expected_model
    assert plan.routing_class == expected_class


def test_cursor_routing_can_be_forced_to_auto_or_grok():
    auto = llm_provider.resolve_call_plan(
        "Pass 1: Select",
        "ignored",
        environment={
            llm_provider.PROVIDER_ENV: "cursor",
            llm_provider.CURSOR_ROUTING_ENV: "auto",
        },
    )
    grok = llm_provider.resolve_call_plan(
        "Pass 3: Score",
        "ignored",
        environment={
            llm_provider.PROVIDER_ENV: "cursor",
            llm_provider.CURSOR_ROUTING_ENV: "grok",
        },
    )

    assert (auto.model, auto.routing_class) == ("auto", "basic")
    assert (grok.model, grok.routing_class) == ("cursor-grok-4.6-high", "hard")


def test_cursor_call_is_text_only_isolated_and_writes_safe_telemetry(
    monkeypatch,
    tmp_path,
):
    captured = {}
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 41,
        "duration_api_ms": 39,
        "result": "SECTION 0\nNONE",
        "session_id": "fixture-session",
    }

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        assert Path(kwargs["cwd"]).is_dir()
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    environment = _cursor_environment(tmp_path)

    result = llm_provider.complete_text(
        "Return the requested section.",
        "claude-sonnet-4-6",
        label="Pass 1: Select",
        environment=environment,
    )

    assert result == "SECTION 0\nNONE"
    assert captured["command"] == [
        "/bin/echo",
        "--mode",
        "ask",
        "--sandbox",
        "enabled",
        "--trust",
        "--print",
        "--output-format",
        "json",
        "--model",
        "cursor-grok-4.6-high",
    ]
    assert captured["cwd"] != str(llm_provider.ROOT_DIR)
    assert "Do not inspect files" in captured["input"]
    assert "Return the requested section." in captured["input"]
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert "OPENAI_API_KEY" not in captured["env"]
    assert "GITHUB_TOKEN" not in captured["env"]
    assert captured["env"]["CURSOR_API_KEY"] == "cursor-key-is-required-when-configured"

    records = [
        json.loads(line)
        for line in (tmp_path / "llm.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["provider"] == "cursor"
    assert records[0]["model"] == "cursor-grok-4.6-high"
    assert records[0]["success"] is True
    assert records[0]["cache_hit"] is False
    assert records[0]["prompt_chars"] == len("Return the requested section.")
    assert "prompt" not in records[0]


def test_cursor_success_is_cached_by_exact_prompt_and_model(monkeypatch, tmp_path):
    calls = []
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_api_ms": 39,
        "result": "exact cached response",
        "session_id": "fixture-session",
    }

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    environment = _cursor_environment(
        tmp_path,
        **{
            llm_provider.CURSOR_CACHE_DIR_ENV: str(tmp_path / "cache"),
        },
    )

    first = llm_provider.complete_text(
        "same exact prompt",
        "ignored",
        label="Pass 1: Select",
        max_tokens=4096,
        environment=environment,
    )
    second = llm_provider.complete_text(
        "same exact prompt",
        "ignored",
        label="Pass 1: Select",
        max_tokens=4096,
        environment=environment,
    )

    assert first == second == "exact cached response"
    assert len(calls) == 1
    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert len(cache_files) == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "llm.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["cache_hit"] for record in records] == [False, True]
    assert records[1]["attempt_count"] == 0


def test_cursor_cache_key_changes_with_prompt_model_label_or_budget(
    monkeypatch,
    tmp_path,
):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        payload = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": f"response-{len(calls)}",
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    environment = _cursor_environment(
        tmp_path,
        **{llm_provider.CURSOR_CACHE_DIR_ENV: str(tmp_path / "cache")},
    )

    llm_provider.complete_text(
        "prompt-a", "ignored", label="Pass 1: Select", max_tokens=4096,
        environment=environment,
    )
    llm_provider.complete_text(
        "prompt-b", "ignored", label="Pass 1: Select", max_tokens=4096,
        environment=environment,
    )
    llm_provider.complete_text(
        "prompt-a", "ignored", label="Pass 1b: Bounded re-select", max_tokens=4096,
        environment=environment,
    )
    llm_provider.complete_text(
        "prompt-a", "ignored", label="Pass 1: Select", max_tokens=2048,
        environment=environment,
    )
    auto_environment = dict(environment)
    auto_environment[llm_provider.CURSOR_ROUTING_ENV] = "auto"
    llm_provider.complete_text(
        "prompt-a", "ignored", label="Pass 1: Select", max_tokens=4096,
        environment=auto_environment,
    )

    assert len(calls) == 5
    assert len(list((tmp_path / "cache").glob("*.json"))) == 5


def test_cursor_failed_response_is_never_cached(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_run(*_args, **_kwargs):
        calls["count"] += 1
        return SimpleNamespace(returncode=1, stdout="", stderr="connection lost")

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    monkeypatch.setattr(llm_provider.time, "sleep", lambda _seconds: None)
    environment = _cursor_environment(
        tmp_path,
        **{llm_provider.CURSOR_CACHE_DIR_ENV: str(tmp_path / "cache")},
    )

    for _ in range(2):
        with pytest.raises(llm_provider.LLMProviderError):
            llm_provider.complete_text(
                "fixture",
                "ignored",
                label="Pass 3: Score",
                environment=environment,
            )

    assert calls["count"] == 4
    assert not list((tmp_path / "cache").glob("*.json"))


def test_cursor_failure_does_not_fall_back_to_anthropic(monkeypatch, tmp_path):
    calls = {"anthropic": 0}

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="not authenticated")

    def forbidden_anthropic(*_args, **_kwargs):
        calls["anthropic"] += 1
        raise AssertionError("metered fallback must not run")

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    monkeypatch.setattr(llm_provider, "_call_anthropic", forbidden_anthropic)
    monkeypatch.setattr(llm_provider.time, "sleep", lambda _seconds: None)

    with pytest.raises(llm_provider.LLMProviderError, match="after 2 attempts"):
        llm_provider.complete_text(
            "fixture",
            "claude-sonnet-4-6",
            label="Pass 3: Score",
            environment=_cursor_environment(tmp_path),
        )

    assert calls["anthropic"] == 0
    record = json.loads(
        (tmp_path / "llm.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert record["success"] is False
    assert record["error_type"] == "LLMProviderError"


def test_cursor_preflight_checks_login_and_exact_account_models(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command[-1] == "status":
            return SimpleNamespace(
                returncode=0,
                stdout="Logged in as fixture@example.com",
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "Available models\n"
                "auto - Auto (default)\n"
                "cursor-grok-4.6-high - Cursor Grok 4.6\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(llm_provider.subprocess, "run", fake_run)
    ready = llm_provider.validate_cursor_ready(
        environment=_cursor_environment(tmp_path)
    )

    assert ready["auto_model"] == "auto"
    assert ready["hard_model"] == "cursor-grok-4.6-high"
    assert calls == [["/bin/echo", "status"], ["/bin/echo", "models"]]


def test_strategy_uses_provider_without_demanding_anthropic_key(monkeypatch):
    monkeypatch.setattr(
        strategy,
        "complete_text",
        lambda *_args, **_kwargs: json.dumps(
            {
                "company": "Fixture",
                "role_title": "Product Intern",
                "role_family": "pm",
                "primary_framing_axis": "customer discovery",
            }
        ),
    )

    parsed, formatted = strategy.generate_strategy(
        jd_text="Product Intern",
        model="claude-sonnet-4-6",
        api_key="",
    )

    assert parsed["company"] == "Fixture"
    assert "customer discovery" in formatted


def test_jobs_propagates_cursor_provider_to_each_child():
    args = SimpleNamespace(
        no_rewrite=False,
        no_score=False,
        no_qc=False,
        no_strategy=False,
        model="claude-sonnet-4-6",
        provider="cursor",
        cursor_routing="hybrid",
        no_smart_cost=True,
        no_docx=False,
    )

    flags = jobs._build_run_app_flags(args, resume_only=True)

    assert flags[flags.index("--provider") + 1] == "cursor"
    assert flags[flags.index("--cursor-routing") + 1] == "hybrid"
    assert "--no-smart-cost" in flags
    assert "--resume-only" in flags
