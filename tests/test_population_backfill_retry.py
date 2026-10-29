"""HTTP truncation must retry full ESPN game responses without checkpointing partial data."""
import io
import sys
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import population_backfill as target
import population_normalizers as normalizers


class _CompleteResponse(io.BytesIO):
    status = 200


class PopulationHTTPRetryTests(unittest.TestCase):
    def test_incomplete_chunk_is_retried_before_json_is_accepted(self):
        url = normalizers.NBA_BASE + "/summary?event=401071502"
        response = _CompleteResponse(b'{"header":{"competitions":[]}}')
        with patch.object(target, "urlopen",
                          side_effect=[IncompleteRead(b'{"header":', 48), response]) as opener:
            actual = target.fetch_json(url, spacing=0.1, attempts=2, sleeper=lambda _: None)
        self.assertEqual(actual, {"header": {"competitions": []}})
        self.assertEqual(opener.call_count, 2)

    def test_exhausted_truncated_chunks_fail_with_source_receipt(self):
        url = normalizers.NBA_BASE + "/summary?event=401071502"
        with patch.object(target, "urlopen",
                          side_effect=[IncompleteRead(b"{", 48)] * 2) as opener:
            with self.assertRaisesRegex(RuntimeError, "HISTORICAL_SOURCE_UNAVAILABLE"):
                target.fetch_json(url, spacing=0.1, attempts=2, sleeper=lambda _: None)
        self.assertEqual(opener.call_count, 2)


if __name__ == "__main__":
    unittest.main()
