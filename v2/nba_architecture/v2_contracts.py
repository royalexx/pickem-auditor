"""NBA V2.5 S/O/G/J/C architecture contract v2.0.0 (research only).

A contract boundary, not a trained forecast model, source authenticator, or release gate.
The v1 module and the original G0 FAIL are intentionally retained unmodified.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import hashlib
import json
import math

VERSION = "nba-sojc-contract/2.0.0"
PROFILES = ("historical_reconstruction", "original_prospective")
PRIMITIVES = ("points", "rebounds", "assists", "threes")
COMPOSITES = {"pr": ("points", "rebounds"),
              "pa": ("points", "assists"),
              "ra": ("rebounds", "assists"),
              "pra": ("points", "rebounds", "assists")}
STATS = frozenset(PRIMITIVES + tuple(COMPOSITES))
PHYSICAL = ("points", "rebounds", "assists", "threes", "two_pm", "two_pa",
            "three_pa", "fgm", "fga", "ftm", "fta", "oreb", "dreb",
            "steals", "blocks", "turnovers", "pr", "pa", "ra", "pra")


class ContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def req(condition, code):
    if not condition:
        raise ContractError(code)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha(value):
    req(isinstance(value, str) and len(value) == 64
        and all(c in "0123456789abcdef" for c in value), "SHA256_REQUIRED")
    return value


def seal(payload):
    req(isinstance(payload, dict) and "content_hash" not in payload,
        "UNSEALED_REQUIRED")
    return dict(payload, content_hash=digest(payload))


def verify(payload):
    req(isinstance(payload, dict) and "content_hash" in payload,
        "CONTENT_HASH_MISSING")
    actual = sha(payload["content_hash"])
    obj = {key: value for key, value in payload.items() if key != "content_hash"}
    req(digest(obj) == actual, "CONTENT_HASH_MISMATCH")
    return actual


def freeze_once(path, payload):
    verify(payload)
    raw = canonical(payload) + b"\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        req(path.read_bytes() == raw, "IMMUTABLE_CONFLICT")
    return payload["content_hash"]


def instant(value):
    req(isinstance(value, str) and "T" in value, "TIMESTAMP_REQUIRED")
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP") from exc
    req(x.tzinfo is not None and x.utcoffset().total_seconds() == 0
        and (value.endswith("Z") or value.endswith("+00:00")),
        "UTC_TIMESTAMP_REQUIRED")
    return x.astimezone(timezone.utc)


def calendar(value):
    req(isinstance(value, str), "CALENDAR_DATE_REQUIRED")
    try:
        x = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("CALENDAR_DATE_REQUIRED") from exc
    req(x.isoformat() == value, "CALENDAR_DATE_REQUIRED")
    return x


def num(x, minimum=0):
    req(type(x) in (int, float) and math.isfinite(x), "FINITE_NUMBER_REQUIRED")
    req(x >= minimum, "NUMBER_BELOW_MINIMUM")
    return x


def ident(x):
    req(isinstance(x, str) and x.strip() == x and bool(x)
        and ":" in x, "NAMESPACED_ID_REQUIRED")
    return x


def strict_keys(d, keys):
    req(isinstance(d, dict) and set(d) == set(keys), "UNEXPECTED_FIELDS")


def check_schema(obj, kind):
    req(isinstance(obj, dict) and obj.get("schema") == VERSION
        and obj.get("kind") == kind, "SCHEMA_VERSION_OR_KIND")
    return verify(obj)


def receipt(payload):
    """Create a stand-alone, self-consistent receipt; no proof of external truth."""
    req(isinstance(payload, dict) and "receipt_sha256" not in payload,
        "RECEIPT_UNSEALED_REQUIRED")
    return dict(payload, receipt_sha256=digest(payload))


def validate_receipt(r, profile, freeze_at, local_day):
    req(isinstance(r, dict) and "receipt_sha256" in r, "RECEIPT_MISSING")
    actual = sha(r["receipt_sha256"])
    req(digest({k: v for k, v in r.items() if k != "receipt_sha256"}) == actual,
        "RECEIPT_HASH_MISMATCH")
    ident(r["source_id"])
    sha(r["raw_sha256"])
    req(type(r["source_revision"]) is int and r["source_revision"] >= 1,
        "SOURCE_REVISION")
    if r["source_revision"] == 1:
        req(r.get("supersedes_receipt_sha256") is None, "UNLINKED_FIRST_REVISION")
    else:
        sha(r["supersedes_receipt_sha256"])
    # Times are separate physical/evidentiary events. No fictional publication time;
    # no unproven retrieval->observation->ingestion order is imposed.
    observed = instant(r["collector_observed_at"])
    retrieved = instant(r["retrieved_at"])
    ingested = instant(r["ingested_at"])
    published = r["provider_published_at"]
    if published is not None:
        pub = instant(published)
        req(r["publication_evidence"] in ("source_header_claim", "verified"),
            "PUBLICATION_EVIDENCE_REQUIRED")
        # Independently verified publication cannot post-date a retrieval of the bytes.
        if r["publication_evidence"] == "verified":
            req(pub <= retrieved, "PUBLICATION_AFTER_RETRIEVAL")
    else:
        req(r["publication_evidence"] == "unknown", "UNKNOWN_PUBLICATION_INFERRED")
    req(r["scope"] in ("prior_game", "pregame_context", "original_offer"),
        "INVALID_SOURCE_SCOPE")
    req(r["contains_target_final"] is False, "TARGET_GAME_LEAKAGE")
    if profile == "original_prospective":
        if published is not None:
            req(instant(published) <= freeze_at, "PUBLICATION_CLAIM_AFTER_FREEZE")
        req(r["origin"] == "original_capture" and
            r["asof_basis"] == "observed_before_freeze",
            "PROSPECTIVE_SOURCE_REQUIRED")
        req(all(t <= freeze_at for t in (observed, retrieved, ingested)),
            "POSTFREEZE_SOURCE")
        if r["provider_published_at"] is not None and r["publication_evidence"] == "verified":
            req(instant(r["provider_published_at"]) <= freeze_at,
                "FUTURE_PUBLISHED_SOURCE")
        req(r["historical_game_date"] is None, "PROSPECTIVE_DATE_PROXY_FORBIDDEN")
    else:
        req(r["origin"] == "retrospective_retrieval" and
            r["asof_basis"] == "prior_game_date_only" and
            bool(r["asof_limitations"]),
            "HISTORICAL_PROXY_DISCLOSURE")
        req(r["scope"] == "prior_game", "RETROSPECTIVE_CONTEXT_NOT_PROVEN")
        req(r["historical_game_date"] is not None and
            calendar(r["historical_game_date"]) < local_day,
            "HISTORICAL_PRIOR_DATE_REQUIRED")
        # Later archive retrieval is allowed; this does not attest that data
        # or later corrections were available on the simulated historic date.
    return True


def validate_pregame(p):
    check_schema(p, "pregame")
    profile = p["source_profile"]
    req(profile in PROFILES, "SOURCE_PROFILE")
    ident(p["game_id"])
    teams = p["team_ids"]
    req(isinstance(teams, list) and len(teams) == 2
        and len(set(teams)) == 2, "TWO_TEAMS_REQUIRED")
    for team in teams:
        ident(team)
    freeze = instant(p["input_freeze_at"])
    decision = instant(p["forecast_at"])
    event = instant(p["event_start_at"])
    cutoff = instant(p["training_cutoff_at"])
    req(cutoff <= freeze <= decision < event, "PREGAME_CLOCK_ORDER")
    local_day = calendar(p["decision_local_date"])
    # Provided local date must be independently sourced; do not derive timezone from UTC.
    if profile == "historical_reconstruction":
        req(p["certification"] == "HISTORICAL_RECONSTRUCTION_UNCERTIFIED",
            "RETROSPECTIVE_CERTIFICATION_FORBIDDEN")
    else:
        req(p["certification"] == "ORIGINAL_SOURCE_SHADOW",
            "PROSPECTIVE_CERTIFICATION_FORBIDDEN")
    sources = p["sources"]
    req(isinstance(sources, list) and len(sources) > 0, "SOURCE_RECEIPTS_REQUIRED")
    by_source = {}
    for source in sources:
        validate_receipt(source, profile, freeze, local_day)
        by_source.setdefault(source["source_id"], []).append(source)
    for group in by_source.values():
        ordered = sorted(group, key=lambda x: x["source_revision"])
        req(len({x["source_revision"] for x in ordered}) == len(ordered),
            "DUPLICATE_SOURCE_REVISION")
        for i, r in enumerate(ordered):
            if i:
                req(r["source_revision"] > ordered[i-1]["source_revision"] and
                    r["supersedes_receipt_sha256"] == ordered[i-1]["receipt_sha256"],
                    "SOURCE_REVISION_CHAIN")
            elif r["source_revision"] != 1:
                # When the preceding receipt is external, the predecessor is
                # independently referenced by digest but must be auditable.
                req(r["supersedes_receipt_sha256"] is not None,
                    "MISSING_SOURCE_PREDECESSOR")
    ids = {}
    req(isinstance(p["players"], list) and bool(p["players"]), "ROSTER_REQUIRED")
    for player in p["players"]:
        pid = ident(player["player_id"])
        req(pid not in ids, "DUPLICATE_PLAYER")
        ids[pid] = player["team_id"]
        req(player["team_id"] in teams, "PLAYER_TEAM_MISMATCH")
        req(player["legal_eligibility"] in (True, False, None),
            "INVALID_ELIGIBILITY")
        req(player["availability"] in ("out", "active_reported", "questionable", "unknown"),
            "INVALID_AVAILABILITY")
        if profile == "historical_reconstruction":
            req(player["legal_eligibility"] is None
                or player["eligibility_evidence"] == "prior_dated_record",
                "HISTORICAL_ELIGIBILITY_LEAK")
    for feature in p["features"]:
        strict_keys(feature, ("source_id","source_receipt_sha256","name","value",
                              "kind","asof_basis","target_game_outcome",
                              "prior_game_date","available_at","measurement_units"))
        req(feature["source_id"] in by_source, "FEATURE_SOURCE_UNKNOWN")
        req(feature["source_receipt_sha256"] in
            {r["receipt_sha256"] for r in by_source[feature["source_id"]]},
            "FEATURE_REVISION_UNBOUND")
        req(isinstance(feature["name"], str) and
            bool(feature["name"]) and
            not any(bad in feature["name"].lower() for bad in
                ("target","final","actual","postgame","future","result",
                 "same_game","samegame")), "FEATURE_NAME_LEAKAGE")
        req(type(feature["value"]) in (str, int, float, bool, type(None))
            or (isinstance(feature["value"], list)
                and all(type(v) in (int,float) and math.isfinite(v)
                        for v in feature["value"])), "UNTYPED_FEATURE_PAYLOAD")
        if type(feature["value"]) in (int, float):
            num(feature["value"], minimum=-math.inf)
        req(isinstance(feature["measurement_units"], str)
            and bool(feature["measurement_units"]), "FEATURE_UNIT_REQUIRED")
        req(feature["target_game_outcome"] is False
            and feature["kind"] != "target_game_result",
            "TARGET_GAME_FEATURE_LEAK")
        req(feature["kind"] in ("prior_boxscore", "schedule", "pregame_availability",
                                "pregame_team_context"), "UNKNOWN_FEATURE_KIND")
        if profile == "historical_reconstruction":
            req(feature["kind"] == "prior_boxscore"
                and calendar(feature["prior_game_date"]) < local_day
                and feature["asof_basis"] == "prior_game_date_only",
                "HISTORICAL_FEATURE_LEAK")
        else:
            req(feature["asof_basis"] == "original_capture"
                and instant(feature["available_at"]) <= freeze,
                "FUTURE_FEATURE")
    # v2 does NOT require an offer to form or freeze a player-stat distribution.
    req(p["original_offer_count"] >= 0 and type(p["original_offer_count"]) is int,
        "OFFER_COUNT_INVALID")
    return True


def component(c):
    req(isinstance(c, dict), "MODEL_COMPONENT_REQUIRED")
    ident(c["model_id"])
    req(isinstance(c["version"], str) and bool(c["version"]), "MODEL_VERSION")
    sha(c["artifact_sha256"])
    sha(c["code_sha256"])
    instant(c["training_cutoff_at"])
    return True


def validate_distribution(d, p, scenarios=None):
    validate_pregame(p)
    check_schema(d, "distribution")
    req(d["source_snapshot_sha256"] == p["content_hash"], "SOURCE_LINEAGE")
    req(d["game_id"] == p["game_id"], "GAME_IDENTITY")
    req(d["event_start_at"] == p["event_start_at"], "DISTRIBUTION_EVENT_START")
    ids = {x["player_id"]: x["team_id"] for x in p["players"]}
    req(d["player_id"] in ids and ids[d["player_id"]] == d["team_id"],
        "STAT_PLAYER_TEAM_MISMATCH")
    req(d["stat"] in STATS and d["period"] == "full_game_including_ot",
        "STAT_PERIOD")
    req(d["source_profile"] == p["source_profile"], "PROFILE_MISMATCH")
    req(d["status"] == ("RESEARCH_RECONSTRUCTION" if p["source_profile"] ==
        "historical_reconstruction" else "UNCERTIFIED_SHADOW"), "STATUS_NOT_RELEASED")
    req(d["support"] == "nonnegative_integer", "STAT_SUPPORT")
    mode = d["pipeline_mode"]
    req(mode in ("S_ONLY", "S_O", "S_O_J"), "PIPELINE_MODE")
    req(d["conditioning"] in ("unconditional", "conditional_on_participation",
                               "conditional_on_declared_roster"),
        "CONDITIONING_REQUIRED")
    lineage = d["lineage"]
    req(set(lineage) == {"S", "O", "G", "J"}, "PIPELINE_FAMILY_LINEAGE")
    required = {"S_ONLY": {"S"}, "S_O": {"S", "O"},
                "S_O_J": {"S", "O", "G", "J"}}[mode]
    for name in ("S", "O", "G", "J"):
        if name in required:
            component(lineage[name])
            req(instant(lineage[name]["training_cutoff_at"]) <=
                instant(p["input_freeze_at"]), "FUTURE_MODEL_FIT")
        else:
            req(lineage[name] is None or (name == "G" and mode == "S_O"
                and component(lineage[name])), "UNDECLARED_DEPENDENCY")
    req(d["forecast_at"] == p["forecast_at"], "FORECAST_TIME_JOIN")
    req(instant(d["frozen_at"]) <= instant(p["event_start_at"]) and
        instant(d["frozen_at"]) >= instant(d["forecast_at"]),
        "FORECAST_FREEZE_TIME")
    req(type(d["rng_seed"]) is int and d["rng_seed"] >= 0, "INVALID_SEED")
    pmf = d["pmf"]
    req(isinstance(pmf, list) and bool(pmf), "PMF_EMPTY")
    values = set()
    total = 0.0
    for row in pmf:
        req(type(row["value"]) is int and row["value"] >= 0
            and row["value"] not in values, "PMF_SUPPORT")
        values.add(row["value"])
        total += num(row["mass"])
    req(abs(total - 1.0) <= 1e-10, "PMF_NOT_NORMALIZED")
    numerical = d["numerical"]
    num(numerical["tail_mass_upper_bound"])
    req(numerical["tail_mass_upper_bound"] <= 1e-8, "TRUNCATED_LAW_UNCERTIFIED")
    req(numerical["method"] in ("analytic", "empirical_mc"), "NUMERICAL_METHOD")
    if numerical["method"] == "empirical_mc":
        req(type(numerical["scenario_count"]) is int
            and numerical["scenario_count"] > 0, "MC_COUNT_REQUIRED")
        num(numerical["max_probability_se"])
        req(numerical["max_probability_se"] <= .5, "MC_SE_INVALID")
    else:
        req(numerical["scenario_count"] is None and
            numerical["max_probability_se"] is None, "ANALYTIC_MC_CONFLICT")
    if mode == "S_O_J":
        sha(d["scenario_bundle_sha256"])
        req(numerical["method"] == "empirical_mc", "J_REQUIRES_EMPIRICAL_PMF")
    else:
        req(d["scenario_bundle_sha256"] is None, "UNEXPECTED_J_SCENARIOS")
    if d["stat"] in COMPOSITES and mode == "S_O_J":
        req(d["derivation"] == "same_draw_primitive_sum", "COMPOSITE_J_DERIVATION")
    if scenarios is not None:
        req(mode == "S_O_J", "SCENARIOS_ONLY_FOR_J")
        validate_scenarios(scenarios, p)
        req(d["scenario_bundle_sha256"] == scenarios["content_hash"],
            "J_SCENARIO_BINDING")
        pmf_actual = {}
        for sc in scenarios["scenarios"]:
            player = next(x for x in sc["players"] if x["player_id"] == d["player_id"])
            key = player["stats"][d["stat"]]
            pmf_actual[key] = pmf_actual.get(key, 0) + sc["weight"]
        req({x["value"]: x["mass"] for x in pmf} == pmf_actual,
            "J_MARGINAL_NOT_FROM_DRAWS")
        req(d["lineage"] == scenarios["lineage"], "J_LINEAGE_MISMATCH")
    if p["source_profile"] == "historical_reconstruction":
        req(d["historical_asof_limitations"] == p["historical_asof_limitations"]
            and bool(d["historical_asof_limitations"]),
            "HISTORICAL_LIMITATION_LOST")
    return True


def validate_scenarios(s, p):
    validate_pregame(p)
    check_schema(s, "scenarios")
    req(s["source_snapshot_sha256"] == p["content_hash"]
        and s["game_id"] == p["game_id"], "SCENARIO_SOURCE_JOIN")
    req(s["pipeline_mode"] == "S_O_J", "NOT_J_SCENARIOS")
    sha(s["game_state_sha256"])
    sha(s["opportunity_sha256"])
    req(all(k in s["lineage"] for k in ("S", "O", "G", "J")),
        "SCENARIO_LINEAGE")
    for name in ("S", "O", "G", "J"):
        component(s["lineage"][name])
        req(instant(s["lineage"][name]["training_cutoff_at"]) <=
            instant(p["input_freeze_at"]), "SCENARIO_MODEL_FUTURE")
    rows = s["scenarios"]
    req(isinstance(rows, list) and bool(rows), "SCENARIOS_EMPTY")
    ids = set()
    probs = 0.0
    universe = {x["player_id"]: x for x in p["players"]}
    for scenario in rows:
        sid = ident(scenario["scenario_id"])
        req(sid not in ids, "DUPLICATE_SCENARIO")
        ids.add(sid)
        probs += num(scenario["weight"])
        ot = scenario["overtime_periods"]
        req(type(ot) is int and ot >= 0, "INVALID_OVERTIME")
        duration = 48 + 5 * ot
        parts = scenario["players"]
        req(len(parts) == len(universe), "INCOMPLETE_J_ROSTER")
        pids = [x["player_id"] for x in parts]
        req(len(pids) == len(set(pids)) and set(pids) == set(universe),
            "J_ROSTER_IDENTITY")
        req(scenario["team_points"][p["team_ids"][0]] !=
            scenario["team_points"][p["team_ids"][1]], "TIED_FINAL_SCORE")
        for team in p["team_ids"]:
            members = [x for x in parts if x["team_id"] == team]
            req(abs(sum(num(x["minutes"]) for x in members) - 5*duration) < 1e-7,
                "TEAM_MINUTES_CONSERVATION")
            req(sum(x["stats"]["points"] for x in members) ==
                scenario["team_points"][team], "TEAM_POINTS_CONSERVATION")
            req(sum(x["stats"]["assists"] for x in members) <=
                sum(x["stats"]["fgm"] for x in members), "TEAM_ASSISTS_CAP")
        for x in parts:
            pid = x["player_id"]
            req(x["team_id"] == universe[pid]["team_id"], "SCENARIO_TEAM_MISMATCH")
            minutes = num(x["minutes"])
            req(minutes <= duration, "PLAYER_MINUTES_CAP")
            state = x["participation"]
            req(state in ("DNP", "PLAYED_ZERO_MINUTES", "PLAYED"),
                "PARTICIPATION_STATE")
            if state == "PLAYED":
                req(minutes > 0, "PLAYED_REQUIRES_MINUTES")
            else:
                req(minutes == 0, "NONPLAYED_MINUTES")
            if universe[pid]["legal_eligibility"] is False:
                req(state == "DNP", "INELIGIBLE_PLAYED")
            stats = x["stats"]
            req(set(stats) == set(PHYSICAL), "FULL_STAT_VECTOR_REQUIRED")
            for name in PHYSICAL:
                req(type(stats[name]) is int and stats[name] >= 0,
                    "INVALID_COUNT_" + name)
            req(stats["two_pm"] <= stats["two_pa"] and
                stats["threes"] <= stats["three_pa"], "SHOT_CONVERSIONS")
            req(stats["fgm"] == stats["two_pm"] + stats["threes"]
                and stats["fga"] == stats["two_pa"] + stats["three_pa"],
                "FG_ACCOUNTING")
            req(stats["ftm"] <= stats["fta"], "FT_CONVERSION")
            req(stats["points"] == 2*stats["two_pm"] + 3*stats["threes"] +
                stats["ftm"], "POINTS_ACCOUNTING")
            req(stats["rebounds"] == stats["oreb"] + stats["dreb"],
                "REBOUND_ACCOUNTING")
            for combo, keys in COMPOSITES.items():
                req(stats[combo] == sum(stats[k] for k in keys),
                    "COMBO_ACCOUNTING_" + combo)
            if state != "PLAYED":
                req(all(val == 0 for val in stats.values()), "ZERO_MINUTE_STATS")
    req(abs(probs - 1.0) <= 1e-10, "SCENARIO_WEIGHTS")
    # The shared state and O values are checked against their provided witnesses.
    for source_name in ("game_state_witness", "opportunity_witness"):
        witness = s[source_name]
        req(set(witness) == ids, "SCENARIO_WITNESS_COVERAGE")
    lookup = {x["scenario_id"]: x for x in rows}
    for sid in ids:
        expected = lookup[sid]
        g = s["game_state_witness"][sid]
        req(g["overtime_periods"] == expected["overtime_periods"] and
            abs(g["weight"] - expected["weight"]) <= 1e-12,
            "INDEPENDENT_GAME_STATE_DRAW")
        a = {x["player_id"]: x for x in s["opportunity_witness"][sid]}
        req(set(a) == set(universe), "OPPORTUNITY_WITNESS_ROSTER")
        for x in expected["players"]:
            b = a[x["player_id"]]
            req(b["team_id"] == x["team_id"] and
                b["participation"] == x["participation"] and
                b["minutes"] == x["minutes"], "OPPORTUNITY_DRAW_CHANGED")
    return True


def marginal_from_joint(s, p, player_id, stat, frozen_at, rng_seed,
                        historical_asof_limitations=None):
    """Extract one J marginal from immutable shared outcomes; never a new vote."""
    validate_scenarios(s, p)
    req(stat in STATS, "UNSUPPORTED_STAT")
    ident(player_id)
    universe = {x["player_id"]: x["team_id"] for x in p["players"]}
    req(player_id in universe, "UNKNOWN_PLAYER")
    bins = {}
    for sc in s["scenarios"]:
        player = next(x for x in sc["players"] if x["player_id"] == player_id)
        val = player["stats"][stat]
        bins[val] = bins.get(val, 0.0) + sc["weight"]
    pmf = [{"value": k, "mass": bins[k]} for k in sorted(bins)]
    numerical = {"method": "empirical_mc", "scenario_count": len(s["scenarios"]),
                 "max_probability_se": max(math.sqrt(x["mass"]*(1-x["mass"]) /
                     len(s["scenarios"])) for x in pmf),
                 "tail_mass_upper_bound": 0.0}
    # Winning probability is conditioned exactly as J was, not inferred from a quote.
    d = seal(dict(schema=VERSION, kind="distribution",
        source_profile=p["source_profile"], game_id=p["game_id"],
        player_id=player_id, team_id=universe[player_id], stat=stat,
        period="full_game_including_ot", support="nonnegative_integer",
        pipeline_mode="S_O_J", conditioning=s["conditioning"],
        status="RESEARCH_RECONSTRUCTION" if p["source_profile"] ==
          "historical_reconstruction" else "UNCERTIFIED_SHADOW",
        source_snapshot_sha256=p["content_hash"], lineage=s["lineage"],
        event_start_at=p["event_start_at"], forecast_at=p["forecast_at"], frozen_at=frozen_at, rng_seed=rng_seed,
        scenario_bundle_sha256=s["content_hash"], derivation=
          "same_draw_primitive_sum" if stat in COMPOSITES else "same_draw_primitive",
        numerical=numerical, pmf=pmf,
        historical_asof_limitations=p["historical_asof_limitations"]))
    validate_distribution(d, p)
    return d


def threshold_triplet(pmf, line):
    num(line)
    return {name: sum(x["mass"] for x in pmf if predicate(x["value"], line))
            for name, predicate in (("over", lambda x, y: x > y),
                                    ("under", lambda x, y: x < y),
                                    ("push", lambda x, y: x == y))}


def validate_offer(q, p):
    validate_pregame(p)
    check_schema(q, "original_offer")
    req(p["source_profile"] == "original_prospective",
        "HISTORICAL_OFFER_NOT_ORIGINAL")
    req(q["source_snapshot_sha256"] == p["content_hash"], "OFFER_SNAPSHOT_JOIN")
    req(q["game_id"] == p["game_id"], "OFFER_GAME_JOIN")
    people = {x["player_id"]: x["team_id"] for x in p["players"]}
    req(q["player_id"] in people and people[q["player_id"]] == q["team_id"],
        "OFFER_PLAYER_JOIN")
    req(q["stat"] in STATS and q["period"] == "full_game_including_ot",
        "OFFER_STAT_PERIOD")
    for key in ("contract_id", "quote_id", "book", "product_type"):
        req(isinstance(q[key], str) and bool(q[key]), "OFFER_ID_REQUIRED")
    num(q["line"])
    sha(q["raw_quote_sha256"])
    refs = {x["receipt_sha256"]: x for x in p["sources"]}
    req(q["source_receipt_sha256"] in refs, "UNBOUND_ORIGINAL_OFFER")
    r = refs[q["source_receipt_sha256"]]
    req(r["scope"] == "original_offer" and r["raw_sha256"] == q["raw_quote_sha256"],
        "OFFER_BYTES_MISMATCH")
    req(instant(q["quoted_at"]) <= instant(p["input_freeze_at"]) and
        instant(q["observed_at"]) <= instant(p["input_freeze_at"]),
        "POSTFREEZE_OFFER")
    return True


def offer_view(d, q, p, frozen_at):
    validate_distribution(d, p)
    validate_offer(q, p)
    req(q["player_id"] == d["player_id"] and q["team_id"] == d["team_id"] and
        q["stat"] == d["stat"] and q["period"] == d["period"],
        "DISTRIBUTION_OFFER_IDENTITY")
    req(instant(frozen_at) >= instant(d["frozen_at"]) and
        instant(frozen_at) < instant(p["event_start_at"]),
        "OFFER_VIEW_FREEZE")
    raw = seal(dict(schema=VERSION, kind="offer_view", game_id=d["game_id"],
        distribution_sha256=d["content_hash"], original_offer_sha256=q["content_hash"],
        contract_id=q["contract_id"], quote_id=q["quote_id"], quote_source_receipt=q["source_receipt_sha256"],
        probabilities=threshold_triplet(d["pmf"], q["line"]),
        status="UNCERTIFIED_SHADOW", frozen_at=frozen_at,
        product_void_semantics="requires_original_product_terms"))
    validate_offer_view(raw, d, q, p)
    return raw


def validate_offer_view(v, d, q, p):
    validate_distribution(d, p)
    validate_offer(q, p)
    check_schema(v, "offer_view")
    req(q["game_id"] == d["game_id"] and
        q["player_id"] == d["player_id"] and
        q["team_id"] == d["team_id"] and
        q["stat"] == d["stat"] and q["period"] == d["period"],
        "DISTRIBUTION_OFFER_IDENTITY")
    req(v["distribution_sha256"] == d["content_hash"] and
        v["original_offer_sha256"] == q["content_hash"] and
        v["contract_id"] == q["contract_id"] and
        v["quote_id"] == q["quote_id"] and
        v["quote_source_receipt"] == q["source_receipt_sha256"],
        "OFFER_VIEW_LINEAGE")
    req(v["status"] == "UNCERTIFIED_SHADOW", "OFFER_VIEW_RELEASE_BLOCKED")
    req(instant(v["frozen_at"]) < instant(p["event_start_at"]) and
        instant(v["frozen_at"]) >= instant(d["frozen_at"]),
        "OFFER_VIEW_TIME")
    probabilities = v["probabilities"]
    req(set(probabilities) == {"over", "under", "push"}, "TRIPLET_REQUIRED")
    expected = threshold_triplet(d["pmf"], q["line"])
    for name in expected:
        req(abs(num(probabilities[name]) - expected[name]) < 1e-10,
            "TRIPLET_MISMATCH")
    req(abs(sum(probabilities.values()) - 1) < 1e-10,
        "TRIPLET_NOT_COMPLEMENTARY")
    req(v["product_void_semantics"] == "requires_original_product_terms",
        "DNP_VOID_INFERRED")
    return True


def validate_evaluation(e, distribution, offer=None):
    check_schema(e, "evaluation")
    req(e["distribution_sha256"] == verify(distribution), "SETTLEMENT_DISTRIBUTION")
    if offer is None:
        req(e["offer_view_sha256"] is None, "UNKNOWN_OFFER_VIEW")
    else:
        req(e["offer_view_sha256"] == verify(offer), "SETTLEMENT_OFFER_VIEW")
    status = e["status"]
    req(status in ("pending", "settled", "push", "void", "unmatched"),
        "SETTLEMENT_STATUS")
    req(type(e["revision"]) is int and e["revision"] >= 1,
        "SETTLEMENT_REVISION")
    if e["revision"] > 1:
        req(e["supersedes_evaluation_sha256"] is not None,
            "CORRECTION_PREDECESSOR_MISSING")
        sha(e["supersedes_evaluation_sha256"])
    else:
        req(e["supersedes_evaluation_sha256"] is None,
            "FIRST_SETTLEMENT_HAS_PARENT")
    req(instant(e["evaluated_at"]) >= instant(e["event_start_at"]),
        "EVALUATED_BEFORE_EVENT")
    req(e["game_id"] == distribution["game_id"], "EVAL_GAME_MISMATCH")
    req(e["event_start_at"] == distribution["event_start_at"],
        "EVAL_EVENT_START_MISMATCH")
    if status in ("pending", "unmatched", "void"):
        req(e["actual"] is None, "OUTCOME_MUST_BE_NULL")
    else:
        req(type(e["actual"]) is int and e["actual"] >= 0,
            "OFFICIAL_COUNT_REQUIRED")
        sha(e["official_source_sha256"])
        if offer is not None and e["contract_line"] is not None:
            if status == "push":
                req(e["actual"] == e["contract_line"], "FALSE_PUSH")
            else:
                req(e["actual"] != e["contract_line"], "MISLABELED_PUSH")
    req(e["participation"] in ("unknown", "DNP", "PLAYED_ZERO_MINUTES", "PLAYED"),
        "SETTLEMENT_PARTICIPATION")
    if status == "void":
        req(e["void_basis"] is not None, "VOID_TERMS_UNVERIFIED")
    return True


def seed_for(master, event_id, scenario_id, component_version):
    req(type(master) is int and master >= 0, "INVALID_SEED")
    for value in (event_id, scenario_id, component_version):
        req(isinstance(value, str) and value and "|" not in value,
            "AMBIGUOUS_SEED")
    raw = "|".join((VERSION, str(master), event_id, scenario_id, component_version))
    return int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest()[:8], "big")
