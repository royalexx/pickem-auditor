"""Independent resealed-payload challenges; all data synthetic."""
import copy
import unittest
from golden_v2 import pregame, j_scenarios, distribution, original_offer
from test_v2_contracts import evaluation
from v2.nba_architecture.v2_contracts import (seal, validate_scenarios,
    validate_distribution, validate_evaluation, marginal_from_joint, offer_view,
    ContractError)


def edit(obj, change):
    obj = copy.deepcopy(obj)
    obj.pop('content_hash')
    change(obj)
    return seal(obj)


class IndependentFinal(unittest.TestCase):
    def setUp(self):
        self.p = pregame('original_prospective', with_offer=True)
        self.j = j_scenarios(self.p)

    def reject_scenario(self, change):
        with self.assertRaises(ContractError):
            validate_scenarios(edit(self.j, change), self.p)

    def test_shared_miss_cannot_generate_two_rebounds(self):
        def change(j):
            sc = j['scenarios'][0]
            a, b = sc['players'][1], sc['players'][6]
            a['stats'].update(two_pa=1, fga=1, oreb=1, rebounds=1, pr=1, ra=1, pra=1)
            b['stats'].update(dreb=1, rebounds=1, pr=1, ra=1, pra=1)
        self.reject_scenario(change)

    def test_assist_cannot_be_on_own_only_field_goal(self):
        def change(j):
            st = j['scenarios'][0]['players'][0]['stats']
            st.update(assists=1, pa=3, ra=1, pra=3)
        self.reject_scenario(change)

    def test_joint_conditioning_cannot_be_relabeled(self):
        d = marginal_from_joint(self.j, self.p, self.p['players'][0]['player_id'],
                                'points', '2026-11-16T23:03:00Z', 42)
        d = edit(d, lambda x: x.update(conditioning='conditional_on_participation'))
        with self.assertRaises(ContractError):
            validate_distribution(d, self.p, self.j)

    def test_joint_ess_cannot_be_inflated(self):
        d = marginal_from_joint(self.j, self.p, self.p['players'][0]['player_id'],
                                'points', '2026-11-16T23:03:00Z', 42)
        def change(d):
            d['numerical'].update(effective_sample_size=2,
                zero_event_95_upper_bound=1-.05**.5)
        with self.assertRaises(ContractError):
            validate_distribution(edit(d, change), self.p, self.j)

    def test_push_cannot_hide_by_omitting_line(self):
        d = distribution(self.p)
        q = edit(original_offer(self.p), lambda x: x.update(line=2))
        v = offer_view(d, q, self.p, '2026-11-16T23:03:00Z')
        e = evaluation(d, v, status='settled', actual=2, line=None)
        with self.assertRaises(ContractError):
            validate_evaluation(e, d, v)

    def test_valid_same_draw_remains_valid(self):
        self.assertTrue(validate_scenarios(self.j, self.p))
