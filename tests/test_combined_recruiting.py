from argparse import Namespace
from discovery.scripts import run_nightly_pipeline as nightly
from discovery.scripts import run_recruiting_daily as combined

def test_combined_nightly_can_use_bounded_discovery_without_send_flags():
    args=Namespace(bounded_discovery=True,window='24h',skip_linkedin=False,skip_handshake=True,skip_jobspy=False,skip_startup_apply=True)
    cmd=nightly._daily_engine_cmd(args,run_id='shared-run')
    assert 'discovery/scripts/run_bounded_discovery.py' in cmd
    assert 'shared-run' in cmd and '--skip-handshake' in cmd and '--skip-startup-apply' in cmd
    assert '--execute-sends' not in cmd

def test_default_combined_preview_does_not_collect_or_send(tmp_path,monkeypatch):
    import json,sys
    from types import SimpleNamespace
    monkeypatch.setattr(combined,'ROOT',tmp_path)
    monkeypatch.setattr(combined,'browser_preflight',lambda *a:{'status':'checked'})
    monkeypatch.setattr(combined,'refresh_relationships',lambda directory:{'status':'checked'})
    monkeypatch.setattr(sys,'argv',['daily','--run-id','preview'])
    plan=tmp_path/'plan.json';plan.write_text('{"selected":[]}')
    calls=[]
    def fake(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0,stdout=f'Artifact: {plan}\n')
    monkeypatch.setattr(combined.subprocess,'run',fake)
    monkeypatch.setattr(combined,'build_preview',lambda *a,**kw:{})
    assert combined.main()==0
    assert len(calls)==2
    assert all('--execute'not in c and '--send-linkedin'not in c for c in calls)
    assert json.loads((tmp_path/'discovery/auto/checkpoints/preview/combined-state.json').read_text())['outbound_enabled']is False

def test_relationship_refresh_reads_before_selection_without_send_or_draft_flags(tmp_path, monkeypatch):
    from discovery.scripts import recruiting_relationships as relationships
    import json
    calls=[]
    queue=tmp_path/'queue.json';queue.write_text('{"results":[]}')
    def execute(command, **kwargs):
        calls.append(command)
        kwargs['log_path'].write_text(f'Artifact: {queue}\n')
        return 0
    monkeypatch.setattr(relationships,'ROOT',tmp_path)
    monkeypatch.setattr(relationships,'execute',execute)
    assert combined.refresh_relationships(tmp_path)['status']=='checked'
    assert len(calls)==2
    assert 'reconcile-linkedin-messages' in calls[0] and 'build-linkedin-reconcile-queue' in calls[1]
    assert '--live' in calls[0] and '--apply' in calls[0]
    assert not any(any('send' in str(flag) or 'draft' in str(flag) for flag in c) for c in calls)

def test_relationship_sync_failure_is_persisted_as_incomplete(tmp_path, monkeypatch):
    import json
    from discovery.scripts import recruiting_relationships as relationships
    monkeypatch.setattr(relationships,'ROOT',tmp_path)
    monkeypatch.setattr(relationships,'execute',lambda *a,**kw:124)
    assert combined.refresh_relationships(tmp_path)['status']=='incomplete'
    assert json.loads((tmp_path/'relationship-sync.json').read_text())['status']=='incomplete'

def test_completed_profile_batches_survive_later_timeout(tmp_path,monkeypatch):
    import json
    from discovery.scripts import recruiting_relationships as relationships
    monkeypatch.setattr(relationships,'ROOT',tmp_path)
    queue=tmp_path/'queue.json';queue.write_text(json.dumps({'results':[{'contact_id':str(i)}for i in range(6)]}))
    completed=tmp_path/'completed.json';completed.write_text(json.dumps({'results':[{'contact_id':str(i),'normalized_status':'pending'}for i in range(3)]}))
    def execute(command,**kwargs):
        name=kwargs['log_path'].name
        artifact=completed if name=='connections-000.log' else queue
        kwargs['log_path'].write_text(f'Artifact: {artifact}\n')
        return 124 if name=='connections-001.log' else 0
    monkeypatch.setattr(relationships,'execute',execute)
    result=relationships.refresh_relationships(tmp_path)
    assert result['results']['connections']['checked']==3
    assert result['results']['connections']['deferred']==3
    saved=json.loads((tmp_path/'discovery/auto/checkpoints/connection-checks.json').read_text())
    assert set(saved)=={'0','1','2'}

def test_healthy_browser_is_never_restarted(tmp_path,monkeypatch):
    from discovery.scripts import recruiting_relationships as relationships
    calls=[]
    monkeypatch.setattr(relationships,'execute',lambda command,**kw:calls.append(command) or 0)
    assert relationships.browser_preflight(tmp_path,'run')['status']=='checked'
    assert len(calls)==1 and 'ensure_chrome_9222.sh' not in str(calls)

def test_discovery_failure_cannot_be_reported_as_preview_ready(tmp_path,monkeypatch):
    import json,sys
    from types import SimpleNamespace
    monkeypatch.setattr(combined,'ROOT',tmp_path)
    monkeypatch.setattr(combined,'browser_preflight',lambda *a:{'status':'checked'})
    monkeypatch.setattr(combined,'refresh_relationships',lambda *a:{'status':'checked'})
    monkeypatch.setattr(combined,'execute',lambda *a,**kw:2)
    monkeypatch.setattr(sys,'argv',['daily','--run-id','partial','--collect'])
    plan=tmp_path/'plan.json';plan.write_text('{"selected":[]}')
    monkeypatch.setattr(combined.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=f'Artifact: {plan}\n'))
    monkeypatch.setattr(combined,'build_preview',lambda *a,**kw:{})
    assert combined.main()==2
    state=json.loads((tmp_path/'discovery/auto/checkpoints/partial/combined-state.json').read_text())
    assert state['status']=='preview_with_gaps'

def test_failed_preview_does_not_leave_prior_success(tmp_path,monkeypatch):
    import json
    monkeypatch.setattr(combined,'ACTIVE_DIRECTORY',tmp_path)
    (tmp_path/'combined-state.json').write_text('{"status":"preview_ready"}')
    def fail():raise RuntimeError('Proof source changed')
    monkeypatch.setattr(combined,'main',fail)
    assert combined.entrypoint()==2
    assert json.loads((tmp_path/'combined-state.json').read_text())['status']=='preview_failed'
