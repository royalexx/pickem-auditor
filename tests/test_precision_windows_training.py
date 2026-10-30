"""Offline tests for native-Windows, read-only research training workflow."""
from __future__ import annotations
import io
import json
import sys
import tarfile
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import history_warehouse_load as loader
import precision_training_driver as driver


class WindowsWarehouseLoaderTests(unittest.TestCase):
    def test_only_archived_warehouse_files_are_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/"test.tar"
            data = b'{"cursor":"2026-10-29"}'
            with tarfile.open(archive, "w") as out:
                member = tarfile.TarInfo("data/bayesian_warehouse/states/nhl_recent.json")
                member.size = len(data)
                out.addfile(member, io.BytesIO(data))
            self.assertEqual(loader.extract_verified_archive(archive, root), 1)
            self.assertEqual(json.loads((root/"data/bayesian_warehouse/states/nhl_recent.json").read_text())["cursor"],
                             "2026-10-29")

    def test_traversal_is_not_permitted(self):
        with self.assertRaises(ValueError):
            loader._member_path("data/bayesian_warehouse/../../../outside.txt")

    def test_symlink_is_not_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/"bad.tar"
            with tarfile.open(archive, "w") as out:
                member = tarfile.TarInfo("data/bayesian_warehouse/escape")
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
                out.addfile(member)
            with self.assertRaisesRegex(ValueError, "symlink"):
                loader.extract_verified_archive(archive, root)


class WindowsTrainingContractTests(unittest.TestCase):
    def _env(self, **changes):
        end = date.today() - timedelta(days=1)
        base = {
            "SPORT":"NHL", "STAT":"shots on goal", "MODE":"holdout",
            "TRAIN_FROM":"2023-10-01", "CUTOFF":"2024-03-01",
            "HOLDOUT_UNTIL":end.isoformat(), "LINE":"2.5",
            "MAX_PER_POSITION":"15"
        }
        base.update(changes)
        return base

    def test_valid_holdout_dates(self):
        v = driver.settings(self._env())
        self.assertEqual(v["mode"],"holdout")
        self.assertEqual(v["family"],"count")

    def test_no_future_cutoff(self):
        with self.assertRaisesRegex(ValueError, "future"):
            driver.settings(self._env(CUTOFF=(date.today()+timedelta(days=1)).isoformat()))

    def test_no_future_heldout_leakage(self):
        with self.assertRaisesRegex(ValueError, "leakage"):
            driver.settings(self._env(HOLDOUT_UNTIL=(date.today()+timedelta(days=1)).isoformat()))

    def test_no_integer_push_threshold_in_holdout(self):
        with self.assertRaisesRegex(ValueError, "threshold"):
            driver.settings(self._env(LINE="2"))

    def test_full_population_cohort_is_explicit(self):
        v=driver.settings(self._env(MAX_PER_POSITION="0"))
        self.assertEqual(v["max_per_position"],0)

    def test_reject_unknown_stat(self):
        with self.assertRaises(ValueError):
            driver.settings(self._env(STAT="made up counting stat"))


if __name__=="__main__":
    unittest.main()
