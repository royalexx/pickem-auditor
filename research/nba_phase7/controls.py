"""Retain frozen controls without manufacturing source-qualified Phase 7 scores."""
from pathlib import Path
from research.nba_phase6.run import load,mean_metrics
from v2.nba_joint.forecast import freeze
from v2.nba_joint.common import STATS


def main():
    root=Path('research/nba_phase7/evidence');original=load('research/nba_joint_v01/results/scores.json.gz');phase6=load('research/nba_phase6/results/count_scores.json.gz')
    common={(r['game_id'],r['player_id']) for r in phase6 if r['model']=='C_ORACLE'}
    controls={}
    for label in ('F0','J0','J1','J2','D_RAW','C_ORACLE'):
        source=phase6 if label in ('D_RAW','C_ORACLE') else original
        rows=[r for r in source if r['model']==label and (r.get('split')=='test' or source is phase6)]
        controls[label]={'all_available':{s:mean_metrics([r for r in rows if r['stat']==s]) for s in STATS},
            'identical_complete_oracle_intersection':{s:mean_metrics([r for r in rows if r['stat']==s and (r['game_id'],r['player_id']) in common]) for s in STATS}}
    freeze(root/'frozen_control_comparisons.json',dict(schema='NBAPhase7FrozenControls/1',historical_only=True,new_prospective_comparison_n=0,
        controls=controls,F=dict(status='BLOCKED-BY-DATA',eligible_comparison_n=0,stat_metrics={s:None for s in STATS}),
        note='No original/Phase 6 retrospective or oracle rows enter the real-pregame cohort. All means/variance/interval/zero/tail metrics remain frozen diagnostic controls.'))

if __name__=='__main__':main()
