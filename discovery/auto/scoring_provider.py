"""Discovery client using the existing isolated, cached Cursor adapter."""

import os
import time
from types import SimpleNamespace

from shared import llm_provider

PROVIDER_ENV = "DISCOVERY_LLM_PROVIDER"
DEFAULT_PROVIDER = "cursor"


def active_provider():
    provider = os.environ.get(PROVIDER_ENV, DEFAULT_PROVIDER).strip().lower()
    if provider not in {"cursor", "anthropic"}:
        raise ValueError(f"Invalid {PROVIDER_ENV}: {provider!r}")
    return provider


def scoring_identity():
    """Separate saved reviews when the selected execution provider changes."""
    provider = active_provider()
    if provider == "cursor":
        return {"provider": provider, "model": os.environ.get(
            llm_provider.CURSOR_AUTO_MODEL_ENV, llm_provider.DEFAULT_CURSOR_AUTO_MODEL)}
    return {"provider": provider}


class CursorScoringClient:
    """Small text-message bridge; paid-provider fallback is deliberately absent."""

    def __init__(self, *, deadline_epoch=None, request_timeout=60):
        self.deadline_epoch = deadline_epoch
        self.request_timeout = request_timeout
        self.messages = self

    def create(self, *, model, max_tokens, messages, timeout=None):
        if len(messages) != 1 or messages[0].get("role") != "user":
            raise ValueError("Discovery expects one text-only user prompt")
        prompt = messages[0]["content"]
        if not isinstance(prompt, str):
            raise ValueError("Discovery Cursor scoring supports text only")
        environment = dict(os.environ)
        environment[llm_provider.PROVIDER_ENV] = "cursor"
        environment[llm_provider.CURSOR_ROUTING_ENV] = "auto"
        deadline = time.time() + min(self.request_timeout, timeout or self.request_timeout)
        if self.deadline_epoch is not None:
            deadline = min(deadline, self.deadline_epoch)
        environment[llm_provider.CURSOR_DEADLINE_ENV] = str(deadline)
        text = llm_provider.complete_text(
            prompt, model, label="Discovery: Score", max_tokens=max_tokens,
            environment=environment,
        )
        return SimpleNamespace(content=[SimpleNamespace(text=text)])


def create_scoring_client(*, deadline_epoch=None, request_timeout=60):
    if active_provider() == "cursor":
        return CursorScoringClient(deadline_epoch=deadline_epoch, request_timeout=request_timeout)
    # The API key is read only after an explicit Anthropic selection.
    import anthropic
    from discovery.auto.scorer import _load_api_key
    return anthropic.Anthropic(api_key=_load_api_key(), timeout=request_timeout, max_retries=0)
