"""P0I challenge suite: independent *cases*, NOT independent *reviewer*.
Runs against exact frozen P0R candidate source; never modifies implementation.
Tests intentionally assert intended G0 invariants even when current code accepts
invalid state. A failure indicates a concrete negative case the boundary missed.
"""
import copy
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from golden_v2 import pregame, distribution, j_scenarios, game_state, opportunity, original_offer
from v2.nba_architecture.v2_contracts import (
    ContractError, VERSION, seal, receipt, freeze_once, verify,
    validate_pregame, validate_distribution, validate_offer_view,
    validate_offer, validate_evaluation, validate_scenarios,
    threshold_triplet, marginal_from_joint, seed_for,
)
from v2.nba_architecture.families_v2 import (
    validate_game_state, validate_opportunity, validate_integration,
)

def mutate(obj, fn):
    x = copy.deepcopy(obj)
    x.pop("content_hash", None)
    fn(x)
    return seal(x)

def reissue(obj, **changes):
    x = copy.deepcopy(obj)
    x.pop("receipt_sha256")
    x.update(changes)
    return receipt(x)

def eval_record(d, *, offer=None, status="settled", actual=2,
                participation="PLAYED", line=None, basis=None):
    return seal({
        "schema": VERSION, "kind": "evaluation",
        "distribution_sha256": d["content_hash"],
        "offer_view_sha256": offer["content_hash"] if offer else None,
        "status": status, "actual": actual, "revision": 1,
        "supersedes_evaluation_sha256": None,
        "official_source_sha256": "9" * 64 if status in ("settled","push") else None,
        "participation": participation, "void_basis": basis,
        "contract_line": line,
        "game_id": d["game_id"], "event_start_at": d["event_start_at"],
        "evaluated_at": "2026-11-17T04:00:00Z",
    })

class P0IAdversarial(unittest.TestCase):
    def rejects(self, method, *args):
        with self.assertRaises(ContractError):
            method(*args)

    def test_01_historical_proxy_cannot_promote_to_original(self):
        p = pregame()
        self.rejects(validate_pregame, mutate(p, lambda x:
            x.update(source_profile="original_prospective",certification="ORIGINAL_SOURCE_SHADOW")))

    def test_02_historical_target_game_same_date_rejected(self):
        p = pregame()
        def change(x):
            s=x["sources"][0]
            x["sources"][0]=reissue(s,historical_game_date=x["decision_local_date"])
            x["features"][0]["source_receipt_sha256"]=x["sources"][0]["receipt_sha256"]
        self.rejects(validate_pregame, mutate(p, change))

    def test_03_original_future_retrieval_not_authorized(self):
        p = pregame("original_prospective")
        def change(x):
            x["sources"][0]=reissue(x["sources"][0],retrieved_at="2026-11-16T23:00:01Z")
            x["features"][0]["source_receipt_sha256"]=x["sources"][0]["receipt_sha256"]
        self.rejects(validate_pregame,mutate(p,change))

    def test_04_unknown_publication_remains_null_and_admitted(self):
        p=pregame("original_prospective")
        self.assertIsNone(p["sources"][0]["provider_published_at"])
        self.assertTrue(validate_pregame(p))

    def test_05_training_cutoff_after_input_freeze_rejected(self):
        p=pregame()
        self.rejects(validate_pregame,mutate(p,lambda x:x.update(
            training_cutoff_at="2022-10-19T23:05:00Z")))

    def test_06_late_source_revision_cannot_backdate_clock(self):
        p=pregame("original_prospective")
        def change(x):
            first=x["sources"][0]
            later=reissue(first,source_revision=2,
                          supersedes_receipt_sha256=first["receipt_sha256"],
                          retrieved_at="2026-11-16T20:00:00Z")
            x["sources"].append(later)
        self.rejects(validate_pregame, mutate(p,change))

    def test_07_offer_free_four_stats_are_complete(self):
        p=pregame()
        self.assertEqual(p["original_offer_count"],0)
        for stat in ("points","rebounds","assists","threes"):
            self.assertTrue(validate_distribution(distribution(p,stat),p))

    def test_08_original_offer_rejects_raw_sha_swap(self):
        p=pregame("original_prospective",with_offer=True)
        o=original_offer(p)
        self.rejects(validate_offer,mutate(o,lambda x:
            x.update(raw_quote_sha256="8"*64)),p)

    def test_09_offer_view_rejects_wrong_game_id_even_resealed(self):
        from v2.nba_architecture.v2_contracts import offer_view
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=original_offer(p)
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        swapped=mutate(v,lambda x:x.update(game_id="espn:game:other"))
        self.rejects(validate_offer_view,swapped,d,q,p)

    def test_10_threshold_half_point_independent_reference(self):
        law=[{"value":0,"mass":0.2},{"value":2,"mass":0.3},{"value":4,"mass":0.5}]
        self.assertEqual(threshold_triplet(law,2.0),
                         {"over":0.5,"under":0.2,"push":0.3})
        self.assertEqual(threshold_triplet(law,2.5),
                         {"over":0.5,"under":0.5,"push":0})

    def test_11_j_pmf_cannot_change_without_scenario_reconciliation(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        d=marginal_from_joint(j,p,p["players"][0]["player_id"],
                              "points","2026-11-16T23:03:00Z",42)
        def change(x):
            x["pmf"][0]["mass"]=0.9
            x["pmf"][1]["mass"]=0.1
        forged=mutate(d,change)
        # G0 API must fail closed even if caller forgets optional scenarios param.
        self.rejects(validate_distribution,forged,p)

    def test_12_j_pmf_forgery_is_detected_if_bundle_is_supplied(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        d=marginal_from_joint(j,p,p["players"][0]["player_id"],
                              "points","2026-11-16T23:03:00Z",42)
        forged=mutate(d,lambda x:(x["pmf"][0].update(mass=.9),x["pmf"][1].update(mass=.1)))
        self.rejects(validate_distribution,forged,p,j)

    def test_13_monte_carlo_uncertainty_ess_reference(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        d=marginal_from_joint(j,p,p["players"][0]["player_id"],
                              "points","2026-11-16T23:03:00Z",42)
        self.assertAlmostEqual(d["numerical"]["effective_sample_size"],1/(.4**2+.6**2))
        self.assertAlmostEqual(d["numerical"]["zero_event_95_upper_bound"],
                                1-.05**(1/d["numerical"]["effective_sample_size"]))

    def test_14_negative_probability_mass_rejected(self):
        p=pregame()
        d=distribution(p)
        forged=mutate(d,lambda x:(x["pmf"][0].update(mass=-.1),
                                  x["pmf"][1].update(mass=1.1)))
        self.rejects(validate_distribution,forged,p)

    def test_15_duplicated_player_in_shared_game_rejected(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        forged=mutate(j,lambda x:x["scenarios"][0]["players"][1].update(
            player_id=x["scenarios"][0]["players"][0]["player_id"]))
        self.rejects(validate_scenarios,forged,p)

    def test_16_illegal_overtime_team_minutes_rejected(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        def change(x):
            sc=x["scenarios"][0]
            sc["overtime_periods"]=1
            x["game_state_witness"][sc["scenario_id"]]["overtime_periods"]=1
        self.rejects(validate_scenarios,mutate(j,change),p)

    def test_17_physical_rebounds_with_zero_missed_shots_rejected(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        def change(x):
            a=x["scenarios"][0]["players"][1]["stats"]
            a["rebounds"]=1
            a["dreb"]=1
            a["ra"]=1
            a["pr"]=1
            a["pra"]=1
        self.rejects(validate_scenarios,mutate(j,change),p)

    def test_18_negative_shooting_account_rejected(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        def change(x):
            a=x["scenarios"][0]["players"][0]["stats"]
            a["two_pm"]=-1
            a["ftm"]=4
        self.rejects(validate_scenarios,mutate(j,change),p)

    def test_19_g_o_j_exact_draw_linkage_rejects_resampling(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        g=game_state(p,j)
        o=opportunity(p,g,j)
        self.assertTrue(validate_integration(j,p,g,o))
        def change(x):
            x["scenarios"][0]["players"][0]["minutes"]=40.0
            x["scenarios"][0]["players"][1]["minutes"]=56.0
        self.rejects(validate_integration,j,p,g,mutate(o,change))

    def test_20_o_unknown_participation_is_not_zero(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        g=game_state(p,j)
        o=opportunity(p,g,j)
        self.assertIsNone(o["players"][0]["participation_probability"])
        self.assertTrue(validate_opportunity(o,p,g))
        def change(x):
            x["players"][0]["participation_probability"]=0
        self.rejects(validate_opportunity,mutate(o,change),p,g)

    def test_21_settled_dnp_cannot_be_misclassified_as_played_zero(self):
        p=pregame("original_prospective")
        d=distribution(p)
        e=eval_record(d,status="settled",actual=0,participation="DNP")
        self.rejects(validate_evaluation,e,d)

    def test_22_push_requires_original_offer_and_contract_line(self):
        p=pregame("original_prospective")
        d=distribution(p)
        e=eval_record(d,status="push",actual=2,participation="PLAYED",line=None)
        self.rejects(validate_evaluation,e,d)

    def test_23_push_must_match_exact_contract_line(self):
        p=pregame("original_prospective",with_offer=True)
        from v2.nba_architecture.v2_contracts import offer_view
        d=distribution(p)
        q=original_offer(p)
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        e=eval_record(d,offer=v,status="push",actual=2,participation="PLAYED",line=2)
        # Real quote line=1.5; an actual 2 cannot be a push.
        self.rejects(validate_evaluation,e,d,v)

    def test_24_void_requires_original_product_terms(self):
        p=pregame("original_prospective")
        d=distribution(p)
        e=eval_record(d,status="void",actual=None,participation="DNP",
                      basis="unsourced free text")
        self.rejects(validate_evaluation,e,d)

    def test_25_immutable_byte_store_detects_conflicting_writes(self):
        p=pregame()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"snap.json"
            freeze_once(path,p)
            raw=path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             hashlib.sha256(raw).hexdigest())
            self.assertEqual(freeze_once(path,p),p["content_hash"])
            alternate=mutate(p,lambda x:x.update(original_offer_count=1))
            self.rejects(freeze_once,path,alternate)

    def test_26_invalid_seed_and_determinism(self):
        expected=int.from_bytes(hashlib.sha256(
            (VERSION+"|943|espn:game:X|synthetic:draw:5|S2").encode()).digest()[:8],"big")
        self.assertEqual(seed_for(943,"espn:game:X","synthetic:draw:5","S2"),expected)
        self.assertEqual(seed_for(943,"espn:game:X","synthetic:draw:5","S2"),expected)
        self.rejects(seed_for,-1,"espn:game:X","synthetic:draw:5","S2")

    def test_27_historical_corrections_cannot_relabel_as_original(self):
        p=pregame()
        def change(x):
            x["sources"][0]=reissue(x["sources"][0],
                 origin="original_capture", asof_basis="observed_before_freeze")
            x["features"][0]["source_receipt_sha256"]=x["sources"][0]["receipt_sha256"]
        self.rejects(validate_pregame,mutate(p,change))

    def test_28_j_derivations_are_not_independent_family_votes(self):
        p=pregame("original_prospective")
        j=j_scenarios(p)
        d=marginal_from_joint(j,p,p["players"][0]["player_id"],
                              "pra","2026-11-16T23:03:00Z",42)
        self.assertEqual(d["pipeline_mode"],"S_O_J")
        self.assertEqual(d["derivation"],"same_draw_primitive_sum")
        self.assertEqual(d["lineage"],j["lineage"])

if __name__=="__main__":
    unittest.main()
