"""Red-to-green G0 remediation closure tests on the research contract only.

These are implementation-authored regression tests, not a substitute for P0I's
separate independent technical reviewer or for certified original source truth.
"""
import copy
import unittest

from golden_v2 import pregame, original_offer, distribution, j_scenarios
from v2.nba_architecture.v2_contracts import (
    ContractError, seal, validate_evaluation, validate_offer_view,
    validate_distribution, offer_view, marginal_from_joint,
)

def reseal(obj, fn):
    raw=copy.deepcopy(obj)
    raw.pop("content_hash")
    fn(raw)
    return seal(raw)

def evaluation(d, v, *, state="settled", actual=0,
               participation="PLAYED_ZERO_MINUTES", void_basis=None, line=None):
    return seal({
        "schema": d["schema"], "kind": "evaluation",
        "distribution_sha256": d["content_hash"],
        "offer_view_sha256": v["content_hash"] if v is not None else None,
        "status": state, "actual": actual, "revision": 1,
        "supersedes_evaluation_sha256": None,
        "official_source_sha256": ("a" * 64 if state in ("settled", "push") else None),
        "participation": participation, "void_basis": void_basis,
        "contract_line": line, "game_id": d["game_id"],
        "event_start_at": d["event_start_at"],
        "evaluated_at": "2026-11-17T03:00:00Z",
    })

class P0RClosureTests(unittest.TestCase):
    def test_original_quote_line_is_a_required_offer_view_field(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=original_offer(p)
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        self.assertEqual(v["contract_line"],1.5)
        self.assertIsNone(v["product_terms_sha256"])
        self.assertTrue(validate_offer_view(v,d,q,p))

    def test_original_quote_line_swap_is_rejected(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=original_offer(p)
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        with self.assertRaisesRegex(ContractError,"OFFER_VIEW_CONTRACT_LINE_MISMATCH"):
            validate_offer_view(reseal(v,lambda x:x.update(contract_line=2)),d,q,p)

    def test_valid_quote_bound_push_does_not_override_original_line(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=original_offer(p)
        q=reseal(q,lambda x:x.update(line=2))
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        e=evaluation(d,v,state="push",actual=2,participation="PLAYED",line=2)
        self.assertTrue(validate_evaluation(e,d,v))

    def test_attached_original_product_terms_allow_explicit_hash_bound_void(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=original_offer(p)
        # A fabricated terms fixture: exercises only identity & integrity,
        # not a claim that the bookmaker actually offered these terms.
        q=reseal(q,lambda x:x.update(payout_terms={
            "synthetic_fixture_void_clause":"DNP is void in this fictional test"
        }))
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        self.assertIsNotNone(v["product_terms_sha256"])
        e=evaluation(d,v,state="void",actual=None,participation="DNP",
                     void_basis="original_terms_sha256:"+v["product_terms_sha256"])
        self.assertTrue(validate_evaluation(e,d,v))

    def test_original_product_terms_hash_swap_is_rejected(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=reseal(original_offer(p),lambda x:x.update(payout_terms={"fictional":"void"}))
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        with self.assertRaisesRegex(ContractError,"OFFER_VIEW_PRODUCT_TERMS_MISMATCH"):
            validate_offer_view(reseal(v,lambda x:x.update(product_terms_sha256="f"*64)),d,q,p)

    def test_void_mismatched_product_terms_digest_rejected(self):
        p=pregame("original_prospective",with_offer=True)
        d=distribution(p)
        q=reseal(original_offer(p),lambda x:x.update(payout_terms={"fictional":"void"}))
        v=offer_view(d,q,p,"2026-11-16T23:03:00Z")
        e=evaluation(d,v,state="void",actual=None,participation="DNP",
                     void_basis="original_terms_sha256:"+"f"*64)
        with self.assertRaisesRegex(ContractError,"VOID_TERMS_HASH_MISMATCH"):
            validate_evaluation(e,d,v)

    def test_played_zero_minute_settled_zero_is_not_dnp(self):
        p=pregame("original_prospective")
        d=distribution(p)
        e=evaluation(d,None,state="settled",actual=0,
                     participation="PLAYED_ZERO_MINUTES")
        self.assertTrue(validate_evaluation(e,d))

    def test_j_derived_offer_view_requires_real_scenario_bundle(self):
        p=pregame("original_prospective",with_offer=True)
        j=j_scenarios(p)
        d=marginal_from_joint(j,p,p["players"][0]["player_id"],
            "points","2026-11-16T23:03:00Z",42)
        q=original_offer(p)
        with self.assertRaisesRegex(ContractError,"J_SCENARIO_CONTEXT_REQUIRED"):
            offer_view(d,q,p,"2026-11-16T23:04:00Z")
        v=offer_view(d,q,p,"2026-11-16T23:04:00Z",j)
        self.assertTrue(validate_offer_view(v,d,q,p,j))
        self.assertTrue(validate_distribution(d,p,j))

if __name__=="__main__":
    unittest.main()
