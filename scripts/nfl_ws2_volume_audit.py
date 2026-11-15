#!/usr/bin/env python3
"""Read-only replay audit of real WS2 ledgers. Never generates or rewrites forecasts."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path


def digest(raw):return hashlib.sha256(raw).hexdigest()
def instant(x):
    d=datetime.fromisoformat(x.replace('Z','+00:00'))
    assert d.tzinfo is not None
    return d

def audit(path):
    path=Path(path);m=json.loads(path.read_bytes());tables={}
    for name,ref in m['artifacts'].items():
        raw=Path(ref['path']).read_bytes()
        assert digest(raw)==ref['sha256'],('ARTIFACT_HASH',name)
        tables[name]=[json.loads(l) for l in raw.splitlines()]
        assert len(tables[name])==ref['rows']
    laws={}; seen=set();totals=Counter(); zeros=Counter();qb=Counter();reasons=Counter()
    for r in tables['distributions_and_abstentions']:
        key=tuple(r[k] for k in ('game_id','player_id','normalized_market','period','model_version'))
        assert key not in seen,'DUPLICATE_DISTRIBUTION_IDENTITY'
        seen.add(key)
        if r['status']=='abstention':reasons[r['abstention_reason']]+=1;continue
        assert instant(r['historical_input_availability'])<=instant(r['training_data_cutoff'])<=instant(r['forecast_at'])<instant(r['kickoff_at'])
        encoded=json.dumps(dict(pmf=r['pmf'],joint_outcomes=r['joint_outcomes']),sort_keys=True,
                           separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
        assert digest(encoded)==r['distribution_sha256'],'DISTRIBUTION_SHA256'
        pmf=dict(r['pmf']);joint=defaultdict(float)
        for x in r['joint_outcomes']:
            assert sum(x['components'].values())==x['value'],'COMPOSITE_IDENTITY'
            assert x['value']==int(x['value'])
            if not r['normalized_market'].endswith('yards'):assert x['value']>=0
            joint[x['value']]+=x['weight']
        assert set(joint)==set(pmf)
        assert all(math.isclose(joint[y],p,abs_tol=1e-12) for y,p in pmf.items())
        assert math.isclose(sum(pmf.values()),1,abs_tol=1e-12)
        mean=sum(y*p for y,p in pmf.items());variance=sum((y-mean)**2*p for y,p in pmf.items())
        assert math.isclose(mean,r['predictive_mean'],abs_tol=1e-10)
        assert math.isclose(variance,r['predictive_variance'],abs_tol=1e-8)
        assert math.isclose(pmf.get(0,0),r['zero_mass'],abs_tol=1e-12)
        assert r['model_sha256']==m['model_sha256']
        laws[(r['player_stat_id'],r['model_version'])]=r
        totals[(r['model_version'],r['normalized_market'])]+=1
        if r['zero_mass']>0:zeros[(r['model_version'],r['normalized_market'])]+=1
        if r['conditional_participation']=='starting_and_appearing':qb[(r['model_version'],r['normalized_market'])]+=1
    contracts=Counter();contract_seen=set()
    for r in tables['original_contract_evaluations']:
        key=(r['candidate_id'],r['model_version']);assert key not in contract_seen;contract_seen.add(key)
        if r['status']=='abstention':continue
        d=laws[(r['player_stat_id'],r['model_version'])]
        assert r['distribution_sha256']==d['distribution_sha256']
        expected=[sum(p for y,p in d['pmf'] if compare(y,r['line'])) for compare in
                  (lambda y,l:y>l,lambda y,l:y<l,lambda y,l:y==l)]
        for k,p in zip(('q_over','q_under','q_push'),expected):assert math.isclose(r[k],p,abs_tol=1e-12)
        assert math.isclose(sum(expected),1,abs_tol=1e-12)
        contracts[(r['model_version'],r['normalized_market'])]+=1
    return dict(status='REPLAY_AUDIT_PASSED',handoff_sha256=digest(path.read_bytes()),
        distribution_rows=len(laws),abstention_rows=sum(reasons.values()),
        contract_probability_rows=sum(contracts.values()),
        coverage=[dict(model=k[0],market=k[1],distributions=n,authentic_contract_probabilities=contracts[k],
                       distributions_with_zero_mass=zeros[k],qb1_distributions=qb[k]) for k,n in sorted(totals.items())],
        abstention_reasons=dict(reasons),canaries=len(tables['canaries']),
        independent_review=False,scope='independent_arithmetic_recomputation_by_same_implementer; no independent_reviewer_claim')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('handoff',type=Path)
    args=p.parse_args();print(json.dumps(audit(args.handoff),sort_keys=True))
