"""Reconstruct the tracker from its preserved backup and later saved row evidence."""
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.discovery_identity import canonical_listing_url


def restore():
    current = ROOT / 'discovery/jobs.xlsx'
    base = ROOT / 'discovery/jobs.xlsx.pre-12twenty-poc.bak'
    prefix = ROOT / 'discovery/source_validation/20261105-tracker-restoration'
    original = pd.read_excel(io.BytesIO(base.read_bytes()), sheet_name='Jobs', dtype=str).fillna('')
    columns = list(original.columns)
    rows = {str(r['id']): dict(r) for _, r in original.iterrows()}
    protected_applied = {key for key, row in rows.items() if row['status'] == 'applied'}
    replay = ROOT / 'discovery/source_validation/20260917-083844-discovery-2027-existing-replay.json'
    for row in json.loads(replay.read_text())['rows']:
        old = rows.get(str(row.get('id')))
        if old and canonical_listing_url(old.get('url', '')) == canonical_listing_url(row.get('url', '')):
            for key in ['lane', 'deadline', 'deadline_source', 'everify_status', 'sponsorship_flag', 'classification', 'reject_reason']:
                if key in row:
                    old[key] = row[key]
    for path in sorted((ROOT / 'discovery/auto/logs').glob('*scored*2026-*.json'), key=lambda p: p.stat().st_mtime):
        if path.name.split('2026-')[-1][:5] < '09-12':
            continue
        try:
            payload = json.loads(path.read_text())
        except ValueError:
            continue
        for row in payload.get('jobs', []):
            try:
                number = int(row.get('id') or 0)
            except (TypeError, ValueError):
                continue
            if number > 4111 and number != 4133 and row.get('decision') == 'Proceed':
                rows[str(number)] = {**rows.get(str(number), {}), **{key: row.get(key, '') for key in columns}}
    updated = 0
    for path in sorted((ROOT / 'apps').glob('**/metadata.json'), key=lambda p: p.stat().st_mtime):
        if any(part in str(path) for part in ['/runs/', '/stale_apply_queues/', '/discovery_runs/']):
            continue
        row = json.loads(path.read_text())
        key, url = str(row.get('id') or ''), canonical_listing_url(row.get('url', ''))
        if not key or not url or (key == '1' and '4476871695' in url):
            continue
        old = rows.get(key)
        if old and canonical_listing_url(old.get('url', '')) != url:
            continue
        if not old:
            if key not in ['4112', '4113']:
                continue
            old = rows[key] = {column: '' for column in columns}
            old['id'] = key
        for column, value in row.items():
            if column in columns:
                if column == 'status' and (key in protected_applied or old.get('status') == 'generated' and value == 'queued'):
                    continue
                old[column] = value
        if (path.parent / 'jd.txt').is_file() and not old.get('jd_text'):
            old['jd_text'] = (path.parent / 'jd.txt').read_text()
        if old.get('status') in ['generated', 'applied', 'promoted']:
            old['folder_path'] = str(path.parent)
        updated += 1
    delta = json.loads((ROOT / 'discovery/auto/logs/linkedin_live_scored_2026-11-05_204956.json').read_text())['jobs'][0]
    delta = {column: delta.get(column, '') for column in columns}
    delta['id'] = str(max(map(int, rows)) + 1)
    rows[delta['id']] = delta
    with tarfile.open(ROOT / 'discovery/source_validation/20261105-pre-completion-queue.tar.gz') as archive:
        for member in archive.getmembers():
            if member.name.endswith('/metadata.json'):
                row = json.load(archive.extractfile(member))
                key = str(row.get('id') or '')
                if key in rows:
                    rows[key].update({column: value for column, value in row.items() if column in columns})
    frame = pd.DataFrame(rows.values()).reindex(columns=columns).fillna('')
    print('RECOVERED', len(frame), 'base', len(original), 'metadata', updated, flush=True)
    print('KNOWN STATES', [(key, rows[key]['status']) for key in ['4034', '4081']], flush=True)
    assert not frame['id'].duplicated().any()
    assert len(frame) >= len(original) + 24
    assert rows['4081']['status'] == 'applied'
    assert rows['4034']['status'] == 'generated'
    candidate = prefix.with_suffix('.candidate.xlsx')
    shutil.copy2(current, candidate)
    with pd.ExcelWriter(candidate, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        frame.to_excel(writer, sheet_name='Jobs', index=False)
    assert len(pd.read_excel(candidate, sheet_name='Jobs')) == len(frame)
    candidate.replace(current)
    prefix.with_suffix('.json').write_text(json.dumps({
        'base_backup': str(base), 'base_rows': len(original), 'restored_rows': len(frame),
        'metadata_updates': updated, 'delta_id': delta['id'],
        'source': 'Historical backup plus later scored artifacts and saved queue metadata',
        'known_checks': {'Solace': 'applied', 'Momentum': 'generated'},
    }, indent=2))
    return frame


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if not args.write:
        parser.error('Emergency reconstruction requires --write; never use this during a normal discovery run.')
    if len(pd.read_excel(ROOT / 'discovery/jobs.xlsx', sheet_name='Jobs')) != 1:
        parser.error('Refusing reconstruction: the tracker is not the one-row failure state this recovery was designed for.')
    restore()
