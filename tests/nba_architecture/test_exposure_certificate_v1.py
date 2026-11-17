"""Exact full-atom certificates, old budget red and adversarial mutations."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import unittest

from v2.nba_architecture.v2_contracts import seal, ContractError
from v2.nba_architecture.exposure_certificate_v1 import certify
from v2.nba_architecture.exposure_v2 import validate_exposure_coupling as old_coupling
from v2.nba_o_certified import build_opportunity

ROOT=Path(__file__).resolve().parents[2]


def build(n=32):
    x=json.loads((ROOT/'research/nba_p4_latest/fixtures_v2/inputs.json').read_bytes())
    p=x['pregame'];g=x['game_state'];original=g['scenarios']
    g={k:v for k,v in g.items() if k!='content_hash'};g['scenarios']=[]
    for i in range(n):
        s=deepcopy(original[i%len(original)]);s.update(scenario_id=f'certificate:{i}',weight=1/n);g['scenarios'].append(s)
    g=seal(g)
    o,_=build_opportunity(p,g,x['priors'],model=x['O_model'],seed=17,variant='O2',
        home_team_id=p['team_ids'][0],home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
    return p,g,o


def reseal(x):return seal({k:v for k,v in x.items() if k!='content_hash'})


class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.p,cls.g,cls.o=build()

    def test_actual_n32_complete_marginals_and_unknown_q_preserved(self):
        r=certify(self.o,self.p,self.g)
        self.assertEqual(r['positive_certificate_columns'],32)
        self.assertTrue(all(x['participation_probability'] is None for x in self.o['players']))
        self.assertTrue(all(v==['1','1'] for v in r['exact_bounds'].values()))
        self.assertGreater(Fraction(r['max_minute_residual']),0)
        self.assertLessEqual(Fraction(r['max_minute_residual']),Fraction(r['minute_tolerance']))
        self.assertFalse(r['genuine_participation_inferred'])

    def test_old_n32_budget_red_is_unchanged(self):
        with self.assertRaisesRegex(ContractError,'O_COUPLING_VERIFICATION_BUDGET'):
            old_coupling(self.o,self.p,self.g)

    def test_small_bounds_agree_with_complete_old_solver(self):
        for n in (4,8):
            p,g,o=build(n)
            self.assertEqual(certify(o,p,g)['bounds'],old_coupling(o,p,g))

    def test_64_columns_are_checked_without_cartesian_enumeration(self):
        p,g,o=build(64);self.assertEqual(certify(o,p,g)['positive_certificate_columns'],64)

    def test_tiny_missing_positive_atom_cannot_disappear(self):
        o=deepcopy(self.o);law=o['players'][0]['minutes_law']['parameters']['support']
        law.append(dict(minutes=0.,mass=1e-200))
        with self.assertRaises(ContractError):certify(reseal(o),self.p,self.g)

    def test_source_hash_and_identity_mutations_reject(self):
        for attack in ('hash','duplicate','team','state','minutes','q','atom','weight','ot'):
            o=deepcopy(self.o)
            if attack=='hash':o['source_snapshot_sha256']='a'*64
            elif attack=='duplicate':o['scenarios'][0]['players'][1]=deepcopy(o['scenarios'][0]['players'][0])
            elif attack=='team':o['scenarios'][0]['players'][0]['team_id']='espn:team:other'
            elif attack=='state':o['scenarios'][0]['players'][0]['participation']='DNP'
            elif attack=='minutes':o['scenarios'][0]['players'][0]['minutes']+=.001
            elif attack=='q':o['players'][0]['participation_probability']=.5
            elif attack=='atom':o['players'][0]['minutes_law']['parameters']['support'][0]['mass']+=1e-5
            elif attack=='weight':o['scenarios'][0]['weight']+=1e-5
            elif attack=='ot':o['scenarios'][0]['overtime_periods']+=1
            with self.subTest(attack=attack),self.assertRaises(ContractError):certify(reseal(o),self.p,self.g)

    def test_positive_count_requirement_is_bound_not_genuine_q(self):
        pid=self.o['players'][0]['player_id']
        certify(self.o,self.p,self.g,required_positive=(pid,1.))
        with self.assertRaisesRegex(ContractError,'FORECAST_COUNT_EXCEEDS_EXPOSURE'):
            certify(self.o,self.p,self.g,required_positive=(pid,1.0000000000000002))

    def test_played_zero_has_positive_participation_but_not_positive_exposure(self):
        p,g,o=build(4);g=deepcopy(g);o=deepcopy(o)
        for sc in g['scenarios']:sc['overtime_periods']=0
        # Existing G envelope has derived fields validated below; all original
        # fixture scenarios already have regulation duration in this construction.
        g=reseal(g);o['game_state_sha256']=g['content_hash']
        for team in p['team_ids']:
            people=[x for x in o['players'] if x['team_id']==team]
            ids=[x['player_id'] for x in people]
            for i,person in enumerate(people):
                person['minutes_law']['parameters']['support']=([dict(minutes=0.,mass=.5),dict(minutes=48.,mass=.5)] if i<2 else [dict(minutes=48.,mass=1.)])
            for j,sc in enumerate(o['scenarios']):
                sc['overtime_periods']=0
                for row in sc['players']:
                    if row['player_id'] in ids:
                        i=ids.index(row['player_id']);zero=i<2 and i==j%2
                        row['minutes']=0. if zero else 48.
                        row['participation']='PLAYED_ZERO_MINUTES' if zero else 'PLAYED'
        r=certify(reseal(o),p,g)
        self.assertEqual(r['exact_bounds'][o['players'][0]['player_id']],['1','1/2'])


if __name__=='__main__':unittest.main()
