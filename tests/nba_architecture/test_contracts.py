"""P0 structural and adversarial checks only; no training or predictive scoring."""
import copy
import tempfile
import unittest
from pathlib import Path
from v2.nba_architecture.contracts import (
    VERSION, ContractError, seal, verify_seal, freeze_once, seed_for,
    validate_pregame, validate_statistical, validate_opportunity,
    validate_game_state, validate_joint, validate_forecast,
    validate_evaluation, validate_bundle, threshold_triplet,
)

HASH = "a" * 64
START = "2026-11-17T00:00:00Z"
FREEZE = "2026-11-16T23:00:00Z"
FORECAST = "2026-11-16T23:05:00Z"
TRAIN = "2026-11-16T22:00:00Z"


def fixture():
    players = [{"player_id": f"espn:player:{t}{i}", "team_id": t,
                "availability": "reported_active", "legal_eligibility": True}
               for t in ("espn:team:1", "espn:team:2") for i in range(5)]
    pre = seal({"schema": VERSION, "record_type": "pregame",
                "event_id": "espn:game:fixture", "home_team_id": "espn:team:1",
                "away_team_id": "espn:team:2", "event_start_at": START,
                "forecast_at": FORECAST, "input_freeze_at": FREEZE,
                "model_training_cutoff_at": TRAIN,
                "sources": [{"source_id": "fixture-original", "raw_sha256": HASH,
                             "source_available_at": FREEZE, "observed_at": FREEZE,
                             "origin": "original_capture"}],
                "players": players, "features": []})
    base = {"schema": VERSION, "source_snapshot_sha256": pre["content_hash"],
            "event_id": pre["event_id"], "model_version": "fixture-v1",
            "code_sha256": HASH, "artifact_sha256": HASH,
            "model_training_cutoff_at": TRAIN}
    s = dict(base, family="S", model_id="S-fixture", stat="points",
             support="nonnegative_integer", conditioning="unconditional",
             pmf=[{"value": 0, "mass": 0.25}, {"value": 2, "mass": 0.75}])
    o = dict(base, family="O", model_id="O-fixture", roster_certified=True,
             players=[{"player_id": p["player_id"],
                       "participation_probability": 1.0,
                       "participation_status": "reported_active",
                       "mean_minutes_given_played": 48.0,
                       "conditioning": "given_played"} for p in players])
    g = dict(base, family="G", model_id="G-fixture",
             scenarios=[{"scenario_id": "draw-1", "overtime_periods": 0,
                         "pace_regulation": 100.0, "score_state": 0.0,
                         "possessions_home": 100, "possessions_away": 100,
                         "weight": 1.0}])
    stats = {key: 0 for key in ("points", "rebounds", "assists", "threes",
                               "fgm", "fga", "ftm", "fta", "oreb", "dreb",
                               "steals", "blocks", "turnovers", "pr", "pa", "ra", "pra")}
    j = dict(base, family="J", model_id="J-fixture", game_state_id="G-fixture",
             opportunity_id="O-fixture",
             scenarios=[{"scenario_id": "draw-1", "overtime_periods": 0,
                         "team_points": {"espn:team:1": 0, "espn:team:2": 0},
                         "players": [{"player_id": p["player_id"],
                                      "team_id": p["team_id"],
                                      "minutes": 48.0, "participated": True,
                                      "stats": dict(stats)} for p in players]}])
    contract = {"contract_id": "original:fixture", "event_id": pre["event_id"],
                "player_id": players[0]["player_id"], "stat": "points",
                "period": "full_game_including_ot", "line": 1.0,
                "quote_at": FREEZE, "quote_sha256": HASH}
    f = seal({"schema": VERSION, "record_type": "forecast",
              "source_snapshot_sha256": pre["content_hash"],
              "event_id": pre["event_id"], "forecast_at": FORECAST,
              "model_training_cutoff_at": TRAIN, "distribution_id": "S-fixture",
              "contract": contract, "probabilities":
                  {"over": .75, "under": .25, "push": 0.0},
              "status": "UNCERTIFIED_SHADOW", "p_market": None})
    e = seal({"schema": VERSION, "record_type": "evaluation",
              "forecast_hash": f["content_hash"], "contract_id": contract["contract_id"],
              "status": "settled", "actual": 2,
              "evaluated_at": "2026-11-17T03:00:00Z",
              "source_receipt_sha256": HASH, "cohort_status": "matched",
              "settlement_version": 1, "distribution": s})
    return pre, s, o, g, j, f, e


class ContractTests(unittest.TestCase):
    def test_valid_bundle(self):
        p, s, o, g, j, f, e = fixture()
        self.assertTrue(validate_bundle(dict(pregame=p, statistical=[s],
            opportunities=[o], game_states=[g], joint=[j], forecasts=[f])))
        self.assertTrue(validate_evaluation(e, f, p))

    def assert_code(self, code, fn, *args):
        with self.assertRaises(ContractError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)

    def test_frozen_hash_tamper(self):
        p, *_ = fixture()
        p["players"][0]["team_id"] = "espn:team:3"
        self.assert_code("CONTENT_HASH_MISMATCH", validate_pregame, p)

    def test_feature_future_leak(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["features"] = [{"source_id": "fixture-original",
                          "available_at": START, "is_target_game_outcome": True}]
        self.assert_code("FUTURE_FEATURE", validate_pregame, seal(p))

    def test_future_source(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["sources"][0]["observed_at"] = START
        p["sources"][0]["source_available_at"] = START
        self.assert_code("POSTFREEZE_SOURCE", validate_pregame, seal(p))

    def test_retrospective_source_rejected(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["sources"][0]["origin"] = "retrospective_retrieval"
        self.assert_code("NONORIGINAL_SOURCE", validate_pregame, seal(p))

    def test_training_future(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["model_training_cutoff_at"] = START
        self.assert_code("PREGAME_TIME_ORDER", validate_pregame, seal(p))

    def test_nonutc(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["forecast_at"] = "2026-11-16T18:05:00-05:00"
        self.assert_code("UTC_REQUIRED", validate_pregame, seal(p))

    def test_duplicate_players(self):
        p, *_ = fixture()
        p.pop("content_hash")
        p["players"].append(dict(p["players"][0]))
        self.assert_code("DUPLICATE_PLAYER", validate_pregame, seal(p))

    def test_masses_not_normalized(self):
        p, s, *_ = fixture()
        s["pmf"][0]["mass"] = .3
        self.assert_code("MASS_NOT_NORMALIZED", validate_statistical, s, p)

    def test_threshold_push(self):
        pmf = [{"value": 1, "mass": .1}, {"value": 2, "mass": .6},
               {"value": 3, "mass": .3}]
        self.assertEqual(threshold_triplet(pmf, 2),
                         dict(over=.3, under=.1, push=.6))

    def test_unknown_participation_cannot_impute(self):
        p, s, o, *_ = fixture()
        o["players"][0]["participation_status"] = "unknown"
        o["players"][0]["participation_probability"] = 1
        self.assert_code("UNKNOWN_AS_CERTAIN", validate_opportunity, o, p)

    def test_fake_roster_cert(self):
        p, s, o, *_ = fixture()
        p.pop("content_hash")
        p["players"][0]["legal_eligibility"] = None
        p = seal(p)
        o["source_snapshot_sha256"] = p["content_hash"]
        self.assert_code("UNSUPPORTED_ROSTER_CERTIFICATION", validate_opportunity, o, p)

    def test_wrong_team_minutes(self):
        p, s, o, g, j, *_ = fixture()
        j["scenarios"][0]["players"][0]["minutes"] -= 1
        self.assert_code("TEAM_MINUTE_CONSERVATION", validate_joint, j, p, o, g)

    def test_inactive_player_scored(self):
        p, s, o, g, j, *_ = fixture()
        row = j["scenarios"][0]["players"][0]
        row["participated"] = False
        row["stats"]["fga"] = 1
        self.assert_code("INACTIVE_OUTCOME", validate_joint, j, p, o, g)

    def test_joint_wrong_scenario(self):
        p, s, o, g, j, *_ = fixture()
        j["scenarios"][0]["scenario_id"] = "different"
        self.assert_code("SCENARIO_JOIN", validate_joint, j, p, o, g)

    def test_forecast_inconsistent_side(self):
        p, s, o, g, j, f, e = fixture()
        f.pop("content_hash")
        f["probabilities"] = {"over": .25, "under": .75, "push": 0}
        self.assert_code("PROBABILITY_LAW_MISMATCH",
                         validate_forecast, seal(f), p, s)

    def test_future_quote(self):
        p, s, o, g, j, f, e = fixture()
        f.pop("content_hash")
        f["contract"]["quote_at"] = START
        self.assert_code("FUTURE_QUOTE", validate_forecast, seal(f), p, s)

    def test_market_inference_blocked(self):
        p, s, o, g, j, f, e = fixture()
        f.pop("content_hash")
        f["p_market"] = .5
        self.assert_code("P0_NO_MARKET_INFERENCE", validate_forecast, seal(f), p, s)

    def test_void_cannot_be_push(self):
        p, s, o, g, j, f, e = fixture()
        e.pop("content_hash")
        e["status"] = "push"
        self.assert_code("FALSE_PUSH", validate_evaluation, seal(e), f, p)

    def test_duplicate_freeze_no_overwrite(self):
        p, *_ = fixture()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "immutable.json"
            freeze_once(path, p)
            freeze_once(path, p)
            self.assertEqual(p["content_hash"], verify_seal(p))
            self.assert_code("IMMUTABLE_CONFLICT", freeze_once, path,
                             seal({**{k: v for k, v in p.items() if k != "content_hash"},
                                   "new": "mutation"}))

    def test_seed_is_stable_and_unambiguous(self):
        a = seed_for(42, "event", "draw-1", "S1")
        self.assertEqual(a, seed_for(42, "event", "draw-1", "S1"))
        self.assertNotEqual(a, seed_for(42, "event", "draw-2", "S1"))
        self.assert_code("AMBIGUOUS_SEED_ID", seed_for, 42, "e|v", "d", "S1")


if __name__ == "__main__":
    unittest.main()
