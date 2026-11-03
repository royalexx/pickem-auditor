"""The archive may add settlements but cannot change earlier forecasts/outcomes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import verify_forecast_history_transition as guard


def row(**updates):
    result = {"run_id":"slate-1", "forecast_at":"2026-11-01T19:00:00Z",
              "event_start":"2026-11-02T00:00:00Z","q_grade":.81,
              "player_id":"p1","game_date":"2026-11-01",
              "side":"over","reference_line":2.5}
    result.update(updates)
    return result


class DurableForecastTransition(unittest.TestCase):
    def test_stored_forecasts_and_settlements_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);old=root/"old.jsonl";new=root/"new.jsonl"
            def save(path,items):
                path.write_text("".join(json.dumps(x)+"\n" for x in items))
            original=row()
            settled=row(actual_stat=3,outcome="win",settled_at="2026-11-02T10:00:00Z")
            appended=row(player_id="p2",q_grade=.74)
            save(old,[original])
            save(new,[settled,appended])
            result=guard.verify(old,new)
            self.assertEqual(result["appended_forecasts"],1)

            # An existing forecast probability cannot be rewritten, even if
            # a settlement matches; only settlement fields can be added.
            save(new,[row(q_grade=.86,actual_stat=3,outcome="win",
                          settled_at="2026-11-02T10:00:00Z"),appended])
            with self.assertRaisesRegex(guard.ForecastHistoryConflict,
                                        "IMMUTABLE_FORECAST_HISTORY_CONFLICT"):
                guard.verify(old,new)

            save(old,[settled])
            save(new,[row(actual_stat=2,outcome="loss",
                          settled_at="2026-11-02T11:00:00Z")])
            with self.assertRaisesRegex(guard.ForecastHistoryConflict,
                                        "IMMUTABLE_SETTLEMENT_HISTORY_CONFLICT"):
                guard.verify(old,new)

    def test_missing_history_or_corrupt_json_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);old=root/"old.jsonl";new=root/"new.jsonl"
            old.write_text(json.dumps(row())+"\n")
            new.write_text("")
            with self.assertRaisesRegex(guard.ForecastHistoryConflict,"EMPTY"):
                guard.verify(old,new)
            new.write_text('{"invalid": NaN}\n')
            with self.assertRaises(guard.ForecastHistoryConflict):
                guard.verify(old,new)


if __name__ == "__main__":
    unittest.main()
