"""Shadow-store shell must resolve Python 3 without a bare ``python`` alias."""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/shadow_store.sh"


@unittest.skipUnless(shutil.which("bash"), "requires Bash")
class ShadowStorePythonTests(unittest.TestCase):
    def test_bash_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_resolve_python_prefers_explicit_bin(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("resolve_python", source)
        self.assertIn("PYTHON_BIN", source)
        env = os.environ.copy()
        env["PYTHON_BIN"] = sys.executable
        # Missing mode must fail with usage, not missing-interpreter.
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("PYTHON_INTERPRETER_UNAVAILABLE", result.stderr)
        self.assertIn("use load or save", result.stderr)

    def test_invalid_python_bin_exits_127(self):
        env = os.environ.copy()
        env["PYTHON_BIN"] = "/nonexistent/python-bin-for-test"
        result = subprocess.run(
            ["bash", str(SCRIPT), "load"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 127)
        self.assertIn("PYTHON_BIN_UNAVAILABLE", result.stderr)


if __name__ == "__main__":
    unittest.main()
