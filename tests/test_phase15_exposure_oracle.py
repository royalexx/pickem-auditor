"""Phase1.5 Gate C one-factor, postgame-only verified exposure oracle tests."""
from __future__ import annotations
import hashlib,json,math,tempfile
from pathlib import Path
import unittest

from v2.phase15_exposure_oracle import evaluate_workload_oracle
from v2.official_nba_nhl_capture import SettlementCaptureError
from tests.test_v25_official_capture import nhl_final


def fixture(root):
    original=nhl_final()
    raw=json.dumps(original,sort_keys=True).encode()
    (root/"nhl.json").write_bytes(raw)
    actual_toi=21+31/60
    row={
      "schema":"v25-phase1-nhl-nba-certified-replay-v1",
      "model_promotion_authorized":False,
      "contracts":[{
          "sport":"NHL","event_id":"orig-1","player_id":"8480069",
          "stat":"shots on goal","line":1.5,"team_id":"COL","opponent_id":"TOR",
          "outcome":{"status":"over","actual":3},
          "opportunity":{"projected_workload":20},
          "models":{
              "naive_recent_exposure_rate":{"status":"counterfactual_shadow",
                   "distribution":{"rate":2.0},
                   "p_over_nonpush":1-math.exp(-2)*3},
              "pooled_peer_shrunk_rate":{"status":"counterfactual_shadow",
                   "distribution":{"rate":2.5},
                   "p_over_nonpush":1-math.exp(-2.5)*3.5}
          }
      }]
    }
    settled=[{
        "sport":"NHL","event_id":"orig-1","player_id":"8480069","stat":"shots on goal",
        "actual":3,"observed_workload_minutes":actual_toi,
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "source_archive_path":"nhl.json"
    }]
    return row,settled


class WorkloadOracleTests(unittest.TestCase):
    def test_exact_final_source_and_exposure_compared_without_pregame_backfill(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            p,s=fixture(root)
            output=evaluate_workload_oracle(p,s,root)
            self.assertEqual(output["source_verified_scored_contracts"],1)
            self.assertAlmostEqual(output["model_oracles"][
                "naive_recent_exposure_rate"]["mean_postgame_oracle_count"],2*(21+31/60)/20)
            self.assertFalse(output["oracle_releasable_as_model"])
            self.assertEqual(output["four_factor_attribution_status"],
                             "BLOCKED_MISSING_GENUINE_PREGAME_FACTOR_FORECASTS")

    def test_source_sha_change_rejects_postgame_oracle(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,s=fixture(root)
            s[0]["source_sha256"]="0"*64
            with self.assertRaisesRegex(SettlementCaptureError,"tampered"):
                evaluate_workload_oracle(p,s,root)

    def test_changed_actual_sog_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,s=fixture(root);s[0]["actual"]=4
            with self.assertRaisesRegex(SettlementCaptureError,"actual_inconsistent"):
                evaluate_workload_oracle(p,s,root)

    def test_missing_settlement_cannot_create_oracle_forecasts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,s=fixture(root)
            with self.assertRaisesRegex(SettlementCaptureError,"cannot_drop_scored_contracts"):
                evaluate_workload_oracle(p,[],root)

    def test_no_original_observed_outcome_stays_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,s=fixture(root)
            p["contracts"][0]["outcome"]={"status":"pending_official_settlement"}
            result=evaluate_workload_oracle(p,[],root)
            self.assertEqual(result["status"],"BLOCKED_NO_SETTLED_OPPORTUNITY")


if __name__=="__main__":unittest.main()
