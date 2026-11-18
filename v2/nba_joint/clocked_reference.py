"""Finite score PMFs and fixed-latent checkpoint normalizer."""
from bisect import bisect_left, bisect_right
from math import fsum, prod

import numpy as np


def slot_scores(opener, follow, last, unit=float):
    """Vectors index 0–3 points for each FG opportunity, ignoring assists."""
    p22, p76 = unit('0.22'), unit('0.76')
    turnover, ordinary_ft, penalty, fg = map(unit, ('0.12', '0.12', '0.02', '0.74'))
    values = [unit('0')] * 7
    values[0] += turnover

    def add_fg(prob, points, shot):
        for scored, mass in enumerate(shot):
            if scored:
                values[points + scored] += prob * mass
            else:
                values[points] += prob * mass * (1 - p22)
                for extra, extra_mass in enumerate(last):
                    values[points + extra] += prob * mass * p22 * extra_mass

    add_fg(fg, 0, opener)
    for first_made in (0, 1):
        first_mass = p76 if first_made else 1 - p76
        add_fg(penalty * first_mass, first_made, follow)
        values[first_made + 1] += ordinary_ft * first_mass * p76
        miss = ordinary_ft * first_mass * (1 - p76)
        values[first_made] += miss * (1 - p22)
        for extra, extra_mass in enumerate(last):
            values[first_made + extra] += miss * p22 * extra_mass
    return values


def checkpoint_normalizer(plan, latents):
    """Score-independent stages factor at the required tied checkpoints."""
    teams = plan['teams']
    starts = {t: [row['start'] * 60 for row in plan['stints'][t]] for t in teams}

    def shot(team, clock, terminal=False):
        index = (bisect_left if terminal else bisect_right)(starts[team], clock) - 1
        ids = plan['stints'][team][index]['lineup']
        weights = [latents[p]['shooter'] for p in ids]
        total = fsum(weights)
        if not total:
            weights, total = [1] * len(ids), len(ids)
        two = fsum(w / total * (1 - latents[p]['three_attempt']) * .5
                   for p, w in zip(ids, weights))
        three = fsum(w / total * latents[p]['three_attempt'] * latents[p]['three_conversion']
                     for p, w in zip(ids, weights))
        return [1 - two - three, 0., two, three]

    distribution, zero, blocks = np.array([1.]), 0, []
    for period in plan['periods']:
        first = teams.index(period['starter'])
        for i, end in enumerate(period['ends']):
            which = (first + i) % 2
            team = teams[which]
            pmf = slot_scores(shot(team, end - 4), shot(team, end - 2), shot(team, end, True))
            distribution = np.convolve(distribution, pmf if which == 0 else pmf[::-1])
            if which:
                zero += len(pmf) - 1
        if period['number'] >= 4:
            final = period['number'] == len(plan['periods'])
            mass = fsum(distribution)
            accepted = (fsum(distribution[:zero]) + fsum(distribution[zero + 1:])
                        if final else float(distribution[zero]))
            blocks.append({'checkpoint_period': period['number'], 'mass_error': abs(mass - 1),
                           'acceptance_probability': accepted})
            distribution, zero = np.array([1.]), 0
    return {'blocks': blocks, 'Z': prod(b['acceptance_probability'] for b in blocks)}
