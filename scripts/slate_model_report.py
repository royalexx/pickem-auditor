#!/usr/bin/env python3
"""One immutable per-pick view of production consensus and comparison models.

All displayed probabilities refer to the original player's exact side/line and
are conditional on no push. Raw masses, versions, timestamps and missing reasons
are retained in JSON. Missing NUTS fits are never replaced with another model.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics

from odds_providers import approved_book_name, normalize_player, normalize_team
from prediction_scoring import conditional_win
from nuts_slate_shadow import instant, identity

VERSION='slate-model-comparison-v1'
FOLDERS={'Bayesian_A':'bayesian_shadow','Bayesian_B':'bayesian_b_shadow',
         'NUTS_saves':'nhl_joint_saves_shadow','NUTS_targets':'nfl_context',
         'NUTS_population':'population_nuts_shadow',
         'NUTS_provisional':'provisional_nuts_shadow'}
COLUMNS=('sport','player','stat','side','line','Engine_A','Engine_B','Consensus',
         'Bayesian_A','Bayesian_B','Market','NUTS','NUTS_provisional','NUTS_model','NUTS_status',
         'Consensus_gap_pp','production_consensus_available','original_rank','block_reason')


def rows(path):
    p=Path(path)
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.is_file() else []


def probability(win,push):
    if type(win) not in (int,float) or type(push) not in (int,float):return None
    try:return conditional_win(win,push)
    except ValueError:return None


def masses(item,*,win='q_win',push='q_push'):
    p=probability(item.get(win),item.get(push))
    return {'probability':p,'q_win':item.get(win) if p is not None else None,'q_push':item.get(push) if p is not None else None,
            'version':item.get('model_build') or item.get('version'),
            'numerical_revision':item.get('numerical_revision'),
            'status':'forecast' if p is not None else 'unavailable',
            'reason':None if p is not None else item.get('reason') or 'probability_not_recorded',
            'reliable':item.get('reliable'),'generated_at':item.get('generated_at')}


def source_market(row,quotes):
    try:at,start=instant(row['forecast_at']),instant(row['event_start'])
    except (ValueError,TypeError,KeyError):
        return {'probability':None,'status':'unavailable','reason':'market_event_time_unverified'}
    selections={}
    attached={approved_book_name(b.get('book')):b for b in (row.get('books') or []) if isinstance(b,dict)}
    for q in quotes:
        book=approved_book_name(q.get('book'));b=attached.get(book)
        if not book or not b:continue
        if (q.get('sport')!=row.get('sport') or q.get('stat')!=row.get('stat')
                or normalize_player(q.get('player'))!=normalize_player(row.get('player'))
                or normalize_team(q.get('team'))!=normalize_team(row.get('team'))
                or normalize_team(q.get('opponent'))!=normalize_team(row.get('opponent'))
                or q.get('line')!=row.get('reference_line') or b.get('line')!=row.get('reference_line')
                or q.get('over_odds')!=b.get('over') or q.get('under_odds')!=b.get('under')):continue
        try:
            updated=instant(q.get('retrieved_at'))
            if instant(q.get('event_start'))!=start or not updated<=at<start:continue
            for k in ('event_id','event_id_namespace'):
                if row.get(k) and str(row[k])!=str(q.get(k)):raise ValueError('event_mismatch')
            odds=[q.get('over_odds'),q.get('under_odds')]
            if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)<100 for x in odds):continue
            over,under=[-x/(-x+100) if x<0 else 100/(x+100) for x in odds]
            value=over/(over+under) if row['side']=='over' else under/(over+under)
            key=(str(q.get('event_id')),str(q.get('event_id_namespace')))
            prior=selections.get(book)
            if prior is None or updated>prior[0]:selections[book]=(updated,value,key)
        except (ValueError,TypeError):continue
    # Never silently combine different events when the original ID is missing.
    event_ids={v[2] for v in selections.values()}
    if len(event_ids)>1 or not selections:
        return {'probability':None,'status':'unavailable','reason':'no_unambiguous_frozen_paired_prices'}
    return {'probability':statistics.median(v[1] for v in selections.values()),'status':'forecast',
            'version':'normalized-paired-American-odds-median-v1','conditional_on_nonpush':True,
            'books':sorted(selections),'observed_at':max(v[0] for v in selections.values()).isoformat()}


def index_sidecars(items):
    result={}
    for item in items:
        key=identity(item)
        if key in result and result[key]!=item:raise ValueError('conflicting_model_sidecar_identity')
        result[key]=item
    return result


def linked_probability(row,item,*,nfl_targets=False):
    if not item:return {'probability':None,'status':'unavailable','reason':'model_output_not_recorded'}
    if item.get('status')!='forecast':
        return {'probability':None,'status':'unavailable','reason':item.get('reason') or 'model_unavailable',
                'version':item.get('version'),'model_id':item.get('model_id')}
    result=masses(item)
    try:
        generated=instant(item.get('generated_at') or (item.get('forecast_at') if nfl_targets else None))
        if not instant(row['forecast_at'])<=generated<instant(row['event_start']):
            raise ValueError('model_not_completed_before_event')
    except (ValueError,TypeError):
        result.update(probability=None,status='unavailable',reason='model_completion_time_unverified_or_poststart')
    result['model_id']=item.get('model_id') or item.get('release_tag') or item.get('model_source_digest')
    result['trained_through']=item.get('trained_through')
    result['training_source_digest']=item.get('training_source_digest') or item.get('model_source_digest')
    result['sampler_diagnostics']=item.get('sampler_diagnostics')
    if item.get('provisional') is True:
        result.update(provisional=True,ranking_allowed=False,publication_eligible=False,
                      model_run_id=item.get('model_run_id'),
                      strict_convergence_passed=False)
    return result


def build(row,indices,quotes):
    key=identity(row);a=row.get('engine_a') or {};b=row.get('engine_b') or {};blend=row.get('blend') or {}
    models={'Engine_A':masses(a,win='q_win_robust',push='q_push_robust'),
            'Engine_B':masses(b)}
    models['Consensus']=masses({'q_win':row.get('q_model'),'q_push':row.get('q_push'),
                               'version':blend.get('version')})
    if not (blend.get('production_policy') and blend.get('available')):
        models['Consensus'].update(probability=None,status='unavailable',
                                   reason='production_consensus_not_available')
    for name in ('Bayesian_A','Bayesian_B'):
        models[name]=linked_probability(row,indices.get(name,{}).get(key))
    models['Market']=source_market(row,quotes)
    nuts={}
    for name in ('NUTS_saves','NUTS_population'):
        item=indices.get(name,{}).get(key)
        if item:nuts[name]=linked_probability(row,item)
    target=indices.get('NUTS_targets',{}).get(key)
    if target:nuts['NUTS_targets']=linked_probability(row,target,nfl_targets=True)
    # Fixed family priority; never select a model based on its probability.
    selected=next((k for k in ('NUTS_targets','NUTS_saves','NUTS_population')
                   if nuts.get(k,{}).get('status')=='forecast'),None)
    chosen=nuts[selected] if selected else {'probability':None,'status':'unavailable',
                    'reason':next((x.get('reason') for x in nuts.values() if x.get('reason')),
                                  'no_verified_trained_model_for_this_pick')}
    models['NUTS']=chosen
    # Explicit side-by-side research-only probability. NEVER used as a
    # fallback for the strict NUTS column or the production consensus.
    research=indices.get('NUTS_provisional',{}).get(key)
    provisional=linked_probability(row,research) if research else {
        'probability':None,'status':'unavailable',
        'reason':'no_eligible_provisional_nuts_artifact_for_exact_contract'}
    models['NUTS_provisional']=provisional
    record={k:row.get(k) for k in ('game_date','run_id','forecast_at','event_start','sport','player','player_id','team','opponent','stat','side')}
    record.update(line=row.get('reference_line'),reference_line=row.get('reference_line'),original_rank=row.get('final_rank'),block_reason=row.get('reason'),
                  probability_scale='P(exact_side_wins | no_push)',models=models,nuts_models=nuts,
                  NUTS_model=selected,NUTS_status=chosen['status'],NUTS_reason=chosen.get('reason'),
                  production_consensus_available=models['Consensus']['probability'] is not None,
                  provisional_nuts_status=provisional['status'],
                  provisional_nuts_reason=provisional.get('reason'),
                  production_policy_version=blend.get('version'),
                  context_adjustment_applied=(row.get('shared_context') or {}).get('applied',False))
    for name,value in models.items():record[name]=value['probability']
    record['Consensus_gap_pp']=100*(record['Consensus']-record['Market']) if record['Consensus'] is not None and record['Market'] is not None else None
    return record


def run(root,day,out_dir):
    import live_pool_exchange as pool
    root=Path(root);out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    snapshots,run_id=pool.pick_latest(rows(root/'data/prop_snapshots.jsonl'),day)
    indices={}
    for name,folder in FOLDERS.items():
        items=rows(root/'data'/folder/(day+'.jsonl'))
        if name=='NUTS_targets':
            # The targets adapter stores its source timestamp separately.
            items=[{**r,'forecast_at':r.get('parent_forecast_at',r.get('forecast_at')),
                    'generated_at':r.get('generated_at') or r.get('forecast_at')} for r in items if r.get('line_origin')=='market']
        if name in ('NUTS_population','NUTS_targets','NUTS_provisional'):
            # Failed retries are audit records, not conflicting forecasts. Keep
            # the earliest successful inference; conflicting probabilities fail.
            grouped={}
            for item in sorted(items,key=lambda x:str(x.get('generated_at') or '')):
                k=identity(item);previous=grouped.get(k)
                if previous and previous.get('status')=='forecast':
                    if item.get('status')=='forecast' and any(
                            previous.get(f)!=item.get(f) for f in ('q_win','q_push','q_over','q_under')):
                        raise ValueError('conflicting_model_sidecar_identity')
                    continue
                if previous is None or item.get('status')=='forecast':grouped[k]=item
            items=list(grouped.values())
        indices[name]=index_sidecars(items)
    quotes=rows(root/'data/odds_quotes.jsonl')
    records=[build(r,indices,quotes) for r in snapshots]
    inputs={'snapshots_sha256':hashlib.sha256((root/'data/prop_snapshots.jsonl').read_bytes()).hexdigest(),
            'code_sha':os.environ.get('PICKEM_CODE_SHA'),
            'comparison_schema':VERSION,'day':day,'run_id':run_id,'rows':len(records),
            'production':'engine_a_engine_b_consensus','forecast_weights':{'a':.7,'b':.3},
            'probability_scale':'conditional_on_nonpush','training_started':False}
    payload={'schema':VERSION,'metadata':inputs,'picks':records}
    paths={'json':out_dir/'slate_model_comparisons.json','csv':out_dir/'slate_model_comparisons.csv',
           'markdown':out_dir/'slate_model_comparisons.md'}
    paths['json'].write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False))
    with paths['csv'].open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    lines=['# Slate probability comparison — '+day,'',
           'All probabilities use the same player, side and line and are conditional on no push. N/A means unavailable; it is never a substituted forecast.',
           '', '| Player | Market | Side / line | A | B | Consensus | Bayes A | Bayes B | Market | NUTS | Gap pp |',
           '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    def pct(x):return 'N/A' if x is None else f'{100*x:.1f}%'
    for r in records:
        vals=[pct(r.get(k)) for k in ('Engine_A','Engine_B','Consensus','Bayesian_A','Bayesian_B','Market','NUTS')]
        lines.append('| '+str(r['player']).replace('|','/')+' | '+str(r['stat'])+' | '+str(r['side'])+' '+str(r['line'])+' | '+' | '.join(vals)+' | '+('N/A' if r['Consensus_gap_pp'] is None else f"{r['Consensus_gap_pp']:+.1f}")+' |')
    paths['markdown'].write_text('\n'.join(lines)+'\n')
    # Produce evidence-backed top ten per sport from the SAME immutable comparison
    # and complete original batch, independent of the capped triage queue.
    from slate_candidate_ranking import build as rank_candidates, write as write_candidates
    ranked = rank_candidates(snapshots, records, day, data_root=root/'data')
    write_candidates(ranked, out_dir)
    # Archive every displayed model probability alongside its source forecast.
    # Same-run retries preserve earlier reports rather than rewriting history.
    sidecar=root/'data/model_comparisons'/(day+'.jsonl')
    prior=rows(sidecar);seen={identity(r) for r in prior}
    pool.dump_jsonl(sidecar,prior+[r for r in records if identity(r) not in seen])
    return payload


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--date',required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args();r=run(a.root,a.date,a.out_dir);print(json.dumps(r['metadata'],sort_keys=True))


if __name__=='__main__':main()
