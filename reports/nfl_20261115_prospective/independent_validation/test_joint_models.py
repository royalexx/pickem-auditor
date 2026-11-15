"""Deterministic adversarial, contract and physical tests; synthetic only."""
import copy
import importlib.util
import json
import pathlib
import sys
import unittest
import numpy as np

HERE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'joint_models'))
from joint_simulator import SCHEMA,ContractError,SCENARIOS,describe,game_once,run_manifest,sample_event,sha,validate


def fixture():
    teams=[]
    for j,(tid,opp) in enumerate((('H','A'),('A','H'))):
        teams.append(dict(team_id=tid,plays_mean=66+2*j,pass_rate=.56-.02*j,sack_rate=.06,
                          starter_qb_id=tid+'Q',starter_status='CONFIRMED_PREGAME',pregame_game_role='FAVORITE' if j==0 else 'UNDERDOG',
                          players=[
                            dict(player_id=tid+'Q',role='QB',participation=1,rush_share=.10,yards_per_carry=4),
                            dict(player_id=tid+'R',role='RB',participation=1,share=1,rush_share=2.6,yards_per_carry=4.5),
                            dict(player_id=tid+'W',role='RECEIVER',participation=1,share=1.65,catch_rate=.68,yards_per_catch=10.2),
                            dict(player_id=tid+'T',role='RECEIVER',participation=1,share=1.15,catch_rate=.74,yards_per_catch=8.3),
                            dict(player_id=tid+'D',role='DEFENDER',participation=1,share=2,snap_share=.90),
                            dict(player_id=tid+'E',role='DEFENDER',participation=1,share=1.5,snap_share=.8)]))
    ev=dict(event_id='SYNTHETIC_2026_NFL_001',event_start_at='2026-11-15T18:00:00Z',teams=teams)
    contracts=[]
    for tid in ('H','A'):
        for pid,s,line in [(tid+'Q','pass_attempts',24.5),(tid+'Q','completions',18.5),
                           (tid+'Q','passing_yards',240.5),(tid+'Q','passing_tds',1),
                           (tid+'Q','qb_rushing_attempts',2),(tid+'R','carries',18.5),
                           (tid+'R','rushing_yards',70.5),(tid+'R','rushing_tds',0),
                           (tid+'W','targets',6.5),(tid+'W','receptions',4),(tid+'W','receiving_yards',49.5),
                           (tid+'W','receiving_tds',0),(tid+'D','solo_tackles',3.5),
                           (tid+'D','tackle_assists',2),(tid+'D','tackles_assists',5.5)]:
            contracts.append(dict(contract_id=f'fixture:{tid}:{pid}:{s}:{line}',original_quote_id=f'F-{len(contracts)}',
                                  event_id=ev['event_id'],team_id=tid,player_id=pid,stat_key=s,line=line,
                                  period='full_game_including_overtime'))
    return dict(schema=SCHEMA,synthetic_fixture=True,source_certification_status='SYNTHETIC_FIXTURE',
                input_freeze_at='2026-11-14T22:00:00Z',model_training_cutoff_at='2026-11-14T20:00:00Z',
                events=[ev],contracts=contracts)


class SourceContract(unittest.TestCase):
    def test_valid_fixture(self): self.assertEqual(validate(fixture())[0],'SYNTHETIC_FIXTURE')
    def mut(self, fn, expected):
        x=fixture();fn(x)
        with self.assertRaisesRegex(ContractError,expected):validate(x)
    def test_future_freeze(self):self.mut(lambda x:x.update(input_freeze_at='2026-11-15T18:00:00Z'),'POST_KICKOFF')
    def test_future_training(self):self.mut(lambda x:x.update(model_training_cutoff_at='2026-11-15T00:00:00Z'),'POST_FREEZE')
    def test_naive_timestamp(self):self.mut(lambda x:x.update(input_freeze_at='2026-11-14T22:00:00'),'TIMESTAMP_NOT_TIMEZONE')
    def test_team_swap(self):self.mut(lambda x:x['contracts'][0].update(team_id='UNKNOWN'),'CONTRACT_TEAM')
    def test_invalid_event(self):self.mut(lambda x:x['contracts'][0].update(event_id='wrong'),'CONTRACT_EVENT')
    def test_duplicate_player(self):self.mut(lambda x:x['events'][0]['teams'][0]['players'][1].update(player_id='HQ'),'PLAYER_ID_COLLISION')
    def test_fake_start(self):self.mut(lambda x:x['events'][0]['teams'][0].update(starter_status='PROBABLE'),'UNVERIFIED_STARTER')
    def test_duplicate_offer(self):self.mut(lambda x:x['contracts'][1].update(contract_id=x['contracts'][0]['contract_id']),'DUPLICATE_OR_MISSING_CONTRACT')
    def test_missing_quote(self):self.mut(lambda x:x['contracts'][0].pop('original_quote_id'),'ORIGINAL_OFFER_ID')
    def test_invalid_line(self):self.mut(lambda x:x['contracts'][0].update(line=float('nan')),'INVALID_ORIGINAL_LINE')
    def test_negative_shares(self):self.mut(lambda x:x['events'][0]['teams'][0]['players'][2].update(share=-1),'INVALID_PARAMETER')
    def test_missing_authentic_source(self):
        x=fixture();x['synthetic_fixture']=False;x['source_certification_status']='CERTIFIED'
        with self.assertRaisesRegex(ContractError,'MISSING_IMMUTABLE_INPUT_SHA'):validate(x)
    def test_postfreeze_source(self):
        x=fixture();x['synthetic_fixture']=False;x['source_certification_status']='CERTIFIED';x['input_manifest_sha256']='f'*64
        for e in x['events']:
            e['source_receipts']=[dict(source_uri='https://example.org/frozen',sha256='a'*64,available_at='2026-11-15T02:00:00Z')]
            e['scenario_source_receipts']=[dict(source_uri='https://example.org/context',sha256='a'*64,available_at='2026-11-14T21:00:00Z')]
        with self.assertRaisesRegex(ContractError,'POST_FREEZE_SOURCE'):validate(x)
    def test_postfreeze_quote(self):
        x=fixture();x['synthetic_fixture']=False;x['source_certification_status']='CERTIFIED';x['input_manifest_sha256']='f'*64
        for e in x['events']:
            e['source_receipts']=[dict(source_uri='https://example.org/frozen',sha256='a'*64,available_at='2026-11-14T21:00:00Z')]
            e['scenario_source_receipts']=[dict(source_uri='https://example.org/context',sha256='a'*64,available_at='2026-11-14T21:00:00Z')]
        for c in x['contracts']:c.update(original_quote_at='2026-11-15T01:00:00Z',original_quote_receipt_sha256='a'*64)
        with self.assertRaisesRegex(ContractError,'POST_FREEZE_QUOTE'):validate(x)
    def test_malformed_probability(self):self.mut(lambda x:x['events'][0]['teams'][0].update(pass_rate=1.3),'INVALID_PROBABILITY')
    def test_unsupported_schema(self):self.mut(lambda x:x.update(schema='WORKSTREAM1_UNKNOWN'),'UNRECOGNIZED_CANONICAL')

class NumericalAndPhysics(unittest.TestCase):
    def test_exact_push(self):
        v=describe(np.array([1,2,2,3.]),2.,'targets')
        self.assertEqual((v['p_over'],v['p_under'],v['p_push']),(.25,.25,.5))
        self.assertAlmostEqual(sum(v[k] for k in ('p_over','p_under','p_push')),1)
    def test_half_line_no_push(self):self.assertEqual(describe(np.array([1,2,3]),1.5,'targets')['p_push'],0)
    def test_same_seed(self):
        e=fixture()['events'][0]
        a,sa=sample_event(e,'J1',16,'frozen')
        b,sb=sample_event(e,'J1',16,'frozen')
        self.assertEqual(a,b);self.assertEqual(sa,sb)
    def test_seed_changes_for_event(self):
        e=fixture()['events'][0]
        a,_=sample_event(e,'J1',4,'frozen')
        b,_=sample_event(e,'J1',4,'different')
        self.assertNotEqual(a,b)
    def test_extended_first_draws(self):
        e=fixture()['events'][0]
        a,_=sample_event(e,'J2',5,'frozen')
        b,_=sample_event(e,'J2',16,'frozen')
        self.assertEqual(a,b[:5])
    def test_conservation_and_signed_support(self):
        e=fixture()['events'][0];out,states=sample_event(e,'J2',40,'frozen')
        neg=0
        for s,ss in zip(out,states):
            for team in e['teams']:
                t=ss[team['team_id']]
                self.assertEqual(t['plays'],t['pass_attempts']+t['rush_attempts']+t['sacks'])
                self.assertLessEqual(sum(v['targets'] for v in t['receivers'].values()),t['pass_attempts'])
                self.assertLessEqual(sum(v['carries'] for v in t['backs'].values()),t['rush_attempts'])
                self.assertLessEqual(t['starter_qb_attempts'],t['pass_attempts'])
                self.assertLessEqual(s.get((team['starter_qb_id'],'completions'),0),t['starter_qb_attempts'])
                for r in t['receivers'].values():self.assertLessEqual(r['receptions'],r['targets'])
                for p in team['players']:
                    pid=p['player_id']
                    self.assertEqual(s.get((pid,'tackles_assists'),0),s.get((pid,'solo_tackles'),0)+s.get((pid,'tackle_assists'),0))
            neg+=sum(int(stat.endswith('yards') and v<0) for (_,stat),v in s.items())
        self.assertGreaterEqual(neg,0)
    def test_full_fixture_outputs_coverage(self):
        x=run_manifest(fixture(),12)
        self.assertEqual(x['classification'],'SYNTHETIC_FIXTURE')
        self.assertEqual(len(x['contracts']),len(fixture()['contracts'])*3)
        self.assertTrue(all(r['status']=='FORECAST' for r in x['contracts']))
        self.assertTrue(all(abs(r['p_over']+r['p_under']+r['p_push']-1)<1e-12 for r in x['contracts']))
        self.assertFalse(any(r['classification']=='CERTIFIED_SHADOW' for r in x['contracts']))
    def test_unavailable_abstention(self):
        x=fixture();x['contracts'].append(dict(x['contracts'][0]));x['contracts'][-1]['contract_id']='nonroster';x['contracts'][-1]['player_id']='UNKNOWN'
        y=run_manifest(x,2,('J1',))
        self.assertEqual(y['contracts'][-1]['reason'],'PLAYER_NOT_IN_FROZEN_ROSTER')
    def test_unsupported_stat_abstention(self):
        x=fixture();x['contracts'][0]['stat_key']='passing_longest_50plus'
        y=run_manifest(x,2,('J1',))
        self.assertEqual(y['contracts'][0]['reason'],'UNSUPPORTED_STAT')
    def test_scenario_weights_frozen(self):self.assertAlmostEqual(sum(v[2] for v in SCENARIOS.values()),1)

if __name__=='__main__':unittest.main(verbosity=2)