"""P4: G0-v2 joint research adapter over the existing WS5 nba_joint v0.1 engine.

This is deliberately NOT an S fitter or an O allocator. It consumes exact frozen
G/O scenarios, shares their weights/minutes/participation and reuses WS5's
shot/assist/rebound event kernel and WS2's five-on-court witness builder.
Synthetic rates are an interface fixture, not a validated conditional likelihood.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import time
import hashlib
from pathlib import Path

import numpy as np

from v2.nba_architecture.v2_contracts import (
    VERSION, ContractError, PHYSICAL, COMPOSITES, component, digest, instant,
    req, seal, verify, validate_pregame, marginal_from_joint,
)
from v2.nba_architecture.families_v2 import (
    validate_game_state, validate_opportunity, validate_integration,
)
from v2.nba_joint.common import rng_for
from v2.nba_joint.events import sample_events
from v2.nba_opportunity import lineup_segments


S_ADAPTER = "NBAJointSRateAdapter/1.0.0"
J_ADAPTER = "NBAJointP4/1.1.0"
VALID_VARIANTS = ("J0", "J1", "J2", "J3")
EVENT_PARAMETERS = (
    "p2", "p3", "pft", "ft_share", "rebound_credit",
    "offensive_rebound_share", "terminal_ft_fraction", "assist_fraction",
)
PRIMITIVES = ("points", "rebounds", "assists", "threes")


def _positive(x, label, *, zero=False):
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0 or (not zero and x == 0):
        raise ContractError(label)
    return float(x)


def _variance(x, label):
    val = _positive(x, label, zero=True)
    req(val <= 1.0, label + "_EXCESSIVE_UNFITTED_NOISE")
    return val


def validate_s_rates(p, s):
    """Strict, time-joined synthetic S interface. No pregame certification."""
    validate_pregame(p)
    req(isinstance(s, dict) and set(s) == {
        "schema", "kind", "content_hash", "source_snapshot_sha256",
        "game_id", "adapter_basis", "model", "players",
    }, "P4_S_SCHEMA")
    verify(s)
    req(s["schema"] == S_ADAPTER and s["kind"] == "conditional_rates",
        "P4_S_VERSION")
    req(s["adapter_basis"] == "synthetic_fixture",
        "P4_S_REAL_LIKELIHOOD_ADAPTER_NOT_ACCEPTED")
    req(s["source_snapshot_sha256"] == p["content_hash"] and
        s["game_id"] == p["game_id"], "P4_S_SOURCE_JOIN")
    component(s["model"])
    req(instant(s["model"]["training_cutoff_at"]) <=
        instant(p["input_freeze_at"]), "P4_S_FUTURE_MODEL")
    roster = {x["player_id"]: x["team_id"] for x in p["players"]}
    seen = set()
    req(len(s["players"]) == len(roster), "P4_S_ROSTER_COVERAGE")
    for row in s["players"]:
        req(set(row) == {"player_id", "team_id", "rates"}, "P4_S_PLAYER_SCHEMA")
        pid = row["player_id"]
        req(pid in roster and roster[pid] == row["team_id"]
            and pid not in seen, "P4_S_PLAYER_IDENTITY")
        seen.add(pid)
        req(set(row["rates"]) == set(PRIMITIVES), "P4_S_RATE_KEYS")
        for name, val in row["rates"].items():
            _positive(val, "P4_S_INVALID_RATE_" + name, zero=True)
        req(row["rates"]["points"] + 1e-12 >= 3 * row["rates"]["threes"],
            "P4_S_INCOMPATIBLE_THREE_POINT_RATE")
    return True


def _lineup_witness(p, participants, ot):
    """Check every team clock stint, not only the aggregate 240+25*OT sum."""
    length = 48 + 5 * ot
    results = {}
    for team in p["team_ids"]:
        subset = [x for x in participants if x["team_id"] == team]
        mins = np.asarray([x["minutes"] for x in subset], dtype=float)
        try:
            stints = lineup_segments(mins, length)
        except ValueError as exc:
            raise ContractError("P4_FIVE_ON_COURT_INFEASIBLE") from exc
        integrated = np.zeros(len(subset))
        for seg in stints:
            req(len(set(seg["player_indices"])) == 5 and
                seg["end"] > seg["start"], "P4_FIVE_ON_COURT")
            integrated[seg["player_indices"]] += seg["end"] - seg["start"]
        req(np.allclose(integrated, mins, atol=1e-7, rtol=0),
            "P4_LINEUP_INTEGRATION")
        results[team] = [
            {"start": float(seg["start"]), "end": float(seg["end"]),
             "player_ids": [subset[k]["player_id"] for k in seg["player_indices"]]}
            for seg in stints
        ]
    return results


def _event_config(events):
    req(isinstance(events, dict) and set(events) == set(EVENT_PARAMETERS),
        "P4_EVENT_CONFIG")
    for name in EVENT_PARAMETERS:
        val = _positive(events[name], "P4_EVENT_PROBABILITY", zero=True)
        req(0 <= val <= 1, "P4_EVENT_PROBABILITY")
    req(all(events[name] > 0 for name in ("p2", "p3", "pft")),
        "P4_ZERO_CONVERSION")
    return deepcopy(events)


def _draw_state(g_row, variant, base_pace, teams):
    if variant == "J0":
        return {"regulation_possession_proxy": base_pace,
                "offensive_effect": [1., 1.]}
    pace = _positive(g_row["pace_regulation"], "P4_PACE")
    home = _positive(g_row["possessions_home"], "P4_HOME_POSSESSIONS")
    away = _positive(g_row["possessions_away"], "P4_AWAY_POSSESSIONS")
    return {"regulation_possession_proxy": pace,
            "offensive_effect": [home / pace, away / pace]}


def _perturb(players, e, rng, role_sigma, efficiency_sigma):
    """J2/J3 synthetic uncertainty, no fitted coefficients or duplicate S law."""
    perturbed = deepcopy(players)
    team_ids = sorted({x["team_id"] for x in perturbed})
    team_effect = {team: math.exp(float(rng.normal(-.5*role_sigma**2, role_sigma)))
                   for team in team_ids}
    for player in perturbed:
        individual = math.exp(float(rng.normal(-.5*role_sigma**2, role_sigma)))
        factor = individual * team_effect[player["team_id"]]
        player["rates"] = {name: v * factor for name, v in player["rates"].items()}
    event = deepcopy(e)
    for name in ("p2", "p3", "pft", "assist_fraction"):
        prob = event[name]
        if 0 < prob < 1 and efficiency_sigma > 0:
            logit = math.log(prob / (1 - prob))
            shocked = logit + float(rng.normal(0, efficiency_sigma))
            event[name] = 1. / (1. + math.exp(-max(-30., min(30., shocked))))
    return perturbed, event


def _physical(c, i):
    stat = {name: int(c[name][i]) if name in c else 0 for name in PHYSICAL}
    stat["fgm"] = stat["two_pm"] + stat["threes"]
    stat["fga"] = stat["two_pa"] + stat["three_pa"]
    for combo, parts in COMPOSITES.items():
        stat[combo] = sum(stat[name] for name in parts)
    return stat


def simulate_p4(p, g, o, s, *, variant="J1", seed=20261116,
                base_pace=100.0, event_parameters=None,
                role_sigma=0., efficiency_sigma=0.,
                enable_j3=False, scenario_regimes=None, regime_multipliers=None,
                max_event_attempts=50):
    """Legacy synthetic control; pinned owner integration uses integration.py."""
    validate_s_rates(p, s)
    return _simulate_p4(p, g, o, s, variant=variant, seed=seed,
        base_pace=base_pace, event_parameters=event_parameters,
        role_sigma=role_sigma, efficiency_sigma=efficiency_sigma,
        enable_j3=enable_j3, scenario_regimes=scenario_regimes,
        regime_multipliers=regime_multipliers, max_event_attempts=max_event_attempts)


def _simulate_p4(p, g, o, s, *, variant="J1", seed=20261116,
                base_pace=100.0, event_parameters=None,
                role_sigma=0., efficiency_sigma=0.,
                enable_j3=False, scenario_regimes=None, regime_multipliers=None,
                max_event_attempts=50, _integration=None):
    """Generate a two-team G0-valid same-scenario J bundle and independent audit.

    J0: frozen pace and efficiency, exact O minutes.
    J1: exact G pace/possession state with exact O minutes.
    J2: J1 plus externally specified research-only role/efficiency uncertainty.
    J3: J2 plus *predeclared* scenario labels; G/O scenario weights unchanged.
    J4 is diagnostics only (see dependence_diagnostics).
    """
    req(variant in VALID_VARIANTS, "P4_INVALID_VARIANT")
    req(type(seed) is int and seed >= 0, "P4_INVALID_SEED")
    req(type(max_event_attempts) is int and 1 <= max_event_attempts <= 100,
        "P4_INVALID_REJECTION_LIMIT")
    _positive(base_pace, "P4_BASE_PACE")
    role_sigma = _variance(role_sigma, "P4_ROLE_SIGMA")
    efficiency_sigma = _variance(efficiency_sigma, "P4_EFFICIENCY_SIGMA")
    if variant in ("J0", "J1"):
        req(role_sigma == 0 and efficiency_sigma == 0,
            "P4_UNDECLARED_EXTRA_UNCERTAINTY")
    if variant == "J3":
        req(enable_j3 is True and isinstance(scenario_regimes, dict) and
            isinstance(regime_multipliers, dict) and bool(regime_multipliers),
            "P4_J3_PRECOMMITMENT_REQUIRED")
        req(set(scenario_regimes) == {x["scenario_id"] for x in g["scenarios"]},
            "P4_J3_SCENARIO_COVERAGE")
        req(all(isinstance(v, str) and v in regime_multipliers
                for v in scenario_regimes.values()), "P4_J3_REGIME_UNKNOWN")
        for mult in regime_multipliers.values():
            req(type(mult) in (int, float) and math.isfinite(mult) and
                0.5 <= mult <= 2.0, "P4_J3_REGIME_MULTIPLIER")
    else:
        req(enable_j3 is False and scenario_regimes is None and
            regime_multipliers is None, "P4_J3_UNGATED")
    validate_opportunity(o, p, g)
    e = _event_config(event_parameters)
    roster = p["players"]
    team_ids = p["team_ids"]
    g_lookup = {x["scenario_id"]: x for x in g["scenarios"]}
    o_lookup = {x["scenario_id"]: x for x in o["scenarios"]}
    rates = {x["player_id"]: x for x in s["players"]}
    scenario_rows, audit_rows, hashes = [], [], {}
    start = time.perf_counter()
    for sg in g["scenarios"]:
        sid = sg["scenario_id"]
        oo = o_lookup[sid]
        by_id = {x["player_id"]: x for x in oo["players"]}
        participants = [by_id[x["player_id"]] for x in roster]
        ix = [[i for i, x in enumerate(roster) if x["team_id"] == team]
              for team in team_ids]
        minutes = np.asarray([x["minutes"] for x in participants], dtype=float)
        lineups = _lineup_witness(p, participants, sg["overtime_periods"])
        sim_players = [{"player_id": x["player_id"], "team_id": x["team_id"],
                        "rates": deepcopy(rates[x["player_id"]]["rates"])}
                       for x in roster]
        if _integration is not None:
            sim_players = _integration.players(sid, e)
        state = _draw_state(sg, variant, base_pace, team_ids)
        if _integration is not None and variant != "J0":
            state["offensive_effect"] = [
                (sg["possessions_home"] if t == _integration.home_team_id
                 else sg["possessions_away"]) / sg["pace_regulation"]
                for t in team_ids]
        if variant == "J3":
            multiplier = float(regime_multipliers[scenario_regimes[sid]])
            state["offensive_effect"] = [v * multiplier for v in state["offensive_effect"]]
        rng_mod = rng_for(seed, p["game_id"], sid, "J2/role_efficiency")
        local_events = deepcopy(e)
        if variant in ("J2", "J3"):
            sim_players, local_events = _perturb(sim_players, e, rng_mod,
                                                 role_sigma, efficiency_sigma)
        spec = {"events": local_events, "state": {"pace_mean": base_pace}}
        first_tie_count = 0
        rejected_events = []
        for attempt in range(max_event_attempts):
            rng = rng_for(seed, p["game_id"], sid, "events/" + str(attempt))
            sampler = sample_events if _integration is None else _integration.sample_events
            counts, ledger = sampler(
                sim_players, minutes, ix, state, spec, rng, constrained=True,
            )
            totals = [int(counts["points"][idx].sum()) for idx in ix]
            if totals[0] != totals[1]:
                break
            first_tie_count += 1
            if _integration is not None:
                rejected_events.append({"event_attempt": attempt,
                    "reason": "TIED_COMPLETED_GAME_SCORE", "team_points": totals,
                    "counts": {k: v.tolist() for k, v in counts.items()},
                    "ledger": ledger})
        else:
            raise ContractError("P4_TIED_COMPLETED_GAME_EXHAUSTED")
        rows = [
            {"player_id": x["player_id"], "team_id": x["team_id"],
             "minutes": float(x["minutes"]), "participation": x["participation"],
             "stats": _physical(counts, i)}
            for i, x in enumerate(participants)
        ]
        scenario = {
            "scenario_id": sid, "weight": sg["weight"],
            "overtime_periods": sg["overtime_periods"],
            "team_points": {team: total for team, total in zip(team_ids, totals)},
            "players": rows,
        }
        scenario_rows.append(scenario)
        hashes[sid] = digest(scenario)
        audit_rows.append({
            "scenario_id": sid, "scenario_sha256": hashes[sid],
            "G_pace_regulation": sg["pace_regulation"],
            "G_possessions": [sg["possessions_home"], sg["possessions_away"]],
            "regime": scenario_regimes[sid] if variant == "J3" else None,
            "rejected_tied_event_draws": first_tie_count,
            "event_ledger_sha256": digest(ledger),
            **({} if _integration is None else {"event_ledger": ledger,
                "rejected_event_draws": rejected_events,
                "integration": _integration.audit(sid)}),
            "lineup_sha256": digest(lineups),
            "five_on_court": True,
        })
    bundle = seal({
        "schema": VERSION, "kind": "scenarios",
        "source_snapshot_sha256": p["content_hash"], "game_id": p["game_id"],
        "pipeline_mode": "S_O_J", "conditioning": "unconditional",
        "lineage": {"S": s["model"], "G": g["model"], "O": o["model"],
                    "J": {"model_id": "research:nba:p4:" + variant,
                          "version": J_ADAPTER, "artifact_sha256": digest({
                              "variant": variant, "rates_sha": s["content_hash"],
                              "seed": seed, "max_event_attempts": max_event_attempts,
                              "events": e, "base_pace": base_pace,
                              "role_sigma": role_sigma,
                              "efficiency_sigma": efficiency_sigma,
                              "regimes": scenario_regimes,
                              "multipliers": regime_multipliers,
                              "integration": None if _integration is None else _integration.manifest,
                          }),
                          "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          "training_cutoff_at": p["training_cutoff_at"]}},
        "scenarios": scenario_rows,
        "game_state_witness": {
            sid: {"overtime_periods": row["overtime_periods"],
                  "weight": row["weight"]}
            for sid, row in g_lookup.items()},
        "opportunity_witness": {
            sid: [{k: x[k] for k in ("player_id", "team_id",
                                   "minutes", "participation")}
                  for x in o_lookup[sid]["players"]]
            for sid in g_lookup},
        "game_state_sha256": g["content_hash"],
        "opportunity_sha256": o["content_hash"],
    })
    validate_integration(bundle, p, g, o)
    return {
        "bundle": bundle, "scenario_hashes": hashes,
        "audit_rows": audit_rows, "variant": variant,
        "input_shas": {"pregame": p["content_hash"], "G": g["content_hash"],
                       "O": o["content_hash"], "S": s["content_hash"]},
        "performance": {"elapsed_seconds": time.perf_counter() - start,
                        "n_scenarios": len(scenario_rows),
                        "n_player_draws": sum(len(r["players"]) for r in scenario_rows)},
        "status": "SYNTHETIC_SHADOW_ONLY",
    }


def scenario_pmfs(result, p, *, frozen_at, seed=20261116,
                  stats=("points", "rebounds", "assists", "threes",
                         "pr", "pa", "ra", "pra")):
    """Reuse G0's exact weighted empirical PMF machinery. No independent combo."""
    bundle = result["bundle"]
    out = {}
    for player in p["players"]:
        pid = player["player_id"]
        out[pid] = {
            stat: marginal_from_joint(bundle, p, pid, stat, frozen_at, seed)
            for stat in stats
        }
    return out


def dependence_diagnostics(result, p, pairs=()):
    """J4 diagnostic, not a fourth scoring vote or a learned copula.

    Reports covariance/correlation of *scenario-level* quantities only.
    Scenario count is NEVER treated as independent observed NBA games.
    """
    bundle = result["bundle"]
    rows = bundle["scenarios"]
    ws = np.asarray([row["weight"] for row in rows], dtype=float)
    req(bool(rows) and np.isclose(ws.sum(), 1), "P4_DIAGNOSTIC_WEIGHTS")
    universe = {x["player_id"]: x["team_id"] for x in p["players"]}
    lookup = [{x["player_id"]: x["stats"] for x in row["players"]} for row in rows]
    answer = []
    for left, lstat, right, rstat in pairs:
        req(left in universe and right in universe and
            lstat in PRIMITIVES + tuple(COMPOSITES) and
            rstat in PRIMITIVES + tuple(COMPOSITES),
            "P4_DIAGNOSTIC_PLAYER_OR_STAT")
        x = np.asarray([row[left][lstat] for row in lookup], dtype=float)
        y = np.asarray([row[right][rstat] for row in lookup], dtype=float)
        mx, my = float(ws @ x), float(ws @ y)
        cov = float(ws @ ((x-mx)*(y-my)))
        vx, vy = float(ws @ (x-mx)**2), float(ws @ (y-my)**2)
        corr = cov / math.sqrt(vx*vy) if vx > 0 and vy > 0 else None
        answer.append({"left": [left, lstat], "right": [right, rstat],
                       "covariance": cov, "correlation": corr,
                       "positive_cooccurrence": float(ws @ ((x>0)&(y>0)).astype(float))})
    return {"variant": "J4_DIAGNOSTIC_ONLY", "pairs": answer,
            "n_scenarios": len(rows),
            "effective_scenario_count_heuristic": float(1. / (ws @ ws)),
            "independent_observed_games": None,
            "scenario_bundle_sha256": bundle["content_hash"]}
