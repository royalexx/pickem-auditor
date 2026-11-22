"""Independent mathematical reference and adversarial P5 research tests (synthetic)."""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from v2.p0_integrity.contracts import record, sha256, AdmissionError
from research.p5_daily.scoring import (
    score_count, full_pmf, three_way, score_contract, score_joint,
    paired_differences, matched_native_nhl_pair, validate_combo, ScoreError,
    LOCKED_NHL, local_slate_date,
)
from research.p5_daily.registry import (
    register_model, rollback_model, select_for_forecast, read_transitions,
    admit_training_observation, POLICY,
)
from research.p5_daily.workflow import (
    settle, run_isolated_daily, eligible_training_row,
    execute_model_update, derive_nba_combinations,
)

CODE="a"*40
T0="2026-11-19T12:00:00Z"
TTRAIN="2026-11-19T23:00:00Z"
START="2026-11-20T19:00:00Z"
FREEZE="2026-11-20T17:45:00Z"
FORECAST="2026-11-20T18:00:00Z"
AVAILABLE="2026-11-20T23:00:00Z"
SETTLED="2026-11-21T06:00:00Z"
LATER="2026-11-22T06:00:00Z"

def sha(b):
    return hashlib.sha256(b).hexdigest()

class Fixture:
    """Invented model/source bytes only; NEVER original live evidence."""
    def __init__(self,root,sport="NBA",dnp=False,real_quote=False):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.sport=sport
        stat="points" if sport=="NBA" else "shots on goal"
        self.stat=stat
        self._makefile("source/pregame.bin",b"SYNTHETIC SOURCE AT 17:30")
        self._makefile("models/fitted.bin",b"SYNTHETIC MODEL PARAMS BEFORE 2026-11-20")
        pre=self._source("pregame","source/pregame.bin",
             "2026-11-20T17:30:00Z","2026-11-20T17:35:00Z")
        features={"prior_rate":1.0,"history_length":5}
        f=record("PregameFeatureSnapshot",feature_snapshot_id="feature-1",
             sport=sport,event_id="E1",team_id="T1",opponent_id="T2",
             player_id="P1",stat_key=stat,period="full",input_freeze_at=FREEZE,
             source_receipt_ids=["pregame"],feature_sha256=sha256(features),
             reconstruction_class="original",features=features)
        m=record("ModelArtifact",model_artifact_id="modelartifact-1",
             model_id="synthetic-model",model_version="1",
             model_code_sha=CODE,artifact_sha256=sha(b"SYNTHETIC MODEL PARAMS BEFORE 2026-11-20"),
             artifact_path="models/fitted.bin",training_data_sha256="b"*64,
             training_cutoff_at=TTRAIN,created_at="2026-11-19T23:30:00Z",
             training_scope="synthetic_only",feature_schema_id="fixture-v1")
        d={"kind":"discrete","masses":[[0,0.75],[1,0.25]]}
        quote=None
        if real_quote:
            self._makefile("source/quote.bin",b"SYNTHETIC MADE UP QUOTE")
            qr=self._source("quote-source","source/quote.bin",
                 "2026-11-20T17:35:00Z","2026-11-20T17:36:00Z")
            self.sources=[pre,qr]
            quote=record("MarketQuote",quote_id="QUOTE1",contract_id="CON1",
               event_id="E1",sport=sport,team_id="T1",opponent_id="T2",
               player_id="P1",stat_key=stat,period="full",
               quote_timestamp="2026-11-20T17:35:00Z",event_start_at=START,
               book="SYNTHETIC_BOOK",product_type="SYNTHETIC",
               quote_kind="real",line=0,side="paired",
               source_receipt_id="quote-source",source_sha256=qr["source_sha256"],
               terms={"stat_period":"full","overtime_rule":"included",
                      "dnp_policy":"void","partial_game_policy":"settle"},
               accepted=True,reject_reason=None)
        else:
            self.sources=[pre]
        ff=record("ForecastSnapshot",forecast_id="F1",run_id="TEST1",
            sport=sport,league=sport,season=2026,event_id="E1",
            team_id="T1",opponent_id="T2",player_id="P1",stat_key=stat,
            period="full",event_start_at=START,forecast_at=FORECAST,
            input_freeze_at=FREEZE,model_training_cutoff_at=TTRAIN,
            feature_snapshot_id="feature-1",model_artifact_id="modelartifact-1",
            model_id="synthetic-model",model_version="1",
            source_receipt_ids=[s["receipt_id"] for s in self.sources],
            input_sha256=sha256(f),output_sha256=sha256(d),
            model_code_sha=CODE,artifact_sha256=m["artifact_sha256"],
            seed=7,distribution=d,
            uncertainty={"complete_pipeline_id":"S_ONLY"},
            abstention_reasons=[],admission_class="B" if quote else "A",
            eligible=True,quote_id="QUOTE1" if quote else None,
            line=0 if quote else None,side="over" if quote else None,
            market_probability=None)
        self.frozen={"forecast":ff,"feature":f,"model":m,"sources":self.sources,"quote":quote}
        self._makefile("source/official.bin",b"SYNTHETIC FINAL BOX")
        official=self._source("official","source/official.bin",
                              AVAILABLE,"2026-11-20T23:05:00Z")
        o=record("OutcomeRecord",outcome_id="O1",sport=sport,event_id="E1",
            team_id="T1",player_id="P1",stat_key=stat,period="full",
            official_result_available_at=AVAILABLE,
            official_source_receipt_id="official",
            official_source_sha256=official["source_sha256"],
            actual_value=None if dnp else 0,
            participation="DNP" if dnp else "PLAYED",
            result_version="v1",status="FINAL")
        self.official={"outcome":o,"sources":[official],"full_game_participation_verified":True}
    def _makefile(self,path,raw):
        p=self.root/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(raw)
    def _source(self,ident,path,available,observed):
        return record("SourceReceipt",receipt_id=ident,source_id=ident,
            source_kind="synthetic_test",source_available_at=available,
            collected_at=observed,source_sha256=sha((self.root/path).read_bytes()),
            archive_path=path,provenance_class="original_publication")

class MathTests(unittest.TestCase):
    def test_discrete_crps_reference(self):
        d={"kind":"discrete","masses":[[0,.75],[1,.25]]}
        s=score_count(d,0,forecast_id="a")
        self.assertAlmostEqual(s["crps"],.0625)
        self.assertAlmostEqual(s["nlpd"],-math.log(.75))
        self.assertAlmostEqual(s["mean"],.25)
        self.assertEqual(s["observed_zero"],1)
        self.assertEqual(s["randomized_pit"],score_count(d,0,forecast_id="a")["randomized_pit"])
    def test_poisson_crps_independent_energy_identity(self):
        d={"kind":"poisson","parameters":{"rate":1.0}}
        y=2
        s=score_count(d,y)
        p=[math.exp(-1)/math.factorial(k) for k in range(20)]
        reference=sum(abs(k-y)*v for k,v in enumerate(p)) - .5*sum(
                  abs(i-j)*p[i]*p[j] for i in range(20) for j in range(20))
        self.assertAlmostEqual(s["crps"],reference,places=9)
        self.assertAlmostEqual(s["nlpd"],1+math.log(2),places=12)
    def test_nb2_and_gamma_p0_exact(self):
        n={"kind":"nb2","parameters":{"mean":3.,"shape":4.}}
        g={"kind":"gamma_poisson","parameters":{"shape":4.,"rate":4./3}}
        self.assertAlmostEqual(full_pmf(n)[0][0],(4/7)**4,places=11)
        self.assertAlmostEqual(full_pmf(g)[0][0],(4/7)**4,places=11)
        self.assertAlmostEqual(sum(full_pmf(n)[0]),1,places=9)
    def test_impossible_count_log_loss_is_explicit_and_json_safe(self):
        d={"kind":"discrete","masses":[[0,1.0]]}
        s=score_count(d,1,forecast_id="IMPOSSIBLE")
        self.assertTrue(s["nlpd_infinite"])
        self.assertIsNone(s["nlpd"])
        self.assertAlmostEqual(s["crps"],1.0)
        json.dumps(s,allow_nan=False)
        quote={"quote_kind":"real","accepted":True,
               "terms":{"stat_period":"full"},"line":0.5,
               "quote_id":"Q","contract_id":"C","book":"fixture"}
        c=score_contract(d,1,quote)
        self.assertTrue(c["three_way_log_loss_infinite"])
        self.assertIsNone(c["three_way_log_loss"])
        json.dumps(c,allow_nan=False)
    def test_invalid_distribution_and_tail(self):
        for d in ({"kind":"discrete","masses":[[0,.8]]},
                  {"kind":"discrete","masses":[[0,.5],[0,.5]]},
                  {"kind":"p4_count_pmf","pmf_from_zero":[.8],"unallocated_upper_tail_mass":.2},
                  {"kind":"nb2","parameters":{"shape":-1,"mean":3}}):
            with self.assertRaises(ScoreError):
                full_pmf(d)
    def test_market_three_way_integer_push(self):
        d={"kind":"discrete","masses":[[0,.2],[1,.3],[2,.4],[3,.1]]}
        self.assertEqual({k:round(v,8) for k,v in three_way(d,2).items()},
                         {"over":.1,"under":.5,"push":.4})
        self.assertAlmostEqual(three_way(d,2.5)["under"],.9)
        quote={"quote_kind":"real","accepted":True,
               "terms":{"a":1},"line":2,"quote_id":"Q1",
               "contract_id":"C1","book":"test"}
        r=score_contract(d,2,quote)
        self.assertEqual(r["observed"],"push")
        self.assertAlmostEqual(r["three_way_brier"],.01+.25+.36)
        with self.assertRaises(ScoreError):
            score_contract(d,2,{**quote,"quote_kind":"synthetic"})
    def test_energy_variogram_analytic(self):
        x=score_joint([[0,0],[2,2]],[1,1])
        self.assertAlmostEqual(x["energy_score"],math.sqrt(2)/2)
        self.assertEqual(x["variogram_score_p05"],0)
        self.assertEqual(x["n_independent_observed_games"],1)
        approx=score_joint([[0,0],[2,2]],[1,1],pair_budget=1)
        self.assertEqual(approx["pair_evaluation"],"fixed_seed_uniform_pair_mc")
    def test_nba_joint_combinations(self):
        self.assertTrue(validate_combo({"points":16,"rebounds":6,"assists":3,
                      "made_threes":2,"PR":22,"PA":19,"RA":9,"PRA":25}))
        with self.assertRaises(ScoreError):
            validate_combo({"points":16,"rebounds":6,"assists":3,
                      "made_threes":2,"PR":25,"PA":19,"RA":9,"PRA":25})
    def test_grouped_comparison_not_lines_as_games(self):
        r=paired_differences([{"event_id":"a","a":.1,"b":.2}]*3+
                             [{"event_id":"b","a":.3,"b":.2}],n_boot=200)
        self.assertEqual(r["n_distinct_clusters"],2)
        self.assertEqual(r["n_simulated_paths_as_games"],0)
        self.assertAlmostEqual(r["mean_cluster_paired_difference"],0)
    def test_toronto_local_slate_boundaries_and_dst(self):
        self.assertEqual(local_slate_date("2026-11-21T23:30:00Z"),"2026-11-21")
        self.assertEqual(local_slate_date("2026-11-22T00:30:00Z"),"2026-11-21")
        self.assertEqual(local_slate_date("2026-11-22T05:00:00Z"),"2026-11-22")
        self.assertEqual(local_slate_date("2026-07-10T03:30:00Z"),"2026-07-09")
        self.assertEqual(local_slate_date("2026-07-10T04:30:00Z"),"2026-07-10")
        self.assertEqual(local_slate_date("2026-03-08T06:59:00Z"),"2026-03-08")
        self.assertEqual(local_slate_date("2026-03-08T07:01:00Z"),"2026-03-08")
        self.assertEqual(local_slate_date("2026-11-01T05:30:00Z"),"2026-11-01")
        self.assertEqual(local_slate_date("2026-11-01T06:30:00Z"),"2026-11-01")
        self.assertEqual(local_slate_date("2026-11-22T00:30:00Z",
            original_date="2026-11-20", original_date_verified=True),"2026-11-20")
        with self.assertRaises(ScoreError):
            local_slate_date("2026-11-22T00:30:00Z",
                original_date="2026-99-99", original_date_verified=True)

    def test_c10_same_toronto_day_is_one_date(self):
        common={"event_id":"g","player_id":"p","book":"b","quote_id":"q",
          "contract_id":"c","line":2.5,"source_manifest_sha256":"a"*64,
          "input_freeze_at":FREEZE,"original_mean":2.8,"outcome_id":"o",
          "original_verified":True,"source_classification":"original_signed"}
        nb=dict(common,shape=4,experiment_id=LOCKED_NHL,model_family="native_nb2")
        base=dict(common,model_family="plugin_poisson")
        dates=("2026-11-21T23:30:00Z","2026-11-22T00:30:00Z")
        cohort=[{"nb2":{**nb,"event_start_at":d},
                 "poisson":{**base,"event_start_at":d}} for d in dates]
        actual=matched_native_nhl_pair(nb,base,count_dates=2,verified_daily_cohort=cohort)
        self.assertEqual(actual["distinct_prospective_dates"],1)
        self.assertTrue(actual["self_reported_dates_disagree"])

    def test_locked_nhl_pair_and_c10(self):
        common={"event_id":"g","player_id":"p","book":"b","quote_id":"q",
          "contract_id":"c","line":2.5,"source_manifest_sha256":"a"*64,
          "input_freeze_at":FREEZE,"original_mean":2.8,"outcome_id":"o",
          "original_verified":True,"source_classification":"original_signed"}
        nb=dict(common,shape=4,experiment_id=LOCKED_NHL,model_family="native_nb2")
        base=dict(common,model_family="plugin_poisson")
        self.assertEqual(matched_native_nhl_pair(nb,base,count_dates=39)["status"],
                         "DESCRIPTIVE_ONLY")
        self.assertEqual(matched_native_nhl_pair(nb,base,count_dates=40)["status"],
                         "DESCRIPTIVE_ONLY")
        cohort=[]
        from datetime import timedelta
        first=datetime(2026,9,1,tzinfo=timezone.utc)
        for i in range(40):
            date=(first+timedelta(days=i)).isoformat().replace("+00:00","Z")
            cohort.append({"nb2":{**nb,"event_start_at":date},
                           "poisson":{**base,"event_start_at":date}})
        proof=matched_native_nhl_pair(nb,base,count_dates=40,
                                     verified_daily_cohort=cohort)
        self.assertEqual(proof["distinct_prospective_dates"],40)
        self.assertEqual(proof["status"],"C10_REVIEW_PENDING_INDEPENDENT_AUDIT")
        self.assertFalse(proof["production_approval"])
        wrong=matched_native_nhl_pair(nb,base,count_dates=40,
                                     verified_daily_cohort=cohort[:39])
        self.assertEqual(wrong["status"],"DESCRIPTIVE_ONLY")
        self.assertTrue(wrong["self_reported_dates_disagree"])
        with self.assertRaises(ScoreError):
            matched_native_nhl_pair({**nb,"shape":5},base,count_dates=41)
        with self.assertRaises(ScoreError):
            matched_native_nhl_pair(nb,{**base,"original_mean":2.81},count_dates=41)

class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.receipts=self.root/"p5"
        self.receipts.mkdir()
        self.f=Fixture(self.root/"sources")
    def tearDown(self):
        self.tmp.cleanup()
    def run_case(self,fixture=None,prior=None,run=SETTLED):
        f=fixture or self.f
        return settle(f.frozen,f.official,source_root=f.root,
            receipt_root=self.receipts,run_at=run,prior_settlement=prior,
            evidence_type="synthetic_fixture")
    def test_original_snapshot_bytes_never_change(self):
        before=sha256(self.f.frozen["forecast"])
        result=self.run_case()
        self.assertEqual(result["statistical_status"],"SETTLED")
        self.assertEqual(result["classification"],"SYNTHETIC_ENGINEERING_ONLY")
        self.assertIsNone(result["contract_score"])
        self.assertEqual(before,sha256(self.f.frozen["forecast"]))
        self.assertEqual(result["p5_receipt"]["status"],"APPENDED")
        self.assertEqual(self.run_case()["p5_receipt"]["status"],"IDEMPOTENT_EXISTING")
        # A rerun after the original morning must preserve the identical
        # settlement bytes rather than rewrite settled_at to its new wall time.
        self.assertEqual(self.run_case(run=LATER)["p5_receipt"]["status"],
                         "IDEMPOTENT_EXISTING")
    def test_future_result_and_dnp(self):
        with self.assertRaises(ScoreError):
            self.run_case(run=FORECAST)
        future=self.run_case(run="2026-11-20T22:00:00Z")
        self.assertEqual(future["status"],"PENDING_FINAL")
        fd=Fixture(self.root/"dnp",dnp=True)
        d=settle(fd.frozen,fd.official,source_root=fd.root,
             receipt_root=self.receipts,run_at=SETTLED,
             evidence_type="synthetic_fixture")
        self.assertEqual(d["statistical_status"],"DNP_EXCLUDED")
        self.assertIsNone(d["statistical_score"])
    def test_source_and_forecast_hash_integrity(self):
        (self.f.root/"source/pregame.bin").write_bytes(b"CORRUPTED")
        with self.assertRaises(AdmissionError):
            self.run_case()
    def test_official_identity_mismatch(self):
        self.f.official["outcome"]["player_id"]="WRONG"
        with self.assertRaises(ScoreError):
            self.run_case()
    def test_official_correction_new_revision(self):
        first=self.run_case()
        (self.f.root/"source/official_v2.bin").write_bytes(b"CORRECTED FINAL BOX")
        new_source=self.f._source("official-v2","source/official_v2.bin",
                                  "2026-11-21T11:00:00Z","2026-11-21T11:02:00Z")
        o=self.f.official["outcome"]
        later=dict(o,outcome_id="O2",official_source_receipt_id="official-v2",
                   official_source_sha256=new_source["source_sha256"],
                   actual_value=1,official_result_available_at="2026-11-21T11:00:00Z",
                   result_version="v2",status="CORRECTED")
        self.f.official={"outcome":later,"sources":[new_source]}
        revised=self.run_case(prior=first["settlement_record"],run=LATER)
        self.assertNotEqual(first["p5_receipt"]["sha256"],revised["p5_receipt"]["sha256"])
        self.assertEqual(revised["settlement_record"]["settlement_version"],2)
        self.assertEqual(revised["settlement_record"]["supersedes_id"],
                         first["settlement_record"]["settlement_id"])
    def test_market_term_separation(self):
        f=Fixture(self.root/"priced",real_quote=True)
        s=settle(f.frozen,f.official,source_root=f.root,
            receipt_root=self.receipts,run_at=SETTLED,evidence_type="synthetic_fixture")
        self.assertEqual(s["market_contract_status"],"PUSH")
        self.assertEqual(s["contract_score"]["observed"],"push")
        f.frozen["quote"]["terms"].pop("overtime_rule")
        (self.root/"alternate").mkdir()
        q=settle(f.frozen,f.official,source_root=f.root,
            receipt_root=self.root/"alternate",run_at=SETTLED,
            evidence_type="synthetic_fixture")
        self.assertEqual(q["market_contract_status"],"NOT_SCOREABLE")
    def test_cross_sport_failure_isolation(self):
        nfl=Fixture(self.root/"nba2")
        nhl=Fixture(self.root/"nhl",sport="NHL")
        bad=Fixture(self.root/"bad")
        bad.frozen["forecast"]["event_id"]="ALTERED"
        cases=[{"frozen":bad.frozen,"official":bad.official}]
        result=run_isolated_daily(nba_cases=cases,nhl_cases=[
                  {"frozen":nhl.frozen,"official":nhl.official}],
                  source_root=nhl.root,receipt_root=self.receipts,run_at=SETTLED)
        self.assertEqual(result["sports"]["NBA"]["blocked"],1)
        self.assertEqual(result["sports"]["NHL"]["settled"],1)
    def test_synthetic_rejected_from_training(self):
        z=self.run_case()
        with self.assertRaises(ScoreError):
            eligible_training_row(z,self.f.official,self.f.frozen,cutoff=SETTLED)
    def test_nba_combos_require_one_official_source(self):
        o=self.f.official["outcome"]
        rows=[]
        for stat,value in [("points",17),("rebounds",6),("assists",4),("threes",2)]:
            rows.append(record("OutcomeRecord",**{k:v for k,v in
                        {**o,"stat_key":stat,"actual_value":value}.items()
                        if k not in ("record_type","schema_version")}))
        self.assertEqual(derive_nba_combinations(rows),
                         {"pr":23,"pa":21,"ra":10,"pra":27})
        rows[0]["official_source_sha256"]="c"*64
        with self.assertRaises(ScoreError):
            derive_nba_combinations(rows)

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.row={"sport":"NHL","event_id":"E1","player_id":"P1",
                  "team_id":"T1","stat_key":"shots on goal","official_value":1,
                  "participation":"PLAYED","official_source_sha256":"c"*64,
                  "official_result_available_at":AVAILABLE,"event_start_at":START,
                  "training_admitted":True,"official_outcome_id":"O1",
                  "exposure":{"toi_minutes":15.0}}
    def tearDown(self):
        self.tmp.cleanup()
    def new_row(self,event_id,available_at):
        row=dict(self.row,event_id=event_id,
                 official_outcome_id="O_"+event_id,
                 event_start_at="2026-11-21T09:00:00Z",
                 official_result_available_at=available_at)
        admit_training_observation(self.root,row,effective_cutoff=available_at)
        return row
    def reg(self,state,parent=None,mode="INCREMENTAL_UPDATE",at=SETTLED,
            cutoff=SETTLED,rows=None):
        rows=[self.row] if rows is None else rows
        for r in rows:
            admit_training_observation(self.root,r,effective_cutoff=cutoff)
        return register_model(self.root,model_id="NHL_ADAPTIVE",family="NHL_GAMMA_ADAPTIVE",
              pipeline_id="GAMMA_ADAPTIVE",sport="NHL",state=state,
              parent_version=parent,training_rows=rows,
              cutoff_at=cutoff,created_at=at,code_commit=CODE,
              update_mode=mode,seed=3,diagnostics={"excluded_count":0},
              passed_validation=True)
    def test_register_select_roll_back_and_no_mutation(self):
        admit_training_observation(self.root,self.row,effective_cutoff=SETTLED)
        a=self.reg({"alpha":2,"beta":4})
        self.assertEqual(a["status"],"NEW_RESEARCH_MODEL_ELIGIBLE")
        second=self.new_row("E2","2026-11-21T16:00:00Z")
        b=self.reg({"alpha":3,"beta":19},parent=1,at=LATER,
                   cutoff=LATER,rows=[self.row,second])
        self.assertEqual(b["model"]["version"],2)
        self.assertEqual(select_for_forecast(self.root,"NHL_ADAPTIVE",
                 freeze_at="2026-11-21T07:00:00Z")["model_version"],1)
        self.assertEqual(select_for_forecast(self.root,"NHL_ADAPTIVE",
                 freeze_at="2026-11-22T07:00:00Z")["model_version"],2)
        rollback_model(self.root,"NHL_ADAPTIVE",rollback_to=1,
                 at="2026-11-23T00:00:00Z",reason="failed_new_validation")
        self.assertEqual(select_for_forecast(self.root,"NHL_ADAPTIVE",
                 freeze_at="2026-11-23T01:00:00Z")["model_version"],1)
        self.assertEqual(len(read_transitions(self.root,"NHL_ADAPTIVE")),3)
        third=self.new_row("E3","2026-11-23T10:00:00Z")
        self.assertEqual(self.reg({"alpha":4},parent=1,
                 cutoff="2026-11-23T23:00:00Z",
                 rows=[self.row,second,third],
                 at="2026-11-24T00:00:00Z")["model"]["version"],3)
    def test_model_state_unchanged_fails(self):
        self.reg({"alpha":2})
        second=self.new_row("E2","2026-11-21T16:00:00Z")
        with self.assertRaises(ScoreError):
            self.reg({"alpha":2},parent=1,at=LATER,cutoff=LATER,
                     rows=[self.row,second])
    def test_future_training_and_missing_source(self):
        with self.assertRaises(ScoreError):
            self.reg({"alpha":2},at="2026-11-20T20:00:00Z")
        self.row["official_source_sha256"]=None
        with self.assertRaises(ScoreError):
            self.reg({"alpha":2})
    def test_empty_update_and_locked_model(self):
        result=execute_model_update(self.root,family="NHL_GAMMA_ADAPTIVE",
              model_id="M",sport="NHL",pipeline_id="ADAPTIVE",
              state_update="INCREMENTAL_UPDATE",training_rows=[],
              cutoff_at=SETTLED,created_at=LATER,code_commit=CODE,
              seed=1,diagnostics={},fit_callback=lambda *a:{"x":2})
        self.assertEqual(result["status"],"UNCHANGED")
        with self.assertRaises(ScoreError):
            register_model(self.root,model_id="LOCKED",family="NHL_NATIVE_NB2_LOCKED",
                pipeline_id="NATIVE",sport="NHL",state={"shape":4},
                parent_version=None,training_rows=[self.row],cutoff_at=SETTLED,
                created_at=LATER,code_commit=CODE,update_mode="INCREMENTAL_UPDATE",
                seed=1,diagnostics={},passed_validation=True)
    def test_failed_callback_preserves_parent(self):
        self.reg({"alpha":2})
        result=execute_model_update(self.root,family="NHL_GAMMA_ADAPTIVE",
              model_id="NHL_ADAPTIVE",sport="NHL",pipeline_id="ADAPTIVE",
              state_update="INCREMENTAL_UPDATE",training_rows=[self.row],
              cutoff_at=SETTLED,created_at=LATER,code_commit=CODE,
              seed=1,diagnostics={},previous_version=1,
              fit_callback=lambda *a:1/0,
              validation_callback=lambda *a: True)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(len(read_transitions(self.root,"NHL_ADAPTIVE")),1)
    def test_registry_concurrent_same_parent_only_one_wins(self):
        self.reg({"alpha":2})
        second=self.new_row("E2","2026-11-21T16:00:00Z")
        results=[]
        def worker(a):
            try:
                results.append(self.reg({"alpha":a},parent=1,at=LATER,cutoff=LATER,
                     rows=[self.row,second])["status"])
            except Exception as e:
                results.append(type(e).__name__)
        ts=[threading.Thread(target=worker,args=(x,)) for x in (3,4)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(results.count("NEW_RESEARCH_MODEL_ELIGIBLE"),1)
        self.assertEqual(len(read_transitions(self.root,"NHL_ADAPTIVE")),2)
    def test_interrupted_prepared_artifact_does_not_activate(self):
        self.reg({"alpha":2})
        (self.root/"versions/NHL_ADAPTIVE/orphan.json").write_text("{}")
        # Simulated mid-write transition in the fsynced .pending namespace:
        # non-activated data must not hide an older valid registry version.
        (self.root/"transitions/NHL_ADAPTIVE/.pending-stalled.tmp").write_bytes(b"{")
        self.assertEqual(select_for_forecast(self.root,"NHL_ADAPTIVE",
                   freeze_at=LATER)["model_version"],1)
        with self.assertRaises(ScoreError):
            select_for_forecast(self.root,"NHL_ADAPTIVE",freeze_at=T0)

if __name__=="__main__":
    unittest.main()
