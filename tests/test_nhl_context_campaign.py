"""Campaign planning, temporal cohorts, raw reconciliation and resume safety."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nhl_context_campaign as campaign
import nhl_context_data as data
import nhl_context_features as features
import nhl_context_train as life
from nhl_context_fixture import games,box

ROOT=Path(__file__).resolve().parents[1]


def config():
    result=life.load_json(ROOT/"config/nhl_context_pilot.json")
    result.update(train_from="2023-10-01T00:00:00Z",cutoff="2025-09-01T00:00:00Z",
                  until="2025-11-01T00:00:00Z",pilot_games=20,restore_history=False)
    return result


def source_history():
    rows=[]
    for year in (2023,2024,2025):
        for bundle in games(30):
            for g in bundle["goalies"]:
                rows.append({"game_id":str(year)+g["game_id"][4:],"game_date":str(year)+g["game_date"][4:],
                             "season":str(year),"team":g["team"],"opponent":g["opponent"]})
    return rows


class Plans(unittest.TestCase):
    def test_holdout_excludes_outcomes_unavailable_at_endpoint(self):
        rows=[{"game_id": "a", "player_id": "1", "start_time": "2025-10-01T23:00:00Z",
               "target_available_at": "2025-10-02T11:00:00Z"}]
        eligible, unavailable=life.holdout_rows(rows, cutoff="2025-09-01T00:00:00Z",
                                               until="2025-10-02T11:00:00Z")
        self.assertEqual(eligible, [])
        self.assertEqual(unavailable[0]["reason"], "target_not_available_by_holdout_end")
        eligible, unavailable=life.holdout_rows(rows, cutoff="2025-09-01T00:00:00Z",
                                               until="2025-10-02T11:00:01Z")
        self.assertEqual(eligible, rows)
        self.assertEqual(unavailable, [])

    def test_pilot_keeps_two_training_seasons_for_unseen_season_holdout(self):
        report=campaign.collection_plan(source_history(),config())
        self.assertEqual(len(report["training_game_ids"]),20)
        self.assertEqual(report["training_seasons"],["2023","2024"])
        self.assertTrue(report["context_only_game_ids"])
        self.assertEqual(len(report["holdout_game_ids"]),60)
        self.assertFalse(report["schedule_completeness_verified"])

    def test_selection_does_not_depend_on_future_target_magnitudes(self):
        rows=source_history()
        original=campaign.collection_plan(rows,config())
        changed=[{**r,"value":9999} for r in rows]
        self.assertEqual(original,campaign.collection_plan(changed,config()))

    def test_cold_start_is_a_source_preflight_error(self):
        c=config();c["train_from"]="2023-10-01T00:00:00Z";c["cutoff"]="2023-10-03T00:00:00Z"
        c["until"]="2023-11-01T00:00:00Z";c["pilot_games"]=0
        with self.assertRaisesRegex(ValueError,"warmup"):
            campaign.collection_plan(source_history(),c)

    def test_single_training_season_cannot_predict_unseen_season(self):
        rows=[r for r in source_history() if r["season"]!="2023"]
        with self.assertRaisesRegex(ValueError,"multiseason"):
            campaign.collection_plan(rows,config())

    def test_unknown_or_boolean_budget_rejected(self):
        c=config();c["draws"]=True
        with self.assertRaises(ValueError):campaign.validate_config(c)
        c=config();c["drwas"]=c.pop("draws")
        with self.assertRaises(ValueError):campaign.validate_config(c)

    def test_blocks_require_attempts(self):
        c=config();c["market"]="blocks"
        with self.assertRaisesRegex(ValueError,"attempt_collection"):campaign.validate_config(c)

    def test_pilot_cohort_is_deterministic_under_row_reordering(self):
        rows=[{**r,"start_time":r["game_date"]+"T00:00:00Z"} for r in source_history() if r["season"]!="2025"]
        a={r["game_id"] for r in features.pilot_cohort(rows,20)}
        b={r["game_id"] for r in features.pilot_cohort(list(reversed(rows)),20)}
        self.assertEqual(a,b)
        self.assertEqual(len(a),20)


class RawSource(unittest.TestCase):
    def test_consistent_but_forged_normalized_counts_fail_raw_replay(self):
        raw=box()
        b=data.normalize(raw,observed_at="2023-10-02T04:00:00Z")
        with tempfile.TemporaryDirectory() as root:
            data.archive_source(root,raw)
            self.assertTrue(data.verify_bundle_source(root,b))
            b["skaters"][0]["hits"]+=1;b["teams"][0]["hits"]+=1
            data.validate_bundle(b)  # Cross-field checks alone cannot detect it.
            with self.assertRaisesRegex(ValueError,"archived_source"):data.verify_bundle_source(root,b)

    def test_one_season_future_forecast_fails_before_sampling(self):
        current=games(15)
        future=copy.deepcopy(current[-1])
        for record in [future]+future["teams"]+future["skaters"]+future["goalies"]:
            record.update(game_id="2024020900",season="2024",game_date="2024-10-01",start_time="2024-10-01T23:00:00+00:00")
        future["source"]["observed_at"]="2024-10-02T04:00:00Z"
        future["source"]["url"]=data.BASE+"/gamecenter/2024020900/boxscore"
        future["play_by_play_source"]["url"]=data.BASE+"/gamecenter/2024020900/play-by-play"
        with tempfile.TemporaryDirectory() as root:
            for b in current+[future]:data.save_bundle(root,b)
            with self.assertRaisesRegex(ValueError,"two_training_seasons_before_sampling"):
                life.freeze(root,train_from="2023-10-01T00:00:00Z",cutoff="2024-09-01T00:00:00Z",
                    market="saves",feature_set="context",policy="recorded",output=Path(root)/"fit",min_rows=10)


class Resuming(unittest.TestCase):
    def test_completed_step_is_verified_not_reexecuted(self):
        with tempfile.TemporaryDirectory() as root:
            c=campaign.Campaign(ROOT,root,config());out=Path(root)/"output.json";called=[]
            def action():called.append(1);life.write_json(out,{"result":1})
            c.step("fit",action,[out]);c.step("fit",action,[out])
            self.assertEqual(len(called),1)
            life.write_json(out,{"result":2})
            with self.assertRaisesRegex(ValueError,"output_changed"):c.step("fit",action,[out])

    def test_modified_config_cannot_resume_existing_campaign(self):
        with tempfile.TemporaryDirectory() as root:
            campaign.Campaign(ROOT,root,config())
            changed=config();changed["draws"]+=100
            with self.assertRaisesRegex(ValueError,"choose_new_run_directory"):campaign.Campaign(ROOT,root,changed)

    def test_exception_is_recorded_before_propagation(self):
        with tempfile.TemporaryDirectory() as root:
            c=campaign.Campaign(ROOT,root,config())
            def fail():raise RuntimeError("source_timeout")
            with self.assertRaises(RuntimeError):c.step("collect",fail,[])
            state=life.load_json(Path(root)/"status.json")
            self.assertEqual(state["steps"]["collect"]["status"],"failed")

    def test_os_lock_prevents_duplicate_campaign_and_releases(self):
        with tempfile.TemporaryDirectory() as root:
            with campaign.campaign_lock(root):
                with self.assertRaisesRegex(RuntimeError,"already_running"):
                    with campaign.campaign_lock(root):pass
            with campaign.campaign_lock(root):pass


if __name__=="__main__":unittest.main()
