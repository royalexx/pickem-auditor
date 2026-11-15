"""Separate audit pass against frozen real inputs; never mutates original report."""
from pathlib import Path
import copy,json,unittest
from . import models as m
from .ws1_feature_adapter import audit_report

def verify(directory):
    d=Path(directory);p=json.loads((d/'adapter_packet.json').read_bytes());r=json.loads((d/'report.json').read_bytes())
    assert m.sha((d/'report.json').read_bytes())==d.name
    assert m.sha((d/'adapter_packet.json').read_bytes())==r['adapter_packet_sha256']
    assert audit_report(copy.deepcopy(r))['mass_mean_variance_push_reconstructions']>0
    # Replay bit-for-bit deterministic model computation from exact frozen inputs.
    a=m.OpportunityModel(p,8192).run();b=m.OpportunityModel(p,8192).run()
    assert m.canonical(a)==m.canonical(b)
    frozen={(x['contract']['contract_id'],x['model']):x for x in r['rows'] if x['status']=='forecast'}
    for x in a['rows']:
        if x['status']=='forecast':
            y=frozen[x['contract']['contract_id'],x['model']]
            assert x['predictive_distribution_conditional']==y['predictive_distribution_conditional']
    attacks=0
    def reject(q):
        nonlocal attacks
        try:m.validate(q)
        except m.GateError:attacks+=1;return
        raise AssertionError('corruption accepted')
    q=copy.deepcopy(p);q['team_history'][0]['sacks']=None;reject(q)
    q=copy.deepcopy(p);q['team_history'][0]['plays']+=1;reject(q)
    q=copy.deepcopy(p);q['player_history'][0]['game_id']='ESPN_WRONG_NAMESPACE';reject(q)
    q=copy.deepcopy(p);q['player_history'][0]['end_at']='2026-11-16T00:00:00Z';reject(q)
    q=copy.deepcopy(p);q['events'][0]['event_start']=q['forecast_at'];reject(q)
    q=copy.deepcopy(p);q['roster'].append(copy.deepcopy(q['roster'][0]));reject(q)
    q=copy.deepcopy(p)
    qb=next(h for h in q['player_history'] if h['position']=='QB' and h.get('pass_attempts') is not None)
    qb['completions']=qb['pass_attempts']+1;reject(q)
    q=copy.deepcopy(p)
    defense=next((h for h in q['player_history'] if h.get('snaps') is not None),None)
    if defense is not None:
        defense['solo']=defense['snaps']+1;reject(q)
    print(json.dumps({'real_forecasts_replayed':len(frozen),'bit_identical_replay':True,'adversarial_packet_mutations_rejected':attacks,'report_sha256':d.name,'team_conservation_max_error':max(x['conservation_max_error'] for x in r['team_opportunities'])}))
