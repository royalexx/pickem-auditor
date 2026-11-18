"""Versioned research-only forward possession process."""
from bisect import bisect_left, bisect_right
from math import fsum, isfinite

from v2.nba_architecture.v2_contracts import ContractError, req
from v2.nba_joint.common import rng_for

LAW = 'NBA-J-CLOCKED-POSSESSION/1.0.0-PROPOSAL'
ATTEMPTS = 128
TOL = 1e-7
STATS = ('points', 'rebounds', 'assists', 'threes')
COMBOS = {'pr': ('points', 'rebounds'), 'pa': ('points', 'assists'),
          'ra': ('rebounds', 'assists'), 'pra': ('points', 'rebounds', 'assists')}


def schedule(game, teams, populations, sidecar):
    """Preserve P3 roster order and raw stints, using next starts at tiny seams."""
    ot = game['overtime_periods']
    req(type(ot) is int and 0 <= ot <= 3, 'CLOCKED_OT_SCOPE')
    req(len(teams) == len(set(teams)) == 2, 'CLOCKED_TEAMS')
    length = 48 + 5 * ot
    people = {row['player_id']: row for row in sidecar['players']}
    req(len(people) == len(sidecar['players']) and
        set(people) == {pid for team in teams for pid in populations[team]},
        'CLOCKED_PLAYER_POPULATION')
    stints = {}
    for team in teams:
        roster = populations[team]
        raw = sidecar['teams'][team]['lineup_segments']
        req(bool(raw) and raw[0]['start'] == 0 and
            abs(raw[-1]['end'] - length) <= TOL, 'CLOCKED_ROTATION_ENDPOINTS')
        residence = {pid: [] for pid in roster}
        raw_residence = {pid: [] for pid in roster}
        stints[team] = []
        for i, seg in enumerate(raw):
            a, b = float(seg['start']), float(seg['end'])
            end = float(raw[i + 1]['start']) if i + 1 < len(raw) else float(length)
            ids = seg['player_indices']
            req(0 <= a < end <= length and b > a and abs(b - end) <= TOL and
                len(ids) == len(set(ids)) == 5 and
                all(type(j) is int and 0 <= j < len(roster) for j in ids),
                'CLOCKED_ROTATION_STINT')
            lineup = [roster[j] for j in ids]
            stints[team].append({'start': a, 'end': b, 'effective_end': end,
                                 'lineup': lineup, 'indices': list(ids)})
            for pid in lineup:
                residence[pid].append(end - a)
                raw_residence[pid].append(b - a)
        for pid in roster:
            row = people[pid]
            minutes = row['minutes']
            req(row['participation'] in ('DNP', 'PLAYED', 'PLAYED_ZERO_MINUTES') and
                0 <= minutes <= length and
                (row['participation'] == 'PLAYED' or minutes == 0) and
                (bool(residence[pid]) == (minutes > 0)) and
                abs(fsum(residence[pid]) - minutes) <= TOL and
                abs(fsum(raw_residence[pid]) - minutes) <= TOL, 'CLOCKED_MINUTES')
    projected = [game['possessions_home'], game['possessions_away']]
    req(all(isfinite(x) and x > 0 for x in projected), 'CLOCKED_PROJECTED_PACE')
    pace = fsum(projected) / (120 * length)
    periods, start = [], 0
    for i, seconds in enumerate([720] * 4 + [300] * ot):
        n = 2 * round(seconds * pace)
        req(n > 0 and 6 <= seconds / n <= 20, 'CLOCKED_SLOT_SCOPE')
        front = int(i in (1, 2))
        periods.append({'number': i + 1, 'start': start, 'end': start + seconds,
                        'starter': teams[front],
                        'ends': [start + seconds * k / n for k in range(1, n + 1)]})
        start += seconds
    return {'teams': list(teams), 'players': people, 'stints': stints,
            'periods': periods, 'G_projected_team_possessions': dict(zip(teams, projected)),
            'stoppages': [
                {'team': team, 'clock': seg['start'] * 60, 'kind': 'retained_opponent_last_touch_out_of_bounds'}
                for team in teams for seg in stints[team][1:]
            ]}


def forward(plan, latents, rng):
    """One proposal, retained through the first incompatible checkpoint."""
    teams = plan['teams']
    score = dict.fromkeys(teams, 0)
    starts = {team: [s['start'] * 60 for s in plan['stints'][team]] for team in teams}
    periods = []

    def lineup(team, clock, terminal=False):
        bisect = bisect_left if terminal else bisect_right
        idx = bisect(starts[team], clock) - 1
        return plan['stints'][team][idx]['lineup']

    def weighted(ids, field):
        weights = [latents[p][field] for p in ids]
        target = rng.random() * fsum(weights)
        if not any(weights):
            return ids[int(rng.integers(len(ids)))]
        for pid, weight in zip(ids, weights):
            target -= weight
            if target < 0:
                return pid
        return ids[-1]

    def rebound(clock, terminal, forced_defense=False):
        retained = not forced_defense and rng.random() < .22
        side = offense if retained else defense
        player = None if rng.random() < .08 else weighted(lineup(side, clock, terminal), 'rebounds')
        actions.append([clock, 'rebound', side, player])
        return retained

    def field_goal(clock, terminal):
        on = lineup(offense, clock, terminal)
        player = weighted(on, 'shooter')
        prop = latents[player]
        value = 3 if rng.random() < prop['three_attempt'] else 2
        made = bool(rng.random() < (prop['three_conversion'] if value == 3 else .5))
        assist = None
        if made and rng.random() < .6:
            assist = weighted([p for p in on if p != player], 'assists')
        actions.append([clock, 'fg', player, value, made, assist])
        score[offense] += int(made) * value
        return not made and rebound(clock, terminal, terminal)

    def free_throws(clock, retained):
        player = weighted(lineup(offense, clock), 'shooter')
        made = [bool(rng.random() < .76) for _ in range(1 if retained else 2)]
        actions.append([clock, 'ft', player, made, retained])
        score[offense] += sum(made)
        return retained or (not made[-1] and rebound(clock, False))

    for period in plan['periods']:
        plays, start = [], period['start']
        first = teams.index(period['starter'])
        for i, end in enumerate(period['ends']):
            offense, defense = teams[(first + i) % 2], teams[(first + i + 1) % 2]
            actions = []
            u = rng.random()
            if u < .12:
                actions.append([end - 4, 'turnover'])
            elif u < .24:
                if free_throws(end - 4, False):
                    field_goal(end, True)
            elif u < .26:
                free_throws(end - 4, True)
                if field_goal(end - 2, False):
                    field_goal(end, True)
            elif field_goal(end - 4, False):
                field_goal(end, True)
            close = actions[-1][0]
            plays.append({'offense': offense, 'start': start, 'end': close, 'actions': actions})
            start = close
        if start < period['end']:
            plays.append({'offense': defense, 'start': start, 'end': period['end'],
                          'actions': [[period['end'], 'horn']]})
        final = period['number'] == len(plan['periods'])
        tied = score[teams[0]] == score[teams[1]]
        violated = period['number'] >= 4 and tied == final
        periods.append({'period': period['number'], 'possessions': plays,
                        'score': dict(score)})
        if violated:
            return {'periods': periods, 'status': 'score_checkpoint_failure'}
    return {'periods': periods, 'status': 'accepted'}


def execute(game_id, scenario_id, plan, latents, seed):
    rng = rng_for(seed, game_id, scenario_id, LAW + '/events')
    result = {'law': LAW, 'game_id': game_id, 'scenario_id': scenario_id, 'seed': seed,
              'plan': plan, 'latents': latents, 'attempts': [], 'status': 'exhausted'}
    for _ in range(ATTEMPTS):
        attempt = forward(plan, latents, rng)
        result['attempts'].append(attempt)
        if attempt['status'] == 'accepted':
            result['status'] = 'accepted'
            break
    return result


def tagged_failure(error: ContractError, scenario_id):
    return {'status': 'rejected_preflight', 'code': error.code, 'scenario_id': scenario_id,
            'attempts': []}
