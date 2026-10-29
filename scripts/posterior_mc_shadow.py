#!/usr/bin/env python3
"""Prospective Monte Carlo forecasts on top of immutable Phase 1/2 shadows.

Only read original pregame forecasts and previously created Bayesian A/B
sidecars. No markets, context modifiers, ranks, or new researcher evidence.
The results are append-only and stored independently of all four engines.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import bayesian_engine as be
import bayesian_usage as bu
import bayesian_shadow as ashad
import bayesian_b_shadow as bshad
import posterior_mc as mc
import usage_baseline as ub

ROOT=Path(__file__).resolve().parents[1]
KEYS=('game_date','sport','player_id','stat','side','reference_line','forecast_at','run_id')


def identity(row):
    return tuple(str(row.get(k)) for k in KEYS)


def _read(path):
    if not Path(path).is_file():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def _indexed(path, versions):
    """Recognize both legacy and audited NBA power-likelihood sidecar versions."""
    permitted={versions} if isinstance(versions,str) else set(versions)
    result={}
    for row in _read(path):
        key=identity(row)
        if row.get('version') not in permitted or row.get('publication_eligible') is not False or key in result:
            raise ValueError('INVALID_INPUT_BAYESIAN_SHADOW_SIDECAR')
        result[key]=row
    return result


def _valid_source(row, sidecar, root):
    """Revalidate exact original pregame collector snapshot for NB quadrature."""
    inputs=row.get('inputs')
    if not isinstance(inputs,dict) or not isinstance(inputs.get('scouting'),dict):
        raise be.ModelUnavailable('missing_original_collector_reference')
    at=bshad._stamp(row.get('forecast_at'))
    start=bshad._stamp(row.get('event_start'))
    if at>=start or row.get('game_date')!=at.astimezone(bshad.TZ).date().isoformat():
        raise be.ModelUnavailable('poststart_original_forecast')
    candidate={**inputs,**{k:row[k] for k in ('sport','stat','team','player_id','game_date')}}
    with ub.using_directory(root):
        if not ub.verify_a(candidate,at):
            raise be.ModelUnavailable('source_history_changed_or_unverified')
        source=ub.load(candidate,at)
    if source.get('content_sha256')!=sidecar.get('source_digest'):
        raise be.ModelUnavailable('source_digest_changed_after_forecast')
    return source,at


def _scope_ok(row, shadow, engine):
    if not shadow:
        raise be.ModelUnavailable('missing_bayesian_'+engine.lower()+'_sidecar')
    if shadow.get('status')!='forecast':
        raise be.ModelUnavailable('bayesian_'+engine.lower()+'_unavailable')
    if shadow.get('publication_eligible') is not False or shadow.get('calibrated') is True:
        raise be.ModelUnavailable('invalid_shadow_publication_flag')
    if not shadow.get('source_digest') or not shadow.get('inputs_hash',shadow.get('input_fingerprint')):
        raise be.ModelUnavailable('unverified_shadow_source_provenance')
    original=row.get('engine_a' if engine=='A' else 'engine_b')
    if not isinstance(original,dict) or original.get('version')!=('history-v5' if engine=='A' else 'scouting-v7'):
        raise be.ModelUnavailable('production_baseline_version_changed')
    at=bshad._stamp(row.get('forecast_at'))
    event=bshad._stamp(row.get('event_start'))
    if at>=event or row.get('game_date')!=at.astimezone(bshad.TZ).date().isoformat():
        raise be.ModelUnavailable('poststart_or_invalid_forecast')
    if not row.get('player_id') or not row.get('sport') or not row.get('stat'):
        raise be.ModelUnavailable('missing_forecast_identity')


def evaluate(row, a, b, *, root, min_draws=mc.MIN_DRAWS, max_draws=mc.MAX_DRAWS,
             target=mc.TARGET_HALF_WIDTH):
    fields={k:row.get(k) for k in KEYS}
    fields.update({k:row.get(k) for k in ('player','team','opponent','event_start')})
    result={**fields,'version':mc.VERSION,'status':'shadow_only',
            'publication_eligible':False,'calibrated':False,'engines':{}}
    for engine,shadow in [('A',a),('B',b)]:
        try:
            _scope_ok(row,shadow,engine)
            if shadow.get('version')==mc.NBA_PRIOR_VERSION:
                if row.get('sport')!='NBA':
                    raise be.ModelUnavailable('prior_power_shadow_not_nba')
                if shadow.get('distribution')=='negbin':
                    # Legacy reconstructors use unweighted histories and would
                    # silently produce the wrong latent rate distribution.
                    raise be.ModelUnavailable('weighted_prior_negbin_mc_requires_source_reconstruction')
            extras={}
            if shadow.get('distribution')=='negbin':
                source,at=_valid_source(row,shadow,root)
                before=at.astimezone(bshad.TZ).date()
                if engine=='A':
                    vals,ids=be.validated_values(source,before=before)
                    extras['values']=vals
                    # Guard against subject-history mutation and gross drift
                    # in stored posterior parameters, beyond the source SHA.
                    if len(vals)!=shadow.get('n_observations'):
                        raise be.ModelUnavailable('a_negbin_observation_count_changed')
                else:
                    pairs=bu.verified_pairs(source,before=before,
                            sport=row['sport'],stat=row['stat'])
                    peers=bu.peers_from_cache(root,sport=row['sport'],stat=row['stat'],
                            player_id=row['player_id'],forecast_at=at,source_date=before)
                    if len(peers)!=shadow.get('peer_count') or len(pairs)!=shadow.get('n_exposure_games'):
                        raise be.ModelUnavailable('b_negbin_peer_cohort_changed')
                    extras.update(pairs=pairs,peers=peers)
            simulated=mc.simulate(shadow,engine=engine,identity=fields,
                line=row['reference_line'],side=row['side'],
                draws=min_draws,max_draws=max_draws,target=target,**extras)
            result['engines'][engine]={**simulated,'status':'forecast',
                                      'source_digest':shadow['source_digest'],
                                      'bayesian_parent_version':shadow['version']}
        except (be.ModelUnavailable,ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError,OSError) as exc:
            result['engines'][engine]={'status':'unavailable',
                'reason':str(exc) if isinstance(exc,be.ModelUnavailable) else type(exc).__name__,
                'publication_eligible':False}
    return result


def run(*, date, original, a_sidecar, b_sidecar, root, output, receipt,
        min_draws=mc.MIN_DRAWS,max_draws=mc.MAX_DRAWS,target=mc.TARGET_HALF_WIDTH):
    path=Path(output)
    old=path.read_text(encoding='utf-8') if path.is_file() else ''
    recorded={}
    for line in old.splitlines():
        if not line.strip():
            raise ValueError('INVALID_MONTE_CARLO_SIDECAR')
        row=json.loads(line)
        key=identity(row)
        if row.get('version')!=mc.VERSION or row.get('publication_eligible') is not False or key in recorded:
            raise ValueError('INVALID_MONTE_CARLO_SIDECAR')
        recorded[key]=True
    count_before=len(recorded)
    a=_indexed(a_sidecar,mc.SUPPORTED_POSTERIOR_VERSIONS_A)
    b=_indexed(b_sidecar,mc.SUPPORTED_POSTERIOR_VERSIONS_B)
    created=[]
    for row in _read(original):
        if row.get('game_date')!=date or row.get('run_type')!='shadow':
            continue
        key=identity(row)
        if key in recorded:
            continue
        recorded[key]=True
        created.append(evaluate(row,a.get(key),b.get(key),root=root,
                      min_draws=min_draws,max_draws=max_draws,target=target))
    created.sort(key=lambda x:(x.get('sport') or '',x.get('player') or '',
                 x.get('stat') or '',x.get('side') or '',str(x.get('reference_line'))))
    summary={'schema':'posterior_mc_shadow_v1','date':date,'model_version':mc.VERSION,
        'previously_recorded':count_before,'new_rows':len(created),
        'total_rows':len(recorded),'publication_eligible':False,
        'production_forecasts_untouched':True,'engines':{}}
    for engine in ('A','B'):
        rows=[r['engines'][engine] for r in created]
        summary['engines'][engine]={
            'forecast_count':sum(r['status']=='forecast' for r in rows),
            'unavailable_count':sum(r['status']=='unavailable' for r in rows),
            'analytic_disagreements':sum(r.get('analytic_agreement') is False for r in rows),
            'reasons':{}}
        for item in rows:
            if item['status']=='unavailable':
                reasons=summary['engines'][engine]['reasons']
                reason=item['reason']
                reasons[reason]=reasons.get(reason,0)+1
    path.parent.mkdir(parents=True,exist_ok=True)
    if created or not path.is_file():
        tmp=path.with_suffix('.tmp')
        tmp.write_text(old+''.join(json.dumps(v,sort_keys=True,allow_nan=False)+'\n'
                    for v in created),encoding='utf-8')
        os.replace(tmp,path)
    rp=Path(receipt)
    rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',required=True)
    p.add_argument('--original',default=str(ROOT/'data/prop_snapshots.jsonl'))
    p.add_argument('--a-sidecar')
    p.add_argument('--b-sidecar')
    p.add_argument('--data-root',default=str(ROOT/'data'))
    p.add_argument('--out')
    p.add_argument('--receipt',default=str(ROOT/'reports/posterior_mc_receipt.json'))
    p.add_argument('--min-draws',type=int,default=mc.MIN_DRAWS)
    p.add_argument('--max-draws',type=int,default=mc.MAX_DRAWS)
    p.add_argument('--target-half-width',type=float,default=mc.TARGET_HALF_WIDTH)
    args=p.parse_args(argv)
    datetime.strptime(args.date,'%Y-%m-%d')
    a=args.a_sidecar or str(ROOT/'data/bayesian_shadow'/(args.date+'.jsonl'))
    b=args.b_sidecar or str(ROOT/'data/bayesian_b_shadow'/(args.date+'.jsonl'))
    output=args.out or str(ROOT/'data/posterior_mc'/(args.date+'.jsonl'))
    report=run(date=args.date,original=args.original,a_sidecar=a,b_sidecar=b,
        root=args.data_root,output=output,receipt=args.receipt,
        min_draws=args.min_draws,max_draws=args.max_draws,target=args.target_half_width)
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
