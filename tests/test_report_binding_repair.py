from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "discovery" / "scripts" / "repair_outreach_report_binding.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("report_binding_repair_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_binding_repair_is_preview_first_exact_and_idempotent(
    tmp_path: Path, capsys
) -> None:
    module = _load_script()
    run_id = "20260711-150851"
    resume_root = tmp_path / "ResumeGenerator v1"
    validation = resume_root / "discovery" / "source_validation"
    validation.mkdir(parents=True)
    outreach = tmp_path / "Outreach"
    reports = outreach / "workspace" / "reports"
    html_reports = reports / "daily_html"
    html_reports.mkdir(parents=True)

    old_stem = "20260711-173446-daily-run-report"
    old_json = reports / f"{old_stem}.json"
    old_markdown = reports / f"{old_stem}.md"
    old_html = html_reports / f"{old_stem}.html"
    latest_markdown = reports / "daily_run_report.md"
    latest_html = html_reports / "daily_run_report.html"
    summary_path = validation / f"{run_id}-nightly-pipeline-summary.json"
    summary_markdown = summary_path.with_suffix(".md")
    created_at = "2026-07-11T15:08:51"

    report_payload = {
        "created_at": "2026-07-11T12:04:46+00:00",
        "report_mode": "run_scoped",
        "since": created_at,
        "nightly_summary": str(summary_path),
        "run_status": "failed_or_incomplete",
        "track_2_execution": {"status": "partial_failed"},
    }
    old_json.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    old_markdown.write_text(
        "\n".join(
            [
                "# Outreach Daily Run Report",
                "",
                "- Created: `2026-07-11T12:04:46+00:00`",
                "- Run status: `failed_or_incomplete`",
                f"- Report artifact: `{old_json}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    old_html.write_text(
        "<html>\n<body>\n  <header>\n    <p>Mode run_scoped</p>\n  </header>\n</body>\n</html>\n",
        encoding="utf-8",
    )
    latest_markdown.write_text("LATEST MARKDOWN SENTINEL\n", encoding="utf-8")
    latest_html.write_text("LATEST HTML SENTINEL\n", encoding="utf-8")
    summary = {
        "run_id": run_id,
        "created_at": created_at,
        "completed_at": "2026-07-11T17:34:43",
        "status": "completed",
        "failures": [],
        "outreach_daily_report": {
            "returncode": 0,
            "summary_artifact": str(old_json),
            "daily_report": str(latest_markdown),
            "html_report_artifact": str(old_html),
            "html_report": str(latest_html),
        },
    }
    original_summary_text = json.dumps(summary, indent=2) + "\n"
    summary_path.write_text(original_summary_text, encoding="utf-8")
    summary_markdown.write_text(
        "\n".join(
            [
                "# Nightly Pipeline Summary",
                "",
                "## Outreach Daily Report",
                "",
                f"- HTML report: {latest_html}",
                f"- Markdown report: {latest_markdown}",
                f"- Report artifact: {old_json}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    original_old_json = old_json.read_text(encoding="utf-8")
    original_old_markdown = old_markdown.read_text(encoding="utf-8")
    original_old_html = old_html.read_text(encoding="utf-8")
    bound_json = reports / f"{run_id}-daily-run-report.json"
    bound_markdown = reports / f"{run_id}-daily-run-report.md"
    bound_html = html_reports / f"{run_id}-daily-run-report.html"

    preview_returncode = module.main(
        ["--summary", str(summary_path), "--outreach-root", str(outreach)]
    )
    preview = json.loads(capsys.readouterr().out)

    assert preview_returncode == 0
    assert preview["mode"] == "preview"
    assert preview["latest_mirrors_touched"] is False
    assert preview["pipeline_or_report_command_run"] is False
    assert not bound_json.exists()
    assert summary_path.read_text(encoding="utf-8") == original_summary_text

    apply_returncode = module.main(
        [
            "--summary",
            str(summary_path),
            "--outreach-root",
            str(outreach),
            "--apply",
        ]
    )
    applied = json.loads(capsys.readouterr().out)

    assert apply_returncode == 0
    assert applied["mode"] == "applied"
    rebound_report = json.loads(bound_json.read_text(encoding="utf-8"))
    assert rebound_report["run_id"] == run_id
    assert rebound_report["run_status"] == "failed_or_incomplete"
    assert rebound_report["track_2_execution"]["status"] == "partial_failed"
    assert f"Run ID: `{run_id}`" in bound_markdown.read_text(encoding="utf-8")
    assert f"Report artifact: `{bound_json}`" in bound_markdown.read_text(
        encoding="utf-8"
    )
    assert f"Run ID {run_id}" in bound_html.read_text(encoding="utf-8")
    rebound_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rebound_pointers = rebound_summary["outreach_daily_report"]
    assert rebound_pointers["summary_artifact"] == str(bound_json)
    assert rebound_pointers["daily_report"] == str(bound_markdown)
    assert rebound_pointers["html_report_artifact"] == str(bound_html)
    assert rebound_pointers["html_report"] == str(bound_html)
    assert rebound_summary["status"] == "completed"
    assert rebound_summary["failures"] == []
    assert f"- HTML report: {bound_html}" in summary_markdown.read_text(encoding="utf-8")
    assert f"- Markdown report: {bound_markdown}" in summary_markdown.read_text(
        encoding="utf-8"
    )

    assert latest_markdown.read_text(encoding="utf-8") == "LATEST MARKDOWN SENTINEL\n"
    assert latest_html.read_text(encoding="utf-8") == "LATEST HTML SENTINEL\n"
    assert old_json.read_text(encoding="utf-8") == original_old_json
    assert old_markdown.read_text(encoding="utf-8") == original_old_markdown
    assert old_html.read_text(encoding="utf-8") == original_old_html

    assert module.main(
        [
            "--summary",
            str(summary_path),
            "--outreach-root",
            str(outreach),
            "--apply",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "applied"
