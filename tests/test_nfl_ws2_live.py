import copy
from datetime import datetime,timezone
import tempfile
from pathlib import Path
import unittest
from scripts.nfl_ws2_live import execute,audit,freeze,canonical,digest,MODEL_IDS,read_bound

NOW=datetime(2026,11,15,14,tzinfo=timezone.utc)
def fixture():
 c=dict(candidate_id='c',source_certified=True,research_shadow_eligible=True,
   event_start_at='2026-11-15T18:00:00Z',event_id='target',player_id='own',
   player_id_namespace='espn',position='WR',stat='receptions',line=3.0)
 packet={'model_training_cutoff_at':'2026-11-15T12:00:00Z','contracts':[
   {'candidate_id':'c','original_candidate_sha256':digest(canonical(c)),'role':'receiver'}], 'players':[]}
 for pid in ['own']+[f'p{i}' for i in range(5)]:
  for j,y in enumerate([0,2,5]):
   packet['players'].append(dict(player_id=pid,player_id_namespace='espn',event_id=f'past{j}',
      position='WR',role='receiver',team='DET',stat='receptions',period='full_game',
      game_end_at=f'2026-11-0{j+1}T23:00:00Z',available_at=f'2026-11-0{j+2}T12:00:00Z',
      source_received_at='2026-11-14T00:00:00Z',appearance='appeared',value=y))
 return {'input_freeze_at':'2026-11-15T04:00:00Z','candidates':[c]},packet

def run(s,p):return execute(s,packet=p,now=NOW,feature_freeze=NOW)
class LiveAdapter(unittest.TestCase):
 def test_valid_count_and_shared_mean(self):
  s,p=fixture();r=run(s,p);self.assertEqual(audit(r)['probability_rows_checked'],5)
  self.assertEqual(r[0]['models'][MODEL_IDS[2]]['mean'],r[0]['models'][MODEL_IDS[3]]['mean'])
 def test_missing_history_retains_every_contract(self):
  s,p=fixture();s['candidates']*=2;r=run(s,None)
  self.assertEqual(len(r),2);self.assertEqual(audit(r)['per_model'][MODEL_IDS[0]]['unavailable'],2)
 def test_dnp_not_zero(self):
  s,p=fixture();p['players'][0]['appearance']='DNP';r=run(s,p)
  self.assertEqual(r[0]['models'][MODEL_IDS[1]]['reason'],'insufficient_player_appearances')
 def test_temporal_identity_and_duplicate_attacks(self):
  for key,val in [('event_id','target'),('available_at','2026-11-16T00:00:00Z'),
     ('source_received_at','2026-11-16T00:00:00Z'),('player_id_namespace','gsis')]:
   s,p=fixture();p['players'][0][key]=val
   self.assertEqual(audit(run(s,p))['probability_rows_checked'],0)
  s,p=fixture();p['players'].append(p['players'][0]);self.assertEqual(audit(run(s,p))['probability_rows_checked'],0)
 def test_contract_line_tamper(self):
  s,p=fixture();s['candidates'][0]['line']=4
  self.assertEqual(audit(run(s,p))['probability_rows_checked'],0)
 def test_postkickoff(self):
  s,p=fixture();s['candidates'][0]['event_start_at']='2026-11-15T13:00:00Z'
  self.assertEqual(run(s,p)[0]['models'][MODEL_IDS[0]]['reason'],'FORECAST_NOT_PREGAME')
 def test_create_once(self):
  s,p=fixture()
  with tempfile.TemporaryDirectory() as d:
   freeze(Path(d),b'source',run(s,p),{'created_at':NOW.isoformat()})
   with self.assertRaises(FileExistsError):freeze(Path(d),b'source',run(s,p),{'created_at':NOW.isoformat()})
 def test_feature_path_escape_and_hash(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'packet.json';path.write_text('{}')
   with self.assertRaises(ValueError):read_bound(Path(d),{'path':'packet.json','sha256':'bad'})
   with self.assertRaises(ValueError):read_bound(Path(d),{'path':'../packet.json','sha256':'bad'})
 def test_valid_original_comparator_and_unknown_blend_moments(self):
  s,p=fixture();c=s['candidates'][0];c.update(over_odds=-110,under_odds=-110)
  p['contracts'][0]['original_candidate_sha256']=digest(canonical(c))
  p['controls']=[{'candidate_id':'c','original_candidate_sha256':digest(canonical(c)),
   'model_version':'production-historical-ensemble-60-40-20261108-v1',
   'forecast_at':'2026-11-15T10:00:00Z','q_over':.6,'q_under':.3,'q_push':.1}]
  r=run(s,p);self.assertEqual(audit(r)['probability_rows_checked'],8)
  for m in MODEL_IDS[5:]:self.assertIsNone(r[0]['models'][m]['mean'])
  p['controls'][0]['original_candidate_sha256']='wrong'
  self.assertEqual(run(s,p)[0]['models'][MODEL_IDS[6]]['status'],'unavailable')
 def test_signed_support_laws_only(self):
  s,p=fixture();c=s['candidates'][0];c['stat']='rushing yards'
  p['contracts'][0]['original_candidate_sha256']=digest(canonical(c))
  for r in p['players']:r['stat']='rushing yards';r['value']-=2
  rows=run(s,p);self.assertEqual(audit(rows)['probability_rows_checked'],2)
  self.assertEqual(rows[0]['models'][MODEL_IDS[2]]['reason'],'not_applicable_to_signed_count')
 def test_wide_table_adapter_dnp_missing_cells_crosswalk(self):
  from scripts.nfl_ws2_ws1_adapter import normalize_ws1_tables
  packet={'teams':[dict(game_id='g',team='DET',game_end_at='2026-11-01T23:00:00Z',
    available_at='2026-11-02T00:00:00Z',source_received_at='2026-11-14T00:00:00Z')],
   'player_crosswalk':[dict(source_player_id_namespace='gsis',source_player_id='00-1',
    player_id='espn1',player_id_namespace='espn',verified=True)],
   'historical_players':[dict(game_id='g',team='DET',player_id_namespace='gsis',player_id='00-1',
    appearance='DNP',position='WR',role='receiver',receptions=None,rushing_yards=-2)]}
  out=normalize_ws1_tables(packet)
  self.assertEqual(len(out['players']),1)
  self.assertEqual(out['players'][0]['appearance'],'DNP')
  self.assertEqual(out['players'][0]['value'],-2)
  self.assertEqual(out['players'][0]['player_id'],'espn1')
  packet['player_crosswalk'][0]['verified']=False
  with self.assertRaises(ValueError):normalize_ws1_tables(packet)
 def test_source_rejected_without_kickoff_preserved(self):
  s,p=fixture();s['candidates'][0].update(source_certified=False,event_start_at=None)
  with tempfile.TemporaryDirectory() as d:
   receipt=freeze(Path(d),b'source',run(s,p),{'created_at':NOW.isoformat()})
   self.assertEqual(receipt['input_contracts'],1)
   self.assertIn('UNKNOWN',receipt['per_kickoff_window'])
 def test_cli_real_population_shape_missing_pin_and_missing_kickoff(self):
  import contextlib,io,json
  from unittest.mock import patch
  from scripts import nfl_ws2_live as live
  s,p=fixture();s['candidates'].append({**s['candidates'][0], 'candidate_id':'rejected',
   'source_certified':False,'event_start_at':None})
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);control=root/'source_control';control.mkdir()
   raw=canonical(s)+b'\n';(control/'source.json').write_bytes(raw)
   (control/'HANDOFF_PIN.json').write_text(json.dumps({'source_control_manifest_sha256':digest(raw),
    'source_control_manifest_relative_path':'source_control/source.json'}))
   output=io.StringIO()
   with patch.object(live,'SOURCE_SHA',digest(raw)),patch('sys.argv',['live','--source-root',d,
     '--out-root',str(root/'output'),'--code-commit','test-fixture']),contextlib.redirect_stdout(output):
    live.main()
   receipt=json.loads(output.getvalue())
   self.assertEqual(receipt['input_contracts'],2)
   self.assertEqual(receipt['per_model'][MODEL_IDS[0]]['unavailable'],2)
   self.assertIsNone(receipt['feature_freeze_at'])
   self.assertEqual(digest(Path(receipt['index_path']).read_bytes()),receipt['index_sha256'])
 def test_actual_ws1_feature_schema_s2_and_unknown_zeros(self):
  s,p=fixture();c=s['candidates'][0]
  bound={**c,'gsis_player_id':'00-1','status':{'CONDITIONAL_ON_APPEARANCE_FORECASTABLE':True}}
  history=[dict(candidate_id='c',gsis_id='00-1',game_id=f'g{i}',game_date=f'2025-11-0{i+1}',
   source_available_at='2026-11-11T18:30:00Z',receptions=v,targets=2) for i,v in enumerate([0,2,4])]
  packet={'native_ws1_feature_v1':True,'contracts':[bound],'history':history}
  r=run(s,packet);self.assertEqual(audit(r)['probability_rows_checked'],1)
  self.assertEqual(r[0]['models'][MODEL_IDS[1]]['mean'],r[0]['models'][MODEL_IDS[1]]['mean'])
  history[0]['targets']=0
  self.assertEqual(run(s,packet)[0]['models'][MODEL_IDS[1]]['reason'],'insufficient_player_appearances')
  history[0]['targets']=2;history[0]['gsis_id']='wrong'
  self.assertEqual(audit(run(s,packet))['probability_rows_checked'],0)
 def test_archived_adapter_nonfinite_not_appearance_evidence(self):
  from scripts.nfl_ws2_archived_history import number
  for x in ('nan','inf','',None,'NA'):self.assertIsNone(number(x))
  self.assertEqual(number('-2'),-2)
 def test_archived_csv_adapter_completed_games_only_and_hashes(self):
  import csv,io,json
  from scripts.nfl_ws2_archived_history import derive
  s,_=fixture();s['candidates'][0]['player']='Example Receiver'
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);folder=root/'source_control/feature_source_receipts';folder.mkdir(parents=True)
   datasets={'players':[{'espn_id':'own','gsis_id':'00-1','display_name':'Example Receiver'}],
    'games2026':[{'season':'2026','game_type':'REG','gameday':f'2026-11-{day:02}',
     'result':'1','week':str(i),'home_team':'DET','away_team':'NE','game_id':f'g{i}'} for i,day in [(1,1),(2,8),(3,15)]],
    'stats2026':[{'season':'2026','season_type':'REG','week':str(i),'team':'DET',
     'player_id':'00-1','receptions':str(i),'targets':'4'} for i in (1,2,3)]}
   for label,rows in datasets.items():
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    raw=out.getvalue().encode();path=folder/(label+'.csv');path.write_bytes(raw)
    (folder/(label+'_CAPTURE.json')).write_text(json.dumps({'raw_path':str(path),
      'sha256':digest(raw),'observed_received_at':'2026-11-15T14:00:00Z'}))
   packet,at,provenance=derive(root,s)
   self.assertEqual(len(packet['history']),2)
   self.assertEqual({h['game_id'] for h in packet['history']},{'g1','g2'})
   (folder/'players.csv').write_text('tampered')
   with self.assertRaises(ValueError):derive(root,s)
