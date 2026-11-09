"""Adversarial tests for NFL 2024 ALL-market week-level result seal."""
from datetime import date,timedelta
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_weekly_blind_multimarket as w


def row(yr,week,player,stat,value,position,team="BUF"):
    day=f"{yr}-09-0{week}" if week<10 else f"{yr}-10-01"
    return {"game_id":f"{yr}_{week}_BAL_BUF","gameday":day,
            "season":yr,"week":week,"team":team,
            "opponent":"BAL","position":position,"player_id":player,
            "stat":stat,"value":float(value),
            "historical_snap_exposure":52.}


def fixture(yr,week):
    day=f"{yr}-09-0{week}" if week<10 else f"{yr}-10-01"
    return {"game_id":f"{yr}_{week}_BAL_BUF",
            "gameday":day,"away_team":"BAL","home_team":"BUF",
            "week":week,"season":yr}


class WeeklyAllMarketTests(unittest.TestCase):
    def test_exact_supported_nfl_markets_no_qb_or_defense_omission(self):
        self.assertEqual(len(w.MARKETS),16)
        self.assertEqual(len(set(w.MARKETS)),16)
        self.assertEqual(set(w.MARKETS),
            set(w.COUNT["NFL"])|set(w.CONTINUOUS["NFL"]))
        for name in ("tackles + assists","tackle assists","solo tackles",
                     "qb hits","passes defended","targets",
                     "pass attempts","completions","passing yards",
                     "passing touchdowns","rushing yards","receiving yards"):
            self.assertIn(name,w.MARKETS)

    def test_future_result_cannot_enter_prior_week_feature(self):
        s=w.make_state()
        w.update_week(s,[row(2023,1,"qb","pass attempts",29,"QB")],[fixture(2023,1)])
        with self.assertRaisesRegex(w.WeeklyReplayError,
                                    "future_game_used_in_player_features"):
            w.features(s,market="pass attempts",player_id="qb",
                       team="BUF",position="QB",game_day="2023-09-01",
                       home=True)

    def test_week_packet_includes_all_markets_and_no_results(self):
        s=w.make_state()
        rows=[row(2023,1,"qb",name,21 if name in ("pass attempts","completions")
                  else 150 if name=="passing yards" else 1,"QB")
              for name in w.MARKETS if w.eligible(name,"QB")]
        rows+= [row(2023,1,"lb",name,5,"LB") for name in w.MARKETS
                if w.eligible(name,"LB")]
        rows+= [row(2023,1,"wr",name,4,"WR") for name in w.MARKETS
                if w.eligible(name,"WR")]
        w.update_week(s,rows,[fixture(2023,1)])
        weekf=fixture(2024,1)
        weekf["gameday"]="2024-09-05"
        p=w.prepare_packet(s,[weekf],1)
        self.assertEqual(p["expected_markets"],16)
        self.assertEqual(list(p["market_packets"]),list(w.MARKETS))
        self.assertIs(p["target_week_results_in_packet"],False)
        self.assertGreater(p["market_packets"]["pass attempts"]["candidates"].__len__(),0)
        self.assertGreater(p["market_packets"]["tackles + assists"]["candidates"].__len__(),0)
        self.assertNotIn('"2024-09-05"',json.dumps(p["market_packets"].get("pass attempts",{}).get("xtx",{})))
        # Current-slate outcomes are not present in any market candidate.
        for market in w.MARKETS:
            for item in p["market_packets"][market]["candidates"]:
                self.assertFalse(set(item)&{"value","actual","hit","result",
                                             "historical_snap_exposure"})

    def test_forecast_refuses_incomplete_registry_even_if_15_markets_fine(self):
        with tempfile.TemporaryDirectory() as d:
            s=w.make_state()
            packet=w.prepare_packet(s,[fixture(2024,1)],1)
            packet["market_packets"].pop("passes defended")
            src=Path(d)/"packet.json"
            src.write_bytes(w.canonical(packet))
            with self.assertRaisesRegex(w.WeeklyReplayError,
                                        "not_all_markets_in_packet"):
                w.forecast(src,Path(d)/"forecast.json")

    def test_market_training_uses_prior_observed_examples_and_changes_weights(self):
        s=w.make_state()
        prior_rows=[]
        fixtures=[]
        # Strict week updates, not a mixture of current-week outcomes.
        for week in range(1,7):
            f=fixture(2023,week)
            fixtures.append(f)
            rows=[]
            for j in range(16):
                rows.append(row(2023,week,f"Q{j}","pass attempts",25+j%7,"QB"))
                rows.append(row(2023,week,f"L{j}","tackles + assists",2+j%5,"LB"))
            w.update_week(s,rows,[f])
        self.assertGreater(s["trained_n"]["pass attempts"],80)
        p=w.prepare_packet(s,[{**fixture(2024,1),"gameday":"2024-09-05"}],1)
        self.assertEqual(p["market_packets"]["pass attempts"]["trained_n"],96)
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"packet.json";b=Path(d)/"forecast.json"
            w.write_new(a,p)
            result=w.forecast(a,b)
            self.assertEqual(result["markets"],16)
            frozen=json.loads(b.read_text())
            self.assertEqual(list(frozen["market_results"]),list(w.MARKETS))
            self.assertEqual(frozen["market_results"]["pass attempts"]["status"],
                            "trained_machine_learning_ridge")
            self.assertTrue(frozen["market_results"]["pass attempts"]["model_coefficients_sha256"])
            self.assertEqual(frozen["market_results"]["tackles + assists"]["status"],
                            "trained_machine_learning_ridge")
            self.assertGreater(frozen["market_results"]["pass attempts"]["pregame_candidates"],0)
            self.assertTrue(all(0<=v["p_over_model"]<=1
                     for v in frozen["market_results"]["pass attempts"]["predictions"]))

    def test_no_week_result_revealed_before_complete_model_lock(self):
        with tempfile.TemporaryDirectory() as d:
            s=w.make_state()
            f=fixture(2024,1)
            packet=w.prepare_packet(s,[f],1)
            a=Path(d)/"packet.json"
            b=Path(d)/"frozen.json"
            w.write_new(a,packet)
            w.forecast(a,b)
            frozen=json.loads(b.read_text())
            frozen["market_results"].pop("tackles + assists")
            b.write_text(json.dumps(frozen))
            with self.assertRaisesRegex(w.WeeklyReplayError,
                                        "unfrozen_or_incomplete_markets"):
                w.settlement(b,a,b"encrypted",b"does_not_matter",[])

    def test_current_week_result_features_all_computed_before_updates(self):
        s=w.make_state()
        same_week=[
            row(2023,1,"Q1","pass attempts",50,"QB"),
            row(2023,1,"Q2","pass attempts",5,"QB"),
        ]
        w.update_week(s,same_week,[fixture(2023,1)])
        # At first week, the second player must NOT see QB 1's current
        # outcome as position prior.
        first=w.make_state()
        w.update_week(first,list(reversed(same_week)),[fixture(2023,1)])
        self.assertEqual(first["xty"]["pass attempts"],s["xty"]["pass attempts"])
        self.assertEqual(first["xtx"]["pass attempts"],s["xtx"]["pass attempts"])

    def test_training_counts_increment_only_after_settlement_update(self):
        s=w.make_state()
        w.update_week(s,[row(2023,1,"qb","pass attempts",27,"QB")],
                      [fixture(2023,1)])
        count=s["trained_n"]["pass attempts"]
        frozen=w.prepare_packet(s,[{**fixture(2024,1),
                                    "gameday":"2024-09-05"}],1)
        self.assertEqual(frozen["market_packets"]["pass attempts"]["trained_n"],count)
        self.assertEqual(s["trained_n"]["pass attempts"],count)
        # Only explicit outcome reveal + update can change count.
        w.update_week(s,[{**row(2024,1,"qb","pass attempts",32,"QB"),
                          "gameday":"2024-09-05"}],
                      [{**fixture(2024,1),"gameday":"2024-09-05"}])
        self.assertEqual(s["trained_n"]["pass attempts"],count+1)


if __name__=="__main__":
    unittest.main()
