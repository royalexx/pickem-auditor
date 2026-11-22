"""P6 adversarial mathematical reference tests: exact owner source is staged separately.

Independent reference calculations use SciPy, direct probability definitions and
closed-form formulas. Synthetic only: not a live source/settlement certification.
No production or owner source is modified.
"""
import importlib.util
import math
import os
import pathlib
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scipy.stats import poisson, nbinom

ROOT = pathlib.Path(os.environ.get("P6_SOURCE_ROOT", "/work/research/p6_qa_20261121/owner_source"))

def read_owner(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

P3 = read_owner("p6_owner_p3_distributions", "p3_distributions.py")
P5 = read_owner("p6_owner_p5_scoring", "p5_scoring.py")

def near(test, a, b, tol=1e-9):
    test.assertLessEqual(abs(a-b), tol, (a,b))

class IndependentCountChecks(unittest.TestCase):
    def test_p3_poisson_low_high(self):
        for mu in [0, 0.001, 0.07, 0.7, 3.0, 15.5, 80., 250.]:
            with self.subTest(mu=mu):
                got, tail = P3.pmf(mu)
                self.assertLess(tail, 1e-9)
                near(self, math.fsum(got.values()), 1., 1e-10)
                for k in [0, 1, 2, 4, 7, 20]:
                    near(self, got.get(k,0.), float(poisson.pmf(k,mu)), 1e-10)
                near(self, got.get(0,0.), math.exp(-mu), 1e-10)

    def test_p3_nb2_shapes(self):
        for mu, shape in [(0,4),(.07,.5),(.8,4),(3,4),(12,1.1),(20,8),(70,30)]:
            with self.subTest(mu=mu,shape=shape):
                got, tail = P3.pmf(mu,shape)
                self.assertLess(tail,1e-9)
                near(self,math.fsum(got.values()),1.,1e-10)
                ref = nbinom(shape,shape/(shape+mu))
                for k in [0,1,2,3,7,15,50]:
                    near(self,got.get(k,0.),float(ref.pmf(k)),1e-9)
                mean = math.fsum(k*p for k,p in got.items())
                variance = math.fsum((k-mean)**2*p for k,p in got.items())
                near(self,mean,mu,1e-7)
                near(self,variance,mu+mu*mu/shape,1e-5)

    def test_p3_integer_and_half_line(self):
        dist = {"kind":"nb2","parameters":{"mean":3.0,"shape":4.}}
        for line in [0,1,2,2.5,3,4.5]:
            got = P3.threshold(dist,line)
            ref = nbinom(4.,4./7.)
            under = float(ref.cdf(math.ceil(line)-1))
            push = float(ref.pmf(int(line))) if float(line).is_integer() else 0.
            near(self, got["under"],under,1e-10)
            near(self, got["push"],push,1e-10)
            near(self, math.fsum(got[s] for s in ("over","under","push")),1.,1e-12)

    def test_p3_opportunity_eligibility_not_inferred(self):
        with self.assertRaises(P3.ForecastBlocked):
            P3.opportunity_mixture(.2,[{"minutes":30., "probability":1.}],None)
        dist, _ = P3.opportunity_mixture(.2,[{"minutes":20.,"probability":1.}],.75)
        p_zero = P3.mass_dictionary(dist)[0]
        near(self,p_zero,.25+.75*math.exp(-4),1e-9)

    def test_p3_negative_support_rejected(self):
        for values in [{-1:1.}, {0:.5,1:.1}, {0:float("nan")}]:
            with self.subTest(values=values),self.assertRaises(P3.ForecastBlocked):
                P3.discrete(values)

    def test_p3_component_mixture_means(self):
        components=[(.3,1.,None),(.7,5.,4.)]
        dist,_=P3.mixture(components)
        stat=P3.statistics(dist)
        near(self,stat["mean"],3.8,1e-7)
        variance=.3*(1+(1-3.8)**2)+.7*(5+25/4+(5-3.8)**2)
        near(self,stat["variance"],variance,1e-5)

class IndependentSettlementScores(unittest.TestCase):
    def test_p5_poisson_gamma_nb2_numerical(self):
        laws=[
            ({"kind":"poisson","parameters":{"rate":2.5}},poisson(2.5)),
            ({"kind":"gamma_poisson","parameters":{"shape":3.,"rate":2.}},nbinom(3.,2./3.)),
            ({"kind":"nb2","parameters":{"mean":5.,"shape":4.}},nbinom(4.,4./9.))
        ]
        for d,ref in laws:
            with self.subTest(kind=d["kind"]):
                pmf,tail=P5.full_pmf(d,observed=5)
                self.assertLess(tail,1e-9)
                for k in range(12):
                    near(self,pmf[k],float(ref.pmf(k)),1e-11)
                near(self,math.fsum(pmf)+tail,1.,1e-9)
                score=P5.score_count(d,5,forecast_id="independent")
                near(self,score["nlpd"],-math.log(float(ref.pmf(5))),1e-11)
                near(self,score["signed_bias"],float(ref.mean())-5,1e-8)

    def test_p5_crps_independent_pair_identity(self):
        d={"kind":"discrete","masses":[[0,.2],[1,.5],[2,.3]]}
        masses=[.2,.5,.3]
        for actual in [0,1,2]:
            eabs=sum(p*abs(k-actual) for k,p in enumerate(masses))
            epair=sum(p*q*abs(i-j) for i,p in enumerate(masses)
                       for j,q in enumerate(masses))
            ref=eabs-.5*epair
            near(self,P5.score_count(d,actual)["crps"],ref,1e-12)

    def test_p5_matched_three_way_push(self):
        d={"kind":"discrete","masses":[[0,.2],[1,.5],[2,.3]]}
        q={"quote_kind":"real","accepted":True,"terms":{"dnp_policy":"void"},
           "line":1,"quote_id":"q1","contract_id":"c1","book":"testbook"}
        got=P5.score_contract(d,1,q)
        self.assertEqual(got["observed"],"push")
        for key,p in [("under",.2),("push",.5),("over",.3)]:
            near(self,got["probabilities"][key],p,1e-12)
        near(self,got["three_way_brier"],.2**2+(.5-1)**2+.3**2,1e-12)
        near(self,got["three_way_log_loss"],-math.log(.5),1e-12)

    def test_p5_void_is_not_push(self):
        d={"kind":"discrete","masses":[[0,1.]]}
        q={"quote_kind":"synthetic","accepted":True,"terms":{},"line":0,
           "quote_id":"q","contract_id":"c","book":"b"}
        with self.assertRaises(P5.ScoreError):
            P5.score_contract(d,0,q)

    def test_p5_zero_infinite_log_loss_explicit(self):
        d={"kind":"discrete","masses":[[0,1.0]]}
        s=P5.score_count(d,2)
        self.assertTrue(s["nlpd_infinite"])
        self.assertIsNone(s["nlpd"])

    def test_p5_randomized_pit_seed(self):
        d={"kind":"poisson","parameters":{"rate":3.}}
        a=P5.score_count(d,2,forecast_id="id-fixed")
        b=P5.score_count(d,2,forecast_id="id-fixed")
        self.assertEqual(a["randomized_pit"],b["randomized_pit"])
        self.assertGreaterEqual(a["randomized_pit"],0.)
        self.assertLessEqual(a["randomized_pit"],1.)

    def test_p5_joint_score_independent_two_particle_identity(self):
        paths=[[0.,0.],[2.,0.]]
        actual=[1.,0.]
        s=P5.score_joint(paths,actual,pair_budget=100)
        # E||X-y||=1, E||X-X'||=1.
        near(self,s["energy_score"],.5,1e-12)
        self.assertEqual(s["n_simulated_paths"],2)
        self.assertEqual(s["n_independent_observed_games"],1)

    def test_p5_impossible_nba_combo_fails(self):
        a={"points":10,"rebounds":5,"assists":3,"made_threes":2,
           "PR":15,"PA":13,"RA":8,"PRA":18}
        self.assertTrue(P5.validate_combo(a))
        a["PRA"]=19
        with self.assertRaises(P5.ScoreError):
            P5.validate_combo(a)

    def test_p5_corr_market_quotes_not_independent(self):
        rows=[{"event_id":"same_game","a":.1,"b":.2} for _ in range(50)]
        rows.extend([{"event_id":"another_game","a":.4,"b":.2}])
        result=P5.paired_differences(rows,n_boot=100)
        self.assertEqual(result["n_distinct_clusters"],2)
        near(self,result["mean_cluster_paired_difference"],.05,1e-12)

    def test_native_fixed_r_and_original_control_gate(self):
        mk = P5.LOCKED_NHL
        fields={"event_id":"e","player_id":"p","book":"book","quote_id":"q",
                "contract_id":"c","line":2.5,"source_manifest_sha256":"a"*64,
                "input_freeze_at":"2026-11-21T23:00:00Z",
                "original_mean":2.5,"outcome_id":"o","original_verified":True}
        nb=dict(fields,experiment_id=mk,model_family="native_nb2",shape=4)
        ctrl=dict(fields,model_family="plugin_poisson",source_classification="original_signed")
        self.assertEqual(P5.matched_native_nhl_pair(nb,ctrl)["shape"],4)
        nb["shape"]=5
        with self.assertRaises(P5.ScoreError):
            P5.matched_native_nhl_pair(nb,ctrl)

    def test_c10_utc_date_is_not_toronto_date_probe(self):
        # Same Toronto date, distinct UTC dates. This diagnostic records if the
        # current helper counts the incorrect calendar grouping (NO promotion).
        mk=P5.LOCKED_NHL
        base={"player_id":"p","book":"b","quote_id":"q","contract_id":"c",
              "line":2.5,"source_manifest_sha256":"a"*64,
              "input_freeze_at":"2026-11-21T22:00:00Z",
              "original_mean":2.5,"outcome_id":"o","original_verified":True}
        pairs=[]
        for i,start in enumerate(["2026-11-21T23:30:00Z","2026-11-22T00:30:00Z"]):
            f=dict(base,event_id=f"e{i}",event_start_at=start)
            nb=dict(f,model_family="native_nb2",shape=4,experiment_id=mk)
            ctrl=dict(f,model_family="plugin_poisson",source_classification="original_signed")
            pairs.append({"nb2":nb,"poisson":ctrl})
        toronto_dates={datetime.fromisoformat(pair["nb2"]["event_start_at"].replace("Z","+00:00")).astimezone(ZoneInfo("America/Toronto")).date() for pair in pairs}
        self.assertEqual(len(toronto_dates),1)
        observed=P5.matched_native_nhl_pair(pairs[0]["nb2"],pairs[0]["poisson"],verified_daily_cohort=pairs)
        # EXPECTED BUG REPRODUCER: on current head this will FAIL (2 != 1).
        self.assertEqual(observed["distinct_prospective_dates"],len(toronto_dates),
                         "UTC_DATE_USED_FOR_TORONTO_SLATE_DATE: owner P5 must verify registered date unit")

if __name__=="__main__":
    unittest.main(verbosity=2)
