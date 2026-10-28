"""Real PyMC model-graph and two-chain NUTS smoke test (offline, synthetic)."""
import importlib.util
import sys
import tempfile
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
        self.assertNotIn("season_toi_sd",model.named_vars)
        later=[{**row,"season":"2019",
                "game_id":str(2019020001+i//16),
                "game_date":f"2019-10-0{1+i//16}"}
               for i,row in enumerate(rows)]
        two_season=mod.build(mod.prepare(rows+later,min_rows=20))
        self.assertIn("season_toi_sd",two_season.named_vars)
        self.assertIn("season_rate_sd",two_season.named_vars)
        with model:
            idata=pm.sample(draws=25,tune=25,chains=2,cores=1,
                            random_seed=847,progressbar=False,
                            nuts={"target_accept":.9},
                            compute_convergence_checks=False)
        self.assertEqual(int(idata.posterior.sizes["chain"]),2)
        self.assertIn("player_effect",idata.posterior)
        self.assertIn("overdispersion",idata.posterior)
        self.assertIn("player_chol_corr",idata.posterior)
        self.assertNotIn("season_toi_sd",idata.posterior)
        self.assertNotIn("season_rate_sd",idata.posterior)
        self.assertIn("season_toi",idata.posterior)
        diagnostic=mod.diagnostics(idata)
        self.assertFalse(diagnostic["publication_eligible"])
        self.assertFalse(diagnostic["validated"])
        self.assertNotEqual(diagnostic["status"],"diagnostics_unavailable",diagnostic)
        import joint_nhl_posterior_audit as geometry
        checked=geometry.evaluate_posterior(idata,{
            "version":mod.VERSION,"publication_eligible":False,
            "source_digest":data["source_digest"],
            "training_cutoff_exclusive":"2018-10-04",
            "diagnostics":{"posterior_sampling_ok":True}})
        self.assertFalse(checked["publication_eligible"])
        self.assertIn("posterior_correlation_mean",checked)
        self.assertIn("minimum_bfmi",checked)
        self.assertGreaterEqual(checked["minimum_bfmi"],0)
        # Smoke bypasses the *quality threshold* for interface testing only.
        # Actual training and ranking never bypass the diagnostics gate.
        predicted=mod.forecast(idata,data,player_id="2000",opponent="NYR",
            season="2018",home=False,line=2.5,draws=250,
            fit_diagnostics={"posterior_sampling_ok":True})
        self.assertAlmostEqual(predicted["q_over"]+predicted["q_under"]+
                               predicted["q_push"],1,places=9)
        self.assertFalse(predicted["publication_eligible"])
        self.assertFalse(predicted["ranking_allowed"])
        with self.assertRaisesRegex(ValueError,"unseen_season_without_identified_multiseason_prior"):
            mod.forecast(idata,data,player_id="2000",opponent="NYR",
                season="2019",home=False,line=2.5,draws=250,
                fit_diagnostics={"posterior_sampling_ok":True})
        fast=mod.forecast(idata,data,player_id="2000",opponent="NYR",
            season="2018",home=False,line=2.5,draws=250,
            fit_diagnostics={"posterior_sampling_ok":True},
            posterior_cache=mod.predictive_cache(idata))
        self.assertEqual(predicted,fast)
        self.assertEqual(predicted["predictive_method"],
                         "latent_posterior_mc_conditional_nb_integrated")
        self.assertIsNotNone(predicted["mc_standard_error_q_over"])
        # Posterior artifacts must really survive a file roundtrip before
        # they are downloadable and used for the later heldout evaluation.
        import arviz as az
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/"posterior.nc"
            idata.to_netcdf(archive)
            restored=az.from_netcdf(archive)
            replay=mod.forecast(restored,data,player_id="2000",
                opponent="NYR",season="2018",home=False,line=2.5,draws=250,
                fit_diagnostics={"posterior_sampling_ok":True})
            self.assertEqual(predicted,replay)




if __name__=="__main__":
    unittest.main()
