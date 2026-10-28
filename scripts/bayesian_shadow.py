#!/usr/bin/env python3
"""Immutable pregame, source-verified Bayesian Engine A shadow forecasts.

Read existing forecasts, never modify them, and never upgrade ranks. Writes a
separate audit sidecar. A missing peer cohort remains unavailable, not guessed.
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
import usage_baseline as ub

ROOT = Path(__file__).resolve().parents[1]
TORONTO = ZoneInfo('America/Toronto')


def _parse(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None: raise ValueError('timestamp must have timezone')
    return result.astimezone(timezone.utc)


def _fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def evaluate(row, *, root):
    """One complete, pregame snapshot; never substitute later observations."""
    meta = {k: row.get(k) for k in ('forecast_at','game_date','sport','player','player_id','stat','side','reference_line','event_start','run_id')}
    output = {**meta, 'engine':'bayesian_a', 'version':be.VERSION,'publication_eligible':False}
    try:
        forecast_at=_parse(row['forecast_at'])
        start=_parse(row['event_start'])
        day=forecast_at.astimezone(TORONTO).date()
        if not forecast_at < start or day.isoformat() != row['game_date']:
            raise be.ModelUnavailable('missing_or_poststart_forecast')
        inputs=row.get('inputs')
        if not isinstance(inputs,dict) or not isinstance(inputs.get('scouting'),dict):
            raise be.ModelUnavailable('missing_source_owned_history_reference')
        candidate={**inputs,**{k:row[k] for k in ('sport','stat','team','player_id','game_date') if k in row}}
        if str(candidate.get('player_id') or '') != str(row.get('player_id') or '') or not candidate.get('player_id'):
            raise be.ModelUnavailable('player_identity_missing')
        with ub.using_directory(root):
            if not ub.verify_a(candidate, forecast_at):
                raise be.ModelUnavailable('engine_a_source_verification_failed')
            data=ub.load(candidate,forecast_at)
        allow_negative=row['stat'] in ('passing yards','rushing yards','receiving yards')
        values,ids=be.validated_values(data, before=day, allow_negative=allow_negative)
        peers=be.peers_from_cache(root,sport=row['sport'],stat=row['stat'],
                player_id=row['player_id'],cutoff=forecast_at,source_date=day)
        prediction=be.forecast(values,[v for v,_ in peers],dist=inputs['dist'],
                        line=row['reference_line'],side=row['side'],var_ratio=inputs.get('var_ratio'))
        if not row.get('engine_a') or row['engine_a'].get('version')!='history-v5':
            raise be.ModelUnavailable('baseline_engine_version_changed')
        # Historical-only shadow result; compare against unadjusted Engine A.
        baseline_probability=row['engine_a']['q_win_robust']
        output.update(status='forecast',q_win=prediction['q_win'],q_push=prediction['q_push'],
                      q_loss=prediction['q_loss'],posterior_mean=prediction['mean'],
                      posterior_mean_se=prediction['posterior_mean_se'],
                      baseline_q_win=baseline_probability,baseline_version='history-v5',
                      n_observations=prediction['n_observations'],peer_count=prediction['peer_count'],
                      distribution=prediction['distribution'],
                      posterior_parameters=prediction['posterior_parameters'],
                      population_prior=prediction['population_prior'],
                      hyperparameter_method='empirical_bayes_peer_pooling',
                      calibrated=False,
                      source_digest=data['content_sha256'],
                      input_fingerprint=_fingerprint({'subject':list(zip(ids,values)),
                        'peers':sorted([(ids,values) for values,ids in peers],key=lambda it:it[0])}),
                      notes=['no_market_features','no_context_features','shadow_only'])
    except (KeyError, ValueError, TypeError, OSError, OverflowError, be.ModelUnavailable) as exc:
        output.update(status='unavailable',reason=str(exc) if isinstance(exc,be.ModelUnavailable) else type(exc).__name__)
    return output


def _identity(row):
    return tuple(str(row.get(k)) for k in
        ('game_date','sport','player_id','stat','side','reference_line','forecast_at'))


def run(*, date, snapshots, data_root, output, receipt):
    path=Path(output)
    original=path.read_text(encoding='utf-8') if path.exists() else ''
    preserved=[]
    seen=set()
    for line in original.splitlines():
        if not line.strip():raise ValueError('INVALID_BAYESIAN_SHADOW_SIDECAR')
        row=json.loads(line)
        if row.get('game_date')!=date or row.get('version')!=be.VERSION or _identity(row) in seen:
            raise ValueError('INVALID_BAYESIAN_SHADOW_SIDECAR')
        seen.add(_identity(row))
        preserved.append(row)
    rows=[]
    for line in Path(snapshots).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        row=json.loads(line)
        if row.get('game_date')!=date or row.get('run_type')!='shadow':continue
        identity=_identity(row)
        if identity in seen:continue
        seen.add(identity)
        rows.append(evaluate(row,root=data_root))
    rows.sort(key=lambda r:(r.get('sport') or '',r.get('player') or '',r.get('stat') or '',r.get('side') or '',str(r.get('reference_line'))))
    result=dict(schema='bayesian_a_shadow_v1',date=date,model_version=be.VERSION,
                previously_recorded=len(preserved),new_rows=len(rows),
                forecast_count=sum(r['status']=='forecast' for r in rows),
                unavailable_count=sum(r['status']=='unavailable' for r in rows),
                total_rows=len(preserved)+len(rows),
                publication_eligible=False,production_forecasts_untouched=True,
                reasons={})
    for row in rows:
        if row['status']=='unavailable':
            reason=row['reason'];result['reasons'][reason]=result['reasons'].get(reason,0)+1
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=original+''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
    if rows or not path.exists():
        tmp=path.with_suffix('.tmp');tmp.write_text(payload,encoding='utf-8');os.replace(tmp,path)
    rp=Path(receipt);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',required=True)
    p.add_argument('--snapshots',default=str(ROOT/'data/prop_snapshots.jsonl'))
    p.add_argument('--data-root',default=str(ROOT/'data'))
    p.add_argument('--out')
    p.add_argument('--receipt',default=str(ROOT/'reports/bayesian_a_shadow_receipt.json'))
    args=p.parse_args(argv)
    datetime.strptime(args.date,'%Y-%m-%d')
    output=args.out or str(ROOT/'data/bayesian_shadow'/ (args.date+'.jsonl'))
    result=run(date=args.date,snapshots=args.snapshots,data_root=args.data_root,
               output=output,receipt=args.receipt)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
