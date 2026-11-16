"""Atomic workbook replacement, conflict detection, and immutable recovery copies."""
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def revision(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_atomically(path: Path, frame, write_staged) -> None:
    import openpyxl
    lock = path.with_suffix('.write.lock')
    with lock.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        original = path.read_bytes() if path.exists() else b''
        expected = frame.attrs.get('tracker_revision')
        if expected and revision(original) != expected:
            raise RuntimeError('Tracker changed after it was read; reload before saving.')
        if original:
            workbook = openpyxl.load_workbook(path, read_only=True)
            before = workbook['Jobs'].max_row - 1
            workbook.close()
            if before > 100 and len(frame) < before / 2 and not frame.attrs.get('allow_tracker_reduction'):
                raise RuntimeError('Refusing a tracker write that would remove more than half of the saved rows.')
        fd, name = tempfile.mkstemp(prefix='.jobs-write-', suffix='.xlsx', dir=path.parent)
        os.close(fd)
        staged = Path(name)
        try:
            if original:
                staged.write_bytes(original)
            else:
                staged.unlink()
            write_staged(staged)
            workbook = openpyxl.load_workbook(staged, read_only=True)
            if workbook['Jobs'].max_row != len(frame) + 1:
                workbook.close()
                raise RuntimeError('Staged tracker row count does not match the proposed update.')
            workbook.close()
            if original:
                backups = path.parent / '.tracker_backups'
                backups.mkdir(exist_ok=True)
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                (backups / f'jobs-{stamp}-{uuid.uuid4().hex[:8]}.xlsx').write_bytes(original)
            os.replace(staged, path)
            frame.attrs['tracker_revision'] = revision(path.read_bytes())
        finally:
            staged.unlink(missing_ok=True)
