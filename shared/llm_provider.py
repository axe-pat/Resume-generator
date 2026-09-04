"""Provider boundary for application-generation model calls.

The existing prompts, parsing, validation, and release gates remain the source
of truth.  This module only decides where a prompt is executed and records the
call.  Anthropic remains the default incumbent; Cursor is opt-in until its
outputs win the existing non-regression checks.

Cursor runs in an empty temporary directory and Ask mode.  It receives the
entire prompt over stdin, cannot mutate the resume repository, and never falls
back to a metered API provider unless a caller explicitly implements that
policy outside this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


ROOT_DIR = Path(__file__).resolve().parent.parent

PROVIDER_ENV = "RESUME_LLM_PROVIDER"
CURSOR_ROUTING_ENV = "RESUME_CURSOR_ROUTING"
CURSOR_AUTO_MODEL_ENV = "RESUME_CURSOR_AUTO_MODEL"
CURSOR_HARD_MODEL_ENV = "RESUME_CURSOR_HARD_MODEL"
CURSOR_CLI_ENV = "RESUME_CURSOR_CLI"
CURSOR_TIMEOUT_ENV = "RESUME_CURSOR_TIMEOUT_SECONDS"
TELEMETRY_PATH_ENV = "RESUME_LLM_TELEMETRY_PATH"
CURSOR_CACHE_DIR_ENV = "RESUME_CURSOR_CACHE_DIR"
CURSOR_CACHE_MODE_ENV = "RESUME_CURSOR_CACHE_MODE"

DEFAULT_PROVIDER = "anthropic"
DEFAULT_CURSOR_ROUTING = "hybrid"
DEFAULT_CURSOR_AUTO_MODEL = "auto"
DEFAULT_CURSOR_HARD_MODEL = "cursor-grok-4.6-high"
DEFAULT_CURSOR_TIMEOUT_SECONDS = 600
DEFAULT_CURSOR_CACHE_MODE = "readwrite"
CURSOR_CACHE_SCHEMA_VERSION = "2026-09-04.1"
# EX_TEMPFAIL: lets jobs.py distinguish a resumable provider interruption from
# content, validation, provenance, or render failures that must not be retried.
CURSOR_TRANSIENT_EXIT_CODE = 75

VALID_PROVIDERS = ("anthropic", "cursor")
VALID_CURSOR_ROUTING = ("hybrid", "auto", "grok")
VALID_CURSOR_CACHE_MODES = ("off", "readwrite", "refresh")

# Explicitly cheap/basic model work.  Unknown labels default to the hard model:
# quality should not silently fall merely because a new semantic pass was added.
_CURSOR_AUTO_LABEL_PREFIXES = (
    "Pass 0: Strategy",
    "Pass 3: Score",
    "Step 1",
    "Step 3",
)

_PRINT_LOCK = threading.Lock()
_TELEMETRY_LOCK = threading.Lock()
_SECRET_ENV_MARKERS = (
    "API_KEY",
    "ACCESS_KEY",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)


class LLMProviderError(RuntimeError):
    """A provider could not complete a text-generation request."""


@dataclass(frozen=True)
class CallPlan:
    """Resolved provider/model decision for one pipeline stage."""

    provider: str
    model: str
    routing_class: str
    label: str


@dataclass(frozen=True)
class CallTelemetry:
    """Non-sensitive metadata for one provider invocation."""

    timestamp_utc: str
    provider: str
    model: str
    routing_class: str
    label: str
    success: bool
    elapsed_seconds: float
    prompt_chars: int
    response_chars: int
    prompt_sha256: str
    attempt_count: int
    cache_hit: bool = False
    provider_duration_ms: int | None = None
    session_id: str | None = None
    error_type: str | None = None


def _normalise(value: object) -> str:
    return str(value or "").strip().lower()


def apply_cli_overrides(
    *,
    provider: str | None = None,
    cursor_routing: str | None = None,
) -> None:
    """Apply explicit CLI choices to this process without changing defaults."""

    if provider is not None:
        normalised = _normalise(provider)
        if normalised not in VALID_PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider {provider!r}; expected one of {VALID_PROVIDERS}"
            )
        os.environ[PROVIDER_ENV] = normalised
    if cursor_routing is not None:
        normalised = _normalise(cursor_routing)
        if normalised not in VALID_CURSOR_ROUTING:
            raise ValueError(
                "Unknown Cursor routing policy "
                f"{cursor_routing!r}; expected one of {VALID_CURSOR_ROUTING}"
            )
        os.environ[CURSOR_ROUTING_ENV] = normalised


def resolve_call_plan(
    label: str,
    legacy_model: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> CallPlan:
    """Resolve the provider/model for a pipeline stage deterministically."""

    env = os.environ if environment is None else environment
    provider = _normalise(env.get(PROVIDER_ENV, DEFAULT_PROVIDER))
    if provider not in VALID_PROVIDERS:
        raise LLMProviderError(
            f"Invalid {PROVIDER_ENV}={provider!r}; expected one of {VALID_PROVIDERS}"
        )

    if provider == "anthropic":
        model = str(legacy_model or "").strip()
        if not model:
            raise LLMProviderError("Anthropic calls require a non-empty model name")
        return CallPlan(
            provider="anthropic",
            model=model,
            routing_class="incumbent",
            label=label,
        )

    routing = _normalise(env.get(CURSOR_ROUTING_ENV, DEFAULT_CURSOR_ROUTING))
    if routing not in VALID_CURSOR_ROUTING:
        raise LLMProviderError(
            f"Invalid {CURSOR_ROUTING_ENV}={routing!r}; "
            f"expected one of {VALID_CURSOR_ROUTING}"
        )
    auto_model = str(
        env.get(CURSOR_AUTO_MODEL_ENV, DEFAULT_CURSOR_AUTO_MODEL)
    ).strip()
    hard_model = str(
        env.get(CURSOR_HARD_MODEL_ENV, DEFAULT_CURSOR_HARD_MODEL)
    ).strip()
    if not auto_model or not hard_model:
        raise LLMProviderError("Cursor model identifiers must be non-empty")

    if routing == "auto":
        model, routing_class = auto_model, "basic"
    elif routing == "grok":
        model, routing_class = hard_model, "hard"
    elif any(label.startswith(prefix) for prefix in _CURSOR_AUTO_LABEL_PREFIXES):
        model, routing_class = auto_model, "basic"
    else:
        model, routing_class = hard_model, "hard"
    return CallPlan(
        provider="cursor",
        model=model,
        routing_class=routing_class,
        label=label,
    )


def provider_summary(
    *, environment: Mapping[str, str] | None = None
) -> str:
    """Return a concise human-readable description of active routing."""

    env = os.environ if environment is None else environment
    provider = _normalise(env.get(PROVIDER_ENV, DEFAULT_PROVIDER))
    if provider != "cursor":
        return f"provider={provider or DEFAULT_PROVIDER}"
    routing = _normalise(env.get(CURSOR_ROUTING_ENV, DEFAULT_CURSOR_ROUTING))
    auto_model = env.get(CURSOR_AUTO_MODEL_ENV, DEFAULT_CURSOR_AUTO_MODEL)
    hard_model = env.get(CURSOR_HARD_MODEL_ENV, DEFAULT_CURSOR_HARD_MODEL)
    return (
        f"provider=cursor | routing={routing} | "
        f"basic={auto_model} | hard={hard_model}"
    )


def _load_secret(name: str, *, explicit: str = "") -> str:
    if explicit:
        return explicit
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith(f"{name}="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    return ""


def load_anthropic_api_key(*, explicit: str = "") -> str:
    """Retain the incumbent key-loading behavior for legacy callers."""

    key = _load_secret("ANTHROPIC_API_KEY", explicit=explicit)
    if not key:
        raise LLMProviderError(
            "ANTHROPIC_API_KEY not set. Check .env or the environment."
        )
    return key


def _cursor_cli_path(environment: Mapping[str, str]) -> str:
    explicit = str(environment.get(CURSOR_CLI_ENV, "")).strip()
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        raise LLMProviderError(
            f"{CURSOR_CLI_ENV} points to a missing or non-executable file: {candidate}"
        )

    for name in ("cursor-agent", "agent"):
        found = shutil.which(name)
        if found:
            return found

    home = Path.home()
    for candidate in (
        home / ".local" / "bin" / "cursor-agent",
        home / ".local" / "bin" / "agent",
        home / ".cursor" / "bin" / "cursor-agent",
        home / ".cursor" / "bin" / "agent",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    raise LLMProviderError(
        "Cursor Agent CLI not found. Install the official CLI, then run "
        "`cursor-agent status` once before generation."
    )


def _cursor_timeout(environment: Mapping[str, str]) -> int:
    raw = str(
        environment.get(CURSOR_TIMEOUT_ENV, DEFAULT_CURSOR_TIMEOUT_SECONDS)
    ).strip()
    try:
        timeout = int(raw)
    except ValueError as exc:
        raise LLMProviderError(
            f"{CURSOR_TIMEOUT_ENV} must be an integer, got {raw!r}"
        ) from exc
    if not 30 <= timeout <= 1800:
        raise LLMProviderError(
            f"{CURSOR_TIMEOUT_ENV} must be between 30 and 1800 seconds"
        )
    return timeout


def _cursor_cache_mode(environment: Mapping[str, str]) -> str:
    mode = _normalise(
        environment.get(CURSOR_CACHE_MODE_ENV, DEFAULT_CURSOR_CACHE_MODE)
    )
    if mode not in VALID_CURSOR_CACHE_MODES:
        raise LLMProviderError(
            f"Invalid {CURSOR_CACHE_MODE_ENV}={mode!r}; "
            f"expected one of {VALID_CURSOR_CACHE_MODES}"
        )
    return mode


def _cursor_cache_dir(environment: Mapping[str, str]) -> Path:
    configured = str(environment.get(CURSOR_CACHE_DIR_ENV, "")).strip()
    if configured:
        return Path(configured).expanduser()
    # ``logs/`` is already ignored by git. Keeping the cache inside the repo
    # makes it durable across process restarts without leaking it into commits.
    return ROOT_DIR / "logs" / "cursor_response_cache"


def _cursor_cache_key(
    *,
    prompt: str,
    plan: CallPlan,
    max_tokens: int,
) -> tuple[str, str]:
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    identity = {
        "schema_version": CURSOR_CACHE_SCHEMA_VERSION,
        "provider": plan.provider,
        "model": plan.model,
        "routing_class": plan.routing_class,
        "label": plan.label,
        "max_tokens": int(max_tokens),
        "prompt_sha256": prompt_sha256,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), prompt_sha256


def _read_cursor_cache(
    *,
    prompt: str,
    plan: CallPlan,
    max_tokens: int,
    environment: Mapping[str, str],
) -> str | None:
    if _cursor_cache_mode(environment) != "readwrite":
        return None
    cache_key, prompt_sha256 = _cursor_cache_key(
        prompt=prompt,
        plan=plan,
        max_tokens=max_tokens,
    )
    path = _cursor_cache_dir(environment) / f"{cache_key}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    response = payload.get("response")
    expected = {
        "schema_version": CURSOR_CACHE_SCHEMA_VERSION,
        "cache_key": cache_key,
        "model": plan.model,
        "label": plan.label,
        "max_tokens": int(max_tokens),
        "prompt_sha256": prompt_sha256,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        return None
    if not isinstance(response, str) or not response.strip():
        return None
    if payload.get("response_sha256") != hashlib.sha256(
        response.encode("utf-8")
    ).hexdigest():
        return None
    return response


def _write_cursor_cache(
    response: str,
    *,
    prompt: str,
    plan: CallPlan,
    max_tokens: int,
    environment: Mapping[str, str],
) -> None:
    if _cursor_cache_mode(environment) == "off":
        return
    cache_key, prompt_sha256 = _cursor_cache_key(
        prompt=prompt,
        plan=plan,
        max_tokens=max_tokens,
    )
    cache_dir = _cursor_cache_dir(environment)
    path = cache_dir / f"{cache_key}.json"
    payload = {
        "schema_version": CURSOR_CACHE_SCHEMA_VERSION,
        "cache_key": cache_key,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": plan.provider,
        "model": plan.model,
        "routing_class": plan.routing_class,
        "label": plan.label,
        "max_tokens": int(max_tokens),
        "prompt_sha256": prompt_sha256,
        "response": response,
        "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
    }
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        staged = cache_dir / (
            f".{cache_key}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        staged.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        os.chmod(staged, 0o600)
        os.replace(staged, path)
    except OSError:
        # Caching is a recovery optimization, never a generation dependency.
        return


def _cursor_child_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Retain Cursor auth/network settings while removing unrelated secrets."""

    child_env = dict(environment)
    for name in tuple(child_env):
        upper_name = name.upper()
        if upper_name.startswith("CURSOR_"):
            continue
        if any(marker in upper_name for marker in _SECRET_ENV_MARKERS):
            child_env.pop(name, None)
    child_env["NO_COLOR"] = "1"
    child_env["TERM"] = "dumb"
    return child_env


def validate_cursor_ready(
    *, environment: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Fail before a batch if login or configured model IDs are unavailable."""

    env = os.environ if environment is None else environment
    binary = _cursor_cli_path(env)
    child_env = _cursor_child_environment(env)

    def run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                text=True,
                capture_output=True,
                env=child_env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LLMProviderError(
                f"Cursor preflight timed out: {' '.join(command)}"
            ) from exc

    status = run([binary, "status"], 60)
    status_text = "\n".join((status.stdout or "", status.stderr or "")).strip()
    if status.returncode != 0 or "logged in as" not in status_text.lower():
        raise LLMProviderError(
            "Cursor CLI is not authenticated. Run `~/.local/bin/agent login` once."
        )

    models = run([binary, "models"], 120)
    models_text = "\n".join((models.stdout or "", models.stderr or ""))
    if models.returncode != 0:
        raise LLMProviderError(
            "Cursor model catalog preflight failed: " + models_text.strip()[:800]
        )
    required = {
        "auto_model": str(
            env.get(CURSOR_AUTO_MODEL_ENV, DEFAULT_CURSOR_AUTO_MODEL)
        ).strip(),
        "hard_model": str(
            env.get(CURSOR_HARD_MODEL_ENV, DEFAULT_CURSOR_HARD_MODEL)
        ).strip(),
    }
    available_ids = {
        line.split(" - ", 1)[0].strip()
        for line in models_text.splitlines()
        if " - " in line
    }
    missing = [model for model in required.values() if model not in available_ids]
    if missing:
        raise LLMProviderError(
            "Configured Cursor model(s) not available on this account: "
            + ", ".join(missing)
        )
    return {"binary": binary, **required}


def _cursor_prompt(prompt: str) -> str:
    return "\n".join(
        (
            "TEXT-ONLY PIPELINE COMPONENT",
            "Use only the prompt supplied below.",
            "Do not inspect files, browse, run commands, or modify anything.",
            "Return only the response requested by the pipeline prompt.",
            "",
            "PIPELINE_PROMPT_BEGIN",
            prompt,
            "PIPELINE_PROMPT_END",
        )
    )


def _parse_cursor_json(stdout: str) -> tuple[str, int | None, str | None]:
    stripped = stdout.strip()
    if not stripped:
        raise LLMProviderError("Cursor CLI returned empty stdout")

    payload = None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        # Be tolerant of a one-line updater/status prefix while still requiring
        # the documented terminal JSON object.
        for line in reversed(stripped.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("type") == "result":
                payload = candidate
                break
    if not isinstance(payload, dict):
        raise LLMProviderError("Cursor CLI did not return its documented JSON result")
    if (
        payload.get("type") != "result"
        or payload.get("subtype") != "success"
        or payload.get("is_error") is not False
    ):
        raise LLMProviderError(
            "Cursor CLI returned a non-success result: "
            + json.dumps(payload, ensure_ascii=False)[:500]
        )
    result = payload.get("result")
    if not isinstance(result, str) or not result.strip():
        raise LLMProviderError("Cursor CLI success result contained no assistant text")
    duration_ms = payload.get("duration_api_ms", payload.get("duration_ms"))
    if not isinstance(duration_ms, int):
        duration_ms = None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        session_id = None
    return result, duration_ms, session_id


def _call_cursor(
    prompt: str,
    plan: CallPlan,
    *,
    environment: Mapping[str, str],
) -> tuple[str, int, int | None, str | None]:
    binary = _cursor_cli_path(environment)
    timeout = _cursor_timeout(environment)
    child_env = _cursor_child_environment(environment)
    command = [
        binary,
        "--mode",
        "ask",
        "--sandbox",
        "enabled",
        "--trust",
        "--print",
        "--output-format",
        "json",
        "--model",
        plan.model,
    ]

    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            with tempfile.TemporaryDirectory(prefix="resume-cursor-") as temp_dir:
                completed = subprocess.run(
                    command,
                    input=_cursor_prompt(prompt),
                    text=True,
                    capture_output=True,
                    cwd=temp_dir,
                    env=child_env,
                    timeout=timeout,
                    check=False,
                )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()
                raise LLMProviderError(
                    f"Cursor CLI exited {completed.returncode}: {detail[:800]}"
                )
            text, duration_ms, session_id = _parse_cursor_json(completed.stdout)
            return text, attempt, duration_ms, session_id
        except (LLMProviderError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2)
    raise LLMProviderError(f"Cursor call failed after 2 attempts: {last_error}")


def _call_anthropic(
    prompt: str,
    plan: CallPlan,
    *,
    max_tokens: int,
    api_key: str,
) -> tuple[str, int, int | None, str | None]:
    import anthropic
    import httpx

    key = load_anthropic_api_key(explicit=api_key)
    client = anthropic.Anthropic(
        api_key=key,
        http_client=httpx.Client(verify=False),
    )
    for attempt in range(1, 5):
        try:
            message = client.messages.create(
                model=plan.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text, attempt, None, None
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            time.sleep(20 * (2 ** (attempt - 1)))
        except anthropic.APIStatusError as exc:
            if getattr(exc, "status_code", None) != 529 or attempt == 4:
                raise
            time.sleep(20 * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


def _telemetry_path(environment: Mapping[str, str]) -> Path:
    configured = str(environment.get(TELEMETRY_PATH_ENV, "")).strip()
    if configured:
        return Path(configured).expanduser()
    return ROOT_DIR / "logs" / "llm_calls.jsonl"


def _write_telemetry(
    record: CallTelemetry,
    *,
    environment: Mapping[str, str],
) -> None:
    path = _telemetry_path(environment)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
        with _TELEMETRY_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError:
        # Telemetry must never be allowed to change generation behavior.
        return


def complete_text(
    prompt: str,
    legacy_model: str,
    *,
    label: str = "",
    max_tokens: int = 8192,
    api_key: str = "",
    environment: Mapping[str, str] | None = None,
) -> str:
    """Complete one pipeline prompt through the configured provider.

    ``legacy_model`` remains authoritative for Anthropic.  Cursor ignores that
    vendor-specific name and uses the deterministic stage policy instead.
    """

    env = os.environ if environment is None else environment
    plan = resolve_call_plan(label, legacy_model, environment=env)
    tag = f" [{label}]" if label else ""
    with _PRINT_LOCK:
        print(f"  -> Calling {plan.provider}:{plan.model}{tag}...", flush=True)

    started = time.perf_counter()
    response = ""
    attempts = 0
    provider_duration_ms = None
    session_id = None
    cache_hit = False
    error: Exception | None = None
    try:
        if plan.provider == "cursor":
            cached_response = _read_cursor_cache(
                prompt=prompt,
                plan=plan,
                max_tokens=max_tokens,
                environment=env,
            )
            if cached_response is not None:
                response = cached_response
                cache_hit = True
                with _PRINT_LOCK:
                    print(
                        f"  CACHE {label or 'LLM call'} reused exact Cursor response",
                        flush=True,
                    )
            else:
                response, attempts, provider_duration_ms, session_id = _call_cursor(
                    prompt,
                    plan,
                    environment=env,
                )
                _write_cursor_cache(
                    response,
                    prompt=prompt,
                    plan=plan,
                    max_tokens=max_tokens,
                    environment=env,
                )
        else:
            response, attempts, provider_duration_ms, session_id = _call_anthropic(
                prompt,
                plan,
                max_tokens=max_tokens,
                api_key=api_key,
            )
        return response
    except Exception as exc:
        error = exc
        raise
    finally:
        elapsed = time.perf_counter() - started
        _write_telemetry(
            CallTelemetry(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                provider=plan.provider,
                model=plan.model,
                routing_class=plan.routing_class,
                label=label,
                success=error is None,
                elapsed_seconds=round(elapsed, 3),
                prompt_chars=len(prompt),
                response_chars=len(response),
                prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                attempt_count=attempts,
                cache_hit=cache_hit,
                provider_duration_ms=provider_duration_ms,
                session_id=session_id,
                error_type=type(error).__name__ if error else None,
            ),
            environment=env,
        )
        if error is None and not cache_hit:
            done_label = label or "LLM call"
            with _PRINT_LOCK:
                print(f"  OK {done_label} complete ({elapsed:.1f}s)", flush=True)


__all__ = [
    "CURSOR_CACHE_DIR_ENV",
    "CURSOR_CACHE_MODE_ENV",
    "CURSOR_TRANSIENT_EXIT_CODE",
    "CURSOR_AUTO_MODEL_ENV",
    "CURSOR_CLI_ENV",
    "CURSOR_HARD_MODEL_ENV",
    "CURSOR_ROUTING_ENV",
    "DEFAULT_CURSOR_AUTO_MODEL",
    "DEFAULT_CURSOR_CACHE_MODE",
    "DEFAULT_CURSOR_HARD_MODEL",
    "DEFAULT_CURSOR_ROUTING",
    "DEFAULT_PROVIDER",
    "LLMProviderError",
    "PROVIDER_ENV",
    "TELEMETRY_PATH_ENV",
    "VALID_CURSOR_ROUTING",
    "VALID_CURSOR_CACHE_MODES",
    "VALID_PROVIDERS",
    "apply_cli_overrides",
    "complete_text",
    "load_anthropic_api_key",
    "provider_summary",
    "resolve_call_plan",
    "validate_cursor_ready",
]
