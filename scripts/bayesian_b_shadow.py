#!/usr/bin/env python3
"""Immutable pregame Bayesian Engine B shadow runner.

Reads official shadow snapshots and verified collector game histories. Never
changes the existing scouting-v7 Engine B, grades, lines, or A/B blend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import bayesian_engine as be
import bayesian_usage as bu
import usage_baseline as ub

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('America/Toronto')


def _stamp(value):
    try:
        out=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if out.tzinfo is None:raise ValueError('timezone required')
        return out.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):
        raise be.ModelUnavailable('invalid_forecast_or_start_timestamp')


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,
                                 separators=(',',':')).encode()).hexdigest()


def identity(row):
    return tuple(str(row.get(k)) for k in
        ('game_date','sport','player_id','stat','side','reference_line','forecast_at','run_id'))


def evaluate(row, *, root):
    meta={k:row.get(k) for k in ('game_date','forecast_at','event_start','sport','team',
          'player','player_id','stat','side','reference_line','run_id')}
    result={**meta,'engine':'bayesian_b','version':bu.VERSION,
            'publication_eligible':False,'calibrated':False}
    try:
        at=_stamp(row.get('forecast_at'))
        start=_stamp(row.get('event_start'))
        if at>=start or row.get('game_date')!=at.astimezone(TZ).date().isoformat():
            raise be.ModelUnavailable('poststart_or_date_mismatched_snapshot')
        raw=row.get('inputs')
        if not isinstance(raw,dict) or not isinstance(raw.get('scouting'),dict):
            raise be.ModelUnavailable('missing_verified_scouting_reference')
        if not row.get('player_id') or not row.get('team'):
            raise be.ModelUnavailable('missing_player_or_team_identity')
        prior_b=row.get('engine_b')
        if not isinstance(prior_b,dict) or prior_b.get('version')!='scouting-v7':
            raise be.ModelUnavailable('incompatible_baseline_engine_b')
        candidate={**raw,**{k:row[k] for k in ('sport','stat','team','player_id','game_date')}}
        if not candidate['scouting'].get('historical_usage'):
            raise be.ModelUnavailable('missing_collector_owned_usage_reference')
        with ub.using_directory(root):
            if not ub.verify_a(candidate,at):
                raise be.ModelUnavailable('collector_production_history_unverified')
            source=ub.load(candidate,at)
        existing_digest=(prior_b.get('terms') or {}).get('history_digest')
        if existing_digest and existing_digest!=source.get('content_sha256'):
            raise be.ModelUnavailable('engine_b_source_digest_mismatch')
        source_day=at.astimezone(TZ).date()
        pairs=bu.verified_pairs(source,before=source_day,sport=row['sport'],stat=row['stat'])
        peers=bu.peers_from_cache(root,sport=row['sport'],stat=row['stat'],
                    player_id=row['player_id'],forecast_at=at,source_date=source_day)
        probability=bu.forecast(pairs,peers,
                    dist=raw['dist'],line=row['reference_line'],side=row['side'],
                    var_ratio=raw.get('var_ratio'),stat=row['stat'],sport=row['sport'])
        # For B, the source collector's production+workload path is the
        # only valid historical comparator (legacy narrative scenarios cannot qualify).
        baseline_q_win=prior_b.get('q_win') if prior_b.get('baseline_origin')=='collector_observations' else None
        baseline_q_push=prior_b.get('q_push') if baseline_q_win is not None else None
        result.update(status='forecast',q_win=probability['q_win'],q_push=probability['q_push'],
                      q_loss=probability['q_loss'],q_over=probability['q_over'],q_under=probability['q_under'],
                      mean=probability['mean'],workload_mean=probability['workload_mean'],
                      workload_sd=probability['workload_sd'],
                      conversion_mean=probability['conversion_mean'],conversion_se=probability['conversion_se'],
                      workload_posterior=probability['workload'],conversion_posterior=probability['conversion'],
                      negative_tail_mass=probability['negative_tail_mass'],
                      n_exposure_games=len(pairs),peer_count=len(peers),
                      baseline_version='scouting-v7',baseline_q_win=baseline_q_win,
                      baseline_q_push=baseline_q_push,baseline_reliable=prior_b.get('reliable') is True,
                      source_digest=source['content_sha256'],
                      inputs_hash=_hash({'subject':pairs,
                        'peers':sorted([p for p in peers],key=lambda items:items[0][0])}),
                      method=probability['predictive_method'],approximation=probability['approximation'],
                      notes=['workload_and_conversion_source_only','no_market_features',
                             'no_context_reweighting','no_tier_authority','shadow_only'])
    except (be.ModelUnavailable,KeyError,ValueError,TypeError,OSError,OverflowError,ZeroDivisionError) as exc:
        result.update(status='unavailable',reason=str(exc) if isinstance(exc,be.ModelUnavailable) else type(exc).__name__)
    return result


def run(*, date, snapshots, data_root, output, receipt):
    path=Path(output)
    old=path.read_text(encoding='utf-8') if path.is_file() else ''
    present={}
    for line in old.splitlines():
        if not line.strip():raise ValueError('INVALID_BAYESIAN_B_SHADOW_SIDECAR')
        item=json.loads(line)
        key=identity(item)
        if (item.get('game_date')!=date or item.get('version')!=bu.VERSION or
                item.get('publication_eligible') is not False or key in present):
            raise ValueError('INVALID_BAYESIAN_B_SHADOW_SIDECAR')
        present[key]=True
    original_count=len(present)
    new=[]
    for line in Path(snapshots).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        item=json.loads(line)
        if item.get('game_date')!=date or item.get('run_type')!='shadow':
            continue
        key=identity(item)
        if key in present:continue
        present[key]=True
        new.append(evaluate(item,root=data_root))
    new.sort(key=lambda r:(r.get('sport') or '',r.get('player') or '',r.get('stat') or '',
                            r.get('side') or '',str(r.get('reference_line'))))
    summary={'schema':'bayesian_b_shadow_v1','date':date,'model_version':bu.VERSION,
             'previously_recorded':original_count,'new_rows':len(new),
             'forecast_count':sum(x['status']=='forecast' for x in new),
             'unavailable_count':sum(x['status']=='unavailable' for x in new),
             'total_rows':len(present),'production_forecasts_untouched':True,
             'publication_eligible':False,'reasons':{}}
    for row in new:
        if row['status']=='unavailable':
            reason=row['reason'];summary['reasons'][reason]=summary['reasons'].get(reason,0)+1
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or new:
        tmp=path.with_suffix('.tmp')
        tmp.write_text(old+''.join(json.dumps(item,sort_keys=True,allow_nan=False)+'\n' for item in new),
                       encoding='utf-8')
        os.replace(tmp,path)
    target=Path(receipt);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',required=True)
    parser.add_argument('--snapshots',default=str(ROOT/'data/prop_snapshots.jsonl'))
    parser.add_argument('--data-root',default=str(ROOT/'data'))
    parser.add_argument('--out')
    parser.add_argument('--receipt',default=str(ROOT/'reports/bayesian_b_shadow_receipt.json'))
    args=parser.parse_args(argv)
    datetime.strptime(args.date,'%Y-%m-%d')
    result=run(date=args.date,snapshots=args.snapshots,data_root=args.data_root,
               output=args.out or str(ROOT/'data/bayesian_b_shadow'/(args.date+'.jsonl')),
               receipt=args.receipt)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
