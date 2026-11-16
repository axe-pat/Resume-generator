"""Review only the exact saved inputs belonging to one bounded discovery run."""
import argparse,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from discovery.scripts.run_bounded_discovery import atomic_json

def collect_inputs(directory):
    inputs=[]
    stream=directory/'linkedin/score-input.json'
    if stream.exists():inputs.append(stream)
    log=directory/'jobspy.log'
    if log.exists():
        paths=re.findall(r'^Wrote JobSpy raw artifact: (.+)$',log.read_text(),re.M)
        if paths and Path(paths[-1]).is_file():inputs.append(Path(paths[-1]))
    return inputs

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--minutes',type=float,default=8)
    a=p.parse_args();jobs=[];sources=collect_inputs(a.run_dir)
    for path in sources:jobs.extend(json.loads(path.read_text()).get('jobs',[]))
    packet=a.run_dir/'review-input.json'
    atomic_json(packet,{'jobs':jobs,'source_raw_artifacts':[str(s)for s in sources]})
    if not jobs:
        empty=a.run_dir/'empty-scored.json';atomic_json(empty,{'jobs':[],'scored':0})
        print(f'Scored artifact: {empty.resolve()}',flush=True);return 0
    return subprocess.run([sys.executable,'-u','discovery/scripts/review_saved_discovery.py','--input',str(packet),'--limit',str(len(jobs)),'--minutes',str(a.minutes)],cwd=ROOT).returncode
if __name__=='__main__':raise SystemExit(main())
