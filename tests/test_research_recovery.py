import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from datetime import datetime,timedelta,timezone
import copy
import unittest
from research_recovery import recover
from research_packet import empty_template
from context_feeds import confirmed_fact,merge_packet_no_clobber
from probability_blend import preview_70_30
import pickem_math as pm

NOW=datetime(2026,10,26,21,50,tzinfo=timezone.utc)
ST=NOW.isoformat()
URL='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=20261026'

class ResearchRecoveryTests(unittest.TestCase):
 def packet(self):
  p=empty_template('2026-10-26')
  p['index']['by_player']['Test Player']={'sport':'NHL','team':'EDM','game':'DET@EDM','player_id':1}
  p['weather']['DET@EDM']={'indoor':None}
  p['availability']['Test Player']={'status':None, 'primary_source':None}
  return p
 def test_recovers_real_sourced_venue_without_fake_active_status(self):
  source=self.packet();source['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',True,URL,ST)
  out,r=recover(self.packet(),source,now=NOW)
  self.assertTrue(out['weather']['DET@EDM']['indoor']['value'])
  self.assertIsNone(out['availability']['Test Player']['status'])
  self.assertEqual(r['recovered_facts'],1)
 def test_rejects_old_or_wrong_identity(self):
  p=self.packet();s=self.packet()
  s['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',True,URL,(NOW-timedelta(minutes=90)).isoformat())
  out,r=recover(p,s,now=NOW)
  self.assertIsNone(out['weather']['DET@EDM']['indoor'])
  s['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',True,URL,ST)
  s['index']['by_player']['Test Player']['player_id']=99
  out,r=recover(p,s,now=NOW)
  self.assertIsNone(out['weather']['DET@EDM']['indoor']);self.assertEqual(r['identity_rejected'],1)
 def test_conflict_is_fail_closed(self):
  a=self.packet();b=self.packet()
  a['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',True,URL,ST)
  b['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',False,'https://www.nhl.com/gamecenter',ST)
  out,r=recover(a,b,now=NOW)
  self.assertIsNone(out['weather']['DET@EDM']['indoor']);self.assertEqual(len(r['conflicts']),1)
 def test_explicit_wrong_date_rejected(self):
  old=self.packet();old['date']='2026-10-25'
  with self.assertRaises(ValueError):recover(self.packet(),old,now=NOW)
 def test_refresh_never_replaces_newer_fact_with_old(self):
  a=self.packet();b=self.packet()
  a['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',True,URL,ST)
  b['weather']['DET@EDM']['indoor']=confirmed_fact('indoor',False,URL,(NOW-timedelta(minutes=25)).isoformat())
  merged=merge_packet_no_clobber(a,b)
  self.assertTrue(merged['weather']['DET@EDM']['indoor']['value'])

class DiagnosticSafetyTests(unittest.TestCase):
 def test_70_30_is_never_deployed(self):
  a={'q_win_robust':.7,'q_push_robust':0,'sample_block':False,'observation_ids_verified':True}
  b={'q_win_b':.6,'q_push_b':0,'reliable':True,'abstain':False,'baseline_origin':'collector_observations'}
  result=preview_70_30(a,b)
  self.assertAlmostEqual(result['q_win'],.67)
  self.assertFalse(result['publication_eligible'])
  self.assertIsNone(preview_70_30(a,{**b,'reliable':False}))
 def test_large_gap_stays_watchlist_and_has_review_explanation(self):
  grade=pm.grade(.75,.63,0,20)
  self.assertEqual(grade['probability_rank'],'WATCHLIST')
  self.assertEqual(grade['gap_review']['cap'],'Watchlist')
  self.assertFalse(grade['gap_review']['override_authorized'])

if __name__=='__main__':unittest.main()

class NhlInjuryFeedTests(unittest.TestCase):
 def test_explicit_injury_out_only_and_no_active_by_omission(self):
  from research_resolver import resolve
  p=empty_template('2026-10-26')
  for name in ('Hurt','Healthy'):
   p['index']['by_player'][name]={'sport':'NHL','team':'EDM','game':'DET@EDM','player_id':name}
   p['availability'][name]={'status':None,'primary_source':None}
  def fetch(url, **kw):
   if 'scoreboard' in url:
    return {'events':[{'id':'123','date':'2026-10-26T23:00:00Z','status':{'type':{'state':'pre'}},
      'competitions':[{'venue':{'indoor':True}, 'competitors':[{'team':{'abbreviation':'DET'}},{'team':{'abbreviation':'EDM'}}]}]}]}
   if 'injuries' in url:
    return {'injuries':[{'team':{'abbreviation':'EDM'},'injuries':[
      {'athlete':{'displayName':'Hurt'},'status':'Out'},
      {'athlete':{'displayName':'Healthy'},'status':'day-to-day'}]}]}
   return {'header':{'id':'123','competitions':[{'status':{'type':{'state':'pre'}}}]}, 'rosters':[]}
  result,r=resolve(p,['NHL|Hurt|shots on goal|under','NHL|Healthy|shots on goal|over'],fetch,now=NOW)
  self.assertEqual(result['availability']['Hurt']['status']['value'],'out')
  self.assertIsNone(result['availability']['Healthy']['status'])
  self.assertTrue(result['weather']['DET@EDM']['indoor']['value'])
  self.assertEqual(r['attempts'][-1]['resolved_negative_statuses'],1)
