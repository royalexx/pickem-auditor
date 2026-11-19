"""Independent P3 raw-source feature oracle and public boundary attacks."""
import copy,hashlib,json,math,pathlib,shutil,statistics,tempfile,unittest
from datetime import datetime
from v2.nba_architecture import subset_p3_v1 as p3
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest,export_requests
ROOT=pathlib.Path(__file__).resolve().parents[5];PACK=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119';OUT=pathlib.Path(__file__).resolve().parent/'final_05b44764';CAP=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture';C=json.loads((PACK/'PROSPECTIVE_COHORT.json').read_bytes());H=PACK/'prospective_inputs';M=ROOT/'research/nba_ws2/results/model.json';CLOCK=(OUT/'forecast_at.txt').read_text().strip();SOURCE=(OUT/'p1.json').read_bytes();WIRE=(OUT/'p3.json').read_bytes();VALUE=json.loads(WIRE)
def utc(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
class IndependentP3(unittest.TestCase):
 def test_raw_observations_and_manual_13feature_oracle(self):
  board=json.loads((CAP/'scoreboard/body.raw').read_bytes());target=next(e for e in board['events'] if str(e['id'])==C['game_id']);rawobs={};games={}
  for tid in C['teams']:
   schedule=json.loads((H/('schedule-'+tid)/'body.raw').read_bytes());events=sorted([e for e in schedule['events'] if utc(e['date'])<utc(C['freeze_at']) and e['competitions'][0]['status']['type'].get('completed') is True],key=lambda e:(utc(e['date']),e['id']));games[tid]=events
   for e in events:
    s=json.loads((H/('summary-'+e['id'])/'body.raw').read_bytes());team=next(t for t in s['boxscore']['players'] if str(t['team']['id'])==tid);stat=team['statistics'][0];index=stat['names'].index('MIN')
    for person in stat['athletes']:
     pid='espn:player:'+str(person['athlete']['id']);mins=person.get('stats',[]);token=mins[index] if len(mins)>index else None;state='DNP' if person['didNotPlay'] is True else 'PLAYED' if isinstance(token,str) and token.isdigit() and int(token)>0 else 'PLAYED_ZERO_DISPLAY' if token=='0' else 'UNKNOWN';rawobs[(pid,e['id'])]=(state,int(token) if state in ['PLAYED','PLAYED_ZERO_DISPLAY'] else None)
  for o in VALUE['observations']:
   expected=rawobs.get((o['player_id'],o['game_id']),('UNKNOWN',None));self.assertEqual((o['state'],o['displayed_minutes']),expected)
  model=p3.native.MinutesModel.load(M)
  for row in VALUE['rows']:
   if not row['forecast']:continue
   tid=row['team_id'].split(':')[-1];pid=row['player_id'];events=games[tid];hist=[(e,rawobs[(pid,e['id'])][1]) for e in events if rawobs.get((pid,e['id']),('UNKNOWN',None))[0]=='PLAYED' and e['date'][:10]<C['start'][:10]][-10:];values=[float(n) for _,n in hist];n=len(values);mean=statistics.mean(values);mean3=statistics.mean(values[-3:]);rest=(datetime.fromisoformat(C['start'][:10])-datetime.fromisoformat(hist[-1][0]['date'][:10])).days;start=next(i for i,e in enumerate(events) if e['id']==hist[0][0]['id']);self.assertTrue(all(rawobs.get((pid,e['id']),('UNKNOWN',None))[0] in ['PLAYED','DNP'] for e in events[start:]));after=events.index(hist[-1][0])+1;gap=sum(rawobs[(pid,e['id'])][0]=='DNP' for e in events[after:]);home=next(t for t in target['competitions'][0]['competitors'] if str(t['id'])==tid)['homeAway']=='home'
   expected=dict(median5=statistics.median(values[-5:]),mean10=mean,mean3=mean3,sd10=statistics.stdev(values),trend=mean3-mean,rest_days=float(min(rest,14)),back_to_back=float(rest==1),return_gap=float(min(gap,5)),team_change=0.,home=float(home),prior_n=float(n),role_high=float(mean>=28),role_low=float(mean<14));self.assertEqual(set(expected),set(row['features']))
   for k,v in expected.items():self.assertAlmostEqual(v,row['features'][k],places=10)
   mu,var=model.parameters(row['model'],expected,row['position']);self.assertAlmostEqual(mu,row['forecast']['distribution']['mean'],places=9);self.assertAlmostEqual(var,row['forecast']['distribution']['variance'],places=9)
 def test_resealed_probability_feature_and_model_claims_rejected(self):
  for kind in ['q','eligibility','feature','distribution','drop','approved']:
   x=copy.deepcopy(VALUE);r=next(r for r in x['rows'] if r['forecast'])
   if kind=='q':r['forecast']['participation_probability']=1
   if kind=='eligibility':r['legal_eligibility']=True
   if kind=='feature':r['features']['median5']+=1
   if kind=='distribution':r['forecast']['distribution']['mean']+=1
   if kind=='drop':x['rows'].pop()
   if kind=='approved':x['approved']=True;x['model_admission']='GENERAL_APPROVED'
   x.pop('payload_sha256');x['payload_sha256']=digest(canonical(x))
   with self.subTest(kind=kind),self.assertRaises(ValueError):p3.read_p3(canonical(x),source_raw=SOURCE,capture_dir=CAP,cohort=C,history_dir=H,model_path=M,forecast_at=CLOCK)
 def test_bad_position_stays_per_player_and_model_bytes_do_not_admit(self):
  with tempfile.TemporaryDirectory() as tmp:
   cap=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,cap);f=cap/'roster-29/body.raw';v=json.loads(f.read_bytes());pid='espn:player:'+str(v['athletes'][0]['id']);v['athletes'][0]['position']=None;f.write_text(json.dumps(v));r=cap/'roster-29/receipt.json';v=json.loads(r.read_bytes());v['raw_sha256']=digest(f.read_bytes());v['bytes']=len(f.read_bytes());r.write_text(json.dumps(v));source=canonical(export_requests(cap,C));x=p3.run_p3(source,cap,C,history_dir=H,model_path=M,forecast_at=CLOCK);self.assertEqual(x['attempt_denominator'],108);self.assertGreater(x['forecasted_rows'],0);self.assertTrue(all(r['forecast'] is None and r['reason']=='P3_POSITION_UNAVAILABLE' for r in x['rows'] if r['player_id']==pid))
   fake=pathlib.Path(tmp)/'model.json';fake.write_bytes(M.read_bytes()+b'\n');x=p3.run_p3(SOURCE,CAP,C,history_dir=H,model_path=fake,forecast_at=CLOCK);self.assertEqual((x['forecasted_rows'],x['abstained_rows']),(0,108))
 def test_credited_dnp_remains_unknown_and_rejected_history_population_stays_counted(self):
  with tempfile.TemporaryDirectory() as tmp:
   h=pathlib.Path(tmp)/'history';shutil.copytree(H,h);chosen=None
   for folder in h.glob('summary-*'):
    value=json.loads((folder/'body.raw').read_bytes());team=next((t for t in value['boxscore']['players'] if str(t['team']['id'])=='29'),None)
    if team:
     stat=team['statistics'][0];row=next((a for a in stat['athletes'] if a.get('didNotPlay') is True),None)
     if row:
      row['stats']=['0']*len(stat['names']);row['stats'][stat['names'].index('PTS')]='3';chosen=(folder,value,'espn:player:'+str(row['athlete']['id']));break
   self.assertIsNotNone(chosen);folder,value,pid=chosen;f=folder/'body.raw';f.write_text(json.dumps(value));r=folder/'receipt.json';value=json.loads(r.read_bytes());value['raw_sha256']=digest(f.read_bytes());value['bytes']=len(f.read_bytes());r.write_text(json.dumps(value));games,_=p3.read_team_history(h,'29',C);obs=next(g['observations'][pid] for g in games if g['source_label']==folder.name);self.assertEqual(obs['state'],'UNKNOWN');self.assertEqual(obs['raw_credit_array'][1],'3')
   schedule=h/'schedule-29/body.raw';value=json.loads(schedule.read_bytes());idx=next(i for i,e in enumerate(value['events']) if e['competitions'][0]['status']['type'].get('completed') is True);value['events'].pop(idx);schedule.write_text(json.dumps(value));r=h/'schedule-29/receipt.json';value=json.loads(r.read_bytes());value['raw_sha256']=digest(schedule.read_bytes());value['bytes']=len(schedule.read_bytes());r.write_text(json.dumps(value));x=p3.run_p3(SOURCE,CAP,C,history_dir=h,model_path=M,forecast_at=CLOCK);self.assertEqual(x['attempt_denominator'],108);self.assertEqual(x['observation_denominator'],540);self.assertGreater(x['forecasted_rows'],0);self.assertIn('29',x['team_errors'])
 def test_forecast_clock_scope_and_duplicate_wire(self):
  with self.assertRaises(ValueError):p3.run_p3(SOURCE,CAP,C,history_dir=H,model_path=M,forecast_at='2026-11-20T01:01:00Z')
  c=copy.deepcopy(C);c['game_id']='401070213'
  with self.assertRaises(ValueError):p3.run_p3(SOURCE,CAP,c,history_dir=H,model_path=M,forecast_at=CLOCK)
  with self.assertRaises(ValueError):p3.read_p3(b'{"q":1,"q":null}',source_raw=SOURCE,capture_dir=CAP,cohort=C,history_dir=H,model_path=M,forecast_at=CLOCK)
if __name__=='__main__':unittest.main(verbosity=2)
