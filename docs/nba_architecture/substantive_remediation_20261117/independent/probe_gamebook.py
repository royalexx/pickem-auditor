"""Independent content oracle and isolated installed-root admission tests."""
import argparse,copy,hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.candidate.resolve();sys.path.insert(0,str(root))
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture import admission_v1 as api
from v2.nba_architecture.v2_contracts import ContractError
source=root/'docs/nba_architecture/substantive_remediation_20261117/source_search'
raw=(source/'nba_pdf.raw').read_bytes();receipt=json.loads((source/'nba_pdf.receipt.json').read_bytes());receipt['raw_sha256']=receipt['sha256']
x=read_final_box(raw,receipt)
# Independently transcribed from visual inspection of official first-page table.
manual={
'PHI':{'Dario Saric':('22:55',6),'Robert Covington':('34:12',8),'Joel Embiid':('36:49',23),'Markelle Fultz':('24:20',5),'Ben Simmons':('42:45',19),'Amir Johnson':('11:11',5),'JJ Redick':('29:46',16),'T.J. McConnell':('22:26',4),'Landry Shamet':('12:42',1),'Furkan Korkmaz':('01:27',0),'Jonah Bolden':('01:27',0),'Demetrius Jackson':(None,None),'Shake Milton':(None,None)},
'BOS':{'Jayson Tatum':('28:56',23),'Gordon Hayward':('24:37',10),'Al Horford':('29:57',9),'Jaylen Brown':('28:23',12),'Kyrie Irving':('29:00',7),'Terry Rozier':('26:31',11),'Marcus Morris':('20:30',16),'Marcus Smart':('25:01',7),'Aron Baynes':('19:14',8),'Daniel Theis':('04:08',0),'Guerschon Yabusele':('01:27',0),'Semi Ojeleye':('01:27',0),'Brad Wanamaker':('00:49',2)}}
assert len(x['rows'])==26
for row in x['rows']:
 clock,points=manual[row['team']][row['name']]
 if clock is None:assert row['state']=='DNP' and row['exact_seconds'] is None and row['stats']=={}
 else:assert row['exact_seconds']==int(clock[:2])*60+int(clock[-2:]) and row['stats']['points']==points
assert x['duration_minutes']=='48' and x['overtime_periods']==0
assert {team:sum(r['stats'].get('points',0) for r in x['rows'] if r['team']==team) for team in manual}=={'PHI':87,'BOS':105}
results=[dict(case='26_manual_name_seconds_points_oracles',status='PASS')]
try:api.admit_gamebook(raw,receipt,required_capability='OFFICIAL_PRINTED_DURATION')
except ContractError as exc:assert exc.code=='ADMISSION_INDEPENDENT_ROOT_UNAVAILABLE'
else:raise AssertionError('Uninstalled root admitted source')
results.append(dict(case='uninstalled_root_fails_closed',status='PASS'))
# Isolated test of the proposed future trusted installation. No implementation
# file is modified; only root-location/hash installation constants are mocked.
with tempfile.TemporaryDirectory() as d:
 temp=Path(d);proof=temp/'approval.json';proof.write_bytes(b'{"synthetic_test_installation_only":true}\n');registry=temp/'registry.json'
 entry=dict(url=receipt['url'],retrieved_at=receipt['retrieved_at'],capabilities=sorted(api.HISTORICAL_CAPABILITIES),independent_receipt_path='approval.json',independent_receipt_sha256=hashlib.sha256(proof.read_bytes()).hexdigest(),reader_raw_sha256=hashlib.sha256((root/'v2/nba_architecture/gamebook_v1.py').read_bytes()).hexdigest())
 original=json.dumps(dict(sources={hashlib.sha256(raw).hexdigest():entry}),sort_keys=True).encode();registry.write_bytes(original)
 with patch.object(api,'ROOT',temp),patch.object(api,'REGISTRY',registry),patch.object(api,'REVIEWED_REGISTRY_SHA256',hashlib.sha256(original).hexdigest()):
  for cap in sorted(api.HISTORICAL_CAPABILITIES):
   r=api.admit_gamebook(raw,receipt,required_capability=cap)
   assert not r['original_pregame_certified'] and r['original_pregame_available_at'] is None and r['correction_history_complete'] is None and not r['external_player_identity_admitted'] and not r['fitted_model_admitted'] and r['upstream_training_rows_admitted']==0
   results.append(dict(case='installed_root_capability',capability=cap,status='PASS'))
  for attack in ('root_bytes','proof_bytes','unreviewed_raw','capture_url','capture_clock','unsupported_capability','receipt_status'):
   blob=raw;r=copy.deepcopy(receipt);cap='OFFICIAL_PRINTED_DURATION'
   if attack=='root_bytes':registry.write_bytes(original+b' ')
   elif attack=='proof_bytes':proof.write_bytes(b'changed')
   elif attack=='unreviewed_raw':blob=raw+b'changed';r['raw_sha256']=hashlib.sha256(blob).hexdigest()
   elif attack=='capture_url':r['url']=r['url'].replace('PHIBOS','BOSPHI')
   elif attack=='capture_clock':r['retrieved_at']='2026-11-17T00:00:00Z'
   elif attack=='unsupported_capability':cap='PREGAME_AVAILABILITY'
   elif attack=='receipt_status':r['status']=403
   try:api.admit_gamebook(blob,r,required_capability=cap)
   except ContractError as exc:results.append(dict(case=attack,status='PASS',rejection=exc.code))
   else:raise AssertionError(attack)
   registry.write_bytes(original);proof.write_bytes(b'{"synthetic_test_installation_only":true}\n')
  spoof=copy.deepcopy(receipt);spoof.update(original_pregame_available_at='2018-10-16T00:00:00Z',source_admission='VERIFIED',fitted_model_admitted=True)
  r=api.admit_gamebook(raw,spoof,required_capability='OFFICIAL_PRINTED_BOX_SCORE');assert r['original_pregame_available_at'] is None and not r['fitted_model_admitted']
  results.append(dict(case='optimistic_caller_labels_do_not_expand_capability',status='PASS'))
result=dict(schema='NBA_P6_GAMEBOOK_INDEPENDENT_CONTENT_AND_PROTOCOL_PROBES_V1',candidate='16f3eb732c476ea8683e7976f36c4d12f7680ed7',raw_pdf_sha256=hashlib.sha256(raw).hexdigest(),reader_sha256=hashlib.sha256((root/'v2/nba_architecture/gamebook_v1.py').read_bytes()).hexdigest(),qa_source_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),manual_row_oracle=manual,results=results,all_pass=True,registry_installation_test_only=True,production_root_installed=False)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
