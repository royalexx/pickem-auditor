"""From repo root: fresh exact-SHA contract checks, no network/model execution.

Receipt outputs go to /tmp by default, never replacing frozen campaign evidence.
Use --out /desired/new/directory for a separate execution packet.
"""
import argparse,ast,re,hashlib,importlib.metadata,json,pathlib,platform,subprocess,sys,tempfile
root=pathlib.Path.cwd();ap=argparse.ArgumentParser();ap.add_argument('--out');args=ap.parse_args();out=pathlib.Path(args.out or tempfile.mkdtemp(prefix='g0-exact-'));out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests/nba_architecture'))
from jsonschema import Draft202012Validator,FormatChecker
from golden_v2 import golden_cases
from test_g0_pipeline_completion_20261116 import coherent_case
from v2.nba_architecture.v2_contracts import canonical
from v2.nba_architecture.families_v2 import validate_forecast
schema=json.loads((root/'v2/nba_architecture/schema-2.0.0.json').read_text());Draft202012Validator.check_schema(schema);v=Draft202012Validator(schema,format_checker=FormatChecker())
def walk(x):
 if isinstance(x,dict):
  if 'schema' in x and 'kind' in x:v.validate(x)
  for y in x.values():walk(y)
 elif isinstance(x,list):
  for y in x:walk(y)
for name,case in golden_cases().items():
 assert (root/'tests/nba_architecture/golden_v2'/f'{name}.json').read_bytes()==canonical(case)+b'\n';walk(case)
c=coherent_case();walk(c);assert validate_forecast(c['points'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c['scenarios'])
assert (root/'docs/nba_architecture/completion_20261116/coherent_joint.json').read_bytes()==canonical(c)+b'\n'
registry=json.loads((root/'docs/nba_architecture/completion_20261116/invariants.json').read_text());assert not registry['unresolved_g0']
for row in registry['invariants']:
 assert row['gate']=='G0' and row['negative_tests'] and row['positive_tests']
 for ref in row['negative_tests']+row['positive_tests']:
  f,method=ref.split('::');assert any(isinstance(n,ast.FunctionDef) and n.name==method for n in ast.walk(ast.parse((root/f).read_text()))),ref
checks=json.loads((root/'docs/nba_architecture/completion_20261116/check_inventory.json').read_text());assert all(row['registry_groups'] for row in checks)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
preserved={}
old='c53a72594923ae995d996f5d9db1d22a63c00241'
for area in ('docs/nba_architecture','tests/nba_architecture/golden_v2'):
 for rel in subprocess.check_output(['git','ls-tree','-r','--name-only',old,area],text=True).splitlines():
  raw=subprocess.check_output(['git','show',old+':'+rel]);assert raw==(root/rel).read_bytes(),rel;preserved[rel]=sha(root/rel)
cmd=[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-p','test_*.py','-v'];r=subprocess.run(cmd,capture_output=True,text=True);(out/'exact-sha.log').write_text(r.stdout+r.stderr)
paths=[f for area in ('v2/nba_architecture','tests/nba_architecture','docs/nba_architecture/completion_20261116') for f in (root/area).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
totals = re.search(r'Ran (\d+) tests', r.stderr)
assert totals is not None
assert not re.search(r'\bskipped=', r.stderr), 'Unexpected skipped tests'
receipt=dict(test_count=int(totals.group(1)),failures=0 if r.returncode==0 else 'see log',errors=0 if r.returncode==0 else 'see log',skipped=0,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=subprocess.check_output(['git','status','--porcelain'],text=True),python=platform.python_version(),packages={n:importlib.metadata.version(n) for n in ['numpy','scipy','jsonschema']},command=cmd,exit=r.returncode,summary=r.stderr.splitlines()[-5:],test_log_sha256=sha(out/'exact-sha.log'),raw_sha256={str(f.relative_to(root)):sha(f) for f in paths},preserved_sha256=preserved,seeds=[42,20261116],schema='Draft202012 + all legacy and complete-pipeline golden instances PASS',goldens='three legacy plus coherent_joint byte-identical',registry='all 24 groups linked to executable positive/negative tests; check inventory mapped',independent_acceptance=False,decision='G0 CANDIDATE READY FOR INDEPENDENT REVIEW' if r.returncode==0 else 'G0 FAIL',output_directory=str(out))
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('raw_sha256','preserved_sha256')},indent=2));sys.exit(r.returncode)
