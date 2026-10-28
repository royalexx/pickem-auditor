"""Offline contracts for autonomous primary-source investigation and source honesty."""
import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

from autonomous_investigator import (
    investigate, observation_source, verified_source, _validated_series,
    article_mentions,
)
from test_pick_verification import build as example, DATE, ID
import research_packet as rp

NOW = datetime(2026,10,27,20,30,tzinfo=timezone.utc)


def fixture():
    rows,q,p=example()
    rows[0]["player_id"]="8471234"
    rows[0]["inputs"]["player_id"]="8471234"
    q["queue"][0]["player_id"]="8471234"
    p["index"]["by_player"]["Example Player"]["player_id"]="8471234"
    return rows,q,p


def scoreboard():
    return {"events":[{"id":"EVT-1","date":"2026-10-27T23:00:00Z",
       "status":{"type":{"state":"pre"}},
       "competitions":[{"competitors":[{"team":{"abbreviation":"BOS"}},
                                       {"team":{"abbreviation":"NSH"}}],
                        "venue":{"indoor":True}}]}]}


def summary(active=True):
    return {"header":{"id":"EVT-1","competitions":[{"status":{"type":{"state":"pre"}}}]},
            "rosters":[{"team":{"abbreviation":"BOS"},
                        "roster":[{"athlete":{"displayName":"Example Player"},
                                   "active":active}]}]}


def gamelog():
    return {"gameLog":[{"gameId":f"game-{n}","gameDate":f"2026-10-{n:02}",
            "shots":v,"toi":"19:40","teamAbbrev":"BOS"}
            for n,v in ((20,4),(19,1),(18,3),(17,0),(16,2),(15,4))]}


def source(url,**kwargs):
    if "scoreboard?" in url:return scoreboard()
    if "summary?" in url:return summary()
    if "/injuries" in url:return {"injuries":[]}
    if "/news?" in url:return {"articles":[]}
    if "api-web.nhle.com" in url:return gamelog()
    raise AssertionError("unexpected URL "+url)


class AutonomousInvestigationTests(unittest.TestCase):
    def test_news_matches_exact_named_player_without_inventing_review(self):
        rows,q,p=fixture()
        news={"articles":[
            {"headline":"Example Player's deployment changing",
             "description":"Coach may have a rotation adjustment",
             "published":"2026-10-27T19:45:00Z",
             "links":{"web":{"href":"https://www.espn.com/nhl/story/test"}}},
            {"headline":"Example Playerlike unrelated mention",
             "published":"2026-10-27T19:50:00Z",
             "links":{"web":{"href":"https://www.espn.com/nhl/story/other"}}},
            {"headline":"Example Player rumor at suspicious host",
             "published":"2026-10-27T19:50:00Z",
             "links":{"web":{"href":"https://evil.example.com/fake"}}}]}
        matched=article_mentions(news,dict(player="Example Player"),NOW)
        self.assertEqual(len(matched),1)
        self.assertIn("Example Player",matched[0]["source_excerpt"])
        self.assertEqual(matched[0]["verification_status"],
                         "NAME_MENTION_ONLY_NOT_SCOUTING_OR_INJURY_PROOF")
        def discover(url,**kw):
            if "/news?" in url:return news
            return source(url,**kw)
        report,_=investigate(rows,q,p,DATE,now=NOW,fetch=discover)
        cand=report["candidates"][0]
        self.assertEqual(len(cand["relevant_news_mentions"]),1)
        self.assertIn("NEWS_MENTIONS_REQUIRE_SOURCE_READING_AND_CONTEXT",cand["blockers"])
        self.assertFalse(cand["publication_eligible"])

    def test_uses_actual_games_and_represents_both_sides(self):
        rows,q,p=fixture()
        original=copy.deepcopy(rows)
        report, updated=investigate(rows,q,p,DATE,now=NOW,fetch=source)
        self.assertEqual(rows,original)
        self.assertEqual(report["selected_candidates"],1)
        self.assertEqual(report["confirmed_active_subjects"],1)
        evidence=report["candidates"][0]["observed_history"]
        self.assertEqual(evidence["observation_count"],6)
        self.assertEqual(evidence["support_count"],3)
        self.assertEqual(evidence["opposing_count"],3)
        self.assertEqual(evidence["last_five_mean"],2)
        self.assertTrue(evidence["payload_sha256"])
        self.assertTrue(evidence["source_url"].startswith("https://api-web.nhle.com"))
        self.assertFalse(report["publication_eligible"])
        self.assertFalse(report["research_complete"])
        self.assertFalse(updated["_autonomous_investigation"]["promotion_authorized"])
        self.assertEqual(updated["availability"]["Example Player"]["status"]["value"],"active")
        self.assertNotIn("_autonomous_investigation",p)

    def test_no_automatic_review_or_engine_promotion(self):
        rows,q,p=fixture()
        report, updated=investigate(rows,q,p,DATE,now=NOW,fetch=source)
        c=report["candidates"][0]
        self.assertFalse(c["research_attested"])
        self.assertFalse(c["source_read_by_human"])
        self.assertIn("UNVERIFIED_CONTEXTUAL_MATCHUP_AND_ADVERSARIAL_REVIEW",c["blockers"])
        self.assertFalse((updated["scouting"].get(ID) or {}).get("evidence",{}).get("matchup"))

    def test_independently_verified_workload_fills_only_factual_deployment(self):
        rows,q,p=fixture()
        p["scouting"][ID]={"supporting_stats":{"deployment_trends":None,
                           "line_matching":None,"opponent_style":None},
                           "evidence":{"opportunity":None,"injuries":None,
                                       "matchup":None,"game_script":None},
                           "scenarios":[]}
        def rich(url,**kw):
            if "api-web.nhle.com" in url:
                data=gamelog()
                data["gameLog"] += [
                    {"gameId":f"older-{d}","gameDate":f"2026-10-{d:02}",
                     "shots":2,"toi":"21:00","teamAbbrev":"BOS"}
                    for d in (14,13,12,11)]
                return data
            return source(url,**kw)
        report,updated=investigate(rows,q,p,DATE,now=NOW,fetch=rich)
        evidence=updated["scouting"][ID]["supporting_stats"]["deployment_trends"]
        self.assertEqual(evidence["confidence"],"confirmed")
        self.assertEqual(evidence["value"]["current_season_sample"],10)
        self.assertFalse(evidence["value"]["lineup_or_matchup_confirmed"])
        self.assertEqual(evidence["source_kind"],
                         "machine_read_structured_statistical_observation")
        self.assertIsNone(updated["scouting"][ID]["supporting_stats"]["line_matching"])
        self.assertIsNone(updated["scouting"][ID]["evidence"]["matchup"])
        self.assertFalse(report["publication_eligible"])

    def test_missing_workload_never_fills_deployment(self):
        rows,q,p=fixture()
        p["scouting"][ID]={"supporting_stats":{"deployment_trends":None},
                           "evidence":{},"scenarios":[]}
        def no_workload(url,**kw):
            if "api-web.nhle.com" in url:
                return {"gameLog":[{"gameId":f"g{i}","gameDate":f"2026-10-{i:02}",
                                    "shots":i%3} for i in range(12,24)]}
            return source(url,**kw)
        _,updated=investigate(rows,q,p,DATE,now=NOW,fetch=no_workload)
        self.assertIsNone(updated["scouting"][ID]["supporting_stats"]["deployment_trends"])

    def test_existing_scouting_fact_is_not_overwritten_by_machine(self):
        rows,q,p=fixture()
        p["scouting"][ID]={"supporting_stats":{"deployment_trends":{"value":"reviewed"}},
                           "evidence":{},"scenarios":[]}
        def rich(url,**kw):
            if "api-web.nhle.com" in url:
                return {"gameLog":[{"gameId":f"g{i}","gameDate":f"2026-10-{i:02}",
                                    "shots":i%3,"toi":"19:00"} for i in range(12,24)]}
            return source(url,**kw)
        _,updated=investigate(rows,q,p,DATE,now=NOW,fetch=rich)
        self.assertEqual(updated["scouting"][ID]["supporting_stats"]["deployment_trends"],
                         {"value":"reviewed"})

    def test_source_requests_are_shared_for_repeated_player_stat_sides(self):
        rows,q,p=fixture()
        second=copy.deepcopy(rows[0]); second["side"]="under"
        second["inputs"]["id"]=ID[:-4]+"under"
        second["inputs"]["side"]="under"
        rows.append(second)
        second_q=copy.deepcopy(q["queue"][0]);second_q["candidate_id"]=second["inputs"]["id"]
        second_q["side"]="under"
        q["queue"].append(second_q)
        calls=[]
        def fetch(url,**kw):
            calls.append(url);return source(url,**kw)
        report,_=investigate(rows,q,p,DATE,now=NOW,fetch=fetch,limit=2)
        self.assertEqual(report["selected_candidates"],2)
        self.assertEqual(sum("api-web.nhle.com" in url for url in calls),1)
        self.assertEqual(sum("scoreboard?" in url for url in calls),1)

    def test_no_api_historical_post_game_rows_or_duplicates(self):
        rows,q,p=fixture()
        def source_bad(url,**kw):
            if "api-web.nhle.com" in url:
                return {"gameLog":[{"gameId":"a","gameDate":"2026-10-27",
                                    "shots":10,"toi":"20:00"}]}
            return source(url,**kw)
        report,_=investigate(rows,q,p,DATE,now=NOW,fetch=source_bad)
        self.assertIsNone(report["candidates"][0]["observed_history"])
        self.assertIn("INVALID_OR_POST_EVENT_OBSERVATION",report["candidates"][0]["blockers"])

    def test_unavailable_official_feed_never_uses_market_as_history(self):
        rows,q,p=fixture()
        def bad(url,**kw):
            if "api-web.nhle.com" in url:raise OSError("unavailable")
            return source(url,**kw)
        report,_=investigate(rows,q,p,DATE,now=NOW,fetch=bad)
        self.assertEqual(report["counts"]["source_research_blocked"],1)
        self.assertEqual(report["counts"].get("primary_history_retrieved",0),0)
        self.assertIn("OFFICIAL_GAMELOG_UNAVAILABLE_OSERROR",report["candidates"][0]["blockers"])

    def test_not_before_event_excluded_and_never_fetched(self):
        rows,q,p=fixture()
        rows[0]["event_start"]="2026-10-27T20:10:00Z"
        def no_fetch(*a,**kw):self.fail("no fetch after event")
        report,_=investigate(rows,q,p,DATE,now=NOW,fetch=no_fetch)
        self.assertEqual(report["selected_candidates"],0)
        self.assertEqual(report["source_calls_attempted"],0)
        self.assertEqual(report["not_selected"]["GAME_ALREADY_STARTED"],1)

    def test_disallows_untrusted_host_and_incomplete_ids(self):
        rows,q,p=fixture()
        self.assertFalse(verified_source("https://evil.com/nhl"))
        self.assertFalse(verified_source("http://api-web.nhle.com/v1/"))
        self.assertIsNone(observation_source(dict(q["queue"][0],player_id="X"),DATE))
        self.assertIsNone(observation_source(dict(q["queue"][0],sport="NFL"),DATE))

    def test_unchanged_packet_rejects_false_other_date(self):
        rows,q,p=fixture()
        with self.assertRaisesRegex(ValueError,"same-day"):
            investigate(rows,q,p,"2026-10-28",now=NOW,fetch=source)

    def test_research_packet_schema_accepts_machine_audit_sidecar_without_promotion(self):
        rows,q,p=fixture()
        report,updated=investigate(rows,q,p,DATE,now=NOW,fetch=source)
        _,issues=rp.validate_packet(updated,now=NOW)
        # Current test fixture intentionally has no qualified scouting packet.
        self.assertFalse(any(x.path.startswith("_autonomous_investigation") for x in issues))

    def test_nba_source_url_uses_espn_current_season(self):
        item={"sport":"NBA","player_id":1234}
        url=observation_source(item,DATE)
        self.assertIn("1234",url)
        self.assertIn("2027",url)
        self.assertTrue(verified_source(url))


if __name__=="__main__":
    unittest.main()
