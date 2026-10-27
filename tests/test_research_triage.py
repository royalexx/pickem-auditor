"""Contract tests: a research queue never upgrades a forecast to a pick."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research_triage import build
NOW=datetime(2026,10,27,20,30,tzinfo=timezone.utc)

def row(player="One",reason="STATUS_NOT_VERIFIED",a=True,b=True,grade=.68,
        market=.50,books=3,run="new",game="BOS@NSH",stat="shots on goal"):
    return {"game_date":"2026-10-27","run_type":"shadow","run_id":run,
            "forecast_at":"2026-10-27T20:00:00Z" if run=="new" else "2026-10-27T18:00:00Z",
            "sport":"NHL","player":player,"player_id":player,"team":"BOS",
            "opponent":"NSH","matchup":game,"stat":stat,"side":"over",
            "reference_line":2.5,"event_start":"2026-10-27T23:00:00Z",
            "reason":reason,"q_grade":grade,"q_market_comparable":market,
            "books":[{"book":"book"+str(i)} for i in range(books)],
            "engine_a":{"reliable":a},"engine_b":{"reliable":b},
            "researched":False,
            "inputs":{"id":f"NHL|{player}|{stat}|over","scouting":{"evidence":{}}}}

class ResearchTriageTests(unittest.TestCase):
    def test_both_engines_first_but_no_publication(self):
        report=build([row("A Only",b=False),row("Both"),
                      row("Thin",reason="SAMPLE_BLOCK")],
                     "2026-10-27",now=NOW)
        self.assertEqual(report["review_queue_count"],2)
        self.assertEqual(report["queue"][0]["player"],"Both")
        self.assertEqual(report["blocker_categories"]["sample_or_distribution"],1)
        self.assertTrue(all(not q["publication_eligible"] for q in report["queue"]))
        self.assertTrue(all("explicit_game_specific_player_status" in q["missing_evidence"]
                            for q in report["queue"]))

    def test_skips_one_book_invalid_and_started(self):
        started=row("Started");started["event_start"]="2026-10-27T20:00:00Z"
        report=build([row("OneBook",books=1),row("NoGrade",grade=None),
                      started,row("Qualified")],"2026-10-27",now=NOW)
        self.assertEqual([r["player"] for r in report["queue"]],["Qualified"])
        self.assertEqual(report["queue_exclusions"]["game_started"],1)

    def test_uses_latest_run_and_player_game_caps(self):
        report=build([row("Old",run="old"),row("Same"),
                      row("Same",stat="blocked shots"),row("Another",game="NYR@PHI")],
                     "2026-10-27",now=NOW,max_per_game=1)
        self.assertEqual(report["run_id"],"new")
        self.assertEqual(report["review_queue_count"],2)
        self.assertEqual(report["forecasts_evaluated"],3)

    def test_packet_gaps_are_not_positive_status(self):
        packet={"date":"2026-10-27",
                "index":{"by_player":{"One":{"team":"BOS","game":"BOS@NSH","sport":"NHL"}}},
                "availability":{}}
        result=build([row()],"2026-10-27",packet=packet,now=NOW)
        self.assertIn("availability.One.status",result["queue"][0]["source_tasks"])
        self.assertFalse(result["integrity"]["infer_active_from_injury_absence"])


    def test_reuses_one_source_url_across_same_sport_without_claiming_verification(self):
        report=build([row("One"), row("Two")],"2026-10-27",now=NOW)
        self.assertEqual(report["review_queue_count"],2)
        self.assertEqual(report["unique_public_source_urls_for_review"],2)
        self.assertEqual(report["source_urls_verified"],0)
        self.assertEqual(len(report["source_checklist"][0]["candidates"]),2)
        self.assertTrue(all(not source["verified"] for source in report["source_checklist"]))
        self.assertTrue(all(not c["source_guides_are_evidence"] for c in report["queue"]))
        self.assertEqual(report["queue"][0]["source_guides"][0]["task"],"confirm_fixture_and_start")

    def test_canonical_fixture_keys_supply_real_packet_gap_paths(self):
        packet={"date":"2026-10-27",
                "index":{"by_player":{"One":{"team":"BOS","game":"BOS@NSH","sport":"NHL"}}},
                "availability":{}}
        report=build([row(game="BOS @ NSH")],"2026-10-27",packet=packet,now=NOW)
        candidate=report["queue"][0]
        self.assertEqual(candidate["matched_packet_game"],"BOS@NSH")
        self.assertIn("weather.BOS@NSH.indoor",candidate["source_tasks"])
        self.assertNotIn("packet_fixture_identity_not_verified",candidate["missing_evidence"])

    def test_mismatched_packet_game_never_supplies_false_fixture_evidence(self):
        packet={"date":"2026-10-27",
                "index":{"by_player":{"One":{"team":"BOS","game":"BOS@MTL","sport":"NHL"}}},
                "availability":{}}
        report=build([row(game="BOS @ NSH")],"2026-10-27",packet=packet,now=NOW)
        candidate=report["queue"][0]
        self.assertIsNone(candidate["matched_packet_game"])
        self.assertIn("packet_fixture_identity_not_verified",candidate["missing_evidence"])
        self.assertFalse(any(x.startswith("weather.") for x in candidate["source_tasks"]))

    def test_nan_and_boolean_probabilities_are_rejected(self):
        report=build([row("Nan",grade=float("nan")),row("Bool",market=True)],
                     "2026-10-27",now=NOW)
        self.assertEqual(report["review_queue_count"],0)
        self.assertEqual(report["numerically_gradeable"],1)

if __name__=="__main__":
    unittest.main()
