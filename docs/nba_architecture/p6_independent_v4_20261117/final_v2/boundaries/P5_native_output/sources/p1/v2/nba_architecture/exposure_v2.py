"""Finite-law feasibility for NBA aggregate exposure; no fitting or sampling.

Find a nonnegative joint measure on physically conserving allocations whose
marginals equal the declared laws (with unknown participation existentially
quantified). G scenario probabilities are constraints, never fitted weights.
This proves aggregate-law compatibility, not chronological rotation realism.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from .v2_contracts import req

MINUTE_TOLERANCE = 1e-7
MASS_TOLERANCE = 1e-12
MAX_SEARCH_NODES = 500_000
MAX_ALLOCATIONS = 50_000
MAX_WITNESS_SOLVES = 256
MAX_TEAM_VARIABLES = 32
MAX_OVERTIME_GROUPS = 64


def validate_exposure_coupling(o, p, g, required_positive=None):
    """Called after ordinary O validation. Legacy diagnostics are not laws."""
    roster = {r['player_id']: r for r in p['players']}
    bounds = {}
    for team in p['team_ids']:
        people = [r for r in o['players'] if r['team_id'] == team]
        if any(r['minutes_law']['family'] != 'discrete_minutes' for r in people):
            continue  # Complete forecast validation separately rejects diagnostics.
        groups = {}
        for sc in g['scenarios']:
            if sc['weight'] > 0:
                groups.setdefault(sc['overtime_periods'], []).append(sc['weight'])
        total = math.fsum(w for weights in groups.values() for w in weights)
        groups = tuple((ot, math.fsum(weights)/total) for ot, weights in sorted(groups.items()))
        players = []
        for person in people:
            r = roster[person['player_id']]
            excluded = r['legal_eligibility'] is False or r['availability'] == 'out'
            probability = 0. if excluded else person['participation_probability']
            support = person['minutes_law']['parameters']['support']
            normalizer = math.fsum(a['mass'] for a in support)
            atoms = tuple(sorted((float(a['minutes']), float(a['mass'])/normalizer) for a in support))
            players.append((probability, atoms))
        by_id = {r['player_id']: i for i, r in enumerate(people)}
        witnesses = set()
        for sc in o['scenarios']:
            if sc['weight'] > 0:
                states = [None] * len(people)
                for r in sc['players']:
                    if r['player_id'] in by_id:
                        states[by_id[r['player_id']]] = (r['participation'], float(r['minutes']))
                witnesses.add((sc['overtime_periods'], tuple(states)))
        constraint = ((by_id[required_positive[0]], required_positive[1])
                      if required_positive is not None and required_positive[0] in by_id else None)
        team_bounds = _check_team(tuple(players), groups, tuple(sorted(witnesses)), constraint)
        bounds.update({person['player_id']: bound for person, bound in zip(people, team_bounds)})
    return bounds


@lru_cache(maxsize=128)
def _check_team(players, groups, witnesses, required_positive=None):
    """Cache pure, immutable numeric inputs only; no hash-only trust shortcuts."""
    req(len(players) <= MAX_TEAM_VARIABLES and len(groups) <= MAX_OVERTIME_GROUPS,
        'O_COUPLING_VERIFICATION_BUDGET')
    # State labels retain DNP versus genuine played-zero in the coupling itself.
    options = []
    for q, atoms in players:
        states = []
        if q is None or q < 1:
            states.append(('DNP', 0.))
        if q is None or q > 0:
            states.extend(('PLAYED' if m > 0 else 'PLAYED_ZERO_MINUTES', m)
                          for m, mass in atoms if mass > 0)
        options.append(tuple(states))
    allocations = []
    nodes = 0
    for group_index, (ot, weight) in enumerate(groups):
        duration = 48 + 5*ot
        pool = 5*duration
        choices = [tuple(s for s in states if s[1] <= duration) for states in options]
        req(all(choices), 'O_LAW_NO_PHYSICAL_STATE')
        low, high = [0.] * (len(players)+1), [0.] * (len(players)+1)
        for i in range(len(players)-1, -1, -1):
            low[i] = low[i+1] + min(s[1] for s in choices[i])
            high[i] = high[i+1] + max(s[1] for s in choices[i])

        def enumerate_allocations(i, elapsed, states):
            nonlocal nodes
            nodes += 1
            req(nodes <= MAX_SEARCH_NODES, 'O_COUPLING_VERIFICATION_BUDGET')
            if elapsed+low[i] > pool+MINUTE_TOLERANCE or elapsed+high[i] < pool-MINUTE_TOLERANCE:
                return
            if i == len(players):
                if abs(math.fsum(s[1] for s in states)-pool) <= MINUTE_TOLERANCE:
                    allocations.append((group_index, tuple(states)))
                    req(len(allocations) <= MAX_ALLOCATIONS, 'O_COUPLING_VERIFICATION_BUDGET')
                return
            for state in choices[i]:
                enumerate_allocations(i+1, elapsed+state[1], states+[state])

        enumerate_allocations(0, 0., [])
    req(bool(allocations), 'O_MINUTE_LAWS_INCOMPATIBLE')
    # Each x column is mass of one conserving state/participation allocation.
    # Unknown participation q_i is an additional [0,1] variable. For a played
    # atom a, marginal mass is q_i*f_i(a); for DNP it is 1-q_i.
    unknown = {i: len(allocations)+k for k, (i, _) in
               enumerate((i, x) for i, x in enumerate(players) if x[0] is None)}
    variable_count = len(allocations)+len(unknown)
    row_indices, col_indices, values, rhs = [], [], [], []

    def row(entries, target):
        index = len(rhs)
        for col, value in entries:
            if value:
                row_indices.append(index); col_indices.append(col); values.append(value)
        rhs.append(target)

    by_group, by_state = {}, {}
    for j, (gi, states) in enumerate(allocations):
        by_group.setdefault(gi, []).append((j, 1.))
        for i, state in enumerate(states):
            by_state.setdefault((i, state), []).append((j, 1.))
    for gi, (_, weight) in enumerate(groups):
        matching = by_group.get(gi, [])
        req(bool(matching), 'O_G_STATE_LAW_INCOMPATIBLE')
        row(matching, weight)
    for i, (q, atoms) in enumerate(players):
        atom_mass = {('PLAYED' if m > 0 else 'PLAYED_ZERO_MINUTES', m): mass
                     for m, mass in atoms}
        for state in options[i]:
            matching = by_state.get((i, state), [])
            # An impossible positive-mass atom must never disappear through LP
            # numerical tolerances, however small its declared probability.
            if q is not None:
                target = 1-q if state[0] == 'DNP' else q*atom_mass[state]
                zero = (q == 1) if state[0] == 'DNP' else (q == 0)
                req(bool(matching) or zero, 'O_MINUTE_LAW_ATOM_UNATTAINABLE')
                req(target > 0 or zero, 'O_COUPLING_NUMERICAL_UNCERTIFIED')
                row(matching, target)
            elif state[0] == 'DNP':
                row(matching+[(unknown[i], 1.)], 1.)
            else:
                if not matching:
                    # f_i(a)>0 with no conserving allocation implies q_i=0,
                    # even when f_i(a) is below the LP coefficient threshold.
                    row([(unknown[i], 1.)], 0.)
                else:
                    row(matching+[(unknown[i], -atom_mass[state])], 0.)
    matrix = coo_matrix((values, (row_indices, col_indices)),
                        shape=(len(rhs), variable_count)).tocsr()
    target = np.asarray(rhs, dtype=float)
    bounds = [(0., 1.)] * variable_count
    if required_positive is not None:
        i, mass = required_positive
        positive_given_played = math.fsum(w for minutes, w in players[i][1] if minutes > 0)
        req(positive_given_played > 0 or mass == 0, 'FORECAST_ZERO_EXPOSURE_POSITIVE_COUNT')
        if i in unknown and mass > 0:
            lower = mass/positive_given_played
            req(lower <= 1+MASS_TOLERANCE, 'FORECAST_COUNT_EXCEEDS_EXPOSURE')
            bounds[unknown[i]] = (min(1., lower), 1.)

    def solve(objective):
        result = linprog(objective, A_eq=matrix, b_eq=target, bounds=bounds,
                         method='highs', options={'primal_feasibility_tolerance': 1e-10,
                                                  'dual_feasibility_tolerance': 1e-10})
        req(result.status != 2, 'O_MINUTE_LAWS_INCOMPATIBLE')
        req(result.success and result.x is not None, 'O_COUPLING_SOLVER_UNCERTIFIED')
        req(np.all(np.isfinite(result.x)) and
            np.max(np.abs(matrix @ result.x-target), initial=0.) <= MASS_TOLERANCE and
            np.min(result.x, initial=0.) >= -MASS_TOLERANCE and
            np.max(result.x, initial=1.) <= 1+MASS_TOLERANCE,
            'O_COUPLING_RESIDUAL_UNCERTIFIED')
        return result.x

    solution = solve(np.zeros(variable_count))
    # A positive-weight sampled joint state must be possible under some compatible
    # coupling. Separate positive solutions may be averaged to support all observed
    # states; their sample frequencies are never equated to law probabilities.
    lookup = {(groups[gi][0], states): j for j, (gi, states) in enumerate(allocations)}
    solves = 0
    for witness in witnesses:
        req(witness in lookup, 'O_DRAW_OUTSIDE_CONSERVING_LAW_SUPPORT')
        j = lookup[witness]
        if solution[j] <= 0:
            solves += 1
            req(solves <= MAX_WITNESS_SOLVES, 'O_COUPLING_VERIFICATION_BUDGET')
            objective = np.zeros(variable_count); objective[j] = -1.
            alternative = solve(objective)
            req(alternative[j] > 0, 'O_DRAW_ZERO_COMPATIBLE_PROBABILITY')
    exposure_bounds = []
    for i, (q, atoms) in enumerate(players):
        if q is None:
            if solution[unknown[i]] >= 1:
                maximum_q = 1.
            else:
                objective = np.zeros(variable_count); objective[unknown[i]] = -1.
                maximum_q = min(1., max(0., solve(objective)[unknown[i]]))
        else:
            maximum_q = q
        positive_given_played = math.fsum(mass for minutes, mass in atoms if minutes > 0)
        exposure_bounds.append((maximum_q, maximum_q*positive_given_played))
    return tuple(exposure_bounds)


def positive_exposure_bound(person, roster, conditioning, compatible_bounds):
    """Necessary P(count>0) bound, before any S likelihood can be trusted."""
    excluded = roster['legal_eligibility'] is False or roster['availability'] == 'out'
    q = 0. if excluded else person['participation_probability']
    if conditioning == 'conditional_on_participation':
        req(q != 0 and compatible_bounds[0] > 0, 'FORECAST_IMPOSSIBLE_PARTICIPATION_CONDITION')
    support = person['minutes_law']['parameters']['support']
    positive = (math.fsum(a['mass'] for a in support if a['minutes'] > 0) /
                math.fsum(a['mass'] for a in support))
    return positive if conditioning == 'conditional_on_participation' else compatible_bounds[1]
