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

    def test_next_market_gets_separate_pinned_monitor_after_frozen_checkout(self):
        import hashlib
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/precision-full-markets.yml").read_text()
        monitor = (root / "scripts/precision_sampling_progress.py").read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(monitor)).encode() + bytes([0]) + monitor).hexdigest()
        self.assertIn(blob, workflow, "monitor digest must match exact staged source")
        self.assertEqual(workflow.count("if: env.INDEX != '0'"), 5)
        self.assertLess(workflow.index("NUTS_MONITOR_STAGED"), workflow.index(
            "      - name: Check out exact frozen code"))
        self.assertLess(workflow.index("      - name: Check out exact frozen code"),
                        workflow.index("NUTS_MONITOR_INSTALLED"))
        self.assertLess(workflow.index("NUTS_MONITOR_INSTALLED"),
                        workflow.index("      - name: Sample hierarchical NUTS model with four chains"))
        self.assertIn("git rev-parse HEAD", workflow)
        self.assertIn("FROZEN_MODEL_SOURCE_CHANGED_OUTSIDE_MONITOR", workflow)
        self.assertIn("code_sha = [string]$env:CODE_HEAD", workflow)
        self.assertIn("index = [string]$env:NEXT_INDEX", workflow)
        self.assertIn("monitor_receipt.json", workflow)
        self.assertIn("monitoring_failure_nonfatal = $true", workflow)

    def test_frozen_safe_nfl_first_router_installed_for_post_sog_only(self):
        import hashlib
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/precision-full-markets.yml").read_text()
        helper = (root / "scripts/precision_campaign_route.py").read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(helper)).encode() + bytes([0]) + helper).hexdigest()
        self.assertEqual(workflow.count(sha), 2)
        self.assertIn("NFL_ROUTE_STAGED", workflow)
        self.assertLess(workflow.index("NFL_ROUTE_STAGED"),
                        workflow.index("      - name: Check out exact frozen code"))
        self.assertLess(workflow.index("      - name: Check out exact frozen code"),
                        workflow.index("NFL_ROUTE_INSTALL_DIGEST_MISMATCH"))
        self.assertIn("if ($env:INDEX -eq '0')", workflow)
        self.assertIn("python scripts/precision_campaign_catalog.py", workflow)
        self.assertIn("python $router --index $env:INDEX", workflow)
        self.assertIn("routing_receipt.json", workflow)
        self.assertIn("NEXT_INDEX", workflow)

    def test_frozen_posterior_safety_is_checksum_pinned_before_sampling(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        workflow=(root/".github/workflows/precision-full-markets.yml").read_text()
        src=(root/"scripts/precision_posterior_safety_patch.py").read_bytes()
        digest=hashlib.sha1(b"blob "+str(len(src)).encode()+bytes([0])+src).hexdigest()
        self.assertEqual(workflow.count(digest),2)
        self.assertIn("POSTERIOR_SAFETY_STAGED",workflow)
        self.assertIn("POSTERIOR_SAFETY_INSTALLED",workflow)
        self.assertIn("posterior_safety_receipt.json",workflow)
        self.assertLess(workflow.index("POSTERIOR_SAFETY_STAGED"),
                        workflow.index("      - name: Check out exact frozen code"))
        self.assertLess(workflow.index("      - name: Check out exact frozen code"),
                        workflow.index("POSTERIOR_SAFETY_INSTALLED"))
        self.assertLess(workflow.index("POSTERIOR_SAFETY_INSTALLED"),
                        workflow.index("      - name: Sample hierarchical NUTS model with four chains"))
        self.assertIn("FROZEN_SOURCE_CHANGED_OUTSIDE_APPROVED_OUTPUT_OVERLAYS",workflow)
        self.assertIn("PICKEM_STRICT_ALL_EFFECTS: '1'",workflow)
        self.assertIn("if: success()",workflow)
        self.assertNotIn("automatically_retry_failed_training",workflow)

    def test_two_chain_report_is_advisory_not_convergence_gate(self):
        root = Path(__file__).resolve().parents[1]
        module = (root / "scripts/precision_sampling_progress.py").read_text()
        workflow = (root / ".github/workflows/precision-full-markets.yml").read_text()
        self.assertIn("nuts_two_chain_preview_v1", module)
        self.assertIn("NUTS_PAIR_PREVIEW ", module)
        self.assertIn('self.preview_file = self.output.parent / "two_chain_preview.json"', module)
        self.assertIn('"all_four_chains_required": True', module)
        self.assertIn('"model_converged": None', module)
        self.assertIn('"advisory_only": True', module)
        self.assertIn('self.preview_thread = threading.Thread(', module)
        self.assertNotIn("NUTS_PAIR_PREVIEW", workflow,
                         "preliminary diagnostics must not drive workflow gating")
        self.assertIn("if: success()", workflow)

    def test_monitored_successor_does_not_change_sampling_or_restart_behavior(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/precision-full-markets.yml").read_text()
        module = (root / "scripts/precision_sampling_progress.py").read_text()
        self.assertIn("PICKEM_NUTS_CHAINS: '4'", workflow)
        self.assertIn("PICKEM_NUTS_DRAWS: '2000'", workflow)
        self.assertIn("PICKEM_NUTS_TUNE: '1800'", workflow)
        self.assertIn("PICKEM_STRICT_ALL_EFFECTS: '1'", workflow)
        self.assertIn("timeout-minutes: 7200", workflow)
        self.assertIn("sampling continues; telemetry disabled", module)
        self.assertIn("except Exception as exc:", module)
        self.assertNotIn("sys.exit(", module)
        self.assertNotIn("raise SystemExit", module)

    def test_history_cache_miss_does_not_abort_pinned_source_fallback(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/precision-full-markets.yml").read_text()
        start = workflow.index("      - name: Restore verified frozen history cache if available")
        finish = workflow.index("      - name: Retrieve frozen population history from private GitHub")
        code = workflow[start:finish]
        # Native process exit 3 is an expected cache miss. Windows Actions
        # PowerShell would otherwise propagate the last failed native exit.
        self.assertIn("elseif ($code -eq 3)", code)
        self.assertIn("FROZEN_HISTORY_CACHE_MISS: retrieving immutable source commit'\n            exit 0", code)
        self.assertIn("FROZEN_HISTORY_CACHE_HIT: immutable warehouse restored from verified archive'\n            exit 0", code)
        self.assertIn("if: env.FROZEN_HISTORY_CACHE_HIT != '1'", workflow)
        self.assertIn("timeout-minutes: 7200", workflow)


if __name__=="__main__":
    unittest.main()
