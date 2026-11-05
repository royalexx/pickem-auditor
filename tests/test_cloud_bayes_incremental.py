"""Deterministic offline guards for the cloud-only incremental Bayesian layer."""
import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import cloud_bayes_incremental as cb
import population_history as hist

DAY="2026-11-05"
DATE="2026-11-06"
def observation(day=DAY, count=3, pid="8480001"):
    return hist.make(sport="NHL",stat="shots on goal",game_id=2026020501,
        game_date=day,season="2026",player_id=pid,position="F",team="BOS",
        opponent="MTL",home=True,value=count,workload=20.0,
        workload_unit="minutes",source_url="https://api-web.nhle.com/v1/gamecenter/2026020501/boxscore",
        source_sha256="a"*64)

def original(day=DAY,side="over",line=1.5,at="2026-11-05T18:00:00Z"):
    return {"game_date":day,"run_id":"cloud-1","run_type":"shadow",
            "event_id":"2026020501","event_id_namespace":"nhl",
            "sport":"NHL","stat":"shots on goal","player_id":"8480001",
            "player":"Skater","side":side,"reference_line":line,
            "forecast_at":at,"event_start":"2026-11-05T23:00:00Z"}

def af_doc(forecast=None,model_q=.55):
    orig=original() if forecast is None else forecast
    bayes={k:orig[k] for k in ("game_date","run_id","sport","stat","player_id",
                               "side","reference_line","forecast_at")}
    return {"phase":"afternoon","game_date":DAY,"forecasts":[orig],
            "shadow":{"bayesian_a":[dict(bayes,status="forecast",q_win=model_q,q_push=0,
                     publication_eligible=False)],
                      "bayesian_b":[dict(bayes,status="forecast",q_win=.6,q_push=0,
                     publication_eligible=False)]}}

def mo_doc(sides=None,pop=None):
    results=sides if sides is not None else [dict(original(),
                actual_stat=3,outcome="win",settled_at="2026-11-06T12:00:00Z")]
    return {"phase":"morning","game_date":DAY,
            "settlements":results,"population":[observation()] if pop is None else pop,
            "population_collection_receipt":{"status":"complete","errors":{}}}

class OnlineBayesianTests(unittest.TestCase):
    def test_exact_gamma_poisson_conjugate_update(self):
        state=cb.initial_state()
        r=cb.update_one_day(state,DAY,[],[mo_doc(sides=[])])
        self.assertEqual(r["population_rows"],1)
        k="NHL|shots on goal|2026|8480001"
        self.assertAlmostEqual(state["rate"][k]["alpha"],5.)
        self.assertAlmostEqual(state["rate"][k]["beta"],2/.13+20.)
        self.assertEqual(state["rate"][k]["games"],1)
        self.assertEqual(state["through"],DAY)
        self.assertFalse(state["nuts_posterior_updated"])

    def test_gammapoisson_predictive_probabilities_reconcile(self):
        prior={"alpha":10.0,"beta":30.0}
        over,push=cb.count_probability(prior,exposure=15.,line=2.,side="over")
        under,push2=cb.count_probability(prior,exposure=15.,line=2.,side="under")
        self.assertAlmostEqual(over+under+push,1.,places=10)
        self.assertEqual(push,push2)
        self.assertTrue(0<over<1)

    def test_single_player_stat_no_multiple_lines_or_sides(self):
        original_1=original(side="over",line=1.5)
        original_2=original(side="under",line=2.5)
        morning=mo_doc(sides=[dict(original_1,actual_stat=3,outcome="win",
                                   settled_at="2026-11-06T12:00:00Z"),
                              dict(original_2,actual_stat=3,outcome="loss",
                                   settled_at="2026-11-06T12:00:00Z")],pop=[])
        matches=cb.settled_matches([af_doc(original_1),af_doc(original_2)], [morning],DAY)
        self.assertEqual(len(matches),1)

    def test_logit_grid_update_uses_slate_level_prequential_prediction(self):
        a=cb.initial_state()
        ref=cb.start_calibrator()
        prior_p=cb.predictive_probability(ref,.55)
        cb.update_one_day(a,DAY,[af_doc()],[mo_doc()])
        score=a["daily_metrics"][DAY]["NHL|shots on goal|bayesian_a"]
        self.assertEqual(score["n"],1)
        self.assertAlmostEqual(score["brier_online"],(prior_p-1)**2)
        next_p=cb.predictive_probability(a["calibration"]["NHL|shots on goal|bayesian_a"],.55)
        self.assertGreater(next_p,prior_p)
        self.assertEqual(a["calibration"]["NHL|shots on goal|bayesian_a"]["events"],1)
        self.assertFalse(cb.calibrator_ready(a["calibration"]["NHL|shots on goal|bayesian_a"]))

    def test_snapshot_freeze_rejects_same_day_future_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"data/prop_snapshots.jsonl"
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps(original())+"\n")
            state=cb.initial_state()
            state["through"]=DAY
            with self.assertRaisesRegex(ValueError,"FUTURE_GAME_RESULTS"):
                cb.forecast_sidecar(root=root,date_text=DAY,state=state,
                                    out=root/"online.jsonl")

    def test_source_failure_must_not_advance_state(self):
        state=cb.initial_state()
        invalid=mo_doc()
        invalid["population_collection_receipt"]["status"]="partial_source_failure"
        with self.assertRaisesRegex(ValueError,"SOURCES_INCOMPLETE"):
            cb.update_one_day(state,DAY,[af_doc()],[invalid])
        self.assertIsNone(state["through"])
        self.assertEqual(state["counts"]["population_events"],0)

    def test_replay_same_as_incremental_updates(self):
        first=cb.initial_state()
        afternoon=af_doc()
        morning=mo_doc()
        cb.update_one_day(first,DAY,[afternoon],[morning])
        replay,stages=cb.rebuild([(afternoon,"f1"),(morning,"m1")],through=DAY)
        self.assertEqual(cb.canonical(first),cb.canonical(replay))
        self.assertEqual(len(stages),1)
        self.assertEqual(cb.pack(first),cb.pack(replay))
        self.assertEqual(cb.unpack(cb.pack(first)),first)

    def test_not_promoted_and_monitoring_uses_only_past_scores(self):
        state=cb.initial_state()
        cb.update_one_day(state,DAY,[af_doc()],[mo_doc()])
        report=cb.monitoring(state)
        self.assertFalse(report["publication_eligible"])
        scope=report["markets"]["NHL|shots on goal|bayesian_a"]
        self.assertEqual(scope["paired_events"],1)
        self.assertFalse(scope["research_qualified"])
        self.assertFalse(scope["automatic_production_approval"])

    def test_immutable_remote_state_put_and_no_update_existing(self):
        state=cb.initial_state()
        state["through"]=DAY
        records=[]
        def fake_api(route,**args):
            records.append((route,args))
            return {"commit":{"sha":"test_sha"}}
        with patch.object(cb,"tree",return_value=[]),patch.object(cb.pool,"api",side_effect=fake_api):
            info=cb.save_state(state,token="dummy")
        self.assertTrue(info["path"].startswith(cb.PREFIX+DAY+"-"))
        self.assertEqual(records[0][1]["method"],"PUT")
        self.assertEqual(records[0][1]["payload"]["branch"],cb.BRANCH)

if __name__=="__main__":
    unittest.main()
