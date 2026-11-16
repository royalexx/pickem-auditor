"""Run from repository root; stdout is the receipt. No network or model training."""
import sys, json, hashlib, subprocess, platform, importlib.metadata
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path('tests/nba_architecture').resolve()))
from golden_v2 import golden_cases
from v2.nba_architecture.v2_contracts import canonical
from jsonschema import Draft202012Validator, FormatChecker
root = Path('.')
schema = json.loads(Path('v2/nba_architecture/schema-2.0.0.json').read_text())
Draft202012Validator.check_schema(schema)
v = Draft202012Validator(schema, format_checker=FormatChecker())
fixture_hashes = {}
for name, case in golden_cases().items():
    f = Path('tests/nba_architecture/golden_v2') / (name+'.json')
    assert f.read_bytes() == canonical(case)+b'\n', name
    fixture_hashes[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    def walk(x):
        if isinstance(x, dict):
            if 'schema' in x and 'kind' in x:
                v.validate(x)
            for y in x.values(): walk(y)
        elif isinstance(x, list):
            for y in x: walk(y)
    walk(case)
files = sorted(list(Path('v2/nba_architecture').glob('*.py')) + list(Path('v2/nba_architecture').glob('*.json')) + list(Path('tests/nba_architecture').glob('*.py')))
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
receipt = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'python': platform.python_version(), 'packages': {n: importlib.metadata.version(n) for n in ['numpy','scipy','jsonschema']},
 'raw_file_sha256': {str(f): sha(f) for f in files}, 'golden_raw_sha256': fixture_hashes,
 'schema': 'Draft 2020-12 schema + all golden object instances PASS'}
r = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-p','test_*.py','-v'], capture_output=True,text=True)
Path('docs/nba_architecture/independent_final_20261116/green.log').write_text(r.stdout+r.stderr)
receipt.update(test_exit=r.returncode, test_log_sha256=sha(Path('docs/nba_architecture/independent_final_20261116/green.log')), test_summary=r.stderr.splitlines()[-4:])
for name in ['G0_HANDOFF.json','G0_P0I_BLOCKED_V2_20261116.json']:
    p = 'docs/nba_architecture/'+name
    old = subprocess.check_output(['git','show','3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2:'+p])
    assert old == Path(p).read_bytes()
    receipt.setdefault('preserved_raw_sha256',{})[p] = sha(Path(p))
print(json.dumps(receipt,indent=2))
assert r.returncode == 0
