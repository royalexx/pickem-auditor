"""Native fixed-NB2 next-date source gate and anti-retrocast tests.

These fixtures do not impersonate a live original offer, forecast or HMAC
receipt. The real signed-source and quote checks are exercised separately
against original bytes by the scheduled deepnote read-only preflight.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from v2.contracts import MarketQuote
from v2.nhl_sog_nb2_source_native import (
    SCHEMA, EXPERIMENT, SHAPE, EXPERIMENT_BASELINE,
    NativeNB2Blocked, _within, _append_once, _read,
    frozen_native_nb2, run_day, _original_raw_market,
    _canonical, _sha,
)


class NativeNB2SourceTests(unittest.TestCase):
    def test_empty_original_source_abstains_without_forecast(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            now = datetime(2026, 11, 14, 21, tzinfo=timezone.utc)
            r = run_day(root, now=now, code_sha="1" * 40)
            self.assertEqual(r["status"], "NO_ORIGINAL_GAMMA_GENERATOR_YET")
            self.assertEqual(r["native_frozen_count"], 0)
            self.assertTrue((root / r["audit_path"]).is_file())
            self.assertEqual(_sha((root / r["audit_path"]).read_bytes()), r["audit_sha256"])

    def test_existing_audit_cannot_be_mutated(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audit.json"
            digest = _append_once(p, {"status": "ABSTAIN"})
            self.assertEqual(digest, _append_once(p, {"status": "ABSTAIN"}))
            with self.assertRaisesRegex(NativeNB2Blocked, "APPEND_ONLY_RECORD_MUTATION"):
                _append_once(p, {"status": "FROZEN"})

    def test_injected_source_path_escapes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(NativeNB2Blocked, "UNSAFE_PATH"):
                _within(root, "../private")
            with self.assertRaisesRegex(NativeNB2Blocked, "PATH_OUTSIDE_PROJECT"):
                _within(root, "/etc/passwd")
            with self.assertRaisesRegex(NativeNB2Blocked, "ORIGINAL_ARTIFACT_MISSING"):
                _read(root, "no_source.json")

    def _original(self, now):
        event = (now + timedelta(hours=3)).isoformat()
        return MarketQuote(
            quote_id="genuine-original-fixture", contract_id="fixture-contract",
            event_id="p-100", event_start_at=event, sport="NHL", league="NHL",
            season=2026, team_id="TOR", opponent_id="MTL", player_id="8470000",
            stat_key="shots on goal", period="full", line=2.5, book="pinnacle",
            product_type="sportsbook_two_sided", quote_at=(now-timedelta(minutes=15)).isoformat(),
            quote_receipt_sha256="a" * 64, quote_archive_path="original.jsonl",
            settlement_policy="strict_gt_lt_equal_push", quote_kind="real",
            over_decimal_odds=1.9, under_decimal_odds=1.9)

    def test_fixed_shape_same_plugin_poisson_mean_not_old_phase1(self):
        now = datetime(2026, 11, 14, 21, tzinfo=timezone.utc)
        q = self._original(now)
        evidence = {
            "quote": q, "official_event_id": "2026020311",
            "plugin_mu": 2.4, "poisson_control": {"over": .5, "under": .5, "push": 0.0},
            "original_input_digest": "1"*64, "snapshot_digest": "2"*64,
            "model_digest": "3"*64, "original_wrapper_digest": "4"*64,
            "provider_http_body_digest": "5"*64,
            "signed_historical_observation_count": 220}
        v = frozen_native_nb2(evidence, now=now, code_sha="a"*40)
        self.assertEqual(v["experiment_id"], EXPERIMENT)
        self.assertEqual(v["schema"], SCHEMA)
        self.assertEqual(v["native_nb2"]["mean"], 2.4)
        self.assertEqual(v["native_nb2"]["shape"], SHAPE)
        self.assertEqual(v["baseline_contract"], EXPERIMENT_BASELINE)
        self.assertFalse(v["original_p15_nb2_experiment_replayed"])
        self.assertFalse(v["production_selection_allowed"])
        self.assertFalse(v["tier_publication_allowed"])
        self.assertFalse(v["model_promotion_allowed"])
        self.assertTrue(v["conditioned_on_played"])
        self.assertFalse(v["dnp_risk_modeled"])

    def test_past_event_rejected_no_retroactive_shadow(self):
        now = datetime(2026, 11, 14, 21, tzinfo=timezone.utc)
        q = self._original(now)
        evidence = {"quote": q, "plugin_mu": 3.0}
        with self.assertRaisesRegex(NativeNB2Blocked, "NATIVE_CAPTURE_AFTER_GAME_CUTOFF"):
            frozen_native_nb2(evidence, now=now+timedelta(hours=3), code_sha="a"*40)
        with self.assertRaisesRegex(NativeNB2Blocked, "NATIVE_MODEL_GIT_COMMIT_UNPINNED"):
            frozen_native_nb2(evidence, now=now, code_sha="unversioned")

    def test_original_http_offer_must_match_exact_two_sides(self):
        now = datetime(2026, 11, 14, 21, tzinfo=timezone.utc)
        quote = self._original(now)
        event = {"id": "p-100", "bookmakers": [
            {"key": "pinnacle", "markets": [{"key": "player_shots_on_goal",
                "outcomes": [
                    {"name": "Over", "player_id": "nhl:8470000",
                     "description": "Test Player", "point": 2.5, "price": -110},
                    {"name": "Under", "player_id": "nhl:8470000",
                     "description": "Test Player", "point": 2.5, "price": -110}
                ]}]}]}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = json.dumps([event]).encode()
            f = root / "original.bin";f.write_bytes(raw)
            manifest = {"original_quote":{
                "raw_body_sha256":_sha(raw), "raw_body_bytes":len(raw),
                "original_raw_file":"original.bin",
                "received_at_utc":quote.quote_at,
                "structured_rows_sha256":"a"*64}}
            inp = {"original_provider_http_body_sha256":_sha(raw),
                   "original_structured_rows_sha256":"a"*64,
                   "source_bound_original_native_nhl_player_id":"nhl:8470000",
                   "chosen_offer_identity":{"provider_player_name":"Test Player",
                       "over_odds":-110,"under_odds":-110}}
            _original_raw_market(root,manifest,inp,quote)
            event["bookmakers"][0]["markets"][0]["outcomes"][1]["price"]=-125
            changed=json.dumps([event]).encode();f.write_bytes(changed)
            manifest["original_quote"]["raw_body_sha256"]=_sha(changed)
            manifest["original_quote"]["raw_body_bytes"]=len(changed)
            inp["original_provider_http_body_sha256"]=_sha(changed)
            with self.assertRaisesRegex(NativeNB2Blocked, "ORIGINAL_TWO_SIDED_HTTP_OFFER_NOT_UNIQUE"):
                _original_raw_market(root,manifest,inp,quote)

    def test_new_original_batch_must_be_structurally_valid_before_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            now=datetime(2026,11,14,21,tzinfo=timezone.utc)
            dest=root/"reports/v25_sog_source_cert_sprint/2026-11-14/daily_original_gamma_poisson_research_20261114T210000Z"
            dest.mkdir(parents=True)
            (dest/"daily_research_generation_manifest.json").write_text(
                json.dumps({"schema":"wrong","slate_date_et":"2026-11-14"}))
            with self.assertRaisesRegex(NativeNB2Blocked,"ORIGINAL_MANIFEST_INVALID"):
                run_day(root,now=now,code_sha="a"*40)


if __name__=="__main__":
    unittest.main()
