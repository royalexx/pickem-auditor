"""Tests for replacing legacy mechanism-count promotion with causal quality."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import mechanism_evidence as me
import pickem_math as pm

NOW=datetime(2026,10,28,12,0,tzinfo=timezone.utc)
ID="NHL|Test Player|shots on goal|over"
ITEM={"candidate_id":ID,"sport":"NHL","stat":"shots on goal",
      "side":"over","opponent":"TOR","team":"BOS"}
def fact(value,url,quote="Official observed source value"):
    return {"fact":"source fact","value":value,"source_url":url,
            "retrieved_at":NOW.isoformat(),"confidence":"confirmed","quote":quote}
def scheme():
    before=fact(10,"https://www.nhl.com/position-matchup")
    after=fact(12,"https://site.api.espn.com/position-matchup")
    opposing=fact(8,"https://www.nhl.com/counterexample")
    return {"event_id":"opponent-scheme-2026-10-28",
            "type":"scheme","supports_side":"over",
            "description":"Team-specific possession chances by position",
            "sources":[before,after],
            "causal_validation":{
                "event_id":"opponent-scheme-2026-10-28",
                "target_stat":"shots on goal","opponent":"TOR",
                "metric":"position_matchup_opportunity_rate",
                "units":"chances per 60", "before":10,"after":12,
                "before_n":10,"after_n":10,
                "before_fact":before,"after_fact":after,
                "counterevidence":opposing}}
def packet(*events):
    return {"mechanisms":{ID:list(events)}}
def assess(p,**kw):
    return me.assess(p,ITEM,now=NOW,review_type="human_attestation",
                     human_reviewed=True,model_inputs={},**kw)
def decide(quality,mechanisms):
    return pm.decide(.60,.59,0,30,mechanisms,market_valid=True,
                     research_checklist=True,mechanism_quality=quality)

class CausalQualityTests(unittest.TestCase):
    def test_measured_primary_source_causal_chain_can_support_tier2(self):
        a=assess(packet(scheme()))
        self.assertEqual(a["tier_ceiling"],"Tier 2")
        self.assertEqual(a["quality"],"quantified_model_incremental_causal_chain")
        self.assertEqual(a["evaluations"][0]["effect_ratio"],.2)
        self.assertEqual(decide(a,1)["final_rank"],"Tier 2")
        self.assertEqual(decide(a,0)["final_rank"],"Tier 2")

    def test_no_sources_many_mechanisms_never_promote(self):
        unverified={"event_id":"x","type":"scheme","supports_side":"over",
                    "description":"Unverified generic mechanism",
                    "sources":[]}
        a=assess(packet(*[dict(unverified,event_id=f"event-{i}") for i in range(20)]))
        self.assertEqual(a["tier_ceiling"],"Watchlist")
        self.assertEqual(decide(a,20)["final_rank"],"Watchlist")

    def test_copied_owner_not_independent(self):
        m=scheme()
        m["sources"][1]["source_url"]="https://api-web.nhle.com/v1/stats"
        m["causal_validation"]["after_fact"]["source_url"]="https://api-web.nhle.com/v1/stats"
        self.assertEqual(assess(packet(m))["tier_ceiling"],"Watchlist")

    def test_wrong_direction_and_stat_and_opponent_block(self):
        for kind in ("direction","stat","opponent"):
            m=scheme()
            if kind=="direction":
                m["causal_validation"]["after"]=8
                m["causal_validation"]["after_fact"]["value"]=8
            elif kind=="stat":
                m["causal_validation"]["target_stat"]="blocked shots"
            else:
                m["causal_validation"]["opponent"]="CAR"
            a=assess(packet(m))
            self.assertEqual(a["tier_ceiling"],"Watchlist",kind)

    def test_stale_or_unquoted_or_missing_counterevidence_block(self):
        for kind in ("stale","quote","counter"):
            m=scheme()
            if kind=="stale":
                m["sources"][0]["retrieved_at"]="2026-10-27T08:00:00Z"
            elif kind=="quote":
                m["causal_validation"]["before_fact"]["quote"]=""
            else:
                m["causal_validation"].pop("counterevidence")
            self.assertEqual(assess(packet(m))["tier_ceiling"],"Watchlist",kind)

    def test_computed_overlap_rejects_self_claimed_independence(self):
        a=me.assess(packet(scheme()),ITEM,now=NOW,
                    review_type="human_attestation",human_reviewed=True,
                    model_inputs={"opponent_factor":1.15})
        self.assertEqual(a["tier_ceiling"],"Watchlist")
        self.assertIn("SCHEME_ALREADY_MODELED",a["evaluations"][0]["reasons"])

    def test_workload_model_overlap_is_not_incremental(self):
        m=scheme();m["type"]="workload"
        a=assess(packet(m))
        self.assertEqual(a["tier_ceiling"],"Watchlist")
        self.assertIn("EMBEDDED_OR_UNRESOLVED_MODEL_INPUT_OVERLAP",
                      a["evaluations"][0]["reasons"])

    def test_human_attestation_missing_is_not_quality(self):
        a=me.assess(packet(scheme()),ITEM,now=NOW,
                    review_type="human_attestation",human_reviewed=False)
        self.assertEqual(a["tier_ceiling"],"Watchlist")

    def test_machine_history_with_valid_proof_only_tier3(self):
        m={"event_id":"observed-15-game-workload-shift","type":"workload",
           "supports_side":"over","sources":[fact({"ratio":1.16},
           "https://api-web.nhle.com/v1/player/42/game-log/20262027/2")]}
        proof={"validated_mechanism":"observed-15-game-workload-shift",
               "independent_live_refetch":True, "source_read_by_human":False,
               "source_payload_sha256":"a"*64, "shared_collector_games":5,
               "supporting_game_count":8,"opposing_game_count":7}
        a=me.assess(packet(m),ITEM,now=NOW,
                    review_type="structured_machine_verification",machine_provenance=proof)
        self.assertEqual(a["tier_ceiling"],"Tier 3")
        self.assertTrue(a["machine_overlap_detected"])
        self.assertEqual(decide(a,1)["final_rank"],"Tier 3")
        self.assertEqual(decide(a,100)["final_rank"],"Tier 3")
        proof["independent_live_refetch"]=False
        b=me.assess(packet(m),ITEM,now=NOW,
                    review_type="structured_machine_verification",machine_provenance=proof)
        self.assertEqual(b["tier_ceiling"],"Watchlist")

    def test_measured_three_owner_strong_chain_can_reach_tier1_ceiling(self):
        m=scheme()
        m["sources"].append(fact(11,"https://www.nba.com/matchup"))
        a=assess(packet(m))
        self.assertEqual(a["tier_ceiling"],"Tier 1")
        self.assertEqual(decide(a,1)["final_rank"],"Tier 1")
        q=deepcopy(a);q["tier_ceiling"]="garbage"
        self.assertEqual(decide(q,30)["final_rank"],"Watchlist")

if __name__=="__main__":
    unittest.main()
