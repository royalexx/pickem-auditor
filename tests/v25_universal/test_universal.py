"""Finite, no-stakes tests: automatic discovery, strict chronology, scores and NFL future capture."""
import gzip
import json
import math
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

from research.v25_universal import registry,report
from research.v25_forward import nfl,scoring


def future_row(**extra):
    t=(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat()
    at=(datetime.now(timezone.utc)-timedelta(minutes=4)).isoformat()
    r={"schema":"V25FrozenResearchForecast/1","sport":"NFL","engine":"NovelO6",
       "event_id":"401000010","player_id":"123","stat":"receptions",
       "original_contract_id":"fake_contract","original_quote_id":"fake_quote",
       "line":4.5,"book":"Pinnacle","source_sha256":"f"*64,
       "source_received_at":at,"input_freeze_at":at,
       "model_training_cutoff_at":at,
       "forecast_at":at,"event_start_at":t,
       "conditioning":"given_played","status":"forecast",
       "distribution":{"kind":"discrete","masses":[[3,.3],[5,.7]]}}
    r.update(extra);return r


class RegistryTests(unittest.TestCase):
    def test_unknown_engine_autodiscovered_under_actual_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry.create_manifest(tmp,"novel_01","NFL","NovelO6",[future_row()])
            d=registry.discover(tmp)
            self.assertEqual(len(d["forecasts"]),1)
            self.assertEqual(d["forecasts"][0]["engine"],"NovelO6")

    def test_no_model_names_are_hardcoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry.create_manifest(tmp,"future_score","NFL","Transformer42",[
                future_row(engine="Transformer42")])
            self.assertEqual(registry.discover(tmp)["forecasts"][0]["engine"],"Transformer42")

    def test_reject_postgame_first_archive(self):
        past=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        earlier=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"FIRST_MANIFEST_ARCHIVE_AFTER_GAME_STARTED"):
                registry.create_manifest(tmp,"postgame","NFL","NovelO6",[
                    future_row(event_start_at=past,source_received_at=earlier,
                        input_freeze_at=earlier,forecast_at=earlier,
                        model_training_cutoff_at=earlier)])

    def test_reject_future_feature_and_training_leak(self):
        r=future_row();r["source_received_at"]=r["event_start_at"]
        with self.assertRaisesRegex(ValueError,"MODEL_SAME_GAME"):
            registry.validate_row(r,{"sport":"NFL","engine":"NovelO6"})

    def test_reject_renormalized_or_missing_probability(self):
        r=future_row();r["distribution"]["masses"]=[[3,.4],[4,.4]]
        with self.assertRaisesRegex(ValueError,"DISCRETE_MASS_NONUNIT"):
            registry.validate_row(r,{"sport":"NFL","engine":"NovelO6"})

    def test_binary_model_requires_original_nfl_contract(self):
        r=future_row(original_contract_id=None)
        with self.assertRaisesRegex(ValueError,"NFL_CONTRACT_IDENTITY_MISSING"):
            registry.validate_row(r,{"sport":"NFL","engine":"NovelO6"})

    def test_original_blob_change_quarantines(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry.create_manifest(tmp,"novel_02","NFL","NovelO6",[future_row()])
            p=Path(tmp)/registry.ROOT/"novel_02"/"forecasts.jsonl"
            p.write_text(p.read_text()+"\n")
            self.assertEqual(registry.discover(tmp)["forecasts"],[])
            self.assertTrue(registry.discover(tmp)["rejected"])

    def test_duplicate_unknown_engine_forecast_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry.create_manifest(tmp,"novel_03","NFL","NovelO6",[future_row(),future_row()])
            r=registry.discover(tmp)
            self.assertEqual(len(r["forecasts"]),1)
            self.assertIn("DUPLICATE",r["rejected"][0]["reason"])


class ScoreTests(unittest.TestCase):
    def test_binary_probability_computed_from_frozen_pmf(self):
        r=future_row()
        self.assertAlmostEqual(report._binary_probability(r,registry.validate_row(r,{"sport":"NFL","engine":"NovelO6"})["validated_distribution"],4.5),.7)

    def test_conditional_nba_m0_crps_without_unconditional_p(self):
        law={"mean":28.,"variance":24.,"ot_probability":.06,"ot_continuation":.25,
             "family":"beta"}
        metrics=report.minutes_continuous_scores(law,29.0)
        self.assertGreater(metrics["crps"],0)
        self.assertLess(metrics["crps"],15)
        self.assertIn(metrics["covered_90"],(0,1))
        self.assertTrue(0<=metrics["pit"]<=1)

    def test_unconditional_requires_eligibility(self):
        r=future_row(conditioning="unconditional")
        d=registry.validate_row(r,{"sport":"NFL","engine":"NovelO6"})
        s=report._model_line("NFL",{},d,5,4.5,provenance="test")
        self.assertEqual(s["status"],"BLOCKED_UNCONDITIONAL_PARTICIPATION_NOT_CERTIFIED")

    def test_equal_contract_paired_scoring_and_calendar_date(self):
        now=datetime.now(timezone.utc)
        e=now.isoformat()
        items=[
          dict(sport="NFL",event_id="1000",player_id="12",stat="receptions",
               engine=n,conditioning="given_played",contract_key="same",
               event_date=now.date().isoformat(),actual=5,line=4.5,
               metrics={"brier":value,"logloss":.3,"crps":.9},
               binary_y=1,p_over=p)
          for n,value,p in (("S2",.04,.8),("NovelO6",.01,.9))]
        result=report._report(items,{})
        self.assertTrue(any(x["first"]=="NovelO6" and x["second"]=="S2"
                            and x["paired_contracts"]==1 for x in result["paired"]))
        self.assertEqual(result["models"][0]["distinct_game_dates"],1)
        self.assertIsNone(result["paired"][0]["game_cluster_bootstrap_95"])

    def test_registry_nba_m0_only_scored_if_played(self):
        now=datetime.now(timezone.utc)
        later=(now+timedelta(hours=7)).isoformat()
        earlier=(now-timedelta(minutes=1)).isoformat()
        r=future_row(sport="NBA",engine="M0",event_id="401000010",
              game_id="espn:game:401000010",player_id="espn:player:1",
              team_id="espn:team:2",stat="minutes",line=None,
              conditioning="given_played",
              source_received_at=earlier,input_freeze_at=earlier,
              forecast_at=earlier,model_training_cutoff_at=earlier,
              event_start_at=later,
              distribution={"kind":"nba_minutes_law","parameters":{
                  "mean":25.,"variance":18.,"ot_probability":.05,
                  "ot_continuation":.2,"family":"beta"}})
        normalized=registry.validate_row(r,{"sport":"NBA","engine":"M0"})
        z=report._model_line("NBA",{},normalized,26,None,provenance="original")
        self.assertEqual(z["status"],"SCORED")
        self.assertIn("crps",z["metrics"])
        self.assertNotIn("brier",z["metrics"])

    def test_missing_registry_and_missing_nba_never_makes_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);out=base/"morning";out.mkdir()
            x=report.build(base,out)
            self.assertEqual(x["registry_forecasts"],0)
            r=json.loads((out/"unified_model_comparison.json").read_text())
            self.assertEqual(r["scored_row_count"],0)
            self.assertEqual(r["denominators"]["NBA_settled_candidates"],0)


class NFLForwardTests(unittest.TestCase):
    def test_original_date_dryrun_has_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            x=nfl.run(day="2026-11-22",storage=p,dry_run=True)
            self.assertEqual(x["status"],"DRY_RUN_NO_SOURCE_CAPTURE")
            self.assertFalse((p/nfl.ROOT).exists())

    def test_original_window_late_fails_without_any_claim(self):
        t=datetime.now(timezone.utc)+timedelta(minutes=20)
        game={"event_id":"401000010","event_start_at":t.isoformat(),
              "home":{"id":"1","abbr":"NE"},"away":{"id":"2","abbr":"DET"}}
        with tempfile.TemporaryDirectory() as tmp:
            r=nfl.capture_game(game,t.astimezone(nfl.TZ).date().isoformat(),tmp,{},at=datetime.now(timezone.utc))
            self.assertEqual(r["status"],"NOT_IN_ORIGINAL_WINDOW")
            self.assertFalse((Path(tmp)/"event_401000010"/"FIRST_CAPTURE.json").exists())

    def test_missed_first_claim_is_never_retried(self):
        start=datetime.now(timezone.utc)+timedelta(minutes=45)
        game={"event_id":"401000015","event_start_at":start.isoformat(),
              "home":{"id":"1","abbr":"NE"},"away":{"id":"2","abbr":"DET"}}
        with tempfile.TemporaryDirectory() as tmp:
            at=datetime.now(timezone.utc)
            # First attempt fails original source; claim remains for forensic review.
            r=nfl.capture_game(game,start.astimezone(nfl.TZ).date().isoformat(),tmp,
                               {"status":"NO_VALID_ORIGINAL_QUOTES","receipts":[],"quotes":[]},
                               at=at,fetch=lambda url,headers: (_ for _ in ()).throw(ValueError("OFFLINE")))
            self.assertEqual(r["status"],"BLOCKED_CAPTURE_FIRST_CLAIM_PRESERVED")
            again=nfl.capture_game(game,start.astimezone(nfl.TZ).date().isoformat(),tmp,
                               {},at=at,fetch=lambda url,headers: b'{}')
            self.assertEqual(again["status"],"ALREADY_CLAIMED_NO_RETRY")

    def test_original_first_capture_preserved_bad_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/scoring.SOURCE/"2026-11-22"/"event_123"
            base.mkdir(parents=True)
            (base/"FIRST_CAPTURE.json").write_text(json.dumps({"snapshot":"snapshot.json","sha256":"0"*64}))
            (base/"snapshot.json").write_text('{"x":1}')
            audited,rows=scoring._original_contracts(tmp)
            self.assertEqual(len(rows),0)
            self.assertEqual(audited[0]["status"],"ORIGINAL_BLOCKED")
            self.assertIn("FORWARD_ORIGINAL_HASH_CHANGED",audited[0]["reason"])


if __name__=="__main__":unittest.main()
