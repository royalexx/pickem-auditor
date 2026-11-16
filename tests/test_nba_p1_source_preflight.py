"""Synthetic filesystem tests only; not original NBA source certification."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.nba_p1_source_preflight import preflight

STATS = ("assists", "blocks", "pa", "points", "pr", "pra", "ra", "rebounds", "steals", "threes", "turnovers")


def fixture(root):
    entries = []
    for stat in STATS:
        for year in range(2019, 2028):
            path = f"data/bayesian_warehouse/populations/nba/{stat}/{year}.jsonl.gz"
            raw = (stat + str(year)).encode()
            file = root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
            entries.append({"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return {"schema": "nba-ws1-coverage-audit/1", "source_manifest": entries}


class PreflightTests(unittest.TestCase):
    def test_all_99_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = preflight(fixture(root), root)
            self.assertEqual(report["status"], "SOURCE_BYTES_VERIFIED")
            self.assertEqual(report["counts"]["VERIFIED_SHA256"], 99)
            self.assertFalse(report["pregame_original_capture_certified"])

    def test_tampered_byte_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            (root / manifest["source_manifest"][0]["path"]).write_bytes(b"tampered")
            result = preflight(manifest, root)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["counts"]["HASH_OR_SIZE_MISMATCH"], 1)

    def test_missing_file_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            (root / manifest["source_manifest"][0]["path"]).unlink()
            result = preflight(manifest, root)
            self.assertEqual(result["counts"]["MISSING"], 1)

    def test_dropped_category_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["source_manifest"] = manifest["source_manifest"][:-1]
            self.assertEqual(len(preflight(manifest, root)["missing_stat_seasons"]), 1)

    def test_duplicate_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["source_manifest"].append(manifest["source_manifest"][0].copy())
            with self.assertRaisesRegex(ValueError, "DUPLICATE_SHARD_PATH"):
                preflight(manifest, root)

    def test_path_traversal_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["source_manifest"][0]["path"] = "../../private.json"
            with self.assertRaisesRegex(ValueError, "UNSAFE_OR_UNEXPECTED_SHARD_PATH"):
                preflight(manifest, root)

    def test_fake_sha_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["source_manifest"][0]["sha256"] = "0" * 64
            self.assertEqual(preflight(manifest, root)["counts"]["HASH_OR_SIZE_MISMATCH"], 1)

    def test_invalid_schema_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["schema"] = "not-coverage"
            with self.assertRaisesRegex(ValueError, "INVALID_WS1_COVERAGE_SCHEMA"):
                preflight(manifest, root)

    def test_unknown_stat_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            manifest["source_manifest"][0]["path"] = "data/bayesian_warehouse/populations/nba/fake/2019.jsonl.gz"
            with self.assertRaisesRegex(ValueError, "UNSAFE_OR_UNEXPECTED_SHARD_PATH"):
                preflight(manifest, root)


if __name__ == "__main__":
    unittest.main()
