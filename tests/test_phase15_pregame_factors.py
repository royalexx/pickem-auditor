"""Phase1.5 P1.5-07 pregame factor runtime guards and no retroactive NBA product."""
from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
import unittest

from v2.phase15_pregame_factors import make_shadow_receipt
from v2.official_nba_nhl_capture import SettlementCaptureError

CLOCK="2026-11-11T18:00:00Z"
EVENT="2026-11-12T00:00:00Z"


def data(root,sport="NHL"):
    (root/"one.json").write_text('{"captured_before_forecast":true}')
    src=root/"one.json"
    ret={"sport":sport,"stat":"shots on goal" if sport=="NHL" else "pra",
         "event_id":"pregame-event","player_id":"123","model_version":"shadow-study-001",
         "period":"full","event_start":EVENT,
         "model_training_cutoff_at":"2026-11-10T00:00:00Z",
         "source_receipts":[{"archive_path":"one.json",
                "sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
                "retrieved_at":"2026-11-11T17:00:00Z"}]}
    if sport=="NHL":
        ret["factors"]={"team_unblocked_attempts":60,
                 "probability_active":.95,"individual_share_if_active":.08,
                 "on_target_probability":.60}
        ret["factorization"]="nhl_SOG_unblocked_team_attempt_product_v1"
        ret["implied_mean"]=60*.95*.08*.60
    else:
        ret["factors"]={"projected_minutes":29,
                 "projected_team_possessions":101,
                 "player_usage_or_opportunity_rate":.21,
                 "conditional_stat_rate_per_minute":.67}
        ret["factorization"]="nba_diagnostic_nonmultiplicative_v1"
        ret["implied_mean"]=None
    return ret


class FactorReceiptTests(unittest.TestCase):
    def test_valid_future_NHL_shadow_is_sha_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root)
            a=make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)
            self.assertEqual(a["validation_receipt"]["source_count"],1)
            self.assertFalse(a["production_promotion_allowed"])
            self.assertIn("receipt_sha256",a)

    def test_NBA_combo_requires_nonmultiplicative_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root,"NBA")
            self.assertEqual(make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)["stat"],"pra")
            ret["factorization"]="nba_false_four_factor_product"
            with self.assertRaisesRegex(SettlementCaptureError,"nba_invalid"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)

    def test_stale_or_game_started_cannot_be_preforecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root);ret["event_start"]="2026-11-11T17:00:00Z"
            with self.assertRaisesRegex(SettlementCaptureError,"not_genuinely_pregame"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)

    def test_future_source_receipt_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root)
            ret["source_receipts"][0]["retrieved_at"]="2026-11-11T18:01:00Z"
            with self.assertRaisesRegex(SettlementCaptureError,"factor_future_source"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)

    def test_source_tampering_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root)
            (root/"one.json").write_text('{"tampered":true}')
            with self.assertRaisesRegex(SettlementCaptureError,"hash_mismatch"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)

    def test_nhl_mean_product_inconsistent_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root);ret["implied_mean"]=100
            with self.assertRaisesRegex(SettlementCaptureError,"product_not_coherent"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)

    def test_unavailable_factors_cannot_be_synthesized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ret=data(root);ret["factors"].pop("individual_share_if_active")
            with self.assertRaisesRegex(SettlementCaptureError,"fields_missing"):
                make_shadow_receipt(ret,source_root=root,observed_clock=CLOCK)


if __name__=="__main__":unittest.main()
