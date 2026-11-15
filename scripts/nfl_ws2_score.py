#!/usr/bin/env python3
"""Postsettlement scoring only; never imported by the pregame WS2 runner."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.contracts import EventProbabilities, canonical_hash, finite
from v2.nfl_marginal_shadow import Law, count_crps
from nfl_ws2_shadow import freeze_report, sha


def summarize(rows):
    if not rows:
        return {"n": 0}
    n=len(rows)
    return {"n":n, "games":len({r['event_id'] for r in rows}),
        "brier":sum((r['p']-r['y'])**2 for r in rows)/n,
        "log_loss":sum(-math.log(max(1e-15,r['p'] if r['y'] else 1-r['p'])) for r in rows)/n,
        "mean_over":sum(r['p'] for r in rows)/n,
        "actual_over":sum(r['y'] for r in rows)/n,
        "signed_over_residual":sum(r['p']-r['y'] for r in rows)/n,
        "selected_over_fraction":sum(r['p']>.5 for r in rows)/n,
        "tie_fraction":sum(r['p']==.5 for r in rows)/n,
        "confidence_interval":None,
        "uncertainty_status":"single exposed or prospective slate descriptive only; no IID prop interval or promotion"}


def evaluate(forecast, settlements):
    """Match complete original quote objects; pushes and voids remain separate.

    Settlements are supplied offline with original quote identity and official
    source IDs. This method verifies identity, not official-source authenticity.
    """
    index={}
    for s in settlements:
        key=canonical_hash(s['quote'])
        if key in index:
            raise ValueError('duplicate_settlement_contract')
        if not s.get('source_id'):
            raise ValueError('settlement_source_id_missing')
        index[key]=s
    binary=defaultdict(dict)
    distributions=defaultdict(list)
    counts=Counter()
    for r in forecast['forecast_rows']:
        key=canonical_hash(r['quote'])
        s=index.get(key)
        counts['original_forecast_contracts']+=1
        if s is None:
            counts['unmatched']+=1;continue
        if s.get('status')=='void':
            counts['void']+=1;continue
        if s.get('status')!='verified':
            counts['unverified']+=1;continue
        if key in binary:
            # A duplicate original quote was preserved as a rejection by runner.
            counts['duplicate_input_quote_not_scored']+=1;continue
        binary[key]={}
        q=r['quote']; y=finite(s['actual'],'actual')
        if not y.is_integer() or (q['stat_key'] not in ('passing yards','rushing yards','receiving yards') and y<0):
            raise ValueError('settled_statistic_support_violation')
        if q['stat_key']=='anytime touchdown' and y not in (0,1):
            raise ValueError('binary_statistic_support_violation')
        outcome='over' if y>q['line'] else 'under' if y<q['line'] else 'push'
        counts['matched:'+outcome]+=1
        models={**r['models'], **r['controls']}
        for model,p in models.items():
            if p.get('status')=='unavailable':
                counts['unavailable:'+model]+=1;continue
            cond=p.get('p_over_given_no_push')
            if cond is None and p.get('q_over') is not None and p.get('q_under') is not None:
                total=p['q_over']+p['q_under']
                cond=p['q_over']/total if total else None
            if outcome!='push' and cond is not None:
                if not 0<=cond<=1 or not math.isfinite(cond):
                    raise ValueError('invalid_probability_in_frozen_output')
                binary[key][model]=dict(p=cond,y=int(outcome=='over'),event_id=q['event_id'],stat=q['stat_key'])
            if all(p.get(k) is not None for k in ('q_over','q_under','q_push')):
                prob=EventProbabilities(p['q_over'],p['q_under'],p['q_push'])
                value={'three_outcome_brier':sum((v-int(name==outcome))**2 for name,v in [('over',prob.over),('under',prob.under),('push',prob.push)]),
                       'three_outcome_log_loss':-math.log(max(1e-15,getattr(prob,outcome)))}
                if p.get('kind') in ('empirical','poisson','gamma_poisson','hurdle_geometric'):
                    law=Law(p['kind'],p['parameters'],p['mean'],p['variance'])
                    value['negative_log_predictive_mass']=-math.log(max(1e-15,law.pmf(y)))
                    if q['stat_key'] not in ('passing yards','rushing yards','receiving yards'):
                        value.update(count_crps(law,y))
                distributions[(q['stat_key'],model)].append(value)
    per_market={}
    stats=sorted({v['stat'] for b in binary.values() for v in b.values()} | {stat for stat,_ in distributions})
    for stat in stats:
        market={}
        names=sorted({m for b in binary.values() for m,v in b.items() if v['stat']==stat} | {m for st,m in distributions if st==stat})
        for model in names:
            rows=[b[model] for b in binary.values() if model in b and b[model]['stat']==stat]
            pairs={}
            for control in ('frozen_60_40','market_only'):
                matched=[b for b in binary.values() if model in b and control in b and b[model]['stat']==stat]
                a=summarize([b[model] for b in matched]);c=summarize([b[control] for b in matched])
                pairs[control]={'candidate':a,'control':c,'paired_brier_difference':a['brier']-c['brier'] if a['n'] else None}
            d=distributions.get((stat,model),[])
            metrics={metric:{'n':len(vs),'mean':sum(vs)/len(vs)} for metric in sorted({k for v in d for k in v}) if (vs:=[v[metric] for v in d if metric in v])}
            market[model]={'all_available_binary':summarize(rows),'matched_controls':pairs,'distribution_metrics':metrics}
        per_market[stat]=market
    return {'schema':'nfl-ws2-postsettlement-score-v1','forecast_sha256':canonical_hash(forecast),
            'denominators':dict(counts),'per_market':per_market,
            'evidence_class':forecast.get('evidence_class','source-authentication-not-established; inspect original freeze before prospective classification'),
            'settlement_source_authentication':'not independently verified by this offline scorer',
            'promotion_allowed':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--forecast',type=Path,required=True)
    p.add_argument('--settlements',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    raw=a.forecast.read_bytes();labels=a.settlements.read_bytes()
    result=evaluate(json.loads(raw),json.loads(labels))
    result.update(original_forecast_file_sha256=sha(raw),settlement_file_sha256=sha(labels))
    print(json.dumps(freeze_report(result,a.out)))


if __name__=='__main__':main()
