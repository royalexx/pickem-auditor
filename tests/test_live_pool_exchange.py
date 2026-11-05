"""Offline tests for append-only Deepnote <> GitHub population exchange."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import live_pool_exchange as live

class LivePoolTests(unittest.TestCase):
    def test_gzip_content_digest_is_stable_and_refuses_bad_phase(self):
        record={"schema":live.SCHEMA,"phase":"afternoon","game_date":"2026-11-05","forecasts":[]}
        first=live.pack(record)
        self.assertEqual(first,live.pack(record))
        self.assertEqual(live.unpack(first),record)
        digest=hashlib.sha256(first).hexdigest()
        self.assertEqual(live.archive_path("2026-11-05","afternoon",digest),
                         "data/live_pool/2026-11-05/afternoon/"+digest+".json.gz")
        with self.assertRaises(ValueError):live.archive_path("2026-11-05","other",digest)

    def test_afternoon_bundle_freezes_pregame_run_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows=[
                {"game_date":"2026-11-04","run_id":"old","run_type":"shadow","forecast_at":"2026-11-04T19:00:00Z"},
                {"game_date":"2026-11-05","run_id":"new","run_type":"shadow","forecast_at":"2026-11-05T20:00:00Z",
                 "player":"P1","sport":"NHL","stat":"shots on goal","reference_line":2.5,"side":"over"},
            ]
            live.dump_jsonl(root/"data/prop_snapshots.jsonl",rows)
            doc=live.bundle(root,phase="afternoon",game_date="2026-11-05")
            self.assertEqual(doc["run_id"],"new")
            self.assertEqual(len(doc["forecasts"]),1)
            self.assertEqual(doc["settlements"],[])
            self.assertEqual(doc["population"],[])
            rows[1]["actual_stat"]=3
            live.dump_jsonl(root/"data/prop_snapshots.jsonl",rows)
            with self.assertRaisesRegex(ValueError,"already_contains_outcome"):
                live.bundle(root,phase="afternoon",game_date="2026-11-05")

    def test_morning_bundle_contains_outcomes_not_new_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            live.dump_jsonl(root/"settled.jsonl",[
                {"game_date":"2026-11-04","run_type":"shadow","run_id":"r1",
                 "actual_stat":4,"outcome":"win","settled_at":"2026-11-05T11:00:00Z"}])
            doc=live.bundle(root,phase="morning",game_date="2026-11-04",
                            snapshot_path=root/"settled.jsonl")
            self.assertEqual(len(doc["settlements"]),1)
            self.assertEqual(doc["forecasts"],[])
            self.assertEqual(doc["source_quotes"],[])
            self.assertEqual(doc["population"],[])

    def test_github_put_is_add_only_and_uses_data_branch(self):
        doc={"schema":live.SCHEMA,"phase":"morning","game_date":"2026-11-04","population":[]}
        observed=[]
        def fake_api(route,**kwargs):
            observed.append((route,kwargs))
            return {"commit":{"sha":"fake-test-commit"}}
        with patch.object(live,"api",side_effect=fake_api):
            receipt=live.publish(doc,token="placeholder-only")
        self.assertEqual(receipt["status"],"published")
        self.assertEqual(len(observed),1)
        self.assertEqual(observed[0][1]["payload"]["branch"],live.BRANCH)
        self.assertTrue(receipt["path"].startswith("data/live_pool/2026-11-04/morning/"))
        self.assertFalse("placeholder-only" in json.dumps(receipt))

    def test_remote_import_never_accepts_future_records(self):
        # Strictly exclusive cutoff is enforced before reading any remote blob.
        called=[]
        def fake_tree(route,**kwargs):
            called.append(route)
            return {"tree":[
                {"path":"data/live_pool/2026-11-06/morning/"+"a"*64+".json.gz","sha":"a"*40},
                {"path":"data/live_pool/2026-11-05/morning/"+"b"*64+".json.gz","sha":"b"*40},
            ]}
        with patch.object(live,"api",side_effect=fake_tree),patch.object(live,"read_blob") as read:
            docs=list(live.iter_remote_docs(token="fake",before="2026-11-05"))
        self.assertEqual(docs,[])
        read.assert_not_called()
        self.assertTrue(called)

    def test_import_merges_one_verified_game_and_keeps_other_sources_single_count(self):
        import population_history as hist
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            row=hist.make(sport="NHL",stat="shots on goal",game_id=2026020501,
                          game_date="2026-11-04",season="2026",player_id=8480001,
                          position="F",team="BOS",opponent="MTL",home=True,
                          value=3,workload=18.5,workload_unit="minutes",
                          source_url="https://api-web.nhle.com/v1/gamecenter/2026020501/boxscore",
                          source_sha256="a"*64)
            doc={"schema":live.SCHEMA,"phase":"morning","game_date":"2026-11-04",
                 "population":[row]}
            with patch.object(live,"iter_remote_docs",return_value=[(doc,"record")]):
                result=live.import_population(root,token="test",before="2026-11-05")
            self.assertEqual(result["records_imported"],1)
            p=hist.read(root,sport="NHL",stat="shots on goal",before="2026-11-05")
            self.assertEqual(len(p),1)
            copy=dict(row,source_sha256="b"*64,
                      source_url="https://other.example/source")
            with patch.object(live,"iter_remote_docs",
                              return_value=[({"game_date":"2026-11-04","population":[copy]},"other")]):
                duplicate=live.import_population(root,token="test",before="2026-11-05")
            self.assertEqual(duplicate["records_imported"],0)
            self.assertEqual(duplicate["redundant"]["same_player_game_stat"],1)
            conflict=dict(copy,value=4)
            with patch.object(live,"iter_remote_docs",
                              return_value=[({"game_date":"2026-11-04","population":[conflict]},"bad")]):
                with self.assertRaisesRegex(ValueError,"LIVE_SOURCE_OBSERVATION_CONFLICT"):
                    live.import_population(root,token="test",before="2026-11-05")

    def test_afternoon_freezes_online_bayesian_shadow_for_next_morning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original={"game_date":"2026-11-05","run_id":"cloud-123","run_type":"shadow",
                      "forecast_at":"2026-11-05T18:00:00Z","sport":"NHL",
                      "player":"Skater","stat":"shots on goal",
                      "reference_line":1.5,"side":"over"}
            online={"game_date":"2026-11-05","run_id":"cloud-123",
                    "sport":"NHL","player":"Skater","models":{
                    "player_rate_gamma_poisson":{"status":"research_shadow","q_win":.6,
                                                  "publication_eligible":False}}}
            live.dump_jsonl(root/"data/prop_snapshots.jsonl",[original])
            live.dump_jsonl(root/"data/online_bayes_shadow/2026-11-05.jsonl",[online])
            doc=live.bundle(root,phase="afternoon",game_date="2026-11-05")
            self.assertEqual(doc["shadow"]["online_bayes"],[online])
            self.assertEqual(doc["forecasts"],[original])
            self.assertEqual(doc["settlements"],[])

if __name__=="__main__":unittest.main()
