#!/usr/bin/env python3
"""Prospective, immutable Monte Carlo vs analytic and legacy outcome audit.

Read pregame shadow forecasts plus *later verified* settled results. Summarize
proper three-class win/push/loss scores; never tune or authorize rankings.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import posterior_mc_shadow as runner

ROOT=Path(__file__).resolve().parents[1]
MIN_SCOPE=30
EPS=1e-12
OUTCOMES=('win','push','loss')


def _vector(win,push):
    if isinstance(win,bool) or isinstance(push,bool):
        return None
    try:
        w=float(win);p=float(push)
    except (ValueError,TypeError):
        return None
    if not (math.isfinite(w) and math.isfinite(p) and 0<=w<=1 and 0<=p<=1 and w+p<=1+1e-9):
        return None
    return (w,p,max(0.,1-w-p))


def _score(vector,label):
    if vector is None or label not in OUTCOMES:
        return None
    target=OUTCOMES.index(label)
    return {'log_loss':-math.log(max(EPS,vector[target])),
            'multiclass_brier':sum((p-int(i==target))**2 for i,p in enumerate(vector))}


def _summary(scores):
    if not scores:
        return {'n':0,'status':'insufficient_settled_shadow_samples',
                'log_loss':None,'multiclass_brier':None}
    return {'n':len(scores),'status':'descriptive_only_uncalibrated',
            'log_loss':sum(s['log_loss'] for s in scores)/len(scores),
            'multiclass_brier':sum(s['multiclass_brier'] for s in scores)/len(scores)}


def _paired_summary(rows):
    if not rows:
        return {'n':0,'status':'insufficient_common_cohort',
                'delta_log_loss_mc_minus_comparator':None,
                'delta_brier_mc_minus_comparator':None}
    return {'n':len(rows),'status':'descriptive_only_uncalibrated',
        'delta_log_loss_mc_minus_comparator':sum(mc['log_loss']-cmp['log_loss'] for mc,cmp in rows)/len(rows),
        'delta_brier_mc_minus_comparator':sum(mc['multiclass_brier']-cmp['multiclass_brier']
                                              for mc,cmp in rows)/len(rows)}


def audit(original, mc_directory):
    # Settled source is authoritative for actual outcomes; pregame forecast
    # timestamps and event-start times must be retained before joining.
    settled={}
    for row in runner._read(original):
        if row.get('outcome') not in OUTCOMES or row.get('actual_stat') is None:
            continue
        try:
            at=runner.bshad._stamp(row.get('forecast_at'))
            start=runner.bshad._stamp(row.get('event_start'))
            if at>=start:continue
        except (ValueError,runner.be.ModelUnavailable,TypeError):
            continue
        key=runner.identity(row)
        if key in settled and row['outcome']!=settled[key]['outcome']:
            raise ValueError('CONFLICTING_SETTLED_OUTCOMES')
        settled[key]=row
    scores=defaultdict(list);by_sport=defaultdict(list)
    by_stat=defaultdict(list);reasons=defaultdict(int)
    paired=defaultdict(list);paired_sport=defaultdict(list)
    matched=0; examined=0
    for path in sorted(Path(mc_directory).glob('*.jsonl')):
        for item in runner._read(path):
            examined+=1
            key=runner.identity(item)
            row=settled.get(key)
            if not row:
                continue
            matched+=1
            for engine in ('A','B'):
                prediction=(item.get('engines') or {}).get(engine) or {}
                if prediction.get('status')!='forecast':
                    reasons[f'{engine}:unavailable']+=1
                    continue
                if prediction.get('publication_eligible') is not False:
                    raise ValueError('INVALID_MONTE_CARLO_PUBLICATION_FLAG')
                original_engine=row.get('engine_a' if engine=='A' else 'engine_b') or {}
                competitors={
                    f'{engine}_mc':_vector(prediction.get('q_win'),prediction.get('q_push')),
                    f'{engine}_bayes_analytic':_vector(prediction.get('analytic_q_win'),
                                                         prediction.get('analytic_q_push')),
                    f'{engine}_legacy':_vector(
                        original_engine.get('q_win_robust') if engine=='A' else original_engine.get('q_win'),
                        original_engine.get('q_push_robust') if engine=='A' else original_engine.get('q_push'))}
                row_scores={}
                for name,vector in competitors.items():
                    score=_score(vector,row['outcome'])
                    if score is None:
                        reasons[f'{name}:invalid_probability']+=1
                        continue
                    row_scores[name]=score
                    scores[name].append(score)
                    by_sport[(name,row['sport'])].append(score)
                    by_stat[(name,row['sport'],row['stat'])].append(score)
                # Pair *only* the same settled pregame forecast on both sides.
                # Different source-coverage cohorts cannot establish gain.
                for comparator in ('bayes_analytic','legacy'):
                    name=f'{engine}_mc_vs_{comparator}'
                    if f'{engine}_mc' in row_scores and f'{engine}_{comparator}' in row_scores:
                        match=(row_scores[f'{engine}_mc'],row_scores[f'{engine}_{comparator}'])
                        paired[name].append(match)
                        paired_sport[(name,row['sport'])].append(match)
    return {
        'schema':'posterior_mc_audit_v1',
        'status':'descriptive_only' if matched else 'insufficient_settled_shadow_samples',
        'examined_shadow_predictions':examined,'matched_settled_forecasts':matched,
        'model_version':'posterior-mc-v1',
        'no_retraining':True,'publication_eligible':False,
        'comparators':{k:_summary(v) for k,v in sorted(scores.items())},
        'paired_comparisons':{k:_paired_summary(v) for k,v in sorted(paired.items())},
        'paired_by_sport':{f'{k}|{sport}':_paired_summary(v)
                           for (k,sport),v in sorted(paired_sport.items()) if len(v)>=MIN_SCOPE},
        'by_sport':{f'{a}|{b}':_summary(v) for (a,b),v in sorted(by_sport.items())
                    if len(v)>=MIN_SCOPE},
        'by_sport_stat':{f'{a}|{b}|{c}':_summary(v) for (a,b,c),v in sorted(by_stat.items())
                         if len(v)>=MIN_SCOPE},
        'excluded':dict(sorted(reasons.items())),
        'interpretation':'Descriptive prospective proper scores; A/B not independent; no automatic weight, gate or tier changes. Compare common matched cohorts only.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',default=str(ROOT/'data/prop_snapshots.jsonl'))
    p.add_argument('--mc-dir',default=str(ROOT/'data/posterior_mc'))
    p.add_argument('--out',default=str(ROOT/'reports/posterior_mc_audit.json'))
    args=p.parse_args(argv)
    report=audit(args.original,args.mc_dir)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
