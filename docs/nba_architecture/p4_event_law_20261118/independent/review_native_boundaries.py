"""Probe actual P3 played-zero/DNP/early-exit schedules with actual P2 fitted inputs."""
import json

from witness_oracle import audit_attempt, require, rotation

from research.nba_p4_latest.fixture import build
from v2.nba_joint.clocked_native import prepare_native, run_seed
from v2.nba_joint.latest_upstream import prepare

PLAYED_ZERO = "espn:player:15"
DNP = "espn:player:25"
SEED = 90902


def zero_priors(priors):
    priors[PLAYED_ZERO]["played_zero_probability"] = 1.0
    priors[DNP]["scenario_participation_prior"] = 0.0


def exit_priors(priors):
    priors[PLAYED_ZERO]["early_exit_probability"] = 1.0
    priors[PLAYED_ZERO]["early_exit_fraction"] = 0.40


def run_case(root, hook):
    # One regulation draw per independent control, no retry of O.
    native = build(root, n=1, variant="O2", seed=17, special=hook)
    p, g, _, side, *_ = native
    team_of = {person["player_id"]: person["team_id"] for person in p["players"]}
    prepared = prepare_native(*native, upstream_root=root, evidence_mode="latest_synthetic_engineering")
    result, = run_seed(prepared, SEED)["paths"]
    require(result["status"] == "accepted", "control event draw was not accepted")
    plan = result["plan"]
    rotation(plan, team_of)
    players, teams = audit_attempt(plan, result["attempts"][-1], team_of)
    return g, side, result, players, teams


def review():
    upstream = prepare()
    _, _, result, players, _ = run_case(upstream, zero_priors)
    people = result["plan"]["players"]
    require(people[PLAYED_ZERO]["participation"] == "PLAYED_ZERO_MINUTES"
            and people[DNP]["participation"] == "DNP", "participation conflated")
    require(all(not any(players[pid].values()) for pid in (PLAYED_ZERO, DNP)),
            "credit with no court time")
    g, side, case, _, teams = run_case(upstream, exit_priors)
    exited = case["plan"]["players"][PLAYED_ZERO]
    cap = (48 + 5 * g["scenarios"][0]["overtime_periods"]) * .4
    require(exited["role_state"] == "early_exit" and 0 < exited["minutes"] <= cap + 1e-7,
            "P3 total-minute early-exit cap")
    return {
        "zero_case": {
            "played_zero": people[PLAYED_ZERO]["participation"], "dnp": people[DNP]["participation"],
            "credits": {pid: {stat: players[pid][stat] for stat in (
                "points", "rebounds", "assists", "threes", "pr", "pa", "ra", "pra",
                "fg2a", "fg2m", "fg3a", "fg3m", "fta", "ftm", "oreb", "dreb",
            )} for pid in (PLAYED_ZERO, DNP)},
        },
        "early_exit_case": {
            "player": PLAYED_ZERO, "minutes": exited["minutes"], "cap": cap,
            "P3_sidecar_content_hash": side["content_hash"],
            "team_final_points": {team: data["points"] for team, data in teams.items()},
            "scope": "Synthetic P3 total-minute cap with no claim about actual exit clock",
        },
        "seed": SEED,
    }


if __name__ == "__main__":
    print(json.dumps(review(), indent=2, sort_keys=True))
