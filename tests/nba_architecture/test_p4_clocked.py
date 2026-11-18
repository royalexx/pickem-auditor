from copy import deepcopy
from fractions import Fraction
from itertools import product
import unittest

from v2.nba_architecture.v2_contracts import ContractError
from v2.nba_joint.clocked import forward, schedule
from v2.nba_joint.clocked_native import prepare_native
from v2.nba_joint.clocked_reference import checkpoint_normalizer, slot_scores
from v2.nba_joint.clocked_replay import reconstruct


class ScriptedRng:
    def __init__(self, values, fallback=.01):
        self.values = iter(values)
        self.fallback = fallback

    def random(self):
        return next(self.values, self.fallback)


def fixture(ot=0):
    rosters = {'h': ['h' + str(i) for i in range(7)],
               'a': ['a' + str(i) for i in range(5)]}
    length = 48 + 5 * ot
    people = [{'player_id': p, 'minutes': length if i < 5 else 0,
               'participation': 'PLAYED' if i < 5 else
               ('DNP' if i == 5 else 'PLAYED_ZERO_MINUTES')}
              for team in rosters.values() for i, p in enumerate(team)]
    sidecar = {'players': people, 'teams': {team: {'lineup_segments': [
        {'start': 0., 'end': float(length), 'player_indices': list(range(5))}
    ]} for team in rosters}}
    g = {'overtime_periods': ot, 'possessions_home': 3 * length,
         'possessions_away': 3 * length}
    plan = schedule(g, list(rosters), rosters, sidecar)
    rates = {p['player_id']: {'shooter': 1., 'rebounds': 1., 'assists': 1.,
                              'three_attempt': 0., 'three_conversion': .4}
             for p in people}
    return plan, rates, g, rosters, sidecar


class TestClockedLaw(unittest.TestCase):
    def test_known_score_pmf_and_normalizer(self):
        F = Fraction
        shot = [F(1, 2), F(0), F(1, 2), F(0)]
        scores = slot_scores(shot, shot, shot, F)
        # Direct Cartesian enumeration draws even the unused transitions.
        truth = [F(0)] * 7
        for category, q in enumerate(map(F, ('0.12', '0.12', '0.02', '0.74'))):
            for a, b, first, last, off in product((False, True), repeat=5):
                chance = q * F('0.76' if a else '0.24') * F('0.76' if b else '0.24')
                chance *= F(1, 4) * F('0.22' if off else '0.78')
                fg_points = 2 if first or (off and last) else 0
                points = [0, int(a) + int(b) + (2 if not b and off and last else 0),
                          int(a) + fg_points, fg_points][category]
                truth[points] += chance
        self.assertEqual(scores, truth)
        self.assertEqual(sum(scores), 1)
        self.assertEqual(sum(scores[6:]), 0)
        plan, rates, *_ = fixture(1)
        # An analytical two-slot-per-period control of the normalizer.
        for period in plan['periods']:
            period['ends'] = [period['start'] + 8, period['start'] + 16]
        totals = [F(1)]
        for _ in range(4):
            nxt = [F(0)] * (len(totals) + len(scores) - 1)
            for i, left in enumerate(totals):
                for j, right in enumerate(scores):
                    nxt[i + j] += left * right
            totals = nxt
        z = sum(x*x for x in totals) * (1 - sum(x*x for x in scores))
        self.assertAlmostEqual(checkpoint_normalizer(plan, rates)['Z'], float(z), places=14)

    def test_single_play_state_machine_and_mutations(self):
        plan, rates, *_ = fixture()
        # Retained penalty miss, then rim miss and offensive team recovery,
        # followed by a made two and a teammate assist.
        rng = ScriptedRng([.25, .01, .99, .01, .99, .99, .01, .01,
                           .01, .99, .01, .01, .01])
        packet = forward(plan, rates, rng)
        self.assertEqual(packet['status'], 'accepted')
        self.assertEqual(packet['periods'][0]['possessions'][0]['actions'],
                         [[6., 'ft', 'h0', [False], True],
                          [8., 'fg', 'h0', 2, False, None],
                          [8., 'rebound', 'h', None],
                          [10., 'fg', 'h0', 2, True, 'h1']])
        totals = reconstruct(plan, packet)
        self.assertEqual(totals['players']['h0']['points'], 2)
        self.assertEqual(totals['players']['h1']['assists'], 1)
        self.assertEqual(totals['teams']['h']['unattributed_oreb'], 1)
        for pid in ('h5', 'h6'):
            self.assertFalse(any(totals['players'][pid].values()))
        for mutator in (
            lambda ev: ev[-1].__setitem__(5, 'h0'),
            lambda ev: ev[-1].__setitem__(5, 'a0'),
            lambda ev: ev[-1].__setitem__(2, 'h5'),
            lambda ev: ev[-1].__setitem__(0, 11),
            lambda ev: ev[2].__setitem__(2, 'a'),
            lambda ev: ev[0][3].append(True),
            lambda ev: ev.pop(2),
        ):
            with self.subTest(mutator=mutator):
                tampered = deepcopy(packet)
                mutator(tampered['periods'][0]['possessions'][0]['actions'])
                with self.assertRaises(ContractError):
                    reconstruct(plan, tampered)

    def test_ot_checkpoints(self):
        plan, rates, *_ = fixture(3)
        all_turnover = forward(plan, rates, ScriptedRng([]))
        self.assertEqual(all_turnover['status'], 'score_checkpoint_failure')
        self.assertEqual(len(all_turnover['periods']), 7)
        reconstruct(plan, all_turnover)
        non_tied = forward(plan, rates, ScriptedRng([.9, .01, .99, .01, .99]))
        self.assertEqual(len(non_tied['periods']), 4)
        self.assertEqual(non_tied['status'], 'score_checkpoint_failure')
        reconstruct(plan, non_tied)

    def test_stoppage_cannot_be_omitted(self):
        _, rates, game, rosters, sidecar = fixture()
        sidecar['teams']['h']['lineup_segments'] = [
            {'start': 0., 'end': 12., 'player_indices': list(range(5))},
            {'start': 12., 'end': 48., 'player_indices': list(range(5))}]
        plan = schedule(game, list(rosters), rosters, sidecar)
        packet = forward(plan, rates, ScriptedRng([]))
        reconstruct(plan, packet)
        plan['stoppages'].clear()
        with self.assertRaisesRegex(ContractError, 'REPLAY_STOPPAGE_LEDGER'):
            reconstruct(plan, packet)

    def test_rotation_gap_and_real_mode_fail(self):
        _, _, game, rosters, sidecar = fixture()
        sidecar['teams']['h']['lineup_segments'] = [
            {'start': 0., 'end': 12., 'player_indices': list(range(5))},
            {'start': 13., 'end': 48., 'player_indices': list(range(5))}]
        with self.assertRaisesRegex(ContractError, 'CLOCKED_ROTATION_STINT'):
            schedule(game, list(rosters), rosters, sidecar)
        with self.assertRaisesRegex(ContractError, 'CLOCKED_REAL_INPUTS_UNADMITTED'):
            prepare_native(None, None, None, None, None, None, None, upstream_root=None)
