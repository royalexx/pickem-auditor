"""Adversarial research-only NBA S0 original O/U quote tests."""
import json
import math
import unittest
from datetime import datetime,timezone
from unittest.mock import patch

from research.v25_remediation import nba_s0_ou_sidecar as m
from v2.p0_integrity.contracts import record


class OriginalOUContractTests(unittest.TestCase):
    @staticmethod
    def originals():
        return [{
            "forecast":{
                "event_id":"espn:game:401910035",
                "team_id":"espn:team:9","opponent_id":"espn:team:2",
                "player_id":"espn:player:3134903","stat_key":"points",
                "event_start_at":"2026-11-23T01:30:00Z",
                "forecast_at":"2026-11-23T00:40:00Z",
                "period":"full"
            },
            "feature":{"features":{"current_name":"Gary Payton II"}}
        }]

    @staticmethod
    def scoreboard():
        e={"events":[{
            "id":"401910035","date":"2026-11-23T01:30:00Z",
            "status":{"type":{"name":"STATUS_SCHEDULED"}},
            "competitions":[{"competitors":[
                {"team":{"id":"9","abbreviation":"GS"}},
                {"team":{"id":"2","abbreviation":"BOS"}}
            ]}]}]}
        return json.dumps(e).encode()

    @staticmethod
    def quote():
        return {"sport":"NBA","event_teams":["GSW","BOS"],
            "event_start":"2026-11-23T01:30:00Z",
            "player":"Gary Payton II","stat":"points","book":"Pinnacle",
            "team":"GSW","line":7.5,"over_odds":-115,"under_odds":-105}

    def test_true_same_event_team_player_time(self):
        cross=m.event_crosswalk(self.scoreboard(),self.originals())
        self.assertTrue(m.identity_match(self.quote(),self.originals()[0],
            cross,captured_at="2026-11-23T00:43:00Z"))

    def test_reject_wrong_event_even_if_player_name_matches(self):
        x=self.quote();x["event_teams"]=["BOS","NYK"]
        with self.assertRaisesRegex(m.QuoteBlocked,"QUOTE_EVENT_TEAM_CROSSWALK"):
            m.identity_match(x,self.originals()[0],
                m.event_crosswalk(self.scoreboard(),self.originals()),
                captured_at="2026-11-23T00:43:00Z")

    def test_reject_wrong_team_and_ambiguous_player(self):
        cross=m.event_crosswalk(self.scoreboard(),self.originals())
        x=self.quote();x["team"]="BOS"
        with self.assertRaisesRegex(m.QuoteBlocked,"QUOTE_PLAYER_TEAM_CONFLICT"):
            m.identity_match(x,self.originals()[0],cross,
                captured_at="2026-11-23T00:43:00Z")
        x=self.quote();x["player"]="Georges Niang"
        with self.assertRaisesRegex(m.QuoteBlocked,"QUOTE_PLAYER_NAME_CONFLICT"):
            m.identity_match(x,self.originals()[0],cross,
                captured_at="2026-11-23T00:43:00Z")

    def test_reject_posttip_but_allow_postfreeze_pregame(self):
        cross=m.event_crosswalk(self.scoreboard(),self.originals())
        with self.assertRaisesRegex(m.QuoteBlocked,"QUOTE_AFTER_EVENT"):
            m.identity_match(self.quote(),self.originals()[0],cross,
                captured_at="2026-11-23T01:31:00Z")
        self.assertTrue(m.identity_match(self.quote(),self.originals()[0],cross,
                captured_at="2026-11-23T00:45:00Z"))

    def test_reject_espn_changed_game_teams_or_final(self):
        doc=json.loads(self.scoreboard())
        doc["events"][0]["competitions"][0]["competitors"][0]["team"]["id"]="18"
        with self.assertRaisesRegex(m.QuoteBlocked,"ESPN_TEAM_CROSSWALK_CONFLICT"):
            m.event_crosswalk(json.dumps(doc).encode(),self.originals())
        doc=json.loads(self.scoreboard())
        doc["events"][0]["status"]["type"]["name"]="STATUS_FINAL"
        with self.assertRaisesRegex(m.QuoteBlocked,"ESPN_EVENT_NOT_SCHEDULED"):
            m.event_crosswalk(json.dumps(doc).encode(),self.originals())

    def test_distribution_exact_push_and_nonpush(self):
        a=m.poisson_contract(0,0.5)
        self.assertEqual(a,{"under":1.,"push":0.,"over":0.})
        b=m.poisson_contract(0,0)
        self.assertEqual(b,{"under":0.,"push":1.,"over":0.})
        c=m.poisson_contract(2,1.5)
        self.assertAlmostEqual(c["under"],3*math.exp(-2),places=12)
        self.assertEqual(c["push"],0.)
        d=m.poisson_contract(2,2)
        self.assertAlmostEqual(d["under"],3*math.exp(-2),places=12)
        self.assertAlmostEqual(d["push"],2*math.exp(-2),places=12)
        self.assertAlmostEqual(sum(d.values()),1,places=12)

    def test_market_no_vig_two_sided(self):
        p=m.market_probabilities(-110,-110)
        self.assertAlmostEqual(p["over_no_vig"],.5)
        self.assertAlmostEqual(p["under_no_vig"],.5)
        self.assertGreater(p["overround"],0)
        with self.assertRaises(m.QuoteBlocked):
            m.market_probabilities(-90,-110)

    def test_supported_marketquote_p0_schema(self):
        q=record("MarketQuote",
            quote_id="nba-s0-ou-quote:abcd",contract_id="nba-s0-ou-contract:abcd",
            event_id="espn:game:401910035",sport="NBA",
            team_id="espn:team:9",opponent_id="espn:team:2",
            player_id="espn:player:3134903",stat_key="points",
            period="full",quote_timestamp="2026-11-23T00:50:00Z",
            event_start_at="2026-11-23T01:30:00Z",book="Pinnacle",
            product_type="player_prop",quote_kind="real",line=7.5,
            side="paired",source_receipt_id="original:receipt",
            source_sha256="a"*64,terms={"over_american":-110,"under_american":-110},
            accepted=True,reject_reason=None)
        self.assertTrue(q["accepted"])
        with self.assertRaises(Exception):
            record("MarketQuote",**{k:v for k,v in q.items() if k not in ("record_type","schema_version")} | {
                "quote_timestamp":"2026-11-23T02:00:00Z"})

    def test_reject_invalid_distribution_and_quote(self):
        for lam,line in [(float("nan"),2.5),(-1,3.5),(1,float("inf"))]:
            with self.assertRaises(m.QuoteBlocked):
                m.poisson_contract(lam,line)
        cross=m.event_crosswalk(self.scoreboard(),self.originals())
        x=self.quote();x["under_odds"]=None
        with self.assertRaisesRegex(m.QuoteBlocked,"TWO_SIDED_PRICES_REQUIRED"):
            m.identity_match(x,self.originals()[0],cross,
                captured_at="2026-11-23T00:43:00Z")


if __name__=="__main__":
    unittest.main()
