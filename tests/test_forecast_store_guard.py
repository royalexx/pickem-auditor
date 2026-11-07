"""Exercise forecast preservation, including a real isolated Git roundtrip."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import forecast_store_guard as guard


def forecast(player="Example Player"):
    return {"run_id": "frozen-run", "game_date": "2026-11-06", "sport": "NBA",
            "player": player, "stat": "points", "side": "over", "reference_line": 20.5,
            "forecast_at": "2026-11-06T20:00:00Z", "event_start": "2026-11-07T00:00:00Z",
            "engine_a": {"q_win": .8, "as_of": "2026-11-06"}, "q_model": .8,
            "market": {"q_market": .52, "closing_q_market": None},
            "actual_stat": None, "outcome": None, "settled_at": None,
            "closing_line": None, "closing_q_market": None}


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class ForecastStoreGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = Path(self.temp.name) / "old.jsonl"
        self.new = Path(self.temp.name) / "new.jsonl"

    def check(self, before, after):
        write_rows(self.old, before)
        write_rows(self.new, after)
        return guard.check_history(self.old, self.new)

    def test_preserves_unknown_nested_forecast_fields_and_asof(self):
        for mutate in (
            lambda r: r.update(q_model=.9),
            lambda r: r.update(reference_line=21.5),
            lambda r: r.update(forecast_at="2026-11-07T01:00:00Z"),
            lambda r: r["engine_a"].update(as_of="2026-11-07"),
            lambda r: r["market"].update(q_market=.7),
            lambda r: r.update(q_model=True),
        ):
            with self.subTest(mutation=mutate):
                row = forecast()
                changed = deepcopy(row)
                mutate(changed)
                with self.assertRaises(guard.ForecastHistoryConflict):
                    self.check([row], [changed])

    def test_rejects_deleted_and_duplicate_identities_in_either_file(self):
        row = forecast()
        for before, after in (([row, forecast("Other Player")], [row]),
                              ([row], [row, deepcopy(row)]),
                              ([row, deepcopy(row)], [row])):
            with self.subTest(before=len(before), after=len(after)):
                with self.assertRaises(guard.ForecastHistoryConflict):
                    self.check(before, after)

    def test_settlement_closing_and_append_are_allowed_without_rewriting(self):
        row = forecast()
        settled = deepcopy(row)
        settled.update(actual_stat=25, outcome="win", settled_at="2026-11-07T11:00:00Z",
                       closing_line=21.5, closing_q_market=.6)
        settled["market"]["closing_q_market"] = .6
        result = self.check([row], [settled, forecast("Other Player")])
        self.assertEqual(result["appended_forecasts"], 1)
        for field in ("actual_stat", "outcome", "settled_at", "closing_line", "closing_q_market"):
            changed = deepcopy(settled)
            changed[field] = None
            with self.subTest(field=field), self.assertRaises(guard.ForecastHistoryConflict):
                self.check([settled], [changed])
        changed = deepcopy(settled)
        changed["market"]["closing_q_market"] = .7
        with self.assertRaises(guard.ForecastHistoryConflict):
            self.check([settled], [changed])

    def test_malformed_or_missing_identity_fails_closed(self):
        for key, value in (("run_id", ""), ("player", None), ("game_date", "bad"),
                           ("sport", "MLB"), ("side", "maybe"), ("reference_line", True)):
            row = forecast()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(guard.ForecastHistoryConflict):
                self.check([], [row])
        for text in ('{"run_id":', '[]\n', '{"run_id":"one","run_id":"two"}\n',
                     json.dumps(forecast()).replace('0.8', 'NaN'),
                     json.dumps(forecast()).replace('0.8', '1e400')):
            self.new.write_text(text, encoding="utf-8")
            with self.subTest(text=text[:25]), self.assertRaises(guard.ForecastHistoryConflict):
                guard.check_history(self.old, self.new)

    def test_initial_history_and_unchanged_reserialization(self):
        row = forecast()
        write_rows(self.new, [row])
        self.assertEqual(guard.check_history(self.old, self.new)["appended_forecasts"], 1)
        self.old.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(guard.check_history(self.old, self.new)["appended_forecasts"], 0)

    def test_existing_settlement_serializer_preserves_the_frozen_payload(self):
        import pickem_math
        import settle
        row = forecast()
        updated, changed = settle.settle_row(row, 25, settled_at="2026-11-07T11:00:00Z")
        self.assertTrue(changed)
        write_rows(self.old, [row])
        self.new.write_text(pickem_math.dump_snapshot(updated), encoding="utf-8")
        self.assertEqual(guard.check_history(self.old, self.new)["existing_forecasts"], 1)


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "requires Git and Bash")
class ForecastStoreGitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.remote = Path(self.temp.name) / "remote.git"
        self.repo = Path(self.temp.name) / "checkout"
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main", str(self.repo))
        self.git("config", "user.name", "audit", cwd=self.repo)
        self.git("config", "user.email", "audit@example.invalid", cwd=self.repo)
        (self.repo / "scripts").mkdir()
        (self.repo / "data").mkdir()
        for name in ("shadow_store.sh", "forecast_store_guard.py"):
            shutil.copy2(ROOT / "scripts" / name, self.repo / "scripts" / name)
        self.snapshot = self.repo / "data/prop_snapshots.jsonl"
        self.initial = [forecast(), forecast("Other Player")]
        write_rows(self.snapshot, self.initial)
        self.git("add", ".", cwd=self.repo)
        self.git("commit", "-qm", "frozen baseline", cwd=self.repo)
        self.git("remote", "add", "origin", str(self.remote), cwd=self.repo)
        self.git("push", "origin", "HEAD:main", "HEAD:data/shadow-calibration", cwd=self.repo)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)

    def head(self):
        return self.git("--git-dir", str(self.remote), "rev-parse",
                        "refs/heads/data/shadow-calibration").stdout.strip()

    def save(self):
        return subprocess.run(["bash", "scripts/shadow_store.sh", "save"], cwd=self.repo,
                              capture_output=True, text=True)

    def test_rejected_edits_never_change_remote_branch(self):
        mutations = {
            "delete": lambda rows: rows.pop(),
            "probability": lambda rows: rows[0].update(q_model=.2),
            "line": lambda rows: rows[0].update(reference_line=30.5),
            "as_of": lambda rows: rows[0]["engine_a"].update(as_of="2026-11-07"),
            "duplicate": lambda rows: rows.append(deepcopy(rows[0])),
            "identity": lambda rows: rows[0].update(run_id="replacement"),
        }
        initial_head = self.head()
        for name, mutate in mutations.items():
            rows = deepcopy(self.initial)
            mutate(rows)
            write_rows(self.snapshot, rows)
            with self.subTest(name=name):
                result = self.save()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("IMMUTABLE_FORECAST_HISTORY_CONFLICT", result.stderr)
                self.assertEqual(self.head(), initial_head)
        self.snapshot.write_text('{"run_id":', encoding="utf-8")
        self.assertNotEqual(self.save().returncode, 0)
        self.assertEqual(self.head(), initial_head)

    def test_valid_settlement_and_appended_forecast_persist_exactly(self):
        rows = deepcopy(self.initial)
        rows[0].update(actual_stat=25, outcome="win", settled_at="2026-11-07T11:00:00Z")
        rows.append(forecast("Third Player"))
        write_rows(self.snapshot, rows)
        expected = self.snapshot.read_bytes()
        result = self.save()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = self.git("--git-dir", str(self.remote), "show",
                          "refs/heads/data/shadow-calibration:data/prop_snapshots.jsonl").stdout.encode()
        self.assertEqual(actual, expected)
        rows[0]["actual_stat"] = 26
        write_rows(self.snapshot, rows)
        saved_head = self.head()
        self.assertNotEqual(self.save().returncode, 0)
        self.assertEqual(self.head(), saved_head)

    def test_new_validation_sidecars_persist_then_reject_rewrite(self):
        folders=('nhl_joint_saves_shadow','population_nuts_shadow','model_comparisons')
        for folder in folders:
            p=self.repo/'data'/folder/'2026-11-06.jsonl';p.parent.mkdir()
            write_rows(p,[{'run_id':'frozen-run','q_win':.7}])
        result=self.save()
        self.assertEqual(result.returncode,0,result.stderr)
        head=self.head()
        for folder in folders:
            saved=self.git('--git-dir',str(self.remote),'show',
                'refs/heads/data/shadow-calibration:data/'+folder+'/2026-11-06.jsonl').stdout
            self.assertEqual(json.loads(saved)['q_win'],.7)
        path=self.repo/'data/model_comparisons/2026-11-06.jsonl'
        write_rows(path,[{'run_id':'frozen-run','q_win':.9}])
        rejected=self.save()
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('IMMUTABLE_VALIDATION_SIDECAR_CONFLICT',rejected.stderr)
        self.assertEqual(self.head(),head)


if __name__ == "__main__":
    unittest.main()
