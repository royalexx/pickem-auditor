"""Regression tests for immutable NHL saves posterior forecast settlement."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nhl_saves_shadow_settle as sh

NOW=datetime(2026,11,3,15,0,tzinfo=timezone.utc)


def records():
    common=dict(game_date="2026-11-02",sport="NHL",player="Goalie Example",
                player_id="913",stat="goalie saves",side="over",
                reference_line=24.5,forecast_at="2026-11-02T17:00:00Z",
                event_start="2026-11-03T00:00:00Z",run_id="afternoon-1")
    forecast={**common,"status":"forecast",
              "version":"nhl-full-saves-posterior-shadow-v1",
              "model_source_digest":"a"*64,
              "q_win":.71,"q_under":.29,"q_over":.71,"q_push":0}
    snapshot={**common,"outcome":"win","actual_stat":28,
              "settled_at":"2026-11-03T12:00:00Z"}
    return forecast,snapshot


class SavesSettlementTests(unittest.TestCase):
    def test_settlement_is_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            forecasts=root/"saves";forecasts.mkdir()
            output=root/"settled";source=root/"snapshots.jsonl"
            forecast,snapshot=records()
            (forecasts/"2026-11-02.jsonl").write_text(json.dumps(forecast)+"\n")
            source.write_text(json.dumps(snapshot)+"\n")
            first=sh.settle(source,forecasts,output,now=NOW)
            self.assertEqual(first["new_settlements"],1)
            receipt=output/"2026-11-02.jsonl"
            frozen=receipt.read_bytes()
            self.assertEqual(json.loads(frozen)["outcome"],"win")
            rerun=sh.settle(source,forecasts,output,now=NOW)
            self.assertEqual(rerun["new_settlements"],0)
            self.assertEqual(rerun["existing_settlements"],1)
            self.assertEqual(receipt.read_bytes(),frozen)
            snapshot["actual_stat"]=20
            snapshot["outcome"]="loss"
            source.write_text(json.dumps(snapshot)+"\n")
            with self.assertRaisesRegex(sh.SettlementConflict,
                                        "IMMUTABLE_SAVES_SETTLEMENT_CONFLICT"):
                sh.settle(source,forecasts,output,now=NOW)
            self.assertEqual(receipt.read_bytes(),frozen)

    def test_missing_actual_and_invalid_clocks_never_create_settlement(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); forecasts=root/"saves";forecasts.mkdir()
            output=root/"settled";source=root/"snapshots.jsonl"
            forecast,snapshot=records()
            (forecasts/"2026-11-02.jsonl").write_text(json.dumps(forecast)+"\n")
            snapshot.update(actual_stat=None,outcome=None)
            source.write_text(json.dumps(snapshot)+"\n")
            r=sh.settle(source,forecasts,output,now=NOW)
            self.assertEqual(r["new_settlements"],0)
            self.assertFalse((output/"2026-11-02.jsonl").exists())
            snapshot.update(actual_stat=28,outcome="win",
                            settled_at="2026-11-02T19:00:00Z")
            source.write_text(json.dumps(snapshot)+"\n")
            with self.assertRaisesRegex(sh.SettlementConflict,
                                        "INVALID_SOURCE_OR_SETTLEMENT_CLOCK"):
                sh.settle(source,forecasts,output,now=NOW)


if __name__=="__main__":
    unittest.main()
