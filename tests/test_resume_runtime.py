import pytest

from shared.resume_runtime import (
    RUNTIME_MODE_ENV,
    V2_SKILL_ROWS_ENV,
    V2_SKILLS_SELECTOR_ENV,
    V2FeatureMode,
    ResumeRuntimeMode,
    requested_v2_skill_rows,
    resolve_runtime_policy,
    resolve_v2_feature_mode,
)


def test_runtime_defaults_to_legacy_and_cannot_change_the_shipping_artifact():
    policy = resolve_runtime_policy(environment={})
    assert policy.mode is ResumeRuntimeMode.LEGACY
    assert not policy.challenger_may_change_artifact
    assert not policy.challenger_report_required


def test_shadow_runs_challenger_reporting_without_shipping_it():
    policy = resolve_runtime_policy(environment={RUNTIME_MODE_ENV: "shadow"})
    assert policy.mode is ResumeRuntimeMode.SHADOW
    assert policy.challenger_report_required
    assert not policy.challenger_may_change_artifact


def test_v2_requires_an_explicit_switch_before_it_can_ship():
    policy = resolve_runtime_policy(ResumeRuntimeMode.V2, environment={})
    assert policy.challenger_may_change_artifact


def test_invalid_runtime_mode_fails_closed():
    with pytest.raises(ValueError, match="Unknown resume runtime mode"):
        resolve_runtime_policy("automatic", environment={})


def test_v2_content_selectors_default_to_shadow_without_changing_the_artifact():
    assert (
        resolve_v2_feature_mode(V2_SKILLS_SELECTOR_ENV, environment={})
        is V2FeatureMode.SHADOW
    )
    assert (
        resolve_v2_feature_mode(
            V2_SKILLS_SELECTOR_ENV,
            V2FeatureMode.APPLY,
            environment={},
        )
        is V2FeatureMode.APPLY
    )


def test_v2_skill_row_request_is_bounded_to_five_or_six():
    # The default considers a sixth, but the resolver and rendered-geometry
    # gates still keep five unless that extra row earns its space.
    assert requested_v2_skill_rows(environment={}) == 6
    assert requested_v2_skill_rows(environment={V2_SKILL_ROWS_ENV: "5"}) == 5
    assert requested_v2_skill_rows(environment={V2_SKILL_ROWS_ENV: "6"}) == 6
    with pytest.raises(ValueError, match="must be 5 or 6"):
        requested_v2_skill_rows(environment={V2_SKILL_ROWS_ENV: "7"})
