"""Real PyMC model-graph and two-chain NUTS smoke test (offline, synthetic)."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import joint_nhl_bayes as mod
import historical_nhl_warehouse as wh


class JointSamplingSmoke(unittest.TestCase):
    def test_joint_model_builds_and_samples_multiple_chains(self):
        if importlib.util.find_spec('pymc') is None:
            self.skipTest('PyMC installed only in the dedicated NUTS CI job')
        import pymc as pm
        rows=[]
        for game in range(3):
            for player in range(16):
                rows.append({
                    "version":wh.VERSION,"sport":"NHL","stat":"shots on goal",
                    "game_id":str(2018020001+game),
                    "game_date":f"2018-10-0{game+1}","season":"2018",
                    "player_id":str(2000+player),
                    "position":"F" if player<10 else "D",
                    "team":"BOS" if player<8 else "NYR",
                    "opponent":"NYR" if player<8 else "BOS",
                    "home":player>=8,
                    "shots":(player+game)%5,"toi_minutes":12.5+(player%6),
                    "source_url":f"https://api-web.nhle.com/v1/gamecenter/{2018020001+game}/boxscore",
                    "source_sha256":"f"*64
                })
        data=mod.prepare(rows,min_rows=20)
        model=mod.build(data)
        self.assertIn("player_chol",model.named_vars)
        self.assertIn("observed_shots",model.named_vars)
        with model:
            idata=pm.sample(draws=25,tune=25,chains=2,cores=1,
                            random_seed=847,progressbar=False,
                            nuts={"target_accept":.9},
                            compute_convergence_checks=False)
        self.assertEqual(int(idata.posterior.sizes["chain"]),2)
        self.assertIn("player_effect",idata.posterior)
        self.assertIn("overdispersion",idata.posterior)
        self.assertIn("player_chol_corr",idata.posterior)
        diagnostic=mod.diagnostics(idata)
        self.assertFalse(diagnostic["publication_eligible"])
        self.assertFalse(diagnostic["validated"])
        self.assertNotEqual(diagnostic["status"],"diagnostics_unavailable")
        # Smoke bypasses the *quality threshold* for interface testing only.
        # Actual training and ranking never bypass the diagnostics gate.
        predicted=mod.forecast(idata,data,player_id="2000",opponent="NYR",
            season="2018",home=False,line=2.5,draws=250,
            fit_diagnostics={"posterior_sampling_ok":True})
        self.assertAlmostEqual(predicted["q_over"]+predicted["q_under"]+
                               predicted["q_push"],1,places=9)
        self.assertFalse(predicted["publication_eligible"])
        self.assertFalse(predicted["ranking_allowed"])



if __name__=="__main__":
    unittest.main()
