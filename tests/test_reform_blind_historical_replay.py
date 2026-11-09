"""Blind historical replay separation tests. No paid odds or network."""
from pathlib import Path
from datetime import timedelta
import copy
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tests"))
import reform_blind_historical_replay as blind
from test_nfl_tackle_snap_share import fixture,game_time


def enough_training():
    bundles=fixture(n=19)
    players=bundles[0]["players"]
    original=[r for r in players if r["player_id"]=="p1"]
    for k in range(12):
        for r in original:
            clone=copy.deepcopy(r)
            clone["player_id"]="additional_"+str(k)
            clone["value"]=4+(k%3)
            clone["workload"]=40+k
            players.append(clone)
    return bundles


class BlindHistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.packets=self.dir/"packets"
        self.vault=self.dir/"restricted_outcomes.json"
        self.forecasts=self.dir/"frozen_forecasts.json"
        self.result=self.dir/"settlement_report.json"

    def test_end_to_end_separation_forecast_lock_before_settlement(self):
        prepared=blind.prepare(enough_training(),
            from_day=game_time(14).date().isoformat(),
            through_day=(game_time(19)+timedelta(days=1)).date().isoformat(),
            packet_dir=self.packets,vault_file=self.vault)
        self.assertGreater(prepared["slate_days"],0)
        self.assertTrue(self.vault.exists())
        self.assertGreater(prepared["packets"][0]["candidates"],0)
        packet=json.loads((self.packets/prepared["packets"][0]["filename"]).read_text())
        self.assertFalse(packet["target_outcomes_in_packet"])
        target_games={x["game_id"] for x in packet["fixtures"]}
        self.assertFalse(target_games & {x["game_id"] for x in packet["history"]["rows"]})
        for c in packet["candidates"]:
            self.assertFalse(blind.FORBIDDEN_TARGET_KEYS & set(c))
        frozen=blind.forecast(self.packets,self.forecasts)
        self.assertGreater(frozen["forecast_count"],0)
        self.assertFalse(frozen["target_outcomes_read"])
        self.assertTrue(Path(str(self.forecasts)+".locked.sha256.json").exists())
        report=blind.settle(self.forecasts,self.vault,self.result)
        self.assertGreater(report["scored"],0)
        self.assertTrue(report["strict_no_target_results_passed_to_forecaster"])
        self.assertFalse(report["real_bookmaker_line_validation"])
        self.assertFalse(report["production_eligible"])

    def test_forecast_cannot_accept_tampered_future_outcome_packet(self):
        prepared=blind.prepare(enough_training(),
            from_day=game_time(14).date().isoformat(),
            through_day=(game_time(19)+timedelta(days=1)).date().isoformat(),
            packet_dir=self.packets,vault_file=self.vault)
        path=self.packets/prepared["packets"][0]["filename"]
        body=json.loads(path.read_text())
        body["candidates"][0]["actual"]=10
        path.write_text(json.dumps(body))
        with self.assertRaisesRegex(blind.BlindReplayError,
                                    "modified_pregame_packet"):
            blind.forecast(self.packets,self.forecasts)

    def test_result_tampering_after_sha_lock_cannot_settle(self):
        blind.prepare(enough_training(),
            from_day=game_time(14).date().isoformat(),
            through_day=(game_time(19)+timedelta(days=1)).date().isoformat(),
            packet_dir=self.packets,vault_file=self.vault)
        blind.forecast(self.packets,self.forecasts)
        data=json.loads(self.forecasts.read_text())
        data["predictions"][0]["p_over_challenger"]=.99
        self.forecasts.write_text(json.dumps(data))
        with self.assertRaisesRegex(blind.BlindReplayError,
                                    "forecast_modified_after_lock"):
            blind.settle(self.forecasts,self.vault,self.result)

    def test_vault_tampering_after_prepare_fails(self):
        blind.prepare(enough_training(),
            from_day=game_time(14).date().isoformat(),
            through_day=(game_time(19)+timedelta(days=1)).date().isoformat(),
            packet_dir=self.packets,vault_file=self.vault)
        blind.forecast(self.packets,self.forecasts)
        changed=json.loads(self.vault.read_text())
        changed["labels"][0]["actual"]+=100
        self.vault.write_text(json.dumps(changed))
        with self.assertRaisesRegex(blind.BlindReplayError,
                                    "outcome_vault_changed"):
            blind.settle(self.forecasts,self.vault,self.result)

    def test_same_result_receipt_is_immutable(self):
        first={"schema":"test","score":.45}
        path=self.dir/"immutable.json"
        one=blind.write_once(path,first)
        self.assertEqual(one,blind.write_once(path,first))
        with self.assertRaisesRegex(blind.BlindReplayError,
                                    "would_rewrite_immutable_replay_artifact"):
            blind.write_once(path,{"schema":"test","score":.99})


if __name__=="__main__":
    unittest.main()
