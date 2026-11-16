import json
from discovery.scripts import run_linkedin_streamed as stream

def test_admission_deduplicates_and_never_overfills_jd_capacity():
    cards=[{'url':'https://www.linkedin.com/jobs/view/1/'},{'url':'https://www.linkedin.com/jobs/view/1/?tracking=x'},{'url':'https://www.linkedin.com/jobs/view/2/'}]
    kept,deferred=stream.admit(cards,set(),1)
    assert len(kept)==1 and len(deferred)==1

def test_interrupted_batch_resumes_jds_without_recollecting(tmp_path,monkeypatch):
    raw=tmp_path/'raw.json';selected=tmp_path/'selected.json';partial=tmp_path/'partial.json';full=tmp_path/'full.json'
    cards=[{'title':'Product Manager 2027','company':'Example','url':f'https://www.linkedin.com/jobs/view/{i}/','jd_text':''}for i in [1,2]]
    for p in [raw,selected]:p.write_text(json.dumps({'cards':cards,'count':2}))
    partial.write_text(json.dumps({'cards':[{**cards[0],'jd_text':'Saved description'},cards[1]]}))
    full.write_text(json.dumps({'cards':[{**r,'jd_text':'Complete saved description'}for r in cards]}))
    calls=[]
    def stage(command,marker,*args):
        calls.append(marker)
        if marker=='Raw artifact: ':return 0,raw
        if marker=='Selected raw artifact: ':return 0,selected
        return (124,partial)if calls.count(marker)==1 else(0,full)
    monkeypatch.setattr(stream,'stage',stage)
    monkeypatch.setattr(stream,'recovered_checkpoint',lambda p:p)
    monkeypatch.setattr(stream,'usable_jd',lambda c:bool(c.get('jd_text')))
    first=stream.run(['Product Manager 2027'],tmp_path/'run',5,2)
    assert first['queries']['Product Manager 2027']['status']=='interrupted'
    assert first['jds_saved']==1
    assert first['queries']['Product Manager 2027']['outcomes'][1]['status']=='jd_unfinished_interruption'
    second=stream.run(['Product Manager 2027'],tmp_path/'run',90,2,resume=True)
    assert second['deadline']==first['deadline']
    assert second['jds_saved']==2 and second['status']=='finished'
    assert calls.count('Raw artifact: ')==1

def test_expired_budget_still_publishes_saved_input(tmp_path,monkeypatch):
    stream.atomic_json(tmp_path/'stream-state.json',{'queries':{},'deadline':0})
    monkeypatch.setattr(stream,'stage',lambda *a:(_ for _ in ()).throw(AssertionError('Must not collect after expiry')))
    state=stream.run(['example'],tmp_path,5,2,resume=True)
    assert state['status']=='finished_with_gaps'
    assert json.loads((tmp_path/'score-input.json').read_text())['jobs']==[]

def test_exact_run_inputs_do_not_include_other_runs(tmp_path):
    from discovery.scripts.review_run_discovery import collect_inputs
    other=tmp_path/'old-jobspy.json';other.write_text('{"jobs":[]}')
    run=tmp_path/'run';(run/'linkedin').mkdir(parents=True)
    stream_input=run/'linkedin/score-input.json';stream_input.write_text('{"jobs":[]}')
    assert collect_inputs(run)==[stream_input]

def test_credit_failure_stops_retrying_same_job():
    from discovery.auto import scorer
    from types import SimpleNamespace
    calls=[]
    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('Your credit balance is too low to access the Anthropic API')
    jd=('MBA graduates completing their degree between December 2026 and June 2027 are eligible. '
        'The Associate Product Manager owns product discovery, roadmap, user research and engineering prioritization. '
        'Responsibilities include working with engineering, design and business teams to measure customer outcomes. '
        'Qualifications include analytical skills, technical experience, communication and product delivery. ')*5
    result=scorer.score_job({'company':'Example','role_title':'Associate Product Manager 2027','lane':'B','jd_text':jd},SimpleNamespace(messages=SimpleNamespace(create=fail)),'candidate','rubric',verbose=False)
    assert result.get('_scoring_fatal_error')=='insufficient_credits'
    assert len(calls)==1
    calls.clear()
    jobs=[{'company':'Example','role_title':'Associate Product Manager 2027','lane':'B','jd_text':jd,'url':str(i)}for i in range(8)]
    out=scorer.score_batch(jobs,client=SimpleNamespace(messages=SimpleNamespace(create=fail)),verbose=False)
    assert len(calls)<=2
    assert len(out)==8 and all(r['decision']=='Error'for r in out)
