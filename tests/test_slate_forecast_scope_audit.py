"""Make the top-10 a presentation view, not a forecasting input universe."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from slate_forecast_scope_audit import audit, MODEL_NAMES


def snapshot(i, sport="NFL", stat="tackles + assists"):
    return {"game_date":"2026-11-08","run_type":"shadow",
            "sport":sport,"player":f"Player {i}","player_id":str(i),
            "team":"NE","opponent":"BUF","stat":stat,"side":"over",
            "reference_line":4.5+i,"forecast_at":"2026-11-08T12:05:00+00:00",
            "event_start":"2026-11-08T18:00:00+00:00","run_id":"SUNDAY"}


def comparison_row(s):
    names={name:{"status":"forecast","probability":.62,"reason":None}
           for name in MODEL_NAMES}
    names["NUTS"]={"status":"unavailable","probability":None,
                   "reason":"no_strict_posterior"}
    names["NUTS_provisional"]={"status":"unavailable","probability":None,
                               "reason":"no_eligible_model"}
    return {"game_date":s["game_date"],"run_id":s["run_id"],"sport":s["sport"],
            "player":s["player"],"player_id":s["player_id"],"stat":s["stat"],
            "side":s["side"],"reference_line":s["reference_line"],"line":s["reference_line"],
            "forecast_at":s["forecast_at"],"event_start":s["event_start"],
            "models":names}


def fixture(count=24):
    slate=[snapshot(i) for i in range(count)]
    report={"schema":"slate-model-comparison-v1",
            "metadata":{"day":"2026-11-08","run_id":"SUNDAY"},
            "picks":[comparison_row(x) for x in slate]}
    top={"date":"2026-11-08","top_10_by_sport":{"NFL":[{
         **{k:slate[i][k] for k in ("game_date","run_id","sport","player",
             "player_id","stat","side","forecast_at","event_start")},
         "line":slate[i]["reference_line"]} for i in range(10)]}}
    sources=[{"game_date":"2026-11-08","sport":"NFL","stat":"tackles + assists"}]
    return slate,report,top,sources


class FullUniverseTests(unittest.TestCase):
    def test_full_24_not_ten_models_every_contract(self):
        slate,report,top,sources=fixture()
        result=audit(day="2026-11-08",source_rows=sources,quotes=[],
                     frozen_rows=slate,comparison=report,top10=top)
        self.assertEqual(result["frozen_contract_count"],24)
        self.assertEqual(result["comparison_contract_count"],24)
        self.assertEqual(result["top10"]["counts_by_sport"]["NFL"],10)
        self.assertTrue(result["top10"]["view_only"])
        self.assertEqual(result["model_coverage"]["Engine_A"]["forecast"],24)
        self.assertEqual(result["model_coverage"]["NUTS"]["unavailable"],24)
        self.assertEqual(result["model_coverage"]["NUTS_provisional"]["unavailable"],24)
        self.assertEqual(result["source"]["counts"]["historical_distribution_or_sample_unavailable"],1)

    def test_full_prepared_pipeline_receipt_reconciles(self):
        slate,report,top,sources=fixture()
        receipt={
            "schema":"all_prepared_props_attempts_v1","date":"2026-11-08",
            "run_id":"SUNDAY","all_prepared_contracts_attempted":True,
            "no_top10_or_triage_pre_filter":True,"prepared_contracts":25,
            "forecast_contracts":24,"unavailable_contracts":1,
            "unavailable_reasons":{"insufficient_source_data":1},
            "attempts":[{"status":"forecast"} for _ in range(24)]
                      +[{"status":"unavailable","reason":"insufficient_source_data"}]}
        result=audit(day="2026-11-08",source_rows=sources,quotes=[],
                     frozen_rows=slate,comparison=report,top10=top,
                     attempt_receipt=receipt)
        self.assertEqual(result["pipeline_attempts"]["prepared_contracts"],25)
        self.assertEqual(result["pipeline_attempts"]["forecast"],24)
        self.assertEqual(result["pipeline_attempts"]["unavailable"],1)

    def test_partial_attempt_receipt_rejected(self):
        slate,report,top,sources=fixture()
        receipt={
            "schema":"all_prepared_props_attempts_v1","date":"2026-11-08",
            "run_id":"SUNDAY","all_prepared_contracts_attempted":True,
            "no_top10_or_triage_pre_filter":True,"prepared_contracts":25,
            "forecast_contracts":24,"unavailable_contracts":1,
            "attempts":[{"status":"forecast"} for _ in range(24)]}
        with self.assertRaisesRegex(ValueError,"prepared_prop_attempt_receipt_incomplete"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top,
                  attempt_receipt=receipt)

    def test_receipt_must_match_forecast_run(self):
        slate,report,top,sources=fixture()
        receipt={
            "schema":"all_prepared_props_attempts_v1","date":"2026-11-08",
            "run_id":"ANOTHER","all_prepared_contracts_attempted":True,
            "no_top10_or_triage_pre_filter":True,"prepared_contracts":0,
            "forecast_contracts":0,"unavailable_contracts":0,
            "attempts":[]}
        with self.assertRaisesRegex(ValueError,"prepared_prop_attempt_receipt_not_matching_frozen_run"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top,
                  attempt_receipt=receipt)

    def test_missing_contract_blocks_publication(self):
        slate,report,top,sources=fixture()
        report["picks"].pop()
        with self.assertRaisesRegex(ValueError,"full_slate_comparison_incomplete"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top)

    def test_duplicate_contract_blocks_publication(self):
        slate,report,top,sources=fixture()
        report["picks"].append(copy.deepcopy(report["picks"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_comparison_prop_contracts"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top)

    def test_model_missing_status_blocks_publication(self):
        slate,report,top,sources=fixture()
        del report["picks"][0]["models"]["Bayesian_B"]
        with self.assertRaisesRegex(ValueError,"model_status_missing:Bayesian_B"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top)

    def test_unavailable_cannot_fake_probability(self):
        slate,report,top,sources=fixture()
        report["picks"][0]["models"]["NUTS"]["probability"]=.8
        with self.assertRaisesRegex(ValueError,"unavailable_model_cannot_supply_probability"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top)

    def test_topten_outside_frozen_run_rejected(self):
        slate,report,top,sources=fixture()
        top["top_10_by_sport"]["NFL"][0]["player_id"]="unknown"
        with self.assertRaisesRegex(ValueError,"top10_contains_non_frozen_contract"):
            audit(day="2026-11-08",source_rows=sources,quotes=[],
                  frozen_rows=slate,comparison=report,top10=top)

    def test_later_run_universe_not_confused_with_earlier_run(self):
        slate,report,top,sources=fixture()
        early=snapshot(900)
        early["run_id"]="EARLIER"
        early["forecast_at"]="2026-11-08T10:00:00+00:00"
        result=audit(day="2026-11-08",source_rows=sources,quotes=[],
                     frozen_rows=[early]+slate,comparison=report,top10=top)
        self.assertEqual(result["frozen_contract_count"],24)
        self.assertEqual(result["frozen_run_id"],"SUNDAY")

    def test_unsupported_stat_and_unavailable_models_are_audited(self):
        slate,report,top,sources=fixture()
        sources.append({"game_date":"2026-11-08","sport":"NHL","stat":"hits"})
        result=audit(day="2026-11-08",source_rows=sources,quotes=[],
                     frozen_rows=slate,comparison=report,top10=top)
        self.assertEqual(result["source"]["counts"]["source_player_stat_rows"],2)
        self.assertEqual(result["model_coverage"]["Market"]["forecast"],24)


if __name__=="__main__":
    unittest.main()
