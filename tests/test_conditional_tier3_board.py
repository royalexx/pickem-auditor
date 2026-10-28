"""Conditional Tier 3 is source-vetoed, strong and NOT a verified pick."""
import copy
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

import conditional_tier3_board as cb
from test_research_ranked_board import fixture

DATE="2026-10-27"
NOW=datetime(2026,10,27,20,30,tzinfo=timezone.utc)


def setup():
    rows,queue=fixture()
    row=rows[0]
    row.update(q_grade=.74,q_market=.69,q_market_comparable=.69)
    packet={"date":DATE,"index":{"by_player":{"Example Skater":{
            "sport":"NHL","team":"BOS","game":"BOS@NSH"}}}}
    return rows,queue,packet


def tendency():
    return {"status":"high_continuity","played_last_5":5,
            "likely_available":True,"confirmed_active":False,
            "usable_for_verified_tier":False,
            "source_snapshot_sha256":"f"*64,"sample":5}


def injury_source(url,**kwargs):
    return {"injuries":[{"team":{"abbreviation":"MTL"},"injuries":[]}]}


def fresh():
    return {"market_retrieved_at":"2026-10-27T20:29:00Z",
            "books":[{"book":"FanDuel","line":2.5,"target":-250,"other":210,"book_side":"over"},
                     {"book":"DraftKings","line":2.5,"target":-255,"other":215,"book_side":"over"}]}


class ConditionalTests(unittest.TestCase):
    def full(self,rows,queue,packet,**kw):
        with (patch.object(cb,"tendency_check",return_value=tendency()),
              patch.object(cb,"machine_review",return_value=(True,None,{
                  "independent_live_refetch":True,"source_read_by_human":False,
                  "source_payload_sha256":"f"*64})),
              patch.object(cb,"assess_mechanism",return_value={
                  "tier_ceiling":"Tier 3","quality":"source_correlated_model_overlap"}),
              patch.object(cb,"quote_refresh",return_value=(fresh(),[]))):
            return cb.build(rows,queue,packet,DATE,now=NOW,fetch=injury_source,**kw)

    def test_historical_5of5_and_live_market_produce_conditional_only(self):
        rows,queue,packet=setup()
        original=copy.deepcopy(rows)
        out=self.full(rows,queue,packet)
        self.assertEqual(out["status"],"conditional_tier3_available",out)
        self.assertEqual(out["conditional_count"],1)
        hit=out["conditional_picks"][0]
        self.assertEqual(hit["tier"],"Conditional Tier 3")
        self.assertGreaterEqual(hit["modeled_win_probability"],.70)
        self.assertEqual(hit["verification_status"],"conditional_not_official_active")
        self.assertFalse(hit["verified_pick"])
        self.assertFalse(hit["publication_eligible"])
        self.assertTrue(hit["conditional_publishable"])
        self.assertFalse(hit["empirical_hit_rate_certified"])
        self.assertEqual(rows,original)

    def test_below_70_and_missing_historical_evidence_never_qualify(self):
        rows,queue,packet=setup()
        rows[0]["q_grade"]=.64
        rows[0]["q_market"]=.59
        rows[0]["q_market_comparable"]=.59
        out=self.full(rows,queue,packet)
        self.assertEqual(out["conditional_count"],0)
        rows,queue,packet=setup()
        with patch.object(cb,"tendency_check",return_value={
                "status":"unknown","likely_available":False,"played_last_5":None}):
            out=cb.build(rows,queue,packet,DATE,now=NOW)
        self.assertEqual(out["conditional_count"],0)

    def test_out_and_questionable_statuses_veto_without_calling_reviewer(self):
        rows,queue,packet=setup()
        for value in ("out","questionable","doubtful","suspended","inactive"):
            p=copy.deepcopy(packet)
            p["availability"]={"Example Skater":{"status":{"value":value}}}
            out=self.full(rows,queue,p)
            self.assertEqual(out["conditional_count"],0,value)
            self.assertEqual(out["excluded"]["explicit_nonactive_status"],1)

    def test_unsafe_or_stale_price_rejects_even_strong_model_and_research(self):
        rows,queue,packet=setup()
        with (patch.object(cb,"tendency_check",return_value=tendency()),
              patch.object(cb,"machine_review",return_value=(True,None,{})),
              patch.object(cb,"assess_mechanism",return_value={"tier_ceiling":"Tier 3"}),
              patch.object(cb,"quote_refresh",return_value=(None,["CURRENT_MARKET_TIMESTAMP_INVALID"]))):
            out=cb.build(rows,queue,packet,DATE,now=NOW,fetch=injury_source)
        self.assertEqual(out["conditional_count"],0)
        self.assertEqual(out["excluded"]["fresh_same_line_market_missing"],1)

    def test_source_scouting_missing_keeps_unranked(self):
        rows,queue,packet=setup()
        with (patch.object(cb,"tendency_check",return_value=tendency()),
              patch.object(cb,"machine_review",return_value=(False,"MACHINE_DOSSIER_MISSING",{}))):
            out=cb.build(rows,queue,packet,DATE,now=NOW,fetch=injury_source)
        self.assertEqual(out["conditional_count"],0)
        self.assertEqual(out["excluded"]["MACHINE_DOSSIER_MISSING"],1)

    def test_official_active_player_stays_on_separate_verified_route(self):
        rows,queue,packet=setup()
        with (patch.object(cb,"tendency_check",return_value=tendency()),
              patch.object(cb,"status_verified",return_value=(True,None))):
            out=cb.build(rows,queue,packet,DATE,now=NOW,fetch=injury_source)
        self.assertEqual(out["conditional_count"],0)
        self.assertEqual(out["excluded"]["already_active_requires_strict_verified_board"],1)

    def test_started_game_never_eligible(self):
        rows,queue,packet=setup()
        after=datetime(2026,10,28,0,0,tzinfo=timezone.utc)
        self.assertEqual(cb.build(rows,queue,packet,DATE,now=after)["conditional_count"],0)

    def test_unreadable_injury_feed_blocks_all_conditional_publication(self):
        rows,queue,packet=setup()
        with patch.object(cb,"tendency_check",return_value=tendency()):
            board=cb.build(rows,queue,packet,DATE,now=NOW,
                           fetch=lambda *a,**k:{"injuries":[]})
        self.assertEqual(board["conditional_count"],0)
        self.assertEqual(board["excluded"]["LIVE_INJURY_SOURCE_UNAVAILABLE"],1)

    def test_explicit_current_injury_report_vetoes_high_historical_continuity(self):
        rows,queue,packet=setup()
        def injured(*a,**kw):
            return {"injuries":[{"team":{"abbreviation":"BOS"},
                "injuries":[{"athlete":{"displayName":"Example Skater"},
                            "status":"Questionable"}]}]}
        with patch.object(cb,"tendency_check",return_value=tendency()):
            board=cb.build(rows,queue,packet,DATE,now=NOW,fetch=injured)
        self.assertEqual(board["conditional_count"],0)
        self.assertEqual(board["excluded"]["EXPLICIT_CURRENT_INJURY_DESIGNATION"],1)

    def test_no_market_fetch_if_no_quality_qualified(self):
        rows,queue,packet=setup()
        rows[0].update(q_grade=.64,q_market=.59,q_market_comparable=.59)
        def forbidden(*args):raise AssertionError("paid feed should not be called")
        out=cb.build(rows,queue,packet,DATE,now=NOW,quote_fetcher=forbidden)
        self.assertEqual(out["conditional_count"],0)


if __name__=="__main__":
    unittest.main()
