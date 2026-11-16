"""Fresh exact-SHA repair evidence. Writes only to a new output directory."""
import argparse,ast,hashlib,importlib.metadata,json,pathlib,platform,re,subprocess,sys,tempfile
root=pathlib.Path.cwd();packet=root/'docs/nba_architecture/law_repair_20261116'
ap=argparse.ArgumentParser();ap.add_argument('--out');args=ap.parse_args()
out=pathlib.Path(args.out or tempfile.mkdtemp(prefix='g0-law-repro-'));out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
from jsonschema import Draft202012Validator,FormatChecker
from golden_v2 import golden_cases
from test_g0_pipeline_completion_20261116 import coherent_case
from test_g0_law_repair_20261116 import LawCouplingControls
from v2.nba_architecture.v2_contracts import canonical
from v2.nba_architecture.families_v2 import validate_forecast
schema=json.loads((root/'v2/nba_architecture/schema-2.0.0.json').read_text());Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema,format_checker=FormatChecker())
def walk(x):
 if isinstance(x,dict):
  if 'schema' in x and 'kind' in x:validator.validate(x)
  for y in x.values():walk(y)
 elif isinstance(x,list):
  for y in x:walk(y)
for name,case in golden_cases().items():
 assert (root/'tests/nba_architecture/golden_v2'/f'{name}.json').read_bytes()==canonical(case)+b'\n';walk(case)
for case,path in [(coherent_case(),'docs/nba_architecture/completion_20261116/coherent_joint.json'),(LawCouplingControls.exchange_case(None),'docs/nba_architecture/law_repair_20261116/exchange_golden.json')]:
 assert (root/path).read_bytes()==canonical(case)+b'\n';walk(case)
 assert validate_forecast(case['points'],case['pregame'],g=case['game_state'],o=case['opportunity'],scenarios=case['scenarios'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent='e1983b2d0b94742dfb1bf411694dc46c7cad1ac6';preserved={}
for area in ['docs/nba_architecture','tests/nba_architecture']:
 for relative in subprocess.check_output(['git','ls-tree','-r','--name-only',parent,area],text=True).splitlines():
  assert (root/relative).read_bytes()==subprocess.check_output(['git','show',parent+':'+relative]),relative
  preserved[relative]=sha(root/relative)
for relative in ['v2/nba_architecture/v2_contracts.py','v2/nba_architecture/schema-2.0.0.json','v2/nba_architecture/requirements.txt']:
 assert (root/relative).read_bytes()==subprocess.check_output(['git','show',parent+':'+relative]),relative
 preserved[relative]=sha(root/relative)
r=json.loads((packet/'invariants.json').read_text());assert r['registry_version']=='1.2.0' and len(r['invariants'])==27 and not r['unresolved_g0']
for entry in r['invariants']:
 for ref in entry['negative_tests']+entry['positive_tests']:
  file,name=ref.split('::');assert any(isinstance(n,ast.FunctionDef) and n.name==name for n in ast.walk(ast.parse((root/file).read_text()))),ref
cmd=[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-p','test_*.py','-v']
completed=subprocess.run(cmd,capture_output=True,text=True);log=completed.stdout+completed.stderr;(out/'exact-sha.log').write_text(log)
match=re.search(r'Ran (\d+) tests',log);assert match
assert not re.search(r'\bskipped=',log),'Unexpected test skips'
paths=[p for area in ['v2/nba_architecture','tests/nba_architecture','docs/nba_architecture/law_repair_20261116'] for p in (root/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
receipt=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=subprocess.check_output(['git','status','--porcelain'],text=True),rejected_parent=parent,python=platform.python_version(),platform=platform.platform(),packages={name:importlib.metadata.version(name) for name in ['numpy','scipy','jsonschema']},command=cmd,test_count=int(match.group(1)),exit=completed.returncode,failures=0 if completed.returncode==0 else 'see log',errors=0 if completed.returncode==0 else 'see log',skipped=0,test_log_sha256=sha(out/'exact-sha.log'),summary=completed.stderr.splitlines()[-5:],raw_sha256={str(p.relative_to(root)):sha(p) for p in paths},preserved_sha256=preserved,schema='Draft202012 + all golden instances PASS',goldens='all three legacy + earlier complete + new exchange exactly reproduced',registry='27 groups, executable references resolved',report_findings='F1/F2 repaired; see failure_ledger.json',independent_acceptance=False,formal_g0='NOT_APPROVED_PENDING_NEW_INDEPENDENT_REVIEW',engineering_candidate='READY_FOR_INDEPENDENT_REVIEW' if completed.returncode==0 else 'FAIL',output_directory=str(out))
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['raw_sha256','preserved_sha256']},indent=2))
sys.exit(completed.returncode)
