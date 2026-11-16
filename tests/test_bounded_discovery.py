import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bounded', ROOT/'discovery/scripts/run_bounded_discovery.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

def test_failed_source_still_publishes_and_resume_skips_success(tmp_path, monkeypatch):
    calls = []
    def execute(command, **kwargs):
        calls.append(command[0])
        return 1 if command[0]=='bad' else 0
    monkeypatch.setattr(runner, 'execute', execute)
    tasks = [('a',['good'],1),('b',['bad'],1)]
    state = runner.supervise(tasks,directory=tmp_path,minutes=1)
    assert state['status']=='finished_with_gaps'
    assert state['publication_returncode']==0
    calls.clear()
    runner.supervise(tasks,directory=tmp_path,minutes=1,resume=True)
    assert 'good' not in calls and 'bad' in calls

def test_deadline_kills_child(tmp_path):
    import sys,time
    start=time.time()
    code=runner.execute([sys.executable,'-c','import time; time.sleep(30)'],deadline=start+.15,log_path=tmp_path/'log')
    assert code==124 and time.time()-start<3

def test_resume_preserves_deadline_and_refreshes_downstream(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(runner,'execute',lambda command,**kw: calls.append(command[0]) or 0)
    first=runner.supervise([('linkedin',['old'],1),('hydrate',['hydrate'],1),('review',['review'],1)],directory=tmp_path,minutes=1)
    calls.clear()
    second=runner.supervise([('linkedin',['new'],1),('hydrate',['hydrate'],1),('review',['review'],1)],directory=tmp_path,minutes=90,resume=True)
    assert second['deadline_epoch']==first['deadline_epoch']
    assert calls[:3]==['new','hydrate','review']

def test_reviews_survive_interruption(tmp_path):
    from shared.discovery_review_journal import review_batch
    journal=tmp_path/'reviews.jsonl'
    rows=[dict(url='a',jd_text='JD A',company='A',role_title='PM',lane='B'),dict(url='b',jd_text='JD B',company='B',role_title='PM',lane='B')]
    def interrupted(jobs,on_result,**kwargs):
        on_result({**jobs[0],'decision':'Proceed','fit_score':8})
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        review_batch(rows,score_fn=interrupted,journal=journal)
    def finish(jobs,on_result,**kwargs):
        assert [j['url']for j in jobs]==['b']
        result={**jobs[0],'decision':'Reject'}
        on_result(result)
        return [result]
    out=review_batch(rows,score_fn=finish,journal=journal)
    assert [r['decision']for r in out]==['Proceed','Reject']
    assert len(journal.read_text().splitlines())==2

def test_policy_budget_and_spring_coverage():
    from shared.discovery_search_policy import linkedin_search_terms
    weekly=linkedin_search_terms('7d');daily=linkedin_search_terms('24h')
    assert len(weekly)==20 and len(daily)==9
    assert sum('Spring 2027' in t for t in weekly)==6
    assert '2027' not in weekly and 'MBA Strategy Operations 2027' in weekly
    assert 'Graduate 2027' in daily[0]
    assert 'Spring 2027' in daily[1]
    assert 'MBA' in daily[2]

def test_handshake_graduate_filter_does_not_require_internship_title():
    from discovery.auto.import_handshake_csv import CsvJob, _handshake_title_prefilter_reason
    item=CsvJob('1','Example','Associate Product Manager, Graduate 2027','','','','','')
    assert _handshake_title_prefilter_reason(item,'B')==''
    assert _handshake_title_prefilter_reason(item,'A')!=''

def test_real_batch_reports_each_completed_review(monkeypatch):
    from discovery.auto import scorer
    monkeypatch.setattr(scorer,'_load_file',lambda *a:'test')
    monkeypatch.setattr(scorer,'score_job',lambda job,*a,**kw:{**job,'decision':'Proceed'})
    seen=[]
    result=scorer.score_batch([{'lane':'B','url':'a'},{'lane':'B','url':'b'}],client=object(),verbose=False,on_result=seen.append)
    assert len(seen)==len(result)==2

def test_skipped_tracker_row_cannot_be_selected_from_old_score(tmp_path, monkeypatch):
    from discovery.scripts import build_daily_action_queue as queue
    artifact=tmp_path/'scored.json'
    artifact.write_text(json.dumps({'jobs':[{'company':'TIAA','role_title':'MBA Associate','url':'https://example.com/1','jd_text':'Full JD','decision':'Proceed'}]}))
    monkeypatch.setattr(queue,'_find_existing_job',lambda *a:queue.ExistingJobState('TIAA','MBA Associate','skipped','8','1','https://example.com/1','test'))
    selected,rejected,_=queue._load_scored_application_sections(scored_artifact_paths=[artifact],job_indexes=({}, {}, {}),blocklist=[])
    assert selected==[] and rejected[0]['write_gate_reason']=='tracker_status_skipped'

def test_mba_leadership_associate_requires_relevant_rotations():
    from shared.job_eligibility import classify_role_surface
    title='U.S. Consumer Cards - Full-Time Leadership Associate, 2027'
    assert classify_role_surface(title,'MBA graduates join two rotations in Product Management and Strategy.')[0]=='keep'
    assert classify_role_surface(title,'MBA preferred. General customer service and branch training.')[0]!='keep'
    assert classify_role_surface('Spring 2027 Entertainment Internship Program - MBA','Placements include Digital Strategy & Business Development.')[0]=='keep'

def test_audit_rechecks_prefilter_instead_of_requeuing_paid_review(monkeypatch):
    from discovery.scripts.audit_discovery_coverage import current_prefilter_rejection, completed_review
    from discovery.auto import scorer
    old={'decision':'Reject','_raw_response':'Pre-filter rejection'}
    monkeypatch.setattr(scorer,'score_job',lambda *a,**kw:{'decision':'Reject','fit_rationale':'Currently pursuing bachelor degree required'})
    assert current_prefilter_rejection({},old)
    monkeypatch.setattr(scorer,'score_job',lambda *a,**kw:{'decision':'Error','fit_rationale':'Client unavailable'})
    assert current_prefilter_rejection({},old)==''
    assert completed_review({'decision':'Reject','review_method':'direct saved-JD review, November 13'})
