"""Regression tests for broad stat coverage, early-season support and safe research recovery."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import odds_providers as op
import fetch_slate as fs
import pickem_math as pm
import research_triage as rt
import usage_baseline as ub

DATE="2026-10-27"
NOW=datetime(2026,10,27,20,30,tzinfo=timezone.utc)

def subject(player, sport, stat, reason, model, grade=None, market=.54, side="under"):
    return {
        "game_date":DATE, "run_type":"shadow", "run_id":"r1",
        "forecast_at":"2026-10-27T20:00:00Z",
        "event_start":"2026-10-28T02:00:00Z",
        "sport":sport, "player":player, "player_id":player,
        "team":"BOS", "opponent":"NYR", "matchup":"BOS@NYR",
        "stat":stat, "side":side, "reference_line":2.5,
        "reason":reason, "q_grade":grade,
        "q_market_comparable":market,
        "books":[{"book":name,"target":-110,"other":-110,"line":2.5}
                 for name in ("DraftKings","FanDuel")],
        "engine_a":{"reliable":grade is not None,
                    "observation_ids_verified":True, "q_win_robust":model},
        "engine_b":{"reliable":grade is not None},
        "inputs":{"id":"|".join((sport,player,stat,side)), "scouting":{"evidence":{}}},
        "researched":False,
    }

class FullSpectrumScreeningTests(unittest.TestCase):
    def test_all_documented_nba_combo_markets_requested(self):
        requested=dict(op.NBA_MARKETS)
        for key,stat in (
            ("player_points_rebounds","pr"),
            ("player_points_assists","pa"),
            ("player_rebounds_assists","ra"),
            ("player_points_rebounds_assists","pra"),
        ):
            self.assertEqual(requested[key],stat)
            self.assertIn(key,op.PROPLINE_SUPPORTED_MARKETS)

    def test_nhl_hits_source_without_inventing_unsupported_propline_prices(self):
        self.assertIn("hits",pm.NHL_SKATER_STATS)
        self.assertEqual(op.STAT_BY_MARKET["player_hits"],"hits")
        self.assertNotIn("player_hits",op.PROPLINE_SUPPORTED_MARKETS)
        self.assertEqual(
            fs.nhl_series([{"hits":4,"gameDate":"2026-10-20",
                            "gameId":"123","toi":"18:00"}],"hits")[0]["value"],4)
        self.assertEqual(fs.nhl_stat_value({"hits":0},"hits"),0)
        self.assertIsNone(fs.nhl_stat_value({},"hits"))
        self.assertIn("hits",fs.LOG_COUNT_STATS)

    def test_recovery_includes_nba_without_fabricating_a_final_grade(self):
        nba=subject("NBA Player","NBA","points","SAMPLE_BLOCK",.78,market=None)
        nhl=subject("NHL Player","NHL","shots on goal","STATUS_NOT_VERIFIED",.68,
                    grade=.68,market=.62)
        result=rt.build([nhl,nba],DATE,now=NOW,limit=9)
        self.assertEqual(result["review_queue_count"],2)
        recovered=next(r for r in result["queue"] if r["sport"]=="NBA")
        self.assertTrue(recovered["recovery_only"])
        self.assertEqual(recovered["model_diagnostic_source"],"engine_a_unverified_recovery_only")
        self.assertEqual(recovered["market_diagnostic_source"],"source_quote_diagnostic_only")
        self.assertFalse(recovered["publication_eligible"])
        self.assertEqual(result["tier_candidate_selected"],1)
        self.assertEqual(result["recovery_only_selected"],1)

    def test_one_player_can_have_multiple_independent_stats(self):
        a=subject("Multi","NHL","shots on goal","STATUS_NOT_VERIFIED",.72,grade=.72,market=.69)
        b=subject("Multi","NHL","blocked shots","STATUS_NOT_VERIFIED",.71,grade=.71,market=.66)
        result=rt.build([a,b],DATE,now=NOW)
        self.assertEqual({r["stat"] for r in result["queue"]},
                         {"shots on goal","blocked shots"})
        self.assertEqual(result["review_queue_count"],2)

    def test_unreliable_goalie_is_researched_but_never_approved(self):
        goalie=subject("Goalie","NHL","goalie saves",None,.81,
                       grade=.81,market=.51)
        goalie["engine_a"]["reliable"]=False
        goalie["engine_b"]["reliable"]=False
        report=rt.build([goalie],DATE,now=NOW)
        self.assertEqual(report["recovery_only_selected"],1)
        candidate=report["queue"][0]
        self.assertTrue(candidate["recovery_only"])
        self.assertTrue(candidate["watchlist_gap_cap_applies"])
        self.assertEqual(candidate["model_diagnostic_source"],
                         "graded_but_engine_unreliable_recovery_only")
        self.assertFalse(candidate["publication_eligible"])

    def test_verified_prior_support_does_not_fake_current_games_or_unicorn(self):
        unbacked=pm.grade(.74,.72,0,3)
        backed=pm.grade(.74,.72,0,3,prior_supported=True)
        self.assertEqual(unbacked["status"],"UNRANKED")
        self.assertEqual(backed["status"],"GRADED")
        self.assertEqual(backed["current_role_n"],3)
        self.assertTrue(backed["prior_supported"])
        self.assertEqual(backed["probability_rank"],"NUMERIC_TIER_3")
        self.assertIn("SOURCE_VERIFIED_EARLY_SEASON_PRIOR",backed["notes"])
        self.assertFalse(backed["unicorn_numeric"])

    def test_six_game_goalie_can_use_real_prior_with_source_check(self):
        goalie=dict(sport="NHL",stat="goalie saves",player_id="37",team="BOS",
                    game_date=DATE,line=26.5,side="under",
                    scouting={"historical_usage":"goalie-receipt"})
        current=[dict(id=f"G26-{i}",date=f"2026-10-{15+i:02d}",
                      value=24+i%3,workload=60.) for i in range(6)]
        prior=[dict(id=f"G25-{i}",date=f"2026-02-{(i%20)+1:02d}",
                    value=25+i%3,workload=60.) for i in range(20)]
        goalie["observation_ids"]={"prior":[x["id"] for x in prior]}
        data=dict(observations=current,prior_observations=prior,source_url="https://api.nhle.com/stats/rest/en/goalie/summary",
                  content_sha256="source-verified")
        with patch.object(ub,"load",return_value=data),patch.object(ub,"verify_a",return_value=True):
            result=ub.project(goalie,NOW)
        self.assertEqual(result["quality"]["n"],6)
        self.assertTrue(result["quality"]["early_season_prior_supported"])
        self.assertTrue(result["reliable"])
        with patch.object(ub,"load",return_value=data),patch.object(ub,"verify_a",return_value=False):
            result=ub.project(goalie,NOW)
        self.assertFalse(result["reliable"])

    def test_market_coverage_exposes_blocked_shot_absence(self):
        from market_coverage_audit import audit
        board=audit([{"sport":"NHL","stat":"shots on goal"}],
                    [{"sport":"NHL","stat":"blocked shots"}])
        blocks=next(x for x in board["market_rows"] if x["market"]=="player_blocked_shots")
        self.assertTrue(blocks["provider_supported"])
        self.assertEqual(blocks["source_rows"],1)
        self.assertEqual(blocks["quote_rows"],0)
        self.assertEqual(blocks["status"],"no_two_sided_quotes_in_normalized_feed")
        hits=next(x for x in board["market_rows"] if x["market"]=="player_hits")
        self.assertFalse(hits["provider_supported"])

    def test_early_season_scout_needs_verified_prior(self):
        from datetime import timedelta
        current=[dict(id=f"2026-{i}",date=f"2026-10-{20+i:02d}",value=12+i,
                      workload=24.+i) for i in range(3)]
        prior=[dict(id=f"2025-{i}",date=f"2026-02-{(i%20)+1:02d}",
                    value=13+i%3,workload=25.+i%2) for i in range(20)]
        candidate=dict(sport="NBA",stat="points",player_id="1",team="BOS",
                       game_date=DATE,line=12.5,side="over",
                       observation_ids={"prior":[x["id"] for x in prior]},
                       scouting={"historical_usage":"abc"})
        payload=dict(observations=current,prior_observations=prior,
                     source_url="https://example.org/games",content_sha256="verified")
        with patch.object(ub,"load",return_value=payload),patch.object(ub,"verify_a",return_value=True):
            result=ub.project(candidate,NOW)
        self.assertTrue(result["quality"]["early_season_prior_supported"])
        self.assertTrue(result["quality"]["numeric_provenance_complete"])
        self.assertGreaterEqual(result["quality"]["effective_n"],10)
        self.assertEqual(result["quality"]["n"],3)
        self.assertEqual(result["terms"]["prior_weight"],.4)
        with patch.object(ub,"load",return_value=payload),patch.object(ub,"verify_a",return_value=False):
            with self.assertRaises(ValueError):
                ub.project(candidate,NOW)

if __name__=="__main__":
    unittest.main()
