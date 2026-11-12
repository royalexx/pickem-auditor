"""Boundary test for preserving Phase 0R full-slate source input bytes.

The producer must not discard valid NFL/NBA/NHL frozen source receipts at the
old 70 MB cap. Actual compressed GitHub chunk size remains independently gated.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_pool_exchange as pool


class SourceArchiveGuardTests(unittest.TestCase):
    def test_valid_three_sport_source_archive_is_not_dropped(self):
        self.assertEqual(pool.MAX_SOURCE_ARCHIVE_BYTES, 256_000_000)
        for size in (0, 1, 70_000_001, 128_000_000, 256_000_000):
            with self.subTest(size=size):
                self.assertIsNone(pool.check_source_archive_size(size))

    def test_bound_is_fail_closed(self):
        for size in (-1, 256_000_001, 999_000_000, 1.5, None, True):
            with self.subTest(size=size):
                with self.assertRaisesRegex(ValueError, "original_forecast_source_archive_too_large"):
                    pool.check_source_archive_size(size)

    def test_small_override_can_enforce_byte_budget_without_large_fixture(self):
        with patch.object(pool, "MAX_SOURCE_ARCHIVE_BYTES", 16):
            pool.check_source_archive_size(16)
            with self.assertRaises(ValueError):
                pool.check_source_archive_size(17)


if __name__ == "__main__":
    unittest.main()
