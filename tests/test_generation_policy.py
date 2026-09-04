import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import jobs
import run_app


class GenerationPolicyTests(unittest.TestCase):
    def test_lean_pm_skips_strategy(self):
        policy = run_app._choose_cost_policy(
            fit_score=6.2,
            requested_strategy=True,
            requested_rewrite=True,
            requested_score=True,
            requested_fix=True,
            requested_qc=True,
            default_model="claude-sonnet-4-6",
            smart_cost=True,
            role_track_hint="pm",
        )

        self.assertEqual(policy["tier"], "lean")
        self.assertFalse(policy["run_strategy"])
        self.assertFalse(policy["run_rewrite"])
        self.assertFalse(policy["run_score"])

    def test_lean_nonpm_keeps_cheap_strategy(self):
        policy = run_app._choose_cost_policy(
            fit_score=6.2,
            requested_strategy=True,
            requested_rewrite=True,
            requested_score=True,
            requested_fix=True,
            requested_qc=True,
            default_model="claude-sonnet-4-6",
            smart_cost=True,
            role_track_hint="nonpm",
        )

        self.assertEqual(policy["tier"], "lean")
        self.assertTrue(policy["run_strategy"])
        self.assertEqual(policy["strategy_model"], run_app.HAIKU_MODEL)
        self.assertFalse(policy["run_rewrite"])
        self.assertFalse(policy["run_score"])

    def test_full_quality_uses_cheap_strategy_and_premium_score_gate(self):
        standard_full = run_app._choose_cost_policy(
            fit_score=8.2,
            requested_strategy=True,
            requested_rewrite=True,
            requested_score=True,
            requested_fix=True,
            requested_qc=True,
            default_model="claude-sonnet-4-6",
            smart_cost=True,
            role_track_hint="pm",
        )
        premium_full = run_app._choose_cost_policy(
            fit_score=8.6,
            requested_strategy=True,
            requested_rewrite=True,
            requested_score=True,
            requested_fix=True,
            requested_qc=True,
            default_model="claude-sonnet-4-6",
            smart_cost=True,
            role_track_hint="pm",
        )

        self.assertEqual(standard_full["strategy_model"], run_app.HAIKU_MODEL)
        self.assertEqual(standard_full["score_model"], run_app.HAIKU_MODEL)
        self.assertEqual(premium_full["strategy_model"], run_app.HAIKU_MODEL)
        self.assertEqual(premium_full["score_model"], "claude-sonnet-4-6")

    def test_budget_mode_skips_rewrite_below_full_quality_threshold(self):
        args = SimpleNamespace(budget_mode=True, no_rewrite=False)

        self.assertTrue(jobs._should_budget_skip_rewrite({"fit_score": 7.7}, args))
        self.assertFalse(jobs._should_budget_skip_rewrite({"fit_score": 7.8}, args))
        self.assertFalse(jobs._should_budget_skip_rewrite({"fit_score": 8.2}, args))

    def test_no_smart_cost_disables_budget_rewrite_cut(self):
        args = SimpleNamespace(
            budget_mode=True,
            no_rewrite=False,
            no_smart_cost=True,
        )

        self.assertFalse(jobs._should_budget_skip_rewrite({"fit_score": 6.0}, args))

    def test_role_router_detects_nonpm_titles_but_preserves_product_titles(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "metadata.json").write_text(
                json.dumps({"role_title": "Corporate Strategy Intern"}),
                encoding="utf-8",
            )
            nonpm = run_app._infer_role_track(app_dir, "", "", "auto")
            self.assertEqual(nonpm["effective_track"], "nonpm")
            self.assertEqual(nonpm["source"], "cheap-router")

            (app_dir / "metadata.json").write_text(
                json.dumps({"role_title": "Product Management Intern, End User Experience"}),
                encoding="utf-8",
            )
            pm = run_app._infer_role_track(app_dir, "", "", "auto")
            self.assertEqual(pm["effective_track"], "pm")
            self.assertEqual(pm["source"], "cheap-router")

            explicit_pm = run_app._infer_role_track(app_dir, "", "", "pm")
            self.assertEqual(explicit_pm["effective_track"], "pm")
            self.assertEqual(explicit_pm["source"], "explicit")

    def test_role_router_keeps_embedded_product_strategy_work_on_pm_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "metadata.json").write_text(
                json.dumps({"role_title": "Intern - Product Strategy"}),
                encoding="utf-8",
            )
            jd = (
                "Join the product team, run user research and usability tests, "
                "then present recommendations to people making product decisions."
            )
            routed = run_app._infer_role_track(app_dir, jd, "", "auto")
            self.assertEqual(routed["effective_track"], "pm")
            self.assertTrue(routed["embedded_product_strategy"])


if __name__ == "__main__":
    unittest.main()
