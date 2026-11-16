"""Review eligible saved JDs; the parent supervisor supplies the hard deadline."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def main():
    from discovery.scripts.audit_discovery_coverage import build_audit
    from discovery.auto.linkedin_live import score_from_raw_artifacts, DEFAULT_MODEL
    p = argparse.ArgumentParser()
    p.add_argument('--window', choices=['24h','7d'], default='24h')
    p.add_argument('--input', type=Path, help='Frozen saved-JD input; do not collect or rebuild the audit.')
    p.add_argument('--since', help='Fixed capture cutoff for resuming an older run.')
    p.add_argument('--limit', type=int, help='Maximum saved JDs to review.')
    p.add_argument('--minutes', type=float, default=8, help='Scoring wall-clock budget.')
    args = p.parse_args()
    if args.minutes <= 0 or (args.limit is not None and args.limit <= 0):
        p.error('minutes and limit must be positive')
    if args.input:
        source = args.input
    else:
        audit = build_audit(args.since or (datetime.now()-timedelta(days=7 if args.window=='7d' else 1)).date().isoformat())
        source = Path(str(audit.with_suffix(''))+'-score-input.json')
    data = json.loads(source.read_text())
    data['jobs'] = data['jobs'][:args.limit or (40 if args.window=='7d' else 15)]
    selected = source.with_name(source.stem+'-bounded.json')
    selected.write_text(json.dumps(data, indent=2))
    if data['jobs']:
        started = time.time()
        score_from_raw_artifacts([str(selected)], dry_run=False, model=DEFAULT_MODEL,
                                 quiet=False, refresh_queue=False,
                                 deadline_epoch=time.time()+args.minutes*60)
        artifacts = [path for path in (ROOT/'discovery/auto/logs').glob('linkedin_live_scored_*.json')
                     if path.stat().st_mtime >= started]
        if artifacts:
            reviewed = json.loads(max(artifacts,key=lambda path:path.stat().st_mtime).read_text()).get('jobs',[])
            if any(row.get('decision') == 'Error' or row.get('_run_timeout_unscored') for row in reviewed):
                return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
