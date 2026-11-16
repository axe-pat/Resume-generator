"""Discovery uses Cursor independently of resume routing and paid API credentials."""
import subprocess
import time

import pytest

from discovery.auto import scoring_provider
from shared import llm_provider
from shared.discovery_review_journal import review_batch


def test_default_discovery_routes_to_existing_cursor_adapter(monkeypatch):
    monkeypatch.delenv(scoring_provider.PROVIDER_ENV, raising=False)
    monkeypatch.setenv(llm_provider.PROVIDER_ENV, "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    deadline = time.time() + 5
    captured = {}

    def complete(prompt, model, **kwargs):
        captured.update(kwargs)
        assert prompt == "saved JD and profile"
        return "Decision: Proceed\nfit_score: 8.4"

    monkeypatch.setattr(llm_provider, "complete_text", complete)
    client = scoring_provider.create_scoring_client(deadline_epoch=deadline)
    response = client.messages.create(model="incumbent", max_tokens=400,
        messages=[{"role": "user", "content": "saved JD and profile"}], timeout=30)
    assert "8.4" in response.content[0].text
    env = captured["environment"]
    assert env[llm_provider.PROVIDER_ENV] == "cursor"
    assert env[llm_provider.CURSOR_ROUTING_ENV] == "auto"
    assert float(env[llm_provider.CURSOR_DEADLINE_ENV]) <= deadline
    assert llm_provider.resolve_call_plan(captured['label'], 'incumbent', environment=env).model == 'auto'


def test_cursor_failure_never_constructs_paid_client(monkeypatch):
    import anthropic
    monkeypatch.setenv(scoring_provider.PROVIDER_ENV, "cursor")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: pytest.fail("paid fallback"))
    def unavailable(*args, **kwargs):
        raise llm_provider.LLMProviderError("authentication required")
    monkeypatch.setattr(llm_provider, "complete_text", unavailable)
    with pytest.raises(llm_provider.LLMProviderError, match="authentication required"):
        scoring_provider.create_scoring_client().messages.create(
            model="incumbent", max_tokens=400, messages=[{"role":"user", "content":"JD"}])


def test_cursor_subprocess_obeys_subsecond_deadline(monkeypatch):
    monkeypatch.setattr(llm_provider, "_cursor_cli_path", lambda env: "/bin/echo")
    clock = [100.0]
    monkeypatch.setattr(llm_provider.time, "time", lambda: clock[0])
    monkeypatch.setattr(llm_provider.time, "sleep", lambda _: pytest.fail("retry exceeded deadline"))
    calls = []
    def timeout(command, **kwargs):
        calls.append(kwargs['timeout'])
        clock[0] = 101.0
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    monkeypatch.setattr(llm_provider.subprocess, "run", timeout)
    env = {llm_provider.PROVIDER_ENV:'cursor', llm_provider.CURSOR_DEADLINE_ENV:'100.25'}
    plan = llm_provider.resolve_call_plan('Discovery: Score', 'incumbent', environment=env)
    with pytest.raises(llm_provider.LLMProviderError):
        llm_provider._call_cursor('JD', plan, environment=env)
    assert calls == [.25]


def test_saved_reviews_do_not_cross_provider_boundary(tmp_path, monkeypatch):
    rows = [{'url':'a','company':'A','role_title':'PM','jd_text':'JD','lane':'B'}]
    calls = []
    def score(jobs, on_result, **kwargs):
        calls.append(len(jobs))
        result = {**jobs[0], 'decision':'Proceed', 'fit_score':8}
        on_result(result)
        return [result]
    journal = tmp_path/'reviews.jsonl'
    monkeypatch.setenv(scoring_provider.PROVIDER_ENV, 'anthropic')
    review_batch(rows, score_fn=score, journal=journal)
    monkeypatch.setenv(scoring_provider.PROVIDER_ENV, 'cursor')
    review_batch(rows, score_fn=score, journal=journal)
    review_batch(rows, score_fn=score, journal=journal)
    assert calls == [1, 1]
