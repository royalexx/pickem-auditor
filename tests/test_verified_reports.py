import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_shared_context import baseline, NOW, fact
import research_packet as rp
import pickem_math as pm
import usage_baseline as ub
import fetch_slate as fs
import shared_context as sc
from verified_reports import apply_reports

class VerifiedReportTests(unittest.TestCase):
 def setup_case(self):
  c,d=baseline();c.update(id='NBA|P|points|over',soft_flags=0,mechanisms=0,hard_veto=False,data_veto=False,research_checklist=True,q_market=.70,retrieved_minutes_ago=1)
  p=rp.empty_template(c['game_date']);p['index']['by_player']['P']={'sport':'NBA','player_id':'P','team':'T','game':'T@U'}
  p['scouting'][c['id']]=c['scouting']
  p['mechanisms'][c['id']]=[{'type':'workload','description':'Synthetic test workload evidence','supports_side':'over','sources':[fact('synthetic workload evidence')]}]
  report={'date':c['game_date'],'reviewer':'test fixture','entries':[dict(player='P',player_id='P',sport='NBA',team='T',game='T@U',status='active',source_url='https://www.nba.com/test-fixture',quote='P is active for this game.',retrieved_at=NOW.isoformat(),published_at=NOW.isoformat(),source_kind='team',basis='explicit_game_report',source_read=True)]}
  return c,d,p,report
 def test_real_cache_report_merge_and_pipeline_can_rank(self):
  c,data,p,report=self.setup_case()
  row={k:c[k] for k in ('sport','team','stat','player_id','game_date')}
  row.update(source_url=data['source_url'],retrieved_at=NOW.isoformat())
  fs.apply_log_summary(row,[dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in data['observations']])
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'PICKEM_DATA_DIR':directory}):
   ub.persist([row],directory)
   validated,issues=rp.validate_packet(p,now=NOW);self.assertFalse(issues)
   blocked=pm.evaluate_candidate(rp.merge_into_pipeline(validated,[c])[0],now=NOW)
   self.assertEqual(blocked['final_rank'],'Unranked')
   reviewed=apply_reports(p,report,NOW)
   validated,issues=rp.validate_packet(reviewed,now=NOW);self.assertFalse(issues)
   result=pm.evaluate_candidate(rp.merge_into_pipeline(validated,[c])[0],now=NOW)
   self.assertEqual(result['final_rank'],'Tier 2',result)
   self.assertEqual(result['engine_a'],blocked['engine_a'])
   self.assertEqual(result['engine_b'],blocked['engine_b'])
 def test_out_does_not_become_an_under_pick(self):
  c,data,p,report=self.setup_case();report['entries'][0]['status']='out'
  p=apply_reports(p,report,NOW);v,issues=rp.validate_packet(p,now=NOW)
  with patch.object(ub,'load',return_value=data):r=pm.evaluate_candidate(rp.merge_into_pipeline(v,[c])[0],now=NOW)
  self.assertNotIn(r['final_rank'],('Tier 1','Tier 2','Tier 3','Watchlist'))
 def test_invalid_reports_never_mutate_packet(self):
  for changes in [{'source_read':False},{'basis':'projected_lineup'},{'team':'WRONG'}, {'basis':'official_inactives'}, {'uplift':1.2}, {'retrieved_at':'2026-10-25T12:00:00Z'}]:
   c,d,p,r=self.setup_case();original=copy.deepcopy(p);r['entries'][0].update(changes)
   with self.assertRaises(ValueError):apply_reports(p,r,NOW)
   self.assertEqual(p,original)
 def test_conflicting_report_needs_resolution_and_keeps_previous(self):
  c,d,p,r=self.setup_case();p['availability']['P']={'status':fact('out')}
  with self.assertRaises(ValueError):apply_reports(p,r,NOW)
  r['entries'][0]['conflict_resolution']='Source explicitly corrects the earlier out designation.'
  result=apply_reports(p,r,NOW)
  self.assertEqual(result['_source_conflicts'][-1]['previous']['value'],'out')
 def test_unsupported_context_is_watchlist_without_probability_bonus(self):
  c,data,p,report=self.setup_case();p=apply_reports(p,report,NOW)
  p['scouting'][c['id']]['event_context']={'events':[{'player_id':'Q','availability':fact('out'),'effective_at':fact('out')['effective_at']}]}
  v,issues=rp.validate_packet(p,now=NOW);self.assertFalse(issues)
  with tempfile.TemporaryDirectory() as directory,patch.object(ub,'load',return_value=data),patch.object(sc,'history_path',return_value=Path(directory)/'missing.json'):
   result=pm.evaluate_candidate(rp.merge_into_pipeline(v,[c])[0],now=NOW)
  self.assertEqual(result['final_rank'],'Watchlist',result)
  self.assertEqual(result['reason'],'CONTEXT_UNSUPPORTED_BASELINE_ONLY')
  self.assertFalse(result['shared_context']['applied'])
  self.assertEqual(result['grade']['q_model'],result['blend']['q_win'])
 def test_duplicate_effect_cannot_use_baseline_fallback(self):
  c,data,p,report=self.setup_case();p=apply_reports(p,report,NOW)
  event={'player_id':'Q','availability':fact('out'),'effective_at':fact('out')['effective_at']}
  p['scouting'][c['id']]['event_context']={'events':[event,event]}
  v,issues=rp.validate_packet(p,now=NOW)
  with patch.object(ub,'load',return_value=data):result=pm.evaluate_candidate(rp.merge_into_pipeline(v,[c])[0],now=NOW)
  self.assertEqual(result['final_rank'],'Unranked');self.assertNotIn('baseline_only',result['shared_context'])

class HistoryFreshnessTests(unittest.TestCase):
 def test_morning_history_survives_evening_but_not_next_day(self):
  from datetime import timedelta
  c,data=baseline();row={k:c[k] for k in ('sport','team','stat','player_id','game_date')}
  row.update(source_url=data['source_url'],retrieved_at=(NOW-timedelta(hours=8)).isoformat())
  fs.apply_log_summary(row,[dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in data['observations']])
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'PICKEM_DATA_DIR':directory}):
   ub.persist([row],directory)
   self.assertTrue(ub.verify_a(c,NOW))
   with self.assertRaises(ValueError):ub.load(c,NOW+timedelta(days=1))
 def test_missing_metadata_baseline_only_but_duplicate_still_blocks(self):
  from test_shared_context import JointAllocationTests
  c,a,b,blend,context=JointAllocationTests().setup_case()
  context['events'][0]['availability'].pop('event_id')
  out=sc.apply(c,a,b,blend,context,NOW)
  self.assertEqual(out['ranking_ceiling'],'Watchlist');self.assertFalse(out['applied'])
  context['events']*=2
  out=sc.apply(c,a,b,blend,context,NOW)
  self.assertNotIn('baseline_only',out);self.assertFalse(out['eligible'])
