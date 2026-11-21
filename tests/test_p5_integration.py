"""P5 additional independent official, C-family and full lifecycle tests.

All source records, quote terms and game outcomes in this file are explicitly
SYNTHETIC and must not count as authentic prospective evidence.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import math
import tempfile
import unittest

from v2.p0_integrity.contracts import sha256
from research.p5_daily.scoring import score_count, digest, ScoreError
from research.p5_daily.complete_pipelines import (
    verify_complete_pipeline_evidence,matched_pipeline_rows,
    fit_chronological_weights,mix_complete_pipelines,resolve_policy,
)
from research.p5_daily.official_adapters import (
    make_p0_official_final,persist_admitted_official_bundle,OfficialAdapterError,
)
from research.p5_daily.registry import (
    admit_training_observation,register_model,select_for_forecast,
    read_transitions,rollback_model,latest_training_observations,
)
from research.p5_daily.workflow import (
    settle,execute_model_update,eligible_training_row,
)
from research.p5_daily.warehouse import scorecard
from test_p5_daily_staged import Fixture, CODE, SETTLED, LATER, START, AVAILABLE

def row(event, date, pipe, stat="points", actual=1, original=True):
    at=date+"T19:00:00Z"
    trained=(datetime.fromisoformat(date+"T00:00:00+00:00")-
             timedelta(days=2)).isoformat().replace("+00:00","Z")
    return {"sport":"NBA","event_id":event,"player_id":"PLAYER1",
            "stat_key":stat,"period":"full",
            "input_freeze_at":date+"T17:00:00Z",
            "forecast_at":date+"T17:30:00Z","event_start_at":at,
            "training_cutoff_at":trained,
            "official_available_at":(datetime.fromisoformat(at.replace("Z","+00:00"))+
                    timedelta(hours=3)).isoformat().replace("+00:00","Z"),
            "original_verified":original,"outcome_verified":True,
            "complete_pipeline_id":pipe,"pipeline_id":pipe,
            "actual":actual,"distribution":{"kind":"discrete",
                        "masses":[[0,.25],[1,.75]]}}

class PipelineTests(unittest.TestCase):
    def test_no_s_o_j_independent_votes(self):
        a=row("E","2026-11-20","S_ONLY")
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([dict(a,pipeline_id="S",complete_pipeline_id="S")])
        with self.assertRaises(ScoreError):
            resolve_policy(policy="W4",eligible_names=["S_ONLY"])
    def test_matched_only_and_distinct_pipeline(self):
        a=row("E","2026-11-20","S_ONLY")
        b=row("E","2026-11-20","S_PLUS_O")
        self.assertEqual(len(matched_pipeline_rows([a,b],["S_ONLY","S_PLUS_O"])),1)
        self.assertEqual(len(matched_pipeline_rows([a],["S_ONLY","S_PLUS_O"])),0)
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([a,dict(a)])
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([a,dict(b,actual=2)])
    def test_original_and_timing_required(self):
        a=row("E","2026-11-20","S_ONLY")
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([dict(a,original_verified=False)])
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([dict(a,training_cutoff_at="2026-11-21T00:00:00Z")])
    def test_w0_w1_fallback_and_w4_stop(self):
        self.assertEqual(resolve_policy(policy="W0",eligible_names=["S_ONLY"]),{"S_ONLY":1.})
        w=resolve_policy(policy="W1",eligible_names=["S_ONLY","S_PLUS_O"])
        self.assertEqual(w,{"S_ONLY":.5,"S_PLUS_O":.5})
        self.assertEqual(resolve_policy(policy="W2",eligible_names=["S_ONLY","S_PLUS_O"]),
                         {"S_ONLY":1.})
    def test_distribution_mixture_not_component_mean(self):
        a=row("E","2026-11-20","S_ONLY")
        b=row("E","2026-11-20","S_PLUS_O")
        b["distribution"]={"kind":"discrete","masses":[[0,.75],[1,.25]]}
        d=mix_complete_pipelines({"S_ONLY":a,"S_PLUS_O":b},
                           {"S_ONLY":.5,"S_PLUS_O":.5})["distribution"]
        self.assertAlmostEqual(d["masses"][0][1],.5)
        self.assertAlmostEqual(d["masses"][1][1],.5)
    def test_40_dates_gate_and_future_label_exclusion(self):
        rows=[]
        for i in range(39):
            dt=(datetime(2026,9,1,tzinfo=timezone.utc)+timedelta(days=i)).date().isoformat()
            for pipe in ("S_ONLY","S_PLUS_O"):
                rows.append(row(f"G{i}",dt,pipe))
        blocked=fit_chronological_weights(rows,policy="W2",
                     cutoff_at="2026-11-20T06:00:00Z",
                     names=["S_ONLY","S_PLUS_O"])
        self.assertEqual(blocked["status"],"INSUFFICIENT_CHRONOLOGICAL_EVIDENCE")
        dt=(datetime(2026,9,1,tzinfo=timezone.utc)+timedelta(days=39)).date().isoformat()
        for pipe in ("S_ONLY","S_PLUS_O"):
            rows.append(row("G39",dt,pipe))
        trained=fit_chronological_weights(rows,policy="W2",
                     cutoff_at="2026-11-20T06:00:00Z",
                     names=["S_ONLY","S_PLUS_O"],max_iter=10)
        self.assertEqual(trained["n_distinct_dates"],40)
        self.assertEqual(trained["n_distinct_games"],40)
        self.assertAlmostEqual(sum(trained["weights"].values()),1.)
        self.assertEqual(trained["independent_holdout_approval"],False)
        blocked_after=fit_chronological_weights(rows,policy="W2",
                     cutoff_at="2026-09-01T01:00:00Z",
                     names=["S_ONLY","S_PLUS_O"])
        self.assertEqual(blocked_after["status"],"INSUFFICIENT_CHRONOLOGICAL_EVIDENCE")
    def test_repeated_lines_not_extra_games(self):
        x=row("E","2026-11-20","S_ONLY")
        y=row("E","2026-11-20","S_PLUS_O")
        with self.assertRaises(ScoreError):
            verify_complete_pipeline_evidence([x,x,y])

class OfficialAdaptersTests(unittest.TestCase):
    def test_nhl_final_played_zero_and_missing_unknown(self):
        fixture={"id":2026020361,"gameState":"OFF",
           "homeTeam":{"abbrev":"NYR"},"awayTeam":{"abbrev":"BOS"},
           "limitedScoring":False,
           "playerByGameStats":{"homeTeam":{"forwards":[
              {"playerId":123,"sog":0,"toi":"12:34"}],"defense":[]},
              "awayTeam":{"forwards":[{"playerId":456,"sog":2,"toi":"11:11"}],
                                "defense":[]}}}
        raw=json.dumps(fixture).encode()
        result=make_p0_official_final(raw=raw,sport="NHL",
                 event_id="CANONICAL_E",official_game_id="2026020361",
                 team_id="NYR",opponent_id="BOS",
                 expected_player_ids=["123","999"],event_start_at=START,
                 official_first_observed_at=SETTLED,
                 original_archive_path="test_synthetic/final.json")
        self.assertEqual(len(result["outcome_records"]),1)
        self.assertEqual(result["outcome_records"][0]["actual_value"],0)
        self.assertEqual(result["outcome_records"][0]["participation"],"PLAYED")
        self.assertEqual(len(result["unresolved_players"]),1)
        self.assertEqual(result["source_receipt"]["source_sha256"],
                         hashlib.sha256(raw).hexdigest())
        with self.assertRaises(OfficialAdapterError):
            make_p0_official_final(raw=raw,sport="NHL",
                 event_id="E",official_game_id="WRONG",team_id="NYR",
                 opponent_id="BOS",expected_player_ids=["123"],
                 event_start_at=START,official_first_observed_at=SETTLED,
                 original_archive_path="test_synthetic/final.json")
    def test_nba_final_made_threes_and_same_box_combos(self):
        labels=["MIN","PTS","REB","AST","3PT"]
        def group(team,pid,stats):
            return {"team":{"abbreviation":team},"statistics":[
                 {"labels":labels,"athletes":[{"athlete":{"id":pid},
                            "didNotPlay":False,"stats":stats}]}]}
        box={"header":{"competitions":[{"id":"401",
                "status":{"type":{"name":"STATUS_FINAL","completed":True}},
                "competitors":[{"team":{"abbreviation":"BOS"}},
                               {"team":{"abbreviation":"NYK"}}]}]},
             "boxscore":{"players":[group("BOS","123",["25:11","20","5","4","2-5"]),
                       group("NYK","456",["21:06","8","2","1","0-1"])]}}
        result=make_p0_official_final(raw=json.dumps(box).encode(),
                sport="NBA",event_id="E",official_game_id="401",
                team_id="BOS",opponent_id="NYK",expected_player_ids=["123"],
                event_start_at=START,official_first_observed_at=SETTLED,
                original_archive_path="test_synthetic/nba.json")
        observed={o["stat_key"]:o["actual_value"] for o in result["outcome_records"]}
        self.assertEqual(observed,{"points":20,"rebounds":5,"assists":4,
                       "threes":2,"pr":25,"pa":24,"ra":9,"pra":29})
        self.assertEqual(result["player_games_counted"],1)
    def test_nba_not_final_block(self):
        box={"header":{"competitions":[{"id":"401",
             "status":{"type":{"name":"STATUS_IN_PROGRESS","completed":False}},
             "competitors":[{"team":{"abbreviation":"BOS"}},
                            {"team":{"abbreviation":"NYK"}}]}]}}
        with self.assertRaises(Exception):
            make_p0_official_final(raw=json.dumps(box).encode(),
                sport="NBA",event_id="E",official_game_id="401",
                team_id="BOS",opponent_id="NYK",expected_player_ids=["123"],
                event_start_at=START,official_first_observed_at=SETTLED,
                original_archive_path="test_synthetic/nba.json")

class ChronologicalCorrectionTests(unittest.TestCase):
    def test_append_only_correction_asof_training_dedup(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            old={"sport":"NHL","event_id":"E","player_id":"P",
                 "team_id":"T","stat_key":"shots on goal",
                 "official_value":1,"participation":"PLAYED",
                 "official_source_sha256":"a"*64,
                 "official_result_available_at":"2026-11-20T23:00:00Z",
                 "event_start_at":START,"training_admitted":True,
                 "official_outcome_id":"OFFICIAL-v1",
                 "exposure":{"toi_minutes_verified":15.0}}
            new=dict(old,official_value=2,official_source_sha256="b"*64,
                 official_result_available_at="2026-11-21T17:00:00Z",
                 official_outcome_id="OFFICIAL-v2")
            admit_training_observation(root,old,effective_cutoff=LATER)
            admit_training_observation(root,new,effective_cutoff=LATER)
            before=latest_training_observations(root,cutoff_at=SETTLED)
            after=latest_training_observations(root,cutoff_at=LATER)
            self.assertEqual(len(before),1)
            self.assertEqual(before[0]["official_value"],1)
            self.assertEqual(len(after),1)
            self.assertEqual(after[0]["official_value"],2)

class SyntheticLifecycle(unittest.TestCase):
    def test_pregame_to_settlement_to_new_model_and_next_version(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            original=Fixture(root/"source",sport="NHL")
            vault=root/"p5";vault.mkdir()
            raw_forecast_sha=sha256(original.frozen["forecast"])
            settled=settle(original.frozen,original.official,
                 source_root=original.root,receipt_root=vault,
                 run_at=SETTLED,evidence_type="synthetic_fixture")
            self.assertEqual(settled["statistical_status"],"SETTLED")
            self.assertEqual(sha256(original.frozen["forecast"]),raw_forecast_sha)
            self.assertEqual(settled["statistical_score"]["actual"],0)
            self.assertEqual(scorecard([settled])[0]["n_distinct_games"],1)
            # Synthetic test admission under ephemeral root only; not a real
            # P0 officially admitted observation or live model update receipt.
            training={"sport":"NHL","event_id":"E1","player_id":"P1",
                 "team_id":"T1","stat_key":"shots on goal",
                 "official_value":0,"participation":"PLAYED",
                 "official_source_sha256":original.official["outcome"]["official_source_sha256"],
                 "official_result_available_at":AVAILABLE,
                 "event_start_at":START,"training_admitted":True,
                 "official_outcome_id":"O1","exposure":{"toi_minutes":15.0}}
            admit_training_observation(vault,training,effective_cutoff=SETTLED)
            initial=register_model(vault,model_id="SYNTH_NHL",
                family="NHL_GAMMA_ADAPTIVE",pipeline_id="GAMMA_ADAPTIVE",
                sport="NHL",state={"alpha":2.0,"beta":10.0},
                parent_version=None,training_rows=[training],
                cutoff_at=SETTLED,created_at=SETTLED,
                code_commit=CODE,update_mode="INCREMENTAL_UPDATE",
                seed=9,diagnostics={},passed_validation=True)
            next_obs=dict(training,event_id="E2",official_outcome_id="O2",
               official_value=2,event_start_at="2026-11-21T09:00:00Z",
               official_result_available_at="2026-11-21T12:00:00Z")
            admit_training_observation(vault,next_obs,effective_cutoff=LATER)
            def update(rows,cutoff):
                return {"alpha":2.0+rows[-1]["official_value"],
                        "beta":10.0+rows[-1]["exposure"]["toi_minutes"]}
            def validate(state,rows,cutoff):
                return state["alpha"]>0 and state["beta"]>10
            result=execute_model_update(vault,family="NHL_GAMMA_ADAPTIVE",
               model_id="SYNTH_NHL",sport="NHL",pipeline_id="GAMMA_ADAPTIVE",
               state_update="INCREMENTAL_UPDATE",training_rows=[training,next_obs],
               cutoff_at=LATER,created_at=LATER,code_commit=CODE,seed=9,
               diagnostics={},previous_version=1,
               fit_callback=update,validation_callback=validate)
            self.assertEqual(result["status"],"NEW_RESEARCH_MODEL_ELIGIBLE")
            self.assertEqual(len(read_transitions(vault,"SYNTH_NHL")),2)
            new=select_for_forecast(vault,"SYNTH_NHL",
                    freeze_at="2026-11-22T07:00:00Z",code_commit=CODE)
            self.assertEqual(new["model_version"],2)
            law={"kind":"gamma_poisson","parameters":
                 {"shape":new["state"]["alpha"],"rate":new["state"]["beta"]}}
            self.assertEqual(score_count(law,1,forecast_id="NEXT-F")["crps"],
                             score_count(law,1,forecast_id="NEXT-F")["crps"])
            rollback_model(vault,"SYNTH_NHL",rollback_to=1,
                         at="2026-11-22T08:00:00Z",reason="research_rollback_test")
            restored=select_for_forecast(vault,"SYNTH_NHL",
                          freeze_at="2026-11-22T09:00:00Z")
            self.assertEqual(restored["state"],initial["model"]["state"])
            self.assertEqual(sha256(original.frozen["forecast"]),raw_forecast_sha)
    def test_no_validator_and_no_eligible_rows_not_training(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            r=execute_model_update(root,family="NHL_GAMMA_ADAPTIVE",
               model_id="M",sport="NHL",pipeline_id="GAMMA",
               state_update="INCREMENTAL_UPDATE",training_rows=[{
                 "training_admitted":True,"official_result_available_at":AVAILABLE}],
               cutoff_at=SETTLED,created_at=SETTLED,code_commit=CODE,
               seed=9,diagnostics={},fit_callback=lambda *x:{"alpha":4})
            self.assertEqual(r["reason"],"INDEPENDENT_NUMERICAL_VALIDATOR_NOT_CONFIGURED")

if __name__=="__main__":
    unittest.main()
