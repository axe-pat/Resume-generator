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
    calls=[]
    def execute(command, **kwargs):
        calls.append(command)
        kwargs['log_path'].write_text('checked')
        return 0
    monkeypatch.setattr(combined,'execute',execute)
    assert combined.refresh_relationships(tmp_path)['status']=='checked'
    assert len(calls)==2
    assert 'reconcile-linkedin-messages' in calls[0] and 'reconcile-linkedin' in calls[1]
    assert all('--live' in c and '--apply' in c for c in calls)
    assert not any(any('send' in str(flag) or 'draft' in str(flag) for flag in c) for c in calls)

def test_relationship_sync_failure_is_persisted_as_incomplete(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(combined,'execute',lambda *a,**kw:124)
    assert combined.refresh_relationships(tmp_path)['status']=='incomplete'
    assert json.loads((tmp_path/'relationship-sync.json').read_text())['status']=='incomplete'

def test_failed_preview_does_not_leave_prior_success(tmp_path,monkeypatch):
    import json
    monkeypatch.setattr(combined,'ACTIVE_DIRECTORY',tmp_path)
    (tmp_path/'combined-state.json').write_text('{"status":"preview_ready"}')
    def fail():raise RuntimeError('Proof source changed')
    monkeypatch.setattr(combined,'main',fail)
    assert combined.entrypoint()==2
    assert json.loads((tmp_path/'combined-state.json').read_text())['status']=='preview_failed'
