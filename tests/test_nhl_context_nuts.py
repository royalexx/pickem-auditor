"""Opt-in real NUTS smoke; synthetic data, never a predictive validation claim."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from nhl_context_fixture import games
import nhl_context_features as features
import nhl_context_model as model


@unittest.skipUnless(os.environ.get("RUN_CONTEXT_NUTS")=="1","opt-in isolated NUTS smoke")
class ContextNuts(unittest.TestCase):
    def test_all_market_graphs_and_saves_posterior_roundtrip(self):
        bundles=games(30)
        for market in features.MARKETS:
            rows,_=features.examples(bundles,market=market)
            design=features.prepare(rows,cutoff="2024-01-01T00:00:00Z",min_rows=20)
            graph=model.build(design)
            self.assertIn("player_chol",graph.named_vars)
            self.assertIn("team_effect",graph.named_vars)
            self.assertNotIn("season_sd",graph.named_vars)
            multi={**design,"seasons":["2022","2023"],
                   "season_idx":[i%2 for i in range(design["rows"])]}
            self.assertIn("season_sd",model.build(multi).named_vars)
            if market!="saves":continue
            trace=model.fit(design,draws=25,tune=25,chains=2,cores=1,progressbar=False)
            diag=model.diagnostics(trace)
            self.assertFalse(diag["posterior_sampling_ok"])
            self.assertNotEqual(diag["status"],"diagnostics_unavailable",diag)
            row=rows[-1].copy()
            row.update(start_time="2024-01-02T23:00:00Z",season="2023")
            f=rows[-1]["features"].copy();f["computed_before"]=row["start_time"]
            # Deliberate test-only diagnostic override verifies the interface;
            # real CLI evaluation always recomputes strict convergence checks.
            options=dict(matchup=row,player_id=row["player_id"],features=f,line=25.,draws=250,
                         diagnostic={"posterior_sampling_ok":True},observed_value=26)
            pred=model.forecast(trace,design,**options)
            self.assertAlmostEqual(sum(pred[k] for k in ("q_over","q_under","q_push")),1.,places=10)
            self.assertFalse(pred["ranking_allowed"])
            self.assertGreater(pred["q_push"],0)
            self.assertLessEqual(pred["expected_minutes"],65)
            self.assertLessEqual(pred["expected_value"],pred["expected_shots_faced"])
            self.assertIsNotNone(pred["log_predictive_density"])
            with tempfile.TemporaryDirectory() as folder:
                import arviz as az
                trace.to_netcdf(Path(folder)/"posterior.nc")
                restored=az.from_netcdf(Path(folder)/"posterior.nc")
                self.assertEqual(pred,model.forecast(restored,design,**options))
            with self.assertRaisesRegex(ValueError,"not_converged"):
                model.forecast(trace,design,**{**options,"diagnostic":diag})
            wrong=f.copy();wrong["identity"]={**f["identity"],"team":"ZZZ"}
            with self.assertRaisesRegex(ValueError,"feature_identity"):
                model.forecast(trace,design,**{**options,"features":wrong})


if __name__=="__main__":unittest.main()
