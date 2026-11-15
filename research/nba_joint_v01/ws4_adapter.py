"""Actual WS4 boundary + count-CDF validation of actual joint research artifacts.

The strict WS4 canonical forecast evaluator remains blocked: these newly
generated historical forecasts were not genuinely archived before their games.
Do not fabricate fit/source clocks to satisfy it. Readiness envelopes below are
explicitly structural reconstructed research envelopes, never source certificates.
"""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from research.nba_ws4.joint_contract import VERSION,validate_fixture
from research.nba_ws4.metrics import distribution,threshold,paired_bootstrap
from v2.nba_joint.forecast import freeze


def envelope(o,j,code):
    g=o['game'];common=dict(schema=VERSION,event_id=g['game_id'],scenario_id=o['scenario_ids'][j],seed=o['seed'],source_manifest_sha256=o['input_sha256'],
        input_freeze_at=g['analysis_cutoff_at'],code_sha=code,artifact_sha256=o['model_sha256'],training_cutoff=o['model']['training_cutoff_at'])
    features={**common,'event_start':g['event_start_at'],'team_ids':g['teams'],'market_anchor':'none','evidence_kind':'reconstructed_research_structure_only','actual_generated_at':g['forecast_at']}
    opportunity={**common,'overtime_periods':int(o['state']['overtime'][j]),'players':[dict(player_id=p['player_id'],team_id=p['team_id'],minutes=float(o['minutes'][j][i]),active=bool(o['minutes'][j][i]>0)) for i,p in enumerate(o['players'])]}
    players=[]
    for i,p in enumerate(o['players']):
        s={k:int(o['stats'][k][j][i]) for k in ('points','rebounds','assists','threes','ftm','fta','pr','pa','ra','pra')}
        s.update(player_id=p['player_id'],team_id=p['team_id'],fgm=int(o['stats']['two_pm'][j][i]+o['stats']['threes'][j][i]),fga=int(o['stats']['two_pa'][j][i]+o['stats']['three_pa'][j][i]))
        players.append(s)
    outcomes={**common,'players':players,'team_points':{t:sum(p['points'] for p in players if p['team_id']==t) for t in g['teams']}}
    return features,opportunity,outcomes


def main():
    root=Path('research/nba_joint_v01/results');receipt=json.loads((root/'run_receipt.json').read_text());code=receipt['code_commit']
    forecasts={}
    for path in sorted(root.glob('forecasts_*.gz')):
        for f in json.loads(gzip.decompress(path.read_bytes())):forecasts[(f['game_id'],f['player_id'],f['stat'])]=f
    scenarios=0;fixture_hashes=[]
    for path in sorted((root/'scenarios').glob('*.gz')):
        o=json.loads(gzip.decompress(path.read_bytes()))
        for j in range(o['n']):
            check=validate_fixture(*envelope(o,j,code));scenarios+=1;fixture_hashes.append(check['fixture_hash'])
    rows=json.loads(gzip.decompress((root/'scores.json.gz').read_bytes()));count_checks=0;max_error=0;pmf_rows=[]
    for r in rows:
        if r['model']!='J2':continue
        f=forecasts[(r['game_id'],r['player_id'],r['stat'])];pmf=[f['pmf'].get(str(k),0.) for k in range(max(map(int,f['pmf']))+1)]
        check=distribution(pmf,int(r['actual']),identity=f['output_sha256'])
        error=abs(check['count_crps']-r['crps']);max_error=max(max_error,error)
        if error>1e-10:raise ValueError('WS4_COUNT_CRPS_DISAGREEMENT')
        threshold_check=threshold(pmf,float(int(r['actual'])+.5))
        if abs(sum(threshold_check.values())-1)>1e-10 or threshold_check['push']!=0:raise ValueError('WS4_THRESHOLD_DISAGREEMENT')
        count_checks+=1;pmf_rows.append(dict(game_id=r['game_id'],player_id=r['player_id'],stat=r['stat'],randomized_pit=check['randomized_pit']))
    # Use independent WS4 date/game cluster implementation, not only WS5's own bootstrap.
    indexed={}
    for r in rows:
        if r['model'] in ('J0','J2'):indexed.setdefault((r['game_id'],r['player_id'],r['stat']),{})[r['model']]=r
    paired={}
    for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
        matched=[]
        for key,v in indexed.items():
            if key[2]!=stat or set(v)!={'J0','J2'} or v['J0']['split']!='test':continue
            matched.append(dict(contract_id='/'.join(key),event_id=key[0],date=v['J0']['date'],delta=v['J2']['crps']-v['J0']['crps']))
        paired[stat]={cluster:paired_bootstrap(matched,cluster=cluster,draws=1000) for cluster in ('date','game')}
    freeze(root/'ws4_adapter_receipt.json',dict(status='PASSED_STRUCTURAL_AND_DISTRIBUTION_CHECKS_ONLY',upstream_sha='9821694260edb08b7414f02adea8c1fb3fd3b13c',upstream_pr=139,
        scenarios_checked=scenarios,count_distribution_checks=count_checks,max_crps_difference=max_error,fixture_hash_manifest_sha256=hashlib.sha256(json.dumps(fixture_hashes).encode()).hexdigest(),paired_crps=paired,
        canonical_pregame_forecast_gate='BLOCKED-BY-DATA: generated retrospectively with unavailable original participation clocks; no retrocertification',independent_statistical_acceptance='PENDING_EXTERNAL_REVIEW'))
    freeze(root/'randomized_pit.json',pmf_rows)
    print(json.dumps(dict(scenarios=scenarios,count_checks=count_checks,max_crps_difference=max_error)))


if __name__=='__main__':main()
