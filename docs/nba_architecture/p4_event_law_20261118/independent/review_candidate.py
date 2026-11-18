"""Independent candidate replay, checkpoint reference, and semantic mutations."""
from collections import Counter
from copy import deepcopy
import json
from math import isclose

from witness_oracle import WitnessError, audit_attempt, require, rotation, score_checkpoints

from research.nba_p4_latest.fixture import build
from v2.nba_architecture.v2_contracts import ContractError
from v2.nba_joint.clocked import ATTEMPTS
from v2.nba_joint.clocked_native import prepare_native, run_seed
from v2.nba_joint.clocked_replay import reconstruct
from v2.nba_joint.latest_upstream import prepare

SEED = 90901
STAT_NAMES = {"two_pa": "fg2a", "two_pm": "fg2m", "three_pa": "fg3a"}


def compare_ledgers(plan, attempt, team_of, starts):
    players, teams = audit_attempt(plan, attempt, team_of, starts=starts)
    claimed = reconstruct(plan, attempt)
    for group, result in (("players", players), ("teams", teams)):
        require(set(claimed[group]) == set(result), "different output population")
        for entity, values in claimed[group].items():
            for stat, observed in values.items():
                expected = result[entity][STAT_NAMES.get(stat, stat)]
                require(expected == observed, (group, entity, stat, expected, observed))
    return players, teams


def mutate(attempt, name):
    candidate = deepcopy(attempt)
    first = candidate["periods"][0]
    if name == "score_delta":
        team = next(iter(first["score"]))
        first["score"][team] += 1
    elif name == "clock_jump":
        first["possessions"][0]["actions"][0][0] += 0.123
    elif name == "lost_possession":
        del first["possessions"][0]
    elif name == "status_swap":
        candidate["status"] = (
            "accepted" if attempt["status"] == "score_checkpoint_failure"
            else "score_checkpoint_failure"
        )
    else:
        actions = (a for p in first["possessions"] for a in p["actions"])
        if name == "self_assist":
            action = next(a for a in actions if a[1] == "fg" and a[4])
            action[5] = action[2]
        elif name == "foreign_rebounder":
            action = next(a for a in actions if a[1] == "rebound")
            action[3] = "foreign-player"
        elif name == "illegal_trip":
            action = next(a for a in actions if a[1] == "ft")
            action[3].extend([False, False])
        else:
            raise ValueError(name)
    return candidate


def test_mutations(plan, attempt, team_of, starts):
    results = {}
    for name in ("score_delta", "clock_jump", "lost_possession", "status_swap",
                 "self_assist", "foreign_rebounder", "illegal_trip"):
        bad = mutate(attempt, name)
        try:
            audit_attempt(plan, bad, team_of, starts=starts)
        except WitnessError as error:
            own_code = str(error)
        else:
            raise ValueError("Independent witness validator accepted " + name)
        try:
            reconstruct(plan, bad)
        except ContractError as error:
            owner_code = error.code
        else:
            raise ValueError("Candidate witness validator accepted " + name)
        results[name] = {"independent_rejection": own_code, "candidate_rejection": owner_code}
    return results


def review():
    upstream = prepare()
    native = build(upstream, seed=17, variant="O2", n=4)
    p, g, _, sidecar, *_ = native
    team_of = {r["player_id"]: r["team_id"] for r in p["players"]}
    packet = run_seed(prepare_native(*native, upstream_root=upstream,
                                     evidence_mode="latest_synthetic_engineering"), SEED)
    complete = {}
    mutation_results = None
    unbound_plan_probe = None
    for gs, os, path in zip(g["scenarios"], sidecar["scenarios"], packet["paths"], strict=True):
        sid = gs["scenario_id"]
        require(path["scenario_id"] == sid == os["scenario_id"], "scenario identity lost")
        require(path["weight"] == gs["weight"] == os["weight"], "scenario mass changed")
        info = {"attempts": len(path["attempts"]), "status": path["status"]}
        complete[sid] = info
        if "plan" not in path:
            info["preflight_code"] = path["code"]
            continue
        plan = path["plan"]
        starts = rotation(plan, team_of)
        for team, stints in plan["stints"].items():
            raw = os["teams"][team]["lineup_segments"]
            indexed = sorted(pid for pid, affiliated in team_of.items() if affiliated == team)
            for plan_stint, provider in zip(stints, raw, strict=True):
                indices = provider["player_indices"]
                require(plan_stint["start"] == provider["start"]
                        and plan_stint["end"] == provider["end"]
                        and plan_stint["indices"] == indices
                        and plan_stint["lineup"] == [indexed[j] for j in indices],
                        "raw P3 stints changed")
        require([r["clock"] for r in plan["stoppages"]] ==
                [clock for team in plan["teams"] for clock in starts[team][1:]],
                "missing rotation stoppage")
        blocks, z = score_checkpoints(plan, path["latents"], team_of, starts=starts)
        expected = path["normalizer"]
        require(all(isclose(x, y["acceptance_probability"], rel_tol=3e-13, abs_tol=3e-15)
                    for x, y in zip(blocks, expected["blocks"], strict=True))
                and isclose(z, expected["Z"], rel_tol=3e-13, abs_tol=3e-15),
                "checkpoint normalizer mismatch")
        flags = Counter()
        for attempt in path["attempts"]:
            players, teams = compare_ledgers(plan, attempt, team_of, starts)
            flags[attempt["status"]] += 1
        if path["status"] == "exhausted":
            require(not flags["accepted"] and len(path["attempts"]) == ATTEMPTS, "missing exhausted attempts")
        else:
            require(flags["accepted"] == 1 and path["attempts"][-1]["status"] == "accepted",
                    "acceptance order mismatch")
        if mutation_results is None:
            mutation_results = test_mutations(plan, path["attempts"][0], team_of, starts)
            stripped = deepcopy(plan)
            require(bool(stripped["stoppages"]), "missing positive rotation witness")
            stripped["stoppages"] = []
            unbound_plan_probe = {
                "mutation": "Remove all stoppages while retaining rest of prepared plan and witness",
                "scope": "Standalone verifier takes a caller-approved plan, not a bound native packet",
            }
            try:
                edited = reconstruct(stripped, path["attempts"][0])
            except ContractError as error:
                unbound_plan_probe.update(standalone_reconstruct_accepts=False, rejection=error.code)
            else:
                require(edited == reconstruct(plan, path["attempts"][0]), "edited ledger changes totals")
                unbound_plan_probe["standalone_reconstruct_accepts"] = True
        info.update(
            independent_checkpoint_blocks=blocks,
            independent_Z=z, candidate_Z=expected["Z"],
            conditional_failure_probability=(1 - z) ** ATTEMPTS,
            last_attempt_team_points={team: total["points"] for team, total in teams.items()},
            last_attempt_team_possessions={team: total["possessions"] for team, total in teams.items()},
            attempt_status_counts=dict(flags),
        )
    return {
        "input_hashes": packet["inputs"], "seed": SEED, "packet_status": packet["status"],
        "scenario_results": complete, "mutations": mutation_results,
        "unbound_plan_probe": unbound_plan_probe,
    }


if __name__ == "__main__":
    print(json.dumps(review(), indent=2, sort_keys=True))
