"""Separate arithmetic/replay pass; not independent human validation."""
import copy
from pathlib import Path
from collections import Counter
import numpy as np
from . import models as m
from .full_market_v2 import FullMarketModel, MODELS, MARKET_MAP

def verify(directory):
    d=Path(directory);raw=(d/'report.json').read_bytes();r=m.strict_json(raw)
    receipt=m.strict_json((d/'receipt.json').read_bytes());m.require(m.sha(raw)==receipt['report_sha256'],'report_receipt')
    p=m.strict_json((d/'adapter_packet.json').read_bytes());m.require(m.sha(m.canonical(p))==r['input_packet_sha256'],'packet_receipt')
    replay=FullMarketModel(p,r['draws']).run()
    # Rejections appended by the adapter are checked separately from simulated rows.
    expected={(x['game_id'],x['player_id'],x['model'],x['market']):x for x in r['player_stat_rows']}
    checked=0
    for x in replay['player_stat_rows']:
        orig=expected[x['game_id'],x['player_id'],x['model'],x['market']]
        m.require(x==orig,'replay_changed')
        if x['status']!='forecast':continue
        v=np.asarray(x['distribution']['values']);weights=np.asarray(x['distribution']['masses'])
        m.require(abs(weights.sum()-1)<1e-12 and np.all(weights>=0),'mass_normalization')
        m.require(np.all(v==np.rint(v)),'integer_stat_support')
        mean=sum(float(a)*float(b) for a,b in zip(v,weights))
        variance=sum(float(b)*(float(a)-mean)**2 for a,b in zip(v,weights))
        m.require(abs(mean-x['moments']['mean'])<1e-9,'mean_reconstruction')
        m.require(abs(variance-x['moments']['sd']**2)<1e-7,'variance_reconstruction');checked+=1
    identity_checks=0
    for e in p['events']:
        env=FullMarketModel(p,r['draws']).environment(e)
        for team in (e['home'],e['away']):
            for mixture in (False,True):
                vals,_,_,_=FullMarketModel(p,r['draws']).offense(e,team,env[team],mixture)
                for x in vals.values():
                    for total,left,right in [('rushing + receiving yards','rushing yards','receiving yards'),('passing + rushing yards','passing yards','rushing yards')]:
                        if total in x:
                            m.require(np.array_equal(x[total],x[left]+x[right]),'composite_identity');identity_checks+=1
    mutations=[('missing_sacks',lambda x:x['team_history'][0].update(sacks=None)),
               ('broken_accounting',lambda x:x['team_history'][0].update(plays=x['team_history'][0]['plays']+1)),
               ('passed_kickoff',lambda x:x.update(forecast_at=x['events'][0]['event_start'])),
               ('future_history',lambda x:x['team_history'][0].update(end_at='2026-11-16T00:00:00Z')),
               ('duplicate_player',lambda x:x['roster'].append(copy.deepcopy(x['roster'][0])))]
    rejected=[]
    for name,mutate in mutations:
        x=copy.deepcopy(p);mutate(x)
        try:FullMarketModel(x,r['draws'])
        except m.GateError:rejected.append(name)
        else:raise AssertionError('accepted corruption '+name)
    keys=[(x['game_id'],x['player_id'],x['model'],x['market']) for x in r['player_stat_rows']]
    m.require(len(keys)==len(set(keys)),'duplicate_stat_output')
    m.require(all(x['market']=='tackles_assists' and x['status']=='abstain' for x in r['player_stat_rows'] if x['model']==MODELS[3]),'O4_public_scope')
    for c in r['contract_rows']:
        if c['status']=='forecast':m.probability_object(c['probabilities_conditional'])
    cutoff=m.stamp(r['training_cutoff_at']);m.require(all(m.stamp(h['end_at'])<cutoff for h in p['player_history']),'historical_cutoff')
    m.require(all(m.stamp(receipt['created_at'])<m.stamp(e['event_start']) for e in p['events']),'freeze_after_kickoff')
    summary={'status':'PASS','method':'separate sequential arithmetic pass by same agent, not independent reviewer',
             'replayed_stat_distributions':checked,'matched_component_identities':identity_checks,
             'rejected_actual_packet_corruptions':rejected,'max_conservation_error':max(c['max_conservation_error'] for c in r['constraint_checks']),
             'report_sha256':m.sha(raw),'input_packet_sha256':r['input_packet_sha256'],
             'source_checks':len(r['adapter_audit']['original_checks'])+len(r['adapter_audit']['extension_checks']),
             'contract_forecasts':dict(Counter(c['model'] for c in r['contract_rows'] if c['status']=='forecast')),
             'original_contract_model_rows':len(r['contract_rows']),
             'abstentions':dict(Counter(x['reason'] for x in r['player_stat_rows'] if x['status']=='abstain'))}
    # Rehash previous frozen handoff, never rewrite it.
    previous=d.parents[1]/'activation_v1/0ee15529f1e8ad3fcf5dc39b4d0e2a10c74d05d29f917932a9d0bdd3d6852cd3/first_forecasts.jsonl'
    m.require(m.sha(previous.read_bytes())=='752e72afa7423f560298b1eeff68623a809a522b8433a22b0726b5416befaa2e','previous_handoff_mutated')
    summary['previous_handoff_unchanged']=True
    with (d/'ARITHMETIC_AUDIT.json').open('xb') as f:f.write(m.canonical(summary))
    return summary
