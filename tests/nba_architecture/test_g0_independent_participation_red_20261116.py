"""Independent G0 adversarial controls: intentionally RED until O/J participation invariants are enforced.

These tests are not predictive-validation claims. They use the original synthetic
golden fixtures, including authentic code-level SHA resealing of modified payloads.
"""
import copy
import unittest
from golden_v2 import golden_cases, j_scenarios, game_state, opportunity
from v2.nba_architecture.v2_contracts import seal, ContractError
from v2.nba_architecture.families_v2 import (
    validate_opportunity, validate_integration,
)


def reseal(value):
    changed = copy.deepcopy(value)
    changed.pop("content_hash", None)
    return seal(changed)


class IndependentG0ParticipationRed(unittest.TestCase):
    def setUp(self):
        self.case = golden_cases()["joint_same_draw"]
        self.p = self.case["pregame"]
        self.g = self.case["game_state"]
        self.o = self.case["opportunity"]
        self.j = self.case["scenarios"]

    def assert_rejected_at_o_and_j(self, o, j, p=None, g=None):
        p = self.p if p is None else p
        g = self.g if g is None else g
        with self.assertRaises(ContractError):
            validate_opportunity(o, p, g)
        with self.assertRaises(ContractError):
            validate_integration(j, p, g, o)

    def test_synthetic_control_passes(self):
        self.assertTrue(validate_integration(self.j, self.p, self.g, self.o))

    def test_verified_zero_probability_cannot_play_48_minutes(self):
        o = copy.deepcopy(self.o)
        o["players"][0]["participation_evidence"] = "verified_out"
        o["players"][0]["participation_probability"] = 0.0
        o = reseal(o)
        j = copy.deepcopy(self.j)
        j["opportunity_sha256"] = o["content_hash"]
        j = reseal(j)
        self.assert_rejected_at_o_and_j(o, j)

    def test_certain_participation_cannot_dnp_with_positive_weight(self):
        o = copy.deepcopy(self.o)
        o["players"][5]["participation_evidence"] = "independently_estimated"
        o["players"][5]["participation_probability"] = 1.0
        o = reseal(o)
        # The existing synthetic scenario 0 has DNP with weight 0.4.
        j = copy.deepcopy(self.j)
        j["opportunity_sha256"] = o["content_hash"]
        j = reseal(j)
        self.assert_rejected_at_o_and_j(o, j)

    def test_pregame_out_cannot_be_represented_as_played(self):
        p = copy.deepcopy(self.p)
        p["players"][0]["availability"] = "out"
        p = reseal(p)
        j = j_scenarios(p)
        g = game_state(p, j)
        o = opportunity(p, g, j)
        self.assert_rejected_at_o_and_j(o, j, p, g)


if __name__ == "__main__":
    unittest.main()
