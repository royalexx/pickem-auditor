"""Independent outcome evidence profile. No fit, inference or score is invoked."""
from pathlib import Path
import collections,copy,hashlib,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.pbp_evidence_v1 import read_population,parse_pbp
from v2.nba_architecture.prospective_s_sources_v1 import next_data
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent;ORIGINAL=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive/inputs/raw';RESULT={}
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(page):return b'<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':page}},separators=(',',':')).encode()+b'</script>'
class Profile(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pop=json.loads((P/'PBP_POPULATION.json').read_bytes());cls.read=read_population(P/'raw',P/'PBP_POPULATION.json',ORIGINAL)
 def test_01_exact20_population_rawreceipts_clocks_all14facts(self):
  self.assertEqual((self.read['game_denominator'],self.read['rejected_games']),(20,0));games=[];players=0;actions=0;states=collections.Counter();ledger=[]
  for name,item in self.pop['sources'].items():
   gid=name[4:];body=(P/'raw'/name/'body.raw').read_bytes();rr=(P/'raw'/name/'receipt.json').read_bytes();r=json.loads(rr);br=(ORIGINAL/('nba-box-'+gid)/'body.raw').read_bytes();receipt=json.loads((ORIGINAL/('nba-box-'+gid)/'receipt.json').read_bytes());self.assertEqual((sha(body),sha(rr)),(item['body_sha256'],item['receipt_sha256']));self.assertEqual(sha(br),receipt['raw_sha256']);self.assertEqual(len(body),r['bytes']);self.assertEqual(len(br),receipt['bytes']);self.assertEqual(r['status'],200)
   self.assertLessEqual(r['retrieval_started_at'],r['retrieval_completed_at']);self.assertLessEqual(r['retrieval_completed_at'],r['ingested_at']);self.assertLessEqual(r['ingested_at'],self.pop['frozen_at'])
   for field in ('source_published_at','original_historical_available_at','correction_history_complete','predecessor_sha256'):self.assertIsNone(r[field]);self.assertIsNone(receipt[field])
   f=next(x['facts'] for x in self.read['rows'] if x['game_id']==gid);page=next_data(body);g=page['game'];self.assertEqual(g['gameStatus'],3);self.assertEqual(g['gameClock'],'PT00M00.00S');self.assertEqual(len(f['reconciled_event_credit_fields']),14);self.assertEqual(f['event_credit_discrepancies'],[]);self.assertEqual(f['unresolved_aliases'],[]);self.assertIsNone(f['exact_wallclock_end_at']);self.assertIsNone(f['correction_history_complete']);self.assertIsNone(f['on_court_lineup_completeness']);actions+=f['action_denominator'];seen=set()
   for side in ('homeTeam','awayTeam'):
    team=g[side];counts=collections.Counter()
    for row in team['players']:
     self.assertNotIn(row['personId'],seen);seen.add(row['personId']);players+=1;comment=row.get('comment') or '';minutes=row['statistics']['minutes'];states['DNP_EXPLICIT' if comment.startswith('DNP') else 'ZERO_DISPLAY' if minutes=='0:00' else 'REPORTED_PLAYED' if minutes else 'UNKNOWN']+=1
     for field in f['reconciled_event_credit_fields']:self.assertIs(type(row['statistics'][field]),int);self.assertGreaterEqual(row['statistics'][field],0);counts[field]+=row['statistics'][field]
    for field,value in counts.items():self.assertEqual(value,team['statistics'][field])
   games.append({'nba_game_id':gid,'start_at':g['gameTimeUTC'],'native_player_rows':len(seen),'final_period':g['period'],'end_wallclock_source_text':f['reported_end_wallclock_text'],'exact_end_at':None,'PIT_new_model_replay_eligible':False,'reason':'TRAINING_GAME_NO_SUPPLIED_PRE_EVENT_NEW_FULL_LAW_FORECAST'})
   ledger.extend([{'path':str(P/'raw'/name/'body.raw'),'sha256':sha(body),'bytes':len(body),'byte_domain':'HTTP_RESPONSE_BODY_BYTES'},{'path':str(P/'raw'/name/'receipt.json'),'sha256':sha(rr),'bytes':len(rr),'byte_domain':'ORIGINAL_CAPTURE_RECEIPT_UTF8_JSON'},{'path':str(ORIGINAL/('nba-box-'+gid)/'body.raw'),'sha256':sha(br),'bytes':len(br),'byte_domain':'HTTP_RESPONSE_BODY_BYTES'}])
  RESULT['population']={'games':20,'native_player_rows':players,'action_rows':actions,'states':dict(states),'14_count_comparisons':14*players,'historical_new_model_PIT_replay_eligible':0,'games_ledger':games};RESULT['input_hashes']=ledger
 def test_02_actual_future_forecast_complete_denominator_no_outcomes(self):
  raw=(P/'actual_full_forecast/forecast.json').read_bytes();f=json.loads(raw);r=json.loads((P/'actual_full_forecast/ISSUANCE_RECEIPT.json').read_bytes());self.assertEqual(sha(raw),'a60ec92b970e6b417a1b9b48dceca3b2a1140dcf84f7f4ef24a8b57edcfc987f');self.assertEqual(sha(raw),r['forecast_raw_sha256']);self.assertLess(f['input_freeze_at'],f['forecast_at']);self.assertLess(f['forecast_at'],f['event_start_at']);rows=f['law_payload']['rows'];self.assertEqual((len(rows),len({(x['player_id'],x['statistic']) for x in rows})),(140,140));self.assertEqual((sum(x['model'] is not None for x in rows),sum(x['model'] is None for x in rows)),(56,84));self.assertEqual(len({x['player_id'] for x in rows}),35);self.assertFalse(f['historical_predictive_validation']);self.assertFalse(f['C_scoring_admitted']);self.assertTrue(all(x['participation_probability'] is None and x['legal_eligibility'] is None for x in rows));RESULT['target']={'game_id':f['cohort']['game_id'],'start':f['event_start_at'],'freeze':f['input_freeze_at'],'forecast_at':f['forecast_at'],'forecast_raw_sha256':sha(raw),'candidate_denominator':35,'attempt_denominator':140,'forecast_records':56,'abstentions':84,'actual_count_outcomes':0,'pending_outcomes':140,'matching_final_target_source_captures':0}
 def test_03_structural_mutation_game_team_actor_population(self):
  name=next(iter(self.pop['sources']));gid=name[4:];body=(P/'raw'/name/'body.raw').read_bytes();box=(ORIGINAL/('nba-box-'+gid)/'body.raw').read_bytes();page=next_data(body)
  for attack in ('game','team','member','final'):
   x=copy.deepcopy(page)
   if attack=='game':x['game']['gameId']='different'
   if attack=='team':next(a for a in x['playByPlay']['actions'] if a['personId'] and a['teamId'])['teamId']=0
   if attack=='member':x['game']['homeTeam']['players'].pop()
   if attack=='final':x['game']['gameStatus']=2
   with self.subTest(attack=attack),self.assertRaises(ValueError):parse_pbp(enc(x),box,gid)
 def test_04_late_publicationclaims_hashes_rejected_without_admission(self):
  name=next(iter(self.pop['sources']));body=(P/'raw'/name/'body.raw').read_bytes();r=json.loads((P/'raw'/name/'receipt.json').read_bytes())
  for attack in ('late','publication','correction','altered'):
   with self.subTest(attack=attack),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);(root/name).mkdir();rr=copy.deepcopy(r);bb=body
    if attack=='late':rr['ingested_at']='2099-01-01T00:00:00+00:00'
    if attack=='publication':rr['source_published_at']=rr['retrieval_started_at']
    if attack=='correction':rr['correction_history_complete']=True
    if attack=='altered':bb+=b' '
    receipt=json.dumps(rr).encode();(root/name/'body.raw').write_bytes(bb);(root/name/'receipt.json').write_bytes(receipt);pop=copy.deepcopy(self.pop);pop['sources']={name:dict(pop['sources'][name],receipt_sha256=sha(receipt))};(root/'population.json').write_text(json.dumps(pop))
    with self.assertRaises(ValueError):read_population(root,root/'population.json',ORIGINAL)
if __name__=='__main__':
 try:unittest.main(verbosity=2,exit=False)
 finally:(HERE/'RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n')
