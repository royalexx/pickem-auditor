"""Integration checks: post-shadow consensus and full-universe rankings."""
import json
from datetime import datetime,timezone
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from slate_model_report import build as report_build
from probability_blend import production_policy
from slate_candidate_ranking import full_universe_review


def sidecar(p, when="2026-11-08T13:00:00+00:00", *, nuts=False):
    result={"status":"forecast","q_win":p,"q_push":0,
            "generated_at":when}
    if nuts: result["sampler_diagnostics"]={"max_rhat":1.006,"min_bulk_ess":500}
    return result


class PostShadowIntegrationTests(unittest.TestCase):
    def row(self):
        return {
            "game_date":"2026-11-08","run_id":"N8","forecast_at":"2026-11-08T12:30:00+00:00",
            "event_start":"2026-11-08T18:00:00+00:00","sport":"NFL",
            "player":"Test QB","player_id":"nfl-001","team":"DAL",
            "opponent":"IND","stat":"pass attempts","side":"over","reference_line":32.5,
            "engine_a":{"q_win_robust":.60,"q_push_robust":0,"reliable":True,
                        "observation_ids_verified":True},
            "engine_b":{"q_win":.50,"q_push":0,"reliable":True,
                        "abstain":False,"baseline_origin":"collector_observations"},
            "blend":{"production_policy":True,"available":True,
                     "preliminary":True,"version":"new-60-40"},
            "q_model":None,"q_push":None,
            "inputs":{"def_matchup_factor":1.03,"pace_ratio":1.06},
        }

    def test_policy_60_40_as_matched_sidecars(self):
        from nuts_slate_shadow import identity
        r=self.row();k=identity(r)
        indexes={"Bayesian_A":{k:sidecar(.70)},
                 "Bayesian_B":{k:sidecar(.80)},
                 "NUTS_population":{k:sidecar(.90,nuts=True)}}
        result=report_build(r,indexes,[],policy=production_policy(ROOT))
        expected=.6*(.6+.7+.8+.9)/4+.4*.5
        self.assertAlmostEqual(result["Consensus"],expected)
        self.assertEqual(result["production_ensemble"]["historical_families"],
                         ["Engine_A","Bayesian_A","Bayesian_B","NUTS"])
        self.assertTrue(result["production_consensus_available"])
        self.assertTrue(result["models"]["Consensus"]["finalized_post_shadow"])
        self.assertNotEqual(result["Consensus"],.6*.6+.4*.5)
        self.assertIsNone(result["Market"])

    def test_poststart_bayesian_removed_not_used_as_future_information(self):
        from nuts_slate_shadow import identity
        r=self.row();k=identity(r)
        indexes={"Bayesian_A":{k:sidecar(.99,when="2026-11-08T19:00:00+00:00")},
                 "Bayesian_B":{k:sidecar(.70)}}
        result=report_build(r,indexes,[],policy=production_policy(ROOT))
        self.assertIsNone(result["Bayesian_A"])
        self.assertEqual(result["production_ensemble"]["historical_families"],
                         ["Engine_A","Bayesian_B"])

    def test_full_universe_review_marks_unsupported_opponent(self):
        row=self.row();row.update(reason="POST_SHADOW_PRODUCTION_PENDING")
        comp={"Consensus":.60,"Engine_A":.60,"Engine_B":.50,"Bayesian_A":.70,
              "Bayesian_B":.80,"Market":.50,"NUTS":None}
        with tempfile.TemporaryDirectory() as root:
            evidence=full_universe_review(row,comp,data_root=root)
        self.assertEqual(evidence["opponent_tendency"]["source_fields"],
                         {"def_matchup_factor":1.03})
        self.assertEqual(evidence["player_tendency"]["status"],"unavailable")
        self.assertEqual(evidence["weather"],
                         "venue_aware_weather_verification_required")
        self.assertEqual(evidence["game_date"],"2026-11-08")


if __name__=="__main__":
    unittest.main()
