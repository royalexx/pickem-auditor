"""Standalone G (shared game state) and O (opportunity) v2.0 contracts.

G/O are producer interfaces, not separate ensemble votes. J integration must
consume their identical scenario/player draws and identity-bound content hashes.
"""
from __future__ import annotations
from .v2_contracts import (
    VERSION, ContractError, req, num, ident, instant, sha, check_schema,
    validate_pregame, validate_scenarios, component, seal,
)


def validate_game_state(g, p):
    validate_pregame(p)
    check_schema(g, "game_state")
    req(g["source_snapshot_sha256"] == p["content_hash"] and
        g["game_id"] == p["game_id"], "G_SOURCE_JOIN")
    component(g["model"])
    req(instant(g["model"]["training_cutoff_at"]) <=
        instant(p["input_freeze_at"]), "G_FUTURE_MODEL")
    req(type(g["rng_seed"]) is int and g["rng_seed"] >= 0, "G_SEED")
    scenarios = g["scenarios"]
    req(isinstance(scenarios, list) and bool(scenarios), "G_EMPTY_SCENARIOS")
    ids, weight = set(), 0.0
    for sc in scenarios:
        sid = ident(sc["scenario_id"])
        req(sid not in ids, "G_DUPLICATE_SCENARIO")
        ids.add(sid)
        weight += num(sc["weight"])
        req(type(sc["overtime_periods"]) is int and
            sc["overtime_periods"] >= 0, "G_OVERTIME")
        num(sc["pace_regulation"])
        num(sc["possessions_home"])
        num(sc["possessions_away"])
        req(sc["score_state"] in ("home_leading", "away_leading", "tied"),
            "G_SCORE_STATE")
    req(abs(weight-1) <= 1e-10, "G_WEIGHT_SUM")
    return True


def validate_opportunity(o, p, g):
    validate_game_state(g, p)
    check_schema(o, "opportunity")
    req(o["source_snapshot_sha256"] == p["content_hash"] and
        o["game_id"] == p["game_id"] and
        o["game_state_sha256"] == g["content_hash"], "O_G_SOURCE_JOIN")
    component(o["model"])
    req(instant(o["model"]["training_cutoff_at"]) <=
        instant(p["input_freeze_at"]), "O_FUTURE_MODEL")
    roster = {x["player_id"]: x for x in p["players"]}
    prior = {x["scenario_id"]: x for x in g["scenarios"]}
    persons = o["players"]
    req(len(persons) == len(roster) and
        len({x["player_id"] for x in persons}) == len(roster),
        "O_ROSTER_COVERAGE")
    for x in persons:
        req(x["player_id"] in roster and
            x["team_id"] == roster[x["player_id"]]["team_id"], "O_PLAYER_TEAM")
        prob = x["participation_probability"]
        req(x["participation_evidence"] in
            ("unknown","verified_out","independently_estimated"),
            "O_PARTICIPATION_EVIDENCE")
        if x["participation_evidence"] == "unknown":
            req(prob is None, "O_UNKNOWN_PARTICIPATION")
        else:
            req(prob is not None and 0 <= num(prob) <= 1, "O_PROBABILITY")
        if x["participation_evidence"] == "verified_out":
            req(prob == 0, "O_OUT_NOT_ZERO")
        if roster[x["player_id"]]["legal_eligibility"] is False:
            req(prob in (None, 0), "O_INELIGIBLE_PROBABILITY")
        law = x["minutes_law"]
        req(law["conditioning"] == "given_played" and
            isinstance(law["family"], str) and bool(law["family"]) and
            isinstance(law["parameters"], dict) and
            law["units"] == "minutes", "O_MINUTES_LAW")
    scenarios = o["scenarios"]
    req(len(scenarios) == len(prior), "O_SCENARIO_COVERAGE")
    seen = set()
    for sc in scenarios:
        sid = sc["scenario_id"]
        req(sid in prior and sid not in seen, "O_SCENARIO_JOIN")
        seen.add(sid)
        ot = prior[sid]["overtime_periods"]
        req(sc["overtime_periods"] == ot and
            abs(sc["weight"] - prior[sid]["weight"]) < 1e-12,
            "O_INDEPENDENT_G_DRAW")
        participants = sc["players"]
        by_id = {x["player_id"]: x for x in participants}
        req(len(participants) == len(roster) and
            set(by_id) == set(roster), "O_SCENARIO_ROSTER")
        duration = 48 + 5 * ot
        for person in participants:
            pid = person["player_id"]
            req(person["team_id"] == roster[pid]["team_id"], "O_TEAM_IDENTITY")
            mn = num(person["minutes"])
            req(mn <= duration, "O_PLAYER_MINUTES_CAP")
            status = person["participation"]
            req(status in ("DNP","PLAYED_ZERO_MINUTES","PLAYED"),
                "O_PARTICIPATION_STATE")
            if status == "PLAYED":
                req(mn > 0, "O_PLAYED_ZERO_MINUTES")
            else:
                req(mn == 0, "O_DNP_EXPOSURE")
            if roster[pid]["legal_eligibility"] is False:
                req(status == "DNP", "O_INELIGIBLE_PLAYED")
        for team in p["team_ids"]:
            total = sum(x["minutes"] for x in participants
                        if x["team_id"] == team)
            req(abs(total - 5*duration) < 1e-7, "O_TEAM_MINUTE_CONSERVATION")
    return True


def validate_integration(j, p, g, o):
    validate_opportunity(o, p, g)
    validate_scenarios(j, p)
    req(j["game_state_sha256"] == g["content_hash"] and
        j["opportunity_sha256"] == o["content_hash"], "J_G_O_HASH_JOIN")
    req(j["lineage"]["G"] == g["model"] and
        j["lineage"]["O"] == o["model"], "J_G_O_MODEL_JOIN")
    expected_g = {x["scenario_id"]: x for x in g["scenarios"]}
    expected_o = {x["scenario_id"]: x for x in o["scenarios"]}
    for sc in j["scenarios"]:
        sid = sc["scenario_id"]
        req(sid in expected_g and sid in expected_o, "J_G_O_SCENARIO_JOIN")
        gg, oo = expected_g[sid], expected_o[sid]
        req(sc["overtime_periods"] == gg["overtime_periods"] and
            abs(sc["weight"]-gg["weight"]) < 1e-12,
            "J_GAME_STATE_CHANGED")
        req(sc["overtime_periods"] == oo["overtime_periods"] and
            abs(sc["weight"]-oo["weight"]) < 1e-12, "J_OPPORTUNITY_STATE_CHANGED")
        source_players = {x["player_id"]: x for x in oo["players"]}
        for x in sc["players"]:
            y = source_players[x["player_id"]]
            req(x["minutes"] == y["minutes"] and
                x["participation"] == y["participation"] and
                x["team_id"] == y["team_id"], "J_RESAMPLED_OPPORTUNITY")
    return True
