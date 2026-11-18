"""Replay event witnesses using a state machine independent of the generator."""
from v2.nba_architecture.v2_contracts import req

COLUMNS = ('points', 'rebounds', 'assists', 'threes', 'two_pa', 'two_pm', 'three_pa',
           'fta', 'ftm', 'oreb', 'dreb', 'pr', 'pa', 'ra', 'pra')


def reconstruct(plan, witness):
    teams = tuple(plan['teams'])
    required_stops = [
        {'team': team, 'clock': seg['start'] * 60,
         'kind': 'retained_opponent_last_touch_out_of_bounds'}
        for team in teams for seg in plan['stints'][team][1:]
    ]
    req(plan['stoppages'] == required_stops, 'REPLAY_STOPPAGE_LEDGER')
    players = {pid: dict.fromkeys(COLUMNS, 0) for pid in plan['players']}
    table = {t: dict.fromkeys((*COLUMNS, 'possessions', 'unattributed_oreb',
                              'unattributed_dreb', 'turnovers'), 0) for t in teams}
    req(set(witness) == {'periods', 'status'} and
        witness['status'] in ('accepted', 'score_checkpoint_failure') and
        0 < len(witness['periods']) <= len(plan['periods']), 'REPLAY_PERIOD_POPULATION')
    failed = False
    for period, expected in zip(witness['periods'], plan['periods']):
        req(not failed and period['period'] == expected['number'], 'REPLAY_PERIOD_ORDER')
        n = len(expected['ends'])
        req(len(period['possessions']) in (n, n + 1), 'REPLAY_POSSESSION_POPULATION')
        previous = expected['start']
        for i, play in enumerate(period['possessions']):
            offense = teams[(teams.index(expected['starter']) + i) % 2]
            defense = teams[1 - teams.index(offense)]
            req(play['offense'] == offense and play['start'] == previous and
                previous < play['end'] <= expected['end'], 'REPLAY_POSSESSION_CONTROL')
            previous = play['end']
            table[offense]['possessions'] += 1
            events = play['actions']
            if i == n:
                req(events == [[expected['end'], 'horn']] and play['end'] == expected['end'],
                    'REPLAY_HORN')
                continue
            nominal = expected['ends'][i]
            stage, retained, action_clock = 'initial', False, nominal - 4
            for event in events:
                clock, kind, *args = event
                req(clock == action_clock and
                    0 < clock - play['start'] <= 24 and stage != 'terminated',
                    'REPLAY_ACTION_CLOCK')
                terminal = clock == nominal

                def on_court(team, pid):
                    for stint in plan['stints'][team]:
                        start, end = stint['start'] * 60, stint['effective_end'] * 60
                        present = start < clock <= end if terminal else start <= clock < end
                        if present:
                            return pid in stint['lineup'] and plan['players'][pid]['minutes'] > 0
                    return False

                def credit(team, pid, column, count=1):
                    players[pid][column] += count
                    table[team][column] += count

                if kind == 'turnover':
                    req(stage == 'initial' and not args, 'REPLAY_TURNOVER')
                    table[offense]['turnovers'] += 1
                    stage = 'terminated'
                elif kind == 'ft':
                    pid, made, retained = args
                    req(stage == 'initial' and on_court(offense, pid) and
                        type(retained) is bool and type(made) is list and
                        len(made) == (1 if retained else 2) and
                        all(type(x) is bool for x in made), 'REPLAY_FREE_THROWS')
                    credit(offense, pid, 'fta', len(made))
                    credit(offense, pid, 'ftm', sum(made))
                    credit(offense, pid, 'points', sum(made))
                    stage = 'shot' if retained else ('terminated' if made[-1] else 'rebound')
                    if retained:
                        action_clock = nominal - 2
                elif kind == 'fg':
                    pid, value, made, assist = args
                    req(stage in ('initial', 'shot') and type(value) is int and value in (2, 3)
                        and type(made) is bool and on_court(offense, pid)
                        and (assist is None or (made and assist != pid and on_court(offense, assist))),
                        'REPLAY_FIELD_GOAL')
                    credit(offense, pid, 'three_pa' if value == 3 else 'two_pa')
                    if made:
                        credit(offense, pid, 'threes' if value == 3 else 'two_pm')
                        credit(offense, pid, 'points', value)
                        if assist is not None:
                            credit(offense, assist, 'assists')
                    stage = 'terminated' if made else 'rebound'
                elif kind == 'rebound':
                    team, pid = args
                    req(stage == 'rebound' and team in teams and (not terminal or team == defense)
                        and (pid is None or on_court(team, pid)), 'REPLAY_REBOUND')
                    kind = 'oreb' if team == offense else 'dreb'
                    if pid is None:
                        table[team]['unattributed_' + kind] += 1
                    else:
                        credit(team, pid, kind)
                        credit(team, pid, 'rebounds')
                    stage = 'shot' if team == offense else 'terminated'
                    if team == offense:
                        req(0 < nominal - clock <= 14, 'REPLAY_RESET_CLOCK')
                        action_clock = nominal
                else:
                    req(False, 'REPLAY_UNKNOWN_EVENT')
            req(stage == 'terminated' and play['end'] == action_clock,
                'REPLAY_UNRESOLVED_POSSESSION')
        req(previous == expected['end'], 'REPLAY_PERIOD_CLOCK')
        score = {t: table[t]['points'] for t in teams}
        req(period['score'] == score, 'REPLAY_SCORE')
        tied = len(set(score.values())) == 1
        failed = period['period'] >= 4 and tied == (period['period'] == len(plan['periods']))
    req(failed == (witness['status'] == 'score_checkpoint_failure') and
        (failed or len(witness['periods']) == len(plan['periods'])), 'REPLAY_OT_CHECKPOINT')
    for row in (*players.values(), *table.values()):
        row.update(pr=row['points'] + row['rebounds'], pa=row['points'] + row['assists'],
                   ra=row['rebounds'] + row['assists'],
                   pra=row['points'] + row['rebounds'] + row['assists'])
    return {'players': players, 'teams': table}
