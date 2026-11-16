"""Adversarial synthetic P4 family tests against independently frozen G0 v2 shapes."""
from copy import deepcopy
import json
import math
import time
import unittest

from golden_v2 import pregame, j_scenarios, game_state, opportunity, model
from v2.nba_architecture.v2_contracts import (
    seal, VERSION, ContractError, marginal_from_joint, validate_scenarios,
)
from v2.nba_architecture.families_v2 import validate_integration, validate_forecast
from v2.nba_joint.p4 import (
    S_ADAPTER, simulate_p4, scenario_pmfs, dependence_diagnostics,
)


PARAMETERS = {
    "p2": .54, "p3": .36, "pft": .78, "ft_share": .25,
    "rebound_credit": .9, "offensive_rebound_share": .24,
    "terminal_ft_fraction": .44, "assist_fraction": .6,
}


def fixture():
    p = pregame("original_prospective")
    source = j_scenarios(p)
    g = game_state(p, source)
    o = opportunity(p, g, source)
    # Unlike the intentionally diagnostic old golden's synthetic_point_mass
    # descriptor, this family test provides a legitimate finite discrete law.
    editable = {k: deepcopy(v) for k, v in o.items() if k != "content_hash"}
    for player in editable["players"]:
        index = int(player["player_id"].rsplit(":", 1)[1][1:])
        values = [0.0] if index == 5 else [48.0]
        player["minutes_law"] = {
            "family": "discrete_minutes", "parameters": {
                "support": [{"minutes": x, "mass": 1.0} for x in values]},
            "conditioning": "given_played", "units": "minutes",
        }
    o = seal(editable)
    rows = []
    for player in p["players"]:
        idx = int(player["player_id"][-1])
        rows.append({
            "player_id": player["player_id"], "team_id": player["team_id"],
            "rates": {"points": .55 + idx * .018,
                      "rebounds": .18 + idx * .006,
                      "assists": .10 + idx * .004,
                      "threes": .07 + idx * .002}
        })
    s = seal({
        "schema": S_ADAPTER, "kind": "conditional_rates",
        "source_snapshot_sha256": p["content_hash"], "game_id": p["game_id"],
        "adapter_basis": "synthetic_fixture", "model": model("S", p),
        "players": rows,
    })
    return p, g, o, s


def run(variant="J1", **kwargs):
    p, g, o, s = fixture()
    z = simulate_p4(p, g, o, s, variant=variant, seed=42,
                    base_pace=100., event_parameters=PARAMETERS, **kwargs)
    return p, g, o, s, z


def reseal(x, f):
    clone = deepcopy(x)
    clone.pop("content_hash")
    f(clone)
    return seal(clone)


class P4JointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p, cls.g, cls.o, cls.s, cls.j = run()

    def error(self, code, f, *args, **kwargs):
        with self.assertRaises(ContractError) as e:
            f(*args, **kwargs)
        self.assertEqual(e.exception.code, code)

    def test_p4_reuses_native_v01_events_and_ws2_witness(self):
        from v2.nba_joint.events import sample_events
        from v2.nba_opportunity import lineup_segments
        self.assertTrue(callable(sample_events))
        self.assertTrue(callable(lineup_segments))
        self.assertTrue(self.j["audit_rows"][0]["lineup_sha256"])
        self.assertEqual(self.j["status"], "SYNTHETIC_SHADOW_ONLY")

    def test_canonical_g0_integration_and_sha(self):
        self.assertTrue(validate_integration(self.j["bundle"], self.p, self.g, self.o))
        self.assertEqual(self.j["bundle"]["game_state_sha256"], self.g["content_hash"])
        self.assertEqual(self.j["bundle"]["opportunity_sha256"], self.o["content_hash"])
        self.assertEqual(len(self.j["scenario_hashes"]), 2)

    def test_reproducible_scenario_hashes(self):
        z = simulate_p4(self.p, self.g, self.o, self.s, variant="J1",
                        seed=42, event_parameters=PARAMETERS)
        self.assertEqual(z["bundle"]["content_hash"], self.j["bundle"]["content_hash"])
        self.assertEqual(z["scenario_hashes"], self.j["scenario_hashes"])
        other = simulate_p4(self.p, self.g, self.o, self.s, variant="J1",
                            seed=43, event_parameters=PARAMETERS)
        self.assertNotEqual(z["bundle"]["content_hash"], other["bundle"]["content_hash"])

    def test_two_team_shots_assists_rebounds_and_five_on_court(self):
        self.assertEqual(self.j["performance"]["n_player_draws"], 24)
        for sc in self.j["bundle"]["scenarios"]:
            self.assertEqual(set(sc["team_points"]), set(self.p["team_ids"]))
            self.assertNotEqual(*sc["team_points"].values())
            self.assertEqual(len(sc["players"]), 12)
            for team in self.p["team_ids"]:
                people = [x for x in sc["players"] if x["team_id"] == team]
                self.assertAlmostEqual(sum(x["minutes"] for x in people),
                                       5 * (48 + 5 * sc["overtime_periods"]), places=8)
                self.assertEqual(sum(x["stats"]["points"] for x in people),
                                 sc["team_points"][team])
            for x in sc["players"]:
                v = x["stats"]
                self.assertLessEqual(v["two_pm"], v["two_pa"])
                self.assertLessEqual(v["threes"], v["three_pa"])
                self.assertLessEqual(v["ftm"], v["fta"])
                self.assertEqual(v["points"], 2*v["two_pm"]+3*v["threes"]+v["ftm"])
                self.assertEqual(v["pra"], v["points"]+v["rebounds"]+v["assists"])
                self.assertEqual(v["pr"], v["points"]+v["rebounds"])
                self.assertEqual(v["pa"], v["points"]+v["assists"])
                self.assertEqual(v["ra"], v["rebounds"]+v["assists"])
                if x["participation"] != "PLAYED":
                    self.assertTrue(all(val == 0 for val in v.values()))

    def test_pmfs_exactly_from_same_draw(self):
        pms = scenario_pmfs(self.j, self.p, frozen_at="2026-11-16T23:03:00Z",
                            seed=42)
        for pid, table in pms.items():
            for stat, d in table.items():
                self.assertAlmostEqual(sum(row["mass"] for row in d["pmf"]), 1.)
                self.assertEqual(d["scenario_bundle_sha256"], self.j["bundle"]["content_hash"])
                self.assertTrue(validate_forecast(
                    d, self.p, g=self.g, o=self.o, scenarios=self.j["bundle"]))
        sc = self.j["bundle"]["scenarios"]
        pid = self.p["players"][0]["player_id"]
        val = [(next(x for x in row["players"] if x["player_id"] == pid)["stats"])
               for row in sc]
        exact = {}
        for a, b in zip(val, sc):
            exact[a["pra"]] = exact.get(a["pra"], 0) + b["weight"]
        self.assertEqual({r["value"]: r["mass"] for r in pms[pid]["pra"]["pmf"]},
                         exact)

    def test_j0_j1_j2_distinct_and_valid(self):
        a = run("J0")[4]
        b = self.j
        c = run("J2", role_sigma=.12, efficiency_sigma=.09)[4]
        for z in (a, b, c):
            self.assertTrue(validate_scenarios(z["bundle"], self.p))
        self.assertNotEqual(a["bundle"]["content_hash"], b["bundle"]["content_hash"])
        self.assertNotEqual(c["bundle"]["content_hash"], b["bundle"]["content_hash"])

    def test_j3_fails_closed_unless_regimes_precommitted(self):
        self.error("P4_J3_PRECOMMITMENT_REQUIRED", simulate_p4,
                   self.p, self.g, self.o, self.s,
                   variant="J3", event_parameters=PARAMETERS)
        labels = {x["scenario_id"]: "high" if i == 0 else "low"
                  for i, x in enumerate(self.g["scenarios"])}
        z = run("J3", enable_j3=True, scenario_regimes=labels,
                regime_multipliers={"high":1.2,"low":.85})[4]
        self.assertTrue(validate_integration(z["bundle"], self.p, self.g, self.o))
        self.assertEqual([x["weight"] for x in z["bundle"]["scenarios"]],
                         [x["weight"] for x in self.g["scenarios"]])
        self.error("P4_J3_UNGATED", simulate_p4,
                   self.p, self.g, self.o, self.s,
                   event_parameters=PARAMETERS, scenario_regimes=labels)

    def test_j4_does_not_count_scenario_draws_as_games(self):
        pid = self.p["players"][0]["player_id"]
        second = self.p["players"][1]["player_id"]
        z = dependence_diagnostics(self.j, self.p, [(pid,"points",pid,"pra"),
                                                   (pid,"assists",second,"points")])
        self.assertIsNone(z["independent_observed_games"])
        self.assertEqual(len(z["pairs"]),2)
        self.assertEqual(z["n_scenarios"], 2)
        self.assertAlmostEqual(z["effective_scenario_count_heuristic"], 1/.52)
        for pair in z["pairs"]:
            self.assertGreaterEqual(pair["positive_cooccurrence"], 0.)
            self.assertLessEqual(pair["positive_cooccurrence"], 1.)

    def test_adversarial_s_wrong_team(self):
        bad = reseal(self.s, lambda x: x["players"][0].update(
            team_id=self.p["team_ids"][1]))
        self.error("P4_S_PLAYER_IDENTITY", simulate_p4,
                   self.p, self.g, self.o, bad, event_parameters=PARAMETERS)

    def test_adversarial_s_future_training_cutoff(self):
        bad = reseal(self.s, lambda x: x["model"].update(
            training_cutoff_at=self.p["event_start_at"]))
        self.error("P4_S_FUTURE_MODEL", simulate_p4,
                   self.p, self.g, self.o, bad, event_parameters=PARAMETERS)

    def test_adversarial_actual_minutes_embedded_in_s(self):
        bad = reseal(self.s, lambda x: x["players"][0].update(actual_minutes=48))
        self.error("P4_S_PLAYER_SCHEMA", simulate_p4,
                   self.p, self.g, self.o, bad, event_parameters=PARAMETERS)

    def test_adversarial_nonphysical_three_rate(self):
        bad = reseal(self.s, lambda x: x["players"][0]["rates"].update(threes=50))
        self.error("P4_S_INCOMPATIBLE_THREE_POINT_RATE", simulate_p4,
                   self.p, self.g, self.o, bad, event_parameters=PARAMETERS)

    def test_adversarial_fake_real_s_adapter(self):
        bad = reseal(self.s, lambda x: x.update(adapter_basis="validated_S2"))
        self.error("P4_S_REAL_LIKELIHOOD_ADAPTER_NOT_ACCEPTED", simulate_p4,
                   self.p, self.g, self.o, bad, event_parameters=PARAMETERS)

    def test_adversarial_mutated_g_and_o(self):
        bad_g = reseal(self.g, lambda x: x["scenarios"][0].update(weight=.9))
        with self.assertRaises(ContractError):
            simulate_p4(self.p, bad_g, self.o, self.s,
                        event_parameters=PARAMETERS)
        bad_o = reseal(self.o, lambda x: x["scenarios"][0]["players"][0].update(minutes=0))
        with self.assertRaises(ContractError):
            simulate_p4(self.p, self.g, bad_o, self.s,
                        event_parameters=PARAMETERS)

    def test_adversarial_corrupt_j_count_and_hash(self):
        bad = reseal(self.j["bundle"], lambda x:
            x["scenarios"][0]["players"][0]["stats"].update(points=999))
        with self.assertRaises(ContractError):
            validate_integration(bad, self.p, self.g, self.o)
        bad_hash = deepcopy(self.j["bundle"])
        bad_hash["content_hash"] = "0"*64
        with self.assertRaises(ContractError):
            validate_scenarios(bad_hash, self.p)

    def test_adversarial_nan_probability_and_negative_minutes(self):
        bad = deepcopy(PARAMETERS); bad["p2"] = float("nan")
        self.error("P4_EVENT_PROBABILITY", simulate_p4,
                   self.p, self.g, self.o, self.s, event_parameters=bad)
        bad_o = reseal(self.o, lambda x:
                       x["scenarios"][0]["players"][0].update(minutes=-1.))
        with self.assertRaises(ContractError):
            simulate_p4(self.p, self.g, bad_o, self.s,
                        event_parameters=PARAMETERS)

    def test_simple_benchmark_receipt(self):
        self.assertEqual(self.j["performance"]["n_scenarios"], 2)
        self.assertTrue(math.isfinite(self.j["performance"]["elapsed_seconds"]))
        self.assertGreater(self.j["performance"]["elapsed_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
