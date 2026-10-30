import copy
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_context_data as data
import nfl_context_campaign as campaign
import nfl_context_model as model
import nhl_context_train as io
from nfl_context_fixture import season


def config():
    c=io.load_json(campaign.ROOT/"config/nfl_context_targets_pilot.json")
    c.update(seasons=[2023,2024,2025],train_from="2023-08-01T00:00:00Z",cutoff="2025-09-01T00:00:00Z",
             until="2026-02-01T00:00:00Z",pilot_games=32)
    return c


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=season(2023)
        cls.bundle=data.normalize(cls.raw,season=2023,until=config()["until"])

    def test_team_data_is_not_sum_of_player_snaps(self):
        b=self.bundle;t=b["teams"][0]
        p=[r for r in b["players"] if r["stat"]=="targets" and r["game_id"]==t["game_id"] and r["team"]==t["team"]]
        self.assertEqual(sum(r["value"] for r in p),t["targets"])
        self.assertNotEqual(sum(r["workload"] for r in p),t["plays"])

    def test_play_type_schema_excludes_nullified_plays_without_no_play_column(self):
        raw=copy.deepcopy(self.raw)
        for p in raw["pbp"]:
            p.pop("no_play")
            p["play_type"]="pass" if p["qb_dropback"] else "run"
        void=copy.deepcopy(raw["pbp"][0]);void.update(play_id=999999,play_type="no_play")
        raw["pbp"].append(void)
        b=data.normalize(raw,season=2023,until=config()["until"])
        self.assertEqual(b["teams"],self.bundle["teams"])
        self.assertEqual(b["players"],self.bundle["players"])

    def test_missing_classification_never_becomes_zero(self):
        raw=copy.deepcopy(self.raw);raw["pbp"][0].pop("no_play")
        with self.assertRaisesRegex(ValueError,"no_play_classification"):
            data.normalize(raw,season=2023,until=config()["until"])
        self.assertTrue(data.no_play({"no_play":0,"play_type":"no_play","pass_attempt":1}))
        self.assertTrue(data.no_play({"play_type":None,"pass_attempt":None}))

    @unittest.skipUnless(importlib.util.find_spec("polars") is not None,"optional Polars schema check")
    def test_actual_polars_adapter_accepts_play_type_schema(self):
        import polars as pl
        rows=copy.deepcopy(self.raw["pbp"])
        for r in rows:
            r.pop("no_play");r["play_type"]="pass" if r["qb_dropback"] else "run"
        frame=pl.DataFrame(rows)
        selected=data.pbp_records(frame)
        self.assertEqual(len(selected),len(rows))
        self.assertNotIn("no_play",selected[0])
        self.assertIn("play_type",selected[0])
        with self.assertRaisesRegex(ValueError,"no_play_or_play_type"):
            data.pbp_records(frame.drop("play_type"))

    def test_weekly_pbp_discrepancy_is_explicit_and_excluded(self):
        raw=copy.deepcopy(self.raw);raw["stats"][0]["targets"]+=1
        b=data.normalize(raw,season=2023,until=config()["until"])
        self.assertEqual(b["excluded"][0]["reason"],"weekly_pbp_count_mismatch")
        pid=raw["stats"][0]["player_id"];gid=raw["schedule"][0]["game_id"]
        self.assertFalse(any(r["player_id"]==pid and r["game_id"]==gid and r["stat"]=="targets" for r in b["players"]))

    def test_missing_completed_game_pbp_fails_closed(self):
        raw=copy.deepcopy(self.raw);gid=raw["schedule"][0]["game_id"]
        raw["pbp"]=[p for p in raw["pbp"] if p["game_id"]!=gid]
        with self.assertRaisesRegex(ValueError,"missing_pbp"):data.normalize(raw,season=2023,until=config()["until"])

    def test_duplicate_pbp_not_double_counted_and_conflicts_rejected(self):
        raw=copy.deepcopy(self.raw);raw["pbp"].append(copy.deepcopy(raw["pbp"][0]))
        b=data.normalize(raw,season=2023,until=config()["until"])
        self.assertEqual(b["teams"],self.bundle["teams"])
        raw["pbp"][-1]["complete_pass"]=1-raw["pbp"][-1]["complete_pass"]
        with self.assertRaisesRegex(ValueError,"duplicate_pbp"):data.normalize(raw,season=2023,until=config()["until"])

    def test_future_targets_and_workloads_do_not_change_pregame_features(self):
        rows=data.examples([self.bundle],"targets");r=rows[30]
        changed=copy.deepcopy(self.bundle)
        for p in changed["players"]:
            if p["start_time"]>=r["start_time"]:p["value"]+=99;p["workload"]=159
        for t in changed["teams"]:
            if t["start_time"]>=r["start_time"]:t["targets"]+=999;t["plays"]+=999
        lookup={(p["game_id"],p["player_id"]):p for p in data.examples([changed],"targets")}
        self.assertEqual(r["x"],lookup[(r["game_id"],r["player_id"])]["x"])

    def test_late_availability_cannot_enter_features(self):
        changed=copy.deepcopy(self.bundle)
        for r in changed["teams"]+changed["players"]:r["available_at"]="2030-01-01T00:00:00Z"
        rows=data.examples([changed],"targets")
        self.assertTrue(all(r["prior_player_games"]==0 for r in rows))
        self.assertTrue(all(r["x"][3:]==[65.,65.,30.,30.] for r in rows))

    def test_asof_excludes_unavailable_completed_game(self):
        start=data.kickoff(self.raw["schedule"][0])
        # All first-week games have identical kickoff; nothing is yet available.
        with self.assertRaisesRegex(ValueError,"empty_nfl_context_source"):
            data.normalize(self.raw,season=2023,until=(start+data.timedelta(hours=18)).isoformat())

    def test_cache_is_idempotent_and_integrity_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def fetcher(s):calls.append(s);return self.raw
            data.collect(folder,[2023],config()["until"],fetcher=fetcher)
            data.collect(folder,[2023],config()["until"],fetcher=fetcher)
            self.assertEqual(calls,[2023])
            (Path(folder)/"season_2023.json.gz").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"cache_hash"):data.collect(folder,[2023],config()["until"],fetcher=fetcher)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundles=[data.normalize(season(y),season=y,until=config()["until"]) for y in (2023,2024,2025)]

    def test_freeze_uses_identical_cohorts_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            report=campaign.freeze(folder,config(),self.bundles)
            self.assertEqual(report["training_seasons"],["2023","2024"])
            self.assertEqual(report["training_games"],32)
            a=io.load_json(Path(folder)/"training_rows.json");b=io.load_json(Path(folder)/"base_training_rows.json")
            key=lambda r:(r["game_id"],r["player_id"])
            self.assertEqual({key(r) for r in a},{key(r) for r in b})
            self.assertTrue(all(data.common.instant(r["available_at"])<data.common.instant(config()["cutoff"]) for r in a))
            campaign.verify_frozen(folder)
            io.write_json(Path(folder)/"holdout_rows.json",[])
            with self.assertRaisesRegex(ValueError,"frozen_input_changed"):campaign.verify_frozen(folder)

    def test_unseen_holdout_entities_are_not_silently_mapped(self):
        changed=copy.deepcopy(self.bundles)
        for r in changed[-1]["players"]:
            if r["player_id"]=="WR-BBB-0":r["player_id"]="new-rookie"
        with tempfile.TemporaryDirectory() as folder:
            report=campaign.freeze(folder,config(),changed)
            self.assertTrue(report["excluded_holdout"])
            self.assertTrue(all(r["reason"]=="unseen_entity" for r in report["excluded_holdout"]))

    def test_invalid_config_rejected(self):
        c=config();c["cores"]=True
        with self.assertRaises(ValueError):campaign.validate(c)


@unittest.skipUnless(os.environ.get("RUN_NFL_CONTEXT_NUTS")=="1","opt-in numerical NFL smoke")
class NumericalTests(unittest.TestCase):
    def test_all_market_graphs_sampling_and_prediction_roundtrip(self):
        import arviz as az
        bundles=LifecycleTests.bundles if hasattr(LifecycleTests,"bundles") else [data.normalize(season(y),season=y,until=config()["until"]) for y in (2023,2024,2025)]
        with tempfile.TemporaryDirectory() as folder:
            campaign.freeze(folder,config(),bundles)
            d=io.load_json(Path(folder)/"context_design.json")
            for market in data.MARKETS:
                rows=[r for r in data.examples(bundles,market) if data.common.instant(r["available_at"])<data.common.instant(config()["cutoff"])]
                market_design=data.prepare(rows,config()["cutoff"],minimum=20)
                graph=model.build(market_design)
                self.assertIn("team_effect",graph.named_vars)
                self.assertIn("player_effect",graph.named_vars)
            trace=model.fit(d,draws=25,tune=25,chains=2,cores=1)
            diag=model.diagnostics(trace)
            self.assertFalse(diag["posterior_sampling_ok"])
            self.assertNotEqual(diag["status"],"diagnostics_unavailable",diag)
            row=io.load_json(Path(folder)/"holdout_rows.json")[0]
            cache=model.cache(trace,d)
            with self.assertRaisesRegex(ValueError,"not_converged"):
                model.forecast(cache,d,row,line=5.5,diagnostic=diag)
            opts=dict(line=5.,draws=250,diagnostic={"posterior_sampling_ok":True})
            pred=model.forecast(cache,d,row,**opts)
            self.assertAlmostEqual(sum(pred[k] for k in ("q_over","q_under","q_push")),1.,places=10)
            self.assertGreater(pred["q_push"],0.)
            self.assertTrue(0<pred["expected_snaps"]<160)
            self.assertFalse(pred["ranking_allowed"])
            trace.to_netcdf(Path(folder)/"posterior.nc")
            restored=az.from_netcdf(Path(folder)/"posterior.nc")
            self.assertEqual(pred,model.forecast(model.cache(restored,d),d,row,**opts))
