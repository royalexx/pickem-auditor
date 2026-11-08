"""Offline tests for append-only Deepnote <> GitHub population exchange."""
import hashlib
import base64
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

    def test_oversize_archive_reconstructed_exactly_from_manifest_parts(self):
        payload_text="".join(hashlib.sha256(str(i).encode()).hexdigest()
                             for i in range(60))
        doc={"schema":live.SCHEMA, "phase":"afternoon",
             "game_date":"2026-11-05",
             "captured_at_utc":"2026-11-05T17:00:00Z",
             "run_id":"first-r1",
             "forecasts":[{"game_date":"2026-11-05","run_id":"first-r1",
                           "forecast_at":"2026-11-05T16:58:00Z",
                           "player_id":"one","sport":"NFL","stat":"pass attempts",
                           "side":"over","reference_line":32.5}],
             "source_quotes":[{"source":"s","data":payload_text}],
             "shadow":{"model_comparisons":[{"run_id":"first-r1",
                                             "q_win":.615,"q_push":0.0}]}}
        stored={}
        blobs={}
        writes=[]
        def fake_api(route, *, token, method="GET", payload=None):
            if route.startswith("/git/trees/"):
                return {"tree":[{"path":path,"sha":v["sha"],"type":"blob"}
                                for path,v in stored.items()]}
            if method=="PUT" and route.startswith("/contents/"):
                path=route[len("/contents/"):]
                raw=base64.b64decode(payload["content"])
                if path in stored:raise RuntimeError("GITHUB_API_422_PUT_contents")
                sha=hashlib.sha1(raw).hexdigest()
                stored[path]={"sha":sha,"bytes":raw}
                blobs[sha]=raw
                writes.append(path)
                self.assertEqual(payload["branch"],live.BRANCH)
                return {"commit":{"sha":"fake-commit"}}
            if route.startswith("/contents/"):
                path=route[len("/contents/"):].split("?ref=")[0]
                if path not in stored:raise RuntimeError("GITHUB_API_404_GET_contents")
                return {"sha":stored[path]["sha"]}
            raise AssertionError("unexpected API: "+route)
        with (patch.object(live,"MAX_COMPRESSED",400),
              patch.object(live,"ARCHIVE_PART_BYTES",240),
              patch.object(live,"api",side_effect=fake_api),
              patch.object(live,"read_blob",side_effect=lambda sha,token:blobs[sha])):
            published=live.publish(doc,token="test-token")
            self.assertEqual(published["archive_format"],"manifest_parts_v1")
            self.assertGreater(published["part_count"],1)
            self.assertTrue(writes[-1].endswith(".manifest.json"))
            self.assertTrue(all("/parts/" in path for path in writes[:-1]))
            self.assertEqual(sum(path.endswith(".manifest.json") for path in writes),1)
            recovered=list(live.iter_remote_docs(token="test-token",
                    before="2026-11-06",after="2026-11-05",phase="afternoon"))
            self.assertEqual(len(recovered),1)
            self.assertEqual(recovered[0][0],doc)
            self.assertEqual(recovered[0][1],published["path"])
            again=live.publish(doc,token="test-token")
            self.assertEqual(again["status"],"already_present")
            self.assertEqual(len(writes),published["part_count"]+1)
            one_part=next(path for path in writes if "/parts/" in path)
            sha=stored[one_part]["sha"]
            blobs[sha]=b"bad-data"
            with self.assertRaisesRegex(ValueError,"LIVE_POOL_SHARD_DIGEST_MISMATCH"):
                list(live.iter_remote_docs(token="test-token",
                     before="2026-11-06",after="2026-11-05",phase="afternoon"))

    def test_uncommitted_parts_are_not_visible_to_settlement(self):
        payload_text="".join(hashlib.sha256(str(i).encode()).hexdigest()
                             for i in range(48))
        doc={"schema":live.SCHEMA,"phase":"morning","game_date":"2026-11-05",
             "population":[{"blob":payload_text}]}
        stored={}
        blobs={}
        part_writes=0
        fail_once=True
        def api(route, *, token, method="GET", payload=None):
            nonlocal part_writes,fail_once
            if route.startswith("/git/trees/"):
                return {"tree":[{"path":path,"sha":key,"type":"blob"}
                                for path,key in stored.items()]}
            if method=="PUT":
                path=route[len("/contents/"):]
                if "/parts/" in path:
                    part_writes+=1
                    if fail_once and part_writes==2:
                        fail_once=False
                        raise RuntimeError("GITHUB_API_500_PUT_contents")
                raw=base64.b64decode(payload["content"])
                digest=hashlib.sha1(raw).hexdigest()
                stored[path]=digest
                blobs[digest]=raw
                return {"commit":{"sha":"commit"}}
            raise AssertionError("unexpected call")
        with (patch.object(live,"MAX_COMPRESSED",400),
              patch.object(live,"ARCHIVE_PART_BYTES",240),
              patch.object(live,"api",side_effect=api),
              patch.object(live,"read_blob",side_effect=lambda sha,token:blobs[sha])):
            with self.assertRaisesRegex(RuntimeError,"GITHUB_API_500"):
                live.publish(doc,token="token")
            self.assertFalse(any(path.endswith(".manifest.json") for path in stored))
            self.assertEqual(list(live.iter_remote_docs(token="token",
                             before="2026-11-06",phase="morning")),[])
            # A retry sees existing shard content; mock API mimics idempotent
            # immutable writes for a previously uploaded first shard.
            def retry_api(route, *, token, method="GET", payload=None):
                if route.startswith("/git/trees/"):
                    return {"tree":[{"path":path,"sha":sha,"type":"blob"}
                                    for path,sha in stored.items()]}
                if method=="PUT":
                    path=route[len("/contents/"):]
                    raw=base64.b64decode(payload["content"])
                    if path in stored:
                        raise RuntimeError("GITHUB_API_422_PUT_contents")
                    sha=hashlib.sha1(raw).hexdigest()
                    stored[path]=sha;blobs[sha]=raw
                    return {"commit":{"sha":"commit"}}
                if route.startswith("/contents/"):
                    path=route[len("/contents/"):].split("?ref=")[0]
                    return {"sha":stored[path]}
                raise AssertionError(route)
            with patch.object(live,"api",side_effect=retry_api):
                receipt=live.publish(doc,token="token")
                self.assertEqual(receipt["status"],"published")
                self.assertEqual(len(list(live.iter_remote_docs(
                    token="token",before="2026-11-06",phase="morning"))),1)

    def test_recovery_copy_preserves_original_pregame_bytes(self):
        doc={"schema":live.SCHEMA,"phase":"afternoon",
             "game_date":"2026-11-05","predictions_are_frozen":True,
             "forecasts":[{"game_date":"2026-11-05",
                           "forecast_at":"2026-11-05T17:00:00Z",
                           "event_start":"2026-11-05T19:00:00Z",
                           "actual_stat":None,"run_id":"r1",
                           "side":"over","reference_line":2.5}],
             "shadow":{"model_comparisons":[{"q_win":.65,"q_push":0.0}]}}
        with tempfile.TemporaryDirectory() as tmp:
            p=live.write_recovery_copy(doc,tmp)
            self.assertTrue(p.is_file())
            self.assertEqual(live.load_recovery_copy(p),doc)
            self.assertEqual(live.write_recovery_copy(doc,tmp),p)
            original=p.read_bytes()
            p.write_bytes(original[:-1]+bytes([original[-1]^1]))
            with self.assertRaisesRegex(ValueError,"RECOVERY_COPY_DIGEST_MISMATCH"):
                live.load_recovery_copy(p)
        invalid=json.loads(json.dumps(doc))
        invalid["forecasts"][0]["forecast_at"]="2026-11-05T20:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            p=live.write_recovery_copy(invalid,tmp)
            with self.assertRaisesRegex(ValueError,"RECOVERY_COPY_FORECAST_NOT_PREGAME"):
                live.load_recovery_copy(p)

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

    def test_rerun_conflicts_restore_first_immutable_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original={"game_date":"2026-11-05","run_id":"same-run-id",
                      "forecast_at":"2026-11-05T23:18:00Z",
                      "sport":"NHL","player_id":"8480001","stat":"shots on goal",
                      "side":"over","reference_line":1.5,"q_win_robust":.6}
            revised=dict(original,forecast_at="2026-11-06T00:18:00Z",
                         q_win_robust=.4)
            first={"phase":"afternoon","game_date":"2026-11-05",
                   "captured_at_utc":"2026-11-05T23:29:00Z",
                   "forecasts":[original],"shadow":{}}
            second={"phase":"afternoon","game_date":"2026-11-05",
                    "captured_at_utc":"2026-11-06T00:21:00Z",
                    "forecasts":[revised],"shadow":{}}
            dest=root/"morning-restored.jsonl"
            with patch.object(live,"iter_remote_docs",
                              return_value=[(second,"later"),(first,"first")]):
                result=live.restore_forecasts(token="fixture",before="2026-11-06",
                                               after="2026-11-05",dest=dest)
            self.assertEqual(live.jsonl(dest),[original])
            self.assertEqual(result["restored_forecasts"],1)
            self.assertEqual(result["later_immutable_reruns_excluded"],1)
            self.assertEqual(result["canonical_dates"],1)

    def test_same_capture_incompatible_archives_are_ambiguous(self):
        base={"phase":"afternoon","game_date":"2026-11-05",
              "captured_at_utc":"2026-11-05T23:29:00Z",
              "forecasts":[{"game_date":"2026-11-05","run_id":"r1",
                            "forecast_at":"2026-11-05T23:18:00Z"}]}
        revised=json.loads(json.dumps(base))
        revised["forecasts"][0]["run_id"]="r2"
        with self.assertRaisesRegex(ValueError,"AMBIGUOUS_SAME_INSTANT"):
            live.canonical_afternoon_docs([base,revised])

    def test_afternoon_archives_nuts_saves_and_targets_without_fabricating_market_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            forecast={"game_date":"2026-11-05","run_id":"frozen-r1",
                      "run_type":"shadow","forecast_at":"2026-11-05T20:00:00Z",
                      "sport":"NHL","stat":"goalie saves","player_id":"848101",
                      "reference_line":22.5,"side":"over","actual_stat":None}
            live.dump_jsonl(root/"data/prop_snapshots.jsonl",[forecast])
            saves={"game_date":"2026-11-05","run_id":"frozen-r1",
                   "player_id":"848101","stat":"goalie saves","side":"over",
                   "reference_line":22.5,"forecast_at":"2026-11-05T20:00:00Z",
                   "generated_at":"2026-11-05T20:05:00Z","status":"forecast",
                   "q_win":0.71,"ranking_allowed":False,"shadow_only":True}
            targets={"game_date":"2026-11-05","run_id":"targets-projection:abc",
                     "stat":"targets","player_id":"00-0123","side":"over",
                     "line_origin":"research_threshold","reference_line":5.5,
                     "forecast_at":"2026-11-05T20:06:00Z","status":"forecast",
                     "q_win":0.63,"ranking_allowed":False,"shadow_only":True}
            live.dump_jsonl(root/"data/nhl_joint_saves_shadow/2026-11-05.jsonl",[saves])
            live.dump_jsonl(root/"data/nfl_context/2026-11-05.jsonl",[targets])
            doc=live.bundle(root,phase="afternoon",game_date="2026-11-05")
            self.assertEqual(doc["forecasts"],[forecast])
            self.assertEqual(doc["shadow"]["nhl_saves_nuts"],[saves])
            self.assertEqual(doc["shadow"]["nfl_targets_nuts"],[targets])
            self.assertEqual(doc["settlements"],[])
            self.assertNotIn("targets", [r["stat"] for r in doc["forecasts"]])

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
