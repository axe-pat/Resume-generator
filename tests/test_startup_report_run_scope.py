from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "discovery" / "scripts" / "build_startup_source_report.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("startup_report_scope_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _artifact(path: Path, company: str) -> None:
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "organization_name": company,
                        "source_kind": "yc_directory",
                        "company_url": f"https://example.test/{company}",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_relationship_loader_rejects_latest_artifact_from_before_run(tmp_path: Path) -> None:
    module = _load_script()
    stale = tmp_path / "20260709-discover-yc_sf_bay_hiring.json"
    _artifact(stale, "Stale Co")
    os.utime(stale, (100, 100))

    items, artifacts = module._load_relationship_targets(
        artifacts_dir=tmp_path,
        source_ids=("yc_sf_bay_hiring",),
        limit_per_source=15,
        artifact_since_epoch=200,
    )

    assert items == []
    assert artifacts["yc_sf_bay_hiring"]["status"] == "missing"


def test_relationship_loader_uses_artifact_written_after_run_cutoff(tmp_path: Path) -> None:
    module = _load_script()
    current = tmp_path / "20260710-discover-yc_sf_bay_hiring.json"
    _artifact(current, "Current Co")
    os.utime(current, (300, 300))

    items, artifacts = module._load_relationship_targets(
        artifacts_dir=tmp_path,
        source_ids=("yc_sf_bay_hiring",),
        limit_per_source=15,
        artifact_since_epoch=200,
    )

    assert [item["organization_name"] for item in items] == ["Current Co"]
    assert artifacts["yc_sf_bay_hiring"]["artifact"] == str(current)
