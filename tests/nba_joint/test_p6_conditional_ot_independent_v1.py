"""P6-only adversarial review of the S4/J conditional-OT research sampler.

NO changes to original source, forecasting formula, probability model, fitted
priors, historical outcomes, eligibility or production. Evidence checks
are intentionally independent of the implementing family's own unit tests.
This test suite is an adversarial engineer's additional evidence, NOT an
organizational independent-approver signature.
"""
import copy
import math
import unittest

from scripts.nba_coherent_mc_pimh import admitted_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_joint.coherent_sensitivity_pimh_v1 import (
    SEED, VARIANTS, fixed_paired_scenario, fixed_pair_invariants)
from v2.nba_joint.conditional_pimh_v1 import (
    VERSION, conditional_event_path, sequential_period_conditional_proposal,
    bootstrap_particle_filter)
from v2.nba_joint.conditional_periods_v1 import source_transition_fidelity
from v2.nba_joint.residual_audit_v1 import audit_path
from v2.nba_joint.residual_events_v1 import event_path


class P6AdversarialOTReadOnlyAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.cohort = admitted_inputs()
        cls.ids={x["player_id"] for x in cls.model["named_players"]}
        cls.TEAMS={p["team_id"] for p in cls.model["named_players"]}

    def make(self,index,weight=None):
        return fixed_paired_scenario(self.model,SEED,index,weight)

    def test_k0_and_k1_remain_exact_old_events_not_PIMH(self):
        selected={0:None,1:None}
        for i in range(128):
            f=self.make(i);k=f["overtime_count"]
            if k in selected and selected[k] is None:selected[k]=i
            if all(v is not None for v in selected.values()):break
        self.assertTrue(all(v is not None for v in selected.values()))
        for k,index in selected.items():
            for name,z in VARIANTS[:3]:
                fixed=self.make(index,z)
                old_rejections=[]
                for attempt in range(4096):
                    sample=event_path(fixed,SEED,attempt)
                    if sample["status"]=="ACCEPTED_PATH_PROPOSAL":break
                    self.assertEqual(sample["status"],"REJECT_OT_PATTERN")
                    old_rejections.append(digest(canonical(sample)))
                out=conditional_event_path(fixed,SEED,budget=4096)
                self.assertEqual(out["status"],"EXACT_ORIGINAL_CONDITIONAL_REJECTION")
                self.assertTrue(out["finite_chain_is_exact_iid"])
                self.assertEqual(out["rejected_count"],len(old_rejections))
                self.assertEqual(out["accepted_path_raw_sha256"],digest(canonical(sample)))
                self.assertEqual(out["path"]["counts"],sample["counts"])
                self.assertEqual(audit_path(fixed,out["path"])["violations"],0)

    def test_source_copied_period_transition_matches_complete_raw_ledger(self):
        for i in (0,1,297,6711):
            f=self.make(i)
            for attempt in (0,1,2):
                r=source_transition_fidelity(f,SEED,attempt)
                self.assertTrue(r["ledger_prefix_identical"])

    def test_Q_is_admitted_only_as_approximation_for_K2_and_K4(self):
        for i in (297,6711):
            f=self.make(i)
            self.assertGreaterEqual(f["overtime_count"],2)
            out=sequential_period_conditional_proposal(f,SEED)
            self.assertEqual(out["status"],"RESEARCH_PERIOD_CONDITIONAL_Q_BOUNDED")
            self.assertFalse(out["original_target_distribution_exact"])
            self.assertFalse(out["exact_original_conditional_law_is_stationary"])
            self.assertFalse(out["finite_chain_is_exact_iid"])
            self.assertFalse(out["independent_P6_convergence_accepted"])
            self.assertEqual(len(out["counts"]),1+f["overtime_count"])
            self.assertEqual(audit_path(f,out["path"])["violations"],0)
            self.assertEqual(len(out["path"]["period_scores"]),4+f["overtime_count"])
            self.assertEqual(out["path"]["status"],"ACCEPTED_PATH_PROPOSAL")

    def test_seq_conditioning_is_not_original_full_conditional_law(self):
        # Finite two-stage counterexample: X~Bernoulli(.5);
        # first A0 succeeds with P(.2|X1),P(.8|X0);
        # future A1 succeeds with P(.9|X1),P(.1|X0).
        # Sequential conditioning on A0 alone yields P(X1)=.2;
        # conditioning jointly yields P(X1)=.09/(.09+.04)=9/13.
        first=0.5*.2/(0.5*.2+0.5*.8)
        joint=0.5*.2*.9/(0.5*.2*.9+0.5*.8*.1)
        self.assertAlmostEqual(first,.2)
        self.assertAlmostEqual(joint,9/13)
        self.assertGreater(joint-first,.49)

    def test_pq_tv_bound_unconditional_applies_to_any_stat_indicator(self):
        pars={(p["minutes"]["ot_probability"],p["minutes"]["ot_continuation"])
              for p in self.model["named_players"]}
        self.assertEqual(len(pars),1)
        p,q=next(iter(pars))
        self.assertAlmostEqual(p*q,0.00634719136781974)
        self.assertGreater(p*q,0)
        # Even an *adversarial disjoint* K>=2 replacement law changes
        # any count event probability by at most P(K>=2).
        old=[.15,.85];new=[1.,0.]
        for a,b in zip(old,new):
            self.assertLessEqual(abs((1-p*q)*a+p*q*b-a),p*q+1e-12)

    def test_PIMH_is_stationary_target_not_finite_iid_claim(self):
        f=self.make(297)
        p=bootstrap_particle_filter(f,SEED,0,particles=32)
        self.assertIn(p["status"],("ZERO_PARTICLE_EVIDENCE",
                                   "POSITIVE_PARTICLE_EVIDENCE"))
        if p["status"]=="ZERO_PARTICLE_EVIDENCE":
            self.assertEqual(p["evidence_estimate"],0)
            self.assertIsNone(p["path"])
        else:
            self.assertGreater(p["evidence_estimate"],0)
            self.assertTrue(math.isfinite(p["logZ"]))
            self.assertEqual(audit_path(f,p["path"])["violations"],0)
        out=conditional_event_path(f,SEED,particles=24,iterations=4,min_moves=0)
        self.assertIn(out["status"],("RESEARCH_FINITE_CHAIN_MIXED",
                                     "FAIL_CANNOT_ASSESS_MIXING"))
        self.assertFalse(out["finite_chain_is_exact_iid"])
        self.assertFalse(out["independent_P6_convergence_accepted"])

    def test_fixed_basketball_opportunity_parameters_do_not_change_with_z(self):
        f=self.make(297)
        self.assertEqual(len(self.ids),14)
        self.assertEqual(len(self.TEAMS),2)
        for name,z in VARIANTS[1:]:
            g=self.make(297,z)
            self.assertTrue(fixed_pair_invariants(f,g))
            self.assertEqual(digest(canonical(f["event_probabilities"])),
                             digest(canonical(g["event_probabilities"])))
            self.assertEqual(f["overtime_count"],g["overtime_count"])
            self.assertEqual(f["pace"],g["pace"])


if __name__=="__main__":
    unittest.main()
