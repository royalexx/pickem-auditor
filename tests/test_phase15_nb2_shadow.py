"""One fixed NB2 hypothesis: prospective pregame shadow, never retro-betting."""
from __future__ import annotations
import copy,math,tempfile,hashlib,json,unittest
from datetime import datetime,timezone
from pathlib import Path
from v2.phase15_nb2_shadow import (
    nb2_sog_probabilities,build_prospective_shadow,SCHEMA,FIXED_SHAPE,
)
from tests.test_phase15_nhl_roster import make_receipt


def fake_phase1(outcome="pending_official_settlement"):
    return {
       "schema":"v25-phase1-nhl-nba-certified-replay-v1",
       "input_immutable_bundle_sha256":"a"*64,
       "model_promotion_authorized":False,
       "tier1_tier2_publication_allowed":False,
       "prepared_attempt_count":2,"retained_paired_contracts":1,
       "by_sport":{"NHL":1},
       "contracts":[{
          "sport":"NHL","stat":"shots on goal","period":"full",
          "contract_id":"original-contract-fixed-hash",
          "event_id":"2026020356","player_id":"8480069",
          "team_id":"COL","opponent_id":"TOR","line":2.5,
          "event_start":"2026-11-11T23:00:00Z",
          "input_freeze_at":"2026-11-11T17:00:00Z",
          "outcome":{"status":outcome},
          "models":{
             "pooled_peer_shrunk_rate":{
                  "status":"counterfactual_shadow",
                  "distribution":{"kind":"poisson","rate":2.4},
                  "p_over_nonpush":.4303,
             },
             "real_no_vig_market":{"status":"available",
                                  "p_over_nonpush":.47},
          },
       }]
    }


def spec():
    return {"schema":"v25_locked_shadow_prospective_experiment_v1",
            "experiment_id":"EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE",
            "research_fixed_nb2_shape":4.0,
            "tier1_tier2_release_allowed":False,
            "model_promotion_allowed":False}


class ShadowMathTests(unittest.TestCase):
    def test_distribution_normalizes_for_fractional_and_integer_lines(self):
        for mean in (0,.001,.5,2.4,4.,12.):
            for line in (.5,1.5,2.,2.5,4.,5.5):
                p=nb2_sog_probabilities(mean,line)
                self.assertAlmostEqual(
                    p["q_over"]+p["q_under"]+p["q_push"],1,places=9)
                self.assertAlmostEqual(p["variance"],mean+mean**2/FIXED_SHAPE)
                if line!=int(line):self.assertEqual(p["q_push"],0)
                if p["p_over_nonpush"] is not None:
                    self.assertTrue(0<=p["p_over_nonpush"]<=1)

    def test_deterministic_zero_and_mean_tail(self):
        r=nb2_sog_probabilities(0,.5)
        self.assertEqual(r["q_over"],0)
        self.assertEqual(r["q_under"],1)
        self.assertEqual(r["variance"],0)
        p=nb2_sog_probabilities(2.5,2.5)
        self.assertTrue(.0<p["q_over"]<1)

    def test_reject_negative_rate_shape_and_bad_line(self):
        for mu,line,shape in ((-1,2.5,4),(1,-1,4),(1,2.5,0),
                              (float("nan"),2.5,4),(1,9999,4)):
            with self.assertRaises(ValueError):
                nb2_sog_probabilities(mu,line,shape=shape)

    def test_high_shape_approaches_poisson_control(self):
        mu=2.4
        p=nb2_sog_probabilities(mu,2.5,shape=1_000_000)
        expected=1-math.exp(-mu)*(1+mu+mu*mu/2)
        self.assertAlmostEqual(p["q_over"],expected,places=5)


class ProspectiveShadowTests(unittest.TestCase):
    def _inputs(self,root):
        return {
            "phase1":fake_phase1(),
            "phase1_bytes_sha256":"b"*64,
            "roster_manifest":{
               "schema":"phase15_nhl_pregame_roster_capture_v1",
               "source_phase1_sha256":"b"*64,
               "roster_receipts":{
                  "COL":make_receipt(root,"COL",pids=(8480069,)),
                  "TOR":make_receipt(root,"TOR",pids=(8470001,)),
               }},
            "roster_root":root,
            "model_revision":"c"*40,
            "now":datetime(2026,11,11,18,tzinfo=timezone.utc),
            "experiment_spec":spec(),
        }

    def test_precise_original_mean_and_source_bound_future_shadow_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            result=build_prospective_shadow(**inputs)
            self.assertEqual(result["NHL_shadow_accepted"],1)
            row=result["forecasts"][0]
            self.assertEqual(row["model"]["mean"],2.4)
            self.assertEqual(row["model"]["shape"],4)
            self.assertEqual(row["source_phase1_scored_sha256"],"b"*64)
            self.assertFalse(row["allowed_as_production_selection"])
            self.assertFalse(result["tier1_tier2_publication_allowed"])
            self.assertEqual(result["NHL_original_contracts"],1)
            self.assertEqual(len(result["complete_candidate_attempt_ledger"]),1)

    def test_late_starts_and_postgame_phase1_cannot_backdate_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            inputs["now"]=datetime(2026,11,12,2,tzinfo=timezone.utc)
            result=build_prospective_shadow(**inputs)
            self.assertEqual(result["NHL_shadow_accepted"],0)
            self.assertEqual(result["NHL_shadow_attempt_status"][
                "event_already_started_no_backdating"],1)
            inputs=self._inputs(Path(tmp))
            inputs["phase1"]["contracts"][0]["outcome"]={"status":"over","actual":3}
            result=build_prospective_shadow(**inputs)
            self.assertEqual(result["NHL_shadow_accepted"],0)
            self.assertEqual(result["NHL_shadow_attempt_status"][
                "already_settled_or_postgame_input_cannot_be_retroforecast"],1)

    def test_unverified_team_and_missing_roster_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            inputs["roster_manifest"]["roster_receipts"].pop("COL")
            report=build_prospective_shadow(**inputs)
            self.assertEqual(report["NHL_shadow_accepted"],0)
            self.assertTrue(any("roster_team_missing" in x
                       for x in report["NHL_shadow_attempt_status"]))

    def test_bad_future_or_tampered_original_digest_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            inputs["roster_manifest"]["source_phase1_sha256"]="9"*64
            with self.assertRaisesRegex(ValueError,"not_for_exact_phase1"):
                build_prospective_shadow(**inputs)

    def test_spec_does_not_authorize_promotion_or_postgame_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            inputs["experiment_spec"]["model_promotion_allowed"]=True
            with self.assertRaisesRegex(ValueError,"anti_promotion"):
                build_prospective_shadow(**inputs)

    def test_naive_fake_clock_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=self._inputs(Path(tmp))
            inputs["now"]=datetime(2026,11,11,18)
            with self.assertRaisesRegex(ValueError,"naive_generation_clock"):
                build_prospective_shadow(**inputs)


if __name__=="__main__":unittest.main()
