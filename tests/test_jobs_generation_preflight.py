import json

from jobs import _generation_target_input, _preflight_generation_targets
from shared.queue_preflight import PreflightStatus


def _healthy_jd() -> str:
    block = """
About the role
This product role owns customer discovery, data analysis, prototyping, and delivery.
What you'll do
You will interview customers, define requirements, partner with engineering and design,
measure adoption, and adjust the roadmap when evidence changes the priority.
Qualifications
Strong analytical judgment, communication, and experience shipping technical products.
"""
    return (block + block).strip()


def _target(tmp_path, key: str, title: str, jd: str):
    app_dir = tmp_path / key
    app_dir.mkdir()
    (app_dir / "jd.txt").write_text(jd, encoding="utf-8")
    (app_dir / "metadata.json").write_text(
        json.dumps({"id": key, "role_title": title, "lane": "B"}),
        encoding="utf-8",
    )
    return {"id": key, "company": key, "app_dir": str(app_dir)}


def test_generation_target_input_uses_stable_metadata_title_and_id(tmp_path):
    target = _target(tmp_path, "42", "Technical Product Manager", _healthy_jd())
    queue_input = _generation_target_input(target)

    assert queue_input is not None
    assert queue_input.key == "42"
    assert queue_input.role_title == "Technical Product Manager"
    assert queue_input.metadata["lane"] == "B"


def test_batch_generation_preflight_detects_cross_target_jd_collision(tmp_path):
    shared_jd = _healthy_jd()
    targets = [
        _target(tmp_path, "mba", "MBA Leadership Associate", shared_jd),
        _target(tmp_path, "systems", "Enterprise Systems Analyst", shared_jd),
    ]

    report = _preflight_generation_targets(targets)

    assert report.status is PreflightStatus.BLOCK
    duplicate = [
        record for record in report.blockers
        if record.code == "JD_DUPLICATE_DIFFERENT_TITLES"
    ]
    assert len(duplicate) == 1
    assert set(duplicate[0].job_keys) == {"mba", "systems"}
