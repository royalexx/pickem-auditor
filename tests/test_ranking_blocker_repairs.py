import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import copy
import unittest
from test_research_packet import minimal_packet,make_fact,NOW,STALE_ISO
import research_packet as rp

class RankingBlockerRepairs(unittest.TestCase):
 def row(self,**extra):
  return dict(id='NHL|Test Player|shots on goal|over',stat='shots on goal',hard_veto=False,data_veto=False,soft_flags=0,role_change=False,**extra)
 def merge(self,p,row):
  v,issues=rp.validate_packet(p,now=NOW);self.assertFalse(issues)
  return rp.merge_into_pipeline(v,[row])[0]
 def test_corrected_status_clears_only_packet_owned_veto(self):
  p=minimal_packet();p['availability']['Test Player']['status']=None
  first=self.merge(p,self.row());self.assertEqual(first['data_veto'],'yes')
  p['availability']['Test Player']['status']=make_fact('active')
  second=self.merge(p,first)
  self.assertFalse(second['data_veto']);self.assertNotIn('availability_issue',second)
  self.assertEqual(second,self.merge(p,second))
 def test_original_veto_survives_refresh(self):
  p=minimal_packet();row=self.row();row['data_veto']=True
  self.assertTrue(self.merge(p,self.merge(p,row))['data_veto'])
 def test_removed_weather_fact_cannot_reuse_old_override(self):
  p=minimal_packet();first=self.merge(p,self.row())
  self.assertFalse(first['outdoor'])
  p['weather']={}
  second=self.merge(p,first)
  self.assertNotIn('outdoor',second);self.assertEqual(second['data_veto'],'yes')
 def test_unrelated_game_does_not_block_but_teammate_does(self):
  p=minimal_packet();p['index']['by_player']['Other']={'sport':'NHL','team':'TOR','game':'TOR@CGY'}
  p['availability']['Other']={'status':make_fact('out',retrieved_at=STALE_ISO)}
  merged,errors=rp.prepare_candidates(p,[self.row()],NOW)
  self.assertEqual(len(merged),1);self.assertEqual(errors,[])
  p['index']['by_player']['Other'].update(team='BOS',game='BOS@NSH')
  merged,errors=rp.prepare_candidates(p,[self.row()],NOW)
  self.assertEqual(merged,[]);self.assertEqual(errors[0]['reason'],'RESEARCH_PACKET_INVALID')
  self.assertIn('availability.Other.status',[x['path'] for x in errors[0]['validation_issues']])
 def test_unrelated_scout_never_blocks_candidate(self):
  p=minimal_packet();p['scouting']={'NHL|Other|shots on goal|over':{'evidence':{'opportunity':make_fact('x',retrieved_at=STALE_ISO)}}}
  merged,errors=rp.prepare_candidates(p,[self.row()],NOW)
  self.assertEqual(len(merged),1);self.assertFalse(errors)

class MarketClockTests(unittest.TestCase):
 def test_saved_prep_age_advances_at_grading(self):
  import pickem_math as pm
  from datetime import timedelta
  row=dict(id='NBA|P|points|over',stat='points',dist='poisson',side='over',line=10.5,baseline_mean=12,baseline_n=20,q_market=.6,retrieved_minutes_ago=1,market_retrieved_at=NOW.isoformat(),soft_flags=0,mechanisms=1,hard_veto=False,data_veto=False,research_checklist=True)
  result=pm.evaluate_candidate(row,now=NOW+timedelta(hours=2))
  self.assertFalse(result['grade']['market_valid']);self.assertEqual(result['final_rank'],'Unranked')
 def test_future_market_stamp_rejected(self):
  import pickem_math as pm
  from datetime import timedelta
  with self.assertRaises(pm.PickemError):
   pm.evaluate_candidate({'market_retrieved_at':(NOW+timedelta(minutes=1)).isoformat()},now=NOW)
 def test_live_audit_rejects_undated_legacy_prep(self):
  rows,errors=rp.prepare_candidates(minimal_packet(),[{'id':'NHL|Test Player|shots on goal|over','retrieved_minutes_ago':0}],NOW,require_market_clock=True)
  self.assertEqual(rows,[]);self.assertEqual(errors[0]['reason'],'MARKET_TIMESTAMP_MISSING')

class PartialAuditIntegrationTests(unittest.TestCase):
 def test_one_bad_game_does_not_suppress_another_games_tier(self):
  import io,json,tempfile
  from contextlib import redirect_stdout,redirect_stderr
  from unittest.mock import patch
  from test_verified_reports import VerifiedReportTests
  from test_shared_context import NOW as clock
  from verified_reports import apply_reports
  import usage_baseline as ub
  c,data,packet,report=VerifiedReportTests().setup_case()
  packet=apply_reports(packet,report,clock)
  packet['index']['by_player']['Other']={'sport':'NBA','team':'V','game':'V@W','player_id':'Q'}
  packet['availability']['Other']={'status':make_fact('out',retrieved_at=STALE_ISO)}
  other={**c,'id':'NBA|Other|points|over','team':'V','player_id':'Q'}
  with tempfile.TemporaryDirectory() as directory,patch.object(ub,'load',return_value=data):
   root=Path(directory);(root/'packet.json').write_text(json.dumps(packet));(root/'prep.jsonl').write_text('\n'.join(json.dumps(r) for r in [c,other]))
   output=io.StringIO()
   with redirect_stdout(output),redirect_stderr(io.StringIO()):
    rc=rp.main(['audit','--packet',str(root/'packet.json'),'--prep',str(root/'prep.jsonl'),'--now',clock.isoformat()])
  rows={r['id']:r for r in map(json.loads,output.getvalue().splitlines())}
  self.assertEqual(rc,1);self.assertEqual(len(rows),2)
  self.assertEqual(rows[c['id']]['final_rank'],'Tier 2')
  self.assertEqual(rows[other['id']]['reason'],'RESEARCH_PACKET_INVALID')
