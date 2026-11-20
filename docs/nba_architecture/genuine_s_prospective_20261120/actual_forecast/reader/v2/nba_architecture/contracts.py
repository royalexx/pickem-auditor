"""NBA S/O/J/C 1.0.0: executable, model-neutral, fail-closed architecture contract.

No model parameters are fitted here. Hashes prove byte identity, not source truth.
All clocks must be authenticated separately by the source/forecast producers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import os

VERSION = "nba-sojc-contract/1.0.0"
STATS = frozenset(("points", "rebounds", "assists", "threes", "steals",
                   "blocks", "turnovers", "pr", "pa", "ra", "pra"))
BASE_STATS = ("points", "rebounds", "assists", "threes", "fgm", "fga",
              "ftm", "fta", "oreb", "dreb", "steals", "blocks", "turnovers")
COMBOS = {"pr": ("points", "rebounds"),
          "pa": ("points", "assists"),
          "ra": ("rebounds", "assists"),
          "pra": ("points", "rebounds", "assists")}


class ContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise ContractError(code)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha(value):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), "INVALID_SHA256")
    return value


def seal(obj):
    require(isinstance(obj, dict) and "content_hash" not in obj,
            "INVALID_UNSEALED_OBJECT")
    return dict(obj, content_hash=digest(obj))


def verify_seal(obj):
    require(isinstance(obj, dict) and "content_hash" in obj, "MISSING_CONTENT_HASH")
    raw = dict(obj)
    observed = raw.pop("content_hash")
    sha(observed)
    require(digest(raw) == observed, "CONTENT_HASH_MISMATCH")
    return observed


def freeze_once(path, obj):
    """Create-only immutable JSON record. Existing equal bytes are idempotent."""
    verify_seal(obj)
    path = Path(path)
    raw = canonical(obj) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as f:
            f.write(raw)
    except FileExistsError:
        require(path.read_bytes() == raw, "IMMUTABLE_CONFLICT")
    return obj["content_hash"]


def instant(s):
    require(isinstance(s, str) and "T" in s
            and (s.endswith("Z") or s.endswith("+00:00")), "UTC_REQUIRED")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP") from exc
    require(dt.utcoffset() is not None and dt.utcoffset().total_seconds() == 0,
            "UTC_REQUIRED")
    return dt.astimezone(timezone.utc)


def number(v, *, low=None):
    require(type(v) in (int, float) and math.isfinite(v), "INVALID_NUMBER")
    if low is not None:
        require(v >= low, "NEGATIVE_NUMBER")
    return v


def nonempty(v):
    require(isinstance(v, str) and bool(v.strip()), "EMPTY_ID")
    return v


def identity_ids(obj):
    home, away = nonempty(obj["home_team_id"]), nonempty(obj["away_team_id"])
    require(home != away, "SAME_TEAM")
    nonempty(obj["event_id"])
    return home, away


def seed_for(master, event_id, scenario_id, component_version):
    require(type(master) is int and master >= 0, "INVALID_SEED")
    for value in (event_id, scenario_id, component_version):
        nonempty(value)
        require("|" not in value, "AMBIGUOUS_SEED_ID")
    s = "|".join([VERSION, str(master), event_id, scenario_id, component_version])
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")


def common(obj, family, source_hash, event_id):
    verify_seal(obj)
    require(obj["schema"] == VERSION and obj["family"] == family, "SCHEMA_OR_FAMILY")
    require(obj["source_snapshot_sha256"] == source_hash, "SOURCE_LINEAGE_MISMATCH")
    require(obj["event_id"] == event_id, "EVENT_ID_MISMATCH")
    nonempty(obj["model_id"])
    nonempty(obj["model_version"])
    sha(obj["code_sha256"])
    sha(obj["artifact_sha256"])
    instant(obj["model_training_cutoff_at"])


def validate_pregame(p):
    require(p["schema"] == VERSION and p["record_type"] == "pregame",
            "PREGAME_SCHEMA")
    verify_seal(p)
    identity_ids(p)
    freeze = instant(p["input_freeze_at"])
    forecast = instant(p["forecast_at"])
    start = instant(p["event_start_at"])
    cutoff = instant(p["model_training_cutoff_at"])
    require(cutoff <= freeze <= forecast < start, "PREGAME_TIME_ORDER")
    sources = p["sources"]
    require(isinstance(sources, list) and len(sources) > 0, "SOURCES_REQUIRED")
    names = []
    for source in sources:
        names.append(nonempty(source["source_id"]))
        sha(source["raw_sha256"])
        require(source["origin"] == "original_capture", "NONORIGINAL_SOURCE")
        require(instant(source["source_available_at"]) <= freeze, "POSTFREEZE_SOURCE")
        require(instant(source["observed_at"]) <= freeze, "POSTFREEZE_OBSERVATION")
        require(instant(source["source_available_at"]) >=
                instant(source["observed_at"]), "SOURCE_CLOCK_CONFLICT")
    require(len(set(names)) == len(names), "DUPLICATE_SOURCE_ID")
    for player in p["players"]:
        nonempty(player["player_id"])
        require(player["team_id"] in identity_ids(p), "PLAYER_TEAM_MISMATCH")
        require(player["availability"] in
                ("confirmed_out", "reported_active", "questionable", "unknown"),
                "INVALID_AVAILABILITY")
        require(player["legal_eligibility"] in (True, False, None),
                "INVALID_ELIGIBILITY")
    ids = [x["player_id"] for x in p["players"]]
    require(len(ids) == len(set(ids)), "DUPLICATE_PLAYER")
    offers = p["offers"]
    offer_ids = []
    for quote in offers:
        offer_ids.append(nonempty(quote["contract_id"]))
        require(quote["event_id"] == p["event_id"], "QUOTE_EVENT_MISMATCH")
        require(quote["player_id"] in ids, "QUOTE_PLAYER_MISMATCH")
        require(quote["team_id"] == next(x["team_id"] for x in p["players"]
                                         if x["player_id"] == quote["player_id"]),
                "QUOTE_TEAM_MISMATCH")
        require(quote["stat"] in STATS and quote["period"] == "full_game_including_ot",
                "QUOTE_STAT_OR_PERIOD")
        number(quote["line"], low=0)
        sha(quote["quote_sha256"])
        nonempty(quote["quote_id"])
        nonempty(quote["book"])
        nonempty(quote["product_type"])
        require(quote["source_id"] in names, "UNBACKED_QUOTE")
        require(instant(quote["quote_at"]) <= freeze, "FUTURE_QUOTE")
    require(len(set(offer_ids)) == len(offer_ids), "DUPLICATE_CONTRACT_ID")
    for feature in p.get("features", []):
        require(feature["source_id"] in names, "UNBACKED_FEATURE")
        require(instant(feature["available_at"]) <= freeze, "FUTURE_FEATURE")
        require(feature.get("is_target_game_outcome", False) is False,
                "TARGET_OUTCOME_LEAK")
    return p["content_hash"]


def validate_statistical(s, pregame):
    validate_pregame(pregame)
    common(s, "S", pregame["content_hash"], pregame["event_id"])
    require(instant(s["model_training_cutoff_at"]) <=
            instant(pregame["input_freeze_at"]), "TRAINING_AFTER_FREEZE")
    require(s["stat"] in STATS, "INVALID_STAT")
    require(s["period"] == "full_game_including_ot", "INVALID_STAT_PERIOD")
    roster = {p["player_id"]: p for p in pregame["players"]}
    require(s["player_id"] in roster and
            roster[s["player_id"]]["team_id"] == s["team_id"], "STAT_PLAYER_JOIN")
    require(s["support"] == "nonnegative_integer", "INVALID_SUPPORT")
    masses = s["pmf"]
    require(isinstance(masses, list) and bool(masses), "EMPTY_PMF")
    seen = set()
    for r in masses:
        require(type(r["value"]) is int and r["value"] >= 0, "COUNT_SUPPORT")
        require(r["value"] not in seen, "DUPLICATE_MASS_POINT")
        seen.add(r["value"])
        number(r["mass"], low=0)
    require(abs(sum(x["mass"] for x in masses) - 1) <= 1e-10,
            "MASS_NOT_NORMALIZED")
    require(s["conditioning"] in ("unconditional", "conditional_on_participation"),
            "UNKNOWN_CONDITIONING")
    return True


def validate_opportunity(o, pregame, game_state=None):
    validate_pregame(pregame)
    common(o, "O", pregame["content_hash"], pregame["event_id"])
    require(instant(o["model_training_cutoff_at"]) <=
            instant(pregame["input_freeze_at"]), "TRAINING_AFTER_FREEZE")
    known = {p["player_id"]: p for p in pregame["players"]}
    require(len(o["players"]) == len(known), "OPPORTUNITY_UNIVERSE_INCOMPLETE")
    ids = set()
    for player in o["players"]:
        pid = player["player_id"]
        require(pid in known and pid not in ids, "OPPORTUNITY_PLAYER_MISMATCH")
        ids.add(pid)
        p = player["participation_probability"]
        if p is not None:
            require(0 <= number(p) <= 1, "INVALID_PARTICIPATION")
        if known[pid]["legal_eligibility"] is False:
            require(p in (0, None), "INELIGIBLE_PARTICIPATION")
        if player["participation_status"] == "unknown":
            require(p is None, "UNKNOWN_AS_CERTAIN")
        number(player["mean_minutes_given_played"], low=0)
        law = player["minutes_law"]
        require(isinstance(law, dict) and
                isinstance(law.get("family"), str) and law["family"] and
                isinstance(law.get("parameters"), dict) and
                law.get("overtime_coupled") is True, "MINUTES_LAW_REQUIRED")
        require(player["conditioning"] == "given_played", "MINUTES_CONDITIONING")
    require(o["roster_certified"] is False or
            all(p["legal_eligibility"] is not None for p in pregame["players"]),
            "UNSUPPORTED_ROSTER_CERTIFICATION")
    nonempty(o["game_state_id"])
    if game_state is not None:
        validate_game_state(game_state, pregame)
        require(o["game_state_id"] == game_state["model_id"],
                "OPPORTUNITY_GAME_STATE_JOIN")
        reference = {sc["scenario_id"]: sc for sc in game_state["scenarios"]}
        allocations = o["scenario_allocations"]
        require(len(allocations) == len(reference), "OPPORTUNITY_SCENARIO_COVERAGE")
        seen = set()
        for sc in allocations:
            sid = sc["scenario_id"]
            require(sid in reference and sid not in seen, "OPPORTUNITY_SCENARIO_JOIN")
            seen.add(sid)
            ot = reference[sid]["overtime_periods"]
            require(sc["overtime_periods"] == ot, "OPPORTUNITY_OT_MISMATCH")
            duration = 48 + 5 * ot
            allocations_by_player = {x["player_id"]: x for x in sc["players"]}
            require(len(sc["players"]) == len(known)
                    and len(allocations_by_player) == len(known)
                    and set(allocations_by_player) == set(known),
                    "OPPORTUNITY_ALLOCATION_ROSTER")
            for player in sc["players"]:
                pid = player["player_id"]
                require(player["team_id"] == known[pid]["team_id"],
                        "OPPORTUNITY_ALLOCATION_TEAM")
                require(type(player["participated"]) is bool,
                        "OPPORTUNITY_ALLOCATION_PARTICIPATION")
                number(player["minutes"], low=0)
                require(player["minutes"] <= duration, "OPPORTUNITY_PLAYER_CAP")
                if not player["participated"] or known[pid]["legal_eligibility"] is False:
                    require(player["minutes"] == 0, "INACTIVE_OPPORTUNITY")
            for team in identity_ids(pregame):
                require(abs(sum(x["minutes"] for x in sc["players"]
                                if x["team_id"] == team) - 5 * duration) < 1e-7,
                        "OPPORTUNITY_TEAM_MINUTES")
    return True


def validate_game_state(g, pregame):
    validate_pregame(pregame)
    common(g, "G", pregame["content_hash"], pregame["event_id"])
    require(instant(g["model_training_cutoff_at"]) <=
            instant(pregame["input_freeze_at"]), "TRAINING_AFTER_FREEZE")
    ids = []
    mass = 0.0
    for scenario in g["scenarios"]:
        ids.append(nonempty(scenario["scenario_id"]))
        require(type(scenario["overtime_periods"]) is int and
                scenario["overtime_periods"] >= 0, "INVALID_OT")
        number(scenario["possessions_home"], low=0)
        number(scenario["possessions_away"], low=0)
        mass += number(scenario["weight"], low=0)
        for key in ("pace_regulation", "score_state"):
            require(key in scenario, "GAME_STATE_INCOMPLETE")
    require(ids and len(set(ids)) == len(ids), "DUPLICATE_SCENARIO")
    require(abs(mass - 1) <= 1e-10, "SCENARIO_WEIGHTS")
    return True


def validate_joint(j, pregame, opportunity, game_state):
    validate_opportunity(opportunity, pregame, game_state)
    validate_game_state(game_state, pregame)
    common(j, "J", pregame["content_hash"], pregame["event_id"])
    require(instant(j["model_training_cutoff_at"]) <=
            instant(pregame["input_freeze_at"]), "TRAINING_AFTER_FREEZE")
    require(j["opportunity_id"] == opportunity["model_id"], "OPPORTUNITY_JOIN")
    require(j["game_state_id"] == game_state["model_id"], "STATE_JOIN")
    require(isinstance(j["outcome_model_ids"], list)
            and bool(j["outcome_model_ids"])
            and len(set(j["outcome_model_ids"])) == len(j["outcome_model_ids"]),
            "OUTCOME_FAMILY_MISSING")
    state_by_id = {s["scenario_id"]: s for s in game_state["scenarios"]}
    opportunity_by_id = {s["scenario_id"]: s for s in opportunity["scenario_allocations"]}
    require(len(j["scenarios"]) == len(state_by_id), "SCENARIO_COVERAGE")
    roster = {p["player_id"]: p for p in pregame["players"]}
    team_ids = identity_ids(pregame)
    joint_ids = []
    for sc in j["scenarios"]:
        sid = sc["scenario_id"]
        require(sid in state_by_id, "SCENARIO_JOIN")
        joint_ids.append(sid)
        state = state_by_id[sid]
        require(sc["overtime_periods"] == state["overtime_periods"],
                "INDEPENDENT_GAME_STATE")
        nmins = 48 + 5 * state["overtime_periods"]
        rows = sc["players"]
        expected_minutes = {p["player_id"]: p for p in
                            opportunity_by_id[sid]["players"]}
        require(len(rows) == len(roster), "INCOMPLETE_JOINT_ROSTER")
        ids = [p["player_id"] for p in rows]
        require(set(ids) == set(roster) and len(ids) == len(set(ids)),
                "PLAYER_SCENARIO_COVERAGE")
        for team in team_ids:
            total = sum(number(p["minutes"], low=0) for p in rows
                        if p["team_id"] == team)
            require(abs(total - 5 * nmins) < 1e-7, "TEAM_MINUTE_CONSERVATION")
        for p in rows:
            pid = p["player_id"]
            require(p["team_id"] == roster[pid]["team_id"],
                    "CROSS_TEAM_OUTCOME")
            require(p["minutes"] == expected_minutes[pid]["minutes"] and
                    p["participated"] == expected_minutes[pid]["participated"],
                    "OPPORTUNITY_JOINT_DRAW_MISMATCH")
            number(p["minutes"], low=0)
            require(p["minutes"] <= nmins, "PLAYER_MINUTE_CAP")
            require(type(p["participated"]) is bool, "INVALID_PLAYED_FLAG")
            d = p["stats"]
            for k in BASE_STATS:
                require(type(d[k]) is int and d[k] >= 0, "INVALID_COUNT:" + k)
            require(d["threes"] <= d["fgm"] <= d["fga"] and
                    d["ftm"] <= d["fta"], "SHOT_IDENTITY")
            require(d["points"] == 2 * d["fgm"] + d["threes"] + d["ftm"],
                    "POINTS_IDENTITY")
            require(d["rebounds"] == d["oreb"] + d["dreb"],
                    "REBOUND_IDENTITY")
            for combo, keys in COMBOS.items():
                require(d[combo] == sum(d[key] for key in keys),
                        "COMBO_IDENTITY:" + combo)
            if not p["participated"] or p["minutes"] == 0 or \
                    roster[pid]["legal_eligibility"] is False:
                require(p["minutes"] == 0 and all(d[k] == 0 for k in d),
                        "INACTIVE_OUTCOME")
        for team in team_ids:
            team_rows = [p for p in rows if p["team_id"] == team]
            require(sum(p["stats"]["assists"] for p in team_rows) <=
                    sum(p["stats"]["fgm"] for p in team_rows),
                    "TEAM_ASSIST_CAP")
            require(sum(p["stats"]["points"] for p in team_rows) ==
                    sc["team_points"][team], "TEAM_SCORE_JOIN")
    require(set(joint_ids) == set(state_by_id) and
            len(joint_ids) == len(set(joint_ids)), "SCENARIO_ID_COVERAGE")
    return True


def joint_stat_pmf(j, game_state, player_id, stat):
    """Weighted same-scenario marginal; combos come from same J primitive draws."""
    require(stat in STATS, "INVALID_STAT")
    states = {x["scenario_id"]: x for x in game_state["scenarios"]}
    masses = {}
    require({x["scenario_id"] for x in j["scenarios"]} == set(states),
            "SCENARIO_JOIN")
    for sc in j["scenarios"]:
        candidates = [p for p in sc["players"] if p["player_id"] == player_id]
        require(len(candidates) == 1, "PLAYER_SCENARIO_COVERAGE")
        val = candidates[0]["stats"][stat]
        masses[val] = masses.get(val, 0.0) + states[sc["scenario_id"]]["weight"]
    return [{"value": v, "mass": masses[v]} for v in sorted(masses)]


def threshold_triplet(pmf, line):
    number(line, low=0)
    over = sum(x["mass"] for x in pmf if x["value"] > line)
    under = sum(x["mass"] for x in pmf if x["value"] < line)
    push = sum(x["mass"] for x in pmf if x["value"] == line)
    return {"over": over, "under": under, "push": push}


def validate_forecast(f, pregame, distribution):
    validate_statistical(distribution, pregame)
    verify_seal(f)
    require(f["schema"] == VERSION and f["record_type"] == "forecast",
            "FORECAST_SCHEMA")
    require(f["source_snapshot_sha256"] == pregame["content_hash"],
            "FORECAST_SOURCE_MISMATCH")
    require(f["event_id"] == pregame["event_id"], "FORECAST_EVENT_MISMATCH")
    require(f["distribution_id"] == distribution["model_id"], "FORECAST_MODEL_JOIN")
    require(instant(f["forecast_at"]) == instant(pregame["forecast_at"]),
            "FORECAST_CLOCK_MISMATCH")
    require(instant(f["model_training_cutoff_at"]) <=
            instant(pregame["input_freeze_at"]), "FORECAST_TRAINING_LEAK")
    quote = f["contract"]
    require(quote["stat"] == distribution["stat"], "CONTRACT_STAT_MISMATCH")
    require(quote["player_id"] == distribution["player_id"] and
            quote["team_id"] == distribution["team_id"] and
            quote["period"] == distribution["period"], "CONTRACT_DISTRIBUTION_JOIN")
    require(instant(quote["quote_at"]) <= instant(f["forecast_at"]),
            "FUTURE_QUOTE")
    matches = [q for q in pregame["offers"] if q["contract_id"] == quote["contract_id"]]
    require(len(matches) == 1 and matches[0] == quote, "CONTRACT_BINDING_MISMATCH")
    require(quote["event_id"] == pregame["event_id"], "CONTRACT_EVENT_MISMATCH")
    require(quote["player_id"] in {p["player_id"] for p in pregame["players"]},
            "CONTRACT_PLAYER_MISMATCH")
    require(quote["period"] == "full_game_including_ot", "PERIOD_UNSUPPORTED")
    require(instant(quote["quote_at"]) <= instant(f["forecast_at"]),
            "FUTURE_QUOTE")
    sha(quote["quote_sha256"])
    probs = threshold_triplet(distribution["pmf"], quote["line"])
    require(set(f["probabilities"]) == {"over", "under", "push"},
            "PROBABILITY_KEYS")
    require(f["conditioning"] == distribution["conditioning"],
            "CONDITIONING_MISMATCH")
    for key in probs:
        require(abs(probs[key] - number(f["probabilities"][key], low=0)) <= 1e-10,
                "PROBABILITY_LAW_MISMATCH")
    require(abs(sum(f["probabilities"].values()) - 1) <= 1e-10,
            "PROBABILITY_COMPLEMENTARITY")
    require(f["status"] in ("UNCERTIFIED_SHADOW", "CERTIFICATION_PENDING"),
            "P0_NO_RELEASE")
    require(f.get("p_market") is None, "P0_NO_MARKET_INFERENCE")
    return True


def validate_evaluation(e, forecast, pregame, distribution):
    validate_forecast(forecast, pregame, distribution)
    verify_seal(e)
    require(e["schema"] == VERSION and e["record_type"] == "evaluation",
            "EVALUATION_SCHEMA")
    require(e["forecast_hash"] == forecast["content_hash"], "EVAL_FORECAST_JOIN")
    require(e["contract_id"] == forecast["contract"]["contract_id"],
            "EVAL_CONTRACT_JOIN")
    require(e["status"] in ("pending", "settled", "push", "void"),
            "INVALID_SETTLEMENT")
    require(instant(e["evaluated_at"]) >= instant(pregame["event_start_at"]),
            "PREMATURE_SETTLEMENT")
    if e["status"] in ("settled", "push"):
        require(type(e["actual"]) is int and e["actual"] >= 0,
                "INVALID_SETTLED_COUNT")
        if e["status"] == "push":
            require(e["actual"] == forecast["contract"]["line"], "FALSE_PUSH")
        else:
            require(e["actual"] != forecast["contract"]["line"], "MISLABELED_PUSH")
    else:
        require(e["actual"] is None, "UNVERIFIED_OUTCOME")
    require(e.get("source_receipt_sha256") is not None or
            e["status"] == "pending", "OUTCOME_RECEIPT_MISSING")
    if e.get("source_receipt_sha256"):
        sha(e["source_receipt_sha256"])
    require("cohort_status" in e and "settlement_version" in e,
            "EVALUATION_DENOMINATOR")
    require(type(e["settlement_version"]) is int and
            e["settlement_version"] >= 1, "INVALID_SETTLEMENT_VERSION")
    if e["settlement_version"] > 1:
        require(e.get("supersedes_evaluation_hash") is not None,
                "UNLINKED_SETTLEMENT_REVISION")
        sha(e["supersedes_evaluation_hash"])
    else:
        require(e.get("supersedes_evaluation_hash") is None,
                "UNLINKED_SETTLEMENT_REVISION")
    return True


def validate_bundle(bundle):
    pregame = bundle["pregame"]
    validate_pregame(pregame)
    for item in bundle.get("statistical", []):
        validate_statistical(item, pregame)
    for item in bundle.get("game_states", []):
        validate_game_state(item, pregame)
    for item in bundle.get("opportunities", []):
        game_state = next((g for g in bundle["game_states"]
                           if g["model_id"] == item["game_state_id"]), None)
        require(game_state is not None, "MISSING_G_DEPENDENCY")
        validate_opportunity(item, pregame, game_state)
    for item in bundle.get("joint", []):
        o = next((x for x in bundle["opportunities"]
                  if x["model_id"] == item["opportunity_id"]), None)
        g = next((x for x in bundle["game_states"]
                  if x["model_id"] == item["game_state_id"]), None)
        require(o is not None and g is not None, "MISSING_J_DEPENDENCY")
        require(all(any(s["model_id"] == sid for s in bundle["statistical"])
                    for sid in item["outcome_model_ids"]), "MISSING_S_DEPENDENCY")
        validate_joint(item, pregame, o, g)
    for item in bundle.get("forecasts", []):
        d = next((x for x in bundle["statistical"]
                  if x["model_id"] == item["distribution_id"]), None)
        require(d is not None, "MISSING_S_DEPENDENCY")
        validate_forecast(item, pregame, d)
    return True
