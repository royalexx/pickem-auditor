"""Adversarial tests for read-only, paired-contract Phase 4 diagnostics."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_phase4_scorecard as scorecard


def sample():
    rows=[]
    base={"sport":"NFL","event_start":"2026-11-08T18:00:00Z",
          "forecast_at":"2026-11-08T14:00:00Z","team":"CAR","opponent":"DEN",
          "player_id":"GSIS1","player":"Example","stat":"completions",
          "line":21.5,"run_id":"frozenrun","models":{}}
    for side in ("over","under"):
        row={**base,"side":side}
        row["Consensus"] = .6 if side=="over" else .4
        row["Market"] = .55 if side=="over" else .45
        row["Engine_A"] = .62 if side=="over" else .38
        for m in ("Engine_B","Bayesian_A","Bayesian_B","NUTS"):
            row[m]=None
        rows.append(row)
    comp={"schema":"slate-model-comparison-v1",
          "metadata":{"run_id":"frozenrun","code_sha":"frozen-code"},
          "picks":rows}
    settles={"pregame_run":"frozenrun","code_sha":"frozen-code",
             "start_window_utc":"2026-11-08T18:00:00Z",
             "games":[{"status":"final","teams":["CAR","DEN"],"espn_event_id":"123"}],
             "contracts":[{"team":"CAR","opponent":"DEN","player_id_gsis":"GSIS1",
                           "player":"Example","stat":"completions","line":21.5,
                           "pregame_forecast_at":"2026-11-08T14:00:00Z",
                           "espn_game_id":"123","settlement_status":"verified",
                           "actual":27,"winning_side":"over"}]}
    return comp,settles


def archive(folder,comp,settles):
    root=Path(folder)
    for name,data in (("frozen.json",comp),("settlement.json",settles)):
        (root/name).write_text(json.dumps(data))
    receipt={"baseline_policy_verified":True,
             "comparison_sha256":hashlib.sha256((root/"frozen.json").read_bytes()).hexdigest(),
             "settlement_sha256":hashlib.sha256((root/"settlement.json").read_bytes()).hexdigest(),
             "scope":{"contracts":1},
             "settlement":{"verified_contracts":1,"seen_settlement_contracts":1}}
    (root/"pinned.json").write_text(json.dumps(receipt))
    return tuple(root/p for p in ("frozen.json","settlement.json","pinned.json"))


class ScoringContracts(unittest.TestCase):
    def test_one_contract_not_two_complementary_hits(self):
        c=scorecard.chosen({"over":.7,"under":.3,"side_sum":1.},"over")
        s=scorecard.score([c])
        self.assertEqual(s["n"],1)
        self.assertEqual(s["hits"],1)
        self.assertAlmostEqual(s["brier"],.09)
        self.assertAlmostEqual(s["directional_accuracy"],1)

    def test_opposite_sides_still_score_same_outcome(self):
        a=scorecard.chosen(scorecard.source_model(.65,.35),"over")
        b=scorecard.chosen(scorecard.source_model(.40,.60),"over")
        self.assertEqual(a["hit"],1)
        self.assertEqual(b["hit"],0)
        self.assertEqual(scorecard.score([a,b])["actual_over_share"],1)

    def test_market_overlap_is_exact_not_naively_pooled(self):
        a=scorecard.chosen(scorecard.source_model(.6,.4),"over")
        b=scorecard.chosen(scorecard.source_model(.56,.44),"over")
        rows=[{"models":{"Consensus":a,"Market":b}},
              {"models":{"Consensus":a,"Market":None}}]
        matched=scorecard.matched_pairwise(rows,"Consensus","Market")
        self.assertEqual(matched["n"],1)
        self.assertEqual(matched["Consensus"]["n"],1)
        self.assertEqual(matched["Market"]["n"],1)

    def test_tied_side_abstains_from_directional_score(self):
        self.assertIsNone(scorecard.chosen(scorecard.source_model(.5,.5),"under"))

    def test_no_model_training_or_production_promotion(self):
        r={"sport":"NFL","stat":"tackles + assists","date":"2026-11-08",
           "game_id":"123","models":{"Engine_A":scorecard.chosen(scorecard.source_model(.9,.1),"under"),
                                       "Consensus":None}}
        report=scorecard.evaluate([r],[])
        self.assertFalse(report["validated_for_deployment"])
        self.assertFalse(report["production_modified"])
        self.assertFalse(report["retraining_performed"])
        self.assertEqual(report["sample_granularity"],"one_nonpush_contract_not_two_sides")


class FrozenOfficialSources(unittest.TestCase):
    def test_original_sha_and_official_scores_match(self):
        comp,settles=sample()
        with tempfile.TemporaryDirectory() as tmp:
            paths=archive(tmp,comp,settles)
            rows,meta=scorecard.load_nfl_slate(*paths)
            self.assertEqual(meta["settled_contracts"],1)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["models"]["Consensus"]["hit"],1)
            self.assertEqual(rows[0]["models"]["Engine_A"]["hit"],1)

    def test_mutating_original_snapshot_breaks_pinned_receipt(self):
        comp,settles=sample()
        with tempfile.TemporaryDirectory() as tmp:
            paths=archive(tmp,comp,settles)
            comp["picks"][0]["Consensus"]=.999
            Path(paths[0]).write_text(json.dumps(comp))
            with self.assertRaisesRegex(scorecard.AuditError,"receipt_mismatch"):
                scorecard.load_nfl_slate(*paths)

    def test_postkickoff_forecast_is_rejected(self):
        comp,settles=sample()
        comp["picks"][0]["forecast_at"]="2026-11-08T20:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(scorecard.AuditError,"post_kickoff"):
                scorecard.load_nfl_slate(*archive(tmp,comp,settles))

    def test_duplicate_over_side_is_rejected(self):
        comp,settles=sample()
        comp["picks"].append(copy.deepcopy(comp["picks"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(scorecard.AuditError,"duplicate_or_invalid"):
                scorecard.load_nfl_slate(*archive(tmp,comp,settles))

    def test_official_false_outcome_is_rejected(self):
        comp,settles=sample()
        settles["contracts"][0]["winning_side"]="under"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(scorecard.AuditError,"winning_side_mismatch"):
                scorecard.load_nfl_slate(*archive(tmp,comp,settles))

    def test_unsupported_settlement_is_not_inferred_zero(self):
        comp,settles=sample()
        settles["contracts"][0]["settlement_status"]="unverified"
        with tempfile.TemporaryDirectory() as tmp:
            paths=archive(tmp,comp,settles)
            manifest=json.loads(paths[2].read_text())
            manifest["settlement"]["verified_contracts"]=0
            paths[2].write_text(json.dumps(manifest))
            rows,meta=scorecard.load_nfl_slate(*paths)
            self.assertEqual(rows,[])
            self.assertEqual(meta["excluded"]["unverified"],1)


class HistoricalIntegrity(unittest.TestCase):
    def make_history(self,root):
        root=Path(root)
        folder=root/"pickem_runs/2026-11-05/abc"
        folder.mkdir(parents=True)
        csv=folder/"all_four_model_comparisons.csv"
        csv.write_bytes(b"frozen original archived quotes\n")
        source={"schema":"archived_source_only_research_backtest_v1",
                "archives":[{"date":"2026-11-05","archive":str(csv),
                             "sha256":hashlib.sha256(csv.read_bytes()).hexdigest()}],
                "sources":[{"id":"g1","sport":"NFL","date":"2026-11-05",
                            "detail":"Final","start":"2026-11-06T01:15:00Z"}],
                "contracts":[{"status":"settled","game_id":"g1","actual":7,"winner":"over",
                              "day":"2026-11-05","sport":"NFL","team":"BAL","player":"Example",
                              "stat":"targets","line":4.5,
                              "forecast_at":"2026-11-05T20:00:00Z",
                              "models":{"Engine_A":{"over":.7,"under":.3},
                                        "Market":{"over":.6,"under":.4}}}]}
        p=root/"historical.json"
        p.write_text(json.dumps(source))
        return p

    def test_only_original_backtest_rows_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=self.make_history(tmp)
            rows,meta=scorecard.load_historical(f,Path(tmp))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["models"]["Engine_A"]["hit"],1)
            self.assertEqual(meta["settled_contracts"],1)

    def test_archive_hash_mismatch_blocks_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=self.make_history(tmp)
            csv=Path(tmp)/"pickem_runs/2026-11-05/abc/all_four_model_comparisons.csv"
            csv.write_bytes(b"posthoc rewritten archive")
            with self.assertRaisesRegex(scorecard.AuditError,"historical_archive_sha256_mismatch"):
                scorecard.load_historical(f,Path(tmp))

    def test_poststart_archive_record_blocks_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=self.make_history(tmp)
            d=json.loads(f.read_text())
            d["contracts"][0]["forecast_at"]="2026-11-06T02:00:00Z"
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(scorecard.AuditError,"historical_forecast_after_game"):
                scorecard.load_historical(f,Path(tmp))


if __name__=="__main__":
    unittest.main()
