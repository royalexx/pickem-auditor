"""Reproduce accepted G0/P4, pinned P6 controls, P2/P3 interface suites.

python -m research.nba_p4_integration.checks
No upstream implementation or test is installed in an owner path.
"""
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import types
import unittest
from v2.nba_joint.integration import load_upstream, raw_sha
from research.nba_p4_integration.prepare import prepare, ROOT


def main():
    root = prepare()
    manifest=json.loads((ROOT/'docs/nba_architecture/P4_WS5_V01_REUSE_MANIFEST_20261116.json').read_text())
    baseline={}
    for path,expected in manifest['source_file_sha1_git_blobs'].items():
        actual=subprocess.check_output(['git','hash-object',path],cwd=ROOT,text=True).strip()
        if actual != expected:
            raise RuntimeError('WS5_BASELINE_CHANGED:'+path)
        baseline[path]=actual
    p2, p3 = load_upstream(root)
    sys.modules['v2.nba_o_family'] = p3
    sys.modules['v2.nba_s_family.model'] = p2
    package = types.ModuleType('v2.nba_s_family')
    for key in ('SFError','FittedS','Prediction','fit','predict','conditional_pmf','predict_conditional','exact_triplet'):
        setattr(package,key,getattr(p2,key))
    sys.modules[package.__name__] = package
    tests = types.ModuleType('tests'); tests.__path__ = [str(ROOT/'tests')]
    sys.modules['tests'] = tests
    sys.path.insert(0, str(ROOT/'tests/nba_architecture'))
    suites = [('G0_P4', ROOT/'tests/nba_architecture'),
              ('P6_CONTROLS', ROOT/'work/qa'),
              ('P3_INTERFACE', ROOT/'work/upstream/tests/nba_architecture'),
              ('P2_INTERFACE', ROOT/'work/upstream/tests/nba_s_family')]
    results=[]
    for name,folder in suites:
        loader=unittest.TestLoader()
        # Independent discovery roots avoid unittest's reused top-level directory.
        suite=loader.discover(str(folder),pattern='test_*.py',top_level_dir=str(folder))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        row={'suite':name,'tests':result.testsRun,'failures':len(result.failures),
             'errors':len(result.errors),'skips':len(result.skipped)}
        results.append(row)
        print('SUITE_RECEIPT',json.dumps(row,sort_keys=True),flush=True)
    receipt={'suites':results,'unchanged_WS5_WS2_blobs':baseline,'runtime':sys.version,'numpy':__import__('numpy').__version__,
             'scipy':__import__('scipy').__version__,'jsonschema':__import__('importlib.metadata',fromlist=['version']).version('jsonschema')}
    path=ROOT/'work/logs/checks.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('CHECKS_RECEIPT_SHA256',raw_sha(path.read_bytes()))
    return int(any(r['failures'] or r['errors'] or r['skips'] for r in results))


if __name__=='__main__':
    raise SystemExit(main())
