"""Adversarial Phase 1 exit tests: old-vote pairing, temporal folds, exact scoring."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import io
import json
import math
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

from v2.contracts import (ContractError, SourceReceipt, DiscreteDistribution,
                          FixedLineDistribution, PoissonDistribution,
                          parse_distribution, canonical_hash)
from v2.evaluation import (categorical_brier, categorical_log_loss,
                           energy_score, variogram_score, evaluate, Settlement)
from v2.experiment import run_experiment, assess_independence
from v2.legacy_adapter import scan_original_pairs
from v2.rolling import run_rolling
from v2.stat_registry import canonical_stat, validate_full_game_settlement
from test_v25_phase1 import forecast, quote, settlement

SHA = "a" * 64
COMMIT = "f" * 40
EXP = "V25-EXP-B-2024-ROLLING-ORIGIN"
T0 = datetime(2024, 9, 5, 18, tzinfo=timezone.utc)


def timestamp(d):
    return d.isoformat().replace("+00:00", "Z")


def synthetic_rolling(n=12):
    """In-memory fixture: never a claim of actual 2024 sportsbook availability."""
    payload = {"schema": "v25-rolling-input-1", "experiment_id": EXP,
               "history": [], "quotes": [], "settlements": [], "origins": []}
    for prior in range(5):
        event = T0 - timedelta(days=(prior+1)*7)
        for player, count in (("p1", 4+prior%2), ("p2", 6+prior%2)):
            payload["history"].append({
                "player_id": player, "stat_key": "targets",
                "role": "WR1", "event_id": f"prior-{prior}",
                "event_start_at": timestamp(event),
                "available_at": timestamp(event+timedelta(hours=5)),
                "exposure": 10.0, "count": float(count),
            })
    for week in range(n):
        game = T0 + timedelta(days=7*week)
        freeze = game - timedelta(hours=3)
        week_offers = []
        for player, count in (("p1", 4+week%3), ("p2", 5+week%2)):
            qid = f"q{week}-{player}"
            is_real = (player == "p1")
            q = dict(quote_id=qid, contract_id="contract-"+qid,
                     event_id=f"season-game-{week}",event_start_at=timestamp(game),
                     sport="NFL",league="NFL",season=2024,
                     team_id="BUF",opponent_id="KC",player_id=player,
                     stat_key="targets",period="full",line=4.5,
                     book="original-source",product_type="sportsbook_two_sided" if is_real else "diagnostic_only",
                     quote_at=timestamp(freeze-timedelta(minutes=15)),
                     quote_receipt_sha256=SHA,
                     settlement_policy="strict_gt_lt_equal_push",
                     quote_kind="real" if is_real else "synthetic",
                     accepted=True,reject_reason=None,
                     over_decimal_odds=1.91 if is_real else None,
                     under_decimal_odds=1.95 if is_real else None)
            payload["quotes"].append(q)
            source = {
                "source_id":"src-"+qid, "first_available_at":timestamp(freeze-timedelta(minutes=18)),
                "retrieved_at":timestamp(freeze-timedelta(minutes=17)),
                "content_sha256":SHA,"source_uri":"https://example.org/archived/"+qid,
                "archive_path":"original/"+qid+".json"}
            week_offers.append({"quote_id":qid,"role":"WR1",
                                "projected_exposure":10.,"sources":[source]})
            payload["history"].append({
                "player_id":player,"stat_key":"targets","role":"WR1",
                "event_id":f"season-game-{week}","event_start_at":timestamp(game),
                "available_at":timestamp(game+timedelta(hours=6)),
                "exposure":10.,"count":float(count)})
            payload["settlements"].append(dict(event_id=f"season-game-{week}",
                player_id=player,stat_key="targets",period="full",
                status="settled",actual=float(count),
                settled_at=timestamp(game+timedelta(hours=6))))
        payload["origins"].append({"origin_id":f"2024-W{week+1:02d}",
            "freeze_at":timestamp(freeze),"offers":week_offers})
    return payload


def legacy_rows():
    freeze = "2026-11-09T16:30:00Z"
    common = {
        "run_id":"r1","game_date":"2026-11-09","sport":"NFL",
        "event_id":"NFL-1","player_id":"player1","stat":"targets",
        "reference_line":4.5,"event_start":"2026-11-09T18:00:00Z",
        "input_freeze_at":freeze,"model_training_cutoff_at":"2026-11-08T00:00:00Z",
        "blend":{"available":True,"weights":{"a":.6,"b":.4}},
        "forecast_at":"2026-11-09T16:35:00Z","q_push":0.,
        "source_receipts":[{"source_id":"collector","model_component":"Engine_A",
            "source_kind":"collector_input_bytes",
            "content_sha256":SHA,"archive_path":"candidate/a.bin",
            "observed_at":"2026-11-09T16:29:00Z"}],
    }
    return [{**common,"side":"over","q_model":.6},
            {**common,"side":"under","q_model":.4}]


def protocol():
    return {"experiment_id":EXP,"start_season":2024,
            "promotion_authorized":False,
            "2025_independent_holdout_status":
                "not_independent_not_eligible_for_unseen_holdout_claims"}


class StatContracts(unittest.TestCase):
    def test_registered_aliases_and_signed_yardage(self):
        self.assertEqual(canonical_stat("NHL", "sog").key,"shots on goal")
        self.assertEqual(canonical_stat("NBA","points + rebounds + assists").key,"pra")
        self.assertEqual(validate_full_game_settlement("NFL","receiving yards","full",-4),-4.)
        with self.assertRaisesRegex(ContractError,"negative_statistic"):
            validate_full_game_settlement("NFL","targets","full",-1)
        with self.assertRaisesRegex(ContractError,"noninteger"):
            validate_full_game_settlement("NHL","goalie saves","full",21.5)
        with self.assertRaisesRegex(ContractError,"unsupported_stat_period"):
            canonical_stat("NFL","targets","first_half")
        with self.assertRaisesRegex(ContractError,"not_registered"):
            canonical_stat("NBA","synthetic_expected_possessions")

    def test_exact_original_fixed_line_cannot_be_repriced(self):
        d=FixedLineDistribution(4.5,.7,.3,0)
        self.assertEqual(parse_distribution(d.to_record()).probabilities(4.5), d.probabilities(4.5))
        with self.assertRaisesRegex(ContractError,"fixed_line_cannot_be_repriced"):
            d.probabilities(5.5)
        with self.assertRaisesRegex(ContractError,"probability_complementarity"):
            FixedLineDistribution(4.5,.7,.7,0)

    def test_collector_possession_cannot_claim_false_publication_uri(self):
        common=dict(source_id="candidate",first_available_at="2026-11-09T16:30:00Z",
                    retrieved_at="2026-11-09T16:30:00Z",
                    content_sha256=SHA,archive_path="candidate/a.bin")
        self.assertIsNone(SourceReceipt(**common,source_uri=None,
                           source_kind="archive_possession").source_uri)
        with self.assertRaisesRegex(ContractError,"archive_possession"):
            SourceReceipt(**common,source_uri="https://example.org/as-if-provider",
                          source_kind="archive_possession")
        with self.assertRaisesRegex(ContractError,"archive_possession"):
            SourceReceipt(**{**common,"retrieved_at":"2026-11-09T16:31:00Z"},
                          source_uri=None,source_kind="archive_possession")


class OriginalLegacyTests(unittest.TestCase):
    def test_final_60_40_both_sides_and_binding(self):
        rows=legacy_rows()
        report=scan_original_pairs(rows,strict_checker=lambda row,**kw:(True,"fixture"),
                                   archive_root="fixture")
        self.assertEqual(report["eligible_pairs"],1)
        pair=report["pairs"][0]
        q=quote()
        saved=pair.bind(q,code_commit=COMMIT,model_artifact_sha256=SHA)
        self.assertAlmostEqual(saved.distribution.probabilities(4.5).over,.6)
        self.assertEqual(saved.distribution.to_record()["kind"],"fixed_line")
        with self.assertRaisesRegex(ContractError,"fixed_line_cannot_be_repriced"):
            saved.distribution.probabilities(3.5)
        self.assertEqual(saved.run_id,"r1")

    def test_uncertified_and_preliminary_are_never_frozen_v1(self):
        rows=legacy_rows()
        self.assertEqual(scan_original_pairs(rows)["eligible_pairs"],0)
        self.assertEqual(scan_original_pairs(rows)["reasons"],
                         {"phase0r_certificate_required":1})
        old=[dict(r) for r in rows]
        old[0]["q_model"]=None
        self.assertEqual(scan_original_pairs(old,strict_checker=lambda row,**kw:(True,"fixture"),
                         archive_root="fixture")["eligible_pairs"],0)
        preliminary=[dict(r) for r in rows]
        preliminary[1]["blend"]={"available":True,"weights":{"a":.6,"b":.4},
                                 "preliminary":True}
        self.assertEqual(scan_original_pairs(preliminary,strict_checker=lambda row,**kw:(True,"fixture"),
                         archive_root="fixture")["eligible_pairs"],0)
        tampered=[dict(r) for r in rows]
        tampered[1]["q_model"]=.8
        result=scan_original_pairs(tampered,strict_checker=lambda row,**kw:(True,"fixture"),
                                   archive_root="fixture")
        self.assertEqual(result["eligible_pairs"],0)

    def test_duplicate_original_side_rejected_and_pair_missing_preserved(self):
        rows=legacy_rows()
        with self.assertRaisesRegex(ContractError,"duplicate_original_side"):
            scan_original_pairs(rows+[rows[0]])
        self.assertEqual(scan_original_pairs(rows[:1])["reasons"],
                         {"legacy_opposite_side_missing":1})


class ThreeWayScoringTests(unittest.TestCase):
    def test_analytic_three_way_scores_and_push(self):
        self.assertAlmostEqual(categorical_brier((.2,.3,.5),"push"),.38)
        self.assertAlmostEqual(categorical_log_loss((.2,.3,.5),"push"),-math.log(.5))
        q=quote(line=6.)
        d=DiscreteDistribution(((0.,.2),(6.,.5),(9.,.3)))
        f=forecast(q,distribution=d)
        report=evaluate([q],[f],[settlement(actual=6)])
        self.assertEqual(report["scorable_contracts"],0)
        self.assertEqual(report["settled_three_way_contracts"],1)
        self.assertEqual(report["models"]["frozen_v1"]["categorical_push_n"],1)
        self.assertAlmostEqual(report["models"]["frozen_v1"]["categorical_log_loss"],-math.log(.5))

    def test_market_no_vig_only_real_and_complete_universe(self):
        q1=quote(product_type="sportsbook_two_sided",
                 over_decimal_odds=1.92,under_decimal_odds=1.92)
        q2=quote(quote_id="q2",contract_id="c2",player_id="unforecasted")
        q3=quote(quote_id="q3",contract_id="c3",accepted=False,reject_reason="quote_stale")
        report=evaluate([q1,q2,q3],[forecast(q1)],[settlement()])
        self.assertEqual(report["quotes_total"],3)
        self.assertEqual(report["real_market_binary_reference"]["scored"],1)
        self.assertEqual(report["unforecasted_accepted_offers"]["frozen_v1"],1)
        self.assertEqual(report["models"]["frozen_v1"]["scorable_missing_forecast"],0)
        self.assertIn("NFL|targets|real",report["models"]["frozen_v1"]["stratified"])
        self.assertEqual(len(report["models"]["frozen_v1"]["calibration_bins"]),5)

    def test_fuzz_poisson_and_discrete_push_mass(self):
        rng=random.Random(7235)
        for i in range(140):
            rate=rng.uniform(0,12)
            line=rng.choice([0.,.5,1.,1.5,2.,2.5,3.,4.5,7.])
            x=PoissonDistribution(rate).probabilities(line)
            self.assertAlmostEqual(x.over+x.under+x.push,1,places=10)
            self.assertGreaterEqual(x.over,0)
            self.assertGreaterEqual(x.under,0)
            brute=sum(math.exp(-rate+k*math.log(rate)-math.lgamma(k+1))
                      for k in range(120) if k>line)
            self.assertAlmostEqual(x.over,brute,places=10)
        signed=DiscreteDistribution(((-3.,.2),(0.,.2),(1.,.6)))
        self.assertAlmostEqual(signed.probabilities(0).push,.2)

    def test_energy_vs_analytic_difference(self):
        self.assertAlmostEqual(energy_score([(0.,0.)],(0.,0.)),0)
        self.assertAlmostEqual(energy_score([(0.,0.)],(3.,4.)),5)
        self.assertAlmostEqual(variogram_score([(0.,2.)],(1.,0.)),(math.sqrt(2)-1)**2)


class RollingTests(unittest.TestCase):
    def test_full_universe_seed_deterministic_and_no_future_game_data(self):
        payload=synthetic_rolling()
        first=run_rolling(payload,seed=919)
        second=run_rolling(payload,seed=919)
        self.assertEqual(canonical_hash(first),canonical_hash(second))
        self.assertEqual(first["all_quotes"],24)
        self.assertEqual(first["all_origins"],12)
        self.assertEqual(first["statuses"]["scorable"],24)
        self.assertEqual(first["models"]["two_sided_no_vig_market"]["matched_scorable_contracts"],12)
        self.assertEqual(first["models"]["naive_pregame_exposure_rate"]["matched_scorable_contracts"],24)
        self.assertTrue(first["counterfactual_only"])
        self.assertEqual(first["prospective_forecasts_created"],0)
        self.assertEqual(first["paired"]["role_shrunk_hierarchical_rate"]
                        ["game_cluster_brier_interval"]["status"],"descriptive_only")
        for fold in first["origin_manifest"]:
            freeze=datetime.fromisoformat(fold["input_freeze_at"].replace("Z","+00:00"))
            self.assertTrue(all(
                not event.endswith(f"-{int(fold['origin_id'][-2:])-1}")
                for event in fold["training_event_ids"]))
            if fold["max_training_available_at"]:
                self.assertLessEqual(datetime.fromisoformat(
                    fold["max_training_available_at"]),freeze)

    def test_future_market_and_projected_exposure_leaks_blocked(self):
        for scenario in ("quote", "source", "kickoff", "duplicate", "uncovered"):
            with self.subTest(scenario=scenario):
                payload=synthetic_rolling(2)
                offer=payload["origins"][0]["offers"][0]
                if scenario=="quote":
                    payload["quotes"][0]["quote_at"]="2024-09-05T18:00:00Z"
                    expected="future_market_quote"
                elif scenario=="source":
                    offer["sources"][0]["retrieved_at"]="2024-09-05T17:00:00Z"
                    expected="future_projected_exposure"
                elif scenario=="kickoff":
                    payload["origins"][0]["freeze_at"]="2024-09-05T19:00:00Z"
                    expected="rolling_origin_after_kickoff"
                elif scenario=="duplicate":
                    payload["origins"][0]["offers"].append(dict(offer))
                    expected="reused_origin_quote"
                else:
                    payload["origins"][0]["offers"].pop()
                    expected="uncovered_rolling_quote"
                with self.assertRaisesRegex(ContractError,expected):
                    run_rolling(payload)

    def test_missing_void_push_and_rejected_denominators(self):
        payload=synthetic_rolling(3)
        payload["quotes"][0]["accepted"]=False
        payload["quotes"][0]["reject_reason"]="original_quote_unverified"
        payload["settlements"]= [
            s for s in payload["settlements"] if s["player_id"]!="p2" or not s["event_id"].endswith("0")
        ]
        payload["settlements"][0]["status"]="void"
        payload["settlements"][0]["actual"]=None
        payload["settlements"][0]["settled_at"]=None
        out=run_rolling(payload)
        self.assertEqual(out["all_quotes"],6)
        self.assertEqual(out["statuses"]["rejected_quote"],1)
        self.assertEqual(out["statuses"]["missing_settlement"],1)
        self.assertEqual(out["statuses"]["void"],1)
        self.assertEqual(len(out["contract_ledger"]),6)

    def test_unregistered_signed_yards_not_as_poisson(self):
        payload=synthetic_rolling(1)
        for q in payload["quotes"]:
            q["stat_key"]="receiving yards"
        for s in payload["settlements"]:
            s["stat_key"]="receiving yards"
        for r in payload["history"]:
            r["stat_key"]="receiving yards"
        outcome=run_rolling(payload)
        self.assertEqual(outcome["models"]["naive_pregame_exposure_rate"]
                         ["matched_scorable_contracts"],0)
        self.assertIn("non_count_likelihood_requires_distinct_baseline",
                      outcome["models"]["naive_pregame_exposure_rate"]["missing_reasons"])


class ExperimentTests(unittest.TestCase):
    def test_receipt_determinism_and_2025_not_independent(self):
        payload={"experiment_id":EXP,"rolling":synthetic_rolling(8)}
        cfg=protocol()
        r1=run_experiment(payload,cfg,input_sha256=SHA,protocol_sha256=SHA,
                          code_commit=COMMIT,seed=8)
        r2=run_experiment(payload,cfg,input_sha256=SHA,protocol_sha256=SHA,
                          code_commit=COMMIT,seed=8)
        self.assertEqual(r1["receipt_sha256"],r2["receipt_sha256"])
        self.assertFalse(r1["independence_audit"]["may_be_used_as_untouched_holdout"])
        self.assertEqual(r1["rolling"]["all_quotes"],16)
        self.assertFalse(r1["production_promotion_authorized"])
        with self.assertRaisesRegex(ContractError,"unsupported_2025"):
            assess_independence({**cfg,"2025_independent_holdout_status":"certified"})

    def test_one_command_immutable_and_hash_receipt(self):
        from scripts.v25_phase1_experiment import main
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            input_file=root/"input.json"
            protocol_file=root/"protocol.json"
            output_file=root/"report.json"
            json.dump({"experiment_id":EXP,"rolling":synthetic_rolling(4)},
                      input_file.open("w"))
            json.dump(protocol(),protocol_file.open("w"))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--input",str(input_file),
                    "--output",str(output_file),"--protocol",str(protocol_file),
                    "--code-commit",COMMIT]),0)
            data=json.loads(output_file.read_text())
            self.assertEqual(data["schema"],"v25-phase1-experiment-manifest-1")
            self.assertEqual(len(data["input_sha256"]),64)
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--input",str(input_file),
                          "--output",str(output_file),
                          "--protocol",str(protocol_file),
                          "--code-commit",COMMIT])


if __name__=="__main__":
    unittest.main()
