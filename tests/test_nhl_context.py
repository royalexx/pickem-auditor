"""Context warehouse, leakage, evaluation and freeze integrity regressions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nhl_context_data as data
import nhl_context_features as features
import nhl_context_evaluate as scoring
import nhl_context_train as train
from nhl_context_fixture import games, box


class ContextData(unittest.TestCase):
    def normalized(self, value=None):
        return data.normalize(value or box(), observed_at="2023-10-02T04:00:00Z")

    def test_separate_rows_and_unknown_advanced_metrics(self):
        b=self.normalized()
        self.assertEqual(len(b["teams"]),2)
        self.assertEqual(len(b["goalies"]),2)
        self.assertIsNone(b["teams"][0]["xgf"])
        self.assertIsNone(b["teams"][0]["attempts_for"])
        self.assertEqual(b["goalies"][0]["saves"],3)

    def test_missing_counts_are_not_zero(self):
        b=box();del b["playerByGameStats"]["homeTeam"]["forwards"][0]["hits"]
        with self.assertRaises(KeyError):self.normalized(b)

    def test_goalie_counts_reconcile(self):
        for field,value in (("saves",4),("goalsAgainst",2),("starter",None),("shotsAgainst",7)):
            b=box();b["playerByGameStats"]["homeTeam"]["goalies"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.normalized(b)

    def test_save_string_checks_denominator(self):
        b=box();b["playerByGameStats"]["homeTeam"]["goalies"][0]["saves"]="3/4"
        self.assertEqual(self.normalized(b)["goalies"][0]["saves"],3)
        b["playerByGameStats"]["homeTeam"]["goalies"][0]["saves"]="3/5"
        with self.assertRaises(ValueError):self.normalized(b)

    def test_empty_net_discrepancy_remains_separate(self):
        b=box();g=b["playerByGameStats"]["homeTeam"]["goalies"][0]
        g.update(shotsAgainst=3,saves=2,goalsAgainst=1)
        n=self.normalized(b)
        self.assertEqual(n["teams"][0]["unassigned_shots_against"],1)
        self.assertEqual(n["goalies"][0]["saves"],2)

    def test_no_zero_minute_goalie_appearance(self):
        b=box();b["playerByGameStats"]["homeTeam"]["goalies"].append({"playerId":999,"toi":"00:00","starter":False})
        self.assertEqual(len(self.normalized(b)["goalies"]),2)

    def test_only_completed_regular_season(self):
        for change in ({"id":2023030001},{"gameState":"LIVE"}):
            b=box();b.update(change)
            with self.assertRaises(ValueError):self.normalized(b)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):data.instant("2026-10-30T12:00:00")

    def test_overtime_uses_winning_goal_clock(self):
        b=box();b["periodDescriptor"]={"number":4,"periodType":"OT"}
        with self.assertRaises(ValueError):self.normalized(b)
        p={"id":b["id"],"plays":[{"typeDescKey":"goal","periodDescriptor":{"number":4},"timeInPeriod":"02:30"}]}
        self.assertEqual(data.game_duration(b,p),62.5)
        b["periodDescriptor"]={"number":5,"periodType":"SO"}
        self.assertEqual(data.game_duration(b,p),65)

    def test_repeated_ingestion_idempotent_but_revision_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            b=self.normalized();self.assertTrue(data.save_bundle(root,b))
            b["source"]["observed_at"]="2023-10-03T04:00:00Z"
            self.assertFalse(data.save_bundle(root,b))
            b["teams"][0]["hits"]+=1
            next(r for r in b["skaters"] if r["team"]==b["teams"][0]["team"])["hits"]+=1
            with self.assertRaisesRegex(ValueError,"revision"):data.save_bundle(root,b)
            self.assertEqual(len(data.read_bundles(root)),1)

    def test_bundle_identity_validation(self):
        b=self.normalized();b["goalies"][0]["game_id"]="other"
        with self.assertRaises(ValueError):data.validate_bundle(b)

    def test_collector_resumes_without_refetch(self):
        with tempfile.TemporaryDirectory() as root:
            called=[]
            def fetch(url):called.append(url);return box()
            self.assertEqual(data.collect(root,game_ids=[2023020001],fetcher=fetch)["inserted_games"],1)
            self.assertEqual(data.collect(root,game_ids=[2023020001],fetcher=fetch)["inserted_games"],0)
            self.assertEqual(len(called),1)

    def test_collection_audit_reports_missing_games(self):
        with tempfile.TemporaryDirectory() as root:
            ids=Path(root)/"ids.json";ids.write_text('["2023020001","2023020002"]')
            data.save_bundle(root,self.normalized())
            result=train.audit_collection(root,expected_ids=ids,output=Path(root)/"audit.json")
            self.assertEqual(result["missing_game_ids"],["2023020002"])
            self.assertFalse(result["complete_against_provided_ids"])

    def test_boolean_counts_rejected(self):
        with self.assertRaises(ValueError):data.count(True)

    def test_pregame_snapshot_requires_evidence_and_time(self):
        snap={"game_id":"2023020001","season":"2023","team":"AAA","opponent":"BBB","home":True,
              "start_time":"2023-10-01T23:00:00Z","snapshot_at":"2023-10-01T22:00:00Z",
              "starter_player_id":"200","starter_status":"confirmed","injuries":[],
              "source_url":"https://example.invalid/report","source_sha256":"a"*64}
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(data.save_matchup(root,snap))
            self.assertFalse(data.save_matchup(root,snap))
            snap["snapshot_at"]="2023-10-02T01:00:00Z"
            with self.assertRaisesRegex(ValueError,"not_pregame"):data.save_matchup(root,snap)

    def test_persisted_counts_cannot_be_tampered_with(self):
        b=self.normalized();b["goalies"][0]["saves"]+=1
        with self.assertRaises(ValueError):data.validate_bundle(b)

    def test_pbp_block_team_comes_from_shooter_identity(self):
        b=box()
        p={"id":b["id"],"plays":[]}
        for side in ("homeTeam","awayTeam"):
            p["plays"] += [{"typeDescKey":"shot-on-goal","periodDescriptor":{"number":1},
                            "details":{"eventOwnerTeamId":b[side]["id"]}}]*4
        p["plays"].append({"typeDescKey":"blocked-shot","periodDescriptor":{"number":1},
                           "details":{"shootingPlayerId":100,"blockingPlayerId":101,"eventOwnerTeamId":2}})
        result=data.normalize(b,observed_at="2023-10-02T04:00:00Z",pbp=p)
        self.assertEqual(result["teams"][0]["attempts_for"],5)
        self.assertEqual(result["teams"][1]["attempts_for"],4)
        del p["plays"][-1]["details"]["shootingPlayerId"]
        with self.assertRaisesRegex(ValueError,"unresolved_blocked"):data.normalize(b,observed_at="2023-10-02T04:00:00Z",pbp=p)


class ContextFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundles=games(20)

    def row(self):return self.bundles[22]["goalies"][0]

    def feature(self,bundles=None,**kw):
        row=self.row()
        return features.context(data.HistoryIndex(bundles or self.bundles,policy=kw.pop("policy","recorded")),row,
                                 player_id=row["player_id"],position="G",market="saves",**kw)

    def test_current_and_future_target_mutations_do_not_change_features(self):
        original=self.feature()
        changed=copy.deepcopy(self.bundles)
        for bundle in changed[22:]:
            for row in bundle["goalies"]:
                row["minutes"]*=.9
                if row["saves"]:
                    row["saves"]-=1;row["goals_against"]+=1
            for row in bundle["skaters"]:row["minutes"]*=.9
            bundle["skaters"][0]["hits"]+=10
            next(r for r in bundle["teams"] if r["team"]==bundle["skaters"][0]["team"])["hits"]+=10
        self.assertEqual(original,self.feature(changed))

    def test_availability_blocks_late_source(self):
        changed=copy.deepcopy(self.bundles)
        for b in changed:b["source"]["observed_at"]="2030-01-01T00:00:00Z"
        self.assertEqual(self.feature(changed)["team_games"],0)
        self.assertGreater(self.feature(changed,policy="retrospective_next_day")["team_games"],0)

    def test_history_uses_event_time_not_retrieval_order(self):
        changed=copy.deepcopy(self.bundles)
        changed[0]["source"]["observed_at"]="2023-10-10T12:00:00Z"
        index=data.HistoryIndex(changed)
        rows=index.before("teams","AAA","2023-10-12T23:00:00Z",window=3)
        self.assertEqual([r["start_time"] for r in rows],sorted(r["start_time"] for r in rows))
        self.assertNotIn(changed[0]["game_id"],[r["game_id"] for r in rows])

    def test_starter_only_training(self):
        rows,_=features.examples(self.bundles,market="saves",min_team_games=0)
        self.assertTrue(all(r["starter"] for r in rows))

    def test_unknown_attempts_prevent_blocks_context_fit(self):
        bundles=copy.deepcopy(self.bundles)
        for b in bundles:
            for r in b["teams"]:r["attempts_for"]=None
        rows,omitted=features.examples(bundles,market="blocks")
        self.assertFalse(rows)
        self.assertTrue(any("missing_opportunity_metric" in r["reason"] for r in omitted))

    def test_stat_specific_feature_designs(self):
        for market in features.MARKETS:
            rows,_=features.examples(self.bundles,market=market)
            self.assertTrue(rows,market)
            self.assertEqual(len(rows[0]["features"]["values"]),7)

    def test_no_team_history_uses_fixed_shrinkage_prior(self):
        f=self.feature([self.bundles[22]])
        self.assertEqual(f["values"][3:],[0.,0.,0.,0.])

    def test_xg_requires_model_vintage_and_available_source(self):
        with self.assertRaisesRegex(ValueError,"missing_xg"):features.validate_xg([{}])
        with self.assertRaisesRegex(ValueError,"missing_point_in_time_xg"):
            self.feature(feature_set="xg")

    def test_cutoff_excludes_unfinished_last_game(self):
        rows,_=features.examples(self.bundles,market="saves",min_team_games=0)
        with self.assertRaisesRegex(ValueError,"cutoff_or_future"):
            features.prepare(rows[:2],cutoff="2023-10-02T00:00:00Z",min_rows=1)

    def test_scaler_uses_only_supplied_training_rows(self):
        rows,_=features.examples(self.bundles,market="saves")
        trainrows=rows[:20]
        d=features.prepare(trainrows,cutoff="2024-01-01T00:00:00Z",min_rows=1)
        import numpy as np
        np.testing.assert_allclose(d["center"],np.mean([r["features"]["values"] for r in trainrows],axis=0))

    def test_mismatched_design_feature_set_rejected(self):
        rows,_=features.examples(self.bundles,market="saves")
        with self.assertRaisesRegex(ValueError,"feature_set_or_availability"):
            features.prepare(rows,cutoff="2024-01-01T00:00:00Z",min_rows=1,feature_set="base")

    def test_xg_future_version_cannot_enter_historical_features(self):
        xg=[]
        for b in self.bundles:
            for r in b["teams"]:
                xg.append({"game_id":r["game_id"],"team":r["team"],"provider":"test","model_version":"v1",
                            "model_trained_through":"2029-01-01T00:00:00Z","available_at":b["source"]["observed_at"],
                            "source_url":"https://test.invalid/xg","source_sha256":"a"*64,"xgf":2.,"xga":2.})
        with self.assertRaisesRegex(ValueError,"missing_point_in_time_xg"):
            self.feature(feature_set="xg",xg_rows=xg)

    def test_freeze_hash_detects_changes(self):
        with tempfile.TemporaryDirectory() as root:
            for b in self.bundles:data.save_bundle(root,b)
            folder=Path(root)/"fit"
            r=train.freeze(root,train_from="2023-10-01T00:00:00Z",cutoff="2023-10-20T12:00:00Z",
                           market="saves",feature_set="context",policy="recorded",output=folder,min_rows=10)
            self.assertFalse(r["ranking_allowed"])
            d,_=train.load_design(folder)
            d["center"][0]+=1
            (folder/"design.json").write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"hash_mismatch"):train.load_design(folder)


class Evaluation(unittest.TestCase):
    def records(self):
        return [{"game_id":str(i//2),"player_id":str(i),"market":"saves","line":25.5,"target":i+20,
                 "start_time":"2023-11-01T23:00:00Z","training_cutoff_exclusive":"2023-11-01T12:00:00Z",
                 "q_over":.6,"q_under":.4,"q_push":0.} for i in range(10)]

    def test_exact_pairing_and_cluster_intervals(self):
        a=self.records();b=copy.deepcopy(a)
        result=scoring.paired_comparison(a,b,bootstrap=100)
        self.assertEqual(result["brier_delta_challenger_minus_incumbent"],0)
        self.assertEqual(result["game_cluster_bootstrap_95_interval"],[0.,0.])
        self.assertFalse(result["automatic_promotion"])
        with self.assertRaisesRegex(ValueError,"population_mismatch"):scoring.paired_comparison(a,b[:-1])

    def test_future_trained_comparator_rejected(self):
        a=self.records();b=copy.deepcopy(a);b[0]["training_cutoff_exclusive"]="2024-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"future"):scoring.paired_comparison(a,b)

    def test_pushes_excluded_and_probabilities_renormalized(self):
        rows=self.records()[:2]
        for r in rows:r.update(line=20,q_over=.4,q_under=.4,q_push=.2)
        m=scoring.metrics(rows)
        self.assertEqual(m["pushes"],1)
        self.assertAlmostEqual(m["brier_nonpush"],.25)

    def test_thinning_identity_independent_numerical_sum(self):
        import numpy as np
        from scipy.stats import nbinom,binom
        alpha,mu,save=9.,30.,.91
        shots=np.arange(501)
        for k in (0,15,25,40):
            explicit=(nbinom.pmf(shots,alpha,alpha/(alpha+mu))*binom.pmf(k,shots,save)).sum()
            thinned=nbinom.pmf(k,alpha,alpha/(alpha+mu*save))
            self.assertAlmostEqual(explicit,thinned,places=12)

    def test_diagnostics_do_not_broadcast_unrelated_effect_dimensions(self):
        import numpy as np
        from types import SimpleNamespace
        import nhl_context_model as model
        result=SimpleNamespace(data_vars={"player":np.ones(1000),"team":np.full(200,2.)})
        values=model._diagnostic_values(result)
        self.assertEqual(len(values),1200)
        self.assertEqual(max(values),2.)
        result.to_array=lambda: self.fail("diagnostics must not broadcast Dataset.to_array")
        import joint_population_bayes as population
        import joint_nhl_bayes as nhl
        self.assertEqual(population._to_values(result),values)
        self.assertEqual(nhl._diagnostic_values(result),values)

    def test_incumbent_adapter_preserves_exact_training_population(self):
        import nhl_context_incumbent as incumbent
        bundles=games(8)
        for market in features.MARKETS:
            rows,_=features.examples(bundles,market=market,min_team_games=0)
            converted=incumbent.legacy_rows(rows)
            self.assertEqual(len(converted),len(rows))
            for old,new in zip(converted,rows):
                self.assertEqual((old["game_id"],old["player_id"],old["value"],old["workload"]),
                                 (new["game_id"],new["player_id"],new["target"],new["minutes"]))


if __name__=="__main__":unittest.main()
