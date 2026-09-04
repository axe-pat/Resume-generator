import os
from pathlib import Path

import run_app


def _write_at(path: Path, payload: bytes, timestamp: float) -> None:
    path.write_bytes(payload)
    os.utime(path, (timestamp, timestamp))


def test_rename_latest_pair_never_mixes_independently_newest_extensions(tmp_path):
    _write_at(tmp_path / "older_jd_r9.0.docx", b"paired-docx", 10)
    _write_at(tmp_path / "older_jd_r9.0.pdf", b"paired-pdf", 11)
    _write_at(tmp_path / "newer-docx_jd_r8.0.docx", b"orphan-docx", 30)
    _write_at(tmp_path / "newer-pdf_jd_r7.0.pdf", b"orphan-pdf", 40)

    docx, pdf = run_app._rename_latest_pair(tmp_path, "_jd", "resume_2099-01-01")

    assert docx == tmp_path / "resume_2099-01-01_r9.0.docx"
    assert pdf == tmp_path / "resume_2099-01-01_r9.0.pdf"
    assert docx.read_bytes() == b"paired-docx"
    assert pdf.read_bytes() == b"paired-pdf"
    assert (tmp_path / "newer-docx_jd_r8.0.docx").read_bytes() == b"orphan-docx"
    assert (tmp_path / "newer-pdf_jd_r7.0.pdf").read_bytes() == b"orphan-pdf"


def test_rename_latest_pair_fails_closed_without_common_stem(tmp_path):
    (tmp_path / "one_jd_r9.0.docx").write_bytes(b"docx")
    (tmp_path / "two_jd_r9.0.pdf").write_bytes(b"pdf")

    assert run_app._rename_latest_pair(tmp_path, "_jd", "resume_2099-01-01") == (
        None,
        None,
    )
