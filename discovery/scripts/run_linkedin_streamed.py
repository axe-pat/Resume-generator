"""Bounded LinkedIn pilot: finish JD retrieval for each admitted page before collecting more."""
import argparse, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from discovery.scripts.run_bounded_discovery import execute, atomic_json, PYTHON
from shared.discovery_search_policy import linkedin_search_terms
from shared.discovery_identity import canonical_listing_url
from discovery.scripts.audit_discovery_coverage import usable_jd

def admit(cards, seen, remaining):
    accepted, deferred=[],[]
    for card in cards:
        key=canonical_listing_url(card.get('url',''))
        if not key or key in seen:continue
        if len(accepted)>=remaining:deferred.append(card);continue
        seen.add(key);accepted.append(card)
    return accepted,deferred

def stage(command, marker, directory, deadline):
    log=directory.with_suffix('.log')
    offset=log.stat().st_size if log.exists()else 0
    code=execute([PYTHON,'-u',*command],deadline=deadline,log_path=log)
    output=''
    if log.exists():
        with log.open()as f:f.seek(offset);output=f.read()
    paths=[Path(line[len(marker):].strip())for line in output.splitlines()if line.startswith(marker)]
    return code,paths[-1]if paths and paths[-1].is_file()else None

def recovered_checkpoint(source):
    """Resume the same saved batch, retaining descriptions fetched before interruption."""
    best=source;count=0
    for path in (ROOT/'discovery/auto/logs').glob('linkedin_live_raw_hydration_inflight_*.json'):
        data=json.loads(path.read_text())
        if str(source.resolve())not in data.get('source_raw_artifacts',[]):continue
        n=sum(usable_jd(row)for row in data.get('cards',[]))
        if n>count:best,count=path,n
    return best

def run(terms, directory, minutes, limit, resume=False, window='7d'):
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'stream-state.json'
    started=time.time()
    state=json.loads(path.read_text())if resume and path.exists()else{'queries':{},'started_at_epoch':started,'deadline':started+minutes*60}
    seen=set();jobs=[];admitted=0
    import jobs as tracker
    blocklist=tracker._load_blocklist()
    for q in state['queries'].values():
        for card in q.get('admitted',[]):seen.add(canonical_listing_url(card['url']));admitted+=1
    try:
        for index,term in enumerate(terms):
            q=state['queries'].setdefault(term,{})
            if q.get('status')in {'reviewed','retrieval_failed'}:continue
            if time.time()>=state['deadline']or (not q.get('admitted')and admitted>=limit):break
            remaining_queries = max(1, len(terms) - index)
            query_deadline = min(state['deadline'], time.time() + max(20,
                (state['deadline'] - time.time()) / remaining_queries))
            prefix=directory/f'query-{index:02d}'
            if not q.get('selected'):
                code,raw=stage(['discovery/auto/linkedin_live.py','--launch-chrome','--extract-only','--count-only','--pages','1','--limit-per-search','25','--allow-jobs-search-fallback','--search',term,'--time','r604800'if window=='7d'else'r86400'], 'Raw artifact: ',prefix,query_deadline)
                if not raw:
                    q.update(status='capture_failed',returncode=code)
                    atomic_json(path,state)
                    continue
                q['capture']=str(raw)
                code,selected=stage(['discovery/scripts/select_linkedin_2027_candidates.py',str(raw),'--exclude-workbook','--require-cohort-signal','--output-dir',str(directory)],'Selected raw artifact: ',prefix,query_deadline)
                if not selected:
                    q.update(status='selection_failed',returncode=code)
                    atomic_json(path,state)
                    continue
                cards=json.loads(selected.read_text()).get('cards',[])
                q['blocklisted']=[c for c in cards if tracker._is_blocklisted(c.get('company',''),blocklist)]
                cards=[c for c in cards if not tracker._is_blocklisted(c.get('company',''),blocklist)]
                chosen,deferred=admit(cards,seen,min(4 if window=='24h'else 12,max(0,limit-admitted)))
                admitted+=len(chosen);q.update(admitted=chosen,budget_deferred=deferred)
                selected=directory/f'query-{index:02d}-admitted.json'
                atomic_json(selected,{'cards':chosen,'count':len(chosen)})
                q['selected']=str(selected);atomic_json(path,state)
            selected=Path(q['selected'])
            if not q.get('admitted'):q['status']='reviewed';atomic_json(path,state);continue
            source=recovered_checkpoint(Path(q.get('resume_source')or selected))
            code,hydrated=stage(['discovery/auto/linkedin_live.py','--hydrate-from-raw',str(source),'--max-hydrate',str(len(q['admitted']))], 'Hydrated raw artifact: ',prefix,query_deadline)
            result=hydrated or recovered_checkpoint(source)
            cards=json.loads(result.read_text()).get('cards',[])
            by_url={canonical_listing_url(c['url']):c for c in cards}
            q['outcomes']=[{'card':by_url.get(canonical_listing_url(c['url']),c),'status':'jd_saved'if usable_jd(by_url.get(canonical_listing_url(c['url']),c))else'jd_unfinished_interruption'if code==124 else'jd_retrieval_failed'}for c in q['admitted']]
            q.update(status='interrupted'if code==124 else'reviewed'if code==0 else'retrieval_failed',returncode=code,result=str(result),resume_source=str(result))
            atomic_json(path,state)
            # A slow query cannot prevent the remaining search lanes from running.
    finally:
        from discovery.auto.linkedin_live import _cards_from_payload,cards_to_jobs
        complete=[o['card']for q in state['queries'].values()for o in q.get('outcomes',[])if o['status']=='jd_saved']
        jobs=cards_to_jobs(_cards_from_payload({'cards':complete}))
        atomic_json(directory/'score-input.json',{'jobs':jobs,'stream_state':str(path)})
        done=sum(q.get('status')in {'reviewed','retrieval_failed'}for q in state['queries'].values())
        state.update(status='finished'if done==len(terms)and all(q.get('status')=='reviewed'and not q.get('budget_deferred')for q in state['queries'].values())else'finished_with_gaps',searches_planned=len(terms),searches_processed=done,admitted=admitted,jds_saved=len(complete),completed_at_epoch=time.time())
        atomic_json(path,state)
    return state

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window',choices=['7d','24h'],default='7d')
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--minutes',type=float)
    p.add_argument('--max-new-jds',type=int)
    p.add_argument('--search-limit',type=int)
    p.add_argument('--search',action='append',help='Explicit small pilot searches; default uses the shared policy.')
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    a.minutes=a.minutes if a.minutes is not None else 43 if a.window=='7d'else 12
    a.max_new_jds=a.max_new_jds if a.max_new_jds is not None else 75 if a.window=='7d'else 25
    terms=a.search or linkedin_search_terms(a.window)
    if a.search_limit:terms=terms[:a.search_limit]
    if a.minutes<=0 or a.max_new_jds<=0:p.error('minutes and max-new-jds must be positive')
    state=run(terms,a.run_dir,a.minutes,a.max_new_jds,a.resume,a.window)
    print(json.dumps({k:v for k,v in state.items()if k!='queries'},indent=2))
    return 0 if state['status']=='finished'else 2
if __name__=='__main__':raise SystemExit(main())
