"""Adversarial Phase 1 SHA/byte verification for frozen inputs and quotes."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import tempfile
import unittest

from v2.contracts import ContractError
from v2.source_bytes import verify_original_source_bytes


def digest(value):
    return hashlib.sha256(value).hexdigest()


class OriginalSourceBytesTests(unittest.TestCase):
    def fixtures(self, root):
        (root/"quotes").mkdir()
        (root/"features").mkdir()
        quote=b'{"book":"OriginalBook","line":4.5}'
        source=b'{"source":"original-preweek-stats"}'
        (root/"quotes/q.json").write_bytes(quote)
        (root/"features/history.json").write_bytes(source)
        q=SimpleNamespace(quote_archive_path="quotes/q.json",quote_receipt_sha256=digest(quote))
        f=SimpleNamespace(sources=(SimpleNamespace(archive_path="features/history.json",
                                                  content_sha256=digest(source)),))
        return q,f

    def test_original_frozen_bytes_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            result=verify_original_source_bytes([q],[f],root)
            self.assertEqual(result["quote_files_checked"],1)
            self.assertEqual(result["forecast_source_files_checked"],1)
            self.assertEqual(result["status"],"original_bytes_verified_no_market_certification")

    def test_tampered_original_quote_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            (root/"quotes/q.json").write_bytes(b'{"book":"MadeUpBook"}')
            with self.assertRaisesRegex(ContractError,"original_source_bytes_digest_mismatch"):
                verify_original_source_bytes([q],[f],root)

    def test_tampered_original_feature_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            (root/"features/history.json").write_text("MUTATED")
            with self.assertRaisesRegex(ContractError,"original_source_bytes_digest_mismatch"):
                verify_original_source_bytes([q],[f],root)

    def test_missing_quote_bytes_cannot_be_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            q.quote_archive_path=None
            with self.assertRaisesRegex(ContractError,"original_archive_path_missing"):
                verify_original_source_bytes([q],[f],root)

    def test_escape_and_symlink_attack_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            q.quote_archive_path="../outside.json"
            with self.assertRaisesRegex(ContractError,"original_archive_path_unsafe"):
                verify_original_source_bytes([q],[f],root)
            q.quote_archive_path="quotes/alias.json"
            outside=root.parent/"external_source_data.json"
            # Do not create outside temporary fixtures unnecessarily.
            (root/"quotes/alias.json").symlink_to(root/"features/history.json")
            with self.assertRaisesRegex(ContractError,"original_source_bytes_digest_mismatch"):
                verify_original_source_bytes([q],[f],root)

    def test_no_silent_coverage_loss(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q,f=self.fixtures(root)
            f.sources=(f.sources[0],SimpleNamespace(
                archive_path="features/not_archived.json", content_sha256="0"*64))
            with self.assertRaisesRegex(ContractError,"original_source_bytes_unavailable"):
                verify_original_source_bytes([q],[f],root)


if __name__=="__main__":
    unittest.main()
