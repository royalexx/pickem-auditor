"""P3 G0-v2 opportunity conformance, synthetic fixtures only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from v2.nba_o_family import (build_opportunity, validate_sidecar,
                              freeze_outputs, validate_priors)
from v2.nba_architecture.v2_contracts import ContractError, seal
from v2.nba_architecture.families_v2 import validate_opportunity

FIXTURE = Path(__file__).parent/"golden_v2"/"joint_same_draw.json"


def inputs():
    base=json.loads(FIXTURE.read_text())
    p,g=base["pregame"],base["game_state"]
    receipt=p["sources"][0]["receipt_sha256"]
    law={"mean":24., "variance":25., "ot_probability":.12,
         "ot_continuation":.25, "family":"beta"}
    priors={}
    for i,r in enumerate(p["players"]):
        # First five on both teams are certain research-scenario participants;
        # the sixth is uncertain, using a hypothetical prior, never an actual.
        last = r["player_id"].split(":")[-1] in ("15","25")
        priors[r["player_id"]]={
            "source_snapshot_sha256":p["content_hash"],
            "source_receipt_sha256":receipt,
            "available_at":p["input_freeze_at"],
            "training_cutoff_at":p["training_cutoff_at"],
            "scenario_participation_prior":.7 if last else 1.,
            "participation_basis":"historical_prior",
            "minutes_distribution":law.copy(),
            "played_zero_probability":0.,
            "early_exit_probability":0.,
            "early_exit_fraction":.2,
            "role_states":[{"probability":1.,"minutes_multiplier":1.}],
            "possession_intensity":1.,
            "usage_concentration":30.,
            "uncertainty_flags":["SYNTHETIC_ONLY"],
        }
    return p,g,priors


def build(variant="O1",seed=17,change=None):
    p,g,priors=inputs()
    if change: change(priors)
    return p,g,*build_opportunity(p,g,priors,model=g["model"],seed=seed,
                                  variant=variant,home_team_id=p["team_ids"][0],
                                  home_team_source_receipt_sha256=
                                  p["sources"][0]["receipt_sha256"])


class OpportunityTests(unittest.TestCase):
    def test_g0_exact_conservation_and_sidecar(self):
        p,g,o,side=build()
        self.assertTrue(validate_opportunity(o,p,g))
        self.assertTrue(validate_sidecar(side,p,g,o))
        for s in o["scenarios"]:
            for team in p["team_ids"]:
                self.assertAlmostEqual(sum(x["minutes"] for x in s["players"]
                    if x["team_id"]==team),240+25*s["overtime_periods"],places=6)
                self.assertLessEqual(max(x["minutes"] for x in s["players"]
                    if x["team_id"]==team),48+5*s["overtime_periods"])

    def test_repeated_seed_exact_hash(self):
        a=build("O1",23)
        b=build("O1",23)
        self.assertEqual(a[2]["content_hash"],b[2]["content_hash"])
        self.assertEqual(a[3]["content_hash"],b[3]["content_hash"])

    def test_three_variants_generate_full_discrete_minute_laws(self):
        for variant in ("O0","O1","O2"):
            with self.subTest(variant=variant):
                p,g,o,side=build(variant)
                for player in o["players"]:
                    law=player["minutes_law"]
                    self.assertEqual(law["family"],"discrete_minutes")
                    self.assertAlmostEqual(sum(x["mass"] for x in
                        law["parameters"]["support"]),1.,places=11)
                self.assertEqual(side["variant"],variant)

    def test_unknown_probability_retained(self):
        p,g,o,side=build()
        self.assertTrue(all(x["participation_evidence"]=="unknown" and
                            x["participation_probability"] is None
                            for x in o["players"]))

    def test_played_zero_distinct_from_dnp(self):
        def update(p):
            p["espn:player:15"]["played_zero_probability"]=1.
            p["espn:player:15"]["scenario_participation_prior"]=1.
        p,g,o,side=build(change=update)
        states={x["participation"] for s in o["scenarios"] for x in s["players"]
                 if x["player_id"]=="espn:player:15"}
        self.assertEqual(states,{"PLAYED_ZERO_MINUTES"})
        self.assertEqual(next(x for x in o["players"] if x["player_id"]==
                              "espn:player:15")["minutes_law"]["parameters"]["support"],
                         [{"minutes":0.,"mass":1.}])

    def test_future_source_and_actual_input_key_fail_closed(self):
        p,g,priors=inputs()
        priors["espn:player:15"]["available_at"]=p["event_start_at"]
        with self.assertRaisesRegex(ContractError,"O_PRIOR_FUTURE_DATA"):
            validate_priors(p,priors,variant="O1")
        p,g,priors=inputs()
        priors["espn:player:15"]["actual_target_minutes"]=30
        with self.assertRaisesRegex(ContractError,"O_PRIOR_FIELDS_OR_POSTGAME_LEAK"):
            validate_priors(p,priors,variant="O1")

    def test_unknowable_roster_cannot_be_forced_active(self):
        def update(p):
            for pid,x in p.items():
                x["scenario_participation_prior"]=float(int(pid.split(":")[-1][-1])<4)
        with self.assertRaisesRegex(ContractError,
            "O_INFEASIBLE_PARTICIPATION_OR_ROTATION"):
            build(change=update)

    def test_verified_estimates_and_out_state_semantics(self):
        def update(p):
            for row in p.values():row["participation_basis"]="verified_pregame_fit"
            p["espn:player:15"]["scenario_participation_prior"]=0.
        p,g,o,side=build(change=update)
        by_id={r["player_id"]:r for r in o["players"]}
        self.assertEqual(by_id["espn:player:15"]["participation_probability"],0.)
        self.assertEqual(by_id["espn:player:15"]["participation_evidence"],
                         "independently_estimated")
        self.assertEqual({s["participation"] for sc in o["scenarios"]
                          for s in sc["players"] if s["player_id"]=="espn:player:15"},
                         {"DNP"})

    def test_early_exit_caps_without_realized_minutes(self):
        def update(p):
            p["espn:player:15"]["scenario_participation_prior"]=1.
            p["espn:player:10"]["early_exit_probability"]=1.
            p["espn:player:10"]["early_exit_fraction"]=.25
        p,g,o,side=build("O2",change=update)
        for sc in o["scenarios"]:
            person=next(x for x in sc["players"] if x["player_id"]=="espn:player:10")
            self.assertLessEqual(person["minutes"],
                                 .25*(48+5*sc["overtime_periods"])+1e-9)

    def test_lineup_and_opportunity_tamper_rejected(self):
        p,g,o,side=build("O2")
        broken=copy.deepcopy(side)
        broken["scenarios"][0]["players"][0]["possession_share"]=.99
        broken=seal({k:v for k,v in broken.items() if k!="content_hash"})
        with self.assertRaisesRegex(ContractError,"O_SHARE_CONSERVATION"):
            validate_sidecar(broken,p,g,o)
        broken=copy.deepcopy(side)
        broken["scenarios"][0]["teams"][p["team_ids"][0]]["lineup_segments"][0]["player_indices"]=[]
        broken=seal({k:v for k,v in broken.items() if k!="content_hash"})
        with self.assertRaisesRegex(ContractError,"O_FIVE_ON_COURT"):
            validate_sidecar(broken,p,g,o)

    def test_immutability_idempotence_and_conflict(self):
        p,g,o,side=build()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(freeze_outputs(d,p,g,o,side),
                             freeze_outputs(d,p,g,o,side))
            path=Path(d)/(o["content_hash"]+".json")
            path.write_text("corrupt")
            with self.assertRaisesRegex(ContractError,"IMMUTABLE_CONFLICT"):
                freeze_outputs(d,p,g,o,side)


if __name__=="__main__":
    unittest.main()
