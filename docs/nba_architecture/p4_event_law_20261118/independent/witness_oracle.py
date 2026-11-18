"""Independent reconstruction of event and box ledgers from a clocked attempt.

This file imports no P4 generator or owner validator code.
"""
from bisect import bisect_right
from collections import Counter


class WitnessError(ValueError):
    """A witness assertion failed."""


def require(condition, why):
    if not condition:
        raise WitnessError(why)


def rotation(plan, team_of):
    players = plan["players"]
    starts = {}
    require(set(players) == set(team_of), "incorrect roster population")
    total_minutes = plan["periods"][-1]["end"] / 60
    for team, stints in plan["stints"].items():
        duration = Counter()
        raw_duration = Counter()
        require(stints[0]["start"] == 0, "initial lineup gap")
        for i, stint in enumerate(stints):
            a, b, eff = (stint[key] for key in ("start", "end", "effective_end"))
            next_start = stints[i + 1]["start"] if i + 1 < len(stints) else total_minutes
            require(a < b and a < eff == next_start and abs(b - eff) <= 1e-7, "invalid rotation seam")
            require(len(stint["lineup"]) == len(set(stint["lineup"])) == 5, "invalid lineup size")
            for pid in stint["lineup"]:
                require(team_of.get(pid) == team, "invalid lineup affiliation")
                raw_duration[pid] += b - a
                duration[pid] += eff - a
        for pid, row in players.items():
            if team_of[pid] == team:
                require(abs(duration[pid] - row["minutes"]) <= 1e-7
                        and abs(raw_duration[pid] - row["minutes"]) <= 1e-7, "minute mismatch")
                require(bool(duration[pid]) == (row["minutes"] > 0), "false played or DNP exposure")
                require(row["participation"] == "PLAYED" or duration[pid] == 0, "DNP/played-zero exposure")
        starts[team] = [s["start"] * 60 for s in stints]
    return starts


def audit_attempt(plan, attempt, team_of, *, starts=None):
    players = plan["players"]
    teams = plan["teams"]
    if starts is None:
        starts = rotation(plan, team_of)
    score = Counter(dict.fromkeys(teams, 0))
    stats = {pid: Counter() for pid in players}
    team_ledger = {team: Counter() for team in teams}

    def on_floor(pid, team, clock, left):
        # Right-limit is the last start <= t, unless the event uses left precedence.
        j = bisect_right(starts[team], clock) - 1
        if left and starts[team][j] == clock:
            j -= 1
        require(j >= 0 and pid in plan["stints"][team][j]["lineup"], "credit outside current lineup")

    def credit(pid, stat, amount=1):
        stats[pid][stat] += amount

    def fg(event, offense, left):
        require(len(event) == 6, "field goal size")
        clock, _, pid, value, made, assist = event
        require(type(value) is int and value in (2, 3) and type(made) is bool, "invalid shot")
        on_floor(pid, offense, clock, left)
        credit(pid, f"fg{value}a")
        if made:
            credit(pid, f"fg{value}m")
            credit(pid, "points", value)
            score[offense] += value
            if assist is not None:
                require(assist != pid, "self-assist")
                on_floor(assist, offense, clock, left)
                credit(assist, "assists")
        else:
            require(assist is None, "assisted miss")
        return made

    def ft(event, offense):
        require(len(event) == 5, "free throw trip size")
        clock, _, pid, makes, retained = event
        require(type(retained) is bool and len(makes) == (1 if retained else 2)
                and all(type(m) is bool for m in makes), "invalid free throw trip")
        on_floor(pid, offense, clock, False)
        credit(pid, "fta", len(makes))
        credit(pid, "ftm", sum(makes))
        credit(pid, "points", sum(makes))
        score[offense] += sum(makes)
        return retained, makes[-1]

    def action_sequence(actions, offense, defense, nominal_end):
        require(bool(actions) and actions[0][0] == nominal_end - 4, "wrong opening clock")
        i = 0

        def grab(kind, clock):
            nonlocal i
            require(i < len(actions), "missing action")
            action = actions[i]
            require(isinstance(action, list) and len(action) >= 2 and action[:2] == [clock, kind],
                    "unexpected action kind or clock")
            i += 1
            return action

        def board(clock, left, must_defense):
            action = grab("rebound", clock)
            require(len(action) == 4, "rebound size")
            _, _, team, rebounder = action
            require(team in (offense, defense) and (not must_defense or team == defense),
                    "invalid rebound side")
            side = "oreb" if team == offense else "dreb"
            if rebounder is None:
                team_ledger[team]["unattributed_" + side] += 1
            else:
                on_floor(rebounder, team, clock, left)
                credit(rebounder, side)
            return team == offense

        def shot(clock, terminal):
            made = fg(grab("fg", clock), offense, terminal)
            return False if made else board(clock, terminal, terminal)

        opening = nominal_end - 4
        first_kind = actions[0][1]
        if first_kind == "turnover":
            require(len(grab("turnover", opening)) == 2, "turnover credits")
            team_ledger[offense]["turnovers"] += 1
            more = False
        elif first_kind == "ft":
            retained, last_made = ft(grab("ft", opening), offense)
            if retained:
                more = shot(nominal_end - 2, False)
            else:
                more = False if last_made else board(opening, False, False)
        else:
            more = shot(opening, False)
        if more:
            shot(nominal_end, True)
        require(i == len(actions), "trailing actions")

    seen_failure = False
    nperiods = len(plan["periods"])
    require(0 < len(attempt["periods"]) <= nperiods, "wrong period population")
    for position, evidence in enumerate(attempt["periods"]):
        period = plan["periods"][position]
        require(not seen_failure and period["number"] == evidence["period"] == position + 1,
                "continued after score boundary failure")
        plays = evidence["possessions"]
        ends = period["ends"]
        require(len(ends) <= len(plays) <= len(ends) + 1, "incorrect number of possessions")
        offense = period["starter"]
        start = period["start"]
        for j, nominal_end in enumerate(ends):
            play = plays[j]
            defense = next(team for team in teams if team != offense)
            require(play["offense"] == offense and play["start"] == start, "control continuity")
            action_sequence(play["actions"], offense, defense, nominal_end)
            last = play["actions"][-1][0]
            require(start < last == play["end"] <= nominal_end and last - start <= 24,
                    "incorrect live possession interval")
            team_ledger[offense]["possessions"] += 1
            offense, start = defense, last
        if start == period["end"]:
            require(len(plays) == len(ends), "empty horn possession after terminal action")
        else:
            require(len(plays) > len(ends) and plays[-1] == {
                "offense": offense, "start": start, "end": period["end"],
                "actions": [[period["end"], "horn"]],
            }, "missing or invalid horn possession")
            team_ledger[offense]["possessions"] += 1
            team_ledger[offense]["horn_possessions"] += 1
        require(evidence["score"] == score, "period score not recoverable")
        if position >= 3:
            tied = score[teams[0]] == score[teams[1]]
            seen_failure = tied == (position + 1 == nperiods)

    expected = "score_checkpoint_failure" if seen_failure else "accepted"
    require(attempt["status"] == expected, "incorrect attempt status")
    require(seen_failure or len(attempt["periods"]) == nperiods, "missing final period")
    for pid, counts in stats.items():
        require(counts["points"] == 2 * counts["fg2m"] + 3 * counts["fg3m"] + counts["ftm"],
                "scoring mismatch")
        require(counts["points"] >= 3 * counts["fg3m"], "impossible PTS/3PM")
        counts["rebounds"] = counts["oreb"] + counts["dreb"]
        counts["threes"] = counts["fg3m"]
        counts["pr"] = counts["points"] + counts["rebounds"]
        counts["pa"] = counts["points"] + counts["assists"]
        counts["ra"] = counts["rebounds"] + counts["assists"]
        counts["pra"] = counts["pr"] + counts["assists"]
        team_ledger[team_of[pid]].update(counts)
    for team, counts in team_ledger.items():
        require(counts["points"] == score[team], "team score not recoverable")
        require(counts["assists"] <= counts["fg2m"] + counts["fg3m"], "too many assists")
    return stats, team_ledger


def score_checkpoints(plan, latents, team_of, *, starts=None):
    """Compute each checkpoint as the inner product of independent team PMFs."""
    from math import fsum, prod

    import numpy as np

    if starts is None:
        starts = rotation(plan, team_of)
    teams = plan["teams"]
    ft1 = np.array([0.24, 0.76])
    turnover = np.array([1.0])

    def fg_pmf(team, clock, left=False):
        j = bisect_right(starts[team], clock) - 1
        if left and starts[team][j] == clock:
            j -= 1
        profiles = [latents[pid] for pid in plan["stints"][team][j]["lineup"]]
        weights = [profile["shooter"] for profile in profiles]
        total = fsum(weights)
        if total == 0:
            weights, total = [1.0] * len(profiles), len(profiles)
        pairs = [(w / total, profile) for w, profile in zip(weights, profiles)]
        make2 = fsum(weight * 0.5 * (1 - profile["three_attempt"])
                     for weight, profile in pairs)
        make3 = fsum(weight * profile["three_attempt"] * profile["three_conversion"]
                     for weight, profile in pairs)
        return np.array([1 - make2 - make3, 0, make2, make3])

    def recover(shot, continuation):
        pmf = shot + (0.22 * shot[0]) * continuation
        pmf[0] -= 0.22 * shot[0]
        return pmf

    def slot(team, nominal):
        final = fg_pmf(team, nominal, left=True)
        opening = recover(fg_pmf(team, nominal - 4), final)
        after_penalty = recover(fg_pmf(team, nominal - 2), final)
        ordinary_ft_terminal = 0.24 * 0.22 * final
        ordinary_ft_terminal[0] += 0.24 * 0.78
        ordinary_ft_terminal[1] += 0.76
        mixture = np.zeros(5)
        mixture[:1] += 0.12 * turnover
        mixture[:4] += 0.74 * opening
        mixture += 0.12 * np.convolve(ft1, ordinary_ft_terminal)
        mixture += 0.02 * np.convolve(ft1, after_penalty)
        require(abs(fsum(mixture) - 1) < 1e-14 and min(mixture) >= 0, "invalid slot distribution")
        return mixture

    team_pmfs = {team: np.array([1.0]) for team in teams}
    probabilities = []
    for i, period in enumerate(plan["periods"]):
        offense = period["starter"]
        for nominal_end in period["ends"]:
            team_pmfs[offense] = np.convolve(team_pmfs[offense], slot(offense, nominal_end))
            offense = next(team for team in teams if team != offense)
        if i < 3:
            continue
        tie = fsum(team_pmfs[teams[0]] * team_pmfs[teams[1]])
        probabilities.append(1 - tie if i + 1 == len(plan["periods"]) else tie)
        team_pmfs = {team: np.array([1.0]) for team in teams}
    return probabilities, prod(probabilities)
