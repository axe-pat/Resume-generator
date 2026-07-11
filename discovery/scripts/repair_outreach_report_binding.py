#!/usr/bin/env python3
"""Rebind one terminal nightly summary to its existing Outreach report artifacts.

The command is preview-only unless ``--apply`` is supplied. It does not run the
nightly pipeline or Outreach report generation, and it never updates mutable
``daily_run_report`` mirrors.

Example:
    python discovery/scripts/repair_outreach_report_binding.py \
      --summary discovery/source_validation/20260711-150851-nightly-pipeline-summary.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTREACH_ROOT = ROOT.parent / "Outreach"
RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}$")


class RepairError(ValueError):
    """Raised when an existing report cannot be unambiguously rebound."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepairError(f"Could not read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RepairError(f"Expected a JSON object at {path}")
    return payload


def _resolve_pointer(value: object, *, outreach_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise RepairError("Required report artifact pointer is missing")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = outreach_root / path
    return path.resolve(strict=False)


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return left.resolve(strict=False) == right.resolve(strict=False)


def _is_within_existing_root(path: Path, root: Path) -> bool:
    for candidate in (path, *path.parents):
        try:
            if candidate.samefile(root):
                return True
        except OSError:
            continue
    return False


def _require_report_artifact(path: Path, *, reports_root: Path, label: str) -> None:
    if not path.is_file():
        raise RepairError(f"{label} does not exist: {path}")
    if not _is_within_existing_root(path, reports_root):
        raise RepairError(f"{label} is outside the Outreach reports directory: {path}")


def _bind_markdown(text: str, *, run_id: str, summary_artifact: Path) -> str:
    lines = text.splitlines()
    run_id_lines = [line for line in lines if line.startswith("- Run ID:")]
    if run_id_lines and run_id not in run_id_lines[0]:
        raise RepairError("Markdown report already carries a different run ID")
    if not run_id_lines:
        insert_at = next(
            (index + 1 for index, line in enumerate(lines) if line.startswith("- Created:")),
            min(2, len(lines)),
        )
        lines.insert(insert_at, f"- Run ID: `{run_id}`")
    for index, line in enumerate(lines):
        if line.startswith("- Report artifact:"):
            lines[index] = f"- Report artifact: `{summary_artifact}`"
            break
    return "\n".join(lines).rstrip() + "\n"


def _bind_html(text: str, *, run_id: str) -> str:
    if run_id in text:
        return text
    marker = "  </header>"
    if marker not in text:
        raise RepairError("HTML report has no header boundary for a run ID marker")
    return text.replace(
        marker,
        f"    <p>Run ID {run_id}</p>\n{marker}",
        1,
    )


def _bind_summary_markdown(
    text: str,
    *,
    summary_artifact: Path,
    markdown: Path,
    html: Path,
) -> str:
    replacements = {
        "- HTML report:": f"- HTML report: {html}",
        "- Markdown report:": f"- Markdown report: {markdown}",
        "- Report artifact:": f"- Report artifact: {summary_artifact}",
    }
    lines = text.splitlines()
    seen: set[str] = set()
    for index, line in enumerate(lines):
        for prefix, replacement in replacements.items():
            if line.startswith(prefix):
                lines[index] = replacement
                seen.add(prefix)
                break
    if seen != set(replacements):
        raise RepairError("Nightly summary Markdown is missing Outreach report pointer lines")
    return "\n".join(lines).rstrip() + "\n"


def build_repair_plan(
    *,
    summary_path: Path,
    outreach_root: Path = DEFAULT_OUTREACH_ROOT,
) -> dict[str, object]:
    summary_path = summary_path.expanduser().resolve(strict=True)
    outreach_root = outreach_root.expanduser().resolve(strict=True)
    reports_root = outreach_root / "workspace" / "reports"
    if not reports_root.is_dir():
        raise RepairError(f"Outreach reports directory does not exist: {reports_root}")

    summary = _load_json(summary_path)
    run_id = str(summary.get("run_id") or "").strip()
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RepairError("Nightly summary has no valid YYYYMMDD-HHMMSS run_id")
    if summary_path.name != f"{run_id}-nightly-pipeline-summary.json":
        raise RepairError("Nightly summary filename does not bind to its run_id")
    if str(summary.get("status") or "") not in {"completed", "failed"}:
        raise RepairError("Only a terminal completed or failed nightly run may be repaired")
    if not str(summary.get("completed_at") or "").strip():
        raise RepairError("Nightly summary is missing completed_at")

    report_meta = summary.get("outreach_daily_report")
    if not isinstance(report_meta, dict) or report_meta.get("returncode") != 0:
        raise RepairError("Nightly summary has no successful Outreach report result to rebind")

    source_json = _resolve_pointer(
        report_meta.get("summary_artifact"), outreach_root=outreach_root
    )
    source_markdown = source_json.with_suffix(".md")
    source_html = _resolve_pointer(
        report_meta.get("html_report_artifact"), outreach_root=outreach_root
    )
    for path, label in (
        (source_json, "Report JSON"),
        (source_markdown, "Exact report Markdown"),
        (source_html, "Exact report HTML"),
    ):
        _require_report_artifact(path, reports_root=reports_root, label=label)
    if source_json.stem != source_markdown.stem or source_json.stem != source_html.stem:
        raise RepairError("Existing JSON, Markdown, and HTML artifacts do not share one report stem")

    report_payload = _load_json(source_json)
    existing_run_id = str(report_payload.get("run_id") or "").strip()
    if existing_run_id and existing_run_id != run_id:
        raise RepairError("Existing report JSON carries a different run_id")
    if str(report_payload.get("report_mode") or "") != "run_scoped":
        raise RepairError("Existing report JSON is not run_scoped")
    if str(report_payload.get("since") or "") != str(summary.get("created_at") or ""):
        raise RepairError("Existing report JSON does not match the nightly run start")
    report_summary = _resolve_pointer(
        report_payload.get("nightly_summary"), outreach_root=outreach_root
    )
    if not _same_file(report_summary, summary_path):
        raise RepairError("Existing report JSON points to a different nightly summary")

    destination_json = source_json.parent / f"{run_id}-daily-run-report.json"
    destination_markdown = source_json.parent / f"{run_id}-daily-run-report.md"
    destination_html = source_html.parent / f"{run_id}-daily-run-report.html"
    report_payload["run_id"] = run_id
    destination_json_text = json.dumps(report_payload, indent=2, ensure_ascii=True) + "\n"
    destination_markdown_text = _bind_markdown(
        source_markdown.read_text(encoding="utf-8"),
        run_id=run_id,
        summary_artifact=destination_json,
    )
    destination_html_text = _bind_html(
        source_html.read_text(encoding="utf-8"), run_id=run_id
    )

    rebound_summary = json.loads(json.dumps(summary))
    rebound_report = rebound_summary["outreach_daily_report"]
    rebound_report["summary_artifact"] = str(destination_json)
    rebound_report["daily_report"] = str(destination_markdown)
    rebound_report["html_report_artifact"] = str(destination_html)
    rebound_report["html_report"] = str(destination_html)
    rebound_summary_text = json.dumps(rebound_summary, indent=2, ensure_ascii=True) + "\n"

    summary_markdown = summary_path.with_suffix(".md")
    summary_markdown_text = ""
    if summary_markdown.is_file():
        summary_markdown_text = _bind_summary_markdown(
            summary_markdown.read_text(encoding="utf-8"),
            summary_artifact=destination_json,
            markdown=destination_markdown,
            html=destination_html,
        )

    return {
        "run_id": run_id,
        "summary_path": summary_path,
        "summary_markdown": summary_markdown if summary_markdown_text else None,
        "source_json": source_json,
        "source_markdown": source_markdown,
        "source_html": source_html,
        "destination_json": destination_json,
        "destination_markdown": destination_markdown,
        "destination_html": destination_html,
        "destination_json_text": destination_json_text,
        "destination_markdown_text": destination_markdown_text,
        "destination_html_text": destination_html_text,
        "summary_text": rebound_summary_text,
        "summary_markdown_text": summary_markdown_text,
    }


def _atomic_write_if_changed(path: Path, text: str, *, mode_source: Path) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, mode_source.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_repair_plan(plan: dict[str, object]) -> None:
    artifact_pairs = (
        (plan["destination_json"], plan["destination_json_text"], plan["source_json"]),
        (
            plan["destination_markdown"],
            plan["destination_markdown_text"],
            plan["source_markdown"],
        ),
        (plan["destination_html"], plan["destination_html_text"], plan["source_html"]),
    )
    for path, text, _source in artifact_pairs:
        assert isinstance(path, Path) and isinstance(text, str)
        if path.is_file() and path.read_text(encoding="utf-8") != text:
            raise RepairError(f"Refusing to overwrite a different run-bound artifact: {path}")
    for path, text, source in artifact_pairs:
        assert isinstance(source, Path)
        _atomic_write_if_changed(path, text, mode_source=source)

    summary_markdown = plan.get("summary_markdown")
    summary_markdown_text = plan.get("summary_markdown_text")
    if isinstance(summary_markdown, Path) and isinstance(summary_markdown_text, str):
        _atomic_write_if_changed(
            summary_markdown, summary_markdown_text, mode_source=summary_markdown
        )
    summary_path = plan["summary_path"]
    summary_text = plan["summary_text"]
    assert isinstance(summary_path, Path) and isinstance(summary_text, str)
    _atomic_write_if_changed(summary_path, summary_text, mode_source=summary_path)


def _public_plan(plan: dict[str, object], *, mode: str) -> dict[str, object]:
    return {
        "mode": mode,
        "run_id": plan["run_id"],
        "summary": str(plan["summary_path"]),
        "source_artifacts": [
            str(plan["source_json"]),
            str(plan["source_markdown"]),
            str(plan["source_html"]),
        ],
        "run_bound_artifacts": [
            str(plan["destination_json"]),
            str(plan["destination_markdown"]),
            str(plan["destination_html"]),
        ],
        "latest_mirrors_touched": False,
        "pipeline_or_report_command_run": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--outreach-root", type=Path, default=DEFAULT_OUTREACH_ROOT)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create the run-bound copies and update only the selected summary pointers.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = build_repair_plan(
            summary_path=args.summary,
            outreach_root=args.outreach_root,
        )
        if args.apply:
            apply_repair_plan(plan)
        print(json.dumps(_public_plan(plan, mode="applied" if args.apply else "preview"), indent=2))
        return 0
    except RepairError as exc:
        print(f"Report binding repair refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
