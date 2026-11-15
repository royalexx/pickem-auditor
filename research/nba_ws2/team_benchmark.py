"""Synthetic contract/integrity benchmark; no historical predictive skill claim."""
from dataclasses import asdict
import json
from pathlib import Path
import resource
import time
import numpy as np
from v2.nba_opportunity import MinuteLaw, sample_team


def main():
    roster=[]
    # Fixed starter-like and bench-like workload fixture, summing 240 in mean.
    means=[34,33,32,30,28,24,20,17,12,10]
    for i,mean in enumerate(means):
        roster.append({'game_id':'fixture-game','team_id':'fixture-team','player_id':str(i),
            'active_roster_eligible':True,'participation_probability':1.,
            'distribution':asdict(MinuteLaw(mean,49 if i<5 else 81,.06,.15))})
    start=time.perf_counter();cpu=time.process_time()
    scenarios=sample_team(roster,seed=20261115,n=1000,ot_probability=.06,ot_continuation=.15,
        unusual_rotation_probability=.1)
    valid=[s for s in scenarios if s['valid']]
    raw=np.array([s['independent_team_total'] for s in valid]);expected=np.array([240+25*s['overtime_periods'] for s in valid])
    constrained=np.array([s['team_total'] for s in valid])
    delta=np.array([np.array(s['minutes'])-s['independent_minutes'] for s in valid])
    report={'evidence':'DETERMINISTIC_SYNTHETIC_FIXTURE_NOT_HISTORICAL_SKILL',
        'seed':20261115,'attempted':len(scenarios),'valid':len(valid),
        'independent_mean_absolute_team_error':float(np.mean(abs(raw-expected))),
        'independent_max_absolute_team_error':float(np.max(abs(raw-expected))),
        'independent_conservation_failure_rate':float(np.mean(abs(raw-expected)>1e-6)),
        'constrained_max_absolute_team_error':float(np.max(abs(constrained-expected))),
        'constrained_conservation_failure_rate':float(np.mean(abs(constrained-expected)>1e-6)),
        'mean_absolute_player_projection_adjustment':float(np.abs(delta).mean()),
        'five_on_court_violations':sum(len(seg['player_indices'])!=5 for s in valid for seg in s['lineup_segments']),
        'overtime_scenarios':sum(s['overtime_periods']>0 for s in valid),
        'max_overtime_periods':max(s['overtime_periods'] for s in valid),
        'unusual_rotation_scenarios':sum(s['rotation_state']=='unusual' for s in valid),
        'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
        'max_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'limitations':['projection changes marginal distributions','active-roster completeness externally supplied',
            'unusual-state probability is a fixture parameter, not an estimated real-world rate',
            'team allocation needs separate historical/prospective calibration']}
    dest=Path('research/nba_ws2/results');dest.mkdir(parents=True,exist_ok=True)
    (dest/'team_benchmark.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (dest/'team_scenario_fixture.json').write_text(json.dumps(scenarios[:3],indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
