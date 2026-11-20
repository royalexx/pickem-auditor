"""Independent reproducible checks of period-transitions and PIMH OT conditioning."""
import copy
import math
import unittest

from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.coherent_sensitivity_v1 import SEED,fixed_paired_scenario
from v2.nba_joint.conditional_periods_v1 import (
    empty_state,stage_transition,period_transition,source_transition_fidelity,
    finalize_path)
from v2.nba_joint.conditional_pimh_v1 import (
    bootstrap_particle_filter,pimh_sample,conditional_event_path)
from v2.nba_joint.common import rng_for


def real_model():
    from scripts.nba_coherent_mc_sensitivity import admitted_inputs
    return admitted_inputs()[0]


class ConditionalOTMathAndKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=real_model()
        cls.fixed0=fixed_paired_scenario(cls.model,SEED,0,None)
        cls.k1=cls.k2=None
        for i in range(256):
            k=fixed_paired_scenario(cls.model,SEED,i,None)['overtime_count']
            if k==1 and cls.k1 is None:cls.k1=i
            if k==2 and cls.k2 is None:cls.k2=i
            if cls.k1 is not None and cls.k2 is not None:break
        assert cls.k1 is not None and cls.k2 is not None

    def test_period_kernel_matches_original_unconditional_random_draws(self):
        for i in (0,1,self.k1,self.k2):
            fixed=fixed_paired_scenario(self.model,SEED,i,None)
            for attempt in (0,1):
                x=source_transition_fidelity(fixed,SEED,attempt)
                self.assertTrue(x['ledger_prefix_identical'])

    def test_period_prefix_explicit_original_NBA_five_man_accounting(self):
        fixed=self.fixed0
        rng=rng_for(SEED,fixed['game_id'],fixed['index'],'isolated-period')
        state=empty_state(fixed)
        for period in range(1,5):
            state=period_transition(fixed,state,rng,period)
        complete=finalize_path(fixed,state)
        self.assertEqual(len(complete['period_scores']),4)
        self.assertEqual(state['t'],48)
        with self.assertRaisesRegex(ValueError,'PIMH_PERIOD_SEQUENCE'):
            period_transition(fixed,state,rng,4)

    def test_stage_indicator_is_not_forced_and_tie_criterion(self):
        fixed=fixed_paired_scenario(self.model,SEED,self.k2,None)
        rng=rng_for(SEED,fixed['game_id'],fixed['index'],'OT-stage-test')
        initial=empty_state(fixed)
        state,valid=stage_transition(fixed,initial,rng,0)
        self.assertEqual(valid,
            state['score'][fixed['teams'][0]]==state['score'][fixed['teams'][1]])
        with self.assertRaisesRegex(ValueError,'PIMH_PREFIX_STAGE_MISMATCH'):
            stage_transition(fixed,initial,rng,1)

    def test_smoke_particle_filter_positive_or_declared_zero_weight(self):
        fixed=fixed_paired_scenario(self.model,SEED,self.k2,None)
        out=bootstrap_particle_filter(fixed,SEED,0,particles=16)
        self.assertIn(out['status'],('POSITIVE_PARTICLE_EVIDENCE',
                                     'ZERO_PARTICLE_EVIDENCE'))
        self.assertTrue(all(0<=x['indicator_fraction']<=1 for x in out['stages']))
        if out['status']=='POSITIVE_PARTICLE_EVIDENCE':
            self.assertEqual(out['path']['status'],'ACCEPTED_PATH_PROPOSAL')
            self.assertAlmostEqual(
               out['logZ'],
               sum(math.log(x['indicator_fraction']) for x in out['stages']))
            self.assertEqual(len(out['path']['period_scores']),6)

    def test_exact_k0_uses_frozen_rejection_kernel(self):
        record=conditional_event_path(self.fixed0,SEED,budget=32)
        self.assertEqual(record['status'],'EXACT_ORIGINAL_CONDITIONAL_REJECTION')
        self.assertTrue(record['finite_chain_is_exact_iid'])
        self.assertFalse(record['independent_P6_convergence_accepted'])

    def test_pimh_fail_closed_when_mixing_threshold_not_met(self):
        with self.assertRaisesRegex(ValueError,'PIMH_CHAIN_BUDGET'):
            pimh_sample(self.fixed0,SEED,particles=16,iterations=2,
                        minimum_accepted_moves=2)

    def test_pimh_reweights_particle_proposals_to_exact_toy_conditional(self):
        """Independent enumerated two-state reference, testing the MH ratio.

        X~Bern(1/2), terminal tie probability .9 for X=1, .1 for X=0.
        P(X=1 | tie)=.9; a finite-size particle proposal is not exact.
        """
        import numpy as np
        rng=np.random.default_rng(324390)
        n=2
        def proposal():
            latent=rng.integers(0,2,size=n)
            survive=[int(x) for x in latent
                     if rng.random()<(.9 if x==1 else .1)]
            if not survive:return None,0.
            return survive[int(rng.integers(len(survive)))],len(survive)/n
        current=None;weight=None;track=[];naive=[]
        for iteration in range(30000):
            proposed,phat=proposal()
            if phat:
                naive.append(proposed)
                if weight is None or rng.random()<min(1.,phat/weight):
                    current,weight=proposed,phat
            if iteration>=5000:
                track.append(current)
        # Exact target is .9, and finite particle output before PIMH
        # generally is biased toward the unconditioned .5 mixture.
        self.assertAlmostEqual(float(np.mean(track)),.9,delta=.025)
        self.assertLess(float(np.mean(naive)),.87)
        self.assertGreater(float(np.mean(naive)),.55)

    def test_unbiased_evidence_bpf_toy_analytical_reference(self):
        # A small two-stage finite model allows an independent exact
        # expectation check of the SMC normalizing constant identity.
        # State X~Bernoulli(.3); first potential G0=1 when X=1.
        # After resampling, Y~Bernoulli(.2 + .4 X), G1=1 when Y=1.
        # Exact P(G0=1,G1=1)=.3*.6=.18.
        import numpy as np
        rng=np.random.default_rng(20261120)
        n=16;reps=20000;res=[]
        for _ in range(reps):
            x=rng.random(n)<.3
            alive=int(x.sum())
            if not alive:
                res.append(0.);continue
            # Every resampled survivor has X==1.
            y=rng.random(n)<.6
            res.append((alive/n)*(int(y.sum())/n))
        estimate=float(np.mean(res))
        self.assertLess(abs(estimate-.18),.006)
        self.assertGreater(np.mean(res),0)


if __name__=='__main__':
    unittest.main()
