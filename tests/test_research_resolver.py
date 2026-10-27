import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import unittest
from datetime import datetime,timezone
import research_packet as rp
from research_resolver import resolve,team_code
import context_feeds as cf

class ResolverTests(unittest.TestCase):
 def packet(self):
  p=rp.empty_template('2026-10-26');p['index']['by_player']['Player']={'team':'TOR','sport':'NHL','game':'TOR@CGY'}
  p['availability']['Player']={'status':None,'primary_source':None};return p
 def scoreboard(self,state='pre',indoor=True):
  return {'events':[{'id':'1','date':'2026-10-27T00:30:00Z','status':{'type':{'state':state}},'competitions':[{'venue':{'indoor':indoor},'competitors':[{'team':{'abbreviation':'TOR'}},{'team':{'abbreviation':'CGY'}}]}]}]}
 def now(self):return datetime(2026,10,26,23,tzinfo=timezone.utc)
 def test_resolves_observed_fields_and_records_attempts(self):
  def fetch(url,**kw):
   if 'scoreboard' in url:return self.scoreboard()
   return {'header':{'id':'1','competitions':[{'status':{'type':{'state':'pre'}}}]},'rosters':[{'team':{'abbreviation':'TOR'},'roster':[{'athlete':{'displayName':'Player'},'active':True}]}]}
  source=self.packet()
  source['availability']['Player']['status']=cf.confirmed_fact('old injury designation','questionable','https://old.test',self.now().isoformat())
  p,report=resolve(source,['NHL|Player|shots on goal|over'],fetch,now=self.now())
  self.assertEqual(p['_source_conflicts'][0]['resolution'],'explicit_game_active_roster')
  self.assertTrue(p['weather']['TOR@CGY']['indoor']['value'])
  self.assertEqual(p['availability']['Player']['status']['value'],'active')
  self.assertNotIn('published_at',p['availability']['Player']['status'])
  self.assertEqual(len(report['attempts']),3)
 def test_roster_membership_without_flag_is_unknown(self):
  def fetch(url,**kw):
   if 'scoreboard' in url:return self.scoreboard()
   return {'header':{'id':'1','competitions':[{'status':{'type':{'state':'pre'}}}]},'rosters':[{'team':{'abbreviation':'TOR'},'roster':[{'athlete':{'displayName':'Player'}}]}]}
  p,r=resolve(self.packet(),['NHL|Player|shots on goal|over'],fetch,now=self.now())
  self.assertIsNone(p['availability']['Player']['status'])
  self.assertEqual(r['resolved_statuses'],[])
 def test_started_game_never_supplies_pregame_availability(self):
  calls=[]
  def fetch(url,**kw):calls.append(url);return self.scoreboard(state='in')
  p,r=resolve(self.packet(),['NHL|Player|shots on goal|over'],fetch,now=self.now())
  self.assertEqual(r['started_games'],['TOR@CGY']);self.assertEqual(len(calls),1)
  self.assertIsNone(p['availability']['Player']['status'])
 def test_source_failure_preserves_old_facts_and_notes(self):
  p=self.packet();p['_feed_notes']=['keep'];p['weather']['TOR@CGY']={'indoor':cf.confirmed_fact('indoor',True,'https://source.test',self.now().isoformat())}
  def fail(*a,**k):raise OSError('unavailable')
  r,report=resolve(p,['NHL|Player|shots on goal|over'],fail,now=self.now())
  self.assertEqual(r['_feed_notes'],['keep']);self.assertTrue(r['weather']['TOR@CGY']['indoor']['value'])
  self.assertEqual(report['attempts'][0]['status'],'source_failed')
 def test_irrelevant_tasks_are_not_generated(self):
  p=rp.empty_template('2026-10-26');p['index']['by_player']['Player']={'team':'DAL','sport':'NFL','game':'DAL@PHI'}
  gaps=cf.gap_paths_for_shortlist(p,['NFL|Player|receptions|over'],now=self.now())
  paths=[g['path'] for g in gaps]
  self.assertFalse(any(x.startswith('lineup.') for x in paths))
  self.assertIn('weather.DAL@PHI.indoor',paths)
  self.assertNotIn('weather.DAL@PHI.gust_mph',paths)

class TeamAliasTests(unittest.TestCase):
 def test_sport_specific_aliases(self):
  self.assertEqual(team_code('LA','NHL'),'LAK')
  self.assertEqual(team_code('LA','NFL'),'LA')
  self.assertEqual(team_code('TB','NHL'),'TBL')
