"""Internal live checks for the combined runner; no message composition or sends."""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from discovery.scripts.run_bounded_discovery import ROOT, atomic_json, execute

OUTREACH = ROOT.parent / 'Outreach'


def browser_preflight(directory, run_id):
    worker = """from outreach.config import OutreachSettings
from outreach.services.linkedin import LinkedInScraper
from playwright.sync_api import sync_playwright
s=OutreachSettings()
LinkedInScraper(s).require_live_cdp_session()
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp(f'http://127.0.0.1:{s.linkedin_debug_port}',timeout=8000)
    assert b.contexts, 'No browser context'
print('Browser attachment verified')
"""
    command = [OUTREACH/'.venv/bin/python', '-c', worker]
    code = execute(command, deadline=time.time()+20,
                   log_path=directory/'browser-preflight.log', cwd=OUTREACH)
    recovered = False
    if code:
        # The existing launcher enforces exact profile and ownership checks.
        # An unowned listener is refused, never killed by this runner.
        environment = dict(os.environ)
        environment['RESUMEGEN_LINKEDIN_BROWSER_OWNER_TOKEN'] = run_id
        recovery = execute(['./discovery/scripts/ensure_chrome_9222.sh'],
            deadline=time.time()+45, log_path=directory/'browser-recovery.log', env=environment)
        if recovery == 0:
            code = execute(command, deadline=time.time()+20,
                log_path=directory/'browser-preflight.log', cwd=OUTREACH)
            recovered = code == 0
    result = {'status':'checked' if code == 0 else 'unavailable', 'recovered':recovered}
    atomic_json(directory/'browser-preflight.json', result)
    return result


def _artifact(log):
    paths = re.findall(r'^Artifact: (.+\.json)$', log.read_text(), re.M) if log.exists() else []
    if not paths:return None
    path = Path(paths[-1])
    return path if path.is_absolute() else OUTREACH/path


def refresh_relationships(directory):
    """Persist inbox reconciliation, then small rotating profile batches."""
    inbox_log = directory/'inbox-sync.log'
    code = execute([OUTREACH/'.venv/bin/python', OUTREACH/'main.py',
        'reconcile-linkedin-messages','--live','--apply','--deep','--include-seen','--limit','300'],
        deadline=time.time()+180, log_path=inbox_log, cwd=OUTREACH)
    results = {'inbox':{'returncode':code,'status':'checked' if code == 0 else 'unavailable',
                         'log':str(inbox_log),'artifact':str(_artifact(inbox_log) or '')}}
    queue_log = directory/'connections-queue.log'
    code = execute([OUTREACH/'.venv/bin/python', OUTREACH/'main.py',
        'build-linkedin-reconcile-queue','--max-age-days','365','--limit','1000'],
        deadline=time.time()+15, log_path=queue_log, cwd=OUTREACH)
    queue_path = _artifact(queue_log)
    queue = json.loads(queue_path.read_text()).get('results',[]) if code == 0 and queue_path and queue_path.exists() else None
    ledger = ROOT/'discovery/auto/checkpoints/connection-checks.json'
    checks = json.loads(ledger.read_text()) if ledger.exists() else {}
    pending = [] if queue is None else [r for r in queue if time.time()-checks.get(r['contact_id'],0)>20*3600]
    pending.sort(key=lambda r:checks.get(r['contact_id'],0))
    deadline = time.time()+120
    completed = 0; batches = []; failed = queue is None
    for start in range(0,len(pending),3):
        if time.time()+15 >= deadline:break
        batch = pending[start:start+3]
        packet = directory/f'connections-{start//3:03d}.json'
        atomic_json(packet, {'results':batch})
        log = packet.with_suffix('.log')
        code = execute([OUTREACH/'.venv/bin/python', OUTREACH/'main.py',
            'reconcile-linkedin','--live','--apply','--queue-artifact',packet,'--limit','3'],
            deadline=min(deadline,time.time()+60),log_path=log,cwd=OUTREACH)
        artifact = _artifact(log)
        successful = []
        if code == 0 and artifact and artifact.exists():
            for row in json.loads(artifact.read_text()).get('results',[]):
                if row.get('normalized_status') in {'connected','replied','pending','not_connected'}:
                    successful.append(row['contact_id'])
            for contact in successful:checks[contact] = time.time()
            atomic_json(ledger,checks)
        completed += len(successful)
        batches.append({'returncode':code,'checked':len(successful),'artifact':str(artifact or '')})
        atomic_json(directory/'connection-batches.json',{'batches':batches,'checked':completed})
        if code:failed=True;break
    deferred = len(pending)-completed
    results['connections'] = {'status':'unavailable' if failed else 'checked_bounded' if deferred else 'checked',
        'checked':completed,'deferred':deferred,'recently_checked':0 if queue is None else len(queue)-len(pending),
        'batches':batches}
    result = {'checked_at':datetime.now().astimezone().isoformat(),
        'status':'incomplete' if any(r['status']=='unavailable' for r in results.values()) else 'checked',
        'coverage':'Inbox scan capped at 300 threads. Pending profiles rotate in durable three-person batches; deferred checks remain explicit.',
        'results':results}
    atomic_json(directory/'relationship-sync.json',result)
    return result
