"""Deterministic structural NBA v2 fixtures (all values synthetic, not measured).

No game result is taken from any current or historical NBA game.
"""
from v2.nba_architecture.v2_contracts import (
    VERSION, receipt, seal, marginal_from_joint,
)

H = "a" * 64
B = "b" * 64
C = "c" * 64
H_EVENT = "2022-10-20T00:00:00Z"
H_FREEZE = "2022-10-19T23:00:00Z"
H_FORECAST = "2022-10-19T23:01:00Z"
H_TRAIN = "2022-10-19T00:00:00Z"
P_EVENT = "2026-11-17T00:00:00Z"
P_FREEZE = "2026-11-16T23:00:00Z"
P_FORECAST = "2026-11-16T23:01:00Z"
P_TRAIN = "2026-11-16T20:00:00Z"
P_OBS = "2026-11-16T22:40:00Z"


def players():
    return [{"player_id": "espn:player:%s%d" % (t, i),
             "team_id": "espn:team:%s" % t,
             "legal_eligibility": None, "eligibility_evidence": None,
             "availability": "unknown"}
            for t in (1, 2) for i in range(6)]


def source(profile, source_id, scope="prior_game", revision=1,
           predecessor=None, prior="2022-10-17"):
    hist = profile == "historical_reconstruction"
    return receipt({
        "source_id": source_id, "source_revision": revision,
        "supersedes_receipt_sha256": predecessor, "raw_sha256": H if scope != "original_offer" else B,
        "origin": "retrospective_retrieval" if hist else "original_capture",
        "scope": scope, "contains_target_final": False,
        "provider_published_at": None, "publication_evidence": "unknown",
        "collector_observed_at": "2026-11-16T13:00:00Z" if hist else P_OBS,
        "retrieved_at": "2026-11-16T12:55:00Z" if hist else P_OBS,
        "ingested_at": "2026-11-16T13:05:00Z" if hist else "2026-11-16T22:45:00Z",
        "asof_basis": "prior_game_date_only" if hist else "observed_before_freeze",
        "historical_game_date": prior if hist else None,
        "asof_limitations": "Date-only prior-game proxy; current archive retrieved in 2026; no contemporary publication certificate." if hist else None,
    })


def pregame(profile="historical_reconstruction", with_offer=False):
    hist = profile == "historical_reconstruction"
    s = [source(profile, "espn:source:boxscore" if hist else "espn:source:pregame",
                scope="prior_game" if hist else "pregame_context")]
    if with_offer:
        assert not hist
        s.append(source(profile, "book:source:original_quote", scope="original_offer"))
    pts = players()
    limitations = s[0]["asof_limitations"] if hist else None
    return seal({
        "schema": VERSION, "kind": "pregame",
        "source_profile": profile, "game_id": "espn:game:synthetic-2022" if hist else "espn:game:synthetic-2026",
        "team_ids": ["espn:team:1", "espn:team:2"],
        "event_start_at": H_EVENT if hist else P_EVENT,
        "input_freeze_at": H_FREEZE if hist else P_FREEZE,
        "forecast_at": H_FORECAST if hist else P_FORECAST,
        "training_cutoff_at": H_TRAIN if hist else P_TRAIN,
        "decision_local_date": "2022-10-19" if hist else "2026-11-16",
        "certification": "HISTORICAL_RECONSTRUCTION_UNCERTIFIED" if hist else "ORIGINAL_SOURCE_SHADOW",
        "historical_asof_limitations": limitations,
        "sources": s, "players": pts, "original_offer_count": 1 if with_offer else 0,
        "features": [{"source_id": s[0]["source_id"],
                      "source_receipt_sha256": s[0]["receipt_sha256"],
                      "name": "prior_points" if hist else "scheduled_game",
                      "value": 7 if hist else "scheduled",
                      "measurement_units": "count" if hist else "status",
                      "kind": "prior_boxscore" if hist else "schedule",
                      "asof_basis": "prior_game_date_only" if hist else "original_capture",
                      "target_game_outcome": False,
                      "prior_game_date": "2022-10-17" if hist else None,
                      "available_at": None if hist else P_OBS}]
    })


def model(label, p):
    return {"model_id": "research:%s:v2" % label, "version": "v2.fixture",
            "artifact_sha256": H, "code_sha256": C,
            "training_cutoff_at": p["training_cutoff_at"]}


def distribution(p, stat="points", mode="S_ONLY", value=2):
    labels = {"S": model("S", p), "O": None, "G": None, "J": None}
    if mode in ("S_O", "S_O_J"):
        labels["O"] = model("O", p)
    if mode == "S_O_J":
        labels["G"] = model("G", p)
        labels["J"] = model("J", p)
    return seal({
        "schema": VERSION, "kind": "distribution",
        "source_profile": p["source_profile"],
        "source_snapshot_sha256": p["content_hash"], "game_id": p["game_id"],
        "player_id": p["players"][0]["player_id"], "team_id": p["players"][0]["team_id"],
        "stat": stat, "period": "full_game_including_ot",
        "support": "nonnegative_integer", "pipeline_mode": mode,
        "conditioning": "unconditional", "status":
            "RESEARCH_RECONSTRUCTION" if p["source_profile"] ==
             "historical_reconstruction" else "UNCERTIFIED_SHADOW",
        "lineage": labels, "forecast_at": p["forecast_at"],
        "frozen_at": ("2022-10-19T23:02:00Z" if p["source_profile"] ==
                      "historical_reconstruction" else "2026-11-16T23:02:00Z"),
        "rng_seed": 42, "scenario_bundle_sha256": None,
        "derivation": "synthetic_analytic_fixture" if mode != "S_O" else "synthetic_opportunity_fixture",
        "numerical": {"method": "analytic", "scenario_count": None,
                      "max_probability_se": None, "tail_mass_upper_bound": 0.0},
        "pmf": [{"value": 0, "mass": .25}, {"value": value, "mass": .75}],
        "historical_asof_limitations": p["historical_asof_limitations"]
    })


def original_offer(p):
    r = next(x for x in p["sources"] if x["scope"] == "original_offer")
    return seal({
        "schema": VERSION, "kind": "original_offer",
        "source_snapshot_sha256": p["content_hash"], "game_id": p["game_id"],
        "player_id": p["players"][0]["player_id"], "team_id": p["players"][0]["team_id"],
        "stat": "points", "period": "full_game_including_ot",
        "contract_id": "book:contract:synthetic-1", "quote_id": "book:quote:synthetic-1",
        "book": "synthetic_fixture_book", "product_type": "original_fixture_offer",
        "line": 1.5, "raw_quote_sha256": r["raw_sha256"],
        "source_receipt_sha256": r["receipt_sha256"],
        "quoted_at": "2026-11-16T22:35:00Z",
        "observed_at": P_OBS, "payout_terms": None
    })


def zero_stats():
    keys = ("points", "rebounds", "assists", "threes", "two_pm", "two_pa",
            "three_pa", "fgm", "fga", "ftm", "fta", "oreb", "dreb",
            "steals", "blocks", "turnovers", "pr", "pa", "ra", "pra")
    return {key: 0 for key in keys}


def j_scenarios(p):
    scenarios = []
    g = {}
    o = {}
    for idx, (sid, weight) in enumerate((("synthetic:draw:0", .4),
                                         ("synthetic:draw:1", .6))):
        rows = []
        for i, player in enumerate(p["players"]):
            stats = zero_stats()
            if i == 0:
                if idx == 0:
                    stats.update({"points": 2, "two_pm": 1, "two_pa": 1,
                                  "fgm": 1, "fga": 1, "pr": 2, "pa": 2, "pra": 2})
                else:
                    stats.update({"points": 3, "threes": 1, "three_pa": 1,
                                  "fgm": 1, "fga": 1, "pr": 3, "pa": 3, "pra": 3})
            if i % 6 == 5:
                status = "DNP" if idx == 0 else "PLAYED_ZERO_MINUTES"
                minutes = 0.
            else:
                status = "PLAYED"
                minutes = 48.
            rows.append({"player_id": player["player_id"], "team_id": player["team_id"],
                         "minutes": minutes, "participation": status, "stats": stats})
        scenarios.append({"scenario_id": sid, "weight": weight,
                          "overtime_periods": 0,
                          "team_points": {"espn:team:1": 2 if idx == 0 else 3,
                                          "espn:team:2": 0},
                          "players": rows})
        g[sid] = {"overtime_periods": 0, "weight": weight}
        o[sid] = [{k: row[k] for k in ("player_id", "team_id", "minutes", "participation")}
                  for row in rows]
    return seal({"schema": VERSION, "kind": "scenarios",
                 "source_snapshot_sha256": p["content_hash"], "game_id": p["game_id"],
                 "pipeline_mode": "S_O_J", "conditioning": "unconditional",
                 "lineage": {k: model(k, p) for k in ("S","O","G","J")},
                 "scenarios": scenarios, "game_state_witness": g, "opportunity_witness": o})


def golden_cases():
    historical = pregame()
    hdist = distribution(historical, "points")
    prospective = pregame("original_prospective", with_offer=True)
    pdist = distribution(prospective, "points")
    offer = original_offer(prospective)
    from v2.nba_architecture.v2_contracts import offer_view
    view = offer_view(pdist, offer, prospective, "2026-11-16T23:03:00Z")
    joint = j_scenarios(prospective)
    m_pts = marginal_from_joint(joint, prospective, prospective["players"][0]["player_id"],
                                "points", "2026-11-16T23:03:00Z", 42)
    m_pra = marginal_from_joint(joint, prospective, prospective["players"][0]["player_id"],
                                "pra", "2026-11-16T23:03:00Z", 42)
    return {
        "historical_offer_free": {"pregame": historical, "distribution": hdist,
            "four_stats": {stat: distribution(historical, stat) for stat in
                           ("points","rebounds","assists","threes")},
            "fixture_provenance": "SYNTHETIC_RESEARCH_PROXY_NO_ORIGINAL_HISTORICAL_CAPTURE"},
        "prospective_original_offer": {"pregame": prospective, "distribution": pdist,
            "offer": offer, "offer_view": view,
            "fixture_provenance": "SYNTHETIC_ORIGINAL_RECEIPT_SHAPE_NOT_REAL_SOURCE"},
        "joint_same_draw": {"pregame": prospective, "scenarios": joint,
            "points": m_pts, "pra": m_pra,
            "fixture_provenance": "SYNTHETIC_PHYSICS_ONLY_NO_FIT"},
    }
