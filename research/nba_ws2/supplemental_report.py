"""Source diagnostics and postgame-only stratification after locked replay."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.nba_ws2.run_experiment import load_population


def main():
    dest=Path('research/nba_ws2/results')
    predictions=pd.read_csv(dest/'matched_predictions.csv.gz',dtype={'game_id':str,'player_id':str})
    context=pd.read_csv(dest/'postgame_context_sample.csv',dtype={'game_id':str,'player_id':str})
    if context.duplicated(['game_id','player_id']).any():raise ValueError('DUPLICATE_CONTEXT')
    joined=predictions.merge(context,on=['game_id','player_id'],validate='one_to_one',how='inner',suffixes=('','_context'))
    groups={
        'starter_outcome_sample':joined.starter_outcome.eq(True),
        'bench_outcome_sample':joined.starter_outcome.eq(False),
        'substantial_blowout_outcome_ge20_sample':joined.final_margin_outcome>=20,
        'closer_game_outcome_lt20_sample':joined.final_margin_outcome<20,
    }
    metrics={}
    for group,mask in groups.items():
        rows=joined.loc[mask]
        metrics[group]={'n':len(rows),'games':int(rows.game_id.nunique()),
            'mean_actual_minutes':float(rows.workload.mean()),
            'models':{m:{k:float(rows[m+'_'+k].mean()) for k in ('mae','point_mae','crps','nlpd_rounded_bin','cover50','cover80','cover90')} for m in ('M0','M1','M2')}}
    rows,manifest=load_population('work/ws2_input')
    df=pd.DataFrame(rows);totals=df.groupby(['season','game_id','team']).workload.sum()
    nearest=240+25*np.maximum(0,np.rint((totals.to_numpy()-240)/25))
    rounded_error=totals.to_numpy()-nearest
    report={
        'evidence':'RETROSPECTIVE_POSTGAME_DESCRIPTIVE_ONLY',
        'sample_design':'32 equally spaced games by chronological date/game ID; selected without model scores; no context fed to model',
        'source_games_attempted':32,'source_games_retrieved':int(context.game_id.nunique()),
        'postgame_roster_entries':len(context),'explicit_dnp_entries':int(context.did_not_play_outcome.eq(True).sum()),
        'matched_conditional_played_entries':len(joined),
        'context_metrics':metrics,
        'population':{'rows':len(df),'games':int(df.game_id.nunique()),'players':int(df.player_id.nunique()),
            'minutes_quantiles':{str(q):float(df.workload.quantile(q)) for q in (.01,.05,.1,.25,.5,.75,.9,.95,.99)},
            'integer_minute_fraction':float(np.mean(df.workload==np.rint(df.workload))),
            'team_games':len(totals),'team_rounding_error_mae':float(np.mean(abs(rounded_error))),
            'max_absolute_team_rounding_error':float(np.max(abs(rounded_error))),
            'exact_team_total_fraction':float(np.mean(abs(rounded_error)<1e-8))},
        'not_measured':['True early exits: no injury/ejection timing labels; low-minutes proxy only',
            'Teammate absence effects: no authenticated historical pregame availability matrix',
            'Starter role changes as pregame inputs: sampled starters are postgame outcomes only',
            'Actual team back-to-back/rest: model uses days between player appearances; missing games conflate absence and rest',
            'Official OT periods: minute-total proxy only; summary status omits period',
            'Market ablation and team strength: no authenticated game spread archive',
            'Participation FPR/FNR: postgame DNP sample is not a frozen pregame eligible universe'],
        'audit_notes':['ESPN source responses fetched now may differ from archived source digests; this is reconstruction, never retrocertification',
            'All sampled margins and starters enter reporting only, never feature matrices']}
    (dest/'supplemental_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
