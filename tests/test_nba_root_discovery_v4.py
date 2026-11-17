"""Regression for both NBA unittest import entrypoints; no test bodies run here."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DiscoveryCompatibilityTests(unittest.TestCase):
    def test_root_discovery_imports_all_canonical_nba_tests_once(self):
        code = '''
import json, unittest
loader=unittest.TestLoader()
suite=loader.discover('tests')
def ids(s):
    for child in s:
        if isinstance(child,unittest.TestSuite): yield from ids(child)
        else: yield child.id()
all_ids=list(ids(suite))
print(json.dumps({'errors':loader.errors,'ids':all_ids}))
'''
        r=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True,check=True)
        result=json.loads(r.stdout)
        self.assertEqual(result['errors'],[])
        self.assertEqual(len(result['ids']),len(set(result['ids'])))
        nba=[s for s in result['ids'] if s.startswith('nba_architecture.')]
        dedicated_code=code.replace("discover('tests')", "discover('tests/nba_architecture')")
        d=subprocess.run([sys.executable,'-c',dedicated_code],cwd=ROOT,capture_output=True,text=True,check=True)
        dedicated=json.loads(d.stdout)
        self.assertEqual(dedicated['errors'],[])
        self.assertGreater(len(nba),0)
        self.assertEqual(sorted(x.removeprefix('nba_architecture.') for x in nba),sorted(dedicated['ids']))

if __name__=='__main__': unittest.main()
