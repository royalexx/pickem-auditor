import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibration_models import shadow as s
from calibration_models.score import compare
from calibration_models import native_ws1


def fixture():
    row = {"contract_id": "c1", "sport": "NFL", "event_id": "g1", "player_id": "p1",
           "stat_key": "receptions", "period": "full_game_including_overtime", "line": 4.5,
           "book": "test_book", "product_type": "sportsbook_two_sided", "settlement_policy": "DNP_void_push_refund",
           "stat_support": "integer", "game_date": s.DAY,
           "event_start_at": "2026-11-15T18:00:00Z", "forecast_at": "2026-11-14T21:00:00Z",
           "input_freeze_at": "2026-11-14T20:00:00Z", "model_training_cutoff_at": "2026-11-13T20:00:00Z",
           "source_available_at": "2026-11-14T19:00:00Z", "source_conflict": False,
           "source_sha256": ["features"], "production_policy": s.POLICY,
           "production": {"over": .7, "under": .3, "push": 0.0}}
    quote = {k: row[k] for k in s.IDENTITY}
    quote.update(original=True, quote_id="q1", event_start_at=row["event_start_at"], observed_at="2026-11-14T19:30:00Z",
                 available_at="2026-11-14T19:29:00Z", over_odds=-120, under_odds=100)
    files = {"features": {"synthetic_test_only": True}, "quotes": {"quotes": [copy.deepcopy(quote)]}}
    row["quote"] = dict(quote, source_sha256="quotes")
    return {"input_freeze_at": "2026-11-14T22:00:00Z"}, files, row


def build(row=None, files=None, now="2026-11-14T23:00:00Z", history=None):
    manifest, originals, sample = fixture()
    return s.build(manifest, originals if files is None else files,
                   [sample if row is None else row], history or [], now=now)


def historical():
    _, files, base = fixture()
    rows = []
    for day in range(40):
        start = datetime(2026, 1, 1, 18, tzinfo=timezone.utc) + timedelta(days=day)
        for j in range(20):
            row = copy.deepcopy(base)
            row.update(contract_id=f"{day}-{j}", event_id=f"game{day}", player_id=f"p{j}",
                       event_start_at=start.isoformat(), game_date=start.date().isoformat(),
                       forecast_at=(start-timedelta(hours=1)).isoformat(),
                       input_freeze_at=(start-timedelta(hours=2)).isoformat(),
                       model_training_cutoff_at=(start-timedelta(days=1)).isoformat(),
                       source_available_at=(start-timedelta(hours=3)).isoformat(),
                       settled_at=(start+timedelta(hours=4)).isoformat(),
                       out_of_fold=True, source_certified=True,
                       outcome="over" if j % 2 else "under")
            row["production"] = {"over": .4 + .02*j, "under": .6-.02*j, "push": 0.0}
            quote = row["quote"]
            quote.update({k: row[k] for k in s.IDENTITY})
            quote.update(event_start_at=row["event_start_at"], observed_at=(start-timedelta(hours=3)).isoformat(),
                         available_at=(start-timedelta(hours=4)).isoformat())
            raw = {k: v for k, v in quote.items() if k != "source_sha256"}
            files["quotes"]["quotes"].append(raw)
            rows.append(row)
    return files, rows


class ForecastTests(unittest.TestCase):
    def test_all_candidates_have_explicit_status(self):
        out = build()
        self.assertEqual(len(out["forecasts"]), 9)
        self.assertEqual({r["candidate"] for r in out["forecasts"] if r["status"] == "abstain"}, {"C5", "C6"})
        self.assertFalse(out["production_modified"])
        self.assertFalse(out["promotion_allowed"])

    def test_identity_exact_and_no_input_mutation(self):
        _, files, row = fixture()
        original = copy.deepcopy(row)
        out = build(row, files)
        self.assertEqual(out["forecasts"][0]["unconditional"], row["production"])
        self.assertEqual(row, original)

    def test_market_devig_and_both_sides(self):
        out = build()
        market = out["forecasts"][1]
        expected = (120/220)/((120/220)+.5)
        self.assertAlmostEqual(market["conditional_no_push"]["over"], expected)
        self.assertIsNone(market["unconditional"])
        for row in out["forecasts"]:
            if row["status"] == "forecast":
                self.assertAlmostEqual(sum(row["conditional_no_push"].values()), 1)

    def test_integer_push_retained(self):
        _, files, row = fixture()
        row["line"] = 4
        row["quote"]["line"] = 4
        files["quotes"]["quotes"][0]["line"] = 4
        row["production"] = {"over": .6, "under": .3, "push": .1}
        out = build(row, files)
        for result in out["forecasts"]:
            if result.get("unconditional"):
                self.assertEqual(result["unconditional"]["push"], .1)
                self.assertAlmostEqual(sum(result["unconditional"].values()), 1)

    def test_fixed_scenarios_and_bounded_C7(self):
        for p in (0, .1, .5, .8, 1):
            for market in (0, .1, .5, .8, 1):
                out = s.probabilities(p, market, {})
                self.assertAlmostEqual(out["C4"], .5+.75*(p-.5))
                self.assertLessEqual(abs(out["C7"]-.5), abs(p-.5)+1e-12)
                self.assertGreaterEqual(abs(out["C7"]-.5)+1e-12, .75*abs(p-.5))
                if abs(p-market) <= .15:
                    self.assertAlmostEqual(out["C7"], p)
                mirror = s.probabilities(1-p, 1-market, {})
                for name in out:
                    self.assertAlmostEqual(out[name], 1-mirror[name], places=7)

    def test_target_outcomes_are_never_used(self):
        _, files, row = fixture()
        original = build(row, files)
        row.update(outcome="under", actual_stat=999, settled_at="2099-01-01T00:00:00Z")
        self.assertEqual(original, build(row, files))

    def test_started_game_abstains_every_candidate(self):
        out = build(now="2026-11-15T18:00:00Z")
        self.assertTrue(all(r["reason"] == "started_game" for r in out["forecasts"]))

    def test_duplicate_poisoned_all_copies(self):
        manifest, files, row = fixture()
        out = s.build(manifest, files, [row, copy.deepcopy(row)], [], now="2026-11-14T23:00:00Z")
        self.assertEqual(len(out["forecasts"]), 18)
        self.assertTrue(all(r["status"] == "abstain" for r in out["forecasts"]))

    def test_adversarial_fail_closed(self):
        mutations = [lambda r: r.update(source_conflict=True),
                     lambda r: r.update(source_sha256=["absent"]),
                     lambda r: r.update(event_id=None),
                     lambda r: r.update(line=float("nan")),
                     lambda r: r.update(forecast_at="2026-11-15T18:00:00Z"),
                     lambda r: r.update(input_freeze_at="2026-11-14T20:00:00"),
                     lambda r: r.update(model_training_cutoff_at="2026-11-15T20:00:00Z"),
                     lambda r: r.update(source_available_at="2026-11-15T20:00:00Z"),
                     lambda r: r.update(market_probability={"over": .5, "under": .49}),
                     lambda r: r.update(market_probability={"over": .4, "under": .6}),
                     lambda r: r.update(production={"over": .6, "under": .5, "push": 0}),
                     lambda r: r.update(production={"over": .6, "under": .3, "push": .1}),
                     lambda r: r.update(production_policy="70/30"),
                     lambda r: r.update(quote=None)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                _, files, row = fixture()
                mutate(row)
                out = build(row, files)
                self.assertEqual(next(r for r in out["forecasts"] if r["candidate"] == "C3")["status"], "abstain")

    def test_bad_prices_and_source_quote_tampering(self):
        for field, value in (("over_odds", 0), ("over_odds", True), ("over_odds", float("inf")),
                             ("under_odds", 99), ("player_id", "other"), ("original", False),
                             ("observed_at", "2026-11-15T20:00:00Z")):
            _, files, row = fixture()
            row["quote"][field] = value
            out = build(row, files)
            self.assertEqual(out["forecasts"][1]["status"], "abstain")
            self.assertEqual(out["forecasts"][0]["status"], "forecast")

    def test_market_only_survives_missing_production_and_model_only_survives_missing_market(self):
        _, files, row = fixture()
        row["production"] = None
        out = build(row, files)
        self.assertEqual(out["forecasts"][0]["status"], "abstain")
        self.assertEqual(out["forecasts"][1]["status"], "forecast")
        _, files, row = fixture()
        row["quote"] = None
        out = build(row, files)
        self.assertEqual(out["forecasts"][0]["status"], "forecast")
        self.assertEqual(out["forecasts"][1]["status"], "abstain")
        self.assertEqual(out["forecasts"][3]["status"], "forecast")

    def test_model_id_changes_with_configuration_or_code(self):
        before = build()["registry"]["C4"]["model_id"]
        with patch.dict(s.CONFIG, C4={"alpha": .8}):
            self.assertNotEqual(before, build()["registry"]["C4"]["model_id"])
        with patch.object(s, "source_hashes", return_value={"fake": "changed"}):
            self.assertNotEqual(before, build()["registry"]["C4"]["model_id"])


class TrainingTests(unittest.TestCase):
    def test_legitimate_chronological_engineering_fit(self):
        files, rows = historical()
        params, receipt = s.learned(rows, files=files, freeze=s.timestamp("2026-11-14T22:00:00Z"))
        self.assertEqual(set(params), {"C5", "C6"})
        self.assertEqual(receipt["split"]["train_n"], 400)
        self.assertEqual(receipt["split"]["holdout_n"], 400)
        self.assertFalse(receipt["refit_on_holdout"])

    def test_holdout_labels_do_not_change_fit(self):
        files, rows = historical()
        freeze = s.timestamp("2026-11-14T22:00:00Z")
        params, receipt = s.learned(rows, files=files, freeze=freeze)
        for row in rows[400:]:
            row["outcome"] = "under" if row["outcome"] == "over" else "over"
        changed, other = s.learned(rows, files=files, freeze=freeze)
        self.assertEqual(params, changed)
        self.assertNotEqual(receipt["historical_holdout"]["metrics"], other["historical_holdout"]["metrics"])

    def test_target_training_rejected_before_fitter(self):
        _, files, row = fixture()
        row.update(outcome="over", out_of_fold=True, source_certified=True,
                   settled_at="2026-11-15T23:00:00Z")
        with patch.object(s.calibration, "fit_beta", side_effect=AssertionError("must not fit")):
            params, receipt = s.learned([row], files=files, freeze=s.timestamp("2026-11-16T00:00:00Z"))
        self.assertEqual(params, {})
        self.assertIn("target_or_future_training_event", receipt["exclusions"])

    def test_uncertified_training_and_duplicates_block(self):
        files, rows = historical()
        freeze = s.timestamp("2026-11-14T22:00:00Z")
        for row in rows:
            row["source_certified"] = False
        self.assertEqual(s.learned(rows, files=files, freeze=freeze)[0], {})
        files, rows = historical()
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(s.learned(rows, files=files, freeze=freeze)[0], {})

    def test_delayed_historical_label_blocks_fit(self):
        files, rows = historical()
        rows[0]["settled_at"] = "2026-10-01T00:00:00Z"
        params, receipt = s.learned(rows, files=files, freeze=s.timestamp("2026-11-14T22:00:00Z"))
        self.assertEqual(params, {})
        self.assertEqual(receipt["reason"], "training_labels_not_available_before_historical_holdout_freeze")


class IOAndScoringTests(unittest.TestCase):
    def test_native_WS1_adapter_preserves_all_rejections_and_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"raw.bin").write_bytes(b"original-test-source")
            manifest = {"schema": native_ws1.SCHEMA, "date": s.DAY,
                "input_freeze_at": "2026-11-14T22:00:00Z",
                "sources": {"provider": {"archive_path": "raw.bin", "sha256": s.sha(b"original-test-source")}},
                "candidates": [{"candidate_id": "x", "source_validation_failure": "EVENT_IDENTITY_UNVERIFIABLE",
                                "source_certified": False, "forecast_eligible": False,
                                "frozen_control": {"Consensus_60_40": {"probability": None}}}],
                "source_certified_quotes": 0, "forecast_eligible_contracts": 0}
            raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            path = root/(s.sha(raw)+".json")
            path.write_bytes(raw+b"\n")
            result = native_ws1.consume(path, s.sha(path.read_bytes()), source_root=root, now="2026-11-14T23:00:00Z")
            self.assertEqual(len(result["forecasts"]), 9)
            self.assertTrue(all(r["reason"] == "EVENT_IDENTITY_UNVERIFIABLE" for r in result["forecasts"]))
            self.assertEqual(result["original_nonnull_control_counts"], {})
            (root/"raw.bin").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "original_source_bytes_hash_mismatch"):
                native_ws1.consume(path, s.sha(path.read_bytes()), source_root=root, now="2026-11-14T23:00:00Z")

    def test_manifest_to_exclusive_forecast_cli_engineering_fixture(self):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 14, 23, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(dir=s.ROOT/"calibration_models") as folder:
            root = Path(folder)
            manifest, _, row = fixture()
            rawquote = {k: v for k, v in row["quote"].items() if k != "source_sha256"}
            entries = []
            for name, value in (("features", {"test_fixture": True}), ("quotes", {"quotes": [rawquote]})):
                raw = s.canonical(value)
                (root/(name+".json")).write_bytes(raw)
                entries.append({"path": name+".json", "sha256": s.sha(raw)})
            row["source_sha256"] = [entries[0]["sha256"]]
            row["quote"]["source_sha256"] = entries[1]["sha256"]
            raw = s.canonical([row])
            (root/"contracts.json").write_bytes(raw)
            entries.append({"path": "contracts.json", "sha256": s.sha(raw)})
            manifest.update(schema="nfl-ws1-calibration-input-v1", producer="workstream_1",
                            target_date=s.DAY, files=entries, contracts_sha256=s.sha(raw))
            path = root/"manifest.json"
            path.write_bytes(s.canonical(manifest))
            args = ["--manifest", str(path), "--manifest-sha256", s.sha(path.read_bytes()), "--out", str(root/"forecast.json")]
            with patch.object(s, "datetime", Clock), patch("builtins.print"):
                s.main(args)
                with self.assertRaises(FileExistsError):
                    s.main(args)
            result = json.loads((root/"forecast.json").read_bytes())
            self.assertEqual(result["coverage"]["C2"]["forecast_contracts"], 1)
            self.assertEqual(result["coverage"]["C5"]["forecast_contracts"], 0)
            self.assertEqual(result["input_manifest_sha256"], s.sha(path.read_bytes()))

    def test_exclusive_write_and_manifest_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"output.json"
            digest = s.write_exclusive(path, {"test": 1})
            self.assertEqual(digest, s.sha(path.read_bytes()))
            with self.assertRaises(FileExistsError):
                s.write_exclusive(path, {"test": 2})
            with self.assertRaisesRegex(ValueError, "manifest_sha256_mismatch"):
                s.load_bundle(path, "0"*64)

    def test_loader_verifies_all_manifest_sources_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"rows.json").write_text("[]")
            digest = s.sha(b"[]")
            manifest = {"schema": "nfl-ws1-calibration-input-v1", "producer": "workstream_1",
                        "target_date": s.DAY, "contracts_sha256": digest,
                        "files": [{"path": "rows.json", "sha256": digest}]}
            path = root/"manifest.json"
            path.write_bytes(s.canonical(manifest))
            self.assertEqual(s.load_bundle(path, s.sha(path.read_bytes()))[2], [])
            (root/"rows.json").write_text("[1]")
            with self.assertRaisesRegex(ValueError, "source_hash_mismatch"):
                s.load_bundle(path, s.sha(path.read_bytes()))
            manifest["files"][0]["path"] = "../escape.json"
            path.write_bytes(s.canonical(manifest))
            with self.assertRaisesRegex(ValueError, "manifest_path_escape"):
                s.load_bundle(path, s.sha(path.read_bytes()))

    def test_scoring_controls_both_sides_and_push_exclusions(self):
        out = build()
        original = out["forecasts"][0]
        settlement = {"contract_id": "c1", "event_id": "g1", "identity": original["identity"], "outcome": "over"}
        scored = compare(out, [settlement])
        self.assertEqual(scored["comparisons"]["C3"]["matched_contracts"], 1)
        metric = scored["comparisons"]["C3"]["metrics"]["C1"]
        self.assertAlmostEqual(metric["brier"], .09)
        self.assertEqual(sum(b["n"] for b in metric["reliability_under"]), 1)
        self.assertIsNone(scored["comparisons"]["C3"]["descriptive_cluster_intervals"]["date"]["C1"]["brier"]["interval_95"])
        settlement["outcome"] = "push"
        self.assertEqual(compare(out, [settlement])["comparisons"]["C3"]["matched_contracts"], 0)
        settlement["identity"] = {}
        with self.assertRaisesRegex(ValueError, "identity_conflict"):
            compare(out, [settlement])


if __name__ == "__main__":
    unittest.main()
