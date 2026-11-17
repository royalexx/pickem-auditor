"""Deliberately FAILING independent counterexamples.

These tests are kept red on a DRAFT QA branch. Do NOT fix underlying forecasting
mathematics in this workstream. Each assertion states a desired fail-closed
invariant that the frozen v2 producer contract does not yet enforce.
"""
import copy
import unittest
from golden_v2 import pregame, distribution, j_scenarios, receipt
from v2.nba_architecture.v2_contracts import (
    VERSION, ContractError, seal, validate_pregame,
    validate_distribution, validate_scenarios, validate_evaluation,
)


def reseal(obj, mutate):
    copy_obj=copy.deepcopy(obj)
    copy_obj.pop("content_hash")
    mutate(copy_obj)
    return seal(copy_obj)


def new_receipt(r, mutate):
    out=copy.deepcopy(r)
    out.pop("receipt_sha256")
    mutate(out)
    return receipt(out)


class GateCounterexamples(unittest.TestCase):
    def test_revision_two_without_verifiable_parent_must_not_pass(self):
        """Raw source correction SHA refers to no provided auditable parent."""
        p=pregame()
        def corrupt(x):
            r=x["sources"][0]
            x["sources"][0]=new_receipt(r,lambda y:y.update(
                source_revision=2, supersedes_receipt_sha256="d"*64))
            x["features"][0]["source_receipt_sha256"]=x["sources"][0]["receipt_sha256"]
        out=reseal(p,corrupt)
        with self.assertRaises(ContractError):
            validate_pregame(out)

    def test_out_player_must_not_appear_in_joint_draw(self):
        """An independently declared OUT roster state should not silently play."""
        p=pregame("original_prospective")
        p=reseal(p,lambda x:x["players"][0].update(availability="out"))
        j=j_scenarios(p)  # Construct legitimate hashes against modified pregame
        self.assertEqual(j["scenarios"][0]["players"][0]["participation"],"PLAYED")
        with self.assertRaises(ContractError):
            validate_scenarios(j,p)

    def test_joint_distribution_must_not_pass_without_same_draw_witness(self):
        """A forged J PMF matches its hashes but NOT the underlying joint draws."""
        p=pregame("original_prospective")
        j=j_scenarios(p)
        from v2.nba_architecture.v2_contracts import marginal_from_joint
        good=marginal_from_joint(j,p,p["players"][0]["player_id"],
                                 "points","2026-11-16T23:03:00Z",42)
        forged=reseal(good,lambda x:x["pmf"].__setitem__(0,
                         {"value":2,"mass":.6}))
        forged=reseal(forged,lambda x:x["pmf"].__setitem__(1,
                         {"value":3,"mass":.4}))
        # This should be rejected even when callers accidentally omit scenarios.
        with self.assertRaises(ContractError):
            validate_distribution(forged,p)

    def test_postgame_dnp_must_not_be_a_settled_played_count(self):
        """DNP and positive official count cannot be simultaneously certified."""
        p=pregame("original_prospective")
        d=distribution(p)
        e=seal({
            "schema":VERSION, "kind":"evaluation",
            "distribution_sha256":d["content_hash"],
            "offer_view_sha256":None,
            "status":"settled","actual":12,"revision":1,
            "supersedes_evaluation_sha256":None,
            "official_source_sha256":"a"*64,
            "participation":"DNP","void_basis":None,
            "contract_line":None,"game_id":d["game_id"],
            "event_start_at":d["event_start_at"],
            "evaluated_at":"2026-11-17T03:00:00Z",
        })
        with self.assertRaises(ContractError):
            validate_evaluation(e,d)


if __name__=="__main__":
    unittest.main()
