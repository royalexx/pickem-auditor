"""Independent NBA P6 positive/adversarial control suite.

Research only. Deliberately avoids model implementation changes and any historical
boxscore fitting. Run with tests/nba_architecture on sys.path.
"""
import copy
import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from golden_v2 import pregame, distribution, original_offer, golden_cases, receipt, P_EVENT, P_FREEZE
from v2.nba_architecture.v2_contracts import (
    ContractError, seal, verify, freeze_once, validate_pregame,
    validate_distribution, validate_scenarios, validate_evaluation,
    validate_offer, validate_offer_view, offer_view, threshold_triplet,
    seed_for, marginal_from_joint, canonical,
)
from v2.nba_architecture.families_v2 import (
    validate_game_state, validate_opportunity, validate_integration,
)


def reseal(obj, mutate):
    out = copy.deepcopy(obj)
    out.pop("content_hash")
    mutate(out)
    return seal(out)


def reseal_receipt(obj, mutate):
    out = copy.deepcopy(obj)
    out.pop("receipt_sha256")
    mutate(out)
    return receipt(out)


class IndependentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = golden_cases()

    def rejects(self, fn, *args):
        with self.assertRaises(ContractError):
            fn(*args)

    def test_baseline_full_graph_is_coherent(self):
        z = self.cases["joint_same_draw"]
        self.assertTrue(validate_game_state(z["game_state"], z["pregame"]))
        self.assertTrue(validate_opportunity(z["opportunity"], z["pregame"], z["game_state"]))
        self.assertTrue(validate_integration(z["scenarios"], z["pregame"], z["game_state"], z["opportunity"]))
        self.assertTrue(validate_distribution(z["points"], z["pregame"], z["scenarios"]))

    def test_duplicate_player_even_if_distinct_team_is_rejected(self):
        p = pregame()
        self.rejects(validate_pregame, reseal(p, lambda x: x["players"][9].update(player_id=x["players"][0]["player_id"])))

    def test_wrong_player_team_in_prediction_is_rejected(self):
        p = pregame()
        d = distribution(p)
        self.rejects(validate_distribution, reseal(d, lambda x: x.update(team_id=p["team_ids"][1])), p)

    def test_swapped_source_receipt_is_rejected(self):
        p = pregame()
        broken = reseal(p, lambda x: x["features"][0].update(source_receipt_sha256="e"*64))
        self.rejects(validate_pregame, broken)

    def test_actual_minutes_in_feature_payload_is_rejected_by_closed_keys(self):
        p = pregame("original_prospective")
        broken = reseal(p, lambda x: x["features"][0].update(target_game_actual_minutes=40))
        self.rejects(validate_pregame, broken)

    def test_model_trained_after_freeze_is_rejected(self):
        p = pregame()
        d = distribution(p, mode="S_ONLY")
        broken = reseal(d, lambda x: x["lineage"]["S"].update(training_cutoff_at=p["event_start_at"]))
        self.rejects(validate_distribution, broken, p)

    def test_post_event_feature_uses_original_clock_and_is_rejected(self):
        p = pregame("original_prospective")
        late = reseal(p, lambda x: x["features"][0].update(available_at=P_EVENT))
        self.rejects(validate_pregame, late)

    def test_late_retrieval_rejected_even_with_early_header_claim(self):
        p = pregame("original_prospective")
        def mutate(x):
            r = x["sources"][0]
            new = reseal_receipt(r, lambda y: y.update(retrieved_at=P_EVENT,
                provider_published_at="2026-11-16T20:00:00Z",
                publication_evidence="source_header_claim"))
            x["sources"][0] = new
            x["features"][0]["source_receipt_sha256"] = new["receipt_sha256"]
        self.rejects(validate_pregame, reseal(p, mutate))

    def test_prospective_no_retroactive_promotion_of_historical_proxy(self):
        p = pregame()
        corrupted = reseal(p, lambda x: x.update(source_profile="original_prospective",
                                               certification="ORIGINAL_SOURCE_SHADOW"))
        self.rejects(validate_pregame, corrupted)

    def test_missing_utc_offset_is_rejected(self):
        p = pregame()
        self.rejects(validate_pregame, reseal(p, lambda x: x.update(forecast_at="2022-10-19T23:01:00")))

    def test_orphan_quote_in_historical_proxy_rejected(self):
        h = pregame()
        q = original_offer(pregame("original_prospective", with_offer=True))
        self.rejects(validate_offer, q, h)

    def test_quote_bound_to_another_player_is_rejected(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        altered = reseal(q, lambda x: x.update(player_id=p["players"][1]["player_id"]))
        d = distribution(p)
        self.rejects(validate_offer_view, offer_view(d,q,p,"2026-11-16T23:03:00Z"), d, altered, p)

    def test_shooting_overconversion_rejected_in_one_scenario(self):
        z = self.cases["joint_same_draw"]
        broken = reseal(z["scenarios"], lambda x: x["scenarios"][0]["players"][0]["stats"].update(two_pa=0))
        self.rejects(validate_scenarios, broken, z["pregame"])

    def test_team_assists_over_field_goals_rejected(self):
        z = self.cases["joint_same_draw"]
        def mutate(x):
            st=x["scenarios"][0]["players"][1]["stats"]
            st["assists"]=3; st["pa"]=3; st["ra"]=3; st["pra"]=3
        self.rejects(validate_scenarios, reseal(z["scenarios"], mutate), z["pregame"])

    def test_combination_must_come_from_same_draw(self):
        z = self.cases["joint_same_draw"]
        self.assertEqual(z["pra"]["pmf"], [{"value":2,"mass":.4},{"value":3,"mass":.6}])
        broken = reseal(z["scenarios"], lambda x: x["scenarios"][1]["players"][0]["stats"].update(pra=100))
        self.rejects(validate_scenarios, broken, z["pregame"])

    def test_minute_conservation_rejects_extra_overtime_player_minutes(self):
        z = self.cases["joint_same_draw"]
        broken = reseal(z["scenarios"], lambda x: x["scenarios"][0]["players"][0].update(minutes=49))
        self.rejects(validate_scenarios, broken, z["pregame"])

    def test_valid_five_minute_overtime_has_265_minutes_each_team(self):
        z=self.cases["joint_same_draw"]
        def mutate(x):
            sc=x["scenarios"][0]
            sc["overtime_periods"]=1
            x["game_state_witness"][sc["scenario_id"]]["overtime_periods"]=1
            for player in sc["players"]:
                if player["participation"]=="PLAYED":
                    player["minutes"]=53.0
            x["opportunity_witness"][sc["scenario_id"]]=[
                {k:p[k] for k in ("player_id","team_id","minutes","participation")}
                for p in sc["players"]]
        j=reseal(z["scenarios"],mutate)
        self.assertTrue(validate_scenarios(j,z["pregame"]))
        sc=j["scenarios"][0]
        self.assertEqual([sum(v["minutes"] for v in sc["players"] if v["team_id"]==team)
                          for team in z["pregame"]["team_ids"]], [265,265])

    def test_corrupted_j_scenario_hash_rejected_when_bound(self):
        z = self.cases["joint_same_draw"]
        d = reseal(z["points"], lambda x: x.update(scenario_bundle_sha256="d"*64))
        self.rejects(validate_distribution, d, z["pregame"], z["scenarios"])

    def test_negative_probability_mass_is_rejected(self):
        p= pregame()
        d = distribution(p)
        broken = reseal(d, lambda x: x["pmf"][0].update(mass=-.25))
        self.rejects(validate_distribution, broken, p)

    def test_integer_support_and_unique_buckets_enforced(self):
        p= pregame()
        d = distribution(p)
        broken = reseal(d, lambda x: x["pmf"][1].update(value=0))
        self.rejects(validate_distribution, broken, p)

    def test_over_under_push_complement_from_a_single_law(self):
        pmf=[{"value":0,"mass":.25},{"value":2,"mass":.75}]
        self.assertEqual(threshold_triplet(pmf,0),{"over":.75,"under":0,"push":.25})
        self.assertEqual(threshold_triplet(pmf,1.5),{"over":.75,"under":.25,"push":0})
        self.assertEqual(threshold_triplet(pmf,2),{"over":0,"under":.25,"push":.75})

    def test_deterministic_seed_respects_full_identity(self):
        x=seed_for(17,"event:A","draw:001","S:v1")
        self.assertEqual(x,seed_for(17,"event:A","draw:001","S:v1"))
        self.assertNotEqual(x,seed_for(17,"event:B","draw:001","S:v1"))
        self.assertNotEqual(x,seed_for(17,"event:A","draw:002","S:v1"))

    def test_seal_matches_separate_sha256_implementation(self):
        p=pregame()
        raw={k:v for k,v in p.items() if k!="content_hash"}
        independently=hashlib.sha256(json.dumps(raw,sort_keys=True,
                         ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        self.assertEqual(independently,p["content_hash"])

    def test_freeze_once_blocks_conflicting_second_write(self):
        p=pregame()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"snap.json"
            freeze_once(path,p)
            before=path.read_bytes()
            changed=reseal(p,lambda x:x.update(original_offer_count=3))
            self.rejects(freeze_once,path,changed)
            self.assertEqual(before,path.read_bytes())

    def test_s_o_j_are_upstream_stages_not_three_probability_voters(self):
        p=pregame()
        for mode in ("S_ONLY","S_O"):
            d=distribution(p,mode=mode)
            self.assertTrue(validate_distribution(d,p))
            self.assertEqual(d["lineage"]["J"],None)
        z=self.cases["joint_same_draw"]
        self.assertEqual(z["points"]["pipeline_mode"],"S_O_J")
        self.assertEqual(set(z["points"]["lineage"]),{"S","O","G","J"})


if __name__=="__main__":
    unittest.main()
