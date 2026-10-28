#!/usr/bin/env python3
"""Phase 4: read-only chronological forecasting validation, never model deployment.

Use frozen pregame snapshot predictions, immutable Bayesian/MC sidecars and
verified postgame settlement timestamps. Never recreate old Bayesian forecasts
from today's game history, train on post-holdout outcomes, or publish tiers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import posterior_mc_shadow as shadow
import posterior_mc_audit as old_audit

VERSION = 'chronological-validation-v1'
TORONTO = ZoneInfo('America/Toronto')
OUTCOMES = ('win','push','loss')
WEIGHT_A = .70                   # diagnostic only; never a deployed weight
MIN_SCOPE = 30
TRAIN_N = 300                    # minimum historical events before a calibrator is assessed
TRAIN_DAYS = 20
HOLDOUT_N = 100
HOLDOUT_DAYS = 20
BOOTSTRAPS = 500
EPS = 1e-12
TEMPERATURES = (1.0,.7,.8,.9,1.1,1.2,1.35,1.5,1.75,2.,2.5)
PAIR_DEFINITIONS = (
    ('legacy_a','bayes_a'),('legacy_b','bayes_b'),
    ('legacy_mix70','bayes_mix70'),('bayes_a','mc_a'),
    ('bayes_b','mc_b'),('bayes_mix70','mc_mix70'),
    ('legacy_mix70','mc_mix70'),
)


def timestamp(value):
    if not isinstance(value,str):
        raise ValueError('missing_timezone_timestamp')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('naive_timestamp')
    return parsed.astimezone(timezone.utc)


def probability(win,push):
    if isinstance(win,bool) or isinstance(push,bool):
        return None
    try:
        win,push=float(win),float(push)
    except (ValueError,TypeError):
        return None
    if any(not math.isfinite(v) for v in (win,push)) or not (0<=win<=1 and 0<=push<=1 and win+push<=1+1e-10):
        return None
    return (win,push,max(0.,1-win-push))


def blend(a,b):
    if a is None or b is None:return None
    return tuple(WEIGHT_A*x+(1-WEIGHT_A)*y for x,y in zip(a,b))


def score(p,outcome):
    if p is None:return None
    target=OUTCOMES.index(outcome)
    return (-math.log(max(EPS,p[target])),
            sum((v-int(i==target))**2 for i,v in enumerate(p)))


def original_key(row):
    """One independent pregame forecast per event/player/stat/side/line.

    Snapshot run IDs can change for successive 4pm re-collections. Choose the
    earliest forecast, while retaining run_id for an exact sidecar join.
    """
    event=str(row.get('event_id') or row.get('matchup') or '')
    player=str(row.get('player_id') or '')
    if not event or not player:
        raise ValueError('ambiguous_event_or_player_identity')
    return tuple(str(row.get(k) or '') for k in ('sport','game_date'))+(
        str(row.get('event_id_namespace') or ''),event,player,
        str(row.get('stat') or ''),str(row.get('side') or ''),
        str(row.get('reference_line')))


def read_sidecars(directory, *, version, engine=None):
    """Reject source corruption and identity clashes instead of silent wins."""
    records={}
    folder=Path(directory)
    for file in sorted(folder.glob('*.jsonl')) if folder.is_dir() else ():
        if file.stem!=file.stem[:10] or not _date_str(file.stem):
            raise ValueError('unexpected_sidecar_filename')
        for item in shadow._read(file):
            if (item.get('version')!=version or item.get('publication_eligible') is not False
                    or item.get('game_date')!=file.stem):
                raise ValueError('invalid_phase4_source_sidecar')
            key=(shadow.ashad._identity(item) if engine=='A' else shadow.identity(item))
            if key in records:
                if records[key]!=item:raise ValueError('conflicting_source_sidecar')
                raise ValueError('duplicate_source_sidecar')
            records[key]=item
    return records


def _date_str(x):
    try:return date.fromisoformat(x).isoformat()==x
    except (ValueError,TypeError):return False


def _sidecar_model(item, *, expected, parent=None):
    if not isinstance(item,dict) or item.get('status')!='forecast':
        return None
    if item.get('version')!=expected or item.get('publication_eligible') is not False:
        return None
    if not item.get('source_digest'):
        return None
    if parent is not None:
        if item.get('source_digest')!=parent.get('source_digest'):
            return None
    return probability(item.get('q_win'),item.get('q_push'))


def _snapshot_models(row,a,b,mc):
    ea=row.get('engine_a') or {}
    eb=row.get('engine_b') or {}
    if not isinstance(ea,dict):ea={}
    if not isinstance(eb,dict):eb={}
    models={}
    models['legacy_a']=probability(ea.get('q_win_robust'),ea.get('q_push_robust')) if ea.get('version')=='history-v5' else None
    models['legacy_b']=probability(eb.get('q_win'),eb.get('q_push')) if eb.get('version')=='scouting-v7' else None
    # The 70/30 mixture is diagnostic. Never imply it was the published forecast.
    if (ea.get('observation_ids_verified') is True and not ea.get('sample_block') and
            eb.get('baseline_origin')=='collector_observations' and eb.get('reliable') is True and
            not eb.get('abstain')):
        models['legacy_mix70']=blend(models['legacy_a'],models['legacy_b'])
    else:models['legacy_mix70']=None
    models['production']=probability(row.get('q_win'),row.get('q_push'))
    models['bayes_a']=_sidecar_model(a,expected='history-bayes-v1')
    models['bayes_b']=_sidecar_model(b,expected='usage-bayes-v1')
    models['bayes_mix70']=blend(models['bayes_a'],models['bayes_b'])
    for engine in ('A','B'):
        name='mc_'+engine.lower()
        data=(mc.get('engines') or {}).get(engine) if isinstance(mc,dict) else None
        parent=(a if engine=='A' else b)
        value=None
        if (isinstance(data,dict) and data.get('status')=='forecast'
                and data.get('version')=='posterior-mc-v1'
                and data.get('publication_eligible') is False and
                data.get('bayesian_parent_version')==('history-bayes-v1' if engine=='A' else 'usage-bayes-v1')
                and parent is not None and data.get('source_digest')==parent.get('source_digest')):
            analytic=_sidecar_model(parent,expected=data['bayesian_parent_version'])
            if analytic is not None:
                try:
                    matches=(abs(float(data['analytic_q_win'])-analytic[0])<1e-9 and
                             abs(float(data['analytic_q_push'])-analytic[1])<1e-9)
                except (TypeError,ValueError):matches=False
                if matches:value=probability(data.get('q_win'),data.get('q_push'))
        models[name]=value
    models['mc_mix70']=blend(models['mc_a'],models['mc_b'])
    return models


def _source_rows(original, directories):
    a=read_sidecars(directories['a'],version='history-bayes-v1',engine='A')
    b=read_sidecars(directories['b'],version='usage-bayes-v1',engine='B')
    mc=read_sidecars(directories['mc'],version='posterior-mc-v1')
    counters=Counter()
    eligible={}
    for row in shadow._read(original):
        counters['source_rows']+=1
        if row.get('outcome') not in OUTCOMES or row.get('actual_stat') is None:
            counters['unsettled']+=1;continue
        try:
            start=timestamp(row.get('event_start'))
            forecast=timestamp(row.get('forecast_at'))
            settled=timestamp(row.get('settled_at'))
            side=row.get('side');line=float(row['reference_line'])
            actual=float(row['actual_stat'])
            if (not all(math.isfinite(x) for x in (line,actual)) or side not in ('over','under')
                    or not forecast<start<=settled
                    or start.astimezone(TORONTO).date().isoformat()!=row.get('game_date')):
                counters['invalid_timing_or_stat']+=1;continue
            outcome=('push' if abs(actual-line)<1e-9 else
                     'win' if (actual>line)==(side=='over') else 'loss')
            if row['outcome']!=outcome:
                counters['outcome_mismatch']+=1;continue
            key=original_key(row)
        except (KeyError,ValueError,TypeError,OverflowError):
            counters['missing_timestamp_or_identity']+=1;continue
        record=eligible.get(key)
        if record is None or forecast<record['_forecast']:
            eligible[key]={**row,'_forecast':forecast,'_start':start,'_settled':settled}
        elif forecast==record['_forecast'] and row!={
                k:v for k,v in record.items() if not k.startswith('_')}:
            raise ValueError('conflicting_duplicate_pregame_forecast')
        else:counters['duplicate_later_pregame']+=1
    # Train/evaluate only earliest qualifying snapshots; do not pick a
    # better-looking later model after knowing results.
    result=[]
    for row in eligible.values():
        models=_snapshot_models(row,
            a.get(shadow.ashad._identity(row)),
            b.get(shadow.identity(row)),
            mc.get(shadow.identity(row)))
        result.append({'date':row['game_date'],'sport':row['sport'],
            'stat':row['stat'],'side':row['side'],
            'tier':str(row.get('final_rank') or 'Unknown'),
            'game':str(row.get('event_id') or row.get('matchup') or ''),
            'outcome':row['outcome'],'at':row['_forecast'],'settled_at':row['_settled'],
            'model':models,
            'context_applied':(row.get('shared_context') or {}).get('applied') is True,
            'role_change':(row.get('inputs') or {}).get('role_change') is True,
            'closing_q':row.get('closing_q_market'),
            'closing_line':row.get('closing_line'),
            'reference_line':row.get('reference_line')})
    result.sort(key=lambda r:(r['date'],r['at'],r['sport'],r['stat'],r['game'],r['side']))
    counters['distinct_verified_pregame_settlements']=len(result)
    counters['bayesian_a_covered']=sum(r['model']['bayes_a'] is not None for r in result)
    counters['bayesian_b_covered']=sum(r['model']['bayes_b'] is not None for r in result)
    counters['monte_carlo_both_covered']=sum(r['model']['mc_mix70'] is not None for r in result)
    return result,dict(sorted(counters.items()))


def _metrics(records,model):
    scored=[(score(r['model'].get(model),r['outcome']),r) for r in records]
    scored=[(s,r) for s,r in scored if s is not None]
    if not scored:
        return {'n':0,'status':'no_precommitted_forecasts','log_loss':None,
                'brier_3class':None,'dates':0,'pushes':0,'calibration_error':None}
    predictions=[(r['model'][model][0],int(r['outcome']=='win')) for _,r in scored]
    bins=[]
    for lo in range(0,10):
        subset=[(p,y) for p,y in predictions if lo/10<=p<((lo+1)/10 if lo<9 else 1.0000001)]
        if subset:
            bins.append({'bin':f'{lo/10:.1f}-{(lo+1)/10:.1f}',
                         'n':len(subset),'mean_q_win':mean(p for p,y in subset),
                         'win_rate':mean(y for p,y in subset),
                         'status':'descriptive' if len(subset)<MIN_SCOPE else 'sufficient_bin'})
    ece=sum(b['n']*abs(b['mean_q_win']-b['win_rate']) for b in bins)/len(scored)
    return {'n':len(scored),'dates':len({r['date'] for s,r in scored}),
        'pushes':sum(r['outcome']=='push' for s,r in scored),
        'status':'descriptive_only' if len(scored)<HOLDOUT_N else 'descriptive_not_deployment_approved',
        'log_loss':mean(s[0] for s,r in scored),
        'brier_3class':mean(s[1] for s,r in scored),
        'calibration_error':ece,'reliability_bins':bins}


def _paired(records,left,right):
    pairs=defaultdict(list)
    for row in records:
        p=row['model']
        l,r=score(p.get(left),row['outcome']),score(p.get(right),row['outcome'])
        if l is not None and r is not None:
            pairs[row['date']].append((r[0]-l[0],r[1]-l[1]))
    days=sorted(pairs)
    flat=[v for day in days for v in pairs[day]]
    if not flat:
        return {'n':0,'dates':0,'status':'no_common_cohort'}
    result={'n':len(flat),'dates':len(days),
        'log_loss_delta_challenger_minus_control':mean(v[0] for v in flat),
        'brier_delta_challenger_minus_control':mean(v[1] for v in flat)}
    if len(flat)<HOLDOUT_N or len(days)<HOLDOUT_DAYS:
        result.update(status='underpowered',ci95_log_loss_delta=None,
                      ci95_brier_delta=None,positive_improvement_not_established=True)
        return result
    rng=random.Random(int.from_bytes(hashlib.sha256(
        (left+'|'+right+'|'+str(days)).encode()).digest()[:8],'big'))
    samples=[[],[]]
    for _ in range(BOOTSTRAPS):
        selected=[v for day in rng.choices(days,k=len(days)) for v in pairs[day]]
        samples[0].append(mean(v[0] for v in selected))
        samples[1].append(mean(v[1] for v in selected))
    intervals=[]
    for values in samples:
        ordered=sorted(values)
        intervals.append([ordered[12],ordered[487]])
    result.update(status='diagnostic_held_out',ci95_log_loss_delta=intervals[0],
                  ci95_brier_delta=intervals[1],
                  positive_improvement_not_established=intervals[0][1]>=0)
    return result


def temperature(p,t):
    if not 0<t or p is None:raise ValueError('invalid_temperature')
    weights=[x**(1/t) for x in p]
    total=sum(weights)
    if total<=0:raise ValueError('undefined_temperature')
    return tuple(x/total for x in weights)


def _fit_temperature(training,model):
    vals=[(row['model'].get(model),row['outcome']) for row in training]
    vals=[(p,y) for p,y in vals if p is not None]
    if len(vals)<TRAIN_N or len({r['date'] for r in training if r['model'].get(model) is not None})<TRAIN_DAYS:
        return None
    def loss(t):
        return mean(score(temperature(p,t),y)[0] for p,y in vals)
    return min(TEMPERATURES,key=lambda x:(loss(x),abs(x-1)))


def _walk_forward(records,model,training_days,holdout_days):
    """Fit temperature ONLY from distinct older dates settled before the test.

    The calibration *algorithm* is a diagnostic challenger; no calibration
    weights are written to runtime configuration or used by tier logic.
    """
    holdout=[]
    for day in holdout_days:
        batch=[r for r in records if r['date']==day and r['model'].get(model) is not None]
        if not batch:continue
        first_at=min(r['at'] for r in batch)
        past=[r for r in records if r['date']<day and r['settled_at']<first_at]
        fitted=_fit_temperature(past,model)
        if fitted is None:continue
        for r in batch:
            p=temperature(r['model'][model],fitted)
            holdout.append((score(p,r['outcome']),score(r['model'][model],r['outcome']),
                            r['date'],fitted))
    if not holdout:
        return {'status':'insufficient_prior_settled_calibration_history',
                'n':0,'calibration_deployed':False}
    sample_n=len(holdout);dates=len(set(v[2] for v in holdout))
    return {'status':'descriptive_walk_forward' if sample_n>=HOLDOUT_N and dates>=HOLDOUT_DAYS else 'underpowered',
            'n':sample_n,'dates':dates,
            'calibrated_log_loss':mean(v[0][0] for v in holdout),
            'raw_same_cohort_log_loss':mean(v[1][0] for v in holdout),
            'calibrated_brier':mean(v[0][1] for v in holdout),
            'raw_same_cohort_brier':mean(v[1][1] for v in holdout),
            'temperature_range':[min(v[3] for v in holdout),max(v[3] for v in holdout)],
            'calibration_deployed':False}


def _market(records):
    same=[];move=[]
    for r in records:
        try:
            close=float(r['closing_line']);line=float(r['reference_line'])
            if math.isfinite(close) and math.isfinite(line):
                move.append(close-line)
                p=float(r['closing_q'])
                if (abs(close-line)<=1e-9 and r['outcome']!='push' and
                    math.isfinite(p) and 0<p<1):
                    same.append((-math.log(p if r['outcome']=='win' else 1-p),r))
        except (TypeError,ValueError):continue
    return {'closing_line_observations':len(move),
            'mean_closing_minus_reference':mean(move) if move else None,
            'matched_same_line_nonpush_q':len(same),
            'same_line_binary_market_log_loss':mean(v[0] for v in same) if same else None,
            'caution':'Closing market probabilities are conditional binary and are not comparable to unconditional three-class scores. A closing-line change can invalidate price comparability.'}


def validate(original,*,a_dir,b_dir,mc_dir):
    records,coverage=_source_rows(original,{'a':a_dir,'b':b_dir,'mc':mc_dir})
    days=sorted({r['date'] for r in records})
    cutoff=max(1,min(len(days)-1,math.floor(len(days)*.70))) if len(days)>=2 else len(days)
    train_dates=days[:cutoff]
    test_dates=days[cutoff:]
    train=[r for r in records if r['date'] in train_dates]
    test=[r for r in records if r['date'] in test_dates]
    names=('production','legacy_a','legacy_b','legacy_mix70','bayes_a','bayes_b',
           'bayes_mix70','mc_a','mc_b','mc_mix70')
    model_metrics={name:_metrics(test,name) for name in names}
    paired={f'{l}_vs_{r}':_paired(test,l,r) for l,r in PAIR_DEFINITIONS}
    slices={}
    for attribute in ('sport','stat','tier','side','context_applied','role_change'):
        groups=defaultdict(list)
        for r in test:
            key=str(r[attribute]) if attribute!='stat' else f"{r['sport']}|{r['stat']}"
            groups[key].append(r)
        slices[attribute]={key:{'n':len(rows),
            'status':'descriptive' if len(rows)<MIN_SCOPE else 'reportable',
            'bayes_mix70':_metrics(rows,'bayes_mix70'),
            'mc_mix70':_metrics(rows,'mc_mix70'),
            'legacy_mix70':_metrics(rows,'legacy_mix70'),
            'pair_bayesian_vs_legacy':_paired(rows,'legacy_mix70','bayes_mix70'),
            'pair_mc_vs_bayesian':_paired(rows,'bayes_mix70','mc_mix70')}
            for key,rows in sorted(groups.items())}
    training_summary={'n':len(train),'days':len(train_dates),
        'first_day':train_dates[0] if train_dates else None,
        'last_day':train_dates[-1] if train_dates else None}
    holdout_summary={'n':len(test),'days':len(test_dates),
        'first_day':test_dates[0] if test_dates else None,
        'last_day':test_dates[-1] if test_dates else None}
    # Strict sample thresholds allow diagnostics without making claims of
    # successful predictive validity or enabling production promotion.
    qualified=(len(train)>=TRAIN_N and len(train_dates)>=TRAIN_DAYS and
               len(test)>=HOLDOUT_N and len(test_dates)>=HOLDOUT_DAYS)
    return {'schema':'phase4_chronological_validation_v1','version':VERSION,
        'status':'holdout_descriptive_only' if qualified else 'underpowered_or_no_prospective_shadow',
        'publication_eligible':False,'calibrated_for_production':False,
        'changes_model_weights':False,'changes_rankings':False,
        'diagnostic_blend_a':WEIGHT_A,
        'baseline_source':'timestamped_collector_pregame_forecasts_only',
        'historical_bayesian_backfill_allowed':False,
        'coverage':coverage,'split':{'method':'chronological_sealed_game_date_70_30',
            'train':training_summary,'holdout':holdout_summary,
            'holdout_sample_threshold_met':qualified},
        'holdout_models':model_metrics,'paired_holdout':paired,
        'calibration_by_model':{m:_walk_forward(records,m,train_dates,test_dates)
                                for m in ('legacy_a','legacy_b','legacy_mix70',
                                          'bayes_a','bayes_b','bayes_mix70','mc_a','mc_b','mc_mix70')},
        'holdout_slices':slices,
        'closing_market':_market(test),
        'limitations':[
           'Historical Bayesian and MC predictions are never backfilled after outcomes',
           'A/B share historical evidence; the diagnostic 70/30 blends are not independent votes',
           'Selection and sample limitations remain; no automatic tier or weight changes',
           'Small sport/stat/tier or reliability bins are explicitly descriptive',
           'Temperature scaling is strictly walk-forward and never deployed',
           'Matched-cohort bootstrap resamples game dates rather than treating correlated props as independent']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',default=str(shadow.ROOT/'data/prop_snapshots.jsonl'))
    parser.add_argument('--a-dir',default=str(shadow.ROOT/'data/bayesian_shadow'))
    parser.add_argument('--b-dir',default=str(shadow.ROOT/'data/bayesian_b_shadow'))
    parser.add_argument('--mc-dir',default=str(shadow.ROOT/'data/posterior_mc'))
    parser.add_argument('--out',default=str(shadow.ROOT/'reports/phase4_validation.json'))
    args=parser.parse_args(argv)
    report=validate(args.original,a_dir=args.a_dir,b_dir=args.b_dir,mc_dir=args.mc_dir)
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'coverage':report['coverage'],
        'holdout':report['split']['holdout'],'output':str(out)},sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
