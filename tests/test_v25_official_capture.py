"""Gate B official final-only settlement identity + no-live-leak adversarial tests."""
import sys
from pathlib import Path
import unittest
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from v2.official_nba_nhl_capture import (
    SettlementCaptureError, original_event_scope, schedule_games,
    match_schedule, nhl_stat_rows, nba_stat_rows, settlement_rows_for_final)


def contract(sport="NHL",**kwargs):
    base={"sport":sport,"event_id":"orig-1","event_start":"2026-11-11T00:00:00Z",
          "input_freeze_at":"2026-11-10T18:01:00Z","team_id":"COL","opponent_id":"TOR",
          "player_id":"8480069","stat":"shots on goal","line":1.5}
    base.update(kwargs)
    return base


def nhl_final():
    return {"id":2026020286,"gameState":"FINAL","limitedScoring":False,
            "homeTeam":{"abbrev":"TOR"},"awayTeam":{"abbrev":"COL"},
            "playerByGameStats":{
                "homeTeam":{"forwards":[],"defense":[]},
                "awayTeam":{"forwards":[],"defense":[
                    {"playerId":8480069,"sog":3,"toi":"21:31","position":"D"}]}}}


def nba_final():
    return {"header":{"competitions":[{
                "status":{"type":{"name":"STATUS_FINAL","completed":True}},
                "competitors":[{"team":{"abbreviation":"NY"}},
                               {"team":{"abbreviation":"MIL"}}]}]},
            "boxscore":{"players":[
                {"team":{"abbreviation":"NY"},"statistics":[
                    {"labels":["MIN","PTS","FG","3PT","FT","REB","AST"],
                     "athletes":[{"athlete":{"id":"42","position":{"abbreviation":"G"}},
                                 "stats":["32","24","8-20","3-6","5-5","7","5"],
                                 "didNotPlay":False}]}]},
                {"team":{"abbreviation":"MIL"},"statistics":[
                    {"labels":["MIN","PTS","FG","3PT","FT","REB","AST"],
                     "athletes":[{"athlete":{"id":"43"},"stats":["0","0","0-0","0-0","0-0","0","0"],
                                 "didNotPlay":True}]}]}]}}


class OfficialFinalGateTests(unittest.TestCase):
    def test_nhl_final_player_id_and_stats(self):
        group=original_event_scope([contract()])[("NHL","orig-1")]
        settled,other=settlement_rows_for_final(
            group,nhl_final(),game_id="2026020286",
            url="https://api-web.nhle.com/v1/gamecenter/2026020286/boxscore",
            raw_digest="a"*64,source_path="nhl.json",
            observed_at="2026-11-11T03:10:00Z")
        self.assertEqual((len(settled),len(other)),(1,0))
        self.assertEqual(settled[0]["actual"],3)
        self.assertAlmostEqual(settled[0]["observed_workload_minutes"],21+31/60)
        self.assertEqual(settled[0]["settlement_clock_semantics"],
            "collector_first_verified_provider_final_no_whistle_claim")

    def test_live_nhl_game_rejected(self):
        x=nhl_final();x["gameState"]="LIVE"
        with self.assertRaisesRegex(SettlementCaptureError,"not_final"):
            nhl_stat_rows(x,expected_teams={"COL","TOR"})

    def test_nhl_team_and_game_identity_cannot_be_reused(self):
        g=original_event_scope([contract()])[("NHL","orig-1")]
        x=nhl_final();x["id"]=999
        with self.assertRaisesRegex(SettlementCaptureError,"game_id_mismatch"):
            settlement_rows_for_final(g,x,game_id="2026020286",url="https://x",
                raw_digest="a"*64,source_path="x",observed_at="2026-11-11T03:00:00Z")
        x=nhl_final();x["homeTeam"]["abbrev"]="BOS"
        with self.assertRaisesRegex(SettlementCaptureError,"teams_mismatch"):
            nhl_stat_rows(x,expected_teams={"COL","TOR"})

    def test_nhl_no_player_does_not_invent_zero(self):
        g=original_event_scope([contract(player_id="not-on-final-roster")])[("NHL","orig-1")]
        settled,missing=settlement_rows_for_final(g,nhl_final(),game_id="2026020286",
          url="https://api-web.nhle.com/v1/gamecenter/2026020286/boxscore",
          raw_digest="a"*64,source_path="nhl.json",
          observed_at="2026-11-11T03:10:00Z")
        self.assertEqual(settled,[])
        self.assertEqual(missing[0]["reason"],"missing_or_did_not_play_in_verified_final_boxscore")

    def test_wrong_team_forecast_quarantined_without_discarding_valid_game(self):
        expected=original_event_scope([contract(
            player_id="8480069",team_id="TOR",opponent_id="COL")])[("NHL","orig-1")]
        result,excluded=settlement_rows_for_final(expected,nhl_final(),
            game_id="2026020286",
            url="https://api-web.nhle.com/v1/gamecenter/2026020286/boxscore",
            raw_digest="a"*64,source_path="nhl.json",
            observed_at="2026-11-11T03:10:00Z")
        self.assertEqual(result,[])
        self.assertEqual(excluded[0]["reason"],
                         "official_player_team_disagrees_frozen_offer")
        self.assertEqual(excluded[0]["original_frozen_team"],"TOR")
        self.assertEqual(excluded[0]["official_postgame_team"],"COL")

    def test_nba_final_all_combo_stats_and_threes(self):
        stat=nba_stat_rows(nba_final(),expected_teams={"NYK","MIL"})
        self.assertEqual(stat["42"]["points"],24)
        self.assertEqual(stat["42"]["rebounds"],7)
        self.assertEqual(stat["42"]["assists"],5)
        self.assertEqual(stat["42"]["threes"],3)
        self.assertEqual(stat["42"]["pra"],36)
        self.assertNotIn("43",stat)

    def test_nba_in_game_never_graded(self):
        x=nba_final();x["header"]["competitions"][0]["status"]["type"]["completed"]=False
        with self.assertRaisesRegex(SettlementCaptureError,"not_final"):
            nba_stat_rows(x,expected_teams={"NYK","MIL"})

    def test_nba_3pm_more_than_attempts_invalid(self):
        x=nba_final();x["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][3]="5-4"
        with self.assertRaisesRegex(SettlementCaptureError,"made_gt_attempted"):
            nba_stat_rows(x,expected_teams={"NYK","MIL"})

    def test_teams_and_start_required_for_match(self):
        items=[contract()]
        scope=original_event_scope(items)
        event={"sport":"NHL","id":"official","teams":{"COL","TOR"},
               "start":__import__("datetime").datetime.fromisoformat("2026-11-11T00:00:00+00:00"),
               "status":"FINAL"}
        self.assertEqual(match_schedule(scope,[event])[("NHL","orig-1")],"official")
        distant={**event,"start":__import__("datetime").datetime.fromisoformat("2026-11-12T00:00:00+00:00")}
        self.assertEqual(match_schedule(scope,[distant]),{})
        with self.assertRaisesRegex(SettlementCaptureError,"multiple_official"):
            match_schedule(scope,[event,{**event,"id":"other"}])

    def test_stale_future_or_duplicate_frozen_candidates_rejected(self):
        x=contract()
        with self.assertRaisesRegex(SettlementCaptureError,"nonpregame"):
            original_event_scope([{**x,"input_freeze_at":"2026-11-11T01:00:00Z"}])
        with self.assertRaisesRegex(SettlementCaptureError,"duplicate_frozen_prop"):
            original_event_scope([x,deepcopy(x)])

    def test_nba_ny_alias_in_schedule(self):
        payload={"events":[{"id":"x","date":"2026-11-11T00:30:00Z",
             "competitions":[{"competitors":[
               {"team":{"abbreviation":"NY"}},{"team":{"abbreviation":"MIL"}}]}],
             "status":{"type":{"completed":True,"name":"STATUS_FINAL"}}}]}
        result=schedule_games("NBA",payload,game_date="2026-11-10")
        self.assertEqual(result[0]["teams"],{"NYK","MIL"})
        self.assertEqual(result[0]["status"],"FINAL")


if __name__=="__main__":
    unittest.main()
