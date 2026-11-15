"""Separate artifact validation using unchanged WS4 count-CDF/boundary code."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from research.nba_ws4.joint_contract import validate_fixture
from research.nba_ws4.metrics import distribution,paired_bootstrap
from research.nba_joint_v01.ws4_adapter import envelope
from v2.nba_joint import audit
from v2.nba_joint.common import sha
from v2.nba_joint.forecast import freeze,extract_forecast
from .run import load,mean_metrics,require_complete_oracle
from research.nba_joint_v01.data import box


def real_forecast_metrics(rows):
    # Real-forecast scoring never accepts an oracle or uncertified reconstructed row.
    for r in rows:
        if r.get('oracle') or not r.get('pregame_source_qualified'):
            raise ValueError('DIAGNOSTIC_CANNOT_ENTER_REAL_FORECAST_METRICS')
    return rows


def event_checks(o):
    c=o['stats'];m=o['minutes'];ix=o['team_indices'];n=o['n']
    if any(v.shape!=m.shape or np.any(v<0) or not np.issubdtype(v.dtype,np.integer) for v in c.values()):raise ValueError('COUNT_SUPPORT')
    np.testing.assert_array_equal(c['points'],2*c['two_pm']+3*c['threes']+c['ftm'])
    np.testing.assert_array_equal(c['rebounds'],c['oreb']+c['dreb'])
    for name,parts in {'pr':['points','rebounds'],'pa':['points','assists'],'ra':['rebounds','assists'],'pra':['points','rebounds','assists']}.items():
        np.testing.assert_array_equal(c[name],sum(c[k] for k in parts))
    if np.any(c['two_pm']>c['two_pa']) or np.any(c['threes']>c['three_pa']) or np.any(c['ftm']>c['fta']):raise ValueError('CONVERSION_SUPPORT')
    if np.any(c['points'][:,ix[0]].sum(axis=1)==c['points'][:,ix[1]].sum(axis=1)):raise ValueError('FINAL_TIE')
    np.testing.assert_allclose(o['state']['duration'],48+5*o['state']['overtime'],rtol=0,atol=1e-10)
    for j,ledger in enumerate(o['event_ledgers']):
        a=np.asarray(ledger['assist_matrix'])
        if np.trace(a)!=0 or np.any(a[np.ix_(ix[0],ix[1])]) or np.any(a[np.ix_(ix[1],ix[0])]):raise ValueError('ASSIST_IDENTITY')
        np.testing.assert_array_equal(a.sum(axis=1),c['assists'][j])
        if np.any(a.sum(axis=0)>c['two_pm'][j]+c['threes'][j]):raise ValueError('ASSIST_SCORER')
        for t,indices in enumerate(ix):
            if c['assists'][j,indices].sum()+ledger['unassisted'][t]!=(c['two_pm'][j,indices]+c['threes'][j,indices]).sum():raise ValueError('ASSIST_TOTAL')
            reb=ledger['rebounds'][t]
            if reb['credited']>reb['available'] or reb['credited']+reb['unattributed']!=reb['available']:raise ValueError('REBOUND_POOL')
            if c['oreb'][j,indices].sum()!=reb['offensive'] or c['dreb'][j,ix[1-t]].sum()!=reb['defensive']:raise ValueError('REBOUND_CREDIT')
    return n


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--results',default='research/nba_phase6/results');parser.add_argument('--output',required=True);args=parser.parse_args()
    root=Path(args.results);counts=load(root/'count_scores.json.gz');minutes=load(root/'minute_scores.json.gz');summary=load(root/'summary.json')
    receipt=load(root/'run_receipt.json');source_checks=0;scenario_checks=0;events=0;crps_checks=0;max_error=0.;raw_conservation_failures=0
    bygame=defaultdict(list)
    for r in counts:
        if r['model'] in ('A','C_ORACLE','D_RAW'):bygame[(r['game_id'],r['model'])].append(r)
    for (gid,label),rows in bygame.items():
        o=load(root/'scenarios'/(gid+'_'+label+'.json.gz'))
        for k in ('minutes','independent_minutes'):o[k]=np.asarray(o[k])
        o['stats']={k:np.asarray(v,dtype=np.int64) for k,v in o['stats'].items()};o['state']={k:np.asarray(v) for k,v in o['state'].items()}
        if o['model_sha256']!=receipt['model_sha256'] or sha(o['model'])!=receipt['model_sha256']:raise ValueError('MODEL_HASH')
        if sha(o['model']['events'])!=receipt['events_sha256']:raise ValueError('EVENT_MODEL_CHANGED')
        events+=event_checks(o)
        if label=='C_ORACLE':
            actual={p['player_id']:p for p in box('work/joint_input/raw/'+gid+'.json')['players'] if p['minutes']>0}
            require_complete_oracle(o['game'],actual)
        if label in ('A','C_ORACLE'):
            audit(o)
            for j in range(o['n']):validate_fixture(*envelope(o,j,receipt['head']));scenario_checks+=1
        else:
            if o.get('research_opportunity',{}).get('kind')!='raw_m0_diagnostic':raise ValueError('RAW_LABEL')
            np.testing.assert_array_equal(o['minutes'],o['independent_minutes'])
            try:audit(o)
            except ValueError as exc:
                if 'TEAM_MINUTES' not in str(exc):raise
                raw_conservation_failures+=1
            else:raise ValueError('RAW_UNEXPECTEDLY_VALID_ROTATION')
        if label!='A':
            try:extract_forecast(o,0,'points')
            except ValueError as exc:
                if 'DIAGNOSTIC_NOT_FORECAST' not in str(exc):raise
            else:raise ValueError('DIAGNOSTIC_FORECAST_EXPORT')
        index={p['player_id']:i for i,p in enumerate(o['players'])}
        for r in rows:
            x=o['stats'][r['stat']][:,index[r['player_id']]];pmf=np.bincount(x).astype(float)/len(x)
            check=distribution(pmf.tolist(),int(r['actual']),identity=gid+'/'+r['player_id']+'/'+r['stat'])
            error=abs(check['count_crps']-r['crps']);max_error=max(max_error,error);crps_checks+=1
            if error>1e-10:raise ValueError('INDEPENDENT_WS4_CRPS_DISAGREEMENT')
    for path in sorted((root/'scenarios').glob('*_E_partial_pools.json.gz')):
        payload=load(path);gid=path.name.split('_')[0];A=load(root/'scenarios'/(gid+'_A.json.gz'));length=np.asarray(A['state']['duration'])
        for label,p in payload.items():
            m=np.asarray(p['known_minutes']);pool=np.asarray(p['unresolved_pool_by_team'])
            if p['identities_assigned'] or p['lineup_witness'] is not None:raise ValueError('FICTITIOUS_UNRESOLVED_IDENTITIES')
            for t,indices in enumerate(A['team_indices']):np.testing.assert_allclose(m[:,indices].sum(axis=1)+pool[:,t],5*length,atol=1e-7,rtol=0)
    for r in counts:
        if r.get('oracle') and r.get('pregame_source_qualified'):raise ValueError('ORACLE_SOURCE_CONTAMINATION')
    try:real_forecast_metrics(counts)
    except ValueError:real_gate='BLOCKED-BY-DATA'
    else:raise ValueError('RECONSTRUCTED_INPUTS_ACCEPTED_AS_REAL')
    pairs={}
    for label in ('C_ORACLE','D_RAW'):
        pairs[label]={}
        for baseline in ('A','J0'):
            pairs[label][baseline]={}
            for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
                rows={}
                for r in counts:
                    if r['model'] in (label,baseline) and r['stat']==stat:rows.setdefault((r['game_id'],r['player_id']),{})[r['model']]=r
                matched=[dict(contract_id='/'.join(k)+'/'+stat,event_id=k[0],date=v[baseline]['date'],delta=v[label]['crps']-v[baseline]['crps']) for k,v in rows.items() if set(v)=={label,baseline}]
                pairs[label][baseline][stat]={c:paired_bootstrap(matched,cluster=c,draws=1000) for c in ('date','game')}
    unique={(r['game_id'],r['player_id'],r['team_id']) for r in load(root/'candidate_ledger.json.gz')}
    freeze(args.output,dict(status='PASSED_STRUCTURAL_AND_SCORE_VALIDATION_ONLY',scenario_boundary_checks=scenario_checks,
        event_scenarios_checked=events,count_crps_checks=crps_checks,max_count_crps_difference=max_error,
        raw_games_correctly_failing_rotation=raw_conservation_failures,complete_oracle_games=24-len(load(root/'C_oracle_abstentions.json')),
        complete_oracle_matched_n=summary['common_matched_n'],real_forecast_metrics_gate=real_gate,unique_candidate_player_team_games_including_missed=len(unique),
        paired_count_crps=pairs,independent_statistical_review='PENDING_EXTERNAL_REVIEW',validation_authorship='Author-run separate pass, using unchanged WS4 #139 implementation; not independent signoff'))
    print(json.dumps(dict(boundaries=scenario_checks,event_scenarios=events,count_crps_checks=crps_checks,max_error=max_error)))

if __name__=='__main__':main()
