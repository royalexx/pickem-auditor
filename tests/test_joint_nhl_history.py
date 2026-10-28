"""Historical NHL source integrity and Bayesian design contracts (network-free)."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import historical_nhl_warehouse as wh
import nhl_bayesian_backfill as backfill
import joint_nhl_bayes as bayes


def raw_game(gid=2018020001, *, state="FINAL"):
    def player(num, i):
        return {"playerId":num,"sog":i%5,"toi":"17:30" if i%2 else "12:20"}
    return {"id":gid,"gameState":state,"awayTeam":{"abbrev":"BOS"},
            "homeTeam":{"abbrev":"NYR"},"playerByGameStats":{
              "awayTeam":{"forwards":[player(1000+i,i) for i in range(5)],
                          "defense":[player(1010+i,i) for i in range(3)]},
              "homeTeam":{"forwards":[player(2000+i,i) for i in range(5)],
                          "defense":[player(2010+i,i) for i in range(3)]}}}


class SourceWarehouse(unittest.TestCase):
    def test_parse_and_duplicate_fails_closed(self):
        rows=wh.canonical_game(raw_game(),"2018-10-01")
        self.assertEqual(len(rows),16)
        self.assertEqual(rows[0]["shots"],0)
        self.assertEqual(rows[0]["toi_minutes"],12+20/60)
        self.assertEqual(len({r["player_id"] for r in rows}),16)
        self.assertEqual(len({r["source_sha256"] for r in rows}),1)
        bad=raw_game()
        bad["playerByGameStats"]["awayTeam"]["forwards"][0]["sog"]=-2
        with self.assertRaisesRegex(ValueError,"invalid_player_shots"):
            wh.canonical_game(bad,"2018-10-01")
        bad=raw_game()
        bad["playerByGameStats"]["awayTeam"]["forwards"][0]["playerId"]=1001
        with self.assertRaisesRegex(ValueError,"duplicate_player_game"):
            wh.canonical_game(bad,"2018-10-01")
        with self.assertRaisesRegex(ValueError,"game_not_final"):
            wh.canonical_game(raw_game(state="LIVE"),"2018-10-01")
        with self.assertRaisesRegex(ValueError,"nhl_season_date_mismatch"):
            wh.canonical_game(raw_game(),"2026-10-01")

    def test_deterministic_gzip_immutable_records_and_cutoff(self):
        rows=wh.canonical_game(raw_game(),"2018-10-01")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertTrue(wh.add_game(root,rows))
            p=wh.shard_path(root,"2018-10-01")
            previous=p.read_bytes()
            self.assertFalse(wh.add_game(root,rows))
            self.assertEqual(p.read_bytes(),previous)
            changed=copy.deepcopy(rows)
            changed[0]["shots"]+=1
            with self.assertRaisesRegex(ValueError,"historical_source_revision_requires_review"):
                wh.add_game(root,changed)
            self.assertEqual(len(wh.read_history(root,before="2018-10-02")),16)
            self.assertEqual(len(wh.read_history(root,before="2018-10-01")),0)
            self.assertEqual(len(wh.read_history(root,before="2018-10-09",max_seasons=1)),16)
            self.assertEqual(p.read_bytes(),previous)
            prep=bayes.prepare(rows,min_rows=8)
            self.assertEqual(prep["rows"],16)
            self.assertEqual(len(prep["players"]),16)
            self.assertEqual(len(prep["opponents"]),2)
            self.assertEqual(len(prep["position_idx"]),16)

    def test_resumable_cursor_partial_games_no_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def successful(url):
                if "/score/" in url:
                    day=url.split("/")[-1]
                    return {"games":[{"id":2018020001,"gameState":"FINAL","gameType":2}]
                           if day=="2018-10-01" else []}
                return raw_game()
            first=backfill.collect(root,max_days=2,max_games=1,
                                   stop_before="2018-10-03",fetcher=successful)
            self.assertEqual(first["new_games"],1)
            self.assertEqual(first["status"],"partial")
            self.assertEqual(backfill.load_state(root)["next_date"],"2018-10-02")
            second=backfill.collect(root,max_days=2,max_games=1,
                                    stop_before="2018-10-03",fetcher=successful)
            self.assertEqual(second["new_games"],0)
            self.assertEqual(second["days_advanced"],2)
            self.assertEqual(backfill.load_state(root)["next_date"],"2018-10-04")
            self.assertEqual(len(wh.read_history(root,before="2018-10-04")),16)

    def test_network_failure_does_not_advance_incomplete_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def broken(url):
                if "/score/" in url:
                    return {"games":[{"id":2018020001,"gameState":"FINAL","gameType":2},
                                     {"id":2018020002,"gameState":"FINAL","gameType":2}]}
                if url.endswith("0002"):
                    raise RuntimeError("HTTP_429")
                return raw_game()
            result=backfill.collect(root,max_days=1,stop_before="2018-10-02",fetcher=broken)
            self.assertEqual(result["status"],"blocked")
            self.assertEqual(result["new_games"],1)
            self.assertEqual(backfill.load_state(root)["next_date"],"2018-10-01")
            def fixed(url):
                if "/score/" in url:
                    return {"games":[{"id":2018020001,"gameState":"FINAL","gameType":2},
                                     {"id":2018020002,"gameState":"FINAL","gameType":2}]}
                return raw_game(gid=2018020002 if url.endswith("0002") else 2018020001)
            again=backfill.collect(root,max_days=1,stop_before="2018-10-02",fetcher=fixed)
            self.assertEqual(again["skipped_games"],1)
            self.assertEqual(again["new_games"],1)
            self.assertEqual(len(wh.read_history(root,before="2018-10-02")),32)

    def test_regression_guards_and_shadow_nonpublication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=wh.canonical_game(raw_game(),"2018-10-01")
            wh.add_game(root,rows)
            first=bayes.prepare(rows,min_rows=10)
            self.assertEqual(first["source_digest"],bayes.prepare(rows,min_rows=10)["source_digest"])
            with self.assertRaisesRegex(ValueError,"insufficient_joint_model_history"):
                bayes.prepare(rows[:4],min_rows=10)
            with self.assertRaisesRegex(ValueError,"joint_mcmc_diagnostics_not_approved"):
                bayes.forecast(None,first,player_id="1000",opponent="NYR",
                    season="2018",home=True,line=2.5)
            with self.assertRaisesRegex(ValueError,"invalid_joint_posterior_sampling_budget"):
                bayes.fit(first,draws=1,tune=1,chains=1)


if __name__=="__main__":
    unittest.main()
