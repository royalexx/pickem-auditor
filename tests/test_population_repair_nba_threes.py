"""No-network NBA historical 3PT source correction and non-regressive replay."""
import sys
import json
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_history as history
import population_backfill as backfill
import population_normalizers as norm
import population_repair_nba_threes as repair
from test_population_multisport import nba_box


class HistoricalThreePointRepair(unittest.TestCase):
    def test_exact_date_replay_only_inserts_missing_threes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            completed=backfill.read_state(root,"NBA")
            completed["cursor"]="2018-10-18"
            completed["dates_complete"]=17
            backfill.save_state(root,"NBA",completed)
            original=norm.nba_game(nba_box(),"2018-10-17","401")
            # Emulate a prior historical archive where direct ESPN 3PM was
            # missing but all other player-game statistics are immutable.
            history.persist(root,[r for r in original if r["stat"]!="threes"])
            previous=history.read(root,sport="NBA",stat="points",before="2018-10-18")
            def fetch(url):
                if "/scoreboard?" in url:
                    day=url.split("dates=")[1][:8]
                    if day=="20181017":
                        return {"events":[{"id":"401","season":{"type":2},
                                           "status":{"type":{"completed":True}}}]}
                    return {"events":[]}
                if "/summary?" in url:return nba_box()
                raise ValueError("unsupported_test_url")
            result=repair.run(root,max_days=30,fetcher=fetch)
            self.assertEqual(result["status"],"caught_up")
            self.assertEqual(result["new_threes_records"],16)
            self.assertEqual(result["games_verified"],1)
            self.assertEqual(backfill.read_state(root,"NBA")["cursor"],"2018-10-18")
            self.assertEqual(history.read(root,sport="NBA",stat="points",
                                          before="2018-10-18"),previous)
            threes=history.read(root,sport="NBA",stat="threes",before="2018-10-18")
            self.assertEqual(len(threes),16)
            self.assertEqual({r["value"] for r in threes},{3})
            second=repair.run(root,max_days=30,fetcher=lambda url:
                              (_ for _ in ()).throw(RuntimeError("unexpected refetch")))
            self.assertEqual(second["status"],"caught_up")
            self.assertEqual(second["new_threes_records"],0)

    def test_missing_original_progress_not_mistaken_for_replay_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            r=repair.run(root,max_days=10,fetcher=lambda url:
                         (_ for _ in ()).throw(RuntimeError("forbidden incomplete period")))
            self.assertEqual(r["new_threes_records"],0)
            self.assertEqual(r["status"],"caught_up")
            self.assertEqual(r["cursor_after"],"2018-10-01")


if __name__=="__main__":
    unittest.main()
