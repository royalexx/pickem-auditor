"""Run from repo root. Writes only this campaign's new execution receipts."""
import hashlib,importlib.metadata,json,pathlib,platform,subprocess,sys
root=pathlib.Path.cwd();out=root/'docs/nba_architecture/hardening_20261116'
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests/nba_architecture'))
from jsonschema import Draft202012Validator,FormatChecker
from golden_v2 import golden_cases
from v2.nba_architecture.v2_contracts import canonical
schema=json.loads((root/'v2/nba_architecture/schema-2.0.0.json').read_text())
Draft202012Validator.check_schema(schema);v=Draft202012Validator(schema,format_checker=FormatChecker())
def walk(x):
 if isinstance(x,dict):
  if 'schema' in x and 'kind' in x:v.validate(x)
  for y in x.values():walk(y)
 elif isinstance(x,list):
  for y in x:walk(y)
for name,case in golden_cases().items():
 assert (root/'tests/nba_architecture/golden_v2'/f'{name}.json').read_bytes()==canonical(case)+b'\n'
 walk(case)
preserved={}
for f in (root/'docs/nba_architecture').rglob('*'):
 if f.is_file() and 'hardening_20261116' not in f.parts:
  rel=str(f.relative_to(root))
  prior=subprocess.run(['git','show','18bd56974a051ed515d601f9931a2cfa7e045e3f:'+rel],capture_output=True)
  if prior.returncode==0:
   assert prior.stdout==f.read_bytes(),rel
   preserved[rel]=hashlib.sha256(f.read_bytes()).hexdigest()
cmd=[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-p','test_*.py','-v']
r=subprocess.run(cmd,capture_output=True,text=True);(out/'exact-sha.log').write_text(r.stdout+r.stderr)
files=sorted(list((root/'v2/nba_architecture').glob('*'))+list((root/'tests/nba_architecture').rglob('*')))
receipt=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),python=platform.python_version(),packages={n:importlib.metadata.version(n) for n in ['numpy','scipy','jsonschema']},command=cmd,exit=r.returncode,summary=r.stderr.splitlines()[-5:],raw_sha256={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file() and '__pycache__' not in f.parts},preserved_sha256=preserved,seeds=[42],schema='Draft202012 and golden instances PASS',goldens='all three byte-identical',independent_acceptance=False,decision='G0 BLOCKED: full manual invariant audit and planned mutation campaign incomplete')
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('raw_sha256','preserved_sha256')},indent=2));sys.exit(r.returncode)
