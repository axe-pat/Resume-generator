"""One review-only daily entrypoint over bounded discovery and existing Outreach planning."""
import argparse,csv,json,re,subprocess,sys,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUTREACH=ROOT.parent/'Outreach'
ACTIVE_DIRECTORY=None
sys.path.insert(0,str(ROOT))
from discovery.scripts.run_bounded_discovery import atomic_json,execute,PYTHON
from discovery.scripts.recruiting_relationships import refresh_relationships,browser_preflight

def read_csv(name):
    with (OUTREACH/'workspace'/name).open(newline='')as f:return list(csv.DictReader(f))

def build_preview(plan, directory, run_id, discovery_state=None,posted=None,warm_context=None):
    organizations={r['organization_id']:r for r in read_csv('organizations.csv')}
    contexts=[organizations.get(a.get('organization_id'),{}).get('notes','')for a in plan.get('selected',[])]
    worker="import json,sys; from pathlib import Path; from outreach.reply_engine.proof import load_proof_beats,select_proof_beats; proof=load_proof_beats(Path('workspace/proof_beats.yml')); print(json.dumps([[b.text for b in select_proof_beats(proof,recipient_context=c,limit=2)]for c in json.load(sys.stdin)]))"
    selected_proof=subprocess.run([str(OUTREACH/'.venv/bin/python'),'-c',worker],cwd=OUTREACH,input=json.dumps(contexts),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if selected_proof.returncode:raise RuntimeError('Outreach proof validation failed: '+selected_proof.stderr[-500:])
    proof_by_company=dict(zip([a.get('organization_id')for a in plan.get('selected',[])],json.loads(selected_proof.stdout)))
    contacts=read_csv('contacts.csv');touches=read_csv('touchpoints.csv')
    briefs=[]
    for action in plan.get('selected',[]):
        org=organizations.get(action.get('organization_id'),{})
        parts={k.strip():v.strip()for part in org.get('notes','').split(' | ')for k,sep,v in [part.partition('=')]if sep}
        history=[r for r in touches if r['organization_id']==action.get('organization_id')]
        history.sort(key=lambda r:r.get('sent_at')or r.get('recorded_at')or'',reverse=True)
        briefs.append({'company':action.get('company'),'organization_id':action.get('organization_id'),'website':org.get('website'),'context':parts.get('description')or'Needs product research','why_fit':parts.get('story_fit_reason')or parts.get('why_this_company')or'Needs fit research','proof':proof_by_company.get(action.get('organization_id'),[]),'planned_action':action,'last_touchpoints':history[:3],'freshness':'Historical tracker context; verify current product/team and thread before sending','learning_prompt':'What customer problem does this product solve, and what could your strongest relevant experience help improve? Treat ideas as hypotheses.'})
    study=next((r for r in organizations.values()if r['name'].casefold()=='studyfetch'),{})
    warm=[r for r in contacts if r['organization_id']==study.get('organization_id')]
    refresh=warm_context
    output={'run_id':run_id,'mode':'review_only','campaign':'spring_ft_2027','discovery':discovery_state or {'status':'saved_inputs_only'},'posted_opportunities':posted or{},'outreach_plan':plan,'company_learning':briefs,'studyfetch_contacts':warm,'live_thread_refresh_artifact':str(refresh)if refresh and refresh.exists()else'','history_completeness':'Review the explicitly supplied snapshot and date; live refresh is not implied','outbound_enabled':False}
    atomic_json(directory/'preview.json',output)
    lines=['# Combined recruiting preview','',f'Run: {run_id}. Campaign: Spring 2027 + 2027 full-time. Review only; no messages sent.','','## StudyFetch warm restart','']
    for r in warm:lines.append(f"- {r['full_name']} — {r['title']} — tracker status: {r['status']}")
    lines+=['','## Posted-opportunity outreach queue','', 'These are existing tracker opportunities, not newly discovered roles in this preview. Eligibility and school/start compatibility still need final application review.']
    for r in (posted or{}).get('results',[]):lines.append(f"- [{r['company']} — {r['role_title']}]({r['source_url']}) — tracker status: {r['status']}")
    lines+=['','## Company worklist','', 'These companies were selected for the actions below. Contact research and company research are preparation tasks; an outreach wave still needs current context and recipient review.','']
    for r in briefs:
        lines += [f"### {r['company']}",f"Website: {r['website'] or 'not recorded'}",f"Planned action: {r['planned_action'].get('campaign_action','see plan')}",f"What they do (saved context): {r['context']}",f"Why this company: {r['why_fit']}",f"Relevant evidence: {' / '.join(r['proof'])or'Needs evidence selection'}",f"Learning question: {r['learning_prompt']}",'Historical context; current company/thread verification pending.','']
    (directory/'preview.md').write_text('\n'.join(lines)+'\n')
    return output

def main():
    global ACTIVE_DIRECTORY
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',default=datetime.now().strftime('%Y%m%d-%H%M%S'))
    p.add_argument('--window',choices=['24h','7d'],default='24h')
    p.add_argument('--collect',action='store_true',help='Run bounded discovery first; default previews saved state only.')
    p.add_argument('--offline-preview',action='store_true',help='Explicit saved-state preview without live inbox/connection reconciliation.')
    p.add_argument('--warm-context',type=Path,help='Explicit dated conversation snapshot to include for review.')
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.run_id):p.error('Invalid run ID')
    directory=ROOT/'discovery/auto/checkpoints'/a.run_id;directory.mkdir(parents=True,exist_ok=True)
    ACTIVE_DIRECTORY=directory
    deadline = time.time() + (90 if a.window == '7d' else 30)*60
    atomic_json(directory/'combined-state.json',{'run_id':a.run_id,'status':'running_preview','outbound_enabled':False})
    stages={};state=None
    browser = {'status':'offline'} if a.offline_preview else browser_preflight(directory,a.run_id)
    sync = {'status':'offline'} if a.offline_preview else refresh_relationships(directory) if browser['status']=='checked' else {'status':'incomplete','reason':'Browser preflight failed'}
    atomic_json(directory/'combined-state.json',{'run_id':a.run_id,'status':'running_discovery' if a.collect else 'building_preview','relationship_sync':sync,'browser':browser,'outbound_enabled':False})
    if a.collect:
        command=[str(PYTHON),'discovery/scripts/run_bounded_discovery.py','--window',a.window,'--run-id',a.run_id,'--minutes',str(max(.1,(deadline-time.time()-45)/60))]
        if browser['status']!='checked':command+=['--skip-linkedin','--skip-handshake']
        stages['discovery_returncode']=execute(command,deadline=deadline-40,log_path=directory/'discovery.log')
        source=directory/'state.json'
        if source.exists():state=json.loads(source.read_text())
    # Read-only planner: no --execute, --live-linkedin or send flags.
    result=subprocess.run([str(OUTREACH/'.venv/bin/python'),'main.py','build-track-2-daily-plan','--workspace','workspace','--max-companies','10','--max-email-research','0','--max-email-drafts','0','--current-hiring-only'],cwd=OUTREACH,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    (directory/'outreach-plan.log').write_text(result.stdout);stages['outreach_plan_returncode']=result.returncode
    paths=re.findall(r'Artifact: (.+\.json)',result.stdout)
    if not paths:
        atomic_json(directory/'combined-state.json',{'run_id':a.run_id,'status':'outreach_plan_failed','stages':stages});return 2
    plan_path=Path(paths[-1]);plan_path=plan_path if plan_path.is_absolute()else OUTREACH/plan_path
    queue=subprocess.run([str(OUTREACH/'.venv/bin/python'),'main.py','build-resume-outreach-queue','--resume-season-focus','spring_ft_2027','--min-score','0','--limit','10'],cwd=OUTREACH,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (directory/'posted-queue.log').write_text(queue.stdout);stages['posted_queue_returncode']=queue.returncode
    queue_paths=re.findall(r'Artifact: (.+\.json)',queue.stdout);posted={}
    if queue_paths:
        qp=Path(queue_paths[-1]);qp=qp if qp.is_absolute()else OUTREACH/qp
        if qp.exists():posted=json.loads(qp.read_text())
    preview=build_preview(json.loads(plan_path.read_text()),directory,a.run_id,state,posted,a.warm_context)
    ready = sync['status'] == 'checked' and all(v==0 for v in stages.values())
    atomic_json(directory/'combined-state.json',{'run_id':a.run_id,'status':'preview_ready' if ready else 'offline_preview_ready' if a.offline_preview else 'preview_with_gaps','relationship_sync':sync,'browser':browser,'stages':stages,'outreach_plan':str(plan_path),'preview':str(directory/'preview.md'),'outbound_enabled':False})
    print(f"Preview: {directory/'preview.md'}")
    return 0 if all(v==0 for v in stages.values()) and (ready or a.offline_preview) else 2
def entrypoint():
    try:return main()
    except Exception as exc:
        if ACTIVE_DIRECTORY is not None:
            atomic_json(ACTIVE_DIRECTORY/'combined-state.json',{'status':'preview_failed','error':str(exc)[:500],'outbound_enabled':False})
        print(f'Combined preview failed: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(entrypoint())
