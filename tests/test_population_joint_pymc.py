"""Real multi-sport count and signed-yard NUTS graph smoke (isolated CI)."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_history as wh
import joint_population_bayes as model
import joint_population_holdout as score


class BayesianPopulationNuts(unittest.TestCase):
    def test_count_and_continuous_signed_outcome_real_mcmc(self):
        if importlib.util.find_spec("pymc") is None:
            self.skipTest("isolated CI installs PyMC")
        import pymc as pm
        for sport,stat in (("NBA","points"),("NFL","receiving yards")):
            with self.subTest(sport=sport,stat=stat):
                rows=[]
                for game in range(3):
                    for athlete in range(16):
                        rows.append(wh.make(
                            sport=sport,stat=stat,
                            game_id=str(9000+game),
                            game_date=f"{2022 if game==0 else 2023}-10-0{game+1}",
                            season=str(2022 if game==0 else 2023),player_id=str(1000+athlete),
                            position="G" if sport=="NBA" else "WR",
                            team="A" if athlete<8 else "B",
                            opponent="B" if athlete<8 else "A",home=athlete>=8,
                            value=((athlete+game)%30 if sport=="NBA" else
                                   -5.+(athlete+game)*4),
                            workload=float(22+(athlete%8)*2),
                            workload_unit="minutes" if sport=="NBA" else "snaps",
                            source_url="https://example.org/source",
                            source_sha256="c"*64))
                data=model.prepare(rows,min_rows=40)
                graph=model.build(data)
                self.assertIn("player_chol_corr",graph.named_vars)
                self.assertIn("observed_volume",graph.named_vars)
                with graph:
                    idata=pm.sample(draws=25,tune=25,chains=2,cores=1,
                          progressbar=False,random_seed=1337,
                          nuts={"target_accept":.90},
                          compute_convergence_checks=False)
                diag=model.diagnostics(idata)
                self.assertFalse(diag["posterior_sampling_ok"])
                self.assertIn(diag["status"],("diagnostics_unavailable","sampling_diagnostics_failed"))
                self.assertFalse(diag["publication_eligible"])
                # Smoke bypass of short-chain *quality criteria* only to
                # exercise code paths, never the production publication gate.
                diagnostic={"posterior_sampling_ok":True}
                p=model.forecast(idata,data,player_id="1000",opponent="B",
                    season="2023",home=False,line=15.5 if sport=="NBA" else 30.5,
                    seed=1234,draws=150,diagnostic=diagnostic)
                self.assertGreaterEqual(p["q_over"],0)
                self.assertLessEqual(p["q_over"],1)
                self.assertAlmostEqual(p["q_over"]+p["q_under"]+p["q_push"],1,places=8)
                self.assertFalse(p["publication_eligible"])
                self.assertFalse(p["ranking_allowed"])
                q=model.forecast(idata,data,player_id="1000",opponent="B",
                    season="2023",home=False,line=15.5 if sport=="NBA" else 30.5,
                    seed=1234,draws=150,diagnostic=diagnostic,
                    cache=model.posterior_cache(idata))
                self.assertEqual(p,q)
                # Previously unseen season is allowed only after the model has
                # learned season-level dispersion from multiple prior seasons.
                next_season=model.forecast(idata,data,player_id="1000",
                    opponent="B",season="2024",home=False,
                    line=15.5 if sport=="NBA" else 30.5,seed=456,
                    draws=150,diagnostic=diagnostic,cache=model.posterior_cache(idata))
                self.assertGreaterEqual(next_season["q_over"],0)
                self.assertLessEqual(next_season["q_over"],1)
                self.assertFalse(next_season["publication_eligible"])
                base=score.simple_control(rows,player="1000",
                    position="G" if sport=="NBA" else "WR",
                    stat_family=data["family"],line=15.5 if sport=="NBA" else 30.5)
                self.assertGreaterEqual(base,0)
                self.assertLessEqual(base,1)


if __name__=="__main__":
    unittest.main()
