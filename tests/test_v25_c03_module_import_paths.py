"""C03 provenance modules must work in both package and scripts/ runtimes.

Uses a fresh child interpreter to avoid other tests incidentally populating
sys.path with scripts/. No network; this does not attest live ESPN feeds.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class C03PackageEntryPointTests(unittest.TestCase):
    def test_package_only_import_without_scripts_on_syspath(self):
        env=dict(os.environ, PYTHONPATH=str(ROOT))
        snippet=(
            "import sys; from pathlib import Path\n"
            "from scripts.c03_live_transport import verify_signed_capture\n"
            "from scripts.c03_pregame_live_capture import annotate_prepared_candidates\n"
            "assert callable(verify_signed_capture) and callable(annotate_prepared_candidates)\n"
            "assert not any(Path(x).resolve()==(Path.cwd()/'scripts').resolve() for x in sys.path if x)\n"
            "print('C03_PACKAGE_ENTRYPOINT_PASS')\n"
        )
        proc=subprocess.run([sys.executable,"-c",snippet],cwd=str(ROOT),
            env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stdout+"\n"+proc.stderr)
        self.assertIn("C03_PACKAGE_ENTRYPOINT_PASS",proc.stdout)

    def test_script_only_import_without_package_shortcut(self):
        env=dict(os.environ, PYTHONPATH=str(ROOT/"scripts"))
        snippet=(
            "import sys; from pathlib import Path\n"
            "import c03_live_transport as live\n"
            "import c03_pregame_live_capture as pregame\n"
            "assert callable(live.verify_signed_capture)\n"
            "assert callable(pregame.annotate_prepared_candidates)\n"
            "print('C03_SCRIPTS_ENTRYPOINT_PASS')\n"
        )
        proc=subprocess.run([sys.executable,"-c",snippet],cwd=str(ROOT/"scripts"),
            env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stdout+"\n"+proc.stderr)
        self.assertIn("C03_SCRIPTS_ENTRYPOINT_PASS",proc.stdout)

if __name__=="__main__":
    unittest.main()
