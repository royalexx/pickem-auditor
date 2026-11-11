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

def af_doc(forecast=None,model_q=.55,captured_at="2026-11-05T18:05:00Z"):
    orig=original() if forecast is None else forecast
    bayes={k:orig[k] for k in ("game_date","run_id","sport","stat","player_id",
                               "side","reference_line","forecast_at")}
    return {"phase":"afternoon","game_date":DAY,
            "captured_at_utc":captured_at,"forecasts":[orig],
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
        archived_batch=af_doc(original_1)
        archived_batch["forecasts"].append(original_2)
        matches=cb.settled_matches([archived_batch], [morning],DAY)
        self.assertEqual(len(matches),1)

    def test_later_archived_rerun_cannot_change_original_calibration(self):
        first=af_doc(model_q=.55,captured_at="2026-11-05T18:05:00Z")
        later=af_doc(model_q=.95,captured_at="2026-11-05T20:05:00Z")
        later["forecasts"][0]["forecast_at"]="2026-11-05T19:55:00Z"
        matches=cb.settled_matches([later,first],[mo_doc(pop=[])],DAY)
        self.assertEqual(len(matches),1)
        self.assertAlmostEqual(matches[0][1][3]["bayesian_a"],.55)

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
        # Separate, forward-only canonical Over v2: no inherited V1 posterior.
        v2=a["calibration"]["NHL|shots on goal|bayesian_a|canonical_over_v2"]
        self.assertEqual(v2["events"],1)
        self.assertFalse(cb.calibrator_ready(v2))
        self.assertEqual(a["daily_metrics"][DAY][
            "NHL|shots on goal|bayesian_a|canonical_over_v2"]["orientation"],
            "CANONICAL_OVER_ONLY_V2")

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

    def test_historical_bootstrap_reads_pinned_verified_source_and_filters_future(self):
        import gzip
        row=observation(day="2026-11-04")
        later=observation(day="2026-11-06",count=20)
        payload=gzip.compress((json.dumps(row)+"\n"+json.dumps(later)+"\n").encode())
        def fake_api(route,**kw):
            if route=="/git/ref/heads/data/bayesian-history":
                return {"object":{"sha":"a"*40}}
            if route=="/git/trees/"+"a"*40+"?recursive=1":
                return {"tree":[{"type":"blob","sha":"b"*40,
                    "path":"data/bayesian_warehouse/populations/nhl/shots_on_goal/2026.jsonl.gz"}]}
            raise AssertionError(route)
        with patch.object(cb.pool,"api",side_effect=fake_api), \
             patch.object(cb.pool,"read_blob",return_value=payload):
            state=cb.bootstrap_history("test",before=DAY)
        self.assertEqual(state["counts"]["historical_seed_events"],1)
        self.assertEqual(state["rate"]["NHL|shots on goal|2026|8480001"]["games"],1)
        self.assertEqual(state["rate"]["NHL|shots on goal|2026|8480001"]["alpha"],5.)
        self.assertEqual(state["bootstrap_source"]["cutoff_exclusive"],DAY)
        self.assertEqual(state["bootstrap_source"]["historical_commit"],"a"*40)

    def test_weekly_cloud_replay_uses_same_seed_and_prospective_rows(self):
        fixtures=[(af_doc(),"afternoon"),(mo_doc(),"morning")]
        with patch.object(cb,"current_state",return_value=(cb.initial_state(),None)), \
             patch.object(cb,"bootstrap_history",return_value=cb.initial_state()), \
             patch.object(cb.pool,"iter_remote_docs",side_effect=[fixtures,fixtures]), \
             patch.object(cb,"save_state",return_value={"status":"published","path":"test"}):
            receipt=cb.run_update(token="test",as_of=DATE,weekly_rebuild=True)
        self.assertTrue(receipt["weekly_full_replay_checked"])
        self.assertEqual(receipt["through"],DAY)
        self.assertEqual(receipt["population_events"],1)
        self.assertFalse(receipt["approved_for_production"])

    def test_afternoon_shadow_uses_only_prior_state_and_keeps_origins_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original_forecast=original()
            data=root/"data"
            data.mkdir()
            under_forecast=original(side="under")
            (data/"prop_snapshots.jsonl").write_text(
                json.dumps(original_forecast)+"\n"+json.dumps(under_forecast)+"\n")
            for subdir,q in (("bayesian_shadow",.55),("bayesian_b_shadow",.6)):
                folder=data/subdir
                folder.mkdir()
                entries=[]
                for part,p in ((original_forecast,q),(under_forecast,1-q)):
                    sidecar={k:part[k] for k in (
                        "game_date","run_id","sport","stat","player_id","side",
                        "reference_line","forecast_at")}
                    sidecar.update(status="forecast",q_win=p,q_push=0.,
                                   workload_mean=19.0)
                    entries.append(json.dumps(sidecar))
                (folder/(DAY+".jsonl")).write_text("\n".join(entries)+"\n")
            state=cb.initial_state()
            state["through"]="2026-11-04"
            state["rate"]["NHL|shots on goal|2026|8480001"]={
                "alpha":10.,"beta":70.,"games":7,"historical_seed_games":6,
                "live_games":1}
            cal=cb.start_calibrator()
            cal["events"]=101
            cal["days"]=16
            state["calibration"]["NHL|shots on goal|bayesian_a|canonical_over_v2"]=copy.deepcopy(cal)
            report=cb.forecast_sidecar(root=root,date_text=DAY,state=state,
                                       out=root/"online.jsonl")
            rows=cb.read_jsonl(root/"online.jsonl")
            self.assertEqual(report["rows"],2)
            self.assertEqual(rows[0]["training_data_through"],"2026-11-04")
            self.assertEqual(rows[0]["models"]["bayesian_a_online_calibrated"]["status"],
                             "research_shadow")
            self.assertEqual(rows[0]["models"]["bayesian_a_online_calibrated"]["model_kind"],
                             "canonical_over_v2")
            self.assertAlmostEqual(
                sum(r["models"]["bayesian_a_online_calibrated"]["q_win"] for r in rows),
                1.0,places=8)
            self.assertEqual(
                rows[1]["models"]["bayesian_a_online_calibrated"]["status"],"research_shadow")
            self.assertEqual(rows[0]["models"]["player_rate_gamma_poisson"]["status"],
                             "research_shadow")
            self.assertFalse(rows[0]["publication_eligible"])
            self.assertEqual(
                [json.loads(line) for line in (data/"prop_snapshots.jsonl").read_text().splitlines()],
                [original_forecast,under_forecast])

    def test_legacy_independently_oriented_calibrator_is_not_misused_for_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/"data";data.mkdir()
            left,right=original(),original(side="under")
            (data/"prop_snapshots.jsonl").write_text(
                json.dumps(left)+"\n"+json.dumps(right)+"\n")
            for folder_name,p in (("bayesian_shadow",.55),("bayesian_b_shadow",.6)):
                folder=data/folder_name;folder.mkdir()
                records=[]
                for source,q in ((left,p),(right,1-p)):
                    rec={k:source[k] for k in ("game_date","run_id","sport","stat",
                        "player_id","side","reference_line","forecast_at")}
                    rec.update(status="forecast",q_win=q,q_push=0.,workload_mean=19.0)
                    records.append(json.dumps(rec))
                (folder/(DAY+".jsonl")).write_text("\n".join(records)+"\n")
            state=cb.initial_state()
            state["through"]="2026-11-04"
            old=cb.start_calibrator()
            old["events"]=150;old["days"]=20
            state["calibration"]["NHL|shots on goal|bayesian_a"]=old
            cb.forecast_sidecar(root=root,date_text=DAY,state=state,
                                out=root/"online.jsonl")
            rows=cb.read_jsonl(root/"online.jsonl")
            self.assertTrue(all(r["models"]["bayesian_a_online_calibrated"]["status"]
                                =="unavailable" for r in rows))
            self.assertTrue(all("coherent_over_v2" in
                r["models"]["bayesian_a_online_calibrated"]["reason"] for r in rows))

    def test_over_v2_update_orients_under_selected_observation(self):
        state=cb.initial_state()
        under=original(side="under")
        afternoon=af_doc(under,model_q=.45)
        morning=mo_doc(sides=[dict(under,actual_stat=3,outcome="loss",
                                  settled_at="2026-11-06T12:00:00Z")],pop=[])
        cb.update_one_day(state,DAY,[afternoon],[morning])
        rec=state["calibration"]["NHL|shots on goal|bayesian_a|canonical_over_v2"]
        reference=cb.start_calibrator()
        cb.update_calibration(reference,[(.55,1)])
        self.assertEqual(rec,reference)

if __name__=="__main__":
    unittest.main()
