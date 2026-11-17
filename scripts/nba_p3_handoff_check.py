#!/usr/bin/env python3
"""Generate actual P3 O/sidecar fixtures and optionally call pinned owner APIs.

All inputs in this executable are SYNTHETIC. No target-game data is accessed.
Run from repository root: python scripts/nba_p3_handoff_check.py --output <folder>
Owner code is loaded only from an explicitly provided disposable owner checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/nba_architecture')]
from test_p3_o_family import inputs
from test_p3_boundaries import reseal
from v2.nba_o_family import build_opportunity, freeze_outputs
from v2.nba_o_consumers import consumer_fixture, replay, call_p2, call_p4
from v2.nba_architecture.v2_contracts import canonical, seal


def check(output, owner_root=None):
    p,g,priors=inputs()
    for row,ot in zip(g['scenarios'],(0,2)):
        row['overtime_periods']=ot
        row['possessions_home']=100+10*ot
        row['possessions_away']=99+10*ot
    g=reseal(g)
    o,side=build_opportunity(p,g,priors,model=g['model'],seed=20261116,variant='O2',
        home_team_id=p['team_ids'][0],home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
    replay(p,g,o,side)
    fixture=consumer_fixture(p,g,o,side)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    freeze_outputs(output,p,g,o,side)
    bundle=dict(provenance='SYNTHETIC_ENGINEERING_ONLY_NO_REAL_FIT',pregame=p,game_state=g,
                opportunity=o,sidecar=side,handoff=fixture)
    raw=canonical(bundle)+b'\n'
    path=output/'consumer_fixture.json'
    if path.exists() and path.read_bytes()!=raw:raise ValueError('IMMUTABLE_FIXTURE_CONFLICT')
    path.write_bytes(raw)
    receipts=[]
    for sc in o['scenarios']:
        for t in p['team_ids']:
            rows=[x for x in sc['players'] if x['team_id']==t]
            receipts.append(dict(scenario_id=sc['scenario_id'],team_id=t,ot=sc['overtime_periods'],
                expected_minutes=240+25*sc['overtime_periods'],
                minutes=sum(x['minutes'] for x in rows),max_player_minutes=max(x['minutes'] for x in rows),
                minute_residual=sum(x['minutes'] for x in rows)-(240+25*sc['overtime_periods']),
                max_on_court_count=max(len(seg['player_indices']) for seg in
                    next(y for y in side['scenarios'] if y['scenario_id']==sc['scenario_id'])['teams'][t]['lineup_segments']),
                min_on_court_count=min(len(seg['player_indices']) for seg in
                    next(y for y in side['scenarios'] if y['scenario_id']==sc['scenario_id'])['teams'][t]['lineup_segments']),
                possession_shares=sum(x['possession_share'] for x in
                    next(y for y in side['scenarios'] if y['scenario_id']==sc['scenario_id'])['players']
                    if next(r for r in p['players'] if r['player_id']==x['player_id'])['team_id']==t)))
    result=dict(provenance=bundle['provenance'],opportunity_sha256=o['content_hash'],
                sidecar_sha256=side['content_hash'],fixture_raw_sha256=hashlib.sha256(raw).hexdigest(),
                deterministic_replay=True,conservation=receipts,
                owner_integration='NOT_REQUESTED')
    if owner_root:
        import v2
        v2.__path__.append(str(Path(owner_root)/'v2'))
        from v2.nba_s_family import fit, predict, conditional_pmf
        from v2.nba_joint.p4 import simulate_p4, S_ADAPTER
        source='1'*64;raw_hash='2'*64
        history=[dict(game_id=f'espn:game:synthetic-prior-{i}',player_id=pid,
            team_id='espn:team:1',stat='points',role='wing',
            game_start_at=f'2022-10-0{1+2*i}T00:00:00Z',
            outcome_available_at=f'2022-10-0{2+2*i}T00:00:00Z',
            source_receipt_sha256=source,source_raw_sha256=raw_hash,count=y,
            minutes=30.,three_attempts=None)
            for pid in ('espn:player:10','espn:player:11') for i,y in enumerate((11,14,18))]
        fitted=fit(history,asof_cutoff_utc='2022-10-10T00:00:00Z',stat='points',
            source_manifest={source:dict(raw_sha256=raw_hash,available_at='2022-10-07T00:00:00Z',status='P1_VERIFIED')})
        prediction=call_p2(p,g,o,side,predict=predict,fitted=fitted,player_id='espn:player:10',role='wing')
        conditional=call_p2(p,g,o,side,predict=predict,fitted=fitted,player_id='espn:player:10',
                            role='wing',conditioning='conditional_on_participation')
        assert conditional.abstain_reason is None, conditional.abstain_reason
        assert prediction.abstain_reason == 'UNKNOWN_APPEARANCE_PROBABILITY'
        # Actual S kernel receives generated scenario minutes; no duplicated S math.
        kernel=[]
        for sc in o['scenarios']:
            row=next(x for x in sc['players'] if x['player_id']=='espn:player:10')
            pmf,tail,_=conditional_pmf(fitted,player_id=row['player_id'],role='wing',opportunity=row['minutes'])
            assert abs(sum(pmf)-1)<1e-8
            kernel.append(dict(scenario_id=sc['scenario_id'],minutes=row['minutes'],tail=tail))
        rates=seal(dict(schema=S_ADAPTER,kind='conditional_rates',
            source_snapshot_sha256=p['content_hash'],game_id=p['game_id'],adapter_basis='synthetic_fixture',
            model=g['model'],players=[dict(player_id=r['player_id'],team_id=r['team_id'],
                rates=dict(points=.6,rebounds=.2,assists=.12,threes=.07)) for r in p['players']]))
        joint=call_p4(p,g,o,side,simulate=simulate_p4,conditional_rates=rates,seed=42,
            event_parameters=dict(p2=.54,p3=.36,pft=.78,ft_share=.25,rebound_credit=.9,
                offensive_rebound_share=.24,terminal_ft_fraction=.44,assist_fraction=.6))
        # P4 owns and validates all J accounting; preserve its returned artifact.
        result['owner_integration']=dict(p2_predict_abstention=prediction.abstain_reason,
            p2_conditional_distribution_sha256=conditional.distribution['content_hash'],
            p2_kernel_calls=kernel,p4_scenario_hashes=joint['scenario_hashes'],p4_return_type=type(joint).__name__)
        if isinstance(joint,dict):
            joint.pop('performance',None)
            (output/'p4_result.json').write_bytes(canonical(joint)+b'\n')
            result['owner_integration']['p4_result_sha256']=hashlib.sha256(canonical(joint)+b'\n').hexdigest()
    (output/'handoff_receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--owner-root')
    args=parser.parse_args()
    print(json.dumps(check(args.output,args.owner_root),sort_keys=True,indent=2))
