# Explicit opt-in validator protocol; G0 v2 remains unchanged.
"""Standalone G (shared game state) and O (opportunity) v2.0 contracts.

G/O are producer interfaces, not separate ensemble votes. J integration must
consume their identical scenario/player draws and identity-bound content hashes.
"""
from __future__ import annotations
from .v2_contracts import (
    structural_boundary, participation_state, VERSION, ContractError, req, num, ident, instant, sha, check_schema,
    validate_pregame, validate_scenarios, component, seal, strict_keys,
)


def validate_game_state(g, p):
    strict_keys(g, ("schema","kind","content_hash","source_snapshot_sha256",
                    "game_id","model","rng_seed","scenarios"))
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


def validate_opportunity_structure(o, p, g):
    strict_keys(o, ("schema","kind","content_hash","source_snapshot_sha256",
                    "game_id","model","game_state_sha256","players","scenarios"))
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
            req(roster[x["player_id"]]["availability"] == "out" or
                roster[x["player_id"]]["legal_eligibility"] is False,
                "O_UNBOUND_VERIFIED_OUT")
        if roster[x["player_id"]]["legal_eligibility"] is False:
            req(prob in (None, 0), "O_INELIGIBLE_PROBABILITY")
        law = x["minutes_law"]
        req(law["conditioning"] == "given_played" and
            isinstance(law["family"], str) and bool(law["family"]) and
            isinstance(law["parameters"], dict) and
            law["units"] == "minutes", "O_MINUTES_LAW")
        if roster[x["player_id"]]["availability"] == "out":
            req(prob in (None, 0), "O_OUT_PROBABILITY")
        strict_keys(law, ("family", "parameters", "conditioning", "units"))
        req(law["family"] in ("synthetic_point_mass", "discrete_minutes"),
            "O_UNREGISTERED_MINUTES_LAW")
        if law["family"] == "discrete_minutes":
            import math
            strict_keys(law["parameters"], ("support",))
            support = law["parameters"]["support"]
            req(isinstance(support, list) and bool(support), "O_MINUTES_SUPPORT")
            seen_minutes = set()
            for atom in support:
                strict_keys(atom, ("minutes", "mass"))
                mn = num(atom["minutes"]); mass = num(atom["mass"])
                req(mn <= max(48 + 5*sc["overtime_periods"] for sc in g["scenarios"]
                              if sc["weight"] > 0), "O_LAW_PHYSICAL_SUPPORT")
                req(mn not in seen_minutes and mass > 0, "O_MINUTES_ATOM")
                seen_minutes.add(mn)
            req(abs(math.fsum(a["mass"] for a in support)-1) <= 1e-12,
                "O_MINUTES_MASS")
        if law["family"] == "synthetic_point_mass":
            req(set(law["parameters"]) == {"median"}, "O_POINT_MASS_PARAMETERS")
            num(law["parameters"]["median"])
    laws = {x["player_id"]: x["minutes_law"] for x in persons}
    estimates = {x["player_id"]: x["participation_probability"] for x in persons}
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
            participation_state(roster[pid], status, mn, estimates[pid], sc["weight"])
            law = laws[pid]
            if law["family"] == "discrete_minutes" and status != "DNP" and sc["weight"] > 0:
                req(any(a["minutes"] == mn for a in law["parameters"]["support"]),
                    "O_DRAW_OUTSIDE_MINUTES_SUPPORT")
            if roster[pid]["legal_eligibility"] is False:
                req(status == "DNP", "O_INELIGIBLE_PLAYED")
        for team in p["team_ids"]:
            total = sum(x["minutes"] for x in participants
                        if x["team_id"] == team)
            req(abs(total - 5*duration) < 1e-7, "O_TEAM_MINUTE_CONSERVATION")
    return True


def validate_opportunity(o,p,g):
    validate_opportunity_structure(o,p,g)
    from .exposure_certificate_v1 import validate_exposure_coupling
    validate_exposure_coupling(o,p,g)
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
    req({sc["scenario_id"] for sc in j["scenarios"]} == set(expected_g),
        "J_G_O_EXACT_SCENARIO_COVERAGE")
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


validate_game_state = structural_boundary(validate_game_state)
validate_opportunity = structural_boundary(validate_opportunity)


def validate_forecast(d, p, *, g=None, o=None, scenarios=None):
    """Complete pipeline boundary; component validators alone do not certify a pipeline.

    Retrieve immutable G/O/J objects before calling. No global lookup or self-reported
    digest is substituted for those objects. S_ONLY remains market independent.
    """
    from .v2_contracts import validate_distribution
    validate_distribution(d, p, scenarios)
    import math
    roster = next(x for x in p['players'] if x['player_id'] == d['player_id'])
    excluded = roster['legal_eligibility'] is False or roster['availability'] == 'out'
    if excluded:
        req(d['conditioning'] != 'conditional_on_participation',
            'FORECAST_IMPOSSIBLE_PARTICIPATION_CONDITION')
        req(math.fsum(r['mass'] for r in d['pmf'] if r['value'] > 0) == 0,
            'FORECAST_EXCLUDED_POSITIVE_COUNT')
    if d['pipeline_mode'] == 'S_ONLY':
        req(g is None and o is None and scenarios is None, 'UNDECLARED_PIPELINE_CONTEXT')
        return True
    req(g is not None and o is not None, 'FORECAST_OPPORTUNITY_CONTEXT_REQUIRED')
    validate_opportunity(o, p, g)
    req(d['opportunity_output_sha256'] == o['content_hash'], 'FORECAST_O_HASH')
    req(d['lineage']['O'] == o['model'], 'FORECAST_O_MODEL')
    req(d['lineage']['G'] == g['model'], 'FORECAST_G_MODEL')
    req(all(x['minutes_law']['family'] != 'synthetic_point_mass' for x in o['players']),
        'DIAGNOSTIC_MINUTES_NOT_FORECAST_LAW')
    from .exposure_v2 import positive_exposure_bound, MASS_TOLERANCE
    from .exposure_certificate_v1 import validate_exposure_coupling
    person = next(x for x in o['players'] if x['player_id'] == d['player_id'])
    compatible_bounds = validate_exposure_coupling(o, p, g)[d['player_id']]
    bound = positive_exposure_bound(person, roster, d['conditioning'], compatible_bounds)
    positive_count = math.fsum(r['mass'] for r in d['pmf'] if r['value'] > 0)
    # Interior analytic probabilities obey the true exposure bound. Empirical
    # MC frequencies can exceed it by finite sampling, so only hard-zero support
    # is deterministic for those marginals (including J-derived distributions).
    if d['numerical']['method'] == 'analytic':
        req(positive_count <= bound + MASS_TOLERANCE, 'FORECAST_COUNT_EXCEEDS_EXPOSURE')
        if d['conditioning'] != 'conditional_on_participation' and positive_count > 0:
            validate_exposure_coupling(o, p, g,
                                      required_positive=(d['player_id'], positive_count))
    if bound == 0:
        req(positive_count == 0, 'FORECAST_ZERO_EXPOSURE_POSITIVE_COUNT')
    if d['pipeline_mode'] == 'S_O_J':
        validate_integration(scenarios, p, g, o)
    return True


def validate_settlement(e, d, p, *, view=None, quote=None, g=None, o=None,
                        scenarios=None, history=()):
    """C boundary: validate frozen forecast, original offer and full correction chain."""
    from .v2_contracts import validate_offer_view, validate_evaluation, verify
    validate_forecast(d, p, g=g, o=o, scenarios=scenarios)
    req((view is None) == (quote is None), 'SETTLEMENT_ORIGINAL_OFFER_CONTEXT')
    if view is not None:
        validate_offer_view(view, d, quote, p, scenarios)
    previous = None
    seen = set()
    for record in [*history, e]:
        h = verify(record)
        req(h not in seen, 'DUPLICATE_SETTLEMENT')
        seen.add(h)
        req(record['revision'] == (1 if previous is None else previous['revision']+1),
            'SETTLEMENT_COMPLETE_HISTORY_REQUIRED')
        validate_evaluation(record, d, view, previous=previous)
        previous = record
    return True
