#!/usr/bin/env python3
"""Independent read-only pooling and analytical comparison of synthetic J runs.

This reads only explicitly synthetic engineering outputs, never an NBA archive.
It does not fit anything, resample O, discard a scenario, or award a law contract.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

from scipy.stats import nbinom


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    summary=json.loads((a.input/'summary.json').read_bytes());fixed=json.loads((a.input/'fixed_inputs.json').read_bytes());reference=json.loads((a.input/'analytic_S_O_components.json').read_bytes())
    assert summary['observed_games']==0 and summary['predictive_validation_performed'] is False
    archive=a.input/'full_seed_outputs.jsonl.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==summary['raw_full_outputs_gzip_sha256']
    targets={x['scenario_id']:x for x in fixed['O']['scenarios']};players={x['player_id']:x for x in fixed['pregame']['players']}
    pooled=defaultdict(lambda:defaultdict(lambda:defaultdict(Fraction)));moments=defaultdict(lambda:defaultdict(list));seeds=[];paths=0
    digest=hashlib.sha256();semantic=hashlib.sha256();rate_attempts=0;event_attempts=0;tied=0
    stats=('points','rebounds','assists','threes','pr','pa','ra','pra')
    with gzip.open(archive,'rb') as stream:
        for line in stream:
            digest.update(line);row=json.loads(line);seeds.append(row['seed']);result=row['native_result'];bundle=result['bundle']
            assert len(bundle['scenarios'])==len(targets)
            assert {x['scenario_id'] for x in bundle['scenarios']}==set(targets)
            by_seed=defaultdict(lambda:defaultdict(float))
            for sc in bundle['scenarios']:
                prior=targets[sc['scenario_id']];assert sc['weight']==prior['weight']
                assert {x['player_id'] for x in sc['players']}==set(players)
                paths+=1;weight=Fraction(str(sc['weight']))
                for person in sc['players']:
                    original=next(x for x in prior['players'] if x['player_id']==person['player_id'])
                    for key in ('player_id','team_id','minutes','participation'):assert person[key]==original[key]
                    s=person['stats'];assert all(type(v) is int and v>=0 for v in s.values())
                    assert s['points']>=3*s['threes']
                    for combo,parts in [('pr',('points','rebounds')),('pa',('points','assists')),('ra',('rebounds','assists')),('pra',('points','rebounds','assists'))]:
                        assert s[combo]==sum(s[k] for k in parts)
                    for stat in stats:
                        pooled[person['player_id']][stat][s[stat]]+=weight
                        by_seed[person['player_id']][stat]+=float(weight)*s[stat]
            for pid,values in by_seed.items():
                for stat,value in values.items():moments[pid][stat].append(value)
            for audit in result['audit_rows']:
                for person in audit['integration']['P2_to_J_projection'].values():
                    assert person['rate_pair_attempts']==len(person['rejected_rate_pairs'])+1
                    rate_attempts+=person['rate_pair_attempts']
            # Published runner already retains every raw rejected draw; derive
            # denominator totals from those explicit arrays rather than success.
            counts=result.get('rejection_denominators')
            stable=dict(row);stable['native_result']=dict(result);stable['native_result'].pop('performance',None)
            semantic.update((json.dumps(stable,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
    assert len(seeds)==len(set(seeds))==256 and seeds==summary['plan']['seeds']
    assert paths==1024 and digest.hexdigest()==summary['raw_full_outputs_uncompressed_sha256']
    metrics=[];complete={}
    for pid,laws in pooled.items():
        complete[pid]={}
        for stat,law in laws.items():
            law={k:v/len(seeds) for k,v in law.items()};assert sum(law.values())==1
            complete[pid][stat]=[dict(value=k,mass=float(p)) for k,p in sorted(law.items())]
            if stat not in reference[pid]:continue
            c=reference[pid][stat];mean=sum(x['weight']*x['mean'] for x in c)
            observed=float(sum(k*p for k,p in law.items()))
            limit=max(law);target={k:sum(x['weight']*float(nbinom.pmf(k,x['shape'],x['success_probability'])) for x in c) for k in range(limit+1)}
            tail=sum(x['weight']*float(nbinom.sf(limit,x['shape'],x['success_probability'])) for x in c)
            tv=.5*(sum(abs(float(law.get(k,0))-target[k]) for k in range(limit+1))+tail)
            metrics.append(dict(player_id=pid,stat=stat,reference_played_conditional_fixed_O_mean=mean,J_mean=observed,mean_difference=observed-mean,mean_MCSE=statistics.stdev(moments[pid][stat])/math.sqrt(len(seeds)),TV=tv))
    assert len(metrics)==48 and sum(len(x) for x in complete.values())==96
    max_mean=max(abs(x['mean_difference']) for x in metrics);max_tv=max(x['TV'] for x in metrics)
    assert abs(max_mean-summary['max_absolute_mean_distortion'])<1e-10
    assert abs(max_tv-summary['max_empirical_TV_estimate'])<1e-10
    result=dict(schema='NBA_P6_INDEPENDENT_ACTUAL_MAP_REFERENCE_V4',analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),observed_games=0,independent_J_repetitions=256,weighted_paths=paths,O_resampled=False,scenarios_discarded=0,rate_pair_attempts=rate_attempts,raw_compressed_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),raw_uncompressed_sha256=digest.hexdigest(),semantic_replay_sha256_excluding_performance=semantic.hexdigest(),pmfs=96,all_normalized=True,max_absolute_mean_difference=max_mean,max_TV=max_tv,metrics=metrics,complete_pmfs=complete,reference_conditioning='Played-conditional fixed O kernel; genuine participation remains unverified/null; not an unconditional authenticated forecast.',contract_acceptance=False)
    with a.output.open('x') as handle:json.dump(result,handle,sort_keys=True,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics','complete_pmfs')},sort_keys=True))


if __name__=='__main__':main()
