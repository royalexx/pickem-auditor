"""Resealed cross-boundary attacks; deterministic synthetic evidence only."""
import copy
import unittest
from golden_v2 import golden_cases, j_scenarios, game_state, opportunity
from v2.nba_architecture.v2_contracts import ContractError, seal, validate_scenarios, validate_distribution
from v2.nba_architecture.families_v2 import validate_opportunity, validate_integration

def reseal(x):
    x=copy.deepcopy(x); x.pop('content_hash',None); return seal(x)

class Hardening(unittest.TestCase):
    def setUp(self):
        c=golden_cases()['joint_same_draw']
        self.p,self.g,self.o,self.j=c['pregame'],c['game_state'],c['opportunity'],c['scenarios']

    def test_endpoint_transition_enumeration(self):
        for prob in (None,0.,.01,.5,.99,1.):
            for index in (0,5):
                with self.subTest(prob=prob,index=index):
                    o=copy.deepcopy(self.o)
                    o['players'][index]['participation_probability']=prob
                    o['players'][index]['participation_evidence']='unknown' if prob is None else 'independently_estimated'
                    o=reseal(o)
                    invalid=(prob==0) or (prob==1 and index==5)
                    if invalid:
                        with self.assertRaises(ContractError): validate_opportunity(o,self.p,self.g)
                    else: self.assertTrue(validate_opportunity(o,self.p,self.g))

    def test_out_rejected_by_standalone_j(self):
        p=copy.deepcopy(self.p); p['players'][0]['availability']='out'; p=reseal(p)
        with self.assertRaises(ContractError): validate_scenarios(j_scenarios(p),p)

    def test_duplicate_opportunity_witness(self):
        j=copy.deepcopy(self.j); sid=j['scenarios'][0]['scenario_id']
        j['opportunity_witness'][sid].append(copy.deepcopy(j['opportunity_witness'][sid][0]))
        with self.assertRaises(ContractError): validate_scenarios(reseal(j),self.p)

    def test_nested_future_payload(self):
        j=copy.deepcopy(self.j); j['scenarios'][0]['players'][0]['target_actual_minutes']=48
        with self.assertRaises(ContractError): validate_scenarios(reseal(j),self.p)

    def test_unknown_conditioning(self):
        j=copy.deepcopy(self.j); j['conditioning']='arbitrary'
        with self.assertRaises(ContractError): validate_scenarios(reseal(j),self.p)

    def test_invalid_minutes_law_support(self):
        o=copy.deepcopy(self.o); o['players'][0]['minutes_law']['parameters']['median']=-1
        with self.assertRaises(ContractError): validate_opportunity(reseal(o),self.p,self.g)

    def test_unregistered_minutes_law(self):
        o=copy.deepcopy(self.o)
        o['players'][0]['minutes_law']['family']='unregistered_negative_support'
        o['players'][0]['minutes_law']['parameters']={'support':[-100,-1]}
        with self.assertRaises(ContractError): validate_opportunity(reseal(o),self.p,self.g)

    def test_player_reordering_preserves_integration(self):
        o=copy.deepcopy(self.o); o['players'].reverse()
        for sc in o['scenarios']: sc['players'].reverse()
        o=reseal(o); j=copy.deepcopy(self.j); j['opportunity_sha256']=o['content_hash']
        self.assertTrue(validate_integration(reseal(j),self.p,self.g,o))

class RevisionClosure(unittest.TestCase):
    def test_missing_receipt_parent(self):
        from golden_v2 import pregame
        from v2.nba_architecture.v2_contracts import receipt, validate_pregame
        p=copy.deepcopy(pregame())
        r=p['sources'][0]; r.pop('receipt_sha256'); r['source_revision']=2
        r['supersedes_receipt_sha256']='f'*64; r=receipt(r)
        p['sources']=[r]; p['features'][0]['source_receipt_sha256']=r['receipt_sha256']
        with self.assertRaises(ContractError): validate_pregame(reseal(p))
