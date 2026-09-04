"""Runtime rollout policy for the resume generator rebuild.

The incumbent remains the default.  Shadow mode may calculate v2 routing,
selection, and lint reports but cannot alter the artifact selected for release.
Only explicit v2 mode may make the challenger authoritative.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


RUNTIME_MODE_ENV = "RESUME_GENERATOR_MODE"
V2_BULLET_BUDGET_ENV = "RESUME_V2_BULLET_BUDGET"
V2_ADD_COMPANY_ENV = "RESUME_V2_ADD_COMPANY"
V2_SKILLS_SELECTOR_ENV = "RESUME_V2_SKILLS_SELECTOR"
V2_SKILL_ROWS_ENV = "RESUME_V2_SKILL_ROWS"
V2_SUMMARY_SELECTOR_ENV = "RESUME_V2_SUMMARY_SELECTOR"

# Process-level signal used only by the jobs.py orchestrator.  Normal quality,
# scorer, provenance, overflow, and renderer failures continue to exit 1.  This
# dedicated code means an observed one-page underfill can request the single
# sanctioned 10 -> 11 distinct-proof retry without scraping human-readable
# terminal output.
V2_PAGE_UNDERFILLED_EXIT_CODE = 42


class ResumeRuntimeMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    V2 = "v2"


class V2FeatureMode(str, Enum):
    """Independent rollout state for a v2 content-selection surface."""

    OFF = "off"
    SHADOW = "shadow"
    APPLY = "apply"


@dataclass(frozen=True)
class RuntimePolicy:
    mode: ResumeRuntimeMode
    challenger_may_change_artifact: bool
    challenger_report_required: bool


def resolve_v2_feature_mode(
    env_name: str,
    explicit_mode: str | V2FeatureMode | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    default: V2FeatureMode = V2FeatureMode.SHADOW,
) -> V2FeatureMode:
    """Resolve an independently reversible v2 subfeature switch.

    Content-shape changes default to shadow: they may produce an audit, but
    cannot alter the prompt or released artifact until explicitly set to
    ``apply``. This is separate from the top-level legacy/shadow/v2 switch.
    """

    env = os.environ if environment is None else environment
    raw = explicit_mode or env.get(env_name) or default.value
    try:
        return raw if isinstance(raw, V2FeatureMode) else V2FeatureMode(str(raw).strip().lower())
    except ValueError as exc:
        valid = ", ".join(item.value for item in V2FeatureMode)
        raise ValueError(
            f"Unknown {env_name} mode {raw!r}; expected one of: {valid}"
        ) from exc


def requested_v2_skill_rows(
    *, environment: Mapping[str, str] | None = None,
) -> int:
    """Return the bounded Skills row request; geometry still controls release."""

    env = os.environ if environment is None else environment
    # Six is the *consideration ceiling*, not the resolved default. The Skills
    # resolver still returns five unless a sixth carries a distinct, positive
    # JD signal; the renderer then requires portable headroom and deterministically
    # falls back to five if the six-row candidate is too dense.
    raw = str(env.get(V2_SKILL_ROWS_ENV, "6")).strip()
    if raw not in {"5", "6"}:
        raise ValueError(f"{V2_SKILL_ROWS_ENV} must be 5 or 6, got {raw!r}")
    return int(raw)


def resolve_runtime_policy(
    explicit_mode: str | ResumeRuntimeMode | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> RuntimePolicy:
    """Resolve the one-line rollback switch, defaulting safely to legacy."""
    env = os.environ if environment is None else environment
    raw = explicit_mode or env.get(RUNTIME_MODE_ENV) or ResumeRuntimeMode.LEGACY.value
    try:
        mode = raw if isinstance(raw, ResumeRuntimeMode) else ResumeRuntimeMode(str(raw).strip().lower())
    except ValueError as exc:
        valid = ", ".join(item.value for item in ResumeRuntimeMode)
        raise ValueError(f"Unknown resume runtime mode {raw!r}; expected one of: {valid}") from exc
    return RuntimePolicy(
        mode=mode,
        challenger_may_change_artifact=mode is ResumeRuntimeMode.V2,
        challenger_report_required=mode in {ResumeRuntimeMode.SHADOW, ResumeRuntimeMode.V2},
    )
