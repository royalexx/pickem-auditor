"""Portable exact final-source and actual installed capability API confirmation."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=a.candidate.resolve();sys.path.insert(0,str(r))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip();assert head=='9e8145972077a598687eaabdbc559f3cbce5e4d7'
from v2.nba_architecture.admission_v1 import admit_gamebook,REVIEWED_REGISTRY_SHA256,HISTORICAL_CAPABILITIES
from v2.nba_architecture.v2_contracts import ContractError
s=r/'docs/nba_architecture/substantive_remediation_20261117/source_search';raw=(s/'nba_pdf.raw').read_bytes();capture=json.loads((s/'nba_pdf.receipt.json').read_bytes());capture['raw_sha256']=capture['sha256'];results=[]
for cap in sorted(HISTORICAL_CAPABILITIES):
 out=admit_gamebook(raw,capture,required_capability=cap);assert out['upstream_training_rows_admitted']==0 and not out['original_pregame_certified'] and not out['external_player_identity_admitted'] and not out['fitted_model_admitted'];results.append(out)
for cap in ['ORIGINAL_AVAILABILITY','PREGAME_ROSTER','EXTERNAL_IDENTITIES','FITTED_MODEL','COMPLETE_CORRECTIONS']:
 try:admit_gamebook(raw,capture,required_capability=cap)
 except ContractError as exc:assert exc.code=='ADMISSION_UNSUPPORTED_CAPABILITY'
 else:raise AssertionError(cap)
registry=r/'docs/nba_architecture/substantive_remediation_20261117/admitted_source_registry.json';reg=json.loads(registry.read_bytes());assert len(reg['sources'])==1 and hashlib.sha256(registry.read_bytes()).hexdigest()==REVIEWED_REGISTRY_SHA256
entry=reg['sources'][hashlib.sha256(raw).hexdigest()];assert set(entry['capabilities'])==set(HISTORICAL_CAPABILITIES) and entry['independent_receipt_sha256']=='64464f369f6696def13a58816b9a1a04c6c78de3bc6ecd7e782555b32a6e6ba6'
files=['v2/nba_architecture/exposure_certificate_v1.py','v2/nba_architecture/families_certified_v1.py','v2/nba_o_certified.py','v2/nba_architecture/gamebook_v1.py','v2/nba_architecture/admission_v1.py','v2/nba_architecture/gamebook_identity_v1.py','tests/nba_architecture/test_exposure_certificate_v1.py','tests/nba_architecture/test_gamebook_v1.py']
core=['v2/nba_architecture/exposure_v2.py','v2/nba_architecture/families_v2.py','v2/nba_architecture/v2_contracts.py','v2/nba_architecture/schema-2.0.0.json']
unchanged=subprocess.check_output(['git','diff','--name-only','59d28dc23be97de2a6a82d22be8338151e31f5b6','--',*core],cwd=r).decode().splitlines();assert unchanged==[]
result=dict(candidate=head,registry_hash=REVIEWED_REGISTRY_SHA256,admitted_content_only=results,unsupported_capabilities_rejected=True,accepted_G0_core_unchanged=core,source_raw_sha256={f:hashlib.sha256((r/f).read_bytes()).hexdigest() for f in files},qa_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),all_pass=True)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(candidate=head,all_pass=True,capabilities=sorted(HISTORICAL_CAPABILITIES))))
