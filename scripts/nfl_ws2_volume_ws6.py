#!/usr/bin/env python3
"""Create-only WS6 transport of previously frozen distributions and exact contracts.

Does not refit, collect, calibrate, backdate, or replace the WS6 v1 comparison.
The distribution-only universe stays distinct from original offer identities.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nfl_volume_distributions import bound,canonical,sha,write_once,ACTIVE


def export(root,handoff,out):
    root=Path(root).resolve();handoff=Path(handoff);out=Path(out)
    raw=handoff.read_bytes();m=json.loads(raw)
    pin=json.loads(bound(root,dict(path=m['source_pin_path'],sha256=m['source_pin_sha256'])))
    contracts=[json.loads(l) for l in bound(root,pin['tables']['original_contracts']).splitlines()]
    def artifact(name):
        ref=m['artifacts'][name];path=Path(ref['path'])
        if path.is_absolute():path=path.relative_to(root)
        return [json.loads(l) for l in bound(root,dict(path=str(path),sha256=ref['sha256'])).splitlines()]
    evaluated={(r['candidate_id'],r['model_version']):r for r in artifact('original_contract_evaluations')}
    laws={(r['player_stat_id'],r['model_version']):r for r in artifact('distributions_and_abstentions')}
    rows=[]
    for c in contracts:
        original=c['original_record'];models={}
        for model in ACTIVE:
            p=evaluated[(c['candidate_id'],model)]
            d=laws.get((c['player_stat_id'],model))
            if p['status']=='abstention':
                models[model]=dict(status='unavailable',reason=p['abstention_reason'])
            else:
                q=p['q_over']+p['q_under']
                models[model]=dict(status='forecast',kind='empirical',parameters=dict(masses=d['pmf']),
                    mean=d['predictive_mean'],variance=d['predictive_variance'],
                    **{k:p[k] for k in ('q_over','q_under','q_push')},
                    p_over_given_no_push=p['q_over']/q if q else None,
                    distribution_sha256=d['distribution_sha256'],
                    training_data_cutoff=d['training_data_cutoff'],forecast_created_at=d['forecast_at'],
                    model_input_fingerprint=d['model_input_fingerprint'],
                    source_pin_sha256=d['source_pin_sha256'],model_sha256=d['model_sha256'])
        rows.append(dict(original_contract_id=c['candidate_id'],original_quote_id=c['quote_id'],
            original_quote=original['original_quote'],original_contract=original,
            original_source_sha256=original['source_sha256'],
            event_id=original['event_id'],kickoff_at=original['event_start_at'],
            normalized_market=c['normalized_market'],player_stat_id=c['player_stat_id'],models=models,
            forecast_created_at=m['forecast_at'],assembly_is_not_forecast_creation=True,
            research_only=True,production_modified=False))
    assert len(rows)==len({r['original_contract_id'] for r in rows})==1845
    out.mkdir(parents=True,exist_ok=False)
    ref=write_once(out/'comparison_input.jsonl',b''.join(canonical(r)+b'\n' for r in rows))
    index=dict(schema='ws2-ws6-volume-transport-v2',original_contract_rows=len(rows),
        source_handoff=dict(path=str(handoff),sha256=sha(raw)),contract_transport=ref,
        distribution_population=m['artifacts']['distributions_and_abstentions'],
        source_pin_sha256=m['source_pin_sha256'],model_sha256=m['model_sha256'],
        counts=m['real_player_stat_distribution_counts'],
        authentic_contract_probability_counts=m['authentic_contract_probability_counts'],
        historical_pregame_availability_claimed=False,research_only=True,production_modified=False,
        original_s2_v1_comparison_replaced=False)
    return write_once(out/'INDEX.json',canonical(index)+b'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--handoff',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(export(a.root,a.handoff,a.out),sort_keys=True))
