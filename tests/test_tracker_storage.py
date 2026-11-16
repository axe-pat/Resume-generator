import hashlib

import pandas as pd
import pytest

from shared.tracker_storage import revision, save_atomically


def workbook(path, count=2):
    frame = pd.DataFrame({'id': [str(i) for i in range(count)]})
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name='Jobs', index=False)
        pd.DataFrame({'cached': ['retained']}).to_excel(writer, sheet_name='ReviewCache', index=False)
    return frame


def test_interrupted_write_leaves_previous_tracker_and_other_sheets_intact(tmp_path):
    path = tmp_path / 'jobs.xlsx'
    frame = workbook(path)
    original = path.read_bytes()
    def fail(staged):
        staged.write_bytes(b'partial file')
        raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError, match='interrupted'):
        save_atomically(path, frame, fail)
    assert path.read_bytes() == original
    assert pd.read_excel(path, sheet_name='ReviewCache')['cached'].iloc[0] == 'retained'


def test_stale_producer_cannot_replace_newer_tracker(tmp_path):
    path = tmp_path / 'jobs.xlsx'
    frame = workbook(path)
    frame.attrs['tracker_revision'] = revision(path.read_bytes())
    workbook(path, 3)
    current = path.read_bytes()
    with pytest.raises(RuntimeError, match='changed after'):
        save_atomically(path, frame, lambda staged: None)
    assert path.read_bytes() == current


def test_unreadable_tracker_is_not_treated_as_empty(tmp_path, monkeypatch):
    from discovery.auto import pipeline
    path = tmp_path / 'jobs.xlsx'
    path.write_bytes(b'incomplete workbook')
    monkeypatch.setattr(pipeline, 'JOBS_XLSX', path)
    with pytest.raises(RuntimeError, match='unreadable tracker as empty'):
        pipeline.load_jobs()


def test_large_unexplained_row_loss_is_refused(tmp_path):
    path = tmp_path / 'jobs.xlsx'
    workbook(path, 200)
    with pytest.raises(RuntimeError, match='half'):
        save_atomically(path, pd.DataFrame({'id': ['1']}), lambda staged: None)


def test_preserving_queue_swap_retains_previous_and_generated_files(tmp_path, monkeypatch):
    from discovery.scripts import refresh_current_apply_queue as queue
    root = tmp_path / 'queues'
    current = root / 'current_apply_queue'
    current.mkdir(parents=True)
    (current / 'resume.pdf').write_bytes(b'generated resume')
    previous = root / '.current_apply_queue_prev'
    previous.mkdir()
    (previous / 'older.docx').write_bytes(b'older generated resume')
    staged = root / 'staging'
    staged.mkdir()
    (staged / 'priority_order.json').write_text('[]')
    monkeypatch.setattr(queue, 'QUEUE_DIR', current)
    monkeypatch.setattr(queue, 'APPLY_QUEUES_DIR', root)
    monkeypatch.setattr(queue, 'ARCHIVE_DIR', tmp_path / 'archive')
    queue._swap_queue(staged, preserve_existing=True)
    assert (previous / 'older.docx').read_bytes() == b'older generated resume'
    saved = list((tmp_path / 'archive/queue_refresh_backups').glob('*/resume.pdf'))
    assert len(saved) == 1 and saved[0].read_bytes() == b'generated resume'
    assert (current / 'priority_order.json').is_file()
