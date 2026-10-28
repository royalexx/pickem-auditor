"""Verification contracts: no backdating, fabricated approval, or mutable history."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pick_verification as pv
import research_packet as rp
from context_feeds import confirmed_fact

NOW = datetime(2026, 10, 27, 20, 30, tzinfo=timezone.utc)
DATE = "2026-10-27"
ID = "NHL|Example Player|shots on goal|over"


def build():
    row = {
        "run_type":"shadow", "run_id":"daily-1", "game_date":DATE, "sport":"NHL",
        "player":"Example Player", "player_id":"42", "team":"BOS", "opponent":"NSH",
        "matchup":"BOS @ NSH", "stat":"shots on goal", "side":"over",
        "reference_line":2.5, "forecast_at":"2026-10-27T20:00:00Z",
        "event_start":"2026-10-27T23:00:00Z", "researched":False,
        "inputs":{"id":ID, "stat":"shots on goal", "side":"over", "line":2.5,
                  "team":"BOS", "opponent":"NSH", "player_id":"42",
                  "game_date":DATE, "soft_flags":0, "mechanisms":0,
                  "hard_veto":"no", "data_veto":"no", "research_checklist":"no",
                  "market_retrieved_at":"2026-10-27T20:20:00Z",
                  "books":[{"book":"FanDuel","line":2.5,"target":-115,
                            "other":-105,"book_side":"over"},
                           {"book":"DraftKings","line":2.5,"target":-115,
                            "other":-105,"book_side":"over"}]},
    }
    q = {"date":DATE,"queue":[{
        "candidate_id":ID, "sport":"NHL", "player":"Example Player",
        "player_id":"42", "team":"BOS", "opponent":"NSH", "stat":"shots on goal",
        "side":"over", "line":2.5, "game":"BOS @ NSH"
    }]}
    packet = rp.empty_template(DATE)
    packet["index"]["by_player"]["Example Player"] = {
        "sport":"NHL", "team":"BOS", "player_id":"42", "game":"BOS@NSH"}
    return [row],q,packet


def attest(row, timestamp="2026-10-27T20:30:00Z"):
    positive = confirmed_fact("opportunity", "yes", "https://example.com/positive",
                              timestamp, quote="Top six role confirmed")
    contrary = confirmed_fact("opposition", "reviewed", "https://example.com/opponent",
                              timestamp, quote="Opponent pressure considered")
    return {"date":DATE,"attestations":[{"candidate_id":ID,
       "forecast_sha256":pv.forecast_digest(row), "team":"BOS", "player_id":"42",
       "decision":"approve", "reviewer":"Human analyst", "source_read":True,
       "reviewed_at":timestamp, "supporting":[positive], "opposing":[contrary]}]}


def active(packet, when="2026-10-27T20:30:00Z"):
    fact=confirmed_fact("explicit game-active roster", "active", 
                        "https://site.api.espn.com/summary", when,
                        quote="Game active")
    fact["report_type"]="final_active_roster"
    packet.setdefault("availability", {})["Example Player"]={
        "status":fact,
        "primary_source":confirmed_fact("primary_source", "league",
                                         "https://site.api.espn.com/summary",when)}
    packet.setdefault("weather", {})["BOS@NSH"]={
        "indoor":confirmed_fact("indoor", True,"https://site.api.espn.com/scoreboard",when)}


class VerificationTests(unittest.TestCase):
    def test_morning_settlement_never_breaks_original_forecast_link(self):
        rows,_,_=build()
        original=pv.forecast_digest(rows[0])
        rows[0].update(actual_stat=4, outcome="win",
                       settled_at="2026-10-28T08:30:00Z")
        self.assertEqual(pv.forecast_digest(rows[0]),original)
        rows[0]["reference_line"]=3.5
        self.assertNotEqual(pv.forecast_digest(rows[0]),original)

    def test_automated_dossier_attaches_provenance_without_false_review(self):
        rows,queue,packet=build()
        packet["_autonomous_investigation"]={
            "candidate_summaries":{ID:{"forecast_sha256":pv.forecast_digest(rows[0]),
                "source":"https://api-web.nhle.com/v1/player/42/game-log/20262027/2",
                "supporting_game_count":4,"opposing_game_count":2,
                "news_mention_count":1}},
            "research_complete":False,"promotion_authorized":False}
        result,_=pv.verify(rows,queue,packet,DATE,now=NOW)
        machine=result["decisions"][0]["autonomous_investigation"]
        self.assertEqual(machine["supporting_game_count"],4)
        self.assertFalse(machine["approval_authorized"])
        self.assertFalse(result["decisions"][0]["publication_eligible"])
        packet["_autonomous_investigation"]["candidate_summaries"][ID]["forecast_sha256"]="tampered"
        result,_=pv.verify(rows,queue,packet,DATE,now=NOW)
        self.assertIsNone(result["decisions"][0]["autonomous_investigation"])

    def test_original_forecasts_are_never_modified(self):
        rows, queue, packet=build()
        before=deepcopy(rows)
        output, checked=pv.verify(rows,queue,packet,DATE,now=NOW)
        self.assertEqual(rows,before)
        self.assertEqual(output["verified"],0)
        self.assertIn("ADVERSARIAL_REVIEW_NOT_ATTESTED_OR_DUPLICATE", output["decisions"][0]["blockers"])
        self.assertFalse(output["decisions"][0]["publication_eligible"])
        self.assertIsNot(packet,checked)

    def test_explicit_active_flag_is_not_inferred_from_injury_omission(self):
        rows,queue,packet=build()
        ok,reason=pv.status_verified(packet,queue["queue"][0],NOW)
        self.assertFalse(ok)
        self.assertEqual(reason,"GAME_SPECIFIC_ACTIVE_STATUS_MISSING")
        active(packet)
        ok,reason=pv.status_verified(packet,queue["queue"][0],NOW)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_unresolved_source_conflict_overrides_an_active_flag(self):
        rows,q,packet=build()
        active(packet)
        packet["_source_conflicts"]=[{"player":"Example Player","field":"status",
                                      "resolution":"unresolved",
                                      "challenger":{"value":"out"}}]
        self.assertEqual(pv.status_verified(packet,q["queue"][0],NOW)[1],
                         "UNRESOLVED_CONTRADICTORY_STATUS_EVIDENCE")

    def test_bare_active_fact_cannot_replace_game_specific_report(self):
        rows,queue,packet=build()
        active(packet)
        packet["availability"]["Example Player"]["status"].pop("report_type")
        self.assertEqual(pv.status_verified(packet,queue["queue"][0],NOW)[1],
                         "STATUS_NOT_FROM_EXPLICIT_GAME_REPORT")

    def test_started_game_never_researched(self):
        rows,queue,packet=build()
        rows[0]["event_start"]="2026-10-27T20:10:00Z"
        fetch=lambda *a,**k:self.fail("should not fetch")
        result,_=pv.verify(rows,queue,packet,DATE,now=NOW,fetch=fetch)
        self.assertEqual(result["checked"],0)
        self.assertEqual(result["not_due"]["GAME_ALREADY_STARTED"],1)

    def test_recheck_window_limits_source_requests(self):
        rows,queue,packet=build()
        calls=[]
        def fetch(*a,**k):
            calls.append(a)
            raise ValueError("not expected")
        result,_=pv.verify(rows,queue,packet,DATE,now=NOW,phase="recheck",fetch=fetch)
        self.assertEqual(calls,[])
        self.assertEqual(result["status"],"no_candidates_due")
        rows[0]["event_start"]="2026-10-27T21:15:00Z"
        self.assertIsNone(pv.eligible_window(rows[0],NOW,phase="recheck"))

    def test_forecast_digests_bind_review_to_exact_input(self):
        rows,queue,packet=build()
        reviewer=attest(rows[0])["attestations"][0]
        self.assertEqual(pv.review_verified(reviewer,rows[0],pv.forecast_digest(rows[0]),NOW),(True,None))
        rows[0]["reference_line"]=3.5
        self.assertFalse(pv.review_verified(reviewer,rows[0],pv.forecast_digest(rows[0]),NOW)[0])

    def test_timestamped_evidence_required_both_directions(self):
        rows,_,_=build()
        review=attest(rows[0])["attestations"][0]
        review["opposing"]=[]
        self.assertEqual(pv.review_verified(review,rows[0],pv.forecast_digest(rows[0]),NOW)[1],
                         "REVIEW_MISSING_OPPOSING")
        review=attest(rows[0])["attestations"][0]
        review["reviewed_at"]="2026-10-26T20:30:00Z"
        self.assertFalse(pv.review_verified(review,rows[0],pv.forecast_digest(rows[0]),NOW)[0])

    def test_stale_original_afternoon_market_cannot_be_reused_at_night(self):
        rows,_,_=build()
        updated,issues=pv.quote_refresh(rows[0]["inputs"],None,
                         datetime(2026,10,27,22,0,tzinfo=timezone.utc))
        self.assertIsNone(updated)
        self.assertIn("ORIGINAL_MARKET_TIMESTAMP_STALE_OR_MISSING",issues)

    def test_live_propline_quote_join_uses_immutable_original_player_identity(self):
        rows,_,_=build()
        candidate=rows[0]["inputs"]
        self.assertNotIn("player",candidate)
        quotes=[
            {"sport":"NHL","player":"Example Player","player_norm":"example player",
             "team":"BOS","opponent":"NSH","event_teams":["BOS","NSH"],
             "game_date":DATE,"stat":"shots on goal","line":2.5,
             "book":book,"over_odds":-115,"under_odds":-105,
             "retrieved_at":"2026-10-27T20:20:00Z"}
            for book in ("DraftKings","Pinnacle")]
        updated,issues=pv.quote_refresh(candidate,quotes,NOW,identity=rows[0])
        self.assertEqual(issues,[])
        self.assertEqual(len(updated["books"]),2)
        self.assertEqual(updated["market_retrieved_at"],"2026-10-27T20:20:00+00:00")
        self.assertNotIn("player",updated)
        self.assertNotIn("sport",updated)

    def test_market_join_refuses_conflicting_fixture(self):
        rows,_,_=build()
        candidate=dict(rows[0]["inputs"],opponent="MTL")
        updated,issues=pv.quote_refresh(candidate,[],NOW,identity=rows[0])
        self.assertIsNone(updated)
        self.assertEqual(issues,["ORIGINAL_PIPELINE_IDENTITY_CONFLICT"])

    def test_stale_market_quote_file_never_grants_grade(self):
        rows,_,_=build()
        updated, issues=pv.quote_refresh(rows[0]["inputs"], [], NOW, identity=rows[0])
        self.assertIsNone(updated)
        self.assertIn("CURRENT_TWO_SIDED_SAME_LINE_MARKET_MISSING",issues)

    def test_mocked_grading_cannot_approve_without_review_or_sources(self):
        rows,queue,packet=build()
        # A positive numerical outcome is insufficient without source review.
        with patch.object(pv.pm,"evaluate_candidate",return_value={
                "final_rank":"Tier 2","engine_a":{"reliable":True},
                "engine_b":{"reliable":True},"blend":{"validated":True}}):
            result,_=pv.verify(rows,queue,packet,DATE,now=NOW)
        self.assertEqual(result["verified"],0)
        self.assertFalse(result["decisions"][0]["publication_eligible"])

    def test_missing_packet_identity_does_not_promote(self):
        rows,queue,packet=build()
        packet["index"]["by_player"]["Example Player"]["game"]="BOS@MTL"
        result,_=pv.verify(rows,queue,packet,DATE,now=NOW)
        self.assertIn("PACKET_FIXTURE_IDENTITY_MISMATCH", result["decisions"][0]["blockers"])

    def test_fully_attested_case_can_generate_separate_verified_tier2(self):
        rows,queue,packet=build()
        active(packet)
        with patch.object(pv.pm,"evaluate_candidate",return_value={
                "final_rank":"Tier 2","engine_a":{"reliable":True},
                "engine_b":{"reliable":True},"blend":{"validated":False},
                "grade":{"q_model":.64,"q_market_comparable":.54}}):
            result,_=pv.verify(rows,queue,packet,DATE,now=NOW,reviews=attest(rows[0]))
        self.assertEqual(result["verified"],1)
        self.assertEqual(result["decisions"][0]["verified_rank"],"Tier 2")
        self.assertTrue(result["decisions"][0]["publication_eligible"])
        self.assertFalse(rows[0]["researched"])

    def test_tier1_still_requires_validated_blend(self):
        rows,queue,packet=build()
        active(packet)
        with patch.object(pv.pm,"evaluate_candidate",return_value={
                "final_rank":"Tier 1","engine_a":{"reliable":True},
                "engine_b":{"reliable":True},"blend":{"validated":False},
                "grade":{"q_model":.64,"q_market_comparable":.54}}):
            result,_=pv.verify(rows,queue,packet,DATE,now=NOW,reviews=attest(rows[0]))
        self.assertEqual(result["verified"],0)
        self.assertIn("TIER1_BLEND_NOT_VALIDATED",result["decisions"][0]["blockers"])

    def test_attested_review_still_requires_two_reliable_engines(self):
        rows,queue,packet=build()
        active(packet)
        review=attest(rows[0])
        with patch.object(pv.pm,"evaluate_candidate",return_value={
                "final_rank":"Tier 2","engine_a":{"reliable":True},
                "engine_b":{"reliable":False},"blend":{"validated":False}}):
            result,_=pv.verify(rows,queue,packet,DATE,now=NOW,reviews=review)
        self.assertEqual(result["verified"],0)
        self.assertIn("TWO_RELIABLE_ENGINES_REQUIRED", result["decisions"][0]["blockers"])

    def test_source_collection_scope_limited_to_selected_candidates(self):
        rows,queue,packet=build()
        called=[]
        def resolver(p, candidates, fetch, now):
            called.extend(candidates)
            return p,{"attempts":[],"verified_pregame_games":[]}
        with patch("research_resolver.resolve",side_effect=resolver):
            result,_=pv.verify(rows,queue,packet,DATE,now=NOW,fetch=lambda *a,**k:None)
        self.assertEqual(called,[ID])
        self.assertEqual(result["verified"],0)

    def test_full_cli_writes_distinct_receipt_without_modifying_snapshots(self):
        import io
        import json
        import os
        import tempfile
        from contextlib import redirect_stdout
        from unittest.mock import patch
        rows,queue,packet=build()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            snapshots=root/"snapshots.jsonl"
            snapshots.write_text(json.dumps(rows[0])+"\n")
            original=snapshots.read_bytes()
            q=root/"queue.json"
            q.write_text(json.dumps(queue))
            p=root/"packet.json"
            p.write_text(json.dumps(packet))
            out=root/"reports"/"verification.json"
            args=["--date",DATE,"--snapshots",str(snapshots),
                  "--queue",str(q),"--packet",str(p),
                  "--phase","initial","--out",str(out),
                  "--archive-root",str(root/"archive"),
                  "--now","2026-10-27T20:30:00Z"]
            with patch.dict(os.environ,{"GITHUB_RUN_ID":"offline-test-1",
                                         "GITHUB_RUN_ATTEMPT":"1"}):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(pv.main(args),0)
                self.assertEqual(snapshots.read_bytes(),original)
                report=json.loads(out.read_text())
                self.assertEqual(report["checked"],1)
                self.assertEqual(report["verified"],0)
                archived=root/"archive"/DATE/"decisions"/"offline-test-1-1-initial.json"
                self.assertEqual(json.loads(archived.read_text())["schema"],
                                 "pick-verification-v1")
                with self.assertRaisesRegex(ValueError,"already exists"):
                    with redirect_stdout(io.StringIO()):
                        pv.main(args)

    def test_bad_reviewed_packet_date_fails_closed(self):
        rows,queue,packet=build()
        with self.assertRaisesRegex(ValueError,"same-date"):
            pv.verify(rows,queue,packet,"2026-10-26",now=NOW)


if __name__=="__main__":
    unittest.main()
