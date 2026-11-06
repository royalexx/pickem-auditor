"""Daily NFL adapter: source timing, feature parity, persistence and release pins."""
import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_context_data as data
import nfl_read_features as reads
import nfl_context_release as rel
import nfl_context_live as live
import nfl_context_daily as daily
import nhl_context_train as io
from nfl_context_fixture import season


def chart(raw,year):
    codes=(0,1,2,"CHK","DES","SD")
    return [{"season":year,"nflverse_game_id":r["game_id"],"nflverse_play_id":r["play_id"],
             "read_thrown":codes[int(r["play_id"])%6]} for r in raw["pbp"]]


class DailyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=season(2026,rotate=True);cls.now=datetime(2026,11,3,15,tzinfo=timezone.utc)
        prior=season(2025,rotate=True)
        cls.prior=data.normalize(prior,season=2025,until=cls.now.isoformat())
        cls.seed=rel.history_seed([cls.prior],"2026-09-01T00:00:00Z")
        full=data.normalize(cls.raw,season=2026,until="2027-03-01T00:00:00Z")
        cls.full=reads.join(full,cls.raw["pbp"],chart(cls.raw,2026))
        cls.rows=data.examples([cls.prior,cls.full],"targets")
        cls.expected=next(r for r in cls.rows if r["game_id"].startswith('2026_10_'))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'season/nfl_context_2026.json.gz'
        self.payload=live.write(self.path,self.raw,chart(self.raw,2026),self.raw["stats"],
            season=2026,retrieved_at=(self.now-timedelta(minutes=1)).isoformat())
        players=sorted(self.seed["players"][i]["player_id"] for i in range(len(self.seed["players"])))
        players=sorted(set(players));names=data.NAMES+reads.FEATURE_NAMES
        self.d={"players":players,"teams":["AAA","BBB","CCC","DDD"],"positions":["WR"],"seasons":["2024","2025"],
            "player_position":{p:"WR" for p in players},"market":"targets","cutoff":"2026-09-01T00:00:00Z",
            "feature_names":names,"center":[0.]*len(names),"scale":[1.]*len(names),"read_features":True,"source_digest":"fixture"}
        n=16
        arrays={"population_workload":np.full((n,1),-1.),"population_log_rate":np.full((n,1),np.log(.12)),
            "player_effect":np.zeros((n,len(players),2)),"team_effect":np.zeros((n,4,2)),"season_effect":np.zeros((n,2,2)),
            "season_sd":np.full((n,2),.1),"beta_workload":np.zeros((n,7)),"beta_rate":np.zeros((n,len(names))),
            "workload_sigma":np.full(n,.3),"count_dispersion":np.full(n,10.)}
        self.cache={"n":n,"arrays":arrays,"source_digest":"fixture"}
        self.meta={"design":self.d,"history_seed":self.seed,"diagnostics":{"posterior_sampling_ok":True}}
        r=self.expected
        self.row={"game_date":"2026-11-03","sport":"NFL","stat":"targets","side":"over","reference_line":5.5,
            "player_id":r["player_id"],"player":"Fixture receiver","team":r["team"],"opponent":r["opponent"],
            "forecast_at":(self.now-timedelta(minutes=1)).isoformat(),"event_start":r["start_time"],
            "retrieved_at":(self.now-timedelta(minutes=1)).isoformat(),"run_type":"shadow","run_id":"one"}
        self.adapter=daily.Adapter(self.meta,self.cache,self.payload,io.file_hash(self.path),self.now)

    def tearDown(self):self.temp.cleanup()

    def test_feature_math_matches_training_and_pregame_has_no_outcome(self):
        p=self.adapter.features(self.row)
        expected=self.expected["x"]+reads.ReadHistory([self.full]).features(self.expected)[0]
        self.assertEqual(p["x"],expected)
        self.assertNotIn("target",p)
        result=self.adapter.evaluate(self.row)
        self.assertIsNone(result["target"]);self.assertIsNone(result["log_predictive_density"])
        self.assertEqual(result["context_application"],"joint_model_only_no_extra_B_or_read_multiplier")
        self.assertFalse(result["availability_verified"])

    def test_history_available_after_forecast_never_enters_core_features(self):
        altered=copy.deepcopy(self.payload["bundle"])
        r=next(r for r in altered["players"] if r["player_id"]==self.row["player_id"])
        r.update(start_time=(self.now-timedelta(days=1)).isoformat(),available_at=(self.now+timedelta(hours=1)).isoformat(),workload=159.)
        history=data.ContextHistory([self.seed,altered],"targets")
        p=self.adapter.features(self.row)
        before=history.features(p,as_of=self.now.isoformat())
        r["workload"]=1.
        self.assertEqual(before,history.features(p,as_of=self.now.isoformat()))
        self.assertNotEqual(before["x"],history.features(p,as_of=(self.now+timedelta(hours=2)).isoformat())["x"])

    def test_stale_source_future_source_and_hash_tampering_rejected(self):
        for now in (self.now+timedelta(hours=2),self.now-timedelta(hours=1)):
            with self.assertRaisesRegex(ValueError,"stale_or_future"):live.load(self.path,now)
        self.path.write_bytes(self.path.read_bytes()+b'bad')
        with self.assertRaisesRegex(ValueError,"hash_changed"):live.load(self.path,self.now)

    def test_identity_role_venue_start_quote_and_poststart_guards(self):
        changes=({"player_id":"unseen"},{"team":"ZZZ"},{"opponent":"ZZZ"},
                 {"event_start":(self.now-timedelta(hours=1)).isoformat()},
                 {"retrieved_at":(self.now-timedelta(hours=2)).isoformat()})
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):self.adapter.features({**self.row,**change})

    def test_append_only_retries_parent_snapshot_unchanged_and_settlement(self):
        snapshots=self.root/'snapshots.jsonl';snapshots.write_text(json.dumps(self.row)+'\n');original=snapshots.read_bytes()
        out=self.root/'nfl_context/2026-11-03.jsonl';receipt=self.root/'receipt.json'
        args=dict(snapshots=snapshots,data_root=self.root,model_dir=self.root/'unused',out=out,receipt=receipt,
                  game_date=self.row["game_date"],now=self.now)
        with patch.object(rel,"load",return_value=(self.meta,self.cache)):
            first=daily.run(**args)
        self.assertEqual(first["forecast_count"],1);saved=out.read_bytes()
        with patch.object(rel,"load",side_effect=AssertionError("must not reload a completed forecast")):
            second=daily.run(**args)
        self.assertEqual(second["new_rows"],0);self.assertEqual(saved,out.read_bytes());self.assertEqual(original,snapshots.read_bytes())
        snapshots.write_text(json.dumps({**self.row,"outcome":"win"})+'\n')
        result=daily.audit(snapshots=snapshots,directory=out.parent,out=self.root/'audit.json',now=self.now+timedelta(days=2))
        self.assertEqual(result["nonpush_scored"],1);self.assertFalse(result["ranking_allowed"])

    def test_release_rejects_metadata_and_parameter_changes(self):
        pins=io.load_json(rel.PIN_PATH)
        with self.assertRaisesRegex(ValueError,"unverified_nfl_release_metadata"):
            rel.validate_meta({"schema":"wrong"},pins)
        self.assertNotEqual(rel.array_hash(np.array([[1.,2.]])),rel.array_hash(np.array([[1.,3.]])))
        folder=self.root/'release';folder.mkdir()
        arrays={"test":np.zeros((6000,1))};hashes={k:rel.array_hash(v) for k,v in arrays.items()}
        meta={"schema":"nfl-targets-inference-release-v1","tag":"test","model_version":rel.model.VERSION,
              "source_posterior_sha256":"test","n":6000,"design":self.d,"history_seed":self.seed,"array_hashes":hashes}
        pins={"tag":"test","posterior_sha256":"test","array_hashes":hashes,
              "design_digest":data.common.digest(self.d),"history_seed_digest":data.common.digest(self.seed)}
        io.write_json(folder/'model.json',meta);np.savez_compressed(folder/'parameters.npz',**arrays)
        rel.load(folder,pins=pins)
        arrays['test'][0,0]=1.;np.savez_compressed(folder/'parameters.npz',**arrays)
        with self.assertRaisesRegex(ValueError,"unverified_nfl_parameter_values"):rel.load(folder,pins=pins)

    def test_receiver_slate_generates_target_projection_not_reception_probability(self):
        slate={**self.row,"stat":"receptions"};slate.pop('reference_line');slate.pop('side')
        (self.root/'slate_fetch.jsonl').write_text(json.dumps(slate)+'\n'+json.dumps({**slate,"stat":"receiving yards"})+'\n')
        out=self.root/'nfl_context/day.jsonl'
        with patch.object(rel,"load",return_value=(self.meta,self.cache)):
            r=daily.run(snapshots=self.root/'no-market-snapshots',data_root=self.root,model_dir=self.root/'model',
                out=out,receipt=self.root/'receipt.json',game_date=self.row['game_date'],now=self.now)
        self.assertEqual(r['forecast_count'],1)
        forecast=daily.read_rows(out)[0]
        self.assertEqual(forecast['stat'],'targets');self.assertEqual(forecast['source_stat'],'receptions')
        self.assertEqual(forecast['line_origin'],'research_threshold');self.assertEqual(forecast['reference_line'],5.5)
        self.assertEqual(forecast['forecast_kind'],'target_opportunity_projection')
        self.assertFalse(forecast['ranking_allowed'])

    def test_fresh_real_target_market_suppresses_synthetic_projection(self):
        slate={**self.row,"stat":"receptions"}
        (self.root/'slate_fetch.jsonl').write_text(json.dumps(slate)+'\n')
        snapshots=self.root/'snapshots.jsonl'
        snapshots.write_text(json.dumps(self.row)+'\n')
        out=self.root/'nfl_context/day.jsonl'
        with patch.object(rel,"load",return_value=(self.meta,self.cache)):
            result=daily.run(snapshots=snapshots,data_root=self.root,model_dir=self.root/'model',
                out=out,receipt=self.root/'receipt.json',game_date=self.row['game_date'],now=self.now)
        self.assertEqual(result['forecast_count'],1)
        self.assertEqual(result['market_target_forecasts'],1)
        self.assertEqual(result['research_threshold_forecasts'],0)
        record=daily.read_rows(out)[0]
        self.assertEqual(record['line_origin'],'market')
        self.assertEqual(record['forecast_kind'],'target_market_forecast')

    def test_stale_market_snapshot_does_not_suppress_fresh_projection(self):
        (self.root/'slate_fetch.jsonl').write_text(json.dumps({**self.row,'stat':'receptions'})+'\n')
        snapshots=self.root/'snapshots.jsonl'
        snapshots.write_text(json.dumps({**self.row,'retrieved_at':(self.now-timedelta(hours=2)).isoformat()})+'\n')
        out=self.root/'nfl_context/day.jsonl'
        with patch.object(rel,'load',return_value=(self.meta,self.cache)):
            result=daily.run(snapshots=snapshots,data_root=self.root,model_dir=self.root/'model',out=out,
                receipt=self.root/'receipt.json',game_date=self.row['game_date'],now=self.now)
        self.assertEqual(result['forecast_count'],1);self.assertEqual(result['unavailable_count'],1)
        prediction=next(r for r in daily.read_rows(out) if r['status']=='forecast')
        self.assertEqual(prediction['line_origin'],'research_threshold')

    def test_missing_charting_stays_missing_with_observation_masks(self):
        payload=live.write(self.path,self.raw,None,self.raw['stats'],season=2026,
                           retrieved_at=(self.now-timedelta(minutes=1)).isoformat())
        adapter=daily.Adapter(self.meta,self.cache,payload,io.file_hash(self.path),self.now)
        p=adapter.features(self.row)
        self.assertIsNone(p['x'][7]);self.assertFalse(p['read_context']['offense_read_available'])
        self.assertEqual(p['x'][7+len(reads.VALUE_NAMES)],0.)

    def test_ambiguous_catalog_player_is_excluded_without_losing_other_players(self):
        original=next(r for r in self.raw['stats'] if r['player_id']==self.row['player_id'])
        catalog=self.raw['stats']+[{**original,'team':'OTHER'}]
        payload=live.write(self.path,self.raw,chart(self.raw,2026),catalog,season=2026,
                           retrieved_at=(self.now-timedelta(minutes=1)).isoformat())
        self.assertIn(self.row['player_id'],payload['ambiguous_players'])
        self.assertNotIn(self.row['player_id'],payload['catalog'])
        self.assertGreater(len(payload['catalog']),1)

    def test_projection_settles_on_targets_with_exact_game_and_gsis_identity(self):
        slate={**self.row,"stat":"receiving yards"}
        (self.root/'slate_fetch.jsonl').write_text(json.dumps(slate)+'\n')
        out=self.root/'nfl_context/day.jsonl'
        with patch.object(rel,"load",return_value=(self.meta,self.cache)):
            daily.run(snapshots=self.root/'none',data_root=self.root,model_dir=self.root/'model',
                out=out,receipt=self.root/'receipt.json',game_date=self.row['game_date'],now=self.now)
        class Loader:
            def load_schedules(_,**kwargs):return self.raw['schedule']
            def load_player_stats(_,**kwargs):return self.raw['stats']
        live.refresh_actuals(self.root/'season/nfl_targets_actuals_2026.json.gz',2026,
                            self.now+timedelta(days=2),loader=Loader())
        result=daily.audit(snapshots=self.root/'none',directory=out.parent,out=self.root/'audit.json',
                           now=self.now+timedelta(days=2))
        self.assertEqual(result['nonpush_scored'],1)
        self.assertIn('research_threshold',result['by_line_origin'])

    def test_no_nfl_candidates_needs_no_assets_or_network(self):
        with patch.object(rel,"load",side_effect=AssertionError("no model download")):
            r=daily.run(snapshots=self.root/'missing',data_root=self.root,model_dir=self.root/'missing',
                out=self.root/'empty.jsonl',receipt=self.root/'empty.json',game_date='2026-11-03',now=self.now)
        self.assertEqual(r["candidates"],0);self.assertEqual(r["status"],"completed")
