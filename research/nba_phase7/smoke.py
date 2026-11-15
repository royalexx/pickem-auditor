"""Safe fixture capture → identity ledger → participation → unchanged J2 → audit."""
import argparse
import json
from pathlib import Path
import resource
import time
from v2.nba_joint import synthetic_fixture,audit
from v2.nba_joint.common import sha,STATS
from v2.nba_joint.forecast import freeze
from research.nba_joint_v01.run import gzfreeze
from .fixtures import GAME,AT,fetch,supplements
from .pilot import capture_slot
from .participation import participation_aware_j2


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();cpu=time.process_time();supplement=supplements(root/'supplements')
    slot=dict(slot=1,toronto_date='2026-11-16',game=GAME,scheduled_freeze_at='2026-11-16T23:30:00Z')
    cap=capture_slot(slot,root/'fixture_pilot',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:AT,fixture_supplement=supplement)
    if cap['status']!='CAPTURED_F_BLOCKED':raise ValueError('FIXTURE_CAPTURE_LEDGER_FAILED:'+str(cap))
    g,_=synthetic_fixture();model=json.loads(Path('research/nba_joint_v01/results/model.json').read_text())
    probabilities=[]
    for p in g['players']:
        i=int(p['player_id'].split(':')[-1])%9
        probabilities.append(dict(player_id=p['player_id'],team_id=p['team_id'],eligible=True,probability=1. if i<5 else .5))
    layer=dict(game_id=g['game_id'],evidence_kind='synthetic_fixture',players=probabilities)
    o=participation_aware_j2(g,model,layer=layer,n=128,fixture=True);check=audit(o)
    gzfreeze(root/'fixture_scenarios.json.gz',o)
    freeze(root/'receipt.json',dict(status='PASSED_FIXTURE_ONLY',mode='synthetic_never_original',source_capture=cap,scenarios=128,violations=check['violations'],
        model_sha256=sha(model),output_sha256=o['output_sha256'],wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,source_qualified_forecasts=0,
        all_eight_stats={stat:dict(mean=float(o['stats'][stat].mean()),variance=float(o['stats'][stat].var()),observed_score=None) for stat in STATS},
        caveat='Fixture participant probabilities are explicit engineering assumptions; they are not fitted, calibrated or real source evidence.'))
    print(json.dumps(dict(status='PASSED_FIXTURE_ONLY',model_sha256=sha(model),scenarios=128,violations=check['violations'])))

if __name__=='__main__':main()
