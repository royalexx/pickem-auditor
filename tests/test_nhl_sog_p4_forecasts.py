"""P4 research-only math, provenance, immutability and update unit tests."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
import unittest

from v2.nhl_sog_p4_forecasts import (
    SCHEMA, BUNDLE_SCHEMA, ADAPTIVE_SCHEMA, P4Blocked,
    fit_source_bundle, full_law, three_way, _mass_for, 
    freeze_forecast, append_immutable, read_immutable,
    propose_adaptive_update, freeze_adaptive_update, coverage_attempt,
    verify_manifest, canonical, sha256,
)
from v2.nhl_sog_exposure_shadow import (
    SCHEMA as GAMMA_SCHEMA, _pmf_poisson, _pmf_gamma_poisson,
    _mass as registered_mass, stable_hash,
)


class P4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.freeze="2026-11-21T12:00:00Z"
        cls.start="2026-11-23T00:00:00Z"
        cls.cutoff="2026-11-16T00:00:00Z"
        cls.recv="2026-11-15T12:00:00Z"
        cls.now=datetime(2026,11,21,21,tzinfo=timezone.utc)
        cls.own=[]
        cls.peers=[]
        def create(pid,index,position,y,w):
            row={"schema":"v25_nhl_sog_observation_v1",
                 "player_id":pid,"event_id":f"historical_{pid}_{index}",
                 "position_group":position, "played":True,
                 "event_ended_at":"2026-11-14T04:00:00Z",
                 "shots_on_goal":y,"toi_minutes":w}
            raw=canonical(row)
            rel=f"obs/{pid}_{index}.json"
            p=cls.root/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(raw)
            return {"source_kind":"collector_observed_bytes",
                    "archive_path":rel,
                    "content_sha256":sha256(raw),
                    "source_url":"https://api-web.nhle.com/v1/gamecenter/final",
                    "received_at":cls.recv}
        for j in range(8):
            cls.own.append(create("101",j,"F",j%5,15.0+(j%3)))
        for ip in range(20):
            for j in range(10):
                cls.peers.append(create(str(200+ip),j,"F",(ip+j)%6,11.5+(j%5)))
        cls.bundle={
            "schema":BUNDLE_SCHEMA,"source_classification":"synthetic",
            "synthetic_fixture":True,"event_id":"synthetic_target",
            "player_id":"101","team_id":"AAA","opponent_id":"BBB",
            "position_group":"F","input_freeze_at":cls.freeze,
            "event_start_at":cls.start,
            "historical_availability_cutoff_at":cls.cutoff,
            "flags":{},"own_official_history":cls.own,
            "peer_official_history":cls.peers,
        }
        cls.model=fit_source_bundle(cls.bundle,source_root=cls.root,now=cls.now)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_registered_gamma_policy_not_rewritten(self):
        m=self.model
        self.assertEqual(m["schema"],GAMMA_SCHEMA)
        self.assertEqual(m["tau_minutes"],60)
        self.assertEqual(m["eta_games"],3)
        self.assertEqual(m["own_played_games"],8)
        self.assertEqual(m["peer_players"],20)
        self.assertEqual(m["peer_games"],200)
        self.assertEqual(m["p4_source_classification"],"synthetic")
        self.assertFalse(m["p4_prospective_certification_candidate"])

    def test_02_poisson_reference(self):
        self.assertAlmostEqual(_pmf_poisson(0,2),math.exp(-2),places=14)
        self.assertAlmostEqual(_pmf_poisson(3,2),4*math.exp(-2)/3,places=14)
        self.assertEqual(_pmf_poisson(1,0),0)

    def test_03_gamma_reference(self):
        self.assertAlmostEqual(_pmf_gamma_poisson(0,3,2,1),(2/3)**3,places=14)
        self.assertAlmostEqual(_pmf_gamma_poisson(1,3,2,1),
                               3*(2/3)**3/3,places=14)

    def test_04_nb2_fixedshape_independent(self):
        m=copy.deepcopy(self.model)
        m["plugin_rate"]=2.0
        m["plugin_exposure"]=1.0
        self.assertAlmostEqual(_mass_for(m,0,"nb2_fixed_shape4"),(4/6)**4,places=13)
        self.assertAlmostEqual(_mass_for(m,1,"nb2_fixed_shape4"),
                               4*(4/6)**4*(2/6),places=13)
        L=full_law(m,"nb2_fixed_shape4")
        self.assertAlmostEqual(L["mean"],2,places=12)
        self.assertAlmostEqual(L["variance"],3,places=12)
        self.assertEqual(L["parameters"]["native_shape"],4.0)

    def test_05_all_registered_laws_match(self):
        for kind in ("plugin_poisson","fixed_exposure_gamma_poisson",
                     "mixture_exposure_plugin_poisson","full_gamma_poisson_exposure"):
            law=full_law(self.model,kind)
            self.assertLessEqual(law["unallocated_upper_tail_mass"],1e-12)
            self.assertAlmostEqual(sum(law["pmf_from_zero"])+
                 law["unallocated_upper_tail_mass"],1,places=10)
            self.assertTrue(law["no_truncation_renormalization"])
            for k in (0,1,3,8):
                self.assertAlmostEqual(law["pmf_from_zero"][k],
                                       registered_mass(self.model,k,kind),places=13)

    def test_06_lines_half_integer_and_push(self):
        law=full_law(self.model,"plugin_poisson")
        half=three_way(law,2.5)
        integer=three_way(law,2)
        self.assertEqual(half["push"],0.0)
        self.assertAlmostEqual(integer["push"],law["pmf_from_zero"][2])
        self.assertAlmostEqual(integer["under"],sum(law["pmf_from_zero"][:2]))
        self.assertAlmostEqual(sum(integer.values()),1.0,places=13)
        self.assertAlmostEqual(sum(half.values()),1.0,places=13)

    def test_07_invalid_lines_and_nonfinite(self):
        law=full_law(self.model,"plugin_poisson")
        for x in (float("nan"),float("inf"),-1,81,True):
            with self.subTest(x=x),self.assertRaises(P4Blocked):
                three_way(law,x)

    def test_08_role_changes_and_outside_cutoff_block(self):
        for flag in ("role_change","role_uncertain","subject_out",
                     "participation_unverified","context_affected"):
            b=copy.deepcopy(self.bundle);b["flags"][flag]=True
            with self.subTest(flag=flag),self.assertRaises(P4Blocked):
                fit_source_bundle(b,source_root=self.root,now=self.now)
        b=copy.deepcopy(self.bundle)
        b["historical_availability_cutoff_at"]="2026-11-14T00:00:00Z"
        with self.assertRaises(P4Blocked):
            fit_source_bundle(b,source_root=self.root,now=self.now)

    def test_09_dnp_zero_not_confounded(self):
        b=copy.deepcopy(self.bundle)
        r=copy.deepcopy(b["own_official_history"][0])
        raw=canonical({"schema":"v25_nhl_sog_observation_v1",
            "player_id":"101","event_id":"DNP_GAME","position_group":"F",
            "played":False,"event_ended_at":"2026-11-14T04:00:00Z",
            "shots_on_goal":0,"toi_minutes":0.0})
        name="obs/DNP_GAME.json"
        (self.root/name).write_bytes(raw)
        r.update(archive_path=name,content_sha256=sha256(raw))
        b["own_official_history"][0]=r
        with self.assertRaisesRegex(Exception,"DNP_NOT_A_PLAYED_GAME"):
            fit_source_bundle(b,source_root=self.root,now=self.now)

    def test_10_tampered_observation_and_duplicate(self):
        b=copy.deepcopy(self.bundle)
        b["own_official_history"][0]["content_sha256"]="f"*64
        with self.assertRaisesRegex(Exception,"SOURCE_DIGEST_MISMATCH"):
            fit_source_bundle(b,source_root=self.root,now=self.now)
        b=copy.deepcopy(self.bundle)
        b["own_official_history"].append(b["own_official_history"][-1])
        with self.assertRaisesRegex(Exception,"DUPLICATE_PLAYER_GAME"):
            fit_source_bundle(b,source_root=self.root,now=self.now)

    def test_11_manifest_integrity(self):
        rel="signed_manifest.json";raw=canonical({"some":"source"})
        (self.root/rel).write_bytes(raw)
        self.assertEqual(verify_manifest(self.root,rel,sha256(raw)),{"some":"source"})
        with self.assertRaises(P4Blocked):
            verify_manifest(self.root,rel,"a"*64)
        with self.assertRaises(P4Blocked):
            verify_manifest(self.root,"../outside","a"*64)

    def test_12_original_must_not_inject_time(self):
        b=copy.deepcopy(self.bundle)
        b.update(source_classification="original_signed",synthetic_fixture=False)
        with self.assertRaisesRegex(P4Blocked,"ORIGINAL_NOW_INJECTION_PROHIBITED"):
            fit_source_bundle(b,source_root=self.root,now=self.now)

    def test_13_full_forecast_freeze_and_restore(self):
        out=freeze_forecast(self.model,kind="full_gamma_poisson_exposure",
            event_id="synthetic_target",player_id="101",team_id="AAA",
            opponent_id="BBB",event_start_at=self.start,
            forecast_at="2026-11-21T21:00:00Z",training_cutoff_at=self.cutoff,
            code_commit="a"*40,source_manifest_sha256=None,
            artifact_root=self.root,forecast_id="fixture_forecast_01",cohort="synthetic")
        row=read_immutable(self.root,out)
        self.assertEqual(row["distribution"]["support"],"nonnegative_integer")
        self.assertTrue(row["research_only"])
        self.assertEqual(row["participation_condition"],"conditional_on_played")
        self.assertIsNone(row["dnp_probability"])
        self.assertEqual(row["cohort"],"synthetic")
        same=freeze_forecast(self.model,kind="full_gamma_poisson_exposure",
            event_id="synthetic_target",player_id="101",team_id="AAA",
            opponent_id="BBB",event_start_at=self.start,
            forecast_at="2026-11-21T21:00:00Z",training_cutoff_at=self.cutoff,
            code_commit="a"*40,source_manifest_sha256=None,
            artifact_root=self.root,forecast_id="fixture_forecast_01",cohort="synthetic")
        self.assertTrue(same["already_frozen"])
        with self.assertRaisesRegex(P4Blocked,"DUPLICATE_FORECAST_ID_OR_MUTATION"):
            append_immutable(self.root,"p4_nhl_sog/forecasts",
                             "fixture_forecast_01",{"modified":True})
        with self.assertRaisesRegex(P4Blocked,"NATIVE_NB2_REQUIRES_REGISTERED_FROZEN_SOURCE"):
            freeze_forecast(self.model,kind="nb2_fixed_shape4",
                event_id="synthetic_target",player_id="101",team_id="AAA",
                opponent_id="BBB",event_start_at=self.start,
                forecast_at="2026-11-21T21:00:00Z",training_cutoff_at=self.cutoff,
                code_commit="a"*40,source_manifest_sha256=None,
                artifact_root=self.root,forecast_id="illegal_native",cohort="distribution_only")

    def test_14_digest_mutation(self):
        rc=append_immutable(self.root,"tamper","damaged",{"value":5})
        (self.root/rc["path"]).write_bytes(b'{"value":6}')
        with self.assertRaisesRegex(P4Blocked,"IMMUTABLE_ARTIFACT_MUTATED"):
            read_immutable(self.root,rc)

    def test_15_adaptive_update_is_separate_and_rollback(self):
        old={"schema":ADAPTIVE_SCHEMA,"research_track":"ADAPTIVE_CHALLENGER",
             "experiment_id":"P4-ADAPTIVE-NHL-001","alpha":3.0,
             "beta":5.0,"version":1,
             "model_training_cutoff_at":"2026-11-14T00:00:00Z",
             "seen_player_game_ids":[]}
        ob={"player_id":"101","event_id":"G3","played":True,"finalized":True,
            "first_available_at":"2026-11-15T11:00:00Z",
            "source_sha256":"a"*64,"shots_on_goal":0,"toi_minutes":18.0}
        r=propose_adaptive_update(old,[ob],cutoff_at="2026-11-16T00:00:00Z")
        self.assertEqual(r["alpha"],3.0)
        self.assertEqual(r["beta"],23.0)
        self.assertEqual(r["version"],2)
        self.assertEqual(old["beta"],5.0)
        rc=freeze_adaptive_update(self.root,"synthetic_model",old,[ob],
                                  cutoff_at="2026-11-16T00:00:00Z")
        self.assertEqual(read_immutable(self.root,rc)["beta"],23.0)
        for invalid in ({**ob,"played":False},
                        {**ob,"first_available_at":"2026-11-17T00:00:00Z"},
                        {**ob,"finalized":False}):
            with self.assertRaises(P4Blocked):
                freeze_adaptive_update(self.root,"synthetic_model",old,
                    [invalid],cutoff_at="2026-11-16T00:00:00Z")
        self.assertEqual(read_immutable(self.root,rc)["beta"],23.0)
        old["experiment_id"]="EXP-V25-NHL-SOG-EXPOSURE-EB-001"
        with self.assertRaisesRegex(P4Blocked,"LOCKED_EXPERIMENT_CANNOT_BE_UPDATED"):
            propose_adaptive_update(old,[ob],cutoff_at="2026-11-16T00:00:00Z")

    def test_16_abstention_and_resource_budget(self):
        start=time.perf_counter()
        for k in ("plugin_poisson","fixed_exposure_gamma_poisson",
                  "mixture_exposure_plugin_poisson","full_gamma_poisson_exposure",
                  "nb2_fixed_shape4"):
            full_law(self.model,k)
        elapsed=time.perf_counter()-start
        self.assertLess(elapsed,5.0)
        rc=coverage_attempt(self.root,attempt_id="synthetic_attempt_1",
           event_id="synthetic_target",player_id="101",reason="NO_AUTHENTIC_QUOTE",
           source_classification="synthetic",
           forecast_at="2026-11-21T21:00:00Z")
        self.assertEqual(read_immutable(self.root,rc)["status"],"ABSTAIN")

if __name__ == "__main__":
    unittest.main()
