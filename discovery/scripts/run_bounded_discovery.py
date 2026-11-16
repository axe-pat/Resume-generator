#!/usr/bin/env python3
"""Local discovery supervisor: deadline, per-stage resume and unconditional report."""
import argparse
import fcntl
import hashlib
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import re

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / 'venv/bin/python'

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, default=str) + '\n')
    temp.replace(path)

def execute(command, *, deadline, log_path, cwd=None):
    """Kill the whole child group on expiry, including browser/scorer children."""
    remaining = deadline - time.time()
    if remaining <= 0:
        return 124
    with log_path.open('a') as output:
        proc = subprocess.Popen([str(x) for x in command], cwd=cwd or ROOT,
                                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while proc.poll() is None:
                if time.time() >= deadline:
                    return 124
                time.sleep(min(.2, max(deadline-time.time(), 0)))
            return proc.returncode
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()

def supervise(stages, *, directory, minutes, resume=False):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'state.json'
    state = json.loads(path.read_text()) if resume and path.exists() else {'stages': {}}
    signature = hashlib.sha256((ROOT/'shared/discovery_search_policy.py').read_bytes()).hexdigest()
    policy_changed = state.get('policy_signature') not in {None, signature}
    state['policy_signature'] = signature
    finish = state.get('deadline_epoch', time.time()+minutes*60) if resume else time.time()+minutes*60
    reserve = min(300, minutes*60*.15)
    state.update(status='running', deadline_epoch=finish)
    state.pop('completed_at',None)
    atomic_json(path, state)
    try:
        inputs_changed = policy_changed
        for name, command, cap in stages:
            previous = state['stages'].get(name, {})
            dependent = name in {'hydrate', 'review'} and inputs_changed
            if previous.get('returncode') == 0 and previous.get('command') == list(map(str, command)) and not dependent and not (policy_changed and name=='linkedin'):
                continue
            end = min(finish-reserve, time.time()+cap)
            state['stages'][name] = {'status': 'running', 'command': list(map(str, command))}
            atomic_json(path, state)
            try:
                code = execute(command, deadline=end, log_path=directory/f'{name}.log')
            except OSError as exc:
                code = 127
                state['stages'][name]['error'] = str(exc)
            state['stages'][name].update(returncode=code, status='completed' if code==0 else 'deferred_or_failed')
            inputs_changed = True
            atomic_json(path, state)
    finally:
        # Discovery's report is independent of resume generation and outbound work.
        command = [PYTHON, 'discovery/scripts/build_daily_action_queue.py', '--report-stage', 'post_score']
        review_log=directory/'review.log'
        paths=re.findall(r'^Scored artifact: (.+)$',review_log.read_text(),re.M)if review_log.exists()else[]
        exact=Path(paths[-1])if paths and Path(paths[-1]).is_file()else directory/'empty-scored.json'
        if not exact.exists():atomic_json(exact,{'jobs':[],'scored':0})
        command += ['--scored-artifact',exact]
        code = execute(command, deadline=finish, log_path=directory/'publish.log')
        state['publication_returncode'] = code
        gaps = any(s.get('returncode') != 0 for s in state['stages'].values())
        state['coverage'] = 'Bounded source scope only; retained candidates have review outcomes or explicit gaps. This does not certify exhaustive market coverage.'
        state['status'] = 'publication_failed' if code else 'finished_with_gaps'if gaps else'finished'
        state['completed_at'] = datetime.now().isoformat()
        atomic_json(path, state)
    return state

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window', choices=['24h','7d'], default='24h')
    p.add_argument('--run-id', default=datetime.now().strftime('%Y%m%d-%H%M%S'))
    p.add_argument('--resume', action='store_true')
    p.add_argument('--saved-only', action='store_true', help='Publish saved inputs without new source calls.')
    p.add_argument('--include-twelvetwenty',action='store_true',help='Opt in to the repeatedly blocked campus portal.')
    p.add_argument('--legacy-linkedin',action='store_true',help='Use the prior split capture/hydration path for comparison.')
    for source in ['linkedin','handshake','jobspy','startup-apply']:
        p.add_argument('--skip-'+source,action='store_true')
    args = p.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.run_id):
        p.error('run-id must contain letters, digits, hyphens or underscores')
    weekly = args.window == '7d'
    run_directory=ROOT/'discovery/auto/checkpoints'/args.run_id
    stages = [] if args.saved_only else [
        ('linkedin', [PYTHON,'discovery/scripts/run_linkedin_streamed.py','--window',args.window,'--run-dir',run_directory/'linkedin','--minutes','43'if weekly else'12','--max-new-jds','75'if weekly else'25','--resume'], 2585 if weekly else 725),
        ('handshake', ['./discovery/scripts/run_handshake_discovery.sh',args.window],360 if weekly else 120),
        ('jobspy', [PYTHON,'discovery/scripts/fetch_jobspy_breadth.py','--hours-old','168' if weekly else '24','--results','30','--query-index','39','--query-index','41','--query-index','51'],300),
        ('startup', [PYTHON,'discovery/auto/startup_apply_pipeline.py','--limit-companies','10','--limit-jobs','15'],180),
    ]
    if not args.saved_only:
        if args.include_twelvetwenty:
            stages.append(('twelvetwenty',['/usr/bin/env','TWELVETWENTY_SCORE=0','./discovery/scripts/run_twelvetwenty_discovery.sh',args.window],60))
        if args.legacy_linkedin:
            stages[0]=('linkedin',[PYTHON,'discovery/scripts/run_linkedin_targeted.py','--window',args.window,'--capture-only','--pages','1','--limit-per-search','25'],1080 if weekly else 480)
            stages.append(('hydrate',[PYTHON,'discovery/scripts/hydrate_saved_discovery.py','--window',args.window],1500 if weekly else 600))
            stages.append(('review',[PYTHON,'discovery/scripts/review_saved_discovery.py','--window',args.window],480 if weekly else 300))
        else:
            stages.append(('review',[PYTHON,'discovery/scripts/review_run_discovery.py','--run-dir',run_directory,'--minutes','8'if weekly else'5'],490 if weekly else 310))
    skipped={name for name,flag in [('linkedin',args.skip_linkedin),('handshake',args.skip_handshake),('jobspy',args.skip_jobspy),('startup',args.skip_startup_apply)]if flag}
    stages=[s for s in stages if s[0]not in skipped and not(s[0]=='hydrate'and args.skip_linkedin)]
    lock_path = ROOT/'discovery/auto/checkpoints/.bounded-discovery.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another bounded discovery run is already active.')
            return 75
        state = supervise(stages, directory=ROOT/'discovery/auto/checkpoints'/args.run_id,
                          minutes=90 if weekly else 30, resume=args.resume)
    print(json.dumps(state, indent=2))
    # Compatibility contract consumed by the existing combined nightly runner.
    publication=run_directory/'publish.log'
    outputs=re.findall(r'^Wrote JSON: (.+)$',publication.read_text(),re.M)if publication.exists()else[]
    metrics=ROOT/'discovery/source_validation'/f'{args.run_id}-source-run-metrics.json'
    atomic_json(metrics,{'run_id':args.run_id,'sources':{name:{'status':'ran'if row.get('returncode')==0 else'failed','returncode':row.get('returncode')}for name,row in state['stages'].items()}})
    atomic_json(ROOT/'discovery/source_validation'/f'{args.run_id}-daily-engine-run-manifest.json',{'run_id':args.run_id,'status':state['status'],'source_metrics':str(metrics),'action_queue':outputs[-1]if outputs else'','bounded_state':str(run_directory/'state.json')})
    return 0 if state['status']=='finished' else 2

if __name__ == '__main__':
    raise SystemExit(main())
