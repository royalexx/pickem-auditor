"""Independent formula, SciPy and source time-travel checks for WS2."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.stats import geom, nbinom, poisson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from v2.nfl_marginal_shadow import (Law, MODEL_IDS, PARAMETERS, empirical, fit_laws,
    fixed_logit, probability_only, count_crps, gamma_prior)
from v2.contracts import canonical_hash
import nfl_ws2_shadow as runner

OWN = [0, 1, 0, 3, 2, 0, 1, 0]
PEERS = [[0, 1, 2, 0, 3+i] for i in range(5)]
NOW = '2026-11-15T12:00:00Z'
FREEZE = '2026-11-15T11:30:00Z'
TRAINED = '2026-11-14T00:00:00Z'


def source(root, name, obj, stamp='2026-11-13T00:00:00Z'):
    raw = runner.canonical(obj)
    (root/name).write_bytes(raw)
    return dict(source_id=name, first_available_at=stamp, retrieved_at=stamp,
                content_sha256=runner.sha(raw), archive_path=name,
                source_uri='https://example.org/'+name)


def fixture(root, *, stat='targets', own=OWN):
    raw = b'original provider bytes; fixture only'
    (root/'raw.bin').write_bytes(raw)
    q = dict(quote_id='q1', contract_id='c1', event_id='target-game',
        event_start_at='2026-11-15T18:00:00Z', sport='NFL', league='NFL',
        season=2026, team_id='teamA', opponent_id='teamB', player_id='subject',
        stat_key=stat, period='full', line=1.0, book='FixtureBook',
        product_type='sportsbook_two_sided', quote_at='2026-11-15T11:00:00Z',
        quote_receipt_sha256=runner.sha(raw), quote_archive_path='raw.bin',
        settlement_policy='strict_gt_lt_equal_push', quote_kind='real',
        over_decimal_odds=1.9, under_decimal_odds=1.9)
    eligibility=dict(quote=q, role='primary', position='WR', participation_basis='conditional_appearance_dnp_void')
    qs=source(root,'quotes.json',dict(quotes=[q],eligibility=[eligibility]),'2026-11-15T11:05:00Z')
    obs=[]
    for player, xs in [('subject',own)]+[(f'peer{i}',ys) for i,ys in enumerate(PEERS)]:
        for i,y in enumerate(xs):
            obs.append(dict(sport='NFL',stat_key=stat,period='full',position='WR',role='primary',
                event_id=f'old-{player}-{i}',player_id=player,observation_id=f'{player}-{i}',
                team_id='teamA',game_end_at=f'2026-10-{i+1:02}T22:00:00Z',
                available_at=f'2026-10-{i+2:02}T01:00:00Z',appearance='appeared',value=y))
    hs=source(root,'history.json',dict(observations=obs))
    c=dict(quote=q,model_version='production-historical-ensemble-60-40-20261108-v1',
           forecast_at='2026-11-15T11:10:00Z',q_over=.6,q_under=.3,q_push=.1)
    cs=source(root,'controls.json',dict(controls=[c]),'2026-11-15T11:15:00Z')
    return dict(schema=runner.SCHEMA,owner='workstream1',target_date=runner.TARGET,
        manifest_id='fixture-only',input_freeze_at=FREEZE,model_training_cutoff_at=TRAINED,
        sources=[qs,hs,cs],contracts=[dict(**eligibility,quote_source_id='quotes.json',
            history_source_ids=['history.json'],control_source_id='controls.json')])


def run(m, root, now=NOW):
    return runner.build(m,root=root,now=now,code_commit='c'*40,manifest_sha256=canonical_hash(m))


def revise(root,m,name,mutate):
    obj=json.loads((root/name).read_text())
    mutate(obj)
    raw=runner.canonical(obj)
    (root/name).write_bytes(raw)
    next(r for r in m['sources'] if r['source_id']==name)['content_sha256']=runner.sha(raw)


class MathematicalTests(unittest.TestCase):
    def laws(self):
        return fit_laws(OWN, PEERS, stat='targets')[0]

    def test_all_five_count_laws_implemented(self):
        self.assertEqual(set(self.laws()),set(MODEL_IDS[:5]))

    def test_normalization_support_and_moments(self):
        for name,law in self.laws().items():
            with self.subTest(model=name):
                mass=np.array([law.pmf(k) for k in range(500)])
                self.assertAlmostEqual(sum(mass),1,places=10)
                self.assertAlmostEqual(sum(k*p for k,p in enumerate(mass)),law.mean,places=9)
                self.assertAlmostEqual(sum((k-law.mean)**2*p for k,p in enumerate(mass)),law.variance,places=8)
                self.assertEqual(law.pmf(-1),0)
                self.assertEqual(law.pmf(.5),0)

    def test_analytical_poisson_pmf_against_scipy(self):
        for mu in (.001,.4,4,50,300):
            law=Law('poisson',{'rate':mu},mu,mu)
            for k in (0,1,2,20,100,300,1000):
                exact=math.exp(-mu+k*math.log(mu)-math.lgamma(k+1))
                self.assertAlmostEqual(law.pmf(k),exact,places=12)
                self.assertAlmostEqual(law.cdf(k)+law.sf(k),1,places=12)

    def test_gamma_poisson_integral_and_pmf(self):
        from scipy.integrate import quad
        from scipy.stats import gamma
        for a,b in ((.2,2),(4,3),(40,10)):
            law=Law('gamma_poisson',{'alpha':a,'beta':b},a/b,a/b+a/b**2)
            for k in (0,1,3,10):
                exact=math.exp(math.lgamma(a+k)-math.lgamma(a)-math.lgamma(k+1)+a*math.log(b/(b+1))-k*math.log(b+1))
                self.assertAlmostEqual(law.pmf(k),exact,places=12)
                integrated=quad(lambda x: poisson.pmf(k,x)*gamma.pdf(x,a,scale=1/b),0,np.inf)[0]
                self.assertAlmostEqual(law.pmf(k),integrated,places=8)
                self.assertAlmostEqual(law.cdf(k),sum(law.pmf(i) for i in range(k+1)),places=12)

    def test_hurdle_against_scipy_positive_geometric(self):
        law=self.laws()[MODEL_IDS[4]]
        z,q=law.parameters['p_zero'],law.parameters['positive_success']
        for k in (0,1,2,20,200):
            self.assertAlmostEqual(law.pmf(k),z if k==0 else (1-z)*geom.pmf(k,q),places=12)
            self.assertAlmostEqual(law.cdf(k),z+(1-z)*geom.cdf(k,q),places=12)
        boundary=Law('hurdle_geometric',{'p_zero':.25,'positive_success':1.},.75,.1875)
        self.assertEqual(boundary.cdf(0),.25)
        self.assertEqual(boundary.sf(0),.75)

    def test_integer_push_and_arbitrary_fractional_lines(self):
        for law in self.laws().values():
            for line in (-1,0,.1,.5,1,1.2,1.9,3,300):
                p=law.probabilities(line)
                self.assertAlmostEqual(p.over+p.under+p.push,1,places=12)
                expected=law.pmf(line) if float(line).is_integer() else 0
                self.assertAlmostEqual(p.push,expected,places=12)
                self.assertAlmostEqual(p.over,sum(law.pmf(k) for k in range(500) if k>line),places=10)

    def test_poisson_nb_same_mean_extra_uncertainty(self):
        laws=self.laws()
        a,b=laws[MODEL_IDS[2]],laws[MODEL_IDS[3]]
        self.assertEqual(a.mean,b.mean)
        self.assertGreater(b.variance,a.variance)
        self.assertNotEqual(a.probabilities(5.5).over,b.probabilities(5.5).over)

    def test_sample_size_shrinks_prior_influence(self):
        _,_,d1=fit_laws([10]*3,PEERS,stat='targets')
        _,_,d2=fit_laws([10]*30,PEERS,stat='targets')
        self.assertGreater(d1['empirical_prior_weight'],d2['empirical_prior_weight'])
        self.assertGreater(d1['posterior_rate']['prior_mean_weight'],d2['posterior_rate']['prior_mean_weight'])

    def test_ew_predeclared_schedule_and_ess(self):
        laws,_,diag=fit_laws([0,0,8],[],stat='targets')
        expected=8/(1+2**(-1/4)+2**(-2/4))
        self.assertAlmostEqual(laws[MODEL_IDS[1]].mean,expected)
        self.assertLess(diag['ew_kish_ess'],3)

    def test_signed_yardage_never_poisson(self):
        laws,reasons,_=fit_laws([-9,0,100,40],[[0,5,10]]*5,stat='rushing yards')
        self.assertEqual(set(laws),set(MODEL_IDS[:2]))
        self.assertGreater(laws[MODEL_IDS[0]].pmf(-9),0)
        self.assertEqual(reasons[MODEL_IDS[2]],'not_applicable_to_signed_count')

    def test_binary_support_no_duplicate_poisson_or_hurdle(self):
        laws,reasons,_=fit_laws([0,0,1],[[0,1,0]]*5,stat='anytime touchdown')
        self.assertEqual(set(laws),set(MODEL_IDS[:2]))
        self.assertTrue(all(l.pmf(2)==0 for l in laws.values()))
        self.assertEqual(reasons[MODEL_IDS[4]],'not_applicable_to_binary')

    def test_zero_heavy_rule_and_no_invented_positive_tail(self):
        laws,reasons,_=fit_laws([0]*5,[[0]*5]*5,stat='receiving touchdowns')
        self.assertEqual(laws[MODEL_IDS[0]].pmf(0),1)
        self.assertNotIn(MODEL_IDS[4],laws)
        self.assertIn('unidentified',reasons[MODEL_IDS[4]])
        laws,reasons,_=fit_laws([1,2,3],PEERS,stat='targets')
        self.assertNotIn(MODEL_IDS[4],laws)

    def test_count_crps_against_pairwise_expectation(self):
        for law in self.laws().values():
            x=np.arange(400)
            p=np.array([law.pmf(int(k)) for k in x])
            for y in (0,2,10):
                exact=np.dot(np.abs(x-y),p)-.5*np.sum(np.abs(x[:,None]-x[None,:])*p[:,None]*p[None,:])
                measured=count_crps(law,y)
                self.assertLessEqual(abs(measured['crps']-exact),measured['tail_error_upper_bound']+1e-11)

    def test_extreme_logit_and_exact_existing_formula(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from reform_step8_market_shadow import equal_logit_over
        for a in (0,1e-300,.01,.5,.99,1):
            for b in (0,1e-300,.1,.5,.9,1):
                p=fixed_logit(a,b)
                self.assertTrue(0<=p<=1)
                self.assertAlmostEqual(p,equal_logit_over({'over':a,'under':1-a},{'over':b,'under':1-b}),places=12)
        for bad in (float('nan'),float('inf'),-.1,1.1,True):
            with self.assertRaises(ValueError): fixed_logit(bad,.5)

    def test_probability_only_moments_unknown_push_not_invented(self):
        r=probability_only(.7,kind='test')
        self.assertIsNone(r['mean'])
        self.assertIsNone(r['variance'])
        self.assertIsNone(r['q_push'])


class SourceAndRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.m=fixture(self.root)
    def tearDown(self): self.tmp.cleanup()
    def first(self,m=None): return run(m or self.m,self.root)['forecast_rows'][0]

    def test_every_original_contract_and_all_models(self):
        r=run(self.m,self.root)
        self.assertEqual(r['input_contracts'],1)
        self.assertEqual(len(r['successful_versions']),8)
        self.assertEqual(len(r['distinct_versions_somewhere']),8)
        self.assertEqual(set(self.first()['models']),set(MODEL_IDS))
        self.assertFalse(r['production_modified'])
        self.assertEqual(r['status'],'UNCERTIFIED_SHADOW')

    def test_original_controls_untouched_and_push_conditioning(self):
        before=copy.deepcopy(self.m)
        r=self.first()
        self.assertEqual(self.m,before)
        self.assertAlmostEqual(r['controls']['frozen_60_40']['q_over'],.6)
        p=r['models'][MODEL_IDS[6]]
        self.assertAlmostEqual(p['q_push'],.1)
        self.assertAlmostEqual(p['q_over']+p['q_under']+p['q_push'],1)
        self.assertAlmostEqual(p['p_over_given_no_push'],.9*(.6/.9)+.1*.5)

    def test_market_disagreement_does_not_filter(self):
        revise(self.root,self.m,'controls.json',lambda o:o['controls'][0].update(q_over=.1,q_under=.8))
        r=self.first()
        self.assertEqual(r['models'][MODEL_IDS[5]]['status'],'forecast')
        self.assertLess(r['models'][MODEL_IDS[5]]['p_over_given_no_push'],.5)

    def test_tamper_source_bytes(self):
        (self.root/'history.json').write_text('{}')
        r=self.first()
        self.assertIn('hash_mismatch',r['models'][MODEL_IDS[0]]['reason'])
        self.assertEqual(r['models'][MODEL_IDS[5]]['status'],'forecast')

    def test_quote_identity_changes_reject_before_prediction(self):
        for key,value in [('line',1.5),('player_id','wrong'),('event_id','wrong'),('team_id','wrong')]:
            with self.subTest(key=key):
                m=copy.deepcopy(self.m);m['contracts'][0]['quote'][key]=value
                self.assertIn('not_bound',self.first(m)['eligibility_reason'])

    def test_target_game_other_player_leakage(self):
        revise(self.root,self.m,'history.json',lambda o:o['observations'][-1].update(event_id='target-game'))
        self.assertIn('target_slate_event',self.first()['models'][MODEL_IDS[0]]['reason'])

    def test_future_game_and_late_availability(self):
        for key in ('game_end_at','available_at'):
            self.m=fixture(self.root)
            revise(self.root,self.m,'history.json',lambda o:o['observations'][0].update({key:'2026-11-15T23:00:00Z'}))
            self.assertIn('future',self.first()['models'][MODEL_IDS[0]]['reason'])

    def test_history_source_after_training_cutoff(self):
        self.m['sources'][1]['first_available_at']='2026-11-15T00:00:00Z'
        self.m['sources'][1]['retrieved_at']='2026-11-15T00:00:00Z'
        self.assertIn('after_training',self.first()['models'][MODEL_IDS[0]]['reason'])

    def test_source_retrieved_after_freeze(self):
        self.m['sources'][0]['retrieved_at']='2026-11-15T11:40:00Z'
        self.assertIn('after_freeze',self.first()['eligibility_reason'])

    def test_unknown_participation_unavailable(self):
        self.m['contracts'][0]['participation_basis']='unknown'
        self.assertIn('unknown_participation',self.first()['eligibility_reason'])

    def test_dnp_not_zero_or_sample(self):
        revise(self.root,self.m,'history.json',lambda o:o['observations'][0].update(appearance='dnp',value=999))
        r=self.first()
        self.assertEqual(r['sample_diagnostics']['player_n'],len(OWN)-1)
        self.assertEqual(r['history_lineage']['source_rows_seen']-r['history_lineage']['eligible_appearance_rows'],1)

    def test_missing_peer_history_keeps_recent_model(self):
        revise(self.root,self.m,'history.json',lambda o:o.update(observations=[r for r in o['observations'] if r['player_id']=='subject']))
        r=self.first()
        self.assertEqual(r['models'][MODEL_IDS[1]]['status'],'forecast')
        self.assertIn('insufficient_role',r['models'][MODEL_IDS[0]]['reason'])

    def test_duplicate_history_fails_closed(self):
        revise(self.root,self.m,'history.json',lambda o:o['observations'].append(copy.deepcopy(o['observations'][0])))
        self.assertIn('duplicate_history',self.first()['models'][MODEL_IDS[1]]['reason'])

    def test_duplicate_contract_kept_as_reject(self):
        self.m['contracts'].append(copy.deepcopy(self.m['contracts'][0]))
        r=run(self.m,self.root)
        self.assertEqual(r['input_contracts'],2)
        self.assertIn('duplicate',r['forecast_rows'][1]['eligibility_reason'])

    def test_raw_quote_bytes_required(self):
        (self.root/'raw.bin').write_bytes(b'tampered')
        self.assertIn('raw_quote_hash',self.first()['eligibility_reason'])

    def test_control_wrong_contract_only_blocks_probability_scenarios(self):
        revise(self.root,self.m,'controls.json',lambda o:o['controls'][0]['quote'].update(line=5.5))
        r=self.first()
        self.assertEqual(r['models'][MODEL_IDS[0]]['status'],'forecast')
        self.assertEqual(r['models'][MODEL_IDS[5]]['status'],'unavailable')

    def test_no_market_inference_from_missing_odds(self):
        for key in ('over_decimal_odds','under_decimal_odds'):
            self.m['contracts'][0]['quote'][key]=None
        # Rebind the canonical input bytes to this explicit missing-price quote.
        q=self.m['contracts'][0]['quote']
        revise(self.root,self.m,'quotes.json',lambda o:(o.update(quotes=[q]),o['eligibility'][0].update(quote=q)))
        r=self.first()
        self.assertNotIn('market_only',r['controls'])
        self.assertEqual(r['models'][MODEL_IDS[5]]['status'],'unavailable')

    def test_no_backdating_after_kickoff(self):
        r=run(self.m,self.root,now='2026-11-15T18:00:00Z')['forecast_rows'][0]
        self.assertIn('not_pregame',r['eligibility_reason'])

    def test_naive_or_future_global_timestamps_reject(self):
        for bad in ('2026-11-15T11:00:00','2026-11-16T00:00:00Z'):
            m=copy.deepcopy(self.m);m['input_freeze_at']=bad
            with self.assertRaises(ValueError):run(m,self.root)

    def test_historical_source_retrieved_after_training_rejected(self):
        self.m['sources'][1]['retrieved_at']='2026-11-15T00:00:00Z'
        self.assertIn('after_training',self.first()['models'][MODEL_IDS[0]]['reason'])

    def test_malformed_input_retained_in_denominator(self):
        self.m['contracts'].append(None)
        r=run(self.m,self.root)
        self.assertEqual(r['input_contracts'],2)
        self.assertEqual(r['coverage']['contracts_fully_unavailable'],1)

    def test_source_path_traversal_and_symlink_rejected(self):
        self.m['sources'][0]['archive_path']='../escape.json'
        self.assertIn('invalid_archive_path',self.first()['eligibility_reason'])

    def test_success_count_not_inflated_for_identical_predictions(self):
        self.m=fixture(self.root,own=[1]*8)
        revise(self.root,self.m,'history.json',lambda o:[r.update(value=1) for r in o['observations']])
        r=run(self.m,self.root)
        self.assertIn('identical_prediction_to',r['forecast_rows'][0]['models'][MODEL_IDS[1]])
        self.assertLess(len(r['distinct_versions_somewhere']),len(r['successful_versions']))

    def test_append_only_freeze(self):
        path=self.root/'output.json'
        r=run(self.m,self.root)
        receipt=runner.freeze_report(r,path)
        self.assertEqual(receipt['sha256'],runner.sha(path.read_bytes()))
        with self.assertRaises(FileExistsError):runner.freeze_report(r,path)



class ScoringTests(unittest.TestCase):
    def test_matched_controls_pushes_and_count_crps(self):
        from nfl_ws2_score import evaluate
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=fixture(root);r=run(m,root)
            before=copy.deepcopy(r)
            q=m['contracts'][0]['quote']
            for actual in (0,1,2):
                score=evaluate(r,[dict(quote=q,actual=actual,status='verified',source_id='official-fixture')])
                outcome='under' if actual==0 else 'push' if actual==1 else 'over'
                self.assertEqual(score['denominators']['matched:'+outcome],1)
                if actual!=1:
                    entry=score['per_market']['targets'][MODEL_IDS[3]]
                    self.assertEqual(entry['matched_controls']['market_only']['candidate']['n'],1)
                    self.assertIn('crps',entry['distribution_metrics'])
                else:
                    entry=score['per_market']['targets'][MODEL_IDS[3]]
                    self.assertEqual(entry['all_available_binary']['n'],0)
                    self.assertEqual(entry['distribution_metrics']['three_outcome_brier']['n'],1)
            self.assertEqual(before,r)

    def test_no_reconstructed_or_wrong_line_settlements(self):
        from nfl_ws2_score import evaluate
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=fixture(root);r=run(m,root)
            q=copy.deepcopy(m['contracts'][0]['quote']);q['line']=2.5
            s=dict(quote=q,actual=2,status='verified',source_id='fixture')
            self.assertEqual(evaluate(r,[s])['denominators']['unmatched'],1)
            with self.assertRaisesRegex(ValueError,'duplicate'):evaluate(r,[s,s])

    def test_void_never_zero_or_push(self):
        from nfl_ws2_score import evaluate
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=fixture(root);r=run(m,root)
            s=dict(quote=m['contracts'][0]['quote'],status='void',source_id='fixture')
            result=evaluate(r,[s])
            self.assertEqual(result['denominators']['void'],1)
            self.assertEqual(result['per_market'],{})




class NativeWS1AdapterTests(unittest.TestCase):
    def test_actual_schema_rejects_preserve_complete_original_universe(self):
        from nfl_ws2_ws1_adapter import audit_native_ws1, canonical, digest
        src={'candidate_id':'candidate','stat':'receptions','source_certified':False,
             'forecast_eligible':False,'source_validation_failure':'EVENT_IDENTITY_UNVERIFIABLE',
             'frozen_control':{'Consensus_60_40':{'probability':None,'status':'NOT_ORIGINALLY_FROZEN'}}}
        obj={'schema':'nfl_20261115_source_control_v1','date':'2026-11-15','candidates':[src]}
        before=copy.deepcopy(obj);raw=canonical(obj)+b'\n';filename=digest(canonical(obj))+'.json'
        r=audit_native_ws1(raw,filename=filename,model_ids=MODEL_IDS,parameters=PARAMETERS,code_hashes={},now=NOW)
        self.assertEqual(r['input_rows'],1);self.assertEqual(r['forecast_count'],0)
        self.assertEqual(r['unavailable_contracts'],1)
        self.assertEqual(r['rows'][0]['frozen_control'],src['frozen_control'])
        self.assertEqual(obj,before)
        self.assertEqual(len(r['rows'][0]['models']),8)
        self.assertEqual(r['reason_counts'],{'EVENT_IDENTITY_UNVERIFIABLE':1})

    def test_native_hash_tamper_never_upgrades_source(self):
        from nfl_ws2_ws1_adapter import audit_native_ws1,canonical,digest
        obj={'schema':'nfl_20261115_source_control_v1','date':'2026-11-15','candidates':[]}
        raw=canonical(obj)+b'\n'
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):
            audit_native_ws1(raw,filename='a'*64+'.json',model_ids=MODEL_IDS,parameters=PARAMETERS,code_hashes={},now=NOW)

    def test_eligible_flag_alone_cannot_invent_history_or_controls(self):
        from nfl_ws2_ws1_adapter import audit_native_ws1,canonical,digest
        obj={'schema':'nfl_20261115_source_control_v1','date':'2026-11-15',
             'candidates':[{'candidate_id':'x','source_certified':True,'forecast_eligible':True,'stat':'targets'}]}
        raw=canonical(obj)+b'\n'
        r=audit_native_ws1(raw,filename=digest(canonical(obj))+'.json',model_ids=MODEL_IDS,parameters=PARAMETERS,code_hashes={},now=NOW)
        self.assertEqual(r['forecast_count'],0)
        self.assertIn('MODEL_HISTORY',r['rows'][0]['reason'])


if __name__=='__main__':unittest.main()
