"""P5 adversarial/scientific synthetic unit tests; no 2023-24 results read."""
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import nbinom

from v2.nba_c import scores as s
from v2.nba_c import experiment as e
from v2.nba_c.warehouse import _write_once, WarehouseError


def fixture(stat="points",date="2022-10-20T00:00:00Z",actual=0,game="nba:g1"):
    # Three COMPLETE alternative distribution pipelines. S/O/J are not votes.
    d=date[:10]
    return {"game_id":game, "player_id":"nba:player1","stat":stat,
            "source_profile":"SYNTHETIC","actual":actual,"date":date,
            "frozen_at":d+"T17:00:00Z","event_start_at":d+"T23:00:00Z",
            "official_available_at":(e._utc(date)+e.timedelta(days=1)).isoformat(),
            "pipelines":{
                "S0":{"mode":"S_ONLY","pmf":{0:.9,1:.1}},
                "SO0":{"mode":"S_O","pmf":{0:.1,1:.9}},
                "J0":{"mode":"S_O_J","pmf":{0:.5,1:.5}}
            }}


class TestScores(unittest.TestCase):
    def test_point_mass(self):
        self.assertEqual(s.crps({4:1},4),0)
        self.assertEqual(s.crps({4:1},1),3)
        self.assertEqual(s.nll({4:1},4),0)
        self.assertTrue(math.isinf(s.nll({4:1},5)))

    def test_bernoulli_reference(self):
        self.assertAlmostEqual(s.crps({0:.75,1:.25},0),.25**2)
        self.assertAlmostEqual(s.crps({0:.75,1:.25},1),.75**2)
        self.assertAlmostEqual(s.nll({0:.75,1:.25},0),-math.log(.75))

    def test_negative_binomial_reference(self):
        # NB failures before 2 successes at p=0.5; CRPS(y=0)=26/27.
        k=np.arange(0,150)
        mass=nbinom.pmf(k,2,.5)
        pmf={int(i):float(x) for i,x in zip(k,mass)}
        self.assertAlmostEqual(s.crps(pmf,0),26/27,places=9)
        self.assertAlmostEqual(s.reference_crps(pmf,0),26/27,places=9)

    def test_brute_cdf_and_sparse_support(self):
        rng=np.random.default_rng(72)
        for _ in range(50):
            keys=sorted(rng.choice(80,size=8,replace=False).tolist())
            weights=rng.dirichlet(np.ones(8))
            pmf=dict(zip(keys,weights))
            y=int(rng.integers(0,90))
            brute=sum((sum(v for k,v in pmf.items() if k<=t)-int(y<=t))**2
                      for t in range(max(max(keys),y)+1))
            self.assertAlmostEqual(s.crps(pmf,y),brute,places=9)

    def test_zero_and_tail(self):
        z=s.diagnostics({0:.2,2:.3,40:.5},40,seed=1,tail_threshold=30)
        self.assertEqual(z["tail_predicted"],.5)
        self.assertEqual(z["tail_observed"],1)
        self.assertEqual(z["zero_predicted"],.2)
        self.assertEqual(z["signed_bias"],.2*0+.3*2+.5*40-40)

    def test_pit_exact_and_seed(self):
        self.assertAlmostEqual(s.randomized_pit({0:.2,1:.8},1,u=.5),.6)
        x=s.randomized_pit({0:.2,1:.8},1,seed=123)
        self.assertEqual(x,s.randomized_pit({0:.2,1:.8},1,seed=123))
        with self.assertRaises(s.ScoreError):
            s.randomized_pit({0:1},0)

    def test_coverage_quantile(self):
        self.assertEqual(s.quantile({0:.1,3:.7,10:.2},.5),3)
        self.assertTrue(s.diagnostics({0:.1,3:.7,10:.2},3,seed=2)["covered"])
        self.assertFalse(s.diagnostics({0:.1,3:.7,10:.2},100,seed=2)["covered"])

    def test_aggregate_mae_rmse_bias(self):
        rows=[s.diagnostics({1:1},0,seed=0),s.diagnostics({3:1},2,seed=1)]
        agg=s.aggregate(rows)
        self.assertEqual(agg["mae"],1)
        self.assertEqual(agg["rmse"],1)
        self.assertEqual(agg["signed_bias"],1)
        self.assertEqual(agg["n_forecast_rows_not_scenarios"],2)

    def test_invalid_pmf(self):
        bad=[{0:.2}, {0:-.1,1:1.1},{0:float("nan")}, [(0,.5),(0,.5)],{-1:1}, {0:True}]
        for pmf in bad:
            with self.subTest(pmf=pmf), self.assertRaises(s.ScoreError):
                s.validate_pmf(pmf)

    def test_joint_exact_energy_variogram(self):
        sc=[((0,0),.5),((2,0),.5)]
        self.assertAlmostEqual(s.energy_score(sc,(2,0)),.5)
        self.assertAlmostEqual(s.variogram_score(sc,(2,0),power=.5),.5)
        self.assertEqual(dict(s.scenarios_to_pmf(sc)),{0:.5,2:.5})

    def test_joint_mc_seed(self):
        sc=[((i%3,(i+1)%4),1/300) for i in range(300)]
        a=s.energy_score(sc,(1,2),max_pair_terms=1200,seed=84)
        self.assertEqual(a,s.energy_score(sc,(1,2),max_pair_terms=1200,seed=84))

    def test_invalid_joint(self):
        for sc in [[((0,1),.3)],[((0,1),1.1)],[((0,float("nan")),1)]]:
            with self.assertRaises(s.ScoreError):
                s.energy_score(sc,(0,1))


class TestExperiment(unittest.TestCase):
    def setUp(self):
        self.rows=[fixture(date=f"2022-10-{20+i:02d}T00:00:00Z",
                           game=f"nba:g{i}") for i in range(5)]
        self.cache=e.CachedCohort(self.rows,authorization="SYNTHETIC_UNIT_TEST")

    def test_guard_historical_fit(self):
        with self.assertRaisesRegex(e.ExperimentError,"NOT_AUTHORIZED"):
            e.CachedCohort(self.rows)
        bad=[dict(self.rows[0],source_profile="historical_reconstruction")]
        with self.assertRaisesRegex(e.ExperimentError,"ONLY_SYNTHETIC"):
            e.CachedCohort(bad,authorization="SYNTHETIC_UNIT_TEST")

    def test_w0_w1_and_optimizer(self):
        zero=e.w0_simple(self.cache,"S0")
        self.assertEqual(sum(zero.values()),1)
        self.assertEqual(zero["S0"],1)
        equal=e.w1_equal(self.cache)
        learned=e.w2_global(self.cache,lam=.01)
        self.assertAlmostEqual(sum(learned.values()),1)
        self.assertTrue(all(v>=0 for v in learned.values()))
        self.assertLessEqual(self.cache.crps_for(list(learned[k] for k in self.cache.pipeline_ids)),
                             self.cache.crps_for(list(equal[k] for k in self.cache.pipeline_ids)))
        self.assertAlmostEqual(self.cache.crps_for([zero[k] for k in self.cache.pipeline_ids]),
                               sum(s.crps(self.rows[i]["pipelines"]["S0"]["pmf"],0)
                                   for i in range(5))/5,places=12)

    def test_w3_shrinkage(self):
        global_w=e.w2_global(self.cache,lam=.1)
        out=e.w3_by_stat(self.rows,global_weights=global_w,lam=2,min_games=3)
        self.assertEqual(set(out),{"points"})
        self.assertAlmostEqual(sum(out["points"].values()),1)
        self.assertEqual(e.w3_by_stat(self.rows,global_weights=global_w,min_games=20)["points"],global_w)

    def test_w4_stays_disabled(self):
        with self.assertRaisesRegex(e.ExperimentError,"W4_CONDITIONAL"):
            e.w4_contextual_gating()

    def test_seeded_cached_monte_carlo(self):
        a=e.explore_simplex(self.cache,seed=88,trials=100)
        self.assertEqual(a,e.explore_simplex(self.cache,seed=88,trials=100))
        self.assertEqual(a["cached_pmf_count"],15)
        self.assertEqual(a["game_count"],5)

    def test_probe_5000_20000(self):
        a=e.mc_precision_probe({0:.2,1:.3,2:.5},seed=19)
        self.assertEqual(a,e.mc_precision_probe({0:.2,1:.3,2:.5},seed=19))
        self.assertEqual(a["se_ratio_nonzero"],2)
        self.assertEqual(a["counts"],[5000,20000])

    def test_cluster_bootstrap_paired(self):
        a=[{"date":"2022-10-20","game_id":"nba:g1","challenger_score":.2,"control_score":.3},
           {"date":"2022-10-20","game_id":"nba:g1","challenger_score":.4,"control_score":.5},
           {"date":"2022-10-21","game_id":"nba:g2","challenger_score":.1,"control_score":.6}]
        out=e.paired_block_bootstrap(a,seed=12,repeats=200)
        self.assertAlmostEqual(out["estimate"],(-.1-.1-.5)/3)
        self.assertEqual(out,e.paired_block_bootstrap(a,seed=12,repeats=200))
        self.assertEqual(out["clusters"],2)

    def test_invalid_matched_coverage(self):
        bad=self.rows.copy()
        bad[0]=dict(bad[0],pipelines={"S0":bad[0]["pipelines"]["S0"]})
        with self.assertRaisesRegex(e.ExperimentError,"INCOMPLETE_MATCHED"):
            e.CachedCohort(bad,authorization="SYNTHETIC_UNIT_TEST")

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(e.ExperimentError,"DUPLICATE"):
            e.CachedCohort(self.rows+[self.rows[0]],authorization="SYNTHETIC_UNIT_TEST")

    def test_holdout_quarantined(self):
        bad=fixture(date="2023-10-30T00:00:00Z")
        with self.assertRaisesRegex(e.ExperimentError,"HOLDOUT"):
            e.CachedCohort([bad],authorization="SYNTHETIC_UNIT_TEST")

    def test_fold_no_future_released_labels(self):
        meta=[{k:r[k] for k in ("game_id","player_id","stat","frozen_at",
                "event_start_at","official_available_at","date")} for r in self.rows]
        folds=e.make_walk_forward_folds(meta,min_train_dates=2)
        self.assertEqual(len(folds),3)
        for fold in folds:
            self.assertTrue(all(e._utc(r["official_available_at"])<
                                e._utc(fold["origin"]) for r in fold["train"]))

    def test_fold_fails_2023_24(self):
        meta=[{k:r[k] for k in ("game_id","player_id","stat","frozen_at",
                "event_start_at","official_available_at","date")} for r in self.rows]
        meta.append({**meta[0],"date":"2023-10-23T00:00:00Z",
                     "event_start_at":"2023-10-23T23:00:00Z",
                     "frozen_at":"2023-10-23T17:00:00Z",
                     "official_available_at":"2023-10-24T00:00:00Z"})
        with self.assertRaisesRegex(e.ExperimentError,"HOLDOUT"):
            e.make_walk_forward_folds(meta,min_train_dates=2)


class TestImmutableStore(unittest.TestCase):
    def test_write_once_and_collision(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"freeze"
            self.assertTrue(_write_once(path,b"frozen"))
            self.assertFalse(_write_once(path,b"frozen"))
            with self.assertRaises(WarehouseError):
                _write_once(path,b"tampered")
            self.assertEqual(path.read_bytes(),b"frozen")


if __name__=="__main__":
    unittest.main()
