import json
from pathlib import Path

import pytest

from resume.variants import challenger_runner as runner


def _bundle(story_id="G-PRICING"):
    grouped = runner.group_causal_stories(runner.load_inventory())
    return runner.build_story_bundle(story_id, grouped)


def _valid_response(bundle):
    claim_id = "customer-evidence-to-pricing"
    candidate_id = f"{runner._slug(bundle.story_id)}-material-challenger"
    return {
        "story_id": bundle.story_id,
        "story_level_findings": {
            "highest_stakes_fact": "The product changed customer behavior.",
            "most_non_replicable_fact": "The decision joined interviews and usage evidence.",
            "strongest_attributable_outcome": "A measured conversion outcome.",
            "facts_that_look_impressive_but_should_not_lead": [],
        },
        "claim_spines": [
            {
                "claim_id": claim_id,
                "hiring_question": "Can this person turn evidence into a product decision?",
                "path": {
                    "trigger_or_observation": "Customer behavior split into two causes.",
                    "judgment": "The causes required different interventions.",
                    "decision_or_artifact": "A segmented product decision.",
                    "attributable_consequence": "Conversion changed after launch.",
                },
                "scarce_atom": "insight",
                "counterfactual_ownership": "The causal separation and resulting decision.",
                "excluded_adjacent_atoms": [],
                "eligible_profiles": ["product-general"],
                "incumbent_ids": [record.stable_id for record in bundle.incumbents],
            }
        ],
        "incumbent_decisions": [
            {
                "incumbent_id": record.stable_id,
                "claim_id": claim_id,
                "verdict": "retain_exact",
                "material_reason": "The challenger does not yet dominate this framing.",
                "critical_vetoes": {key: "pass" for key in runner.VETO_KEYS},
                "material_loss_if_replaced": "none",
                "replacement_candidate_id": "",
            }
            for record in bundle.incumbents
        ],
        "challengers": [
            {
                "candidate_id": candidate_id,
                "claim_id": claim_id,
                "text": "Connected customer evidence to one product decision and its matched outcome.",
                "archetype": "diagnostic",
                "one_earned_detail": "the causal separation",
                "matched_outcome": "measured conversion",
                "material_win_over_incumbent": "clearer causal closure",
                "material_loss_vs_incumbent": "none",
                "source_fact_atoms": ["customer evidence", "product decision"],
                "estimated_line_cost": 2,
                "recommendation": "human_review",
                "rulebook_checks": {
                    dimension: {
                        "verdict": "not_applicable" if dimension == "evidence_loop" else "pass",
                        "reason": (
                            "This is not a discovery story."
                            if dimension == "evidence_loop"
                            else "The candidate satisfies this consolidated rule dimension."
                        ),
                    }
                    for dimension in runner.STRUCTURED_CHALLENGER_DIMENSIONS
                },
            }
        ],
        "surviving_variant_ids": [record.stable_id for record in bundle.incumbents],
        "human_decisions": [],
    }


def test_groups_only_causal_surfaces_and_combines_semantic_monitoring_family():
    grouped = runner.group_causal_stories(runner.load_inventory())

    assert len(grouped) == 22
    assert "SUMMARY" not in grouped
    assert "SKILLS-ANALYTICS" not in grouped
    assert "SKILLS-COMMUNITY" not in grouped
    assert len(grouped["H-MONITORING"]) == 13
    assert {record.story for record in grouped["H-MONITORING"]} == {
        "H-MONITORING",
        "H-MONITORING-AI",
    }
    assert {record.story for record in grouped["I-BILLING"]} == {
        "I-BILLING",
        "I-RECONCILIATION",
    }
    assert {record.track for record in grouped["I-BILLING"]} == {"pm", "nonpm"}
    assert {record.track for record in grouped["G-PRICING"]} == {"pm", "nonpm"}


def test_cross_track_value_differences_are_explicit_human_decisions():
    bundle = _bundle("G-PRICING")

    assert bundle.consistency_warnings
    assert "HUMAN DECISION REQUIRED" in bundle.evidence
    assert "PM-only" in bundle.consistency_warnings[0]
    assert "NONPM-only" in bundle.consistency_warnings[0]


def test_story_evidence_prefers_canonical_sources_and_never_uses_counterfactual_lab():
    canonical = _bundle("F-ENTERPRISE")
    fallback = _bundle("P-FOUNDER")
    final_project_fallback = _bundle("P-GRAB")

    assert canonical.evidence_sources == (
        "docs/career_workbench/story_engine/stories/_GOLD_REFERENCE_flairx_enterprise_wedge.md",
    )
    assert "prompt-owned context" not in canonical.evidence
    assert "prompt-owned context" in fallback.evidence
    assert "profile_maxing_lab" not in canonical.evidence
    assert "profile_maxing_lab" not in fallback.evidence
    assert "Rules for using proof units" not in final_project_fallback.evidence
    assert len(final_project_fallback.evidence) < 1_000


def test_prompt_contains_original_incumbent_ids_and_exact_text():
    bundle = _bundle()
    prompt = runner.build_prompt(bundle)

    assert "{{STORY_ID}}" not in prompt
    for record in bundle.incumbents:
        assert record.stable_id in prompt
        assert record.text in prompt


def test_response_schema_is_exact_and_checks_references():
    bundle = _bundle()
    payload = _valid_response(bundle)
    assert runner.validate_response(payload, bundle) == []

    payload["unexpected"] = True
    errors = runner.validate_response(payload, bundle)
    assert any("extra keys" in error for error in errors)

    payload.pop("unexpected")
    payload["incumbent_decisions"].pop()
    errors = runner.validate_response(payload, bundle)
    assert any("missing incumbents" in error for error in errors)


def test_tradeoff_is_a_valid_challenger_archetype():
    bundle = _bundle()
    payload = _valid_response(bundle)
    payload["challengers"][0]["archetype"] = "tradeoff"
    assert runner.validate_response(payload, bundle) == []


def test_every_structured_rule_dimension_is_required_for_each_challenger():
    bundle = _bundle()
    payload = _valid_response(bundle)
    payload["challengers"][0]["rulebook_checks"].pop("causal_closure")

    errors = runner.validate_response(payload, bundle)

    assert any("missing dimensions" in error and "causal_closure" in error for error in errors)


def test_accepted_challenger_cannot_fail_a_structured_rule_dimension():
    bundle = _bundle()
    payload = _valid_response(bundle)
    challenger = payload["challengers"][0]
    challenger["recommendation"] = "accept_challenger"
    challenger["rulebook_checks"]["single_story_spine"] = {
        "verdict": "fail",
        "reason": "The second clause belongs to a different causal path.",
    }

    errors = runner.validate_response(payload, bundle)

    assert any("cannot accept" in error and "single_story_spine" in error for error in errors)


def test_saved_opener_is_rejected_before_a_challenger_can_enter_review():
    bundle = _bundle()
    payload = _valid_response(bundle)
    payload["challengers"][0]["text"] = (
        "Saved a flagship account after an API blocker; shipped an unrelated "
        "marketplace channel and removed duplicate work."
    )

    errors = runner.validate_response(payload, bundle)

    assert any("FORBIDDEN_OR_WEAK_OPENER" in error and "saved" in error for error in errors)


def test_parse_response_rejects_markdown_wrapped_json():
    bundle = _bundle()
    raw = "```json\n" + json.dumps(_valid_response(bundle)) + "\n```"
    with pytest.raises(ValueError, match="not bare valid JSON"):
        runner.parse_response(raw, bundle)


def test_dry_run_writes_atomic_requests_and_manifest_without_api(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "AUDIT_ROOT", tmp_path)

    def forbidden_api(*_args):
        pytest.fail("dry run must not call the API")

    run_dir, results = runner.run_challenges(
        ["H-MONITORING-AI", "G-PRICING"],
        model="explicit-test-model",
        dry_run=True,
        workers=2,
        retries=0,
        run_id="dry-run-fixture",
        api_call=forbidden_api,
    )

    assert [result.story_id for result in results] == ["G-PRICING", "H-MONITORING"]
    assert all(result.status == "dry-run" for result in results)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == "explicit-test-model"
    assert manifest["requested_story_ids"] == ["H-MONITORING", "G-PRICING"]
    assert manifest["human_review_path"].endswith("HUMAN_REVIEW.md")
    assert len(list(run_dir.glob("*.request.json"))) == 2
    assert not list(run_dir.glob("*.response.json"))
    run_review = (run_dir / "HUMAN_REVIEW.md").read_text(encoding="utf-8")
    assert "G-PRICING" in run_review
    assert "H-MONITORING" in run_review
    assert "Cross-track value atoms differ" in run_review


def test_mocked_api_writes_validated_response_and_side_by_side_review(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "AUDIT_ROOT", tmp_path)
    bundle = _bundle("G-PRICING")

    def fake_api(_prompt, story_id):
        assert story_id == bundle.story_id
        return json.dumps(_valid_response(bundle))

    run_dir, results = runner.run_challenges(
        [bundle.story_id],
        model="explicit-test-model",
        dry_run=False,
        workers=1,
        retries=1,
        run_id="mocked-live-fixture",
        api_call=fake_api,
    )

    assert results[0].status == "complete"
    response = json.loads((run_dir / "g-pricing.response.json").read_text(encoding="utf-8"))
    assert response["story_id"] == bundle.story_id
    review = (run_dir / "g-pricing.review.md").read_text(encoding="utf-8")
    for record in bundle.incumbents:
        assert record.stable_id in review
        assert record.text in review
    assert "Proposed challenger" in review


def test_mocked_invalid_api_output_fails_closed_per_story(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "AUDIT_ROOT", tmp_path)

    run_dir, results = runner.run_challenges(
        ["G-PRICING"],
        model="explicit-test-model",
        dry_run=False,
        workers=1,
        retries=0,
        run_id="invalid-output-fixture",
        api_call=lambda _prompt, _story: "not json",
    )

    assert results[0].status == "failed"
    assert (run_dir / "g-pricing.error.json").exists()
    assert not (run_dir / "g-pricing.response.json").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["results"][0]["status"] == "failed"
    run_review = (run_dir / "HUMAN_REVIEW.md").read_text(encoding="utf-8")
    assert "[error](g-pricing.error.json)" in run_review


def test_resume_selector_uses_exact_ids_or_text_and_never_guesses(tmp_path):
    grouped = runner.group_causal_stories(runner.load_inventory())
    record = grouped["G-PRICING"][0]
    fixture = tmp_path / "resume.json"
    fixture.write_text(json.dumps({"variants": [record.stable_id]}), encoding="utf-8")
    assert runner.stories_for_resume(fixture, grouped) == ("G-PRICING",)

    unknown = tmp_path / "unknown.txt"
    unknown.write_text("Gojek product resume", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to guess"):
        runner.stories_for_resume(unknown, grouped)


def test_cli_requires_explicit_model_and_one_target():
    with pytest.raises(SystemExit):
        runner.parse_args(["--all"])
    with pytest.raises(SystemExit):
        runner.parse_args(["--model", "x"])
    args = runner.parse_args(["--model", "x", "--story", "G-PRICING", "--dry-run"])
    assert args.model == "x"
    assert args.story == ["G-PRICING"]
    assert args.dry_run


def test_api_key_loads_from_dotenv_without_printing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=fixture-secret\n", encoding="utf-8")

    assert runner.load_api_key({}) == "fixture-secret"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("workers", "retries", "message"),
    [(0, 0, "workers"), (runner.MAX_WORKERS + 1, 0, "workers"), (1, -1, "retries"), (1, runner.MAX_RETRIES + 1, "retries")],
)
def test_concurrency_and_retries_are_bounded(monkeypatch, tmp_path, workers, retries, message):
    monkeypatch.setattr(runner, "AUDIT_ROOT", tmp_path)
    with pytest.raises(ValueError, match=message):
        runner.run_challenges(
            ["G-PRICING"],
            model="explicit-test-model",
            dry_run=True,
            workers=workers,
            retries=retries,
            run_id="bounds",
        )
