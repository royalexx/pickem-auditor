"""WS1 Nov16 source-population safety regressions; synthetic fixtures only."""
from __future__ import annotations
import copy,json,pathlib,tempfile,unittest
from scripts.population_replay_guard import (
    canonical,digest,identity,reconcile_population,enforce_population
)
DAY="2026-11-15"
def row(**kw):
    base={"sport":"NFL","stat":"pass attempts","game_id":"401873055",
          "player_id":"4685720","game_date":DAY,"value":30,"workload":62,
          "source_sha256":"a"*64,"source_url":"https://example.invalid/immutable"}
    base.update(kw)
    return base
def doc(*rows,receipt="complete"):
    return {"phase":"morning","game_date":DAY,
            "population_collection_receipt":{"status":receipt},
            "population":list(rows)}

class PopulationGuardTests(unittest.TestCase):
    def test_single_observation(self):
        accepted,rep=reconcile_population([doc(row())],DAY)
        self.assertEqual(accepted,[row()])
        self.assertFalse(rep["quarantine"])
        self.assertTrue(rep["posterior_update_allowed"])
    def test_identical_retry_within_bundle(self):
        accepted,rep=reconcile_population([doc(row(),row())],DAY)
        self.assertEqual(accepted,[row()])
        self.assertEqual(rep["exact_retry_count"],1)
    def test_identical_retry_across_bundles(self):
        accepted,rep=reconcile_population([doc(row()),doc(copy.deepcopy(row()))],DAY)
        self.assertEqual(accepted,[row()])
        self.assertEqual(rep["exact_retry_count"],1)
    def test_key_order_not_conflict(self):
        newer=dict(reversed(list(row().items())))
        accepted,rep=reconcile_population([doc(row(),newer)],DAY)
        self.assertEqual(len(accepted),1)
        self.assertEqual(rep["conflicting_identity_count"],0)
    def test_conflicting_value_quarantine_no_partial_learning(self):
        _,rep=reconcile_population([doc(row(),row(value=35),row(player_id="other"))],DAY)
        self.assertEqual(rep["conflicting_identity_count"],1)
        self.assertFalse(rep["posterior_update_allowed"])
        self.assertEqual(len(rep["quarantine"][0]["variant_sha256"]),2)
        with self.assertRaisesRegex(ValueError,"CONFLICTING_DUPLICATE_POPULATION_OBSERVATION"):
            enforce_population([doc(row(),row(value=35))],DAY)
    def test_conflicting_provenance_quarantine(self):
        _,rep=reconcile_population([doc(row(),row(source_sha256="b"*64))],DAY)
        self.assertEqual(rep["conflicting_identity_count"],1)
        self.assertIn("source_sha256",rep["quarantine"][0]["varying_fields"])
    def test_missing_receipt_fail_closed(self):
        _,rep=reconcile_population([doc(row(),receipt="pending")],DAY)
        self.assertEqual(rep["malformed_or_incomplete_count"],1)
        self.assertFalse(rep["posterior_update_allowed"])
        with self.assertRaisesRegex(ValueError,"DO_NOT_UPDATE_POSTERIOR"):
            enforce_population([doc(row(),receipt="pending")],DAY)
    def test_wrong_date_quarantine(self):
        _,rep=reconcile_population([doc(row(game_date="2026-11-16"))],DAY)
        self.assertEqual(rep["malformed_or_incomplete_count"],1)
        self.assertFalse(rep["posterior_update_allowed"])
    def test_missing_identity_quarantine(self):
        bad=row();del bad["player_id"]
        _,rep=reconcile_population([doc(bad)],DAY)
        self.assertEqual(rep["malformed_or_incomplete_count"],1)
    def test_validator_failure_quarantine(self):
        def validate(r):
            if r["workload"]<1:raise ValueError("invalid_workload")
        _,rep=reconcile_population([doc(row(workload=0))],DAY,validator=validate)
        self.assertEqual(rep["malformed_or_incomplete_count"],1)
    def test_no_collapsing_alternate_stats(self):
        a,rep=reconcile_population([doc(row(),row(stat="completions",value=21))],DAY)
        self.assertEqual(len(a),2)
    def test_multiple_players_stay_distinct(self):
        a,rep=reconcile_population([doc(row(),row(player_id="different"))],DAY)
        self.assertEqual(len(a),2)
    def test_quarantine_receipt_append_only_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            records=[doc(row(),row(value=31))]
            with self.assertRaisesRegex(ValueError,"CONFLICTING_DUPLICATE"):
                enforce_population(records,DAY,quarantine_dir=temp)
            stored=list(pathlib.Path(temp).glob("*.json"))
            self.assertEqual(len(stored),1)
            contents=stored[0].read_bytes()
            with self.assertRaisesRegex(ValueError,"CONFLICTING_DUPLICATE"):
                enforce_population(records,DAY,quarantine_dir=temp)
            self.assertEqual(contents,stored[0].read_bytes())
            self.assertEqual(json.loads(contents)["posterior_update_allowed"],False)
            with self.assertRaisesRegex(ValueError,"CONFLICTING_DUPLICATE"):
                enforce_population([doc(row(),row(value=99))],DAY,quarantine_dir=temp)
            self.assertEqual(len(list(pathlib.Path(temp).glob("*.json"))),2)
    def test_collision_report_reproducible(self):
        r=[doc(row(),row(value=31))]
        _,a=reconcile_population(r,DAY)
        _,b=reconcile_population(r,DAY)
        self.assertEqual(a,b)
        self.assertEqual(a["report_sha256"],digest({k:v for k,v in a.items() if k!="report_sha256"}))
    def test_finite_canonical_values(self):
        with self.assertRaises(ValueError):
            canonical({"value":float("nan")})

if __name__=="__main__":unittest.main()
