"""End-to-end automated source adjudication: source integrity before Tier ranking."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

import autonomous_investigator as ai
import automated_scouting_review as ar
import pick_verification as pv
import verified_board
import usage_baseline as ub
from test_pick_verification import build, DATE, ID, NOW


def official_games():
    return [{"gameId":f"g{i}","gameDate":f"2026-10-{i:02}",
             "shots":(1 if i <= 10 else 4),
             "toi":("10:00" if i <= 10 else "11:45"),"teamAbbrev":"BOS"}
            for i in range(1,16)]


def fetch_source(url, **kwargs):
    if "/scoreboard?" in url:
        return {"events":[{"id":"pregame-01","date":"2026-10-27T23:00:00Z",
            "status":{"type":{"state":"pre"}},
            "competitions":[{"venue":{"indoor":True},
              "competitors":[{"team":{"abbreviation":"BOS"}},
                             {"team":{"abbreviation":"NSH"}}]}]}]}
    if "/summary?" in url:
        return {"header":{"id":"pregame-01","competitions":[{"status":{"type":{"state":"pre"}}}]},
                "rosters":[{"team":{"abbreviation":"BOS"},
                  "roster":[{"athlete":{"displayName":"Example Player"},
                             "active":True}]}]}
    if "/injuries" in url:return {"injuries":[]}
    if "/news?" in url:return {"articles":[]}
    if "api-web.nhle.com" in url:return {"gameLog":official_games()}
    raise AssertionError("unexpected unapproved request: "+url)


def backed_case(root):
    rows,queue,packet=build()
    entries=[{"id":f"g{i}","date":f"2026-10-{i:02}",
              "value":float(1 if i <= 10 else 4),
              "workload":float(10 if i <= 10 else 11.75)}
             for i in range(1,16)]
    ub.persist([{"sport":"NHL","player_id":"42","stat":"shots on goal",
                 "game_date":DATE,"team":"BOS",
                 "source_url":ai.observation_source(queue["queue"][0],DATE),
                 "retrieved_at":NOW.isoformat(),
                 "usage_observations":entries}],root)
    key=ub.key("NHL","42","shots on goal",DATE)
    packet["scouting"][ID]={"historical_usage":key,
                           "evidence":{"matchup":None,"opportunity":None,
                                       "injuries":None,"game_script":None},
                           "supporting_stats":{"deployment_trends":None,
                                               "line_matching":None},
                           "scenarios":[]}
    rows[0]["inputs"]["scouting"]={"historical_usage":key}
    return rows,queue,packet


class MachineReviewTests(unittest.TestCase):
    def test_machine_embedded_workload_yields_capped_tier3_board(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows,queue,packet=backed_case(root)
            original=copy.deepcopy(rows)
            dossier,updated=ai.investigate(rows,queue,packet,DATE,now=NOW,
                                           fetch=fetch_source,data_root=root)
            self.assertEqual(rows,original)
            self.assertEqual(dossier["counts"]["workload_mechanisms_added"],1)
            self.assertEqual(dossier["counts"]["collector_history_correlated"],1)
            self.assertEqual(len(updated["mechanisms"][ID]),1)
            valid,reason,proof=ar.evaluate(queue["queue"][0],rows[0],updated,
                                           now=NOW,fetch=fetch_source,data_root=root)
            self.assertTrue(valid,reason)
            self.assertFalse(proof["source_read_by_human"])
            self.assertTrue(proof["independent_live_refetch"])
            self.assertEqual(proof["supporting_game_count"],5)
            self.assertEqual(proof["opposing_game_count"],10)
            with patch.object(pv.pm,"evaluate_candidate",return_value={
                    "final_rank":"Tier 2","engine_a":{"reliable":True},
                    "engine_b":{"reliable":True},"blend":{"validated":False},
                    "grade":{"q_model":.74,"q_market_comparable":.72}}):
                result,_=pv.verify(rows,queue,updated,DATE,now=NOW,
                                   auto_review=True,fetch=fetch_source,data_root=root)
            self.assertEqual(result["verified"],1)
            decision=result["decisions"][0]
            self.assertTrue(decision["publication_eligible"])
            self.assertEqual(decision["review_type"],"structured_machine_verification")
            self.assertFalse(decision["source_read_by_human"])
            self.assertEqual(decision["verified_rank"],"Tier 3")
            self.assertEqual(decision["mechanism_evidence"]["tier_ceiling"],"Tier 3")
            self.assertTrue(decision["mechanism_evidence"]["machine_overlap_detected"])
            board=verified_board.build(rows,[result],DATE,now=NOW)
            self.assertEqual(board["rank_counts"]["Tier 3"],1)
            self.assertEqual(board["verified_picks"][0]["candidate_id"],ID)

    def test_real_engine_a_and_b_regrade_without_mocked_probabilities(self):
        import fetch_slate as fs
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows,q,p=backed_case(root)
            games=[{"tie":r["gameId"],"when":r["gameDate"],
                    "value":r["shots"],"workload":(10. if r["toi"]=="10:00" else 11.75)}
                   for r in official_games()]
            summary=fs.summarize_log(games,"shots on goal")
            candidate=rows[0]["inputs"]
            candidate.update(dist=summary["suggested_dist"],
                baseline_mean=summary["baseline_window_mean"],
                baseline_n=summary["baseline_n"],
                recent_mean=summary["recent_mean"],
                recent_n=summary["recent_n"],
                season_n=summary["season_n"],
                observation_ids={**(summary.get("observation_ids") or {}),"prior":[]})
            if candidate["dist"]=="negbin":
                candidate["var_ratio"]=summary["var_ratio"]
            if candidate["dist"]=="normal":
                candidate["sd"]=summary["sd"]
            _,updated=ai.investigate(rows,q,p,DATE,now=NOW,
                                      fetch=fetch_source,data_root=root)
            import research_packet as rp
            import pickem_math as pm
            scoped=rp.candidate_packet(updated,rows[0]["inputs"])
            validated,issues=rp.validate_packet(scoped,now=NOW)
            self.assertEqual(issues,[])
            prepared=rp.merge_into_pipeline(validated,[rows[0]["inputs"]])[0]
            prepared["research_checklist"]="yes"
            with ub.using_directory(root):
                try:
                    pm.evaluate_candidate(prepared,now=NOW)
                except pm.PickemError as exc:
                    self.fail("Real Engine A/B integration: "+str(exc))
            report,_=pv.verify(rows,q,updated,DATE,now=NOW,fetch=fetch_source,
                                auto_review=True,data_root=root)
            decision=report["decisions"][0]
            self.assertTrue(decision["machine_review"]["independent_live_refetch"])
            self.assertTrue(decision["engine_a_reliable"],decision["blockers"])
            self.assertTrue(decision["engine_b_reliable"],decision["blockers"])
            # This fixture has real A/B evidence but no eligible frozen
            # historical-consensus sidecars. A numerical production win
            # probability must not be fabricated from A/B alone.
            self.assertIsNone(decision["verified_model_probability"])
            self.assertFalse(decision["publication_eligible"])
            self.assertTrue(decision["blockers"])
            # A genuinely non-qualifying numeric grade remains blocked; no
            # synthetic probability or Tier label is injected into Engine A/B.
            if not decision["publication_eligible"]:
                self.assertEqual(decision["verified_rank"],"Unranked")
                self.assertTrue(decision["blockers"])

    def test_conditional_source_review_never_approves_missing_roster_in_strict_path(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); rows,queue,packet=backed_case(root)
            _,updated=ai.investigate(rows,queue,packet,DATE,now=NOW,
                                     fetch=fetch_source,data_root=root)
            updated["availability"].pop("Example Player",None)
            item=queue["queue"][0]
            strict,issue,_=ar.evaluate(item,rows[0],updated,now=NOW,
                                         fetch=fetch_source,data_root=root)
            self.assertFalse(strict)
            self.assertEqual(issue,"MACHINE_GAME_SPECIFIC_ACTIVE_STATUS_MISSING")
            tendency={"status":"high_continuity","played_last_5":5,
                      "likely_available":True,"confirmed_active":False,
                      "usable_for_verified_tier":False,
                      "source_snapshot_sha256":"f"*64}
            conditional,issue,proof=ar.evaluate(
                item,rows[0],updated,now=NOW,fetch=fetch_source,
                data_root=root,conditional_tendency=tendency)
            self.assertTrue(conditional,issue)
            self.assertFalse(proof["current_game_active_confirmed"])
            self.assertEqual(proof["availability_basis"],
                             "five_game_historical_tendency_only")
            # The original strict pick verifier must still reject the subject.
            receipt,_=pv.verify(rows,queue,updated,DATE,now=NOW,
                                fetch=None,auto_review=True,data_root=root)
            self.assertEqual(receipt["verified"],0)

    def test_changed_source_body_blocks_machine_grade(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows,q,p=backed_case(root)
            _,p=ai.investigate(rows,q,p,DATE,now=NOW,fetch=fetch_source,data_root=root)
            def altered(url,**kw):
                response=fetch_source(url,**kw)
                if "api-web.nhle.com" in url:
                    response["gameLog"][0]["shots"]=99
                return response
            ok,reason,_=ar.evaluate(q["queue"][0],rows[0],p,now=NOW,
                                    fetch=altered,data_root=root)
            self.assertFalse(ok)
            self.assertEqual(reason,"MACHINE_OFFICIAL_SOURCE_HASH_CHANGED")

    def test_no_source_or_news_conflict_or_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows,q,p=backed_case(root)
            _,p=ai.investigate(rows,q,p,DATE,now=NOW,fetch=fetch_source,data_root=root)
            for patcher,expected in [
                (lambda z:z["_autonomous_investigation"]["candidate_summaries"][ID].update(
                    forecast_sha256="tampered"),"MACHINE_FORECAST_DIGEST_MISMATCH"),
                (lambda z:z["_autonomous_investigation"]["candidate_summaries"][ID].update(
                    news_mention_count=1),"MACHINE_PLAYER_NEWS_REQUIRES_SOURCE_REVIEW"),
                (lambda z:z["_autonomous_investigation"]["candidate_summaries"][ID].update(
                    collector_overlap=0),"MACHINE_INDEPENDENT_COLLECTOR_CORROBORATION_MISSING"),
                (lambda z:z["mechanisms"][ID].clear(),"MACHINE_CAUSAL_MECHANISM_NOT_REPRODUCIBLE"),
                ]:
                modified=copy.deepcopy(p);patcher(modified)
                ok,reason,_=ar.evaluate(q["queue"][0],rows[0],modified,
                                         now=NOW,fetch=fetch_source,data_root=root)
                self.assertFalse(ok)
                self.assertEqual(reason,expected)
            refused,reason,_=ar.evaluate(q["queue"][0],rows[0],p,
                                         now=NOW,fetch=None,data_root=root)
            self.assertFalse(refused)
            self.assertEqual(reason,"MACHINE_LIVE_OFFICIAL_SOURCE_REQUIRED")

    def test_blocked_case_cannot_publish_even_with_mocked_good_probabilities(self):
        rows,q,p=build()
        with patch.object(pv.pm,"evaluate_candidate",return_value={
                "final_rank":"Tier 2","engine_a":{"reliable":True},
                "engine_b":{"reliable":True},"blend":{"validated":True},
                "grade":{"q_model":.6,"q_market_comparable":.58}}):
            outcome,_=pv.verify(rows,q,p,DATE,now=NOW,auto_review=True,
                                fetch=lambda *a,**kw:{"events":[]})
        self.assertEqual(outcome["verified"],0)
        self.assertIn("MACHINE_DOSSIER_MISSING",outcome["decisions"][0]["blockers"])


if __name__ == "__main__":
    unittest.main()
