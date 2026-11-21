"""Isolated P3 mathematical and point-in-time tests (synthetic only).

No synthetic source or test-run output is original NBA pregame evidence.
P0 authoritative admission is exercised against on-disk test bytes.
"""
from __future__ import annotations
import copy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v2.p0_integrity.contracts import record, sha256, validate_record
from research.nba_p3_frozen.distributions import (
    ForecastBlocked, pmf, mixture, empirical, statistics, threshold, combo_counts)
from research.nba_p3_frozen.joint import lineup_segments, simulate
from research.nba_p3_frozen.engine import (
    generate, fit_research_parameters, previous_version, create_research_model,
    validate_research_model, MODEL_SCHEMA)

CODE="a"*40
TRAIN="c"*64
FREEZE="2026-11-21T20:00:00Z"
FORECAST="2026-11-21T20:01:00Z"
START="2026-11-22T00:00:00Z"
CUTOFF="2026-11-20T19:00:00Z"


def fake_game():
    players=[]
    params={}
    for ti,team in enumerate(("espn:team:A","espn:team:B")):
        for i in range(6):
            pid=f"espn:player:{ti}:{i}"
            players.append({"player_id":pid,"team_id":team,
                            "participation_probability":1.,
                            "projected_minutes":30. if i<5 else 10.})
            params[pid]={"two_attempts_per_minute":0.33,
                         "three_attempts_per_minute":0.14,
                         "free_throws_per_minute":0.17,
                         "two_pct":0.52,"three_pct":0.36,"ft_pct":0.79,
                         "rebound_weight":1.,"assist_weight":1.}
    return ({"schema":"NBA-P3-JointInput/1",
             "teams":["espn:team:A","espn:team:B"],"players":players},params)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"sources").mkdir()
        (self.root/"models").mkdir()
        raw=b"SYNTHETIC TEST SOURCE - NOT AN ORIGINAL NBA CAPTURE\n"
        (self.root/"sources"/"source.txt").write_bytes(raw)
        srcsha=hashlib.sha256(raw).hexdigest()
        self.source=record("SourceReceipt",receipt_id="synthetic-p3-receipt-1",
             source_id="synthetic-test",source_kind="test_fixture",
             source_available_at="2026-11-21T19:00:00Z",
             collected_at="2026-11-21T19:00:00Z",
             source_sha256=srcsha,archive_path="sources/source.txt",
             provenance_class="collector_possession")
        self.game,self.parameters=fake_game()
        history=[{"game_id":f"espn:game:prior:{j}",
                  "game_date":f"2026-11-{18+j:02}",
                  "player_id":"espn:player:0:0","team_id":"espn:team:A",
                  "participation":"played","minutes":30.+j,
                  "stats":{"points":20+j,"rebounds":6+j,"assists":4+j,"threes":2+j}}
                  for j in range(2)]
        self.features={"interface_version":"PA-NBA-P3/SYNTHETIC-1",
                       "prior_player_history":history,
                       "participation_probability":1.,
                       "legal_eligibility":"VERIFIED",
                       "joint_game":self.game}
        self.refresh_feature()
        self.model_payload={
            "schema":MODEL_SCHEMA,"family":"S0",
            "model_id":"nba-p3/S0-test","model_version":"0.1-fixture",
            "training_cutoff_at":CUTOFF,"training_reference_sha256":TRAIN,
            "min_history_games":2,
            "priors_per_minute":{s:{"alpha":1.,"beta":1.} for s in ("points","rebounds","assists","threes")},
            "dispersion_shapes":{s:12. for s in ("points","rebounds","assists","threes")},
            "opportunity":{"espn:player:0:0":{"minutes_law":[
                {"minutes":25.,"probability":0.25},
                {"minutes":35.,"probability":0.75}]}},
            "joint_variant":"J1","joint_state":{"pace_sigma":0.05,
                "ot_probability":0.2,"ot_continuation":0.1,
                "assist_probability":0.65,
                "offensive_rebound_probability":0.22},
            "joint_parameters":self.parameters,
            "update_policy":"PERIODIC_FULL_REFIT_ONLY",
        }
        self.refresh_model()

    def refresh_feature(self):
        self.feature=record("PregameFeatureSnapshot",
             feature_snapshot_id="fixture:feature:1",sport="NBA",
             event_id="espn:game:target",team_id="espn:team:A",
             opponent_id="espn:team:B",player_id="espn:player:0:0",
             stat_key="points",period="full",input_freeze_at=FREEZE,
             source_receipt_ids=["synthetic-p3-receipt-1"],
             feature_sha256=sha256(self.features),
             reconstruction_class="reconstructed",features=copy.deepcopy(self.features))

    def refresh_model(self):
        raw=json.dumps(self.model_payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        (self.root/"models"/"model.json").write_bytes(raw)
        self.model=record("ModelArtifact",model_artifact_id="fixture:model:1",
            model_id=self.model_payload["model_id"],
            model_version=self.model_payload["model_version"],
            model_code_sha=CODE,artifact_sha256=hashlib.sha256(raw).hexdigest(),
            artifact_path="models/model.json",training_data_sha256=TRAIN,
            training_cutoff_at=CUTOFF,created_at="2026-11-20T19:01:00Z",
            training_scope="synthetic_only",feature_schema_id="PA-NBA-P1/1")

    def run_forecast(self,**changes):
        kwargs={"source_root":self.root,"event_start_at":START,
                "forecast_at":FORECAST,"code_commit":CODE,
                "run_id":"synthetic-run-1","season":2026,"seed":73,
                "pipeline":"S_ONLY","persist":False}
        kwargs.update(changes)
        return generate(self.feature,self.model,[self.source],**kwargs)


class DistributionTests(unittest.TestCase):
    def test_poisson_analytic(self):
        d,tail=pmf(3.0)
        self.assertLess(tail,1e-11)
        self.assertAlmostEqual(d[0],math.exp(-3),12)
        self.assertAlmostEqual(sum(d.values()),1.,12)
        self.assertAlmostEqual(sum(k*p for k,p in d.items()),3.,9)

    def test_nb2_analytic(self):
        d,_=pmf(4.,2.)
        self.assertAlmostEqual(d[0],(2/6)**2,11)
        self.assertAlmostEqual(sum(k*p for k,p in d.items()),4.,8)
        self.assertAlmostEqual(sum((k-4)**2*p for k,p in d.items()),12.,7)

    def test_mixture_zero_and_threshold(self):
        d,tail=mixture([(0.3,0.,None),(0.7,3.,None)])
        self.assertAlmostEqual(dict(d["masses"])[0],.3+.7*math.exp(-3),11)
        p=threshold(d,2)
        self.assertAlmostEqual(sum(p[k] for k in ("over","under","push")),1.,11)
        self.assertGreater(p["push"],0)
        self.assertEqual(threshold(d,2.5)["push"],0)
        self.assertLess(tail,1e-10)

    def test_invalid_probability_and_support(self):
        with self.assertRaises(ForecastBlocked): pmf(float("nan"))
        with self.assertRaises(ForecastBlocked): empirical([1,-1])
        with self.assertRaises(ForecastBlocked): mixture([(0.1,1.,None)])

    def test_combo_scenario_not_product_of_independent_marginals(self):
        paths=[{"points":7,"rebounds":3,"assists":2,"threes":1},
               {"points":0,"rebounds":0,"assists":0,"threes":0}]
        self.assertEqual(combo_counts(paths,"pra"),[12,0])
        self.assertEqual(combo_counts(paths,"ra"),[5,0])
        self.assertEqual(combo_counts(paths,"pr"),[10,0])
        self.assertEqual(combo_counts(paths,"pa"),[9,0])


class ForecastTests(Fixture):
    def test_s0_frozen_and_repeated_hash(self):
        a=self.run_forecast()
        b=self.run_forecast()
        self.assertEqual(a.status,"RESEARCH_DRY_RUN",a.reason)
        self.assertEqual(sha256(a.forecast),sha256(b.forecast))
        self.assertEqual(a.admission["admission_class"],"C")
        self.assertEqual(a.forecast["distribution"]["kind"],"poisson")
        self.assertEqual(a.forecast["distribution"]["parameters"]["rate"],
                         (20+21)/(30+31)*30.5)
        self.assertEqual(a.warehouse["stat_key"],"points")
        self.assertFalse(a.warehouse["research_only"] is False)
        validate_record("ForecastSnapshot",a.forecast)

    def test_eligible_unverified_stays_abstained(self):
        self.features["participation_probability"]=None
        self.features["legal_eligibility"]="UNVERIFIED"
        self.refresh_feature()
        a=self.run_forecast()
        self.assertEqual(a.status,"RESEARCH_DRY_RUN",a.reason)
        self.assertFalse(a.forecast["eligible"])
        self.assertIn("PARTICIPATION_UNRESOLVED",a.forecast["abstention_reasons"])
        self.assertEqual(self.run_forecast(pipeline="S_PLUS_O").status,
                         "PARTICIPATION_UNRESOLVED")

    def test_opportunity_mixture_and_DNP_not_official_zero(self):
        self.features["participation_probability"]=.5
        self.refresh_feature()
        a=self.run_forecast(pipeline="S_PLUS_O")
        self.assertEqual(a.status,"RESEARCH_DRY_RUN",a.reason)
        self.assertEqual(a.forecast["distribution"]["kind"],"discrete")
        self.assertGreater(dict(a.forecast["distribution"]["masses"])[0],.5)
        self.assertTrue(a.forecast["uncertainty"]["history"]["nonparticipation_void_caveat"])

    def test_corrupted_source_rejected(self):
        (self.root/"sources"/"source.txt").write_bytes(b"MUTATED")
        a=self.run_forecast()
        self.assertEqual(a.status,"SOURCE_UNCERTIFIED")
        self.assertIsNone(a.forecast)

    def test_missing_model_and_wrong_commit(self):
        self.assertEqual(self.run_forecast(code_commit="b"*40).status,"MODEL_NOT_READY")
        (self.root/"models"/"model.json").unlink()
        self.assertEqual(self.run_forecast().status,"MODEL_NOT_READY")

    def test_no_future_or_actual_minutes(self):
        self.features["prior_player_history"][1]["game_date"]="2026-11-22"
        self.refresh_feature()
        self.assertEqual(self.run_forecast().status,"SOURCE_STALE")
        self.features["actual_minutes"]=42
        # P0 rejects forbidden feature keys even when hash is resealed.
        with self.assertRaises(ValueError):
            self.refresh_feature()

    def test_target_game_label_not_allowed(self):
        self.features["prior_player_history"][0]["game_id"]="espn:game:target"
        self.refresh_feature()
        self.assertEqual(self.run_forecast().status,"IDENTITY_UNVERIFIED")

    def test_post_event_freeze_and_training_cutoff(self):
        self.assertEqual(self.run_forecast(forecast_at=START).status,"MISSED_FREEZE")
        self.model_payload["training_cutoff_at"]="2026-11-21T21:00:00Z"
        self.refresh_model()
        self.assertEqual(self.run_forecast().status,"MODEL_NOT_READY")

    def test_j_shared_scenario_complete_game(self):
        a=self.run_forecast(pipeline="S_O_J",n_scenarios=25)
        self.assertEqual(a.status,"RESEARCH_DRY_RUN",a.reason)
        self.assertEqual(a.forecast["distribution"]["kind"],"discrete")
        self.assertEqual(a.warehouse["scenario_sha256"],a.forecast["uncertainty"]["scenario_sha256"])
        self.assertAlmostEqual(sum(p for _,p in a.forecast["distribution"]["masses"]),1.,12)

    def test_J_blocks_incomplete_P1_subset(self):
        self.features.pop("joint_game")
        self.refresh_feature()
        self.assertEqual(self.run_forecast(pipeline="S_O_J").status,"MODEL_NOT_READY")

    def test_frozen_writer_calls_P0_only_after_admission(self):
        with patch("research.nba_p3_frozen.engine.append_immutable",return_value={"status":"APPENDED"}) as writer:
            a=self.run_forecast(persist=True)
            self.assertEqual(a.status,"FORECAST_FROZEN",a.reason)
            writer.assert_called_once()
            self.assertEqual(writer.call_args.args[1],"ForecastSnapshot")
        (self.root/"sources"/"source.txt").write_bytes(b"BAD")
        with patch("research.nba_p3_frozen.engine.append_immutable") as writer:
            self.assertEqual(self.run_forecast(persist=True).status,"SOURCE_UNCERTIFIED")
            writer.assert_not_called()


    def test_s1_s2_finite_complete_likelihoods(self):
        for family in ("S1","S2"):
            self.model_payload["family"]=family
            self.refresh_model()
            a=self.run_forecast()
            self.assertEqual(a.status,"RESEARCH_DRY_RUN",a.reason)
            self.assertEqual(a.forecast["distribution"]["kind"],"nb2")
            d=a.forecast["distribution"]["parameters"]
            self.assertGreater(d["mean"],0)
            self.assertGreater(d["shape"],0)
            self.assertAlmostEqual(a.warehouse["moments"]["p_zero"],
                (d["shape"]/(d["shape"]+d["mean"]))**d["shape"],9)

    def test_traded_player_history_is_not_invalid_identity(self):
        self.features["prior_player_history"][0]["team_id"]="espn:team:prior"
        self.refresh_feature()
        self.assertEqual(self.run_forecast().status,"RESEARCH_DRY_RUN")

    def test_historical_dnp_not_scored_as_zero(self):
        prior=self.features["prior_player_history"][0]
        prior["participation"]="dnp"
        prior["minutes"]=None
        prior["stats"]={}
        self.refresh_feature()
        self.assertEqual(self.run_forecast().status,"INSUFFICIENT_HISTORY")

    def test_write_once_synthetic_model_artifact(self):
        obj=create_research_model(self.model_payload,source_root=self.root,
             model_code_sha=CODE,created_at="2026-11-21T19:00:00Z")
        obj2=create_research_model(self.model_payload,source_root=self.root,
             model_code_sha=CODE,created_at="2026-11-21T19:00:00Z")
        self.assertEqual(obj["record"]["artifact_sha256"],
                         obj2["record"]["artifact_sha256"])
        self.assertIsNone(obj["persisted"])
        p=self.root/obj["record"]["artifact_path"]
        p.write_bytes(b"CORRUPTED AFTER FROZEN")
        with self.assertRaises(ForecastBlocked):
            create_research_model(self.model_payload,source_root=self.root,
                model_code_sha=CODE,created_at="2026-11-21T19:00:00Z")

    def test_rng_reproduction_and_full_game_physics(self):
        a=simulate(self.game,self.model_payload,seed=25,n=10,variant="J2")
        b=simulate(self.game,self.model_payload,seed=25,n=10,variant="J2")
        self.assertEqual(a["scenario_sha256"],b["scenario_sha256"])
        for scenario in a["draws"]:
            for team in self.game["teams"]:
                horizon=48+5*scenario["overtime_periods"]
                by=scenario["minutes"][team]
                self.assertAlmostEqual(sum(by.values()),5*horizon,5)
                self.assertTrue(all(0 <= x <= horizon for x in by.values()))
                self.assertAlmostEqual(sum(s["duration"] for s in scenario["lineup_segments"][team]),horizon,5)
                self.assertTrue(all(len(s["players"])==5 for s in scenario["lineup_segments"][team]))
            for c in scenario["players"].values():
                self.assertEqual(c["points"],2*c["two_made"]+3*c["threes"]+c["ft_made"])
                self.assertLessEqual(c["threes"],c["three_attempts"])
            self.assertEqual(sum(c["rebounds"] for c in scenario["players"].values()),
                             sum(scenario["missed_field_goals"].values()))

    def test_mc_budget_and_no_independent_game_multiplier(self):
        self.assertRaises(ForecastBlocked,simulate,self.game,self.model_payload,seed=1,n=20001)
        a=simulate(self.game,self.model_payload,seed=11,n=40)
        self.assertEqual(a["n"],40)
        self.assertEqual(len(a["draws"]),40)


class FitTests(unittest.TestCase):
    def test_fit_cutoff_and_rollback(self):
        history=[{"event_id":"a","player_id":"p","team_id":"t","stat":"points",
                 "count":7,"minutes":20,"event_start_at":"2026-11-10T01:00:00Z",
                 "outcome_available_at":"2026-11-11T01:00:00Z","source_sha256":"a"*64}]
        p=fit_research_parameters(history,cutoff_at=CUTOFF,family="S1",
             model_id="nba-p3/test",model_version="v2",
             training_reference_sha256=TRAIN)
        self.assertEqual(p["update_policy"],"PERIODIC_FULL_REFIT_ONLY")
        history[0]["outcome_available_at"]="2026-11-22T01:00:00Z"
        with self.assertRaises(ForecastBlocked):
            fit_research_parameters(history,cutoff_at=CUTOFF,family="S1",
                 model_id="nba-p3/test",model_version="v3",
                 training_reference_sha256=TRAIN)
        versions=[{"model_id":"a","model_version":"v1","artifact_sha256":"1"*64},
                  {"model_id":"a","model_version":"v2","artifact_sha256":"2"*64}]
        self.assertEqual(previous_version(versions,"a","v2")["model_version"],"v1")
        self.assertEqual(versions[-1]["model_version"],"v2")


if __name__=="__main__":
    unittest.main()
