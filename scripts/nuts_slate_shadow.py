#!/usr/bin/env python3
"""Read completed population NUTS artifacts and freeze prospective comparison rows.

GET-only discovery. Active/failed jobs are never downloaded or changed. Original
strict gates remain mandatory; these probabilities never enter production blend.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone, date
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

REPO='royalexx/pickem-auditor'
WORKFLOW='Precision 31-market research campaign (self-hosted)'
VERSION='population-nuts-slate-shadow-v1'
KEYS=('game_date','sport','player_id','stat','side','reference_line','forecast_at','run_id')


def instant(value):
    result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('timezone_required')
    return result.astimezone(timezone.utc)


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def identity(row):return tuple(str(row.get(k,'')) for k in KEYS)


def shared_contract_seed(row):
    """One deterministic NUTS integration stream for both sides of a contract.

    Side and per-side forecast_at are intentionally omitted: the original
    collector records Over and Under milliseconds apart. Including its
    timestamp produced different Monte Carlo samples and incoherent pair
    probabilities in the frozen November 8 NFL reception forecasts.
    The run/fixture/player/stat/line remain part of the seed identity.
    """
    keys=('run_id','game_date','sport','event_start','team','opponent',
          'player_id','stat','reference_line')
    contract={k:row.get(k) for k in keys}
    if any(contract[k] in (None,'') for k in keys):
        raise ValueError('missing_nuts_shared_contract_identity')
    line=contract['reference_line']
    if type(line) not in (int,float) or not math.isfinite(line):
        raise ValueError('invalid_nuts_shared_contract_line')
    contract['reference_line']=format(float(line),'.15g')
    return int.from_bytes(hashlib.sha256(json.dumps(
        contract,sort_keys=True,separators=(',',':')).encode()).digest()[:8],'big')


def canon_stat(stat):return 'saves' if stat=='goalie saves' else stat


def strict_manifest(m):
    d=m.get('diagnostics') or {}
    def finite(k,bound,lower=False):
        x=d.get(k)
        return (type(x) in (int,float) and math.isfinite(x) and
                (x>=bound if lower else x<=bound))
    return (m.get('schema')=='multisport_joint_fit_manifest_v1'
            and m.get('model_version')=='multisport-joint-bayes-v1'
            and m.get('family')=='count' and m.get('max_per_position')==0
            and m.get('diagnosed_all_player_and_opponent_effects') is True
            and m.get('sampler_chains')==4 and m.get('sampler_retained_draws_per_chain',0)>=2000
            and d.get('posterior_sampling_ok') is True
            and type(d.get('divergences')) is int and d['divergences']==0
            and finite('max_rhat',1.01) and finite('min_bulk_ess',400,True)
            and finite('minimum_bfmi',.30,True)
            and bool(m.get('source_digest')) and bool(m.get('players')))


def request(path,token,*,binary=False):
    return urllib.request.Request('https://api.github.com/repos/'+REPO+path,
        headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream' if binary else 'application/vnd.github+json',
                 'User-Agent':'pickem-validation-nuts','X-GitHub-Api-Version':'2022-11-28'})


def get_json(path,token,opener):
    with opener(request(path,token),timeout=90) as f:return json.load(f)


def completed_runs(runs):
    return [r for r in runs if r.get('name')==WORKFLOW and
            r.get('status')=='completed' and r.get('conclusion')=='success']


def extract_model(archive,folder,*,wanted):
    """Read manifest first; only extract an eligible exact model, with safe paths."""
    folder=Path(folder)
    with zipfile.ZipFile(archive) as z:
        manifests=[x for x in z.infolist() if PurePosixPath(x.filename).name=='manifest.json']
        accepted=[]
        for item in manifests:
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or item.file_size>3_000_000:
                raise ValueError('unsafe_model_manifest')
            m=json.loads(z.read(item))
            if (m.get('sport'),m.get('stat')) not in wanted or not strict_manifest(m):continue
            name=str(p.parent/'posterior.nc') if str(p.parent)!='.' else 'posterior.nc'
            info=z.getinfo(name)
            if not 0<info.file_size<1_500_000_000:raise ValueError('invalid_posterior_size')
            target=folder/(m['sport'].lower()+'-'+m['stat'].replace(' ','-'))
            target.mkdir(parents=True,exist_ok=True)
            # Source copies are immutable. Never replace a prior artifact copy.
            manifest_path=target/'manifest.json'; posterior_path=target/'posterior.nc'
            manifest_bytes=z.read(item)
            if manifest_path.exists() and manifest_path.read_bytes()!=manifest_bytes:
                raise ValueError('immutable_cached_manifest_conflict')
            if not posterior_path.exists():
                tmp=target/'posterior.download'
                with z.open(info) as src,tmp.open('xb') as dst:shutil.copyfileobj(src,dst)
                tmp.replace(posterior_path)
            manifest_path.write_bytes(manifest_bytes)
            accepted.append(target)
    return accepted


def discover(cache,*,wanted,token,opener=urllib.request.urlopen,remote=True):
    """Completed successful artifacts only. Cache records bind exact ZIP hashes."""
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    found=[];events=[]
    cached_run_ids=set()
    # Cached, hash-verified approved fits remain usable with a Contents-only
    # token. ChatGPT's connected GitHub access can stage additional completed
    # artifacts without granting or exposing any extra credential permissions.
    for receipt_path in sorted(cache.glob('*/artifact_receipt.json')):
        target=receipt_path.parent;saved=json.loads(receipt_path.read_text())
        cached_run_ids.add(saved.get('run_id'))
        for entry in saved.get('models',[]):
            folder=target/entry['folder']
            if (checksum(folder/'posterior.nc')!=entry['posterior_sha256'] or
                    checksum(folder/'manifest.json')!=entry['manifest_sha256']):
                raise ValueError('cached_model_hash_mismatch')
            m=json.loads((folder/'manifest.json').read_text())
            if (m.get('sport'),m.get('stat')) in wanted and strict_manifest(m):found.append(folder)
    if not remote:return found,events
    try:listing=get_json('/actions/runs?per_page=100',token,opener)
    except Exception as exc:
        return found,[{'status':'remote_discovery_unavailable','error_type':type(exc).__name__,
                       'verified_cached_models':len(found)}]
    for run in completed_runs(listing.get('workflow_runs',[])):
        run_id=run.get('id')
        if type(run_id) is not int:continue
        if run_id in cached_run_ids:continue
        target=cache/str(run_id);receipt_path=target/'artifact_receipt.json'
        if receipt_path.is_file():
            saved=json.loads(receipt_path.read_text())
            for entry in saved.get('models',[]):
                folder=target/entry['folder']
                if checksum(folder/'posterior.nc')!=entry['posterior_sha256']:
                    raise ValueError('cached_posterior_hash_mismatch')
                if checksum(folder/'manifest.json')!=entry['manifest_sha256']:
                    raise ValueError('cached_manifest_hash_mismatch')
                m=json.loads((folder/'manifest.json').read_text())
                if (m.get('sport'),m.get('stat')) in wanted and strict_manifest(m):found.append(folder)
            continue
        assets=get_json('/actions/runs/'+str(run_id)+'/artifacts',token,opener)
        for a in assets.get('artifacts',[]):
            digest=a.get('digest','')
            if (a.get('expired') or not str(a.get('name','')).startswith('precision-full-market-')
                    or not digest.startswith('sha256:')):continue
            aid=a.get('id')
            if type(aid) is not int:continue
            target.mkdir(parents=True,exist_ok=True)
            archive=target/'artifact.download.zip'
            with opener(request('/actions/artifacts/'+str(aid)+'/zip',token,binary=True),timeout=240) as src,archive.open('wb') as dst:
                shutil.copyfileobj(src,dst)
            try:
                if checksum(archive)!=digest[7:]:raise ValueError('artifact_zip_hash_mismatch')
                models=extract_model(archive,target,wanted=wanted)
                saved={'run_id':run_id,'artifact_id':aid,'zip_sha256':digest[7:],
                       'code_sha':run.get('head_sha'),'models':[
                    {'folder':str(p.relative_to(target)),'posterior_sha256':checksum(p/'posterior.nc'),
                     'manifest_sha256':checksum(p/'manifest.json')} for p in models]}
                # Empty model lists are not cached: a future slate may need that market.
                if models:receipt_path.write_text(json.dumps(saved,indent=2,sort_keys=True))
                found.extend(models);events.append({k:v for k,v in saved.items() if k!='models'})
            finally:archive.unlink(missing_ok=True)
    return found,events


def candidate_context(row,m,now):
    if (row.get('sport'),canon_stat(row.get('stat'))) != (m['sport'],m['stat']):
        raise ValueError('wrong_model_market')
    at,start=instant(row.get('forecast_at')),instant(row.get('event_start'))
    if not at<=now<start:raise ValueError('not_prospective')
    day=date.fromisoformat(row['game_date'])
    if date.fromisoformat(m['last_game'])>=day or date.fromisoformat(m['training_cutoff_exclusive'])>day:
        raise ValueError('training_overlaps_prediction')
    pid=str(row.get('player_id') or '')
    if pid not in m['players']:raise ValueError('player_not_in_frozen_posterior')
    team,opponent=str(row.get('team') or ''),str(row.get('opponent') or '')
    home,away=str(row.get('home_team') or ''),str(row.get('away_team') or '')
    if (row.get('matchup_orientation_verified') is not True or not team or not opponent
            or {team,opponent}!={home,away} or home==away or opponent not in m['opponents']):
        raise ValueError('unverified_team_opponent_or_venue')
    if row.get('side') not in ('over','under'):raise ValueError('invalid_side')
    if type(row.get('reference_line')) not in (int,float) or not math.isfinite(row['reference_line']):
        raise ValueError('invalid_line')
    if m['sport']=='NFL':season=str(day.year if day.month>=3 else day.year-1)
    elif m['sport']=='NBA':season=str(day.year if day.month>=7 else day.year-1)
    else:season=str((day.year if day.month>=7 else day.year-1)*10000+(day.year+1 if day.month>=7 else day.year))
    # Preserve the exact source season naming convention when known.
    matching=[s for s in m['seasons'] if str(s)==season]
    if matching:season=matching[0]
    elif m['sport']!='NFL':raise ValueError('season_requires_explicit_adapter')
    return dict(player_id=pid,opponent=opponent,season=season,home=team==home,line=row['reference_line'])


def evaluate(row,m,posterior,cache,now,*,model_id,clock=None):
    result={k:row.get(k) for k in KEYS+('player','team','opponent','event_start')}
    result.update(version=VERSION,model_version=m['model_version'],model_id=model_id,
                  generated_at=now.isoformat(),status='unavailable',ranking_allowed=False,
                  publication_eligible=False,shadow_only=True,trained_through=m['last_game'])
    result['training_source_digest']=m.get('source_digest')
    result['sampler_diagnostics']=m.get('diagnostics')
    try:
        if not strict_manifest(m):raise ValueError('strict_convergence_failed')
        context=candidate_context(row,m,now)
        # Both sides of an identical contract MUST use identical posterior
        # integration draws; in particular, exclude per-side forecast_at.
        seed=shared_contract_seed(row)
        from joint_population_bayes import forecast
        q=forecast(posterior,m,**context,seed=seed,draws=1500,diagnostic=m['diagnostics'],cache=cache)
        completed=clock() if clock else now
        if completed>=instant(row['event_start']):raise ValueError('inference_completed_after_event_start')
        result['generated_at']=completed.isoformat()
        result.update(status='forecast',q_over=q['q_over'],q_under=q['q_under'],q_push=q['q_push'],
                      q_win=q['q_over'] if row['side']=='over' else q['q_under'],
                      numerical_mc_se=q['numerical_mc_se'],mc_se_kind='conditional_iid_integration_error',
                      calibrated=False,conditional_on_appearance=True)
    except (ValueError,KeyError,TypeError,OverflowError) as exc:result['reason']=str(exc)
    return result


def run(root,day,*,cache_dir,token=None,now=None,discover_remote=True):
    import live_pool_exchange as pool
    root=Path(root);now=now or datetime.now(timezone.utc)
    rows,_=pool.pick_latest(pool.jsonl(root/'data/prop_snapshots.jsonl'),day)
    from population_history import COUNT
    wanted={(r['sport'],canon_stat(r['stat'])) for r in rows
            if canon_stat(r['stat']) in COUNT.get(r['sport'],())}
    folders=[];events=[];error=None
    try:
        if wanted:folders,events=discover(cache_dir,wanted=wanted,token=token,remote=discover_remote)
    except Exception as exc:error=type(exc).__name__ # Do not expose authenticated URLs.
    out=root/'data/population_nuts_shadow'/(day+'.jsonl')
    old=pool.jsonl(out);seen={(identity(r),r.get('model_id')) for r in old};added=[]
    frozen_identities={identity(r) for r in old}
    # Deterministic newest completed fit per sport/stat, not best-probability selection.
    by_market={}
    for folder in sorted(folders,key=lambda p:str(p)):
        m=json.loads((folder/'manifest.json').read_text())
        if not strict_manifest(m):continue
        key=(m['sport'],m['stat'])
        if key not in by_market or m['last_game']>by_market[key][0]['last_game']:
            by_market[key]=(m,folder)
    for (sport,stat),(m,folder) in by_market.items():
        candidates=[r for r in rows if r['sport']==sport and canon_stat(r['stat'])==stat
                    and identity(r) not in frozen_identities]
        if not candidates:continue
        import arviz as az
        from joint_population_bayes import posterior_cache
        posterior=az.from_netcdf(folder/'posterior.nc');cache=posterior_cache(posterior)
        model_id=checksum(folder/'posterior.nc')
        if (posterior.posterior.sizes.get('chain')!=4 or
                posterior.posterior.sizes.get('draw')!=m['sampler_retained_draws_per_chain']):
            raise ValueError('posterior_chain_or_draw_count_mismatch')
        for row in candidates:
            if (identity(row),model_id) not in seen:
                added.append(evaluate(row,m,posterior,cache,now,model_id=model_id,
                                      clock=lambda:datetime.now(timezone.utc)))
        del posterior,cache
    for row in rows:
        if (row['sport'],canon_stat(row['stat'])) not in by_market:
            k=(identity(row),'none')
            if k not in seen and identity(row) not in frozen_identities:
                reason=(error or 'no_completed_strictly_converged_population_model') if (row['sport'],canon_stat(row['stat'])) in wanted else 'market_requires_separately_validated_nuts_adapter'
                added.append({**{key:row.get(key) for key in KEYS},'version':VERSION,'model_id':'none',
                    'status':'unavailable','reason':reason,
                    'generated_at':now.isoformat(),'ranking_allowed':False,'publication_eligible':False,'shadow_only':True})
    pool.dump_jsonl(out,old+added)
    receipt={'schema':VERSION,'date':day,'source_candidates':len(rows),'new_rows':len(added),
             'forecasts':sum(r.get('status')=='forecast' for r in added),'discovery_error':error,
             'completed_artifacts':events,'active_jobs_modified':False,'new_training_started':False,
             'production_blend_changed':False}
    p=root/'reports/population_nuts_shadow_receipt.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(receipt,indent=2))
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--date',required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--cache-dir',type=Path,required=True);p.add_argument('--offline',action='store_true')
    a=p.parse_args();print(json.dumps(run(a.root,a.date,cache_dir=a.cache_dir,
        token=os.environ.get('GITHUB_TOKEN'),discover_remote=not a.offline),sort_keys=True))


if __name__=='__main__':main()
