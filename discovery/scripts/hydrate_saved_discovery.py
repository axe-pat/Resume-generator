"""Fetch a prioritized, capped saved-card batch under the supervisor's JD budget."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def main():
    from discovery.scripts.audit_discovery_coverage import build_audit
    p=argparse.ArgumentParser()
    p.add_argument('--window', choices=['24h','7d'], default='24h')
    args=p.parse_args()
    audit=build_audit((datetime.now()-timedelta(days=7 if args.window=='7d'else 1)).date().isoformat())
    source=Path(str(audit.with_suffix(''))+'-hydrate-input.json')
    cards=json.loads(source.read_text())['cards']
    cards.sort(key=lambda r:not bool(re.search(r'2027|\bmba\b|new.?grad|graduate',str(r.get('title')or r.get('role_title')or''),re.I)))
    limit=75 if args.window=='7d'else 25
    chosen=source.with_name(source.stem+'-bounded.json')
    chosen.write_text(json.dumps({'cards':cards[:limit],'count':min(limit,len(cards))},indent=2))
    if not cards:return 0
    return subprocess.run([sys.executable,'discovery/auto/linkedin_live.py','--hydrate-from-raw',str(chosen),'--max-hydrate',str(limit)],cwd=ROOT).returncode

if __name__=='__main__':raise SystemExit(main())
