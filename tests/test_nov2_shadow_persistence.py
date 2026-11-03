"""End-to-end persistence contract, executed in disposable local git repositories.

No network, source fetch, bookmaker, model fitting or hosted Actions usage.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shadow_store.sh"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, text=True,
                          capture_output=True, check=True).stdout


class DurableShadowStore(unittest.TestCase):
    def test_load_save_retry_and_conflicting_forecasts_fail_closed(self):
        if not shutil.which("git") or not shutil.which("bash"):
            self.skipTest("local git and bash required")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote, work, clean = root / "remote.git", root / "work", root / "clean"
            remote.mkdir()
            git(remote, "init", "--bare")
            work.mkdir()
            git(work, "init", "-b", "main")
            git(work, "config", "user.name", "offline-test")
            git(work, "config", "user.email", "offline@test.invalid")
            # Byte-for-byte immutability checks need stable Git checkout bytes,
            # regardless of Git for Windows global core.autocrlf settings.
            git(work, "config", "core.autocrlf", "false")
            git(work, "remote", "add", "origin", str(remote))
            (work / "scripts").mkdir()
            shutil.copy2(SCRIPT, work / "scripts" / "shadow_store.sh")
            # Isolated saves invoke this guard when an archived history exists.
            # Bundle the real guard, not an untracked stub.
            shutil.copy2(ROOT / "scripts" / "verify_forecast_history_transition.py",
                         work / "scripts" / "verify_forecast_history_transition.py")
            snapshots = work / "data" / "prop_snapshots.jsonl"
            snapshots.parent.mkdir()
            snapshots.write_text('{"original":"forecast"}\n', newline="\n")
            saves = work / "data" / "nhl_joint_saves_shadow" / "2026-11-02.jsonl"
            saves.parent.mkdir(parents=True)
            first = '{"id":"first","q_win":0.8}\n'
            second = '{"id":"second","q_win":0.7}\n'
            saves.write_text(first, newline="\n")
            cert = work / "config" / "probability_blend" / "NHL_saves.json"
            cert.parent.mkdir(parents=True)
            cert.write_text('{"version":"registered-v1"}\n', newline="\n")
            # Only implementation code belongs on main in this fixture.
            # Forecasts and certificates must first be saved to a *new*
            # data/shadow-calibration branch. Tracking them on main would
            # make the first save look like a no-op and never create the branch.
            git(work, "add", "scripts")
            git(work, "commit", "-m", "base")
            git(work, "push", "-u", "origin", "main")

            # The Bash helper must invoke the same Python interpreter as
            # unittest, even when Git Bash otherwise finds Windows Store Python.
            env = dict(os.environ)
            env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
            def save():
                return subprocess.run(["bash", "scripts/shadow_store.sh", "save"],
                    cwd=work, env=env, text=True, capture_output=True)
            initial = save()
            self.assertEqual(initial.returncode, 0,
                f"initial save exit={initial.returncode}\nstdout:\n{initial.stdout}\nstderr:\n{initial.stderr}")
            git(work, "fetch", "origin", "data/shadow-calibration")
            archived = git(work, "show",
                "origin/data/shadow-calibration:data/nhl_joint_saves_shadow/2026-11-02.jsonl")
            self.assertEqual(archived, first)
            stored_certificate = git(work, "show",
                "origin/data/shadow-calibration:config/probability_blend/NHL_saves.json")
            self.assertEqual(stored_certificate, cert.read_text())

            saves.write_text(first + second, newline="\n")
            extension = save()
            self.assertEqual(extension.returncode, 0,
                f"append save exit={extension.returncode}\nstdout:\n{extension.stdout}\nstderr:\n{extension.stderr}")
            git(work, "fetch", "origin", "data/shadow-calibration")
            archived = git(work, "show",
                "origin/data/shadow-calibration:data/nhl_joint_saves_shadow/2026-11-02.jsonl")
            self.assertEqual(archived, first + second)

            saves.write_text(second + first, newline="\n")
            changed = save()
            self.assertNotEqual(changed.returncode, 0)
            self.assertIn("IMMUTABLE_NHL_SAVES_SHADOW_CONFLICT", changed.stderr)

            saves.write_text(first + second, newline="\n")
            cert.write_text('{"version":"unauthorized-replacement"}\n', newline="\n")
            changed_cert = save()
            self.assertNotEqual(changed_cert.returncode, 0)
            self.assertIn("IMMUTABLE_REGISTERED_CERTIFICATE_CONFLICT", changed_cert.stderr)

            # A fresh checkout restores both sidecar and registered certificate.
            git(root, "-c", "core.autocrlf=false", "clone", "--branch", "main", str(remote), str(clean))
            # Main has no forecast/certificate state; this is a real clean
            # checkout that must restore both assets from the data branch.
            self.assertFalse((clean / "data" / "nhl_joint_saves_shadow").exists())
            self.assertFalse((clean / "config" / "probability_blend").exists())
            loaded = subprocess.run(["bash", "scripts/shadow_store.sh", "load"],
                cwd=clean, env=env, text=True, capture_output=True)
            self.assertEqual(loaded.returncode, 0,
                f"fresh restore exit={loaded.returncode}\nstdout:\n{loaded.stdout}\nstderr:\n{loaded.stderr}")
            self.assertEqual(
                (clean / "data" / "nhl_joint_saves_shadow" / "2026-11-02.jsonl").read_text(),
                first + second)
            self.assertEqual(
                (clean / "config" / "probability_blend" / "NHL_saves.json").read_text(),
                '{"version":"registered-v1"}\n')


if __name__ == "__main__":
    unittest.main()
