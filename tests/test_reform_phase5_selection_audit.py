"""Adversarial frozen, full-universe top-k rank replay tests."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_phase5_selection_audit as audit


def fixture():
    base={"run_id":"frozen","forecast_at":"2026-11-08T14:00:00+00:00",
          "event_start":"2026-11-08T18:00:00Z",
          "sport":"NFL","player_id":"p1","player":"Example",
          "team":"CAR","opponent":"DEN","stat":"receptions",
          "side":"under","line":4.5,
          "block_reason":"POST_SHADOW_PRODUCTION_PENDING",
          "Engine_A":.63,"Engine_B":.65,
          "Bayesian_A":.70,"Bayesian_B":.72,
          "Consensus":.72,"Market":.50,
          "production_consensus_available":True,
          "models":{"Engine_A":{"reliable":True},
                    "Engine_B":{"reliable":True},
                    "Market":{"status":"forecast","books":["Fanduel","DraftKings"]}}}
    review={k:base[k] for k in ("run_id","forecast_at","sport","player_id",
                               "player","team","opponent","stat","side","line")}
    review.update(original_block_reason=base["block_reason"],
                  player_tendency={"status":"unavailable","opportunity":None})
    comparison={"schema":"slate-model-comparison-v1",
                "metadata":{"run_id":"frozen","day":"2026-11-08"},
                "picks":[base]}
    reviews={"schema":"slate-full-universe-player-opponent-review-v1",
             "run_id":"frozen","date":"2026-11-08",
             "contracts_reviewed":1,"reviews":[review]}
    return comparison,reviews


def files(folder):
    c,r=fixture()
    p=Path(folder)
    a,b=p/"comparison.json",p/"reviews.json"
    a.write_text(json.dumps(c));b.write_text(json.dumps(r))
    return a,b


def board_from(candidate):
    row=candidate["row"]
    return {"schema":"slate-evidence-priority-v1",
            "date":"2026-11-08",
            "full_universe_before_top10":True,
            "ranking_not_a_probability":True,
            "original_forecasts_unchanged":True,
            "candidate_pool_count":1,
            "full_universe_evaluated":1,
            "excluded":{},
            "top_counts":{"NFL":1,"NBA":0,"NHL":0},
            "top_10_by_sport":{
                "NFL":[{**row,"research_priority_score":candidate["score"],
                        "sport_rank":1}],
                "NBA":[],"NHL":[]}
            }


class FrozenTopKTests(unittest.TestCase):
    def test_reconstructs_complete_eligibility_and_rank(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            cohort,excluded,total=audit.rebuild_pool(a,b)
            self.assertEqual(total,1)
            self.assertEqual(excluded,{})
            self.assertEqual(len(cohort),1)
            result=audit.reconstructed_ranks(cohort,board_from(cohort[0]))
            self.assertEqual(result["NFL"][0]["identity"],cohort[0]["identity"])

    def test_wrong_rank_score_fails_not_repaired_after_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            cohort,_,_=audit.rebuild_pool(a,b)
            board=board_from(cohort[0])
            board["top_10_by_sport"]["NFL"][0]["research_priority_score"]+=1
            with self.assertRaisesRegex(audit.SelectionAuditError,"not_reproducible"):
                audit.reconstructed_ranks(cohort,board)

    def test_mutated_review_original_clock_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            original=json.loads(b.read_text())
            original["reviews"][0]["forecast_at"]="2026-11-08T14:00:01Z"
            b.write_text(json.dumps(original))
            with self.assertRaisesRegex(audit.SelectionAuditError,"unmatched_frozen_review_identity"):
                audit.rebuild_pool(a,b)

    def test_poststart_input_never_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            data=json.loads(a.read_text())
            data["picks"][0]["forecast_at"]="2026-11-08T19:00:00Z"
            a.write_text(json.dumps(data))
            with self.assertRaisesRegex(audit.SelectionAuditError,"poststart_forecast"):
                audit.rebuild_pool(a,b)

    def test_unqualified_model_does_not_pass_research_gate(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            data=json.loads(a.read_text())
            data["picks"][0]["models"]["Engine_A"]["reliable"]=False
            a.write_text(json.dumps(data))
            cohort,excluded,_=audit.rebuild_pool(a,b)
            self.assertEqual(cohort,[])
            self.assertEqual(excluded,{"production_or_primary_research_gate":1})

    def test_without_two_original_books_rank_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            data=json.loads(a.read_text())
            data["picks"][0]["models"]["Market"]["books"].pop()
            a.write_text(json.dumps(data))
            cohort,excluded,_=audit.rebuild_pool(a,b)
            self.assertEqual(cohort,[])
            self.assertEqual(excluded,{"fewer_than_two_matched_frozen_books":1})

    def test_calibration_uses_one_bet_side_not_opposite_complement(self):
        items=[{"consensus":.70,"market":.53,"hit":1,
                "game_id":"G1","stat":"receptions","side":"under"},
               {"consensus":.63,"market":.50,"hit":0,
                "game_id":"G1","stat":"receptions","side":"over"}]
        s=audit.score_observations(items)
        self.assertEqual(s["n"],2)
        self.assertEqual(s["hits"],1)
        self.assertAlmostEqual(s["hit_rate"],.5)
        self.assertAlmostEqual(s["consensus_brier"],(.3*.3+.63*.63)/2)
        self.assertEqual(s["distinct_games"],1)

    def test_full_audit_rejects_hidden_board_eligibility_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            cohort,_,_=audit.rebuild_pool(a,b)
            board=board_from(cohort[0])
            board["candidate_pool_count"]=2
            path=Path(d)/"board.json"
            path.write_text(json.dumps(board))
            with self.assertRaisesRegex(audit.SelectionAuditError,"not_replayable"):
                audit.audit(frozen=a,review=b,board=path,
                            settlement=Path(d)/"unused.json",pinned=Path(d)/"unused2.json")

    def test_sample_size_never_certifies_optimizers_curse(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=files(d)
            cohort,_,_=audit.rebuild_pool(a,b)
            board=board_from(cohort[0])
            path=Path(d)/"board.json"
            path.write_text(json.dumps(board))
            row=cohort[0]["row"]
            contract=("NFL",row["event_start"],row["team"],row["opponent"],
                      row["player_id"],row["player"],row["stat"],"4.5")
            observed=[{"contract":contract,"outcome":"under","game_id":"game01"}]
            with patch.object(audit,"load_nfl_slate",return_value=(observed,{})):
                result=audit.audit(frozen=a,review=b,board=path,
                                  settlement=Path(d)/"unused.json",pinned=Path(d)/"unused2.json")
            self.assertEqual(result["outcome_scope"]["selected_1pm_top10_scored"],1)
            self.assertFalse(result["evidence_sufficient_to_infer_optimizers_curse"])
            self.assertFalse(result["production_changed"])
            self.assertFalse(result["training_started"])


if __name__=="__main__":
    unittest.main()
