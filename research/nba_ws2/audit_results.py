"""Sequential evidence audit, no model selection or refitting.

Adds point-estimate uncertainty, stress-cohort uncertainty, weekly sensitivity,
source/output hashes and conservative adoption status to a separate receipt.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd
from research.nba_ws2.run_experiment import bootstrap_diff


def paired(base,challenger,cluster):
    return bootstrap_diff(pd.DataFrame({'crps':base}),pd.DataFrame({'crps':challenger}),cluster)


def main():
    dest=Path('research/nba_ws2/results');report=json.loads((dest/'report.json').read_text())
    df=pd.read_csv(dest/'matched_predictions.csv.gz',dtype={'game_id':str,'player_id':str})
    assert not df.duplicated(['game_id','player_id']).any()
    assert (df.last_observation_date < df.game_date).all()
    assert report['source_identity_exclusions']==68
    assert report['rows_loaded_raw']==report['rows_loaded']+report['source_identity_exclusions']
    assert len(df)==report['rows_test']
    model=json.loads((dest/'model.json').read_text());
    executed={}
    for path,expected in report['executed_code_hashes'].items():
        blob=subprocess.check_output(['git','show',report['code_commit']+':'+path])
        actual=hashlib.sha256(blob).hexdigest()
        if actual!=expected:raise AssertionError('EXECUTED_COMMIT_HASH_MISMATCH:'+path)
        executed[path]=actual
    week=pd.to_datetime(df.game_date).dt.to_period('W').astype(str)
    differences={}
    stress={}
    totals={}
    from research.nba_ws2.run_experiment import load_population,franchise_population
    raw,_=load_population('work/ws2_input');rows,_=franchise_population(raw)
    for r in rows:
        if r['season']=='2025':totals[r['game_id'],r['team']]=totals.get((r['game_id'],r['team']),0)+r['workload']
    ot=np.array([totals[g,t]>=257.5 for g,t in zip(df.game_id,df.team)])
    for name in ('M1','M2'):
        differences[name]={
            'point_mae_date':paired(df.M0_point_mae,df[name+'_point_mae'],df.game_date),
            'crps_week':paired(df.M0_crps,df[name+'_crps'],week)}
        stress[name]={}
        for cohort,ix in {'low_minute_outcome_le5':df.workload<=5,'inferred_overtime_outcome':ot}.items():
            s=df.loc[ix]
            stress[name][cohort]={
                'n':len(s),
                'coverage90_difference':paired(s.M0_cover90,s[name+'_cover90'],s.game_date),
                'crps_difference':paired(s.M0_crps,s[name+'_crps'],s.game_date)}
    archive=dest/'initial_unfiltered'/'matched_predictions.csv.gz'
    initial={'status':'SUPERSEDED_BY_IDENTITY_CORRECTION','initial_prediction_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'initial_model_commit':'6e5765e67a3dd6a69fe505960f07c0a59bb466d9',
        'note':'Original unfiltered numerical results preserved. Initial report executed_code_hashes were collected at completion while team-only sampler validation changed concurrently; use initial_model_commit for exact original fitting/score code. Corrected replay hashes are verified against its committed code.'}
    (dest/'initial_unfiltered'/'provenance_note.json').write_text(json.dumps(initial,indent=2)+'\n')
    audit={'status':'SEQUENTIAL_EXECUTABLE_AUDIT_NOT_INDEPENDENT_WS4_VALIDATION',
        'executed_code_commit_verified':report['code_commit'],'executed_code_hashes_verified':executed,
        'chronological_features_verified':True,'unique_player_games_verified':True,
        'source_exclusion_ledger_rows':68,'weekly_sensitivity_and_point_mae':differences,
        'stress_comparisons':stress,
        'adoption_decision':{name:{'overall_preregistered_statistical_gates':report['acceptance'][name],
            'adopt':False,'status':'HISTORICAL_AGGREGATE_GAIN_WITH_STRESS_REGRESSION',
            'reasons':['Material low-minute and/or overtime outcome-cohort coverage regression versus M0',
                'No authenticated pregame participation/roster validation',
                'Historical reconstruction and design exposure; independent prospective WS4 validation absent']} for name in ('M1','M2')},
        'no_claims':['No causal minutes/rate attribution','No per-minute outcome or prop-probability gain established',
                     'No economic edge or production promotion','Outcome-selected stress coverage is not expected to equal unconditional nominal coverage'],
        'distribution_tail_bound_beyond120':model['ot_probability']*model['ot_continuation']**14}
    (dest/'audit_receipt.json').write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
