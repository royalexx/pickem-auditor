"""Phase 3 Monte Carlo: deterministic posterior integration and append-only audits."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bayesian_engine as ba
import bayesian_usage as bu
import posterior_mc as mc
import posterior_mc_shadow as shadow
import posterior_mc_audit as audit


def observations(player,n=12,*,count=False):
    return [(f'{player}-{i}',float(1+i%4 if count else 10+2*(i%4)),
             float(18+(i%5))) for i in range(n)]


def peer_values():
    return [[float(2+(i+j)%3) for j in range(12)] for i in range(7)]


def workload_peers(*,count=False):
    return [observations(f'p{i}',15,count=count) for i in range(7)]


def a_model(dist):
    data=[1.,2.,3.,4.,1.,3.,2.,4.,3.,2.,1.,4.]
    model=ba.forecast(data,peer_values(),dist=dist,line=2.5,side='over',
                       var_ratio=1.6 if dist=='negbin' else None)
    model.update(status='forecast',posterior_mean=model['mean'])
    return model,data


def b_model(dist):
    pairs=observations('x',count=(dist!='normal'))
    peers=workload_peers(count=(dist!='normal'))
    p=bu.forecast(pairs,peers,dist=dist,line=2.5 if dist!='normal' else 11.5,
                  side='over',var_ratio=1.6 if dist=='negbin' else None,
                  stat='shots on goal' if dist!='normal' else 'receiving yards',
                  sport='NHL' if dist!='normal' else 'NFL')
    p.update(status='forecast',distribution=dist,workload_posterior=p['workload'],
             conversion_posterior=p['conversion'])
    return p,pairs,peers


class SimulationMathTests(unittest.TestCase):
    def test_deterministic_seed_and_no_global_random(self):
        a,_=a_model('poisson')
        k=dict(engine='A',identity=['2026-10-28','p','shots','over'],line=2.5,side='over',
               draws=1024,max_draws=2048,target=.015)
        first=mc.simulate(a,**k)
        second=mc.simulate(a,**k)
        self.assertEqual(first,second)
        self.assertNotEqual(first['seed'],mc.simulate(a,**{**k,'identity':['other']})['seed'])
        self.assertFalse(first['publication_eligible'])
        self.assertEqual(first['method'],'posterior_latent_mc_observation_noise_integrated')
        self.assertAlmostEqual(first['q_win']+first['q_push']+first['q_loss'],1,places=10)

    def test_a_gamma_poisson_matches_analytic_both_sides(self):
        a,_=a_model('poisson')
        for side in ('over','under'):
            row=dict(a,q_win=a['q_over'] if side=='over' else a['q_under'])
            result=mc.simulate(row,engine='A',identity=['x',side],line=2.5,side=side,
                               draws=1024,max_draws=4096,target=.008)
            self.assertLess(abs(result['q_win']-row['q_win']),.03)
            self.assertTrue(result['analytic_agreement'])

    def test_a_nb_grid_compares_properly(self):
        a,values=a_model('negbin')
        result=mc.simulate(a,engine='A',identity=['a-nb'],line=2.5,side='over',
                           draws=1024,max_draws=4096,target=.009,values=values)
        self.assertTrue(result['analytic_agreement'])
        self.assertAlmostEqual(result['q_win']+result['q_loss'],1,places=9)
        with self.assertRaisesRegex(ba.ModelUnavailable,'a_negbin_requires'):
            mc.simulate(a,engine='A',identity=['x'],line=2.5,side='over')

    def test_a_normal_student_posterior_matches_analytic(self):
        result=ba.forecast([9.,11.,12.,9.,10.,8.,12.,11.],peer_values(),dist='normal',
                           line=10.5,side='over')
        result.update(status='forecast',posterior_mean=result['mean'])
        simulated=mc.simulate(result,engine='A',identity=['a-normal'],line=10.5,
                              side='over',draws=1024,max_draws=4096,target=.009)
        self.assertTrue(simulated['analytic_agreement'])

    def test_b_poisson_and_normal_conditional_uncertainty(self):
        for dist in ('poisson','normal'):
            posterior,_,_=b_model(dist)
            line=2.5 if dist=='poisson' else 11.5
            result=mc.simulate(posterior,engine='B',identity=['b',dist],
                   line=line,side='over',draws=1024,max_draws=4096,target=.01)
            self.assertAlmostEqual(result['q_win']+result['q_loss'],1,places=9)
            self.assertGreater(result['draws'],0)
            # B analytic integrates only 17 equally spaced posterior workload
            # quantiles, hence a nonzero discretization gap can be genuine.
            self.assertLess(abs(result['q_win']-posterior['q_win']),.08)

    def test_b_negative_binomial_reconstruction(self):
        posterior,pairs,peers=b_model('negbin')
        result=mc.simulate(posterior,engine='B',identity=['b','nb'],line=2.5,side='over',
                           draws=1024,max_draws=4096,target=.01,pairs=pairs,peers=peers)
        self.assertTrue(0<=result['q_win']<=1)
        with self.assertRaisesRegex(ba.ModelUnavailable,'b_negbin_requires'):
            mc.simulate(posterior,engine='B',identity=['missing'],line=2.5,side='over')

    def test_whole_line_push_and_invalid_configuration(self):
        over,under,push=mc.conditional_probs('poisson',2.8,2)
        self.assertAlmostEqual(over+under+push,1)
        self.assertGreater(push,0)
        a,_=a_model('poisson')
        with self.assertRaisesRegex(ba.ModelUnavailable,'invalid_mc_sample_budget'):
            mc.simulate(a,engine='A',identity=['bad'],line=2.5,side='over',
                        draws=128,max_draws=128)
        with self.assertRaisesRegex(ba.ModelUnavailable,'unsupported_nb_ratio'):
            mc.conditional_probs('negbin',2.8,2,ratio=1.02)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.row={'forecast_at':'2026-10-28T19:00:00Z','event_start':'2026-10-28T23:00:00Z',
            'game_date':'2026-10-28','run_type':'shadow','sport':'NHL','player':'Example',
            'player_id':'99','team':'BOS','stat':'shots on goal','side':'over',
            'reference_line':2.5,'run_id':'run1','inputs':{'scouting':{'historical_usage':'ref'}},
            'engine_a':{'version':'history-v5','q_win_robust':.55},
            'engine_b':{'version':'scouting-v7','q_win':.54}}

    def test_two_simulations_on_original_matching_shadows(self):
        a,_=a_model('poisson')
        b,_,_=b_model('poisson')
        parent_a={**self.row,**a,'version':ba.VERSION,'status':'forecast',
                  'source_digest':'source-1','input_fingerprint':'fp','publication_eligible':False,
                  'posterior_mean':a['mean']}
        parent_b={**self.row,**b,'version':bu.VERSION,'status':'forecast',
                  'source_digest':'source-1','inputs_hash':'fp','publication_eligible':False}
        answer=shadow.evaluate(self.row,parent_a,parent_b,root=Path('/unused'),
                               min_draws=1024,max_draws=2048,target=.012)
        self.assertEqual(answer['engines']['A']['status'],'forecast')
        self.assertEqual(answer['engines']['B']['status'],'forecast')
        self.assertFalse(answer['publication_eligible'])
        self.assertTrue(answer['engines']['A']['seed']!=answer['engines']['B']['seed'])

    def test_missing_shadows_and_poststart_fail_closed(self):
        result=shadow.evaluate(self.row,None,None,root=Path('/missing'))
        self.assertEqual(result['engines']['A']['status'],'unavailable')
        self.assertEqual(result['engines']['B']['status'],'unavailable')
        later={**self.row,'event_start':'2026-10-28T18:00:00Z'}
        a,_=a_model('poisson')
        a={**a,'status':'forecast','source_digest':'x','input_fingerprint':'x',
             'posterior_mean':a['mean'],'publication_eligible':False}
        self.assertEqual(shadow.evaluate(later,a,None,root=Path('/missing'))['engines']['A']['status'],
                         'unavailable')

    def test_sidecar_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);src=p/'original.jsonl';src.write_text(json.dumps(self.row)+'\n')
            out=p/'mc.jsonl';receipt=p/'receipt.json'
            f=lambda:shadow.run(date='2026-10-28',original=src,
                       a_sidecar=p/'missingA',b_sidecar=p/'missingB',root=p,
                       output=out,receipt=receipt)
            first=f()
            self.assertEqual(first['new_rows'],1)
            self.assertEqual(f()['new_rows'],0)
            self.assertEqual(json.loads(src.read_text()),self.row)
            out.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'INVALID_MONTE_CARLO_SIDECAR'):
                f()


class AuditTests(unittest.TestCase):
    def test_audit_joins_exact_pregame_identity_and_proper_scoring(self):
        row={'game_date':'2026-10-28','sport':'NHL','player_id':'99','stat':'shots on goal',
             'side':'over','reference_line':2.5,'forecast_at':'2026-10-28T19:00:00Z',
             'event_start':'2026-10-28T23:00:00Z','run_id':'r',
             'actual_stat':4,'outcome':'win',
             'engine_a':{'q_win_robust':.6,'q_push_robust':0},
             'engine_b':{'q_win':.7,'q_push':0}}
        outcome={**row,'engines':{'A':{'status':'forecast','publication_eligible':False,
                       'q_win':.8,'q_push':0.,'analytic_q_win':.6,'analytic_q_push':0.},
                    'B':{'status':'unavailable'}},'version':mc.VERSION,
                 'publication_eligible':False}
        with tempfile.TemporaryDirectory() as root:
            p=Path(root); original=p/'original.jsonl'; original.write_text(json.dumps(row)+'\n')
            d=p/'montecarlo'; d.mkdir()
            (d/'2026-10-28.jsonl').write_text(json.dumps(outcome)+'\n')
            report=audit.audit(original,d)
            self.assertEqual(report['matched_settled_forecasts'],1)
            self.assertEqual(report['comparators']['A_mc']['n'],1)
            self.assertAlmostEqual(report['comparators']['A_mc']['log_loss'],-math.log(.8))
            self.assertEqual(report['comparators']['B_mc']['n'],0) if 'B_mc' in report['comparators'] else None
            self.assertTrue(report['no_retraining'])
            original.write_text('')
            self.assertEqual(audit.audit(original,d)['matched_settled_forecasts'],0)

if __name__=='__main__':
    unittest.main()
